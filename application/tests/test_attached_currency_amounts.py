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


if __name__ == "__main__":
    unittest.main()
