from email.message import Message
from io import BytesIO
import time
import unittest

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


class PdfUploadTests(unittest.TestCase):
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

        self.assertEqual(handler.read_uploaded_pdf(), pdf)

if __name__ == "__main__":
    unittest.main()
