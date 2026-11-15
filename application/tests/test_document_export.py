import csv
import copy
import io
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_export import (
    ExportValidationError,
    export_document_csv,
    export_document_json,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class DocumentExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_json_export_round_trips_complete_record_without_source_bytes(self):
        exported = json.loads(export_document_json(self.fixture))
        self.assertEqual(exported, self.fixture)
        self.assertIn("sha256", exported["source"])
        self.assertNotIn("source_bytes", exported)

    def test_csv_carries_complete_review_history_as_safe_json(self):
        from alfa_document_intelligence.review_ledger import append_review_event
        record = append_review_event(self.fixture, actor_id="=synthetic", action="queued", timestamp="2026-11-15T12:00:00+00:00")
        record = append_review_event(record, actor_id="synthetic-user", action="opened", timestamp="2026-11-15T12:00:01+00:00")
        rows = list(csv.DictReader(io.StringIO(export_document_csv(record))))
        self.assertEqual(json.loads(rows[0]["review_events_json"]), record["review"]["events"])
        self.assertTrue(rows[0]["review_events_json"].startswith("["))
        self.assertTrue(all(not row["review_events_json"] for row in rows[1:]))
        self.assertEqual(json.loads(export_document_json(record))["review"]["events"], record["review"]["events"])

    def test_json_export_rejects_record_that_breaks_contract(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fields"]["total_amount"]["evidence"][0]["source_sha256"] = "0" * 64
        with self.assertRaises(ExportValidationError):
            export_document_json(invalid)

    def test_export_rejects_missing_or_tampered_review_ledger(self):
        from alfa_document_intelligence.review_ledger import append_review_event
        invalid = copy.deepcopy(self.fixture)
        invalid["review"] = {}
        for exporter in (export_document_json, export_document_csv):
            with self.subTest(exporter=exporter.__name__, case="missing"):
                with self.assertRaises(ExportValidationError):
                    exporter(invalid)
        altered = append_review_event(self.fixture, actor_id="synthetic", action="queued", timestamp="2026-11-15T12:00:00Z")
        altered["review"]["events"][0]["actor_id"] = "tampered"
        for exporter in (export_document_json, export_document_csv):
            with self.subTest(exporter=exporter.__name__, case="tampered"):
                with self.assertRaises(ExportValidationError):
                    exporter(altered)

    def test_export_rejects_missing_schema_required_property(self):
        invalid = copy.deepcopy(self.fixture)
        del invalid["document_family"]
        with self.assertRaises(ExportValidationError):
            export_document_csv(invalid)

    def test_csv_exports_one_lossless_candidate_projection_per_field(self):
        rows = list(csv.DictReader(io.StringIO(export_document_csv(self.fixture))))
        self.assertEqual(len(rows), len(self.fixture["fields"]))
        amount = next(row for row in rows if row["field_name"] == "total_amount")
        self.assertEqual(amount["source_sha256"], self.fixture["source"]["sha256"])
        self.assertEqual(json.loads(amount["candidate_json"]), self.fixture["fields"]["total_amount"])

    def test_csv_json_encodes_formula_like_literals_as_data(self):
        record = copy.deepcopy(self.fixture)
        evidence = record["fields"]["issue_date"]["evidence"][0]
        evidence["literal"] = "=HYPERLINK(\"https://example.invalid\",\"open\")"
        serialized = export_document_csv(record)
        rows = list(csv.DictReader(io.StringIO(serialized)))
        row = next(item for item in rows if item["field_name"] == "issue_date")
        candidate = json.loads(row["candidate_json"])
        self.assertEqual(candidate["evidence"][0]["literal"], evidence["literal"])
        self.assertTrue(row["candidate_json"].startswith("{"))
        for csv_row in rows:
            for cell in csv_row.values():
                self.assertFalse(cell.startswith(("=", "+", "-", "@")))

    def test_csv_json_encodes_formula_like_filename_as_data(self):
        record = copy.deepcopy(self.fixture)
        record["source"]["original_filename"] = "=2+2.pdf"
        serialized = export_document_csv(record)
        rows = list(csv.DictReader(io.StringIO(serialized)))
        self.assertEqual(
            json.loads(rows[0]["source_filename_json"]), "=2+2.pdf"
        )
        self.assertTrue(rows[0]["source_filename_json"].startswith('"'))
        for csv_row in rows:
            for cell in csv_row.values():
                self.assertFalse(cell.startswith(("=", "+", "-", "@")))

    def test_csv_with_no_fields_still_exports_document_identity(self):
        record = copy.deepcopy(self.fixture)
        record["fields"] = {}
        rows = list(csv.DictReader(io.StringIO(export_document_csv(record))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["document_id"], record["document_id"])
        self.assertEqual(rows[0]["field_name"], "")


if __name__ == "__main__":
    unittest.main()
