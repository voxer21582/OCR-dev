"""Synthetic evidence-bound tests for OCR statement-line proposals."""
import hashlib
import unittest

from alfa_document_intelligence.expense_line_extraction import extract_expense_lines, validate_expense_lines
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken


def _token(token_id, text, x1, y1, x2, y2, score=0.95):
    return OCRToken(
        token_id, text,
        ((x1, y1), (x2, y1), (x2, y2), (x1, y2)),
        score,
    )


class ExpenseLineExtractionTests(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha256(b"synthetic statement").hexdigest()

    def page(self, number, tokens):
        return OCRPageResult(self.digest, number, "FakeOCR", "1", "it+en", tuple(tokens))

    def test_groups_tokens_by_visual_row_and_keeps_region_and_source_evidence(self):
        result = extract_expense_lines([
            self.page(1, [
                _token("p1-t1", "Taxi", .05, .10, .20, .14),
                _token("p1-t2", "12,34", .75, .10, .92, .14),
                _token("p1-t3", "Hotel", .05, .20, .22, .24),
                _token("p1-t4", "80,00", .74, .20, .91, .24),
            ])
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["description"]["value"], "Taxi 12,34")
        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "12.34")
        evidence = amount["evidence"][0]
        self.assertEqual(evidence["source_sha256"], self.digest)
        self.assertEqual(evidence["page_number"], 1)
        self.assertEqual(evidence["token_ids"], ["p1-t1", "p1-t2"])
        self.assertEqual(evidence["literal"], "Taxi 12,34")
        self.assertEqual(evidence["region"]["coordinate_space"], "normalized_page")

    def test_multiple_amounts_remain_uncertain_with_alternatives(self):
        result = extract_expense_lines([
            self.page(1, [
                _token("p1-t1", "2 x 10,00", .1, .1, .5, .15),
                _token("p1-t2", "20,00", .7, .1, .9, .15),
            ])
        ])
        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "uncertain")
        self.assertIsNone(amount["value"])
        self.assertEqual(
            [item["value"] for item in amount["alternatives"]], ["10.00", "20.00"],
        )
        self.assertEqual(amount["evidence"][0]["source_sha256"], self.digest)

    def test_each_page_gets_stable_unique_line_ids_and_explicit_missing_values(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "Spese viaggio", .1, .1, .5, .15)]),
            self.page(2, [_token("p2-t1", "EUR 35,50", .1, .1, .5, .15)]),
        ])
        self.assertEqual([row["line_id"] for row in result], ["line-p0001-00001", "line-p0002-00001"])
        self.assertEqual(result[0]["amount"]["status"], "absent")
        self.assertEqual(result[1]["amount"]["value"], "35.50")
        self.assertEqual(result[1]["currency"]["value"], "EUR")
        self.assertEqual(result[1]["date"]["status"], "absent")

    def test_dollar_symbol_stays_uncertain_without_an_explicit_currency_code(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "$ 50.00", .1, .1, .5, .15)])
        ])

        currency = result[0]["currency"]
        self.assertEqual(currency["status"], "uncertain")
        self.assertIsNone(currency["value"])
        self.assertEqual([item["value"] for item in currency["alternatives"]], ["$"])

        identified = extract_expense_lines([
            self.page(1, [_token("p1-t1", "$ 50.00 USD", .1, .1, .5, .15)])
        ])[0]["currency"]
        self.assertEqual(identified["status"], "observed")
        self.assertEqual(identified["value"], "USD")

    def _uncertain_amount_line(self):
        result = extract_expense_lines([
            self.page(1, [
                _token("p1-t1", "2 x 10,00", .1, .1, .5, .15),
                _token("p1-t2", "20,00", .7, .1, .9, .15),
            ])
        ])
        return result

    def test_alternative_evidence_requires_a_normalized_page_region(self):
        result = self._uncertain_amount_line()
        result[0]["amount"]["alternatives"][0]["evidence"][0].pop("region")

        issues = validate_expense_lines(result, self.digest, {1})

        self.assertTrue(any("alternative evidence requires a normalized page region" in issue for issue in issues))

    def test_alternative_evidence_requires_ocr_producer_metadata(self):
        result = self._uncertain_amount_line()
        result[0]["amount"]["alternatives"][0]["evidence"][0].pop("producer")

        issues = validate_expense_lines(result, self.digest, {1})

        self.assertTrue(any("alternative evidence producer is invalid" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
