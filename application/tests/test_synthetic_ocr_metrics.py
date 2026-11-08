import unittest

from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.synthetic_ocr_metrics import (
    aggregate_reports,
    evaluate_page,
)


SOURCE = "a" * 64
POLYGON = ((0.1, 0.1), (0.9, 0.1), (0.9, 0.2), (0.1, 0.2))


def page(case_id, lines):
    return OCRPageResult(
        SOURCE, 1, "synthetic-fake", "1", "it+en",
        tuple(OCRToken(f"t{i}", line, POLYGON, 1.0) for i, line in enumerate(lines, 1)),
    )


class SyntheticOCRMetricsTests(unittest.TestCase):
    def test_exact_invoice_scores_field_candidates_and_source_evidence(self):
        lines = (
            "FATTURA",
            "FORNITORE: HOTEL AURORA",
            "N DOCUMENTO: 2026-001",
            "IMPONIBILE EUR 100.00",
            "IVA 22%",
            "TOTALE EUR 122.00",
        )
        result = evaluate_page("invoice-it", page("invoice-it", lines), list(lines), lines)
        self.assertEqual(result["character_errors"], 0)
        self.assertEqual(result["word_errors"], 0)
        self.assertEqual(result["field_results"]["supplier_name"]["candidate_recalled"], 1)
        self.assertEqual(result["field_results"]["total_amount"]["candidate_recalled"], 1)
        self.assertEqual(result["field_results"]["vat_rate"]["candidate_recalled"], 1)
        self.assertEqual(result["evidence_supported"], result["evidence_total"])
        self.assertEqual(result["confirmed_candidates"], 0)

    def test_pos_payment_amount_does_not_become_fiscal_total_or_vat(self):
        lines = (
            "CARD PAYMENT SLIP",
            "MERCHANT: CAFE ROMA",
            "DATE 14 10 2026",
            "AMOUNT EUR 12.50",
            "PAYMENT APPROVED",
        )
        result = evaluate_page("pos-payment-slip", page("pos-payment-slip", lines), list(lines), lines)
        self.assertEqual(result["field_results"]["amount_candidates"]["candidate_recalled"], 1)
        self.assertEqual(result["pos_prohibited_role_proposals"], 0)
        self.assertEqual(result["confirmed_candidates"], 0)

    def test_failure_diagnostics_detect_split_cue_and_value_without_emitting_text(self):
        tokens = (
            OCRToken("label", "TOTALE EUR", POLYGON, 1.0),
            OCRToken("value", "122.00", POLYGON, 1.0),
        )
        page_result = OCRPageResult(SOURCE, 1, "synthetic-fake", "1", "it+en", tokens)
        lines = ("FATTURA", "FORNITORE: HOTEL AURORA", "IMPONIBILE EUR 100.00",
                 "IVA 22%", "TOTALE EUR 122.00")
        report = evaluate_page("invoice-it", page_result, ["TOTALE EUR", "122.00"], lines)
        failure = next(item for item in report["failed_field_diagnostics"]
                       if item["field"] == "total_amount")
        self.assertTrue(failure["cue_seen"])
        self.assertTrue(failure["value_seen"])
        self.assertFalse(failure["cue_and_value_same_token"])
        self.assertNotIn("122.00", str(report))

    def test_aggregate_reports_separate_text_from_field_metrics(self):
        lines = ("FATTURA", "FORNITORE: HOTEL AURORA", "IMPONIBILE EUR 100.00", "IVA 22%", "TOTALE EUR 122.00")
        exact = evaluate_page("invoice-it", page("invoice-it", lines), list(lines), lines)
        degraded = evaluate_page("invoice-it", page("invoice-it", lines), ["FATTURA"], lines)
        report = aggregate_reports([exact, degraded])
        self.assertEqual(report["documents"], 2)
        self.assertGreater(report["character_error_rate"], 0)
        self.assertEqual(report["fields"]["total_amount"]["eligible"], 2)
        self.assertEqual(report["confirmed_field_count"], 0)
        self.assertEqual(report["fields"]["total_amount"]["review_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
