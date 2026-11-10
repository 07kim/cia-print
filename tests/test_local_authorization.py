from email.message import Message
from io import BytesIO
import time
import unittest
from unittest.mock import patch
import subprocess

import local_server


class PrintAuthorizationTests(unittest.TestCase):
    def setUp(self):
        with local_server.TOKEN_LOCK:
            local_server.TOKENS.clear()

    def test_token_is_single_use_for_same_client(self):
        token = local_server.issue_token("192.168.1.20")

        self.assertTrue(local_server.consume_token(token, "192.168.1.20"))
        self.assertFalse(local_server.consume_token(token, "192.168.1.20"))

    def test_token_cannot_move_to_another_client(self):
        token = local_server.issue_token("192.168.1.20")

        self.assertFalse(local_server.consume_token(token, "192.168.1.21"))
        self.assertFalse(local_server.consume_token(token, "192.168.1.20"))

    def test_expired_token_is_rejected(self):
        token = local_server.issue_token("192.168.1.20")
        with local_server.TOKEN_LOCK:
            local_server.TOKENS[token] = (time.time() - 1, "192.168.1.20")

        self.assertFalse(local_server.consume_token(token, "192.168.1.20"))


class AdminEntryTests(unittest.TestCase):
    def test_admin_password_opens_admin_without_changing_print_password(self):
        with patch.dict(local_server.CONFIG, {"access_password": "PRINT"}):
            self.assertEqual(local_server.unlock_destination("admin0000"), "admin")
            self.assertEqual(local_server.unlock_destination("PRINT"), "print")
            self.assertIsNone(local_server.unlock_destination("wrong"))


class DocumentUploadTests(unittest.TestCase):
    def test_multipart_pdf_upload_works_without_cgi_module(self):
        boundary = "cia-print-test-boundary"
        pdf = b"%PDF-1.4\nCIA Print test\n%%EOF\n"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="document"; filename="test.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + pdf + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = Message()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Content-Length"] = str(len(body))
        handler = local_server.PrintHandler.__new__(local_server.PrintHandler)
        handler.headers = headers
        handler.rfile = BytesIO(body)

        self.assertEqual(handler.read_uploaded_document(), (pdf, ".pdf"))

    def test_png_photo_upload_is_accepted(self):
        boundary = "cia-print-photo-boundary"
        photo = b"\x89PNG\r\n\x1a\nCIA Print photo"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="document"; filename="photo.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + photo + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = Message()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Content-Length"] = str(len(body))
        handler = local_server.PrintHandler.__new__(local_server.PrintHandler)
        handler.headers = headers
        handler.rfile = BytesIO(body)

        self.assertEqual(handler.read_uploaded_document(), (photo, ".png"))


class PrinterStatusTests(unittest.TestCase):
    @patch("local_server.subprocess.run")
    def test_unregistered_printer_is_not_reported_as_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "unknown printer")

        self.assertIn("登録されていません", local_server.printer_status_error("missing"))

    @patch("local_server.subprocess.run")
    def test_offline_printer_is_not_reported_as_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "printer is offline", "")

        self.assertIn("接続できません", local_server.printer_status_error("offline"))

    @patch("local_server.subprocess.run")
    def test_idle_printer_has_no_error(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "printer is idle", "")

        self.assertIsNone(local_server.printer_status_error("ready"))


class LocalAddressTests(unittest.TestCase):
    def test_accepts_common_wifi_and_tethering_addresses(self):
        self.assertTrue(local_server.is_usable_lan_address("192.168.75.160"))
        self.assertTrue(local_server.is_usable_lan_address("172.20.10.2"))
        self.assertTrue(local_server.is_usable_lan_address("10.0.0.4"))

    def test_rejects_loopback_and_unusable_special_addresses(self):
        self.assertFalse(local_server.is_usable_lan_address("127.0.0.1"))
        self.assertFalse(local_server.is_usable_lan_address("192.0.0.2"))
        self.assertFalse(local_server.is_usable_lan_address("not-an-address"))

if __name__ == "__main__":
    unittest.main()
