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

    def test_unicode_minus_sign_is_preserved_in_negative_amount(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "−12,34", .1, .1, .3, .15)])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "-12.34")
        self.assertEqual(amount["normalization"]["original_literal"], "−12,34")
        self.assertEqual(amount["evidence"][0]["literal"], "−12,34")

    def test_unicode_minus_as_separate_token_stays_bound_to_negative_amount(self):
        result = extract_expense_lines([
            self.page(1, [
                _token("p1-minus", "−", .1, .1, .13, .15),
                _token("p1-amount", "12,34", .14, .1, .3, .15),
            ])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "-12.34")
        self.assertEqual(amount["normalization"]["original_literal"], "− 12,34")
        self.assertEqual(amount["evidence"][0]["token_ids"], ["p1-minus", "p1-amount"])

    def test_unicode_minus_followed_by_tab_stays_bound_to_negative_amount(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "−\t12,34", .1, .1, .3, .15)])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "-12.34")
        self.assertEqual(amount["normalization"]["original_literal"], "−\t12,34")

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

    def test_rejects_pages_bound_to_different_source_documents(self):
        foreign_page = OCRPageResult(
            "b" * 64, 2, "FakeOCR", "1", "it+en",
            (_token("p2-t1", "EUR 35,50", .1, .1, .5, .15),),
        )

        with self.assertRaisesRegex(ValueError, "one source document"):
            extract_expense_lines([
                self.page(1, [_token("p1-t1", "Spese viaggio", .1, .1, .5, .15)]),
                foreign_page,
            ])

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

    def test_explicit_currency_code_does_not_hide_ambiguous_dollar_symbol(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "EUR $ 50.00", .1, .1, .5, .15)])
        ])

        currency = result[0]["currency"]
        self.assertEqual(currency["status"], "uncertain")
        self.assertIsNone(currency["value"])
        self.assertEqual(
            [item["value"] for item in currency["alternatives"]], ["EUR", "$"],
        )

    def test_matching_dollar_currency_codes_resolve_the_symbol(self):
        for code in ("USD", "CAD", "AUD"):
            with self.subTest(code=code):
                currency = extract_expense_lines([
                    self.page(1, [_token("p1-t1", f"{code} $ 50.00", .1, .1, .5, .15)])
                ])[0]["currency"]

                self.assertEqual(currency["status"], "observed")
                self.assertEqual(currency["value"], code)
                self.assertEqual(currency["alternatives"], [])

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


class AdjacentCurrencyAmountTests(unittest.TestCase):
    """OCR often joins a currency code and its amount without a space."""

    def setUp(self):
        self.digest = hashlib.sha256(b"synthetic statement").hexdigest()

    def page(self, number, tokens):
        return OCRPageResult(self.digest, number, "FakeOCR", "1", "it+en", tuple(tokens))

    def _amount_of(self, text):
        lines = extract_expense_lines([self.page(1, [_token("p1-t1", text, .05, .10, .90, .14)])])
        return lines[0]["amount"], lines[0]["currency"]

    def test_amount_attached_to_currency_code_is_read(self):
        for text in ("Ricevuta n.001 EUR11,37", "Ricevuta n.001 eur11,37", "Ricevuta n.001 USD11,37"):
            with self.subTest(text=text):
                amount, _ = self._amount_of(text)
                self.assertEqual((amount["status"], amount["value"]), ("observed", "11.37"))

    def test_attached_form_matches_spaced_and_symbol_forms(self):
        values = {
            text: self._amount_of(text)[0]["value"]
            for text in ("Taxi EUR11,37", "Taxi EUR 11,37", "Taxi €11,37")
        }
        self.assertEqual(set(values.values()), {"11.37"})

    def test_attached_amount_keeps_the_row_text_as_evidence(self):
        amount, currency = self._amount_of("Taxi EUR11,37")
        self.assertEqual(amount["evidence"][0]["literal"], "Taxi EUR11,37")
        self.assertEqual(currency["value"], "EUR")

    def test_letters_that_are_not_a_currency_code_still_block_the_amount(self):
        for text in ("Taxi ABC11,37", "Taxi XEUR11,37", "Taxi EURO11,37"):
            with self.subTest(text=text):
                amount, _ = self._amount_of(text)
                self.assertEqual(amount["status"], "absent")


class AmbiguousDateHintTests(unittest.TestCase):
    """Owner decision D3 / assumption A8: a visible, reversible day/month hint."""

    def setUp(self):
        self.digest = hashlib.sha256(b"synthetic statement dates").hexdigest()

    def _date_of(self, text, **kwargs):
        page = OCRPageResult(self.digest, 1, "FakeOCR", "1", "it+en",
                             (_token("p1-t1", text, .05, .10, .90, .14),))
        return extract_expense_lines([page], **kwargs)[0]["date"]

    def _rules(self, candidate):
        return [(item["value"], item["normalization"]["rule_id"]) for item in candidate["alternatives"]]

    def test_default_preselects_day_month_and_keeps_the_date_uncertain(self):
        candidate = self._date_of("02/11/2026 Taxi 11,37")
        self.assertEqual(candidate["status"], "uncertain")
        self.assertIsNone(candidate["value"])
        self.assertEqual(self._rules(candidate), [
            ("2026-11-02", "date-dmy-hint"),
            ("2026-02-11", "iso-date"),
        ])

    def test_italian_mixed_and_unknown_documents_get_the_day_month_hint(self):
        for language in ("it", "mixed", "unknown"):
            with self.subTest(language=language):
                candidate = self._date_of("02/11/2026 Taxi 11,37", document_language=language)
                self.assertEqual(self._rules(candidate)[0], ("2026-11-02", "date-dmy-hint"))

    def test_english_documents_get_no_hint(self):
        candidate = self._date_of("02/11/2026 Taxi 11,37", document_language="en")
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual({rule for _, rule in self._rules(candidate)}, {"iso-date"})

    def test_month_day_setting_puts_the_month_day_reading_first(self):
        candidate = self._date_of("02/11/2026 Taxi 11,37", date_order_hint="mdy")
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual(self._rules(candidate), [
            ("2026-02-11", "date-mdy-hint"),
            ("2026-11-02", "iso-date"),
        ])

    def test_none_setting_keeps_both_readings_without_a_hint(self):
        candidate = self._date_of("02/11/2026 Taxi 11,37", date_order_hint="none")
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual({rule for _, rule in self._rules(candidate)}, {"iso-date"})
        self.assertEqual({value for value, _ in self._rules(candidate)}, {"2026-11-02", "2026-02-11"})

    def test_unambiguous_dates_are_not_hinted(self):
        candidate = self._date_of("25/11/2026 Taxi 11,37")
        self.assertEqual(candidate["status"], "observed")
        self.assertEqual(candidate["value"], "2026-11-25")
        self.assertEqual(candidate["normalization"]["rule_id"], "iso-date")

    def test_hinted_lines_pass_validation(self):
        page = OCRPageResult(self.digest, 1, "FakeOCR", "1", "it+en",
                             (_token("p1-t1", "02/11/2026 Taxi 11,37", .05, .10, .90, .14),))
        lines = extract_expense_lines([page])
        self.assertEqual(validate_expense_lines(lines, self.digest, {1}), [])

    def test_unknown_setting_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "date order hint"):
            self._date_of("02/11/2026 Taxi 11,37", date_order_hint="ymd")


class PageHeaderRowTests(unittest.TestCase):
    """Issue #135: page headers must not become expense lines."""

    def setUp(self):
        self.digest = hashlib.sha256(b"synthetic statement headers").hexdigest()

    def page(self, number, rows):
        tokens = [
            _token(f"p{number}-t{index}", text, .05, .05 + index * .05, .90, .08 + index * .05)
            for index, text in enumerate(rows)
        ]
        return OCRPageResult(self.digest, number, "FakeOCR", "1", "it+en", tuple(tokens))

    def descriptions(self, pages):
        return [line["description"]["value"] for line in extract_expense_lines(pages)]

    def test_pagination_headers_are_not_lines(self):
        for header in ("Nota spese - pag. 1", "Pagina 1 di 3", "Page 1 of 3", "pag. 1/3"):
            with self.subTest(header=header):
                self.assertEqual(
                    self.descriptions([self.page(1, [header, "02/11/2026 Taxi EUR 11,37"])]),
                    ["02/11/2026 Taxi EUR 11,37"],
                )

    def test_header_repeated_on_every_page_is_not_a_line(self):
        pages = [
            self.page(1, ["Data Descrizione Importo", "02/11/2026 Taxi EUR 11,37"]),
            self.page(2, ["Data Descrizione Importo", "03/11/2026 Hotel EUR 80,00"]),
        ]
        self.assertEqual(self.descriptions(pages), ["02/11/2026 Taxi EUR 11,37", "03/11/2026 Hotel EUR 80,00"])

    def test_single_row_without_values_stays_an_explicit_line(self):
        lines = extract_expense_lines([self.page(1, ["Spese viaggio", "02/11/2026 Taxi EUR 11,37"])])
        self.assertEqual(lines[0]["description"]["value"], "Spese viaggio")
        self.assertEqual(lines[0]["amount"]["status"], "absent")

    def test_pagination_text_with_an_amount_stays_a_line(self):
        lines = extract_expense_lines([self.page(1, ["pag. 2 Parcheggio EUR 4,50"])])
        self.assertEqual(lines[0]["amount"]["value"], "4.50")

    def test_line_ids_follow_visual_rows_after_a_skipped_header(self):
        lines = extract_expense_lines([self.page(1, ["Nota spese - pag. 1", "02/11/2026 Taxi EUR 11,37"])])
        self.assertEqual([line["line_id"] for line in lines], ["line-p0001-00002"])


if __name__ == "__main__":
    unittest.main()
