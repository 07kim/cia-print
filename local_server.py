#!/usr/bin/env python3
"""Local print relay for the CIA event iPad terminal."""

from __future__ import annotations

import cgi
import hmac
import json
import secrets
import socket
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "local-config.json"
DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8765,
    "printer_name": "EPSON_EW_M634T_Series",
    "pdf_path": "assets/connection-test.pdf",
    "cooldown_seconds": 15,
    "reset_seconds": 20,
    "access_password": "PRINT",
    "admin_pin": "6340",
}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def local_ip_addresses() -> list[str]:
    """Return usable LAN addresses without depending on a fixed Wi-Fi interface name."""
    addresses: set[str] = set()
    for interface in ("en0", "en1", "en2", "bridge100"):
        try:
            result = subprocess.run(
                ["/usr/sbin/ipconfig", "getifaddr", interface],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                addresses.add(result.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(result[4][0])
    except OSError:
        pass
    return sorted(address for address in addresses if not address.startswith("127."))


def load_config() -> dict:
    config = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return config


CONFIG = load_config()
PRINT_LOCK = threading.Lock()
TOKEN_LOCK = threading.Lock()
TOKENS: dict[str, float] = {}
LAST_PRINT_AT = 0.0


def save_config() -> None:
    CONFIG_PATH.write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def document_path() -> Path:
    candidate = (ROOT / str(CONFIG["pdf_path"])).resolve()
    if ROOT not in candidate.parents:
        raise ValueError("PDF path must remain inside the project directory")
    return candidate


def clean_tokens() -> None:
    now = time.time()
    with TOKEN_LOCK:
        expired = [token for token, expires in TOKENS.items() if expires <= now]
        for token in expired:
            TOKENS.pop(token, None)


def issue_token() -> str:
    clean_tokens()
    token = secrets.token_urlsafe(24)
    with TOKEN_LOCK:
        TOKENS[token] = time.time() + 300
    return token


def consume_token(token: str) -> bool:
    clean_tokens()
    with TOKEN_LOCK:
        expires = TOKENS.pop(token, None)
    return bool(expires and expires > time.time())


def constant_match(value: str, expected: str) -> bool:
    return hmac.compare_digest(str(value), str(expected))


def run_print() -> tuple[bool, str, int]:
    global LAST_PRINT_AT
    pdf = document_path()
    if not pdf.exists():
        return False, "印刷資料が設定されていません。管理者にお知らせください。", 404

    with PRINT_LOCK:
        remaining = int(CONFIG["cooldown_seconds"]) - int(time.time() - LAST_PRINT_AT)
        if remaining > 0:
            return False, f"印刷機を準備しています。{remaining}秒後にもう一度お試しください。", 429

        command = [
            "lp",
            "-d",
            str(CONFIG["printer_name"]),
            "-n",
            "1",
            str(pdf),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"Macからプリンターへ送信できませんでした: {error}", 503
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "印刷命令が失敗しました").strip()
            return False, detail, 503
        LAST_PRINT_AT = time.time()
        return True, (result.stdout or "印刷を受け付けました").strip(), 200


class PrintHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format_string: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64 * 1024:
            raise ValueError("Request is too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def admin_allowed(self) -> bool:
        return constant_match(self.headers.get("X-Admin-PIN", ""), CONFIG["admin_pin"])

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            pdf = document_path()
            self.send_json(
                HTTPStatus.OK,
                {
                    "ready": pdf.exists(),
                    "printer": CONFIG["printer_name"],
                    "documentAvailable": pdf.exists(),
                    "resetSeconds": CONFIG["reset_seconds"],
                },
            )
            return
        if path == "/api/admin/config":
            if not self.admin_allowed():
                self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "管理者PINが違います。"})
                return
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "printerName": CONFIG["printer_name"],
                    "documentName": Path(CONFIG["pdf_path"]).name,
                    "cooldownSeconds": CONFIG["cooldown_seconds"],
                    "resetSeconds": CONFIG["reset_seconds"],
                    "accessPassword": CONFIG["access_password"],
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/unlock":
                data = self.read_json()
                if not constant_match(data.get("password", ""), CONFIG["access_password"]):
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "パスワードが間違っています。"})
                    return
                self.send_json(HTTPStatus.OK, {"ok": True, "token": issue_token()})
                return

            if path == "/api/print":
                auth = self.headers.get("Authorization", "")
                token = auth.removeprefix("Bearer ").strip()
                if not consume_token(token):
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "認証の有効期限が切れました。"})
                    return
                ok, message, status = run_print()
                self.send_json(status, {"ok": ok, "message": message})
                return

            if path == "/api/admin/config":
                if not self.admin_allowed():
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "管理者PINが違います。"})
                    return
                data = self.read_json()
                if data.get("accessPassword"):
                    CONFIG["access_password"] = str(data["accessPassword"])
                if data.get("printerName"):
                    CONFIG["printer_name"] = str(data["printerName"])
                if data.get("adminPin"):
                    CONFIG["admin_pin"] = str(data["adminPin"])
                CONFIG["cooldown_seconds"] = max(0, min(300, int(data.get("cooldownSeconds", CONFIG["cooldown_seconds"]))))
                CONFIG["reset_seconds"] = max(5, min(300, int(data.get("resetSeconds", CONFIG["reset_seconds"]))))
                save_config()
                self.send_json(HTTPStatus.OK, {"ok": True, "message": "設定を保存しました。"})
                return

            if path == "/api/admin/upload":
                if not self.admin_allowed():
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "管理者PINが違います。"})
                    return
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
                )
                upload = form["document"] if "document" in form else None
                if upload is None or not getattr(upload, "file", None):
                    self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": "PDFを選択してください。"})
                    return
                data = upload.file.read(MAX_UPLOAD_BYTES + 1)
                if len(data) > MAX_UPLOAD_BYTES or not data.startswith(b"%PDF-"):
                    self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": "20MB以下のPDFを選択してください。"})
                    return
                target = ROOT / "assets" / "print-document.pdf"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                CONFIG["pdf_path"] = str(target.relative_to(ROOT))
                save_config()
                self.send_json(HTTPStatus.OK, {"ok": True, "message": "印刷資料を差し替えました。"})
                return

            if path == "/api/admin/print":
                if not self.admin_allowed():
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "管理者PINが違います。"})
                    return
                ok, message, status = run_print()
                self.send_json(status, {"ok": ok, "message": message})
                return
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(error)})
            return
        except Exception as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "message": f"処理に失敗しました: {error}"})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})


def serve() -> None:
    host = str(CONFIG["host"])
    port = int(CONFIG["port"])
    server = ThreadingHTTPServer((host, port), PrintHandler)
    addresses = local_ip_addresses()
    print("\n" + "=" * 64)
    print(" CIA PRINT を起動しました")
    print("=" * 64)
    if addresses:
        print("\n iPadのSafariに、次のURLをそのまま入力してください:\n")
        for address in addresses:
            print(f"   参加者画面  http://{address}:{port}/")
            print(f"   管理画面    http://{address}:{port}/admin/\n")
    else:
        print("\n IPアドレスを取得できませんでした。MacのWi-Fi接続を確認してください。\n")
    print(f" プリンター: {CONFIG['printer_name']}")
    print(f" 印刷資料:   {document_path()}")
    print("\n 終了するときは Control + C を押してください。")
    print("=" * 64 + "\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
