from io import BytesIO
import hashlib

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
