"""An idle connection (a browser's preconnect) must not freeze the local server."""
from __future__ import annotations

import socket
import threading
import time
import unittest
import urllib.request
import urllib.error

from alfa_document_intelligence.local_intake_app import serve_expense_report_local


def test_access_log_does_not_write_request_or_query(capsys):
    server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/?q=SYNTHETIC_PRIVATE_291', timeout=6) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    captured = capsys.readouterr()
    assert 'SYNTHETIC_PRIVATE_291' not in captured.err
    assert 'SYNTHETIC_PRIVATE_291' not in captured.out


def test_server_error_does_not_write_exception_content(capsys):
    server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
    def failing_app(environ, start_response):
        raise RuntimeError('SYNTHETIC_DOCUMENT_622')
    server.set_app(failing_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with unittest.TestCase().assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=6)
        assert error.exception.code == 500
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    captured = capsys.readouterr()
    assert 'SYNTHETIC_DOCUMENT_622' not in captured.err
    assert 'SYNTHETIC_DOCUMENT_622' not in captured.out
    assert captured.err.count('OCR2_HTTP_ERROR') == 1


def test_wsgi_error_stream_supports_writelines_without_disclosing_content(capsys):
    server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
    def app(environ, start_response):
        environ['wsgi.errors'].writelines(['SYNTHETIC_PRIVATE_931\n'])
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']
    server.set_app(app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=6) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    captured = capsys.readouterr()
    assert 'SYNTHETIC_PRIVATE_931' not in captured.out + captured.err
    assert captured.err.count('OCR2_HTTP_ERROR') == 1


def test_handler_failure_does_not_write_exception_or_client_address(capsys):
    server = serve_expense_report_local(port=0, idle_connection_timeout_seconds=1)
    class FailingHandler:
        def __init__(self, request, client_address, server):
            raise RuntimeError('SYNTHETIC_HANDLER_SECRET_557')
    server.RequestHandlerClass = FailingHandler
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with socket.create_connection(('127.0.0.1', port), timeout=6) as client:
            client.sendall(b'GET / HTTP/1.0\r\n\r\n')
            try:
                client.recv(1)
            except (ConnectionResetError, ConnectionAbortedError):
                pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    captured = capsys.readouterr()
    assert 'SYNTHETIC_HANDLER_SECRET_557' not in captured.err
    assert '127.0.0.1' not in captured.err
    assert 'OCR2_HTTP_HANDLER_ERROR' in captured.err


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
