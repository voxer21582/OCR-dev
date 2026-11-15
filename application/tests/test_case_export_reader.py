"""An exported case is read back without loss and altered copies are refused (REQ-089)."""
from __future__ import annotations

import copy
import json
import unittest
from urllib.parse import urlencode

from alfa_document_intelligence.case_export_reader import CaseExportError, read_case_export
from alfa_document_intelligence.expense_reconciliation import build_reconciliation
from alfa_document_intelligence.local_intake_app import create_expense_report_app

from test_expense_reconciliation_ui import _Archive, _request


class CaseExportReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = _Archive()
        app = create_expense_report_app(archive_store=archive)
        try:
            line = archive.documents["statement"].record["expense_lines"][0]
            current = build_reconciliation(
                "case-1", "statement", archive.case["statement_sha256"], [line], archive.case["attachments"],
                {key: value.record for key, value in archive.documents.items()},
                source_set_revision=archive.source_set_revision(),
            )
            review = urlencode({
                "_reconciliation_revision": current["case_revision"],
                "_line_id": current["lines"][0]["line_id"],
                "_line_evidence_sha256": current["lines"][0]["evidence_sha256"],
                "_event_id": "event-reader", "_action": "confirmed",
                "_candidate_document_id": "receipt-1", "_reviewer_note": "Verificato",
            }).encode("ascii")
            assert _request(app, "POST", "/cases/case-1/reconciliation/review", review,
                            "application/x-www-form-urlencoded")[0] == "200 OK"
            status, _, data = _request(app, path="/cases/case-1/export")
            assert status == "200 OK"
            cls.text = data.decode("utf-8")
        finally:
            app.close()

    def test_round_trip_keeps_everything_and_separates_layers(self):
        read = read_case_export(self.text)
        self.assertEqual(read, json.loads(self.text))
        line = read["lines"][0]
        self.assertTrue(line["suggestions"], "machine suggestions")
        self.assertEqual(read["review_events"][0]["action"], "confirmed", "human decision")
        self.assertEqual(line["status"], "confirmed")
        self.assertEqual(len(line["evidence_sha256"]), 64, "evidence binding")

    def _altered(self, change):
        payload = json.loads(self.text)
        change(payload)
        return json.dumps(payload)

    def test_altered_exports_are_refused(self):
        changes = {
            "line amount edited": lambda p: p["lines"][0]["fields"].update(
                amount={**p["lines"][0]["fields"]["amount"], "value": "999.00"}),
            "status changed without a decision": lambda p: p["lines"][0].update(status="rejected"),
            "decision note edited": lambda p: p["review_events"][0].update(reviewer_note="altro"),
            "decision removed": lambda p: p.update(review_events=[]),
            "suggestion points elsewhere": lambda p: p["lines"][0]["suggestions"][0].update(document_id="receipt-9"),
            "attachment hash changed": lambda p: p["attachments"][0].update(source_sha256="0" * 64),
            "unknown version": lambda p: p.update(export_schema_version="9.9.9"),
            "extra field": lambda p: p.update(extra=True),
        }
        for label, change in changes.items():
            with self.subTest(label):
                with self.assertRaises(CaseExportError):
                    read_case_export(self._altered(change))
        for text in ("", "[]", "{not json", "x" * 10):
            with self.subTest(text=text[:10]):
                with self.assertRaises(CaseExportError):
                    read_case_export(text)

    def test_reading_does_not_share_state_with_the_caller(self):
        first = read_case_export(self.text)
        mutated = copy.deepcopy(first)
        mutated["lines"][0]["status"] = "x"
        self.assertEqual(read_case_export(self.text), first)


if __name__ == "__main__":
    unittest.main()
