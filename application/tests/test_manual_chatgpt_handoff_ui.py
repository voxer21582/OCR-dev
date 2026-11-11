import io
import re
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence import chatgpt_handoff, local_intake_app
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
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": "http://127.0.0.1:8080",
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


class ManualChatGPTHandoffUITests(unittest.TestCase):
    def test_browser_shows_manual_prompt_only_after_human_field_confirmation(self):
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

        with patch.object(
            local_intake_app,
            "create_expense_report_intake_session",
            side_effect=with_synthetic_candidate,
        ):
            app = create_expense_report_app()
            _upload(app)
            assign = urlencode({"note_document_id": "doc-001"}).encode()
            result, _ = _request(
                app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded"
            )
            self.assertEqual(result["status"], "200 OK")

            result, page = _request(app, path="/chatgpt")
            self.assertEqual(result["status"], "200 OK")
            self.assertIn(b"confirm fields first", page)
            self.assertNotIn(b"<textarea readonly", page)

            correction = urlencode({"value": "100.00"}).encode()
            result, _ = _request(
                app,
                "POST",
                "/reviews/doc-001/fields/total_amount",
                correction,
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "200 OK")

            result, page = _request(app, path="/chatgpt")
            self.assertEqual(result["status"], "200 OK")
            self.assertIn(b"<textarea readonly", page)
            self.assertIn(b"100.00", page)
            self.assertIn(b"expense_note", page)
            self.assertNotIn(b"private-note-name.pdf", page)
            self.assertNotIn(b"private-receipt-name.pdf", page)
            self.assertNotIn(b"private-trip.zip", page)
            self.assertNotIn(b"OCR raw total", page)
            self.assertIn(b"non lo invia", page)

    def test_blocked_review_warning_allows_copy_only_after_current_text_confirmation(self):
        original_create = local_intake_app.create_expense_report_intake_session
        original_append = local_intake_app.append_review_event

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
                    "literal": "synthetic amount",
                }],
            }
            return session

        def append_block_after_correction(record, **kwargs):
            updated = original_append(record, **kwargs)
            if kwargs.get("action") == "field_corrected":
                updated = original_append(
                    updated,
                    actor_id="synthetic-reviewer",
                    action="flagged",
                    timestamp=kwargs["timestamp"],
                    reason_code="PRIVATE-SYNTHETIC-REASON",
                )
            return updated

        with (
            patch.object(
                local_intake_app,
                "create_expense_report_intake_session",
                side_effect=with_synthetic_candidate,
            ),
            patch.object(
                local_intake_app,
                "append_review_event",
                side_effect=append_block_after_correction,
            ),
        ):
            app = create_expense_report_app()
            _upload(app)
            result, _ = _request(
                app, "POST", "/assign-note",
                urlencode({"note_document_id": "doc-001"}).encode(),
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "200 OK")
            _request(
                app, "POST", "/reviews/doc-001/fields/total_amount",
                urlencode({"value": "100.00"}).encode(),
                "application/x-www-form-urlencoded",
            )
            result, page = _request(app, path="/chatgpt")
            self.assertEqual(result["status"], "200 OK")
            self.assertIn(b'role="alert"', page)
            self.assertIn(b"Revisione bloccata", page)
            self.assertIn(b"incompleta", page)
            self.assertIn(b"non approvata", page)
            self.assertNotIn(b"<textarea readonly", page)
            self.assertNotIn(b"100.00", page)
            self.assertNotIn(b"PRIVATE-SYNTHETIC-REASON", page)

            draft_body = urlencode({"draft": "synthetic draft"}).encode()
            result, page = _request(
                app, "POST", "/chatgpt/return", draft_body,
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "409 Conflict")
            self.assertIn(b"Conferma prima", page)

            result, page = _request(app, path="/chatgpt")
            digest = re.search(rb'name="prompt_sha256" value="([a-f0-9]{64})"', page)
            self.assertIsNotNone(digest)
            consent = urlencode({
                "safe_to_share": "1",
                "prompt_sha256": digest.group(1).decode("ascii"),
            }).encode()
            result, page = _request(
                app, "POST", "/chatgpt/prepare", consent,
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "200 OK")
            self.assertIn(b"Revisione bloccata", page)
            self.assertIn(b"<textarea readonly", page)
            self.assertIn(b"100.00", page)
            self.assertNotIn(b"PRIVATE-SYNTHETIC-REASON", page)

            result, page = _request(
                app, "POST", "/chatgpt/return", draft_body,
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "200 OK")
            self.assertIn(b"synthetic draft", page)

            original_prompt = local_intake_app.build_chatgpt_handoff_prompt
            with patch.object(
                local_intake_app,
                "build_chatgpt_handoff_prompt",
                side_effect=lambda *args, **kwargs: original_prompt(*args, **kwargs) + " CHANGED-SYNTHETIC-TEXT",
            ):
                result, changed_page = _request(app, path="/chatgpt")
            self.assertEqual(result["status"], "200 OK")
            self.assertNotIn(b"<textarea readonly", changed_page)
            self.assertNotIn(b"100.00", changed_page)
            self.assertNotIn(b"synthetic draft", changed_page)
            self.assertIn(b"safe_to_share", changed_page)
            self.assertIn("bozza precedente non è mostrata".encode("utf-8"), changed_page)


    def test_malformed_review_never_renders_prompt_or_private_error(self):
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
                    "literal": "synthetic amount",
                }],
            }
            return session

        with patch.object(
            local_intake_app,
            "create_expense_report_intake_session",
            side_effect=with_synthetic_candidate,
        ):
            app = create_expense_report_app()
            _upload(app)
            result, _ = _request(
                app, "POST", "/assign-note",
                urlencode({"note_document_id": "doc-001"}).encode(),
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(result["status"], "200 OK")
            _request(
                app, "POST", "/reviews/doc-001/fields/total_amount",
                urlencode({"value": "100.00"}).encode(),
                "application/x-www-form-urlencoded",
            )
            with patch.object(
                chatgpt_handoff,
                "verify_review_ledger",
                side_effect=ValueError("PRIVATE-SYNTHETIC-LEDGER-DETAIL"),
            ):
                result, page = _request(app, path="/chatgpt")

        self.assertEqual(result["status"], "200 OK")
        self.assertIn(b"role=\"alert\"", page)
        self.assertIn(b"non pu\xc3\xb2 essere verificata", page)
        self.assertNotIn(b"<textarea readonly", page)
        self.assertNotIn(b"100.00", page)
        self.assertNotIn(b"PRIVATE-SYNTHETIC-LEDGER-DETAIL", page)
