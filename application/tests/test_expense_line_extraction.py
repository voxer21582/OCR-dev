"""Synthetic evidence-bound tests for OCR statement-line proposals."""
import copy
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

    def test_identical_token_regions_are_ordered_independently_of_input(self):
        tokens = [
            _token("token-a", "Taxi", .1, .1, .5, .15),
            _token("token-b", "12,34", .1, .1, .5, .15),
        ]

        forward = extract_expense_lines([self.page(1, tokens)])
        reversed_input = extract_expense_lines([self.page(1, list(reversed(tokens)))])

        self.assertEqual(forward, reversed_input)
        evidence = forward[0]["description"]["evidence"][0]
        self.assertEqual(forward[0]["description"]["value"], "Taxi 12,34")
        self.assertEqual(evidence["token_ids"], ["token-a", "token-b"])

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

    def test_conflicting_parenthesized_signs_remain_uncertain(self):
        for literal in ("-(+12,34)", "+(-12,34)"):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]
                self.assertEqual(amount["status"], "uncertain")
                self.assertEqual({item["value"] for item in amount["alternatives"]}, {"12.34", "-12.34"})

    def test_parenthesized_amount_after_text_preserves_literal(self):
        for text in ("Spesa (12,34)", "ABC(12,34)"):
            with self.subTest(text=text):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", text, .1, .1, .7, .15)])
                ])[0]["amount"]
                self.assertEqual(amount["status"], "uncertain")
                self.assertEqual({item["value"] for item in amount["alternatives"]}, {"12.34", "-12.34"})
                self.assertEqual({item["normalization"]["original_literal"] for item in amount["alternatives"]}, {"(12,34)"})

    def test_currency_prefix_explicit_minus_is_preserved(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "EUR-12,34", .1, .1, .5, .15)])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "-12.34")
        self.assertEqual(amount["normalization"]["original_literal"], "EUR-12,34")
        self.assertEqual(amount["evidence"][0]["literal"], "EUR-12,34")
        self.assertEqual(validate_expense_lines(result, self.digest, {1}), [])

    def test_explicit_signs_outside_parentheses_keep_direction(self):
        results = [
            extract_expense_lines([
                self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
            ])[0]["amount"]
            for literal in ("-12,34", "+12,34", "−12,34")
        ]

        self.assertEqual([item["status"] for item in results], ["observed"] * 3)
        self.assertEqual([item["value"] for item in results], ["-12.34", "12.34", "-12.34"])
        self.assertEqual(
            [item["normalization"]["original_literal"] for item in results],
            ["-12,34", "+12,34", "−12,34"],
        )

    def test_parenthesized_amount_without_sign_keeps_both_interpretations(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "(12,34)", .1, .1, .5, .15)])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "uncertain")
        self.assertIsNone(amount["value"])
        self.assertEqual([item["value"] for item in amount["alternatives"]], ["12.34", "-12.34"])
        self.assertEqual(
            [item["normalization"]["original_literal"] for item in amount["alternatives"]],
            ["(12,34)", "(12,34)"],
        )
        self.assertEqual(amount["evidence"][0]["literal"], "(12,34)")
        self.assertEqual(validate_expense_lines(result, self.digest, {1}), [])

    def test_word_attached_hyphen_is_not_silently_dropped(self):
        result = extract_expense_lines([
            self.page(1, [_token("p1-t1", "ABC-12,34", .1, .1, .5, .15)])
        ])

        amount = result[0]["amount"]
        self.assertEqual(amount["status"], "uncertain")
        self.assertIsNone(amount["value"])
        self.assertEqual([item["value"] for item in amount["alternatives"]], ["12.34", "-12.34"])
        self.assertEqual(amount["evidence"][0]["literal"], "ABC-12,34")

    def test_unsigned_amount_after_attached_code_or_label_is_retained(self):
        for literal in ("EUR12,34",):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]

                self.assertEqual(amount["status"], "observed")
                self.assertEqual(amount["value"], "12.34")
                self.assertEqual(amount["evidence"][0]["literal"], literal)

    def test_product_code_is_not_certain_amount(self):
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", "SKU123.45", .1, .1, .5, .15)])
        ])[0]["amount"]
        self.assertNotEqual(amount["status"], "observed")

    def test_currency_code_inside_identifier_is_not_certain_amount(self):
        for literal in ("SKU1EUR12.34", "123EUR-12.34"):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]
                self.assertNotEqual(amount["status"], "observed")

    def test_parentheses_followed_by_currency_keep_ambiguity(self):
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", "(12.34)EUR", .1, .1, .5, .15)])
        ])[0]["amount"]
        self.assertEqual(amount["status"], "uncertain")
        self.assertEqual({item["value"] for item in amount["alternatives"]}, {"12.34", "-12.34"})

    def test_punctuation_after_signed_parentheses_keeps_negative_sign(self):
        for literal in ("-(12.34),", "-(12.34)."):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]
                self.assertEqual(amount["value"], "-12.34")

    def test_parentheses_attached_to_identifiers_remain_uncertain(self):
        for literal in ("ABC-(12.34)", "1-(12.34)", "(12.34)XYZ"):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]
                self.assertEqual(amount["status"], "uncertain")
                self.assertEqual({item["value"] for item in amount["alternatives"]}, {"12.34", "-12.34"})

    def test_explicit_minus_with_repeated_spaces_is_preserved(self):
        for literal in ("-  12,34", "EUR-  12,34"):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]

                self.assertEqual(amount["status"], "observed")
                self.assertEqual(amount["value"], "-12.34")
                self.assertEqual(amount["evidence"][0]["literal"], literal)

    def test_word_attached_explicit_plus_does_not_create_negative_alternative(self):
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", "ABC+12,34", .1, .1, .5, .15)])
        ])[0]["amount"]

        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "12.34")
        self.assertEqual(amount["alternatives"], [])
        self.assertEqual(amount["evidence"][0]["literal"], "ABC+12,34")

    def test_currency_inside_parentheses_keeps_sign_ambiguity(self):
        for literal in ("(EUR 12,34)", "($12.34)", "(12,34 €)"):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]

                self.assertEqual(amount["status"], "uncertain")
                self.assertIsNone(amount["value"])
                self.assertEqual([item["value"] for item in amount["alternatives"]], ["12.34", "-12.34"])
                self.assertEqual(
                    [item["normalization"]["original_literal"] for item in amount["alternatives"]],
                    [literal, literal],
                )

    def test_signed_currency_inside_parentheses_preserves_complete_literal(self):
        literal = "( EUR-12,34 )"
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
        ])[0]["amount"]

        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "-12.34")
        self.assertEqual(amount["normalization"]["original_literal"], literal)
        self.assertEqual(amount["evidence"][0]["literal"], literal)

    def test_sign_outside_parentheses_is_preserved_in_normalization_literal(self):
        for literal, expected in (("-(12,34)", "-12.34"), ("+(12,34)", "12.34")):
            with self.subTest(literal=literal):
                amount = extract_expense_lines([
                    self.page(1, [_token("p1-t1", literal, .1, .1, .5, .15)])
                ])[0]["amount"]

                self.assertEqual(amount["status"], "observed")
                self.assertEqual(amount["value"], expected)
                self.assertEqual(amount["normalization"]["original_literal"], literal)
                self.assertEqual(amount["evidence"][0]["literal"], literal)

    def test_unsigned_parenthesized_zero_deduplicates_equal_values(self):
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", "(0,00)", .1, .1, .5, .15)])
        ])[0]["amount"]

        self.assertEqual(amount["status"], "observed")
        self.assertEqual(amount["value"], "0.00")
        self.assertEqual(amount["alternatives"], [])

    def test_amount_results_follow_text_position_across_pattern_kinds(self):
        amount = extract_expense_lines([
            self.page(1, [_token("p1-t1", "20,00 -10,00 30,00", .1, .1, .9, .15)])
        ])[0]["amount"]

        self.assertEqual(amount["status"], "uncertain")
        self.assertEqual(
            [item["value"] for item in amount["alternatives"]],
            ["20.00", "-10.00", "30.00"],
        )

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


    def test_non_string_unhashable_line_id_returns_validation_issue(self):
        lines = extract_expense_lines([
            self.page(1, [_token("p1-t1", "Taxi 12,34", .1, .1, .5, .15)])
        ])
        lines[0]["line_id"] = ["not", "hashable"]

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any(".line_id: invalid or duplicate" in issue for issue in issues))

    def test_alternative_evidence_enforces_the_primary_evidence_constraints(self):
        mutations = (
            ("cross-page", lambda item: item.update(page_number=2), {1, 2}),
            ("oversized-literal", lambda item: item.update(literal="x" * 16_385), {1}),
            ("non-string-token-id", lambda item: item.update(token_ids=[["nested"]]), {1}),
            ("duplicate-token-id", lambda item: item.update(token_ids=["same", "same"]), {1}),
            ("oversized-token-id", lambda item: item.update(token_ids=["x" * 257]), {1}),
        )
        for label, mutate, page_numbers in mutations:
            with self.subTest(label=label):
                lines = self._uncertain_amount_line()
                evidence = copy.deepcopy(lines[0]["amount"]["evidence"][0])
                lines[0]["amount"]["alternatives"][0]["evidence"] = [evidence]
                mutate(evidence)

                issues = validate_expense_lines(lines, self.digest, page_numbers)

                self.assertTrue(issues, f"malformed {label} alternative evidence was accepted")

    def test_unhashable_primary_page_number_returns_validation_issue(self):
        lines = extract_expense_lines([
            self.page(1, [_token("p1-t1", "Taxi 12,34", .1, .1, .5, .15)])
        ])
        lines[0]["amount"]["evidence"][0]["page_number"] = []

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any("source and an inventoried page" in issue for issue in issues))

    def test_boolean_primary_page_number_is_not_treated_as_page_one(self):
        lines = extract_expense_lines([
            self.page(1, [_token("p1-t1", "Taxi 12,34", .1, .1, .5, .15)])
        ])
        lines[0]["amount"]["evidence"][0]["page_number"] = True

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any("source and an inventoried page" in issue for issue in issues))

    def test_unhashable_alternative_page_number_returns_validation_issue(self):
        lines = self._uncertain_amount_line()
        evidence = copy.deepcopy(lines[0]["amount"]["evidence"][0])
        lines[0]["amount"]["alternatives"][0]["evidence"] = [evidence]
        evidence["page_number"] = []

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any("alternative evidence is not source-bound" in issue for issue in issues))


    def test_unhashable_candidate_status_returns_validation_issue(self):
        lines = extract_expense_lines([
            self.page(1, [_token("p1-t1", "Taxi 12,34", .1, .1, .5, .15)])
        ])
        lines[0]["amount"]["status"] = []

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any("invalid candidate status" in issue for issue in issues))

    def test_unhashable_alternative_status_returns_validation_issue(self):
        lines = self._uncertain_amount_line()
        lines[0]["amount"]["alternatives"][0]["status"] = []

        issues = validate_expense_lines(lines, self.digest, {1})

        self.assertTrue(any("alternative candidate is invalid" in issue for issue in issues))

if __name__ == "__main__":
    unittest.main()
