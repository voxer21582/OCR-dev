import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.analysis_pipeline import analyze_ocr_results
from alfa_document_intelligence.document_validation import (
    DocumentValidationError,
    validate_document_consistency,
)
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class TripDateConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.record["document_family"] = "expense_report"
        base = self.record["fields"]["issue_date"]["evidence"][0]
        for name, value, literal in (
            ("trip_start_date", "2026-10-12", "Inizio trasferta: 12/10/2026"),
            ("trip_end_date", "2026-10-14", "Fine trasferta: 14/10/2026"),
        ):
            evidence = copy.deepcopy(base)
            evidence["literal"] = literal
            evidence["token_ids"] = [name]
            self.record["fields"][name] = {
                "value": value, "status": "observed", "alternatives": [],
                "evidence": [evidence],
            }

    def test_ordered_dates_pass_with_both_source_evidences_and_no_mutation(self):
        before = copy.deepcopy(self.record)
        findings = validate_document_consistency(self.record)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "trip-date-order")
        self.assertEqual(finding["dimension"], "date_consistency")
        self.assertEqual((finding["outcome"], finding["severity"]), ("pass", "info"))
        self.assertEqual(finding["field_names"], ["trip_start_date", "trip_end_date"])
        self.assertEqual(
            {item["literal"] for item in finding["evidence"]},
            {"Inizio trasferta: 12/10/2026", "Fine trasferta: 14/10/2026"},
        )
        self.assertEqual(len(finding["evidence"]), 2)
        self.assertTrue(all(item["source_sha256"] == self.record["source"]["sha256"]
                            and item["page_number"] == 1 and item["token_ids"]
                            for item in finding["evidence"]))
        self.assertEqual(self.record, before)

    def test_reverse_order_fails_without_mutation(self):
        self.record["fields"]["trip_end_date"]["value"] = "2026-10-11"
        before = copy.deepcopy(self.record)
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual((finding["outcome"], finding["severity"]), ("fail", "error"))
        self.assertEqual(self.record, before)

    def test_same_day_is_valid(self):
        self.record["fields"]["trip_end_date"]["value"] = "2026-10-12"
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual((finding["outcome"], finding["severity"]), ("pass", "info"))

    def test_uncertain_date_keeps_alternative_evidence_and_is_indeterminate(self):
        end = self.record["fields"]["trip_end_date"]
        alternative_evidence = copy.deepcopy(end["evidence"][0])
        alternative_evidence["token_ids"] = ["alternative-end"]
        end.update(value=None, status="uncertain", alternatives=[{
            "value": "2026-10-14", "status": "observed",
            "evidence": [alternative_evidence],
        }])
        before = copy.deepcopy(self.record)
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual((finding["outcome"], finding["severity"]), ("indeterminate", "warning"))
        self.assertIn(alternative_evidence, finding["evidence"])
        self.assertEqual(self.record, before)

    def test_absent_date_is_indeterminate_without_invented_evidence(self):
        self.record["fields"]["trip_end_date"] = {
            "value": None, "status": "absent", "alternatives": [], "evidence": [],
        }
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual((finding["outcome"], finding["severity"]), ("indeterminate", "warning"))
        self.assertEqual(finding["evidence"], self.record["fields"]["trip_start_date"]["evidence"])

    def test_other_family_does_not_receive_trip_rule(self):
        self.record["document_family"] = "invoice"
        self.assertEqual(validate_document_consistency(self.record), [])

    def test_missing_either_field_does_not_assert_a_contradiction(self):
        for name in ("trip_start_date", "trip_end_date"):
            with self.subTest(missing=name):
                record = copy.deepcopy(self.record)
                del record["fields"][name]
                self.assertEqual(validate_document_consistency(record), [])

    def test_invalid_evidence_fails_closed(self):
        self.record["fields"]["trip_end_date"]["evidence"][0]["page_number"] = 99
        with self.assertRaisesRegex(DocumentValidationError, "record contract failed"):
            validate_document_consistency(self.record)

    def test_pipeline_proposals_remain_uncertain_and_produce_indeterminate_finding(self):
        document = copy.deepcopy(self.record)
        del document["fields"]["trip_start_date"]
        del document["fields"]["trip_end_date"]
        document["processing"]["ocr"]["status"] = "completed"
        before = copy.deepcopy(document)
        polygon = ((0.1, 0.2), (0.8, 0.2), (0.8, 0.4), (0.1, 0.4))
        page = OCRPageResult(
            document["source"]["sha256"], 1, "synthetic-ocr", "test-1", "it+en",
            (
                OCRToken("start", "Inizio trasferta: 12/10/2026", polygon),
                OCRToken("end", "Fine trasferta: 14/10/2026", polygon),
            ),
        )

        result = analyze_ocr_results(document, [page]).document

        for name in ("trip_start_date", "trip_end_date"):
            self.assertEqual(result["fields"][name]["status"], "uncertain")
            self.assertIsNone(result["fields"][name]["value"])
        findings = [f for f in result["validation_findings"] if f["rule_id"] == "trip-date-order"]
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["outcome"], findings[0]["severity"]),
                         ("indeterminate", "warning"))
        self.assertEqual(
            {item["literal"] for item in findings[0]["evidence"]},
            {"Inizio trasferta: 12/10/2026", "Fine trasferta: 14/10/2026"},
        )
        self.assertTrue(all(item["source_sha256"] == document["source"]["sha256"]
                            and item["page_number"] == 1 and item["token_ids"]
                            for item in findings[0]["evidence"]))
        self.assertEqual(document, before)


if __name__ == "__main__":
    unittest.main()
