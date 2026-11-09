import copy
import csv
import io
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_export import (
    ExportValidationError,
    export_document_csv,
    export_reviewed_document_csv,
)
from alfa_document_intelligence.review_ledger import ReviewRejected, append_review_event
from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
COLUMNS = [
    "export_format_version", "document_id", "source_sha256", "review_status",
    "extracted_document_family", "reviewed_document_family", "extracted_fiscal_json",
    "reviewed_fiscal_json", "field_name", "extracted_candidate_json", "reviewed_candidate_json",
]


class ReviewedCsvProjectionTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def event(self, record, action, event_id, **kwargs):
        return append_review_event(
            record, actor_id="synthetic-reviewer", action=action,
            timestamp="2026-10-14T10:00:00Z", event_id=event_id, **kwargs,
        )

    def reviewed_record(self):
        record = copy.deepcopy(self.record)
        record["document_family"] = "unknown"
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain", "alternatives": [
                {"value": "invoice", "status": "observed", "evidence": evidence}
            ], "evidence": evidence,
        }
        record = self.event(record, "queued", "event-1")
        record = self.event(record, "opened", "event-2")
        candidate = copy.deepcopy(record["fields"]["merchant_name"])
        candidate["value"] = '=HYPERLINK("https://example.invalid","open")'
        candidate["evidence"][0]["literal"] = candidate["value"]
        record = self.event(record, "field_corrected", "event-3", field_name="merchant_name",
                            reason_code="visual_correction", candidate=candidate)
        record = self.event(record, "field_corrected", "event-4", field_name="manual_note",
                            reason_code="visual_correction", candidate=candidate)
        family = {"value": "invoice", "status": "observed", "alternatives": [], "evidence": evidence}
        record = self.event(record, "field_corrected", "event-5", field_name="document_family",
                            reason_code="family_review", candidate=family)
        fiscal = {"status": "payment_evidence", "evidence": evidence}
        return self.event(record, "fiscal_state_corrected", "event-6", reason_code="document_type_review", fiscal_state=fiscal)

    def test_projection_preserves_extracted_and_effective_views(self):
        record = self.reviewed_record()
        original = copy.deepcopy(record)
        old_csv = export_document_csv(record)
        reader = csv.DictReader(io.StringIO(export_reviewed_document_csv(record)))
        rows = list(reader)
        self.assertEqual(reader.fieldnames, COLUMNS)
        self.assertEqual({r["field_name"] for r in rows}, set(record["fields"]) | {"manual_note", "document_family"})
        for row in rows:
            self.assertEqual(row["export_format_version"], "ocr2-reviewed-csv-v1")
            self.assertEqual(row["document_id"], record["document_id"])
            self.assertEqual(row["source_sha256"], record["source"]["sha256"])
            self.assertEqual(row["review_status"], record["review"]["status"])
            self.assertEqual(row["extracted_document_family"], "unknown")
            self.assertEqual(row["reviewed_document_family"], "invoice")
            self.assertEqual(json.loads(row["extracted_fiscal_json"]), record["fiscal_document_state"])
            self.assertEqual(json.loads(row["reviewed_fiscal_json"]), record["review"]["events"][-1]["fiscal_state"])
            for cell in row.values():
                self.assertFalse(cell.startswith(("=", "+", "-", "@")))
        by_name = {row["field_name"]: row for row in rows}
        self.assertEqual(json.loads(by_name["merchant_name"]["extracted_candidate_json"]), record["fields"]["merchant_name"])
        self.assertEqual(json.loads(by_name["merchant_name"]["reviewed_candidate_json"]), record["review"]["events"][2]["candidate"])
        self.assertEqual(by_name["manual_note"]["extracted_candidate_json"], "null")
        self.assertEqual(json.loads(by_name["manual_note"]["reviewed_candidate_json"]), record["review"]["events"][3]["candidate"])
        untouched = by_name["issue_date"]
        self.assertEqual(json.loads(untouched["reviewed_candidate_json"]), record["fields"]["issue_date"])
        self.assertEqual(record, original)
        self.assertEqual(export_document_csv(record), old_csv)

    def test_review_statuses_and_latest_correction(self):
        queued = self.event(self.record, "queued", "status-1")
        opened = self.event(queued, "opened", "status-2")
        first = copy.deepcopy(opened["fields"]["merchant_name"])
        first["value"] = "First correction"
        first["evidence"][0]["literal"] = first["value"]
        corrected = self.event(opened, "field_corrected", "status-3", field_name="merchant_name",
                               reason_code="visual_correction", candidate=first)
        second = copy.deepcopy(first)
        second["value"] = "Second correction"
        second["evidence"][0]["literal"] = second["value"]
        corrected = self.event(corrected, "field_corrected", "status-4", field_name="merchant_name",
                               reason_code="visual_correction", candidate=second)
        blocked = self.event(corrected, "flagged", "status-5", reason_code="needs_review")
        reopened = self.event(blocked, "opened", "status-6")
        completed = self.event(reopened, "completed", "status-7")
        for record, status, expected in ((queued, "queued", self.record["fields"]["merchant_name"]),
                                         (blocked, "blocked", second), (completed, "completed", second)):
            with self.subTest(status=status):
                rows = list(csv.DictReader(io.StringIO(export_reviewed_document_csv(record))))
                self.assertTrue(all(row["review_status"] == status for row in rows))
                merchant = next(row for row in rows if row["field_name"] == "merchant_name")
                self.assertEqual(json.loads(merchant["extracted_candidate_json"]), self.record["fields"]["merchant_name"])
                self.assertEqual(json.loads(merchant["reviewed_candidate_json"]), expected)

    def test_custom_family_schema_with_snapshot(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1", "families": [{"id": "custom_taxi_receipt",
                "label": "Ricevuta taxi", "title_cues": ["RICEVUTA TAXI"], "fields": []}],
        }))
        record = copy.deepcopy(self.record)
        record["schema_version"] = "0.2.0"
        record["document_family"] = "custom_taxi_receipt"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        rows = list(csv.DictReader(io.StringIO(export_reviewed_document_csv(record))))
        self.assertTrue(rows)
        self.assertTrue(all(row["extracted_document_family"] == "custom_taxi_receipt" and
                            row["reviewed_document_family"] == "custom_taxi_receipt" for row in rows))

    def test_rejects_tampered_ledger(self):
        record = self.reviewed_record()
        record["review"]["events"][2]["candidate"]["value"] = "tampered"
        with self.assertRaises(ReviewRejected):
            export_reviewed_document_csv(record)

    def test_rejects_formula_like_identifiers(self):
        record = copy.deepcopy(self.record)
        record["document_id"] = "=1+1"
        with self.assertRaises(ExportValidationError):
            export_reviewed_document_csv(record)
        record = copy.deepcopy(self.record)
        record["fields"]["=1+1"] = record["fields"]["merchant_name"]
        with self.assertRaises(ExportValidationError):
            export_reviewed_document_csv(record)

    def test_empty_fields_retains_identity_and_json_nulls(self):
        record = copy.deepcopy(self.record)
        record["fields"] = {}
        rows = list(csv.DictReader(io.StringIO(export_reviewed_document_csv(record))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["field_name"], "")
        self.assertEqual(rows[0]["extracted_candidate_json"], "null")
        self.assertEqual(rows[0]["reviewed_candidate_json"], "null")
        self.assertEqual(rows[0]["document_id"], record["document_id"])


if __name__ == "__main__":
    unittest.main()
