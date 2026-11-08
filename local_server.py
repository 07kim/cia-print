#!/usr/bin/env python3
"""CIA Print local server: iPad Safari -> macOS CUPS -> fixed PDF."""

from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "local-config.json"


def load_config() -> dict:
    defaults = {
        "host": "0.0.0.0",
        "port": 8000,
        "printer_name": "EPSON_EW_M634T_Series",
        "pdf_path": "assets/connection-test.pdf",
        "cooldown_seconds": 15,
    }
    if CONFIG_PATH.exists():
        defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return defaults


CONFIG = load_config()
PRINT_LOCK = threading.Lock()
LAST_ACCEPTED_AT = 0.0


class PrintHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/status":
            pdf = (ROOT / CONFIG["pdf_path"]).resolve()
            self.send_json(
                HTTPStatus.OK,
                {
                    "ready": pdf.is_file(),
                    "printer": CONFIG["printer_name"],
                    "documentAvailable": pdf.is_file(),
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        global LAST_ACCEPTED_AT

        if urlparse(self.path).path != "/api/print":
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "code": "not_found"})
            return

        request_id = self.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
        pdf = (ROOT / CONFIG["pdf_path"]).resolve()
        if not pdf.is_relative_to(ROOT) or not pdf.is_file():
            self.send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"ok": False, "code": "pdf_missing", "message": "印刷する資料が見つかりません。"},
            )
            return

        if not PRINT_LOCK.acquire(blocking=False):
            self.send_json(
                HTTPStatus.CONFLICT,
                {"ok": False, "code": "busy", "message": "別の印刷を処理しています。"},
            )
            return

        try:
            remaining = CONFIG["cooldown_seconds"] - (time.monotonic() - LAST_ACCEPTED_AT)
            if remaining > 0:
                self.send_json(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {
                        "ok": False,
                        "code": "cooldown",
                        "message": "印刷指示はすでに送信されています。用紙が出るまでお待ちください。",
                    },
                )
                return

            try:
                result = subprocess.run(
                    ["lp", "-d", CONFIG["printer_name"], "-n", "1", str(pdf)],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except FileNotFoundError:
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "code": "lp_missing", "message": "Macの印刷機能を起動できません。"},
                )
                return
            except subprocess.TimeoutExpired:
                self.send_json(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    {
                        "ok": False,
                        "code": "unknown_result",
                        "message": "送信結果を確認できません。再度押さず、係員へお知らせください。",
                    },
                )
                return

            if result.returncode != 0:
                print(f"[{request_id}] lp error: {result.stderr.strip()}")
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "code": "rejected", "message": "プリンターが印刷指示を受け付けませんでした。"},
                )
                return

            LAST_ACCEPTED_AT = time.monotonic()
            print(f"[{request_id}] {result.stdout.strip()}")
            self.send_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "requestId": request_id,
                    "message": "印刷指示を送信しました。用紙が出てくるまでお待ちください。",
                },
            )
        finally:
            PRINT_LOCK.release()

    def log_message(self, format: str, *args) -> None:
        print(f"{self.client_address[0]} - {format % args}")


def main() -> None:
    address = (CONFIG["host"], int(CONFIG["port"]))
    server = ThreadingHTTPServer(address, PrintHandler)
    print(f"CIA Print: http://localhost:{address[1]}")
    print(f"Printer: {CONFIG['printer_name']}")
    print(f"Document: {CONFIG['pdf_path']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
