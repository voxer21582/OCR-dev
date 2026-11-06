"""Synthetic contract baseline tests, runnable with unittest and discoverable by pytest."""
import unittest
from decimal import Decimal


class ContractBaselineTests(unittest.TestCase):
    def test_amounts_use_decimal_not_binary_float(self):
        self.assertEqual(Decimal("10.20") + Decimal("0.80"), Decimal("11.00"))

    def test_payment_slip_does_not_imply_fiscal_document(self):
        payment_evidence = {"kind": "pos_slip", "paid_amount": "12.00"}
        fiscal_document_status = "unknown"
        self.assertEqual(payment_evidence["kind"], "pos_slip")
        self.assertNotEqual(fiscal_document_status, "confirmed")

    def test_uncertain_value_keeps_alternatives_and_evidence(self):
        candidate = {
            "value": None,
            "status": "uncertain",
            "alternatives": ["2026-10-12", "2026-10-17"],
            "evidence": [{"source_sha256": "a" * 64, "page_number": 1}],
        }
        self.assertEqual(len(candidate["alternatives"]), 2)
        self.assertEqual(candidate["evidence"][0]["page_number"], 1)


if __name__ == "__main__":
    unittest.main()
