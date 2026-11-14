from io import BytesIO
import hashlib
import unittest

from alfa_document_intelligence.document_decoder import DecodedPage
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter


class FakeEngine:
    def __init__(self, text="Totale EUR 12,34", polygon=None):
        self.text = text
        self.polygon = polygon or [[10, 10], [40, 10], [40, 20], [10, 20]]

    def predict(self, image):
        return [{
            "res": {
                "rec_texts": [self.text],
                "rec_scores": [0.95],
                "rec_polys": [self.polygon],
            }
        }]


def _intake(data=b"%PDF-1.7\nsynthetic note"):
    batch = materialize_stream_batch([("nota.pdf", BytesIO(data))])
    return create_expense_report_intake_session(
        batch,
        expense_report_id="report-1",
        note_document_id="doc-1",
        document_ids=["doc-1"],
        session_id="session-1",
        received_at="2026-10-15T10:00:00+00:00",
    )


def _decoder(page_count=1, emitted=1):
    def decode(data, media_kind, *, source_sha256, limits):
        assert hashlib.sha256(data).hexdigest() == source_sha256
        assert media_kind == "pdf"
        for number in range(1, emitted + 1):
            yield DecodedPage(
                RasterPage(number, 100, 80, b"synthetic-pixels"), page_count
            )
    return decode


def test_local_processing_binds_decoder_pages_and_returns_uncertain_fields():
    intake = _intake()
    original = intake.documents["doc-1"]
    adapter = PaddleOCRAdapter(FakeEngine(), "3.7.0", image_decoder=lambda page: None)

    result = process_document_record(
        original,
        intake.source_bytes["doc-1"],
        adapter,
        decoder=_decoder(),
    )

    assert result is not original
    assert result["source"]["sha256"] == original["source"]["sha256"]
    assert result["source"]["page_count"] == 1
    assert result["pages"] == [{"page_number": 1, "width_px": 100, "height_px": 80}]
    assert result["processing"]["ocr"]["status"] == "completed"
    assert result["processing"]["ocr"]["producer"] == {
        "stage": "ocr", "name": "PaddleOCR", "version": "3.7.0"
    }
    assert result["processing"]["semantic_extraction"]["status"] == "completed"
    assert result["schema_version"] == "0.3.0"
    assert len(result["expense_lines"]) == 1
    assert result["expense_lines"][0]["description"]["value"] == "Totale EUR 12,34"
    assert result["expense_lines"][0]["amount"]["value"] == "12.34"
    assert result["expense_lines"][0]["amount"]["evidence"][0]["source_sha256"] == original["source"]["sha256"]
    assert result["fields"]["total_amount"]["value"] is None
    assert result["fields"]["total_amount"]["alternatives"][0]["value"] == "12.34"
    assert result["fields"]["total_amount"]["status"] == "uncertain"
    assert result["fields"]["total_amount"]["evidence"][0]["source_sha256"] == original["source"]["sha256"]


def test_local_processing_records_source_hash_failure_without_mutating_input():
    intake = _intake()
    original = intake.documents["doc-1"]
    adapter = PaddleOCRAdapter(FakeEngine(), "3.7.0", image_decoder=lambda page: None)

    result = process_document_record(
        original, b"wrong bytes", adapter, decoder=_decoder()
    )

    assert result is not original
    assert result["processing"]["ocr"] == {
        "status": "failed", "error_code": "source_hash_mismatch"
    }
    assert original["processing"]["ocr"]["status"] == "not_started"
    assert result["fields"] == {}


def test_local_processing_fails_closed_when_decoder_omits_a_page():
    intake = _intake()
    adapter = PaddleOCRAdapter(FakeEngine(), "3.7.0", image_decoder=lambda page: None)
    result = process_document_record(
        intake.documents["doc-1"],
        intake.source_bytes["doc-1"],
        adapter,
        decoder=_decoder(page_count=2, emitted=1),
    )
    assert result["processing"]["ocr"] == {
        "status": "failed", "error_code": "decode_failed"
    }
    assert result["fields"] == {}


def test_local_processing_fails_closed_on_invalid_ocr_geometry():
    intake = _intake()
    adapter = PaddleOCRAdapter(
        FakeEngine(polygon=[[-1, 10], [40, 10], [40, 20], [10, 20]]),
        "3.7.0",
        image_decoder=lambda page: None,
    )
    result = process_document_record(
        intake.documents["doc-1"],
        intake.source_bytes["doc-1"],
        adapter,
        decoder=_decoder(),
    )
    assert result["processing"]["ocr"] == {
        "status": "failed", "error_code": "ocr_contract_failed"
    }
    assert result["fields"] == {}


class DocumentProcessingProgressTests(unittest.TestCase):
    def setUp(self):
        self.intake = _intake()
        self.original = self.intake.documents["doc-1"]
        self.adapter = PaddleOCRAdapter(FakeEngine(), "3.7.0", image_decoder=lambda page: None)

    @staticmethod
    def _decoder(page_count=1, emitted=1):
        def decode(data, media_kind, *, source_sha256, limits):
            assert hashlib.sha256(data).hexdigest() == source_sha256
            assert media_kind == "pdf"
            for number in range(1, emitted + 1):
                yield DecodedPage(
                    RasterPage(number, 100, 80, b"\x00" * (100 * 80 * 3)), page_count
                )
        return decode

    def test_reports_page_progress_after_each_valid_page(self):
        for reject_second_page in (False, True):
            with self.subTest(reject_second_page=reject_second_page):
                events = []

                class RecordingEngine(FakeEngine):
                    calls = 0

                    def predict(self, image):
                        self.calls += 1
                        events.append(("ocr", self.calls))
                        if reject_second_page and self.calls == 2:
                            return FakeEngine(
                                polygon=[[-1, 10], [40, 10], [40, 20], [10, 20]]
                            ).predict(image)
                        return super().predict(image)

                adapter = PaddleOCRAdapter(
                    RecordingEngine(), "3.7.0", image_decoder=lambda page: None
                )
                result = process_document_record(
                    self.original,
                    self.intake.source_bytes["doc-1"],
                    adapter,
                    decoder=self._decoder(page_count=2, emitted=2),
                    progress_callback=lambda completed, total: events.append(
                        ("progress", completed, total)
                    ),
                )
                expected = [("ocr", 1), ("progress", 1, 2), ("ocr", 2)]
                if reject_second_page:
                    self.assertEqual(result["processing"]["ocr"], {
                        "status": "failed", "error_code": "ocr_contract_failed",
                    })
                    self.assertEqual(result["pages"], [])
                    self.assertEqual(result["fields"], {})
                else:
                    expected.append(("progress", 2, 2))
                    self.assertEqual(result["source"]["page_count"], 2)
                    self.assertEqual(result["processing"]["ocr"]["status"], "completed")
                self.assertEqual(events, expected)

    def test_progress_callback_is_optional(self):
        result = process_document_record(
            self.original,
            self.intake.source_bytes["doc-1"],
            self.adapter,
            decoder=self._decoder(),
        )
        self.assertEqual(result["processing"]["ocr"]["status"], "completed")

    def test_progress_callback_failure_returns_unprocessed_failure_record(self):
        def fail_progress(_completed, _total):
            raise RuntimeError("synthetic progress channel failure")

        result = process_document_record(
            self.original,
            self.intake.source_bytes["doc-1"],
            self.adapter,
            decoder=self._decoder(),
            progress_callback=fail_progress,
        )
        self.assertIsNot(result, self.original)
        self.assertEqual(result["processing"]["ocr"], {
            "status": "failed", "error_code": "ocr_failed",
        })
        self.assertEqual(result["fields"], {})
        self.assertEqual(result["pages"], [])
        self.assertEqual(result["source"], self.original["source"])
        self.assertNotIn("page_count", self.original["source"])
        self.assertEqual(result["processing"]["semantic_extraction"]["status"], "not_started")
        self.assertEqual(result["processing"]["document_validation"]["status"], "not_started")
        self.assertEqual(self.original["processing"]["ocr"]["status"], "not_started")

class OverflowProcessingTests(unittest.TestCase):
    def test_overflow_failed_status_is_distinct_and_no_partial_fields(self):
        from unittest.mock import patch
        intake = _intake()
        adapter = PaddleOCRAdapter(FakeEngine(), '3.7.0', image_decoder=lambda page: None)
        with patch('alfa_document_intelligence.semantic_proposals.MAX_PROPOSALS_PER_FIELD', 0):
            result = process_document_record(intake.documents['doc-1'], intake.source_bytes['doc-1'], adapter, decoder=_decoder())
        self.assertEqual(result['processing']['semantic_extraction'], {'status': 'failed', 'error_code': 'semantic_proposal_field_limit'})
        self.assertEqual(result['fields'], {})
    def test_all_overflow_codes_reach_processing(self):
        from unittest.mock import patch
        from alfa_document_intelligence.analysis_pipeline import AnalysisProposalLimitError
        from alfa_document_intelligence.contracts import validate_document_record
        intake = _intake()
        adapter = PaddleOCRAdapter(FakeEngine(), '3.7.0', image_decoder=lambda page: None)
        for code in ('semantic_proposal_field_limit', 'semantic_proposal_catalog_limit', 'semantic_proposal_family_limit'):
            with self.subTest(code=code), patch('alfa_document_intelligence.document_processing.analyze_ocr_results', side_effect=AnalysisProposalLimitError(code)):
                result = process_document_record(intake.documents['doc-1'], intake.source_bytes['doc-1'], adapter, decoder=_decoder())
                self.assertEqual(result['processing']['semantic_extraction'], {'status': 'failed', 'error_code': code})
                self.assertEqual(result['fields'], {})
                self.assertEqual(validate_document_record(result), [])
