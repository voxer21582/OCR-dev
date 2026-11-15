"""Synthetic WSGI coverage for the local expense reconciliation screen."""
from copy import deepcopy
import io
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.expense_line_extraction import extract_expense_lines
from alfa_document_intelligence.local_document_store import StoreConcurrentUpdate
from alfa_document_intelligence.expense_reconciliation import case_source_set_revision
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from test_expense_reconciliation import _case


class _Archive:
    def __init__(self):
        _, documents = _case()
        statement_hash = documents["statement"]["source"]["sha256"]
        line = extract_expense_lines([OCRPageResult(
            statement_hash, 1, "SyntheticOCR", "1", "it+en", (
                OCRToken("p1-t1", "Pranzo", ((.05, .1), (.3, .1), (.3, .15), (.05, .15)), .99),
                OCRToken("p1-t2", "EUR 42.50", ((.65, .1), (.95, .1), (.95, .15), (.65, .15)), .99),
            ),
        )])[0]
        self.case = {
            "case_id": "case-1",
            "case_revision": "c" * 64,
            "schema_version": "0.1.0",
            "statement_document_id": "statement",
            "statement_sha256": documents["statement"]["source"]["sha256"],
            "attachments": [{
                "document_id": "receipt-1",
                "source_sha256": documents["receipt-1"]["source"]["sha256"],
                "included": True,
            }],
            "chunks": [], "review_events": [], "inclusion_events": [],
            "processing": {"state": "completed", "cursor": None, "result_bytes": 0},
        }
        documents["statement"]["schema_version"] = "0.3.0"
        documents["statement"]["expense_lines"] = [line]
        self.documents = {
            key: SimpleNamespace(record=value, source_bytes=b"synthetic local fixture")
            for key, value in documents.items()
        }
        self.saved = []

    def get_case(self, case_id):
        return deepcopy(self.case) if case_id == self.case["case_id"] else None

    def get(self, document_id):
        return self.documents.get(document_id)

    def source_set_revision(self):
        return case_source_set_revision(
            self.case["statement_document_id"], self.case["statement_sha256"],
            self.case["chunks"], self.case["inclusion_events"],
        )

    def save_case(self, case, *, expected_revision=None):
        if expected_revision != self.case["case_revision"]:
            raise StoreConcurrentUpdate("stale case")
        self.case = deepcopy(case)
        self.saved.append(deepcopy(case))
        return deepcopy(case)

    def append_attachment_inclusion_event(
        self, case_id, expected_revision, document_id, source_sha256, included, reason, event_id,
    ):
        if expected_revision != self.case["case_revision"]:
            raise RuntimeError("stale case")
        attachment = next(item for item in self.case["attachments"] if item["document_id"] == document_id)
        if attachment["source_sha256"] != source_sha256:
            raise RuntimeError("stale source")
        attachment["included"] = included
        self.case["case_revision"] = "d" * 64
        body = {
            "event_id": event_id, "case_revision": expected_revision,
            "document_id": document_id, "source_sha256": source_sha256,
            "included": included, "reason": reason.strip(),
        }
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.case["inclusion_events"].append({
            **body, "sequence": len(self.case["inclusion_events"]) + 1,
            "event_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        })
        return deepcopy(self.case)


def _request(app, method="GET", path="/", body=b"", content_type="", headers=None):
    response = {}

    def start_response(status, response_headers):
        response["status"] = status
        response["headers"] = dict(response_headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": "http://127.0.0.1:8080",
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    environ.update(headers or {})
    payload = b"".join(app(environ, start_response))
    return response["status"], response["headers"], payload


class ExpenseReconciliationUITests(unittest.TestCase):
    def setUp(self):
        self.archive = _Archive()
        self.app = create_expense_report_app(archive_store=self.archive)
        self.addCleanup(self.app.close)

    def test_local_review_route_displays_evidence_and_never_auto_confirms(self):
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Confronto con la nota definitiva", page)
        self.assertIn(b"Pranzo", page)
        self.assertIn(b"Conferma abbinamento selezionato", page)
        self.assertIn(b"Nessun abbinamento \xc3\xa8 confermato automaticamente", page)
        self.assertNotIn(b'Esito revisione: confirmed', page)

    def test_review_post_appends_source_bound_human_confirmation(self):
        from alfa_document_intelligence.expense_reconciliation import build_reconciliation

        line = self.archive.documents["statement"].record["expense_lines"][0]
        current = build_reconciliation(
            "case-1", "statement", self.archive.case["statement_sha256"], [line],
            self.archive.case["attachments"],
            {key: value.record for key, value in self.archive.documents.items()},
            source_set_revision=self.archive.source_set_revision(),
        )
        body = urlencode({
            "_reconciliation_revision": current["case_revision"],
            "_line_id": current["lines"][0]["line_id"],
            "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
            "_event_id": "event-1", "_action": "confirmed",
            "_candidate_document_id": "receipt-1", "_reviewer_note": "Verificato dall’utente",
        }).encode("ascii")
        status, _, response = _request(
            self.app, "POST", "/cases/case-1/reconciliation/review", body,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Decisione salvata", response)
        self.assertEqual(len(self.archive.saved), 1)
        event = self.archive.case["review_events"][0]
        self.assertEqual(event["action"], "confirmed")
        self.assertEqual(event["candidate_sources"][0]["document_id"], "receipt-1")

    def test_exclude_reinclude_after_confirmation_does_not_restore_old_review(self):
        from alfa_document_intelligence.expense_reconciliation import build_reconciliation

        line = self.archive.documents["statement"].record["expense_lines"][0]
        current = build_reconciliation(
            "case-1", "statement", self.archive.case["statement_sha256"], [line],
            self.archive.case["attachments"],
            {key: value.record for key, value in self.archive.documents.items()},
            source_set_revision=self.archive.source_set_revision(),
        )
        confirmed = urlencode({
            "_reconciliation_revision": current["case_revision"],
            "_line_id": current["lines"][0]["line_id"],
            "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
            "_event_id": "event-before-exclusion", "_action": "confirmed",
            "_candidate_document_id": "receipt-1", "_reviewer_note": "Verificato",
        }).encode("ascii")
        self.assertEqual(_request(
            self.app, "POST", "/cases/case-1/reconciliation/review", confirmed,
            "application/x-www-form-urlencoded",
        )[0], "200 OK")

        for included, event_id in ((False, "exclude"), (True, "reinclude")):
            self.archive.append_attachment_inclusion_event(
                "case-1", self.archive.case["case_revision"], "receipt-1", "b" * 64,
                included, f"Synthetic {event_id}", event_id,
            )
        self.archive.case["processing"]["state"] = "completed"
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertNotIn(b"Esito revisione: confirmed", page)
        self.assertIn(b"Nessun abbinamento ", page)
        self.assertEqual(self.archive.case["review_events"][0]["action"], "confirmed")

    def test_stale_review_revision_is_rejected_without_persisting(self):
        body = urlencode({
            "_reconciliation_revision": "0" * 64,
            "_line_id": "line-1", "_line_evidence_sha256": "0" * 64,
            "_event_id": "event-stale", "_action": "missing_support",
            "_reviewer_note": "",
        }).encode("ascii")
        status, _, response = _request(
            self.app, "POST", "/cases/case-1/reconciliation/review", body,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "409 Conflict")
        self.assertNotIn(b"0" * 64, response)
        self.assertEqual(self.archive.saved, [])

    def test_every_review_outcome_is_an_explicit_append_only_action(self):
        from alfa_document_intelligence.expense_reconciliation import build_reconciliation

        line = self.archive.documents["statement"].record["expense_lines"][0]
        for index, action in enumerate((
            "confirmed", "rejected", "ambiguous", "missing_support",
            "possible_duplicate", "excluded_with_reason",
        )):
            current = build_reconciliation(
                "case-1", "statement", self.archive.case["statement_sha256"], [line],
                self.archive.case["attachments"],
                {key: value.record for key, value in self.archive.documents.items()},
                source_set_revision=self.archive.source_set_revision(),
            )
            fields = {
                "_reconciliation_revision": current["case_revision"],
                "_line_id": current["lines"][0]["line_id"],
                "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
                "_event_id": f"event-action-{index}", "_action": action,
                "_reviewer_note": "Revisione umana" if action == "excluded_with_reason" else "",
            }
            if action != "missing_support":
                fields["_candidate_document_id"] = "receipt-1"
            body = urlencode(fields).encode("ascii")
            status, _, _ = _request(
                self.app, "POST", "/cases/case-1/reconciliation/review", body,
                "application/x-www-form-urlencoded",
            )
            self.assertEqual(status, "200 OK", action)
        self.assertEqual(
            [event["action"] for event in self.archive.case["review_events"]],
            ["confirmed", "rejected", "ambiguous", "missing_support", "possible_duplicate", "excluded_with_reason"],
        )

    def test_review_event_replay_is_idempotent(self):
        from alfa_document_intelligence.expense_reconciliation import build_reconciliation

        line = self.archive.documents["statement"].record["expense_lines"][0]
        current = build_reconciliation(
            "case-1", "statement", self.archive.case["statement_sha256"], [line],
            self.archive.case["attachments"],
            {key: value.record for key, value in self.archive.documents.items()},
            source_set_revision=self.archive.source_set_revision(),
        )
        body = urlencode({
            "_reconciliation_revision": current["case_revision"],
            "_line_id": current["lines"][0]["line_id"],
            "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
            "_event_id": "event-idempotent", "_action": "confirmed",
            "_candidate_document_id": "receipt-1", "_reviewer_note": "Confrontato",
        }).encode("ascii")
        first = _request(self.app, "POST", "/cases/case-1/reconciliation/review", body, "application/x-www-form-urlencoded")
        second = _request(self.app, "POST", "/cases/case-1/reconciliation/review", body, "application/x-www-form-urlencoded")
        self.assertEqual(first[0], "200 OK")
        self.assertEqual(second[0], "200 OK")
        self.assertIn("già stata salvata", second[2].decode("utf-8"))
        self.assertEqual(len(self.archive.case["review_events"]), 1)
        self.assertEqual(len(self.archive.saved), 1)

    def test_export_is_explicit_local_json_download_with_machine_status(self):
        from alfa_document_intelligence.expense_reconciliation import build_reconciliation

        line = self.archive.documents["statement"].record["expense_lines"][0]
        current = build_reconciliation(
            "case-1", "statement", self.archive.case["statement_sha256"], [line],
            self.archive.case["attachments"],
            {key: value.record for key, value in self.archive.documents.items()},
            source_set_revision=self.archive.source_set_revision(),
        )
        review = urlencode({
            "_reconciliation_revision": current["case_revision"],
            "_line_id": current["lines"][0]["line_id"],
            "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
            "_event_id": "event-export", "_action": "confirmed",
            "_candidate_document_id": "receipt-1", "_reviewer_note": "Verificato",
        }).encode("ascii")
        self.assertEqual(_request(
            self.app, "POST", "/cases/case-1/reconciliation/review", review,
            "application/x-www-form-urlencoded",
        )[0], "200 OK")
        status, headers, payload = _request(self.app, path="/cases/case-1/export")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers.get("Content-Disposition"), 'attachment; filename="expense-reconciliation.json"')
        exported = json.loads(payload)
        self.assertEqual(exported["case_id"], "case-1")
        self.assertEqual(exported["lines"][0]["status"], "confirmed")
        self.assertTrue(exported["lines"][0]["suggestions"], "machine proposals remain separate from the human status")
        self.assertEqual(exported["review_events"][0]["action"], "confirmed")
        self.assertIn("evidence_sha256", exported["lines"][0])

    def test_statement_and_candidate_show_local_source_page_links(self):
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"/cases/case-1/documents/statement/pages/1.png", page)
        self.assertIn(b"/cases/case-1/documents/receipt-1/pages/1.png", page)

    def test_source_page_route_only_serves_documents_bound_to_the_case(self):
        with patch(
            "alfa_document_intelligence.local_intake_app._source_page_png",
            return_value=b"synthetic-page-image",
        ):
            status, headers, body = _request(
                self.app, path="/cases/case-1/documents/statement/pages/1.png",
            )
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(body, b"synthetic-page-image")
            status, _, _ = _request(
                self.app, path="/cases/case-1/documents/other-case-doc/pages/1.png",
            )
            self.assertEqual(status, "404 Not Found")

    def test_reconciliation_html_escapes_untrusted_source_text(self):
        line = self.archive.documents["statement"].record["expense_lines"][0]
        line["description"]["value"] = "<script>alert(1)</script>"
        self.archive.documents["receipt-1"].record["source"]["original_filename"] = '<img src=x onerror="1">'
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertNotIn(b"<script>alert(1)</script>", page)
        self.assertNotIn(b'<img src=x onerror="1">', page)
        self.assertIn(b"&lt;img src=x onerror=&quot;1&quot;&gt;", page)

    def test_attachment_exclusion_is_explicit_reasoned_and_revision_bound(self):
        case_revision = self.archive.case["case_revision"]
        body = urlencode({
            "_case_revision": case_revision, "_included": "false",
            "_reason": "Illeggibile, da verificare a mano", "_event_id": "inclusion-event-1",
        }).encode("ascii")
        status, _, response = _request(
            self.app, "POST", "/cases/case-1/attachments/receipt-1/inclusion", body,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Giustificativo escluso dal prossimo OCR", response)
        self.assertFalse(self.archive.case["attachments"][0]["included"])
        self.assertEqual(self.archive.case["inclusion_events"][0]["reason"], "Illeggibile, da verificare a mano")
        intake = _request(self.app, path="/cases/case-1/intake")[2]
        self.assertIn(b"Cronologia inclusione ed esclusione", intake)
        self.assertIn("Illeggibile, da verificare a mano".encode("utf-8"), intake)
        reinclusion = urlencode({
            "_case_revision": self.archive.case["case_revision"], "_included": "true",
            "_reason": "Documento recuperato", "_event_id": "inclusion-event-2",
        }).encode("ascii")
        status, _, included = _request(
            self.app, "POST", "/cases/case-1/attachments/receipt-1/inclusion", reinclusion,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Giustificativo incluso nel prossimo OCR", included)
        self.assertTrue(self.archive.case["attachments"][0]["included"])

    def test_intake_lists_attachments_without_exposing_source_filenames_and_allows_reinclusion(self):
        status, _, page = _request(self.app, path="/cases/case-1/intake")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Giustificativi acquisiti", page)
        self.assertIn(b"Escludi dal prossimo OCR", page)
        self.assertNotIn(b"synthetic", page.lower())

    def test_stale_attachment_inclusion_is_rejected(self):
        body = urlencode({
            "_case_revision": "0" * 64, "_included": "false",
            "_reason": "Test sintetico", "_event_id": "inclusion-event-stale",
        }).encode("ascii")
        status, _, _ = _request(
            self.app, "POST", "/cases/case-1/attachments/receipt-1/inclusion", body,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "409 Conflict")
        self.assertTrue(self.archive.case["attachments"][0]["included"])
        self.assertEqual(self.archive.case["inclusion_events"], [])

    def test_missing_support_and_unmatched_receipts_are_visible(self):
        self.archive.documents["receipt-1"].record["fields"] = {}
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Supporto non trovato", page)
        self.assertIn(b"Giustificativi non abbinati", page)
        self.assertIn(b"synthetic-fiscal-receipt-001.pdf", page)

    def test_stale_processing_results_cannot_be_reconciled_until_reprocessed(self):
        self.archive.case["processing"]["state"] = "stale"
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "409 Conflict")
        self.assertIn(b"Elabora localmente la nota spese", page)

    def test_changed_attachment_hash_fails_closed_against_case_binding(self):
        self.archive.documents["receipt-1"].record["source"]["sha256"] = "e" * 64
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "500 Internal Server Error")
        self.assertIn(b"Fascicolo non disponibile", page)
        self.assertNotIn(b"e" * 64, page)

    def test_review_and_export_stay_separate_from_chatgpt_handoff(self):
        status, _, page = _request(self.app, path="/cases/case-1/reconciliation")
        self.assertEqual(status, "200 OK")
        self.assertNotIn(b"/chatgpt", page)
        self.assertNotIn("approvazione".encode("utf-8"), page.lower())
        self.assertNotIn(b"pagamento", page.lower())


if __name__ == "__main__":
    unittest.main()
