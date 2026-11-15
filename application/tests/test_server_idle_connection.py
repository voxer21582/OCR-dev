"""An idle connection (a browser's preconnect) must not freeze the local server."""
from __future__ import annotations

import socket
import threading
import time
import unittest
import urllib.request

from alfa_document_intelligence.local_intake_app import serve_expense_report_local


class IdleConnectionTests(unittest.TestCase):
    def test_request_is_answered_while_another_connection_sends_nothing(self):
        server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            idle = socket.create_connection(("127.0.0.1", port))
            try:
                started = time.monotonic()
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=6) as response:
                    self.assertEqual(response.status, 200)
                self.assertLess(time.monotonic() - started, 4)
            finally:
                idle.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_default_idle_timeout_is_short(self):
        server = serve_expense_report_local(port=0)
        try:
            self.assertLessEqual(server.RequestHandlerClass.timeout, 5)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
