"""Synthetic loopback request security tests."""
import re
from io import BytesIO
from urllib.parse import urlsplit
import unittest

from alfa_document_intelligence.local_intake_app import create_expense_report_app


class _ObservedBody(BytesIO):
    def __init__(self, value):
        super().__init__(value)
        self.bytes_read = 0

    def read(self, size=-1):
        result = super().read(size)
        self.bytes_read += len(result)
        return result


def _invoke(app, environ):
    response = {}
    body = b"".join(app(environ, lambda status, headers: response.update(status=status, headers=dict(headers))))
    return response, body


class LoopbackCsrfTests(unittest.TestCase):
    def setUp(self):
        self.app = create_expense_report_app()

    def _initial_page(self):
        response, body = _invoke(self.app, {
            "REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "127.0.0.1:8080",
        })
        self.assertTrue(response["status"].startswith("200"))
        match = re.search(rb'name="_ocr2_csrf" value="([A-Za-z0-9_-]+)"', body)
        self.assertIsNotNone(match)
        action = re.search(rb'action="(/upload\?[^" ]+)"', body)
        self.assertIsNotNone(action)
        return match.group(1).decode("ascii"), action.group(1).decode("ascii")

    def _token(self):
        return self._initial_page()[0]

    def _clear_query(self):
        token, upload_url = self._initial_page()
        boundary = "synthetic-session-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"nota.pdf\"\r\n"
            "Content-Type: application/pdf\r\n\r\n%PDF-1.7\nsynthetic fixture\n"
            f"\r\n--{boundary}--\r\n"
        ).encode("ascii")
        response, page = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/upload", "QUERY_STRING": urlsplit(upload_url).query,
            "HTTP_HOST": "127.0.0.1:8080", "HTTP_ORIGIN": "http://127.0.0.1:8080",
            "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": BytesIO(body),
        })
        self.assertTrue(response["status"].startswith("200"))
        action = re.search(rb'action="(/clear\?[^" ]+)"', page)
        self.assertIsNotNone(action)
        return token, urlsplit(action.group(1).decode("ascii")).query

    def test_untrusted_origin_is_rejected_before_body_read(self):
        body = _ObservedBody(b"x=1")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "https://untrusted.example", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": "3", "wsgi.input": body,
        })
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(body.bytes_read, 0)

    def test_missing_origin_is_rejected_before_body_read(self):
        body = _ObservedBody(b"x=1")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "CONTENT_TYPE": "application/x-www-form-urlencoded", "CONTENT_LENGTH": "3", "wsgi.input": body,
        })
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(body.bytes_read, 0)

    def test_matching_loopback_origin_keeps_normal_post_flow(self):
        _, query = self._clear_query()
        body = b"clear=1"
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "QUERY_STRING": query, "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": BytesIO(body),
        })
        self.assertTrue(response["status"].startswith("200"))

    def test_loopback_origin_with_different_port_is_rejected(self):
        body = _ObservedBody(b"clear=1")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "http://127.0.0.1:8081", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": "7", "wsgi.input": body,
        })
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(body.bytes_read, 0)

    def test_opaque_origin_accepts_one_matching_token(self):
        token, query = self._clear_query()
        form = ("_ocr2_csrf=" + token).encode("ascii")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "QUERY_STRING": query, "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(form)), "wsgi.input": BytesIO(form),
        })
        self.assertTrue(response["status"].startswith("200"))

    def test_opaque_origin_rejects_wrong_token(self):
        token = self._token()
        form = b"_ocr2_csrf=wrong"
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(form)), "wsgi.input": BytesIO(form),
        })
        self.assertTrue(response["status"].startswith("403"))

    def test_opaque_origin_rejects_duplicate_token(self):
        token = self._token()
        form = ("_ocr2_csrf=" + token + "&_ocr2_csrf=" + token).encode("ascii")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(form)), "wsgi.input": BytesIO(form),
        })
        self.assertTrue(response["status"].startswith("403"))

    def test_opaque_origin_multipart_replays_bounded_prefix_to_upload_parser(self):
        token, upload_url = self._initial_page()
        boundary = "synthetic-csrf-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"_ocr2_csrf\"\r\n\r\n{token}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"nota.pdf\"\r\n"
            "Content-Type: application/pdf\r\n\r\n%PDF-1.7\nsynthetic fixture\n"
            f"\r\n--{boundary}--\r\n"
        ).encode("ascii")
        response, page = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/upload", "QUERY_STRING": urlsplit(upload_url).query, "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": BytesIO(body),
        })
        self.assertTrue(response["status"].startswith("200"))
        self.assertIn(b"nota.pdf", page)

    def test_opaque_origin_multipart_wrong_token_reads_only_bounded_prefix(self):
        self._token()
        boundary = "synthetic-csrf-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"_ocr2_csrf\"\r\n\r\nwrong\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"nota.pdf\"\r\n"
            "Content-Type: application/pdf\r\n\r\n%PDF-1.7\n" + "x" * 8192 +
            f"\r\n--{boundary}--\r\n"
        ).encode("ascii")
        stream = _ObservedBody(body)
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/upload", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": stream,
        })
        self.assertTrue(response["status"].startswith("403"))
        self.assertLessEqual(stream.bytes_read, 4096)

    def test_valid_csrf_token_does_not_replace_session_authorization(self):
        token = self._token()
        form = ("_ocr2_csrf=" + token).encode("ascii")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(form)), "wsgi.input": BytesIO(form),
        })
        self.assertTrue(response["status"].startswith("409"))

    def test_valid_token_does_not_override_non_loopback_host(self):
        token = self._token()
        form = ("_ocr2_csrf=" + token).encode("ascii")
        response, _ = _invoke(self.app, {
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "192.0.2.5:8080",
            "HTTP_ORIGIN": "null", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(form)), "wsgi.input": BytesIO(form),
        })
        self.assertTrue(response["status"].startswith("403"))


if __name__ == "__main__":
    unittest.main()
