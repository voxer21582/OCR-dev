"""Merchant name proposed from the top lines of a receipt when no label names it (REQ-052)."""
from __future__ import annotations

import unittest

from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.semantic_proposals import propose_common_fields


def _page(lines: list[tuple[str, float]]) -> OCRPageResult:
    tokens = tuple(
        OCRToken(f"t{index}", text, ((0.1, top), (0.6, top), (0.6, top + 0.03), (0.1, top + 0.03)), 0.95)
        for index, (text, top) in enumerate(lines, 1)
    )
    return OCRPageResult(
        source_sha256="b" * 64, page_number=1, engine_name="synthetic", engine_version="1",
        language="it+en", tokens=tokens,
    )


class MerchantNameTests(unittest.TestCase):
    def test_top_line_of_a_receipt_is_an_uncertain_merchant_with_evidence(self):
        page = _page([("Bar Centrale", 0.04), ("Via Roma 1, Milano", 0.09), ("Data: 12/11/2026", 0.15), ("Totale: EUR 4,50", 0.6)])
        merchant = propose_common_fields([page])["merchant_name"]
        self.assertEqual(merchant["status"], "uncertain")
        self.assertIsNone(merchant["value"])
        self.assertEqual([item["value"] for item in merchant["alternatives"]], ["Bar Centrale", "Via Roma 1, Milano"])
        first = merchant["alternatives"][0]
        self.assertEqual(first["normalization"]["rule_id"], "merchant-top-line")
        self.assertEqual(first["evidence"][0]["token_ids"], ["t1"])

    def test_no_merchant_is_invented_when_the_top_lines_are_headings_dates_or_amounts(self):
        page = _page([("RICEVUTA 001", 0.04), ("Data: 12/11/2026", 0.09), ("Totale: EUR 4,50", 0.14), ("Bar Lontano", 0.7)])
        self.assertNotIn("merchant_name", propose_common_fields([page]))

    def test_an_explicit_label_takes_precedence(self):
        page = _page([("Bar Centrale", 0.04), ("Esercente: Caffè Esempio", 0.5)])
        merchant = propose_common_fields([page])["merchant_name"]
        self.assertEqual([item["value"] for item in merchant["alternatives"]], ["Caffè Esempio"])


    def test_expense_report_header_is_not_a_merchant(self):
        page = _page([("Mario Rossi", 0.04), ("Taxi aeroporto EUR 12,00", 0.3)])
        self.assertNotIn("merchant_name", propose_common_fields([page], document_family="expense_report"))

    def test_customer_heading_is_not_a_merchant_when_a_supplier_label_exists(self):
        page = _page([("Spett.le Beta SpA", 0.04), ("Fornitore: Acme Srl", 0.3), ("Totale EUR 10,00", 0.6)])
        self.assertNotIn("merchant_name", propose_common_fields([page]))

    def test_addressee_salutations_are_not_merchants(self):
        page = _page([("Gentile Cliente", 0.04), ("Totale EUR 10,00", 0.6)])
        self.assertNotIn("merchant_name", propose_common_fields([page]))


if __name__ == "__main__":
    unittest.main()
