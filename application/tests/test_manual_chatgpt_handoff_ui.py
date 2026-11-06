import io
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence import local_intake_app
from alfa_document_intelligence.local_intake_app import create_expense_report_app


NOTE = b"%PDF-1.7\nsynthetic expense report\n"
RECEIPT = b"%PDF-1.7\nsynthetic receipt\n"


def _request(app, method="GET", path="/", body=b"", content_type=""):
    result = {}

    def start_response(status, headers):
        result["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    return result, b"".join(app(environ, start_response))


def _upload(app):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zipped:
        zipped.writestr("private-note-name.pdf", NOTE)
        zipped.writestr("private-receipt-name.pdf", RECEIPT)
    boundary = "chatgpt-handoff-test"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="private-trip.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + archive.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    result, _ = _request(app, "POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
    assert result["status"] == "200 OK"


def test_browser_shows_manual_prompt_only_after_human_field_confirmation(monkeypatch):
    original_create = local_intake_app.create_expense_report_intake_session

    def with_synthetic_candidate(*args, **kwargs):
        session = original_create(*args, **kwargs)
        record = session.documents["doc-001"]
        record["pages"] = [{"page_number": 1}]
        record["fields"]["total_amount"] = {
            "value": "99.99",
            "status": "uncertain",
            "alternatives": [],
            "evidence": [{
                "source_sha256": record["source"]["sha256"],
                "page_number": 1,
                "region": {"x": 1, "y": 1, "width": 10, "height": 4},
                "literal": "OCR raw total",
            }],
        }
        return session

    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", with_synthetic_candidate)
    app = create_expense_report_app()
    _upload(app)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    result, _ = _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")
    assert result["status"] == "200 OK"

    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert b"confirm fields first" in page
    assert b"<textarea readonly" not in page

    correction = urlencode({"value": "100.00"}).encode()
    result, _ = _request(
        app,
        "POST",
        "/reviews/doc-001/fields/total_amount",
        correction,
        "application/x-www-form-urlencoded",
    )
    assert result["status"] == "200 OK"

    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert b"<textarea readonly" in page
    assert b"100.00" in page
    assert b"expense_note" in page
    assert b"private-note-name.pdf" not in page
    assert b"private-receipt-name.pdf" not in page
    assert b"private-trip.zip" not in page
    assert b"OCR raw total" not in page
    assert b"non lo invia" in page
