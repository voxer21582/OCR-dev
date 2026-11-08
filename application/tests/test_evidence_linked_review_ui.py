import copy
import hashlib
import io
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence import local_intake_app
from alfa_document_intelligence.expense_reports import ExpenseReportIntakeSession
from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.review_ledger import verify_review_ledger


NOTE = b"%PDF-1.7\nsynthetic expense report\n"
RECEIPT = b"%PDF-1.7\nsynthetic fiscal receipt\n"


def _archive():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("note.pdf", NOTE)
        archive.writestr("receipt.pdf", RECEIPT)
    return buffer.getvalue()


def _request(app, method="GET", path="/", body=b"", content_type=""):
    result = {}

    def start_response(status, headers):
        result["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": "http://127.0.0.1:8080",
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(app(environ, start_response))
    return result["status"], payload


def _upload(app):
    boundary = "synthetic-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="trip.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + _archive() + f"\r\n--{boundary}--\r\n".encode()
    return _request(app, "POST", "/upload", body, f"multipart/form-data; boundary={boundary}")


def test_human_correction_is_appended_with_source_evidence_and_does_not_overwrite_ocr(monkeypatch):
    real_create = local_intake_app.create_expense_report_intake_session
    captured = {}

    def with_synthetic_candidate(*args, **kwargs):
        session = real_create(*args, **kwargs)
        record = session.documents["doc-001"]
        digest = record["source"]["sha256"]
        record["pages"] = [{"page_number": 1}]
        record["fields"]["merchant_name"] = {
            "value": "Cafe ABC",
            "status": "uncertain",
            "alternatives": [],
            "evidence": [{
                "source_sha256": digest,
                "page_number": 1,
                "region": {"x": 10, "y": 10, "width": 100, "height": 20},
                "literal": "Cafe ABC",
            }],
        }
        captured["session"] = session
        captured["original_fields"] = copy.deepcopy(record["fields"])
        return session

    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", with_synthetic_candidate)
    app = create_expense_report_app()
    assert _upload(app)[0] == "200 OK"
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    assert _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")[0] == "200 OK"

    status, page = _request(app, path="/reviews/doc-001")
    assert status == "200 OK"
    assert b"Apri documento originale" in page
    assert b"Registra correzione" in page
    assert b"Cafe ABC" in page

    correction = urlencode({"value": "Caffè ABC"}).encode()
    status, page = _request(
        app,
        "POST",
        "/reviews/doc-001/fields/merchant_name",
        correction,
        "application/x-www-form-urlencoded",
    )
    assert status == "200 OK"
    assert "Caffè ABC".encode() in page
    session = captured["session"]
    updated = session.documents["doc-001"]
    assert updated["fields"] == captured["original_fields"]
    assert updated["review"]["status"] == "in_progress"
    assert [event["action"] for event in updated["review"]["events"]] == [
        "queued", "opened", "field_corrected"
    ]
    assert updated["review"]["events"][-1]["candidate"]["evidence"][0]["source_sha256"] == hashlib.sha256(NOTE).hexdigest()
    assert verify_review_ledger(updated)
