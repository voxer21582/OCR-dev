"""Synthetic integration contract for multipage TIFF processing provenance."""
from __future__ import annotations

from io import BytesIO
import hashlib
import unittest

from alfa_document_intelligence.document_decoder import DecodedPage
from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter
from tests.test_ingestion import make_tiff


class _SyntheticEngine:
    def predict(self, _image):
        return [{"res": {
            "rec_texts": ["Totale EUR 12,34"],
            "rec_scores": [0.95],
            "rec_polys": [[[1, 1], [3, 1], [3, 2], [1, 2]]],
        }}]


class MultipageTiffProcessingContractTests(unittest.TestCase):
    def test_inventory_to_analysis_preserves_each_page_and_source_evidence(self):
        source_bytes = make_tiff([(8, 6), (6, 4), (5, 4)])
        batch = materialize_stream_batch([
            ("synthetic-multipage.tiff", BytesIO(source_bytes)),
        ])
        document_id = "doc-tiff-1"
        intake = create_expense_report_intake_session(
            batch,
            expense_report_id="report-tiff-1",
            note_document_id=document_id,
            document_ids=[document_id],
            session_id="session-tiff-1",
            received_at="2026-11-06T00:00:00+00:00",
        )
        record = intake.documents[document_id]
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        self.assertEqual(record["source"]["media_type"], "image/tiff")
        self.assertEqual(record["source"]["sha256"], source_sha256)

        def synthetic_decoder(data, media_kind, *, source_sha256, limits):
            self.assertEqual(data, source_bytes)
            self.assertEqual(media_kind, "tiff")
            self.assertEqual(source_sha256, hashlib.sha256(data).hexdigest())
            for page_number, (width, height) in enumerate(
                ((8, 6), (6, 4), (5, 4)), start=1
            ):
                yield DecodedPage(
                    RasterPage(page_number, width, height, bytes(page_number) * width * height * 3),
                    3,
                )

        adapter = PaddleOCRAdapter(
            _SyntheticEngine(), "synthetic-test", image_decoder=lambda page: page
        )
        result = process_document_record(
            record,
            intake.source_bytes[document_id],
            adapter,
            decoder=synthetic_decoder,
        )

        self.assertEqual(result["processing"]["ocr"]["status"], "completed")
        self.assertEqual(result["source"]["page_count"], 3)
        self.assertEqual(
            result["pages"],
            [
                {"page_number": 1, "width_px": 8, "height_px": 6},
                {"page_number": 2, "width_px": 6, "height_px": 4},
                {"page_number": 3, "width_px": 5, "height_px": 4},
            ],
        )
        references = result["fields"]["total_amount"]["evidence"]
        self.assertEqual({item["source_sha256"] for item in references}, {source_sha256})
        self.assertEqual({item["page_number"] for item in references}, {1, 2, 3})
        self.assertTrue(all(item["region"] for item in references))


if __name__ == "__main__":
    unittest.main()
