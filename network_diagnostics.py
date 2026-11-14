"""Read-only macOS network diagnostics for the local CIA Print server.

Never present CLAT (192.0.0.0/29), loopback or a public IPv4 address as a
reachable iPad LAN URL. A listed LAN address is a *candidate*, not a
guarantee that tethering/firewall/client isolation permits access.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import subprocess

CLAT = ipaddress.ip_network("192.0.0.0/29")
LAN = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
LINK_LOCAL = ipaddress.ip_network("169.254.0.0/16")
SHARED = ipaddress.ip_network("100.64.0.0/10")
# Virtual and peer-to-peer links are not reliable destinations for an iPad.
SKIP_INTERFACES = ("utun", "awdl", "llw", "lo", "gif", "stf", "anpi", "ap")


def run_readonly(command: list[str]) -> str:
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=4, check=False
        )
        return done.stdout if done.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def parse_ifconfig(output: str) -> dict:
    """Extract per-interface IPv4/IPv6 addresses without assuming en0/en1."""
    interfaces = {}
    current = None
    for line in output.splitlines():
        header = re.match(r"^([a-zA-Z0-9_.-]+):\s+flags=", line)
        if header:
            current = header.group(1)
            interfaces[current] = {"ipv4": [], "ipv6": [], "active": "UP" in line.split("<", 1)[-1].split(">", 1)[0].split(",")}
            continue
        if current is None:
            continue
        ipv4 = re.match(r"^\s*inet\s+(\d+\.\d+\.\d+\.\d+)\b", line)
        ipv6 = re.match(r"^\s*inet6\s+([a-fA-F0-9:]+)", line)
        if ipv4:
            interfaces[current]["ipv4"].append(ipv4.group(1))
        if ipv6:
            interfaces[current]["ipv6"].append(ipv6.group(1))
    return interfaces


def classify_ipv4(address: str) -> str:
    try:
        addr = ipaddress.ip_address(address)
    except ValueError:
        return "invalid"
    if not isinstance(addr, ipaddress.IPv4Address):
        return "invalid"
    if addr in CLAT:
        return "clat"
    if any(addr in network for network in LAN):
        return "lan"
    if addr in SHARED:
        return "shared"
    if addr in LINK_LOCAL:
        return "link_local"
    if addr.is_loopback or addr.is_unspecified:
        return "loopback"
    return "other"


def inspect_network() -> dict:
    interfaces = parse_ifconfig(run_readonly(["/sbin/ifconfig", "-a"]))
    addresses = set()
    ipv6_present = False
    for name, details in interfaces.items():
        if name == "lo0" or not details["active"] or name.startswith(SKIP_INTERFACES):
            continue
        addresses.update(details["ipv4"])
        ipv6_present |= bool(details["ipv6"])

    # Additional dynamic discovery for setups where ifconfig is unavailable.
    if not interfaces:
        for name in ("en0", "en1", "en2", "en3", "en4", "bridge0", "bridge100"):
            address = run_readonly(["/usr/sbin/ipconfig", "getifaddr", name]).strip()
            if address:
                addresses.add(address)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass

    gateway = ""
    route_interface = ""
    route = run_readonly(["/sbin/route", "-n", "get", "default"])
    for line in route.splitlines():
        item = line.strip()
        if item.startswith("gateway:"):
            gateway = item.split(":", 1)[1].strip()
        elif item.startswith("interface:"):
            route_interface = item.split(":", 1)[1].strip()

    grouped = {kind: [] for kind in (
        "lan", "shared", "clat", "link_local", "loopback", "other", "invalid"
    )}
    for address in sorted(addresses):
        grouped[classify_ipv4(address)].append(address)
    # RFC6598 shared space is sometimes used for tethering. It is only a candidate,
    # never a claim that an iPad can reach the Mac across the hotspot.
    usable = grouped["lan"] + grouped["shared"]
    return {
        "interfaces": interfaces,
        "addresses": grouped,
        "usable": usable,
        "ipv6_present": ipv6_present,
        "gateway": gateway,
        "route_interface": route_interface,
    }


def diagnosis(report: dict) -> tuple[str, list[str]]:
    types = report["addresses"]
    if report["usable"]:
        return "LAN_IP_FOUND", [
            "表示したURLは接続候補です。iPadとMacを同じネットワークに接続してください。",
            "iPadで開けない場合は端末間通信の制限・VPN・Macのファイアウォールを確認してください。",
            "MacのSafariで http://127.0.0.1:8765/ が開けるか確認してください。",
            "100.64.x.x〜100.127.x.x は共有アドレスです。通信可否は必ずiPadから確認してください。",
        ]
    if types["clat"]:
        return "CLAT_IPV6_ONLY", [
            "192.0.0.2 等はIPv4通信用のCLATアドレスです。iPad向けURLには使用できません。",
            "iPhone/Androidのテザリングを切断し、再接続してIPv4アドレスが配布されるか確認してください。",
            "Mac・iPadを同じWi-Fiに接続してください。改善しなければ別のWi-Fi/ルーターを試してください。",
            "テザリングがIPv6のみの場合、接続機器同士のIPv4通信は保証されません。",
            "手動で192.0.0.2を許可したり、根拠なく固定IPを設定したりしないでください。",
        ]
    if types["link_local"]:
        return "LINK_LOCAL_ONLY", [
            "169.254.x.x はDHCPから通常のIPv4設定を取得できなかった可能性があります。",
            "Wi-Fiの再接続、DHCPリースの更新、テザリング元の接続状態を確認してください。",
        ]
    if not any(types.values()):
        return "NO_IPV4", [
            "Macに利用可能なIPv4アドレスが見つかりません。",
            "Wi-Fi/テザリング接続を確認し、必要なら再接続・DHCP更新を行ってください。",
            "IPv6のみの回線では、このIPv4ベースの案内URLを作成できません。",
        ]
    return "NO_LAN_IPV4", [
        "MacにはIPv4がありますが、iPad向けに案内できるプライベートLANアドレスではありません。",
        "端末が同じWi-Fiまたは端末間通信可能なテザリングに接続されているか確認してください。",
        "VPN/仮想アダプター経由のアドレスは実際にiPadから到達できるとは限りません。",
    ]


def format_guidance(report: dict, port: int) -> str:
    code, steps = diagnosis(report)
    lines = ["", " ネットワーク診断: " + code]
    if report["route_interface"] or report["gateway"]:
        lines.append(
            " 使用中の経路: " +
            (report["route_interface"] or "不明") +
            " / gateway " + (report["gateway"] or "不明")
        )
    for kind in ("lan", "shared", "clat", "link_local", "other"):
        values = report["addresses"].get(kind, [])
        if values:
            lines.append(" " + kind + ": " + ", ".join(values))
    if report["usable"]:
        lines.extend(
            f" 参加者画面  http://{address}:{port}/\n 管理画面    http://{address}:{port}/admin/"
            for address in report["usable"]
        )
    else:
        lines.append(" iPad向けURLを表示できません。以下を確認してください。")
    lines.extend(f"  - {step}" for step in steps)
    lines.append(f" Mac自身での確認URL: http://127.0.0.1:{port}/")
    lines.append(" 注: iPadからの到達可否はMacだけでは確認できません。")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_guidance(inspect_network(), 8765))
