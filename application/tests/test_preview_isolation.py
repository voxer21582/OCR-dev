"""Page previews decode in the isolated, bounded worker, never in the web process (REQ-030)."""
from __future__ import annotations

import hashlib
from io import BytesIO
import unittest
from unittest.mock import patch

from alfa_document_intelligence import local_intake_app
from alfa_document_intelligence.document_decoder import DecodedPage, DocumentDecodeError
from alfa_document_intelligence.ocr_adapter import RasterPage


def _record(data: bytes, media_type: str) -> dict:
    return {
        "source": {"byte_length": len(data), "sha256": hashlib.sha256(data).hexdigest(), "media_type": media_type},
        "pages": [{"page_number": 1, "width_px": 2, "height_px": 1}],
    }


class PreviewIsolationTests(unittest.TestCase):
    def test_preview_decodes_in_isolated_worker(self):
        data = b"%PDF-1.7\nsynthetic"
        calls = []

        def isolated(source_bytes, media_kind, *, source_sha256, limits, timeout_seconds, **kwargs):
            calls.append((media_kind, source_sha256, timeout_seconds))
            yield DecodedPage(RasterPage(1, 2, 1, b"\xff\xff\xff\x00\x00\x00"), 1)

        def in_process(*args, **kwargs):
            raise AssertionError("preview decoded in the web process")

        with patch.object(local_intake_app, "iter_decoded_pages_isolated", side_effect=isolated), \
                patch.object(local_intake_app, "iter_decoded_pages", side_effect=in_process):
            png = local_intake_app._source_page_png(_record(data, "application/pdf"), data, 1)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(calls, [("pdf", hashlib.sha256(data).hexdigest(), 30.0)])

    def test_malformed_pdf_preview_fails_closed(self):
        data = b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >>\n"  # truncated, no xref
        with self.assertRaises(DocumentDecodeError):
            local_intake_app._source_page_png(_record(data, "application/pdf"), data, 1)


if __name__ == "__main__":
    unittest.main()
