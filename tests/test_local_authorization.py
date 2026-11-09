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


if __name__ == "__main__":
    unittest.main()
