import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_validation import (
    DocumentValidationError,
    validate_document_consistency,
)

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class HotelDateValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.record["document_family"] = "hotel_document"
        base_evidence = self.record["fields"]["issue_date"]["evidence"][0]
        check_in_evidence = copy.deepcopy(base_evidence)
        check_in_evidence["literal"] = "Check-in 12/10/2026"
        check_in_evidence["token_ids"] = ["hotel-check-in"]
        check_out_evidence = copy.deepcopy(base_evidence)
        check_out_evidence["literal"] = "Check-out 14/10/2026"
        check_out_evidence["token_ids"] = ["hotel-check-out"]
        self.record["fields"]["check_in_date"] = {
            "value": "2026-10-12", "status": "observed",
            "alternatives": [], "evidence": [check_in_evidence],
        }
        self.record["fields"]["check_out_date"] = {
            "value": "2026-10-14", "status": "observed",
            "alternatives": [], "evidence": [check_out_evidence],
        }

    def test_valid_stay_order_returns_pass_with_bound_evidence(self):
        findings = validate_document_consistency(self.record)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["outcome"], "pass")
        self.assertEqual(findings[0]["severity"], "info")
        self.assertEqual(findings[0]["field_names"], ["check_in_date", "check_out_date"])
        self.assertTrue(findings[0]["evidence"])
        self.assertEqual(len(findings[0]["evidence"]), 2)
        self.assertEqual({item["literal"] for item in findings[0]["evidence"]}, {"Check-in 12/10/2026", "Check-out 14/10/2026"})
        self.assertEqual(findings[0]["evidence"][0]["source_sha256"], self.record["source"]["sha256"])

    def test_checkout_before_checkin_returns_failure_without_mutating_record(self):
        self.record["fields"]["check_in_date"]["value"] = "2026-10-15"
        before = copy.deepcopy(self.record)
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual(finding["outcome"], "fail")
        self.assertEqual(finding["severity"], "error")
        self.assertEqual(finding["message_code"], "hotel_checkout_precedes_checkin")
        self.assertEqual(self.record, before)

    def test_uncertain_dates_are_indeterminate_not_failed_or_confirmed(self):
        candidate = self.record["fields"]["check_out_date"]
        candidate["value"] = None
        candidate["status"] = "uncertain"
        candidate["alternatives"] = [{
            "value": "2026-10-14", "status": "observed",
            "evidence": copy.deepcopy(candidate["evidence"]),
        }]
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual(finding["outcome"], "indeterminate")
        self.assertEqual(finding["severity"], "warning")
        self.assertTrue(finding["evidence"])

    def test_non_hotel_families_do_not_receive_hotel_rule(self):
        self.record["document_family"] = "invoice"
        self.assertEqual(validate_document_consistency(self.record), [])

    def test_missing_date_candidate_does_not_assert_a_contradiction(self):
        del self.record["fields"]["check_out_date"]
        self.assertEqual(validate_document_consistency(self.record), [])

    def test_malformed_record_fails_closed(self):
        self.record["fields"]["check_in_date"]["evidence"][0]["page_number"] = 99
        with self.assertRaisesRegex(DocumentValidationError, "record contract failed"):
            validate_document_consistency(self.record)


class TaxArithmeticValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        base_evidence = self.record["fields"]["total_amount"]["evidence"][0]
        taxable_evidence = copy.deepcopy(base_evidence)
        taxable_evidence["literal"] = "Imponibile 100,00"
        vat_evidence = copy.deepcopy(base_evidence)
        vat_evidence["literal"] = "IVA 23,45"
        self.record["fields"]["taxable_base"] = {
            "value": "100.00", "status": "observed",
            "alternatives": [], "evidence": [taxable_evidence],
        }
        self.record["fields"]["vat_amount"] = {
            "value": "23.45", "status": "observed",
            "alternatives": [], "evidence": [vat_evidence],
        }

    def test_exact_sum_passes_with_all_source_bound_evidence_without_mutation(self):
        before = copy.deepcopy(self.record)
        findings = validate_document_consistency(self.record)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "taxable-base-vat-total-arithmetic")
        self.assertEqual(finding["dimension"], "amount_arithmetic_consistency")
        self.assertEqual(finding["outcome"], "pass")
        self.assertEqual(finding["severity"], "info")
        self.assertEqual(finding["field_names"], ["taxable_base", "vat_amount", "total_amount"])
        self.assertEqual(len(finding["evidence"]), 3)
        self.assertEqual(
            {item["literal"] for item in finding["evidence"]},
            {"Imponibile 100,00", "IVA 23,45", "123,45 EUR"},
        )
        self.assertTrue(all(item["source_sha256"] == self.record["source"]["sha256"] for item in finding["evidence"]))
        self.assertEqual(self.record, before)

    def test_arithmetic_difference_requires_review_and_is_not_a_failure_verdict(self):
        self.record["fields"]["vat_amount"]["value"] = "22.00"
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual(finding["outcome"], "indeterminate")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["message_code"], "tax_total_arithmetic_requires_review")

    def test_uncertain_or_noncanonical_amounts_are_indeterminate(self):
        vat = self.record["fields"]["vat_amount"]
        vat["value"] = None
        vat["status"] = "uncertain"
        vat["alternatives"] = [{
            "value": "23.45", "status": "observed",
            "evidence": copy.deepcopy(vat["evidence"]),
        }]
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual(finding["outcome"], "indeterminate")
        self.assertTrue(finding["evidence"])

        vat["value"] = "NaN"
        vat["status"] = "observed"
        vat["alternatives"] = []
        finding = validate_document_consistency(self.record)[0]
        self.assertEqual(finding["outcome"], "indeterminate")

    def test_missing_tax_components_and_pos_slips_do_not_get_arithmetic_finding(self):
        del self.record["fields"]["taxable_base"]
        self.assertEqual(validate_document_consistency(self.record), [])
        self.record["fields"]["taxable_base"] = {
            "value": "100.00", "status": "observed", "alternatives": [],
            "evidence": copy.deepcopy(self.record["fields"]["total_amount"]["evidence"]),
        }
        self.record["document_family"] = "pos_slip"
        self.record["fiscal_document_state"]["status"] = "payment_evidence"
        self.assertEqual(validate_document_consistency(self.record), [])


if __name__ == "__main__":
    unittest.main()
