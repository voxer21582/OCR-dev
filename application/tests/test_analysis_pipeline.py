import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from alfa_document_intelligence.analysis_pipeline import (
    AnalysisPipelineError,
    analyze_ocr_results,
)
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_hotel_document.json"
POLYGON = ((0.1, 0.2), (0.8, 0.2), (0.8, 0.4), (0.1, 0.4))


class AnalysisPipelineTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.document["processing"]["ocr"]["status"] = "completed"
        self.original = copy.deepcopy(self.document)
        self.page = OCRPageResult(
            self.document["source"]["sha256"], 1, "synthetic-ocr", "test-1", "it+en",
            (
                OCRToken("check-in", "Check-in: 12/10/2026", POLYGON),
                OCRToken("check-out", "Check-out: 14/10/2026", POLYGON),
                OCRToken("total", "Totale EUR 120,00", POLYGON),
            ),
        )

    def test_enriches_copy_with_review_required_candidates_and_validation(self):
        result = analyze_ocr_results(self.document, [self.page])
        self.assertEqual(self.document, self.original)
        self.assertEqual(result.document["fields"]["total_amount"]["value"], "110.00")
        self.assertEqual(result.unapplied_proposals["total_amount"]["status"], "uncertain")
        self.assertEqual(result.document["fields"]["check_in_date"]["status"], "uncertain")
        self.assertEqual(result.document["processing"]["semantic_extraction"]["status"], "completed")
        self.assertEqual(result.document["processing"]["document_validation"]["status"], "completed")
        self.assertEqual(len(result.document["validation_findings"]), 1)
        self.assertEqual(result.document["validation_findings"][0]["outcome"], "indeterminate")


    def test_pipeline_passes_expense_report_family_to_context_extraction(self):
        document = copy.deepcopy(self.document)
        document["document_family"] = "expense_report"
        page = OCRPageResult(
            document["source"]["sha256"], 1, "synthetic-ocr", "test-1", "it+en",
            (
                OCRToken("traveler", "Nome trasfertista: Ada Rossi", POLYGON),
                OCRToken("destination", "Destinazione trasferta: Milano", POLYGON),
                OCRToken("purpose", "Causale trasferta: incontro cliente", POLYGON),
                OCRToken("start", "Inizio trasferta: 01/02/2026", POLYGON),
                OCRToken("end", "Fine trasferta: 03/02/2026", POLYGON),
            ),
        )

        result = analyze_ocr_results(document, [page])

        for field_name in (
            "traveler_name", "trip_destination", "trip_purpose",
            "trip_start_date", "trip_end_date",
        ):
            candidate = result.document["fields"][field_name]
            self.assertEqual(candidate["status"], "uncertain")
            self.assertIsNone(candidate["value"])
            self.assertEqual(
                candidate["evidence"][0]["source_sha256"],
                document["source"]["sha256"],
            )
        self.assertEqual(
            result.document["fields"]["traveler_name"]["evidence"][0]["literal"],
            "Nome trasfertista: Ada Rossi",
        )

    def test_requires_completed_ingestion_and_ocr_stages(self):
        self.document["processing"]["ocr"]["status"] = "not_started"
        with self.assertRaisesRegex(AnalysisPipelineError, "OCR must be completed"):
            analyze_ocr_results(self.document, [self.page])
        self.document["processing"]["ocr"]["status"] = "completed"
        self.document["processing"]["ingestion"]["status"] = "in_progress"
        with self.assertRaisesRegex(AnalysisPipelineError, "ingestion must be completed"):
            analyze_ocr_results(self.document, [self.page])

    def test_rejects_incomplete_page_results_before_semantic_proposals(self):
        self.assertEqual(getattr(self.page, "status", None), "complete")
        for status in ("partial", "failed"):
            with self.subTest(status=status):
                page = OCRPageResult(
                    source_sha256=self.page.source_sha256,
                    page_number=self.page.page_number,
                    engine_name=self.page.engine_name,
                    engine_version=self.page.engine_version,
                    language=self.page.language,
                    tokens=self.page.tokens,
                    status=status,
                )
                with patch(
                    "alfa_document_intelligence.analysis_pipeline.propose_common_fields"
                ) as propose, patch(
                    "alfa_document_intelligence.analysis_pipeline.extract_expense_lines"
                ) as extract:
                    with self.assertRaisesRegex(
                        AnalysisPipelineError, "every OCR page must be complete"
                    ):
                        analyze_ocr_results(self.document, [page])
                propose.assert_not_called()
                extract.assert_not_called()
                self.assertEqual(self.document, self.original)

    def test_rejects_mismatched_source_page_inventory_and_result_type(self):
        wrong_source = OCRPageResult("b" * 64, 1, "synthetic-ocr", "test-1", "it+en", ())
        with self.assertRaisesRegex(AnalysisPipelineError, "source hash"):
            analyze_ocr_results(self.document, [wrong_source])
        extra_page = copy.deepcopy(self.document)
        extra_page["pages"].append({"page_number": 2, "width_px": 1000, "height_px": 1400})
        with self.assertRaisesRegex(AnalysisPipelineError, "every inventoried page"):
            analyze_ocr_results(extra_page, [self.page])
        with self.assertRaisesRegex(AnalysisPipelineError, "OCRPageResult"):
            analyze_ocr_results(self.document, [object()])

    def test_rejects_malformed_document_contract(self):
        self.document["source"]["sha256"] = "invalid"
        with self.assertRaisesRegex(AnalysisPipelineError, "record contract failed"):
            analyze_ocr_results(self.document, [self.page])



class OverflowPipelineTests(AnalysisPipelineTests):
    def test_overflow_code_propagates_without_output(self):
        tokens = tuple(OCRToken(str(i), '12,50', POLYGON) for i in range(101))
        page = OCRPageResult(self.document['source']['sha256'], 1, 'synthetic', '1', 'it', tokens)
        with self.assertRaises(AnalysisPipelineError) as caught:
            analyze_ocr_results(self.document, [page])
        self.assertEqual(caught.exception.code, 'semantic_proposal_field_limit')
        self.assertEqual(self.document, self.original)


if __name__ == "__main__":
    unittest.main()
