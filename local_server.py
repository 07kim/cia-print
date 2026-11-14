#!/usr/bin/env python3
"""Local print relay for the CIA event iPad terminal."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default as email_policy
import hmac
import errno
import ipaddress
import json
import re
import secrets
import socket
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import network_diagnostics

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "local-config.json"
DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8765,
    "printer_name": "EPSON_EW_M634T_Series",
    "pdf_path": "output/pdf/cia-print-a4-monochrome.pdf",
    "cooldown_seconds": 15,
    "reset_seconds": 7,
    "access_password": "いんさつ",
}
ADMIN_ENTRY_PASSWORD = "admin0000"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# The browser intentionally shows a five-second connection phase after unlock.
# Keep a small server-only allowance so the participant still receives the full
# documented 60-second print window after that presentation finishes.
AUTHORIZATION_SECONDS = 70
CLIENT_AUTHORIZATION_SECONDS = 60
PRINT_JOB_MAX_AGE_SECONDS = 60
LAN_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
)


def is_usable_lan_address(address: str) -> bool:
    """Accept addresses that an iPad on the same local network can normally reach."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return isinstance(parsed, ipaddress.IPv4Address) and any(
        parsed in network for network in LAN_NETWORKS
    )


def local_ip_addresses() -> list[str]:
    """Report only candidate RFC1918 LAN addresses, never CLAT 192.0.0.2."""
    return network_diagnostics.inspect_network()["usable"]


def load_config() -> dict:
    config = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return config


CONFIG = load_config()
PRINT_LOCK = threading.Lock()
TOKEN_LOCK = threading.Lock()
TOKENS: dict[str, tuple[float, str]] = {}
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
        expired = [token for token, (expires, _) in TOKENS.items() if expires <= now]
        for token in expired:
            TOKENS.pop(token, None)


def issue_token(client_address: str) -> str:
    clean_tokens()
    token = secrets.token_urlsafe(24)
    with TOKEN_LOCK:
        TOKENS[token] = (time.time() + AUTHORIZATION_SECONDS, client_address)
    return token


def consume_token(token: str, client_address: str) -> bool:
    clean_tokens()
    with TOKEN_LOCK:
        authorization = TOKENS.pop(token, None)
    if not authorization:
        return False
    expires, authorized_address = authorization
    return expires > time.time() and constant_match(authorized_address, client_address)


def constant_match(value: str, expected: str) -> bool:
    # compare_digest accepts ASCII-only str; UTF-8 bytes support Japanese passwords.
    return hmac.compare_digest(str(value).encode("utf-8"), str(expected).encode("utf-8"))


def unlock_destination(password: str) -> str | None:
    """Return the presentation destination for a submitted password."""
    if constant_match(password, ADMIN_ENTRY_PASSWORD):
        return "admin"
    if constant_match(password, CONFIG["access_password"]):
        return "print"
    return None


def clear_stale_print_jobs() -> None:
    """Discard jobs left in CUPS before this event session starts."""
    printer = str(CONFIG["printer_name"])
    try:
        registered = subprocess.run(
            ["lpstat", "-p", printer],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if registered.returncode != 0:
            return
    except (OSError, subprocess.TimeoutExpired):
        return
    try:
        result = subprocess.run(
            ["cancel", "-a", printer],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(" 前回から残っていた印刷待ちを消去しました。")
        else:
            detail = (result.stderr or result.stdout).strip()
            if detail:
                print(f" 印刷待ちの確認: {detail}")
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f" 印刷待ちを確認できませんでした: {error}")


def cancel_print_job(job_id: str) -> None:
    """Expire an unfinished CUPS job so it cannot print after a later reconnect."""
    try:
        subprocess.run(
            ["cancel", job_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def expire_print_job_later(output: str) -> None:
    match = re.search(r"request id is ([^\s]+)", output)
    if not match:
        return
    timer = threading.Timer(
        PRINT_JOB_MAX_AGE_SECONDS,
        cancel_print_job,
        args=(match.group(1),),
    )
    timer.daemon = True
    timer.start()


def printer_status_error(printer: str) -> str | None:
    """Return a participant-safe message when CUPS cannot use the printer."""
    try:
        state = subprocess.run(
            ["lpstat", "-l", "-p", printer],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "プリンターの接続状態を確認できませんでした。"
    if state.returncode != 0:
        return "Macにプリンターが登録されていません。管理者にお知らせください。"
    state_text = f"{state.stdout}\n{state.stderr}".lower()
    error_words = (
        "disabled",
        "offline",
        "not responding",
        "unable",
        "unreachable",
        "停止中",
        "一時停止",
        "応答していません",
        "接続できません",
    )
    if any(word in state_text for word in error_words):
        return "プリンターへ接続できません。電源とWi-Fiを確認してください。"
    return None


def run_print() -> tuple[bool, str, int]:
    global LAST_PRINT_AT
    pdf = document_path()
    if not pdf.exists():
        return False, "印刷資料が設定されていません。管理者にお知らせください。", 404

    with PRINT_LOCK:
        remaining = int(CONFIG["cooldown_seconds"]) - int(time.time() - LAST_PRINT_AT)
        if remaining > 0:
            return False, f"印刷機を準備しています。{remaining}秒後にもう一度お試しください。", 429

        printer = str(CONFIG["printer_name"])
        status_error = printer_status_error(printer)
        if status_error:
            return False, status_error, 503

        command = [
            "lp",
            "-d",
            printer,
            "-n",
            "1",
            "-o",
            "media=A4",
            "-o",
            "ColorModel=Gray",
            "-o",
            "print-color-mode=monochrome",
            "-o",
            "sides=one-sided",
            "-o",
            "fit-to-page",
            str(pdf),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"Macからプリンターへ送信できませんでした: {error}", 503
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "印刷命令が失敗しました").strip()
            return False, detail, 503
        output = result.stdout or ""
        job_match = re.search(r"request id is ([^\s]+)", output)
        job_id = job_match.group(1) if job_match else ""
        # `lp` can accept a job before CUPS notices that a network printer is
        # unreachable. Give it a short opportunity to surface that state so
        # the participant never sees a false "受付完了".
        for attempt in range(3):
            if attempt:
                time.sleep(1)
            status_error = printer_status_error(printer)
            if status_error:
                if job_id:
                    cancel_print_job(job_id)
                return False, status_error, 503
        expire_print_job_later(output)
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

    def read_uploaded_document(self) -> tuple[bytes, str]:
        """Read an uploaded PDF or photo without the removed Python 3.13 cgi module."""
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ValueError("PDFまたは写真を選択してください。")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES + 1024 * 1024:
            raise ValueError("20MB以下のPDFまたは写真を選択してください。")
        body = self.rfile.read(length)
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )
        if not message.is_multipart():
            raise ValueError("PDFまたは写真を選択してください。")
        for part in message.iter_parts():
            if part.get_param("name", header="content-disposition") == "document":
                data = part.get_payload(decode=True) or b""
                if len(data) > MAX_UPLOAD_BYTES:
                    raise ValueError("20MB以下のPDFまたは写真を選択してください。")
                if data.startswith(b"%PDF-"):
                    return data, ".pdf"
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    return data, ".png"
                if data.startswith(b"\xff\xd8\xff"):
                    return data, ".jpg"
                raise ValueError("PDF、PNG、JPEGのいずれかを選択してください。")
        raise ValueError("PDFまたは写真を選択してください。")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
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
                destination = unlock_destination(data.get("password", ""))
                if destination == "admin":
                    self.send_json(HTTPStatus.OK, {"ok": True, "admin": True})
                    return
                if destination != "print":
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "パスワードが間違っています。"})
                    return
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "token": issue_token(self.client_address[0]),
                        "expiresIn": CLIENT_AUTHORIZATION_SECONDS,
                    },
                )
                return

            if path == "/api/print":
                auth = self.headers.get("Authorization", "")
                token = auth.removeprefix("Bearer ").strip()
                if not consume_token(token, self.client_address[0]):
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "認証の有効期限が切れました。"})
                    return
                ok, message, status = run_print()
                self.send_json(status, {"ok": ok, "message": message})
                return

            if path == "/api/admin/config":
                data = self.read_json()
                if data.get("accessPassword"):
                    CONFIG["access_password"] = str(data["accessPassword"])
                if data.get("printerName"):
                    CONFIG["printer_name"] = str(data["printerName"])
                CONFIG["cooldown_seconds"] = max(0, min(300, int(data.get("cooldownSeconds", CONFIG["cooldown_seconds"]))))
                CONFIG["reset_seconds"] = max(5, min(300, int(data.get("resetSeconds", CONFIG["reset_seconds"]))))
                save_config()
                self.send_json(HTTPStatus.OK, {"ok": True, "message": "設定を保存しました。"})
                return

            if path == "/api/admin/upload":
                data, suffix = self.read_uploaded_document()
                target = ROOT / "assets" / f"print-document{suffix}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                CONFIG["pdf_path"] = str(target.relative_to(ROOT))
                save_config()
                self.send_json(HTTPStatus.OK, {"ok": True, "message": "印刷資料を差し替えました。"})
                return

            if path == "/api/admin/print":
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
    clear_stale_print_jobs()
    try:
        server = ThreadingHTTPServer((host, port), PrintHandler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print("\n ポートはすでに使用されています。CIA Printが起動中か確認してください。")
            print(" lsof -nP -iTCP:" + str(port) + " -sTCP:LISTEN")
            print(" CIA Printが正常稼働しているか、Macのブラウザで確認してください。")
            print(f" http://127.0.0.1:{port}/api/status")
            return
        raise
    report = network_diagnostics.inspect_network()
    print("\n" + "=" * 64)
    print(" CIA PRINT を起動しました")
    print("=" * 64)
    print(network_diagnostics.format_guidance(report, port))
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
