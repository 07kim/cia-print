"""Regression tests for local network discovery and actionable diagnostics."""
import unittest
from unittest.mock import patch

import network_diagnostics as nd


def sample_report(**overrides):
    data = {
        "interfaces": {},
        "addresses": {
            "lan": [], "shared": [], "clat": [], "link_local": [], "loopback": [],
            "other": [], "invalid": [],
        },
        "usable": [],
        "ipv6_present": False,
        "gateway": "",
        "route_interface": "",
    }
    data.update(overrides)
    return data


class NetworkDiagnosticsTests(unittest.TestCase):
    def test_classifies_typical_iphone_hotspot(self):
        self.assertEqual(nd.classify_ipv4("172.20.10.2"), "lan")

    def test_iphone_hotspot_exact_observed_address(self):
        self.assertEqual(nd.classify_ipv4("172.20.10.14"), "lan")

    def test_all_private_lan_ranges(self):
        for address in ("10.2.3.4", "172.20.10.14", "192.168.75.2"):
            with self.subTest(address=address):
                self.assertEqual(nd.classify_ipv4(address), "lan")

    def test_carrier_shared_tethering_range(self):
        self.assertEqual(nd.classify_ipv4("100.64.1.2"), "shared")
        self.assertEqual(nd.classify_ipv4("100.127.255.254"), "shared")
        self.assertEqual(nd.classify_ipv4("100.128.0.1"), "other")

    def test_inactive_and_virtual_interfaces_not_offered(self):
        raw = (
            "en0: flags=8863<UP,BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 172.20.10.14 netmask 0xfffffff0\n"
            "en9: flags=8822<BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 192.168.43.3 netmask 0xffffff00\n"
            "utun0: flags=8051<UP,POINTOPOINT,RUNNING> mtu 1380\n"
            "\tinet 10.8.0.2 netmask 0xffffff00\n"
        )
        def fake_run(command):
            if command[:2] == ["/sbin/ifconfig", "-a"]:
                return raw
            return ""
        with patch.object(nd, "run_readonly", side_effect=fake_run), \
             patch.object(nd.socket, "socket", side_effect=OSError("offline")):
            report = nd.inspect_network()
        self.assertEqual(report["usable"], ["172.20.10.14"])

    def test_shared_address_has_candidate_url_and_warning(self):
        types = {
            "lan": [], "shared": ["100.66.1.2"], "clat": [],
            "link_local": [], "loopback": [], "other": [], "invalid": [],
        }
        report = sample_report(addresses=types, usable=["100.66.1.2"])
        output = nd.format_guidance(report, 8765)
        self.assertIn("http://100.66.1.2:8765/", output)
        self.assertIn("共有アドレス", output)

    def test_classifies_android_hotspot(self):
        self.assertEqual(nd.classify_ipv4("192.168.43.20"), "lan")

    def test_classifies_university_private_lan(self):
        self.assertEqual(nd.classify_ipv4("10.11.12.13"), "lan")

    def test_clat_is_not_a_lan_url(self):
        self.assertEqual(nd.classify_ipv4("192.0.0.2"), "clat")

    def test_loopback_is_not_a_lan_url(self):
        self.assertEqual(nd.classify_ipv4("127.0.0.1"), "loopback")

    def test_link_local_has_separate_guidance(self):
        self.assertEqual(nd.classify_ipv4("169.254.1.3"), "link_local")

    def test_non_private_address_not_advertised(self):
        self.assertEqual(nd.classify_ipv4("8.8.8.8"), "other")

    def test_invalid_addresses_are_safe(self):
        self.assertEqual(nd.classify_ipv4("not-an-address"), "invalid")

    def test_dynamic_interface_names(self):
        raw = (
            "en7: flags=8863<UP,BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 172.20.10.4 netmask 0xffffff00\n"
            "\tinet6 fe80::1234%en7 prefixlen 64\n"
            "en0: flags=8863<UP,BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 192.0.0.2 netmask 0xffffffff\n"
        )
        parsed = nd.parse_ifconfig(raw)
        self.assertEqual(parsed["en7"]["ipv4"], ["172.20.10.4"])
        self.assertEqual(parsed["en0"]["ipv4"], ["192.0.0.2"])
        self.assertEqual(parsed["en7"]["ipv6"], ["fe80::1234"])

    def test_real_clat_diagnostic(self):
        addresses = {
            "lan": [], "shared": [], "clat": ["192.0.0.2"], "link_local": [],
            "loopback": [], "other": [], "invalid": [],
        }
        r = sample_report(addresses=addresses,
                          gateway="192.0.0.1", route_interface="en0",
                          ipv6_present=True)
        code, steps = nd.diagnosis(r)
        self.assertEqual(code, "CLAT_IPV6_ONLY")
        output = nd.format_guidance(r, 8765)
        self.assertIn("CLAT", output)
        self.assertIn("iPad向けURLを表示できません", output)
        self.assertNotIn("http://192.0.0.2:8765/", output)

    def test_legacy_report_without_shared_does_not_crash(self):
        addresses = {
            "lan": [], "clat": ["192.0.0.2"],
            "link_local": [], "loopback": [], "other": [], "invalid": [],
        }
        report = sample_report(addresses=addresses)
        self.assertIn("CLAT_IPV6_ONLY", nd.format_guidance(report, 8765))

    def test_private_ipv4_shows_candidate_url(self):
        addresses = {
            "lan": ["172.20.10.2"], "shared": [], "clat": [], "link_local": [],
            "loopback": [], "other": [], "invalid": [],
        }
        r = sample_report(addresses=addresses, usable=["172.20.10.2"])
        self.assertEqual(nd.diagnosis(r)[0], "LAN_IP_FOUND")
        self.assertIn("http://172.20.10.2:8765/", nd.format_guidance(r, 8765))
        self.assertIn("端末間通信", nd.format_guidance(r, 8765))

    def test_ipv6_only_without_ipv4(self):
        r = sample_report(ipv6_present=True)
        self.assertEqual(nd.diagnosis(r)[0], "NO_IPV4")

    def test_link_local_only_explains_dhcp(self):
        addresses = {
            "lan": [], "shared": [], "clat": [], "link_local": ["169.254.1.2"],
            "loopback": [], "other": [], "invalid": [],
        }
        self.assertEqual(nd.diagnosis(sample_report(addresses=addresses))[0],
                         "LINK_LOCAL_ONLY")

    def test_public_ipv4_not_advertised(self):
        addresses = {
            "lan": [], "shared": [], "clat": [], "link_local": [], "loopback": [],
            "other": ["8.8.8.8"], "invalid": [],
        }
        r = sample_report(addresses=addresses)
        self.assertEqual(nd.diagnosis(r)[0], "NO_LAN_IPV4")
        self.assertNotIn("http://8.8.8.8:8765/", nd.format_guidance(r, 8765))

    def test_collects_from_all_interfaces_and_route(self):
        ifconfig = (
            "lo0: flags=8049<UP,LOOPBACK> mtu 16384\n"
            "\tinet 127.0.0.1 netmask 0xff000000\n"
            "en7: flags=8863<UP,BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 172.20.10.8 netmask 0xffffff00\n"
            "en0: flags=88e3<UP,BROADCAST,RUNNING> mtu 1500\n"
            "\tinet 192.0.0.2 netmask 0xffffffff\n"
        )
        def fake_run(command):
            if command[:2] == ["/sbin/ifconfig", "-a"]:
                return ifconfig
            if command[:4] == ["/sbin/route", "-n", "get", "default"]:
                return "gateway: 192.0.0.1\ninterface: en0\n"
            return ""
        with patch.object(nd, "run_readonly", side_effect=fake_run), \
             patch.object(nd.socket, "socket", side_effect=OSError("offline")):
            report = nd.inspect_network()
        self.assertEqual(report["usable"], ["172.20.10.8"])
        self.assertEqual(report["addresses"]["clat"], ["192.0.0.2"])
        self.assertEqual(report["gateway"], "192.0.0.1")

    def test_mac_without_ifconfig_is_not_fatal(self):
        with patch.object(nd, "run_readonly", return_value=""), \
             patch.object(nd.socket, "socket", side_effect=OSError("offline")):
            report = nd.inspect_network()
        self.assertEqual(report["usable"], [])
        self.assertEqual(nd.diagnosis(report)[0], "NO_IPV4")


if __name__ == "__main__":
    unittest.main()
