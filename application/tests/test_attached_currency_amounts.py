"""Amounts glued to a currency code by OCR ('Total:EUR186.03') are still read (REQ-051)."""
from __future__ import annotations

import unittest

from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.semantic_proposals import propose_common_fields

BOX = ((0.1, 0.5), (0.8, 0.5), (0.8, 0.55), (0.1, 0.55))


def _fields(text: str) -> dict:
    page = OCRPageResult(
        source_sha256="d" * 64, page_number=1, engine_name="synthetic", engine_version="1",
        language="it+en", tokens=(OCRToken("t1", text, BOX, 0.9),),
    )
    return propose_common_fields([page])


class AttachedCurrencyAmountTests(unittest.TestCase):
    def test_total_glued_to_the_currency_code(self):
        for text, expected in (("Total:EUR186.03", "186.03"), ("Totale:EUR124,52", "124.52")):
            with self.subTest(text=text):
                fields = _fields(text)
                self.assertEqual([item["value"] for item in fields["total_amount"]["alternatives"]], [expected])
                self.assertEqual(fields["total_amount"]["evidence"][0]["literal"].replace(" ", ""), text.replace(" ", ""))
                self.assertEqual(fields["currency"]["alternatives"][0]["value"], "EUR")

    def test_codes_inside_words_are_not_split(self):
        self.assertNotIn("total_amount", _fields("REF ABCEUR12.34X"))


    def test_codes_after_other_labels_are_not_split(self):
        for text in ("Rif:EUR2024,00", "Codice CAD82"):
            with self.subTest(text=text):
                fields = _fields(text)
                self.assertNotIn("total_amount", fields)
                self.assertNotIn("amount_candidates", fields)



class ColumnTotalTests(unittest.TestCase):
    def test_total_label_and_amount_in_separate_cells_of_a_row(self):
        page = OCRPageResult(
            source_sha256="d" * 64, page_number=1, engine_name="synthetic", engine_version="1", language="it+en",
            tokens=(
                OCRToken("label", "Totale", ((0.05, 0.45), (0.15, 0.45), (0.15, 0.47), (0.05, 0.47)), 0.9),
                OCRToken("value", "211,10", ((0.8, 0.45), (0.9, 0.45), (0.9, 0.47), (0.8, 0.47)), 0.9),
                OCRToken("other", "Materiale 136,17", ((0.05, 0.36), (0.9, 0.36), (0.9, 0.38), (0.05, 0.38)), 0.9),
            ),
        )
        total = propose_common_fields([page])["total_amount"]
        self.assertEqual([item["value"] for item in total["alternatives"]], ["211.10"])
        self.assertEqual(total["alternatives"][0]["evidence"][0]["token_ids"], ["label", "value"])


    def test_rightmost_amount_of_a_total_row_and_no_labelled_cells(self):
        def cell(token_id, text, x):
            return OCRToken(token_id, text, ((x, 0.45), (x + 0.1, 0.45), (x + 0.1, 0.47), (x, 0.47)), 0.9)

        page = OCRPageResult(
            source_sha256="d" * 64, page_number=1, engine_name="synthetic", engine_version="1", language="it+en",
            tokens=(cell("label", "Totale", 0.05), cell("base", "100,00", 0.4), cell("vat", "22,00", 0.6),
                    cell("total", "122,00", 0.8)),
        )
        total = propose_common_fields([page])["total_amount"]
        self.assertEqual([item["value"] for item in total["alternatives"]], ["122.00"])
        page = OCRPageResult(
            source_sha256="d" * 64, page_number=1, engine_name="synthetic", engine_version="1", language="it+en",
            tokens=(cell("label", "Totale", 0.05), cell("vat", "IVA 22% 23,45", 0.5)),
        )
        self.assertNotIn("total_amount", propose_common_fields([page]))


if __name__ == "__main__":
    unittest.main()
