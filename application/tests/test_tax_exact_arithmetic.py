import copy
import json
import unittest
from decimal import Inexact, Overflow, Rounded, localcontext
from pathlib import Path

from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_validation import validate_document_consistency

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class TaxExactArithmeticTests(unittest.TestCase):
    def make_record(self, base, vat, total):
        record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        template = record["fields"]["total_amount"]
        for name, value in (("taxable_base", base), ("vat_amount", vat), ("total_amount", total)):
            candidate = copy.deepcopy(template)
            candidate["value"] = value
            candidate["evidence"][0]["literal"] = f"{name}: {value}"
            candidate["normalization"]["original_literal"] = candidate["evidence"][0]["literal"]
            candidate["normalization"]["normalized_value"] = value
            record["fields"][name] = candidate
        self.assertEqual(validate_document_record(record), [], "synthetic fixture must satisfy the record contract")
        return record

    def check_case(self, base, vat, total, outcome):
        record = self.make_record(base, vat, total)
        before = copy.deepcopy(record)
        findings = validate_document_consistency(record)
        self.assertEqual(record, before)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["field_names"], ["taxable_base", "vat_amount", "total_amount"])
        expected_evidence = [record["fields"][name]["evidence"][0] for name in finding["field_names"]]
        self.assertCountEqual(finding["evidence"], expected_evidence)
        self.assertTrue(all(e["source_sha256"] == record["source"]["sha256"] for e in finding["evidence"]))
        self.assertEqual(finding["outcome"], outcome)
        self.assertEqual(finding["severity"], "info" if outcome == "pass" else "warning")
        self.assertEqual(finding["message_code"], "taxable_base_vat_sum_matches_total" if outcome == "pass" else "tax_total_arithmetic_requires_review")

    def test_large_false_matches_require_review(self):
        cases = [
            ("10000000000000000000000000000.00", "0.01", "10000000000000000000000000000.00"),
            ("9999999999999999999999999999.99", "0.02", "10000000000000000000000000000.00"),
            ("-10000000000000000000000000000.00", "-0.01", "-10000000000000000000000000000.00"),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.check_case(*case, "indeterminate")

    def test_large_exact_sums_pass_including_carry_and_negative(self):
        cases = [
            ("10000000000000000000000000000.00", "0.01", "10000000000000000000000000000.01"),
            ("9999999999999999999999999999.99", "0.01", "10000000000000000000000000000.00"),
            ("-10000000000000000000000000000.00", "-0.01", "-10000000000000000000000000000.01"),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.check_case(*case, "pass")

    def test_changed_local_decimal_precision_does_not_change_result(self):
        with localcontext() as context:
            context.prec = 4
            for total, outcome in (("123.45", "indeterminate"), ("123.46", "pass")):
                with self.subTest(total=total):
                    self.check_case("123.45", "0.01", total, outcome)

    def test_length_limit_includes_sign_and_decimal_point(self):
        at_limit = "1" * 125 + ".00"
        over_limit = "1" * 126 + ".00"
        self.assertEqual(len(at_limit), 128)
        self.assertEqual(len(over_limit), 129)
        self.check_case(at_limit, "0.00", at_limit, "pass")
        self.check_case("-" + "1" * 124 + ".00", "0.00", "-" + "1" * 124 + ".00", "pass")
        for values in ((over_limit, "0.00", over_limit), ("0.00", over_limit, over_limit), ("0.00", "0.00", over_limit)):
            with self.subTest(values=values):
                self.check_case(*values, "indeterminate")

    def test_zero_negative_and_exponential_notation(self):
        for values, outcome in [
            (("-0.00", "0.00", "0.00"), "pass"),
            (("-1.25", "0.25", "-1.00"), "pass"),
            (("1e2", "0.00", "100.00"), "indeterminate"),
        ]:
            with self.subTest(values=values):
                self.check_case(*values, outcome)

    def test_restrictive_decimal_context_and_traps_do_not_affect_arithmetic(self):
        with localcontext() as context:
            context.prec = 4
            context.Emax = 2
            context.Emin = -2
            for signal in (Inexact, Rounded, Overflow):
                context.traps[signal] = True
            self.check_case("12345.67", "0.01", "12345.68", "pass")
            self.check_case("12345.67", "0.01", "12345.67", "indeterminate")


if __name__ == "__main__":
    unittest.main()
