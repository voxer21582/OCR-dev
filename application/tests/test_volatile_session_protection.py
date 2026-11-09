import io
import re
import unittest
from urllib.parse import urlencode, urlsplit

from alfa_document_intelligence.local_intake_app import create_expense_report_app


FIRST = b"%PDF-1.7\nfirst synthetic document\n"
SECOND = b"%PDF-1.7\nsecond synthetic document\n"


def request(app, method="GET", path="/", body=b"", content_type=""):
    response = {}

    if path != "/":
        status, page = request(app)
        assert status == "200 OK"
        token = re.search(rb'_ocr2_session=([A-Za-z0-9_-]+)', page)
        assert token is not None
        path += "?_ocr2_session=" + token.group(1).decode("ascii")
    parsed = urlsplit(path)

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": parsed.path, "QUERY_STRING": parsed.query,
        "HTTP_HOST": "127.0.0.1:8080", "HTTP_ORIGIN": "http://127.0.0.1:8080",
        "CONTENT_LENGTH": str(len(body)) if body else "", "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    result = b"".join(app(environ, start_response))
    return response["status"], result


def upload(app, filename, data, *, include_note=False):
    boundary = "synthetic-boundary"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        'Content-Type: application/pdf\r\n\r\n'
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    if include_note:
        note_part = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="note.pdf"\r\n'
                     'Content-Type: application/pdf\r\n\r\n').encode() + b"%PDF-1.7\nsynthetic note\n" + b"\r\n"
        body = note_part + body
    return request(app, "POST", "/upload", body, f"multipart/form-data; boundary={boundary}")


def assign(app):
    return request(app, "POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode(),
                   "application/x-www-form-urlencoded")


class VolatileSessionProtectionTest(unittest.TestCase):
    def test_second_upload_preserves_review_and_source_until_explicit_clear(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1, "width_px": 1000, "height_px": 1400}]
            record["processing"]["ocr"]["status"] = "completed"
            evidence = {
                "source_sha256": record["source"]["sha256"], "page_number": 1,
                "token_ids": ["synthetic-family-cue"], "literal": "CARD PAYMENT SLIP",
                "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
            }
            record["fields"]["document_family_candidates"] = {
                "value": None, "status": "uncertain",
                "alternatives": [{"value": "pos_slip", "status": "observed", "evidence": [evidence]}],
                "evidence": [evidence],
            }
            return record

        app = create_expense_report_app(document_processor=processor)
        self.assertEqual(request(app)[0], "200 OK")
        self.assertEqual(request(app)[0], "200 OK")  # a second initial form
        self.assertEqual(upload(app, "first.pdf", FIRST, include_note=True)[0], "200 OK")
        self.assertEqual(assign(app)[0], "200 OK")
        form = urlencode({"document_family": "pos_slip", "review_seconds": "1"}).encode()
        status, reviewed = request(app, "POST", "/reviews/doc-002/document-family", form,
                                   "application/x-www-form-urlencoded")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Famiglia attualmente revisionata: pos_slip", reviewed)
        self.assertEqual(request(app, path="/reviews/doc-002/source"), ("200 OK", FIRST))

        self.assertEqual(upload(app, "second.pdf", SECOND)[0], "409 Conflict")
        status, reviewed = request(app, path="/reviews/doc-002")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Famiglia attualmente revisionata: pos_slip", reviewed)
        self.assertEqual(request(app, path="/reviews/doc-002/source"), ("200 OK", FIRST))

        self.assertEqual(request(app, "POST", "/clear", b"clear=1",
                                 "application/x-www-form-urlencoded")[0], "200 OK")
        self.assertEqual(upload(app, "second.pdf", SECOND)[0], "200 OK")
        self.assertEqual(assign(app)[0], "200 OK")
        self.assertEqual(request(app, path="/reviews/doc-001/source"), ("200 OK", SECOND))


if __name__ == "__main__":
    unittest.main()
