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
            self.assertLessEqual(server.RequestHandlerClass.idle_timeout, 5)
        finally:
            server.server_close()



class SlowUploadTests(unittest.TestCase):
    def test_a_request_that_pauses_mid_body_is_not_cut(self):
        server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            boundary = "slow-boundary"
            body = (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"nota.pdf\"\r\n"
                "Content-Type: application/pdf\r\n\r\n"
            ).encode() + b"%PDF-1.7\nsynthetic " + b"x" * 2000 + f"\r\n--{boundary}--\r\n".encode()
            head = (
                f"POST /upload HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nOrigin: http://127.0.0.1:{port}\r\n"
                f"Content-Type: multipart/form-data; boundary={boundary}\r\nContent-Length: {len(body)}\r\n\r\n"
            ).encode()
            with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
                connection.sendall(head + body[:500])
                time.sleep(1.6)  # longer than the idle timeout, like a file still being fetched
                connection.sendall(body[500:])
                reply = connection.recv(64)
            self.assertTrue(reply.startswith(b"HTTP/1.0 "), reply)
            self.assertNotIn(b" 400 ", reply[:16])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
