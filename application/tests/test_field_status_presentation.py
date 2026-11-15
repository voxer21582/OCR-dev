"""GOAL field state and reason shown in the review page and in the CSV export (REQ-060)."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.document_export import CSV_EXPORT_VERSION, export_document_csv
from alfa_document_intelligence.local_intake_app import _render_editable_record

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _record() -> dict:
    record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    total = record["fields"]["total_amount"]
    evidence = total["evidence"]
    record["fields"]["total_amount"] = {
        "value": None, "status": "uncertain", "evidence": copy.deepcopy(evidence),
        "alternatives": [
            {"value": "12.34", "status": "uncertain", "evidence": copy.deepcopy(evidence)},
            {"value": "12.43", "status": "uncertain", "evidence": copy.deepcopy(evidence)},
        ],
    }
    record["fields"]["currency"] = {"value": None, "status": "absent", "evidence": [], "alternatives": []}
    return record


class FieldStatusPresentationTests(unittest.TestCase):
    def test_csv_has_goal_status_and_reason_columns(self):
        rows = list(csv.DictReader(io.StringIO(export_document_csv(_record()))))
        self.assertEqual(CSV_EXPORT_VERSION, "ocr2-document-csv-v2")
        by_field = {row["field_name"]: row for row in rows}
        self.assertEqual(by_field["merchant_name"]["goal_status"], "valido")
        self.assertEqual(by_field["merchant_name"]["goal_status_reason"], "letto dal documento")
        self.assertEqual(by_field["total_amount"]["goal_status"], "incerto")
        self.assertEqual(by_field["total_amount"]["goal_status_reason"], "più letture possibili: 2")
        self.assertEqual(by_field["currency"]["goal_status"], "mancante")
        header = next(csv.reader(io.StringIO(export_document_csv(_record()))))
        self.assertEqual(header.index("goal_status"), header.index("field_name") + 1)

    def test_review_page_shows_state_label_and_reason(self):
        html = _render_editable_record(_record(), document_id="doc-1", has_source=False)
        self.assertIn("Stato: Incerto — più letture possibili: 2", html)
        self.assertIn("Stato: Valido — letto dal documento", html)
        self.assertIn("Stato: Mancante — non trovato nel documento", html)


if __name__ == "__main__":
    unittest.main()
