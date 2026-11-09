"""Synthetic checks for RapidOCR result shape and processing failure handling."""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import unittest

from alfa_document_intelligence.document_decoder import DecodedPage
from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.rapidocr_adapter import RapidOCRAdapter


def _adapter(result):
    return RapidOCRAdapter(lambda _image: result, "3.10.0", image_decoder=lambda _page: None)


def _decode(_data, _kind, *, source_sha256, limits):
    yield DecodedPage(RasterPage(1, 1, 1, b"rgb"), 1)


class RapidOCROutputShapeTests(unittest.TestCase):
    def test_rejects_unknown_and_partial_result_objects(self):
        invalid = (
            object(), {}, SimpleNamespace(),
            SimpleNamespace(boxes=None),
            SimpleNamespace(txts=None, scores=None),
            SimpleNamespace(boxes=[], txts=[]),
        )
        for result in invalid:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    _adapter(result).recognize(RasterPage(1, 1, 1, b"rgb"), ("it", "en"))

    def test_preserves_existing_empty_result_shapes(self):
        for result in (None, SimpleNamespace(boxes=None, txts=None, scores=None)):
            with self.subTest(result=result):
                self.assertEqual(
                    _adapter(result).recognize(RasterPage(1, 1, 1, b"rgb"), ("it", "en")), ()
                )

    def test_invalid_result_fails_processing_without_mutating_input(self):
        batch = materialize_stream_batch([("synthetic.pdf", BytesIO(b"%PDF-1.7\nsynthetic"))])
        intake = create_expense_report_intake_session(
            batch, expense_report_id="report-1", note_document_id="doc-1",
            document_ids=["doc-1"], session_id="session-1",
            received_at="2026-10-15T10:00:00+00:00",
        )
        original = intake.documents["doc-1"]
        before = deepcopy(original)
        result = process_document_record(
            original, intake.source_bytes["doc-1"], _adapter(object()), decoder=_decode,
        )
        self.assertEqual(result["processing"]["ocr"], {"status": "failed", "error_code": "ocr_failed"})
        self.assertEqual(result["fields"], before["fields"])
        self.assertEqual(original, before)
        self.assertIsNot(result, original)


if __name__ == "__main__":
    unittest.main()
