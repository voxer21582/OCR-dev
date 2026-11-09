import copy
import io
import json
import re
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.parse import urlencode

from alfa_document_intelligence.local_intake_app import (
    IntakeRequestError,
    _apply_field_correction,
    _render_editable_record,
    create_expense_report_app,
)
from alfa_document_intelligence.review_ledger import reviewed_overlay, verify_review_ledger


class ManualMissingFieldTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(
            (Path(__file__).parent / "fixtures" / "synthetic_invoice.json").read_text(encoding="utf-8")
        )
        self.record["pages"] = [{"page_number": 1, "orientation": "portrait"}]
        self.record["fields"].pop("merchant_name", None)

    def correct(self, field_name="merchant_name", **overrides):
        arguments = {
            "field_name": field_name,
            "value": "Negozio Sintetico",
            "timestamp": "2026-11-08T10:00:00Z",
            "region_page_number": 1,
            "region_coordinates": ("0.1", "0.2", "0.6", "0.35"),
        }
        arguments.update(overrides)
        return _apply_field_correction(self.record, **arguments)

    def test_ui_offers_missing_merchant_field_with_page_region(self):
        page = _render_editable_record(self.record, document_id="synthetic-1", has_source=True)
        self.assertIn('/reviews/synthetic-1/fields/merchant_name', page)
        self.assertIn('/reviews/synthetic-1/pages/1.png', page)
        self.assertIn('name="region_page"', page)
        self.assertIn('name="region_x0"', page)
        self.assertIn('name="region_y1"', page)
        self.assertNotIn("merchant_name", self.record["fields"])

    def test_missing_field_gets_human_evidence_without_changing_extraction(self):
        before = copy.deepcopy(self.record)
        updated = self.correct()
        overlay = reviewed_overlay(updated)
        candidate = overlay["reviewed_fields"]["merchant_name"]
        self.assertEqual(self.record, before)
        self.assertEqual(updated["fields"], before["fields"])
        self.assertNotIn("merchant_name", overlay["extracted_fields"])
        self.assertEqual(candidate["value"], "Negozio Sintetico")
        self.assertEqual(candidate["status"], "observed")
        self.assertEqual(candidate["alternatives"], [])
        evidence = candidate["evidence"][0]
        self.assertEqual(evidence["source_sha256"], before["source"]["sha256"])
        self.assertEqual(evidence["page_number"], 1)
        self.assertEqual(evidence["producer"]["stage"], "human_review")
        self.assertEqual(evidence["region"]["polygon"], [[0.1, 0.2], [0.6, 0.2], [0.6, 0.35], [0.1, 0.35]])
        self.assertNotIn("literal", evidence)
        self.assertTrue(verify_review_ledger(updated))

    def test_missing_field_requires_valid_page_and_region(self):
        before = copy.deepcopy(self.record)
        for overrides in (
            {"region_page_number": None, "region_coordinates": None},
            {"region_page_number": 2},
            {"region_coordinates": ("0.5", "0.2", "0.5", "0.35")},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(IntakeRequestError):
                self.correct(**overrides)
            self.assertEqual(self.record, before)

    def test_second_human_correction_is_appended_and_preserves_first(self):
        first = self.correct()
        second = _apply_field_correction(
            first, field_name="merchant_name", value="Negozio Sintetico Due",
            timestamp="2026-11-08T10:01:00Z",
        )
        edits = [event for event in second["review"]["events"] if event["action"] == "field_corrected"]
        self.assertEqual([event["candidate"]["value"] for event in edits],
                         ["Negozio Sintetico", "Negozio Sintetico Due"])
        self.assertEqual(reviewed_overlay(second)["reviewed_fields"]["merchant_name"]["value"],
                         "Negozio Sintetico Due")
        self.assertNotIn("merchant_name", second["fields"])
        self.assertTrue(verify_review_ledger(second))

    def test_completed_review_does_not_offer_missing_field_forms(self):
        first = self.correct()
        from alfa_document_intelligence.review_ledger import append_review_event
        completed = append_review_event(first, actor_id="local-session", action="completed", timestamp="2026-11-08T10:02:00Z")
        page = _render_editable_record(completed, document_id="synthetic-1", has_source=True)
        self.assertNotIn("Aggiungi un campo non rilevato", page)

    def test_page_change_clears_coordinate_inputs(self):
        page = _render_editable_record(self.record, document_id="synthetic-1", has_source=True)
        # Check the emitted browser code, not a separate test implementation of it.
        self.assertRegex(page, r'page\.addEventListener\("change",\(\)=>\{[^;]+;clear\(\)')
        clear = re.search(r'const clear=\(\)=>\{([^}]+)\}', page)
        self.assertIsNotNone(clear)
        self.assertRegex(clear.group(1), r'fields\.forEach\([^;]*\.value\s*=\s*[\"\']{2}')

    def test_wsgi_missing_field_correction_with_opaque_origin_token(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1}]
            record["fields"].pop("merchant_name", None)
            return record

        app = create_expense_report_app(document_processor=processor)

        def invoke(method, path, body=b"", content_type="", origin="http://127.0.0.1:8080"):
            response = {}
            environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": "127.0.0.1:8080",
                       "HTTP_ORIGIN": origin, "CONTENT_LENGTH": str(len(body)) if body else "",
                       "CONTENT_TYPE": content_type, "wsgi.input": io.BytesIO(body)}
            payload = b"".join(app(environ, lambda status, headers: response.update(status=status)))
            return response["status"], payload

        boundary = "synthetic-missing-field"
        source = b"%PDF-1.7\nsynthetic source\n"
        upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="receipt.pdf"\r\n'
                  'Content-Type: application/pdf\r\n\r\n').encode() + source + f"\r\n--{boundary}--\r\n".encode()
        status, _ = invoke("POST", "/upload", upload, f"multipart/form-data; boundary={boundary}")
        self.assertTrue(status.startswith("200"))
        status, _ = invoke("POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("200"))
        status, page = invoke("GET", "/reviews/doc-001")
        self.assertTrue(status.startswith("200"))
        token = re.search(rb'name="_ocr2_csrf" value="([A-Za-z0-9_-]+)"', page)
        self.assertIsNotNone(token)
        form = urlencode({"_ocr2_csrf": token.group(1).decode(), "value": "Negozio Sintetico",
                          "region_page": "1", "region_x0": "0.1", "region_y0": "0.2",
                          "region_x1": "0.6", "region_y1": "0.35", "review_seconds": "0"}).encode()
        status, _ = invoke("POST", "/reviews/doc-001/fields/merchant_name", form,
                           "application/x-www-form-urlencoded", origin="null")
        self.assertTrue(status.startswith("400"))
        with patch("alfa_document_intelligence.local_intake_app._source_page_png", return_value=b"synthetic-preview"):
            status, _ = invoke("GET", "/reviews/doc-001/pages/1.png")
        self.assertTrue(status.startswith("200"))
        status, page = invoke("POST", "/reviews/doc-001/fields/merchant_name", form,
                              "application/x-www-form-urlencoded", origin="null")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Negozio Sintetico", page)
        self.assertIn(b"regione selezionata e verificata da una persona", page)

    def test_arbitrary_and_reserved_missing_names_are_rejected(self):
        for name in ("arbitrary_custom_field", "document_family", "document_family_candidates", "fiscal_document_state"):
            with self.subTest(name=name):
                self.record["fields"].pop(name, None)
                before = copy.deepcopy(self.record)
                with self.assertRaises(IntakeRequestError):
                    self.correct(field_name=name)
                self.assertEqual(self.record, before)

    def test_wsgi_absent_field_requires_preview_before_region_correction(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1}]
            record["fields"]["merchant_name"] = {
                "value": None, "status": "absent", "evidence": [], "alternatives": [],
            }
            return record

        app = create_expense_report_app(document_processor=processor)

        def invoke(method, path, body=b"", content_type=""):
            response = {}
            environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": "127.0.0.1:8080",
                       "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_LENGTH": str(len(body)) if body else "",
                       "CONTENT_TYPE": content_type, "wsgi.input": io.BytesIO(body)}
            payload = b"".join(app(environ, lambda status, headers: response.update(status=status)))
            return response["status"], payload

        boundary = "synthetic-absent-field"
        source = b"%PDF-1.7\nsynthetic source\n"
        upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="receipt.pdf"\r\n'
                  'Content-Type: application/pdf\r\n\r\n').encode() + source + f"\r\n--{boundary}--\r\n".encode()
        status, _ = invoke("POST", "/upload", upload, f"multipart/form-data; boundary={boundary}")
        self.assertTrue(status.startswith("200"))
        status, _ = invoke("POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("200"))
        form = urlencode({"value": "Negozio Sintetico", "region_page": "1", "region_x0": "0.1",
                          "region_y0": "0.2", "region_x1": "0.6", "region_y1": "0.35",
                          "review_seconds": "0"}).encode()
        status, _ = invoke("POST", "/reviews/doc-001/fields/merchant_name", form,
                           "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("400"))
        with patch("alfa_document_intelligence.local_intake_app._source_page_png", return_value=b"synthetic-preview"):
            status, _ = invoke("GET", "/reviews/doc-001/pages/1.png")
        self.assertTrue(status.startswith("200"))
        status, page = invoke("POST", "/reviews/doc-001/fields/merchant_name", form,
                              "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Negozio Sintetico", page)

    def test_wsgi_region_requires_successful_preview_for_same_document_and_page(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1}, {"page_number": 2}]
            record["fields"].pop("merchant_name", None)
            return record

        app = create_expense_report_app(document_processor=processor)

        def invoke(method, path, body=b"", content_type=""):
            response = {}
            environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": "127.0.0.1:8080",
                       "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_LENGTH": str(len(body)) if body else "",
                       "CONTENT_TYPE": content_type, "wsgi.input": io.BytesIO(body)}
            payload = b"".join(app(environ, lambda status, headers: response.update(status=status)))
            return response["status"], payload

        boundary = "synthetic-preview-binding"
        source = b"%PDF-1.7\nsynthetic source\n"
        part = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="receipt.pdf"\r\n'
                'Content-Type: application/pdf\r\n\r\n').encode() + source + b"\r\n"
        upload = part + part.replace(b'receipt.pdf', b'receipt-2.pdf') + f"--{boundary}--\r\n".encode()
        status, _ = invoke("POST", "/upload", upload, f"multipart/form-data; boundary={boundary}")
        self.assertTrue(status.startswith("200"))
        status, _ = invoke("POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("200"))

        def correction(page):
            return urlencode({"value": "Negozio Sintetico", "region_page": str(page),
                              "region_x0": "0.1", "region_y0": "0.2", "region_x1": "0.6",
                              "region_y1": "0.35", "review_seconds": "0"}).encode()

        module = "alfa_document_intelligence.local_intake_app"
        with patch(f"{module}._source_page_png", side_effect=ValueError("synthetic failure")):
            status, _ = invoke("GET", "/reviews/doc-001/pages/1.png")
        self.assertTrue(status.startswith("422"))
        with patch(f"{module}._apply_field_correction") as apply_correction:
            status, _ = invoke("POST", "/reviews/doc-001/fields/merchant_name", correction(1),
                               "application/x-www-form-urlencoded")
            self.assertTrue(status.startswith("400"))
            apply_correction.assert_not_called()

        with patch(f"{module}._source_page_png", return_value=b"synthetic-preview"):
            status, _ = invoke("GET", "/reviews/doc-001/pages/1.png")
        self.assertTrue(status.startswith("200"))
        for document_id, page in (("doc-001", 2), ("doc-002", 1)):
            with self.subTest(document_id=document_id, page=page), patch(
                f"{module}._apply_field_correction"
            ) as apply_correction:
                status, _ = invoke("POST", f"/reviews/{document_id}/fields/merchant_name", correction(page),
                                   "application/x-www-form-urlencoded")
                self.assertTrue(status.startswith("400"))
                apply_correction.assert_not_called()

        with patch(f"{module}._source_page_png", side_effect=AssertionError("POST decoded preview")), patch(
            f"{module}.iter_decoded_pages", side_effect=AssertionError("POST decoded source")
        ):
            status, page = invoke("POST", "/reviews/doc-001/fields/merchant_name", correction(1),
                                  "application/x-www-form-urlencoded")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Negozio Sintetico", page)


if __name__ == "__main__":
    unittest.main()
