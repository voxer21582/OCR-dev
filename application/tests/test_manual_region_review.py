import hashlib
import html
import io
import json
import re
import struct
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

from alfa_document_intelligence.local_intake_app import (
    IntakeRequestError,
    _apply_field_correction,
    _page,
    _render_editable_record,
    _source_page_png,
    create_expense_report_app,
)
from alfa_document_intelligence.document_decoder import DecodedPage, DocumentDecodeError
from alfa_document_intelligence.manual_region_review import (
    build_human_region_evidence,
    encode_rgb8_png,
    normalized_rectangle,
)
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.review_ledger import reviewed_overlay


class _BrowserClient:
    """Follow the session-bound local URLs emitted by the application."""

    def __init__(self, app):
        self.app = app
        self.urls = {}
        self.invoke({"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "127.0.0.1:8080"})

    def invoke(self, environ):
        environ = dict(environ)
        path = environ["PATH_INFO"]
        if path != "/":
            url = urlsplit(self.urls[path])
            environ["PATH_INFO"] = url.path
            environ["QUERY_STRING"] = url.query
        response = {}
        payload = b"".join(self.app(
            environ, lambda status, headers: response.update(status=status, headers=dict(headers))
        ))
        if response["headers"].get("Content-Type", "").startswith("text/html"):
            for match in re.finditer(rb"(?:href|action|src)=[\"'](/[^\"']+)[\"']", payload):
                url = html.unescape(match.group(1).decode("utf-8"))
                self.urls[urlsplit(url).path] = url
        return response, payload


class ManualRegionEvidenceTests(unittest.TestCase):
    def test_browser_can_append_source_bound_human_correction_with_opaque_origin_token(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1}]
            record["fields"]["merchant_name"] = {
                "value": None, "status": "absent", "evidence": [], "alternatives": [],
            }
            return record

        app = create_expense_report_app(document_processor=processor)

        client = _BrowserClient(app)

        def invoke(method, path, body=b"", content_type="", origin="http://127.0.0.1:8080"):
            environ = {
                "REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": "127.0.0.1:8080",
                "CONTENT_LENGTH": str(len(body)) if body else "", "CONTENT_TYPE": content_type,
                "wsgi.input": io.BytesIO(body),
            }
            if origin is not None:
                environ["HTTP_ORIGIN"] = origin
            return client.invoke(environ)

        boundary = "synthetic-region-correction"
        source = b"%PDF-1.7\nsynthetic source\n"
        upload = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"receipt.pdf\"\r\n"
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("ascii") + source + f"\r\n--{boundary}--\r\n".encode("ascii")
        response, _ = invoke("POST", "/upload", upload, f"multipart/form-data; boundary={boundary}")
        self.assertTrue(response["status"].startswith("200"))
        assignment = b"note_document_id=doc-001"
        response, _ = invoke("POST", "/assign-note", assignment, "application/x-www-form-urlencoded")
        self.assertTrue(response["status"].startswith("200"))
        response, page = invoke("GET", "/reviews/doc-001")
        self.assertTrue(response["status"].startswith("200"))
        self.assertIn(b"data-region-image", page)
        token_match = re.search(rb'name="_ocr2_csrf" value="([A-Za-z0-9_-]+)"', page)
        self.assertIsNotNone(token_match)
        form = urlencode({
            "_ocr2_csrf": token_match.group(1).decode("ascii"), "value": "Hotel Sintetico",
            "region_page": "1", "region_x0": "0.1", "region_y0": "0.2",
            "region_x1": "0.7", "region_y1": "0.4", "review_seconds": "0",
        }).encode("ascii")
        response, result = invoke(
            "POST", "/reviews/doc-001/fields/merchant_name", form,
            "application/x-www-form-urlencoded", origin="null",
        )
        self.assertTrue(response["status"].startswith("200"))
        self.assertIn(b"Hotel Sintetico", result)
        self.assertIn(b"regione selezionata e verificata da una persona", result)

    def test_preview_route_serves_only_hash_bound_synthetic_png(self):
        def processor(record, _source):
            record["pages"] = [{"page_number": 1}]
            record["fields"]["merchant_name"] = {
                "value": None, "status": "absent", "evidence": [], "alternatives": [],
            }
            return record

        app = create_expense_report_app(document_processor=processor)
        boundary = "synthetic-preview"
        source = b"%PDF-1.7\nsynthetic source\n"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"receipt.pdf\"\r\n"
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("ascii") + source + f"\r\n--{boundary}--\r\n".encode("ascii")

        client = _BrowserClient(app)
        invoke = client.invoke

        response, _ = invoke({
            "REQUEST_METHOD": "POST", "PATH_INFO": "/upload", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
        })
        self.assertTrue(response["status"].startswith("200"))
        assignment = b"note_document_id=doc-001"
        response, _ = invoke({
            "REQUEST_METHOD": "POST", "PATH_INFO": "/assign-note", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(assignment)), "wsgi.input": io.BytesIO(assignment),
        })
        self.assertTrue(response["status"].startswith("200"))
        response, _ = invoke({
            "REQUEST_METHOD": "GET", "PATH_INFO": "/reviews/doc-001", "HTTP_HOST": "127.0.0.1:8080",
        })
        self.assertTrue(response["status"].startswith("200"))
        decoded = DecodedPage(RasterPage(1, 1, 1, b"\xff\x00\x00"), 1)
        with patch(
            "alfa_document_intelligence.local_intake_app.iter_decoded_pages",
            return_value=iter([decoded]),
        ) as decoder:
            response, preview = invoke({
                "REQUEST_METHOD": "GET", "PATH_INFO": "/reviews/doc-001/pages/1.png",
                "HTTP_HOST": "127.0.0.1:8080",
            })
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "image/png")
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")
        self.assertEqual(response["headers"]["X-Content-Type-Options"], "nosniff")
        self.assertTrue(preview.startswith(b"\x89PNG\r\n\x1a\n"))
        decoder.assert_called_once()

    def test_rejected_csrf_post_does_not_mutate_session(self):
        """Every mutating browser route must reject an untrusted Origin before effects."""
        from alfa_document_intelligence.local_intake_app import create_expense_report_app
        from urllib.parse import urlencode
        app = create_expense_report_app()

        client = _BrowserClient(app)
        invoke = client.invoke

        boundary = "synthetic-session"
        source = b"%PDF-1.7\nsynthetic receipt\n"
        upload = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"receipt.pdf\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode("ascii") + source + f"\r\n--{boundary}--\r\n".encode("ascii")
        for method, path, body, content_type in (
            ("POST", "/upload", upload, f"multipart/form-data; boundary={boundary}"),
            ("POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode(), "application/x-www-form-urlencoded"),
        ):
            response, _ = invoke({
                "REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": "127.0.0.1:8080",
                "HTTP_ORIGIN": "http://127.0.0.1:8080", "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
            })
            self.assertTrue(response["status"].startswith("200"))
        body = b"note_document_id=synthetic"
        rejected, output = invoke({
            "REQUEST_METHOD": "POST", "PATH_INFO": "/clear", "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "https://untrusted.example", "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
        })
        self.assertTrue(rejected["status"].startswith("403"))
        self.assertIn(b"Richiesta locale non valida", output)
        response, page = invoke({
            "REQUEST_METHOD": "GET", "PATH_INFO": "/reviews/doc-001", "HTTP_HOST": "127.0.0.1:8080",
        })
        self.assertTrue(response["status"].startswith("200"))
        self.assertIn(b"Stato revisione: in_progress", page)

    def test_normalized_rectangle_is_clockwise_and_bounded(self):
        self.assertEqual(
            normalized_rectangle("0.2", "0.3", "0.8", "0.9"),
            {
                "coordinate_space": "normalized_page",
                "polygon": [[0.2, 0.3], [0.8, 0.3], [0.8, 0.9], [0.2, 0.9]],
            },
        )
        for values in (
            ("0.5", "0", "0.5", "1"),
            ("NaN", "0", "1", "1"),
            ("0", "-0.1", "1", "1"),
            ("0", "0", "1.01", "1"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalized_rectangle(*values)

    def test_human_evidence_binds_hash_and_page_without_ocr_text(self):
        digest = hashlib.sha256(b"synthetic source").hexdigest()
        evidence = build_human_region_evidence(digest, 2, "0.1", "0.2", "0.4", "0.6")
        self.assertEqual(evidence["source_sha256"], digest)
        self.assertEqual(evidence["page_number"], 2)
        self.assertEqual(evidence["producer"]["stage"], "human_review")
        self.assertNotIn("literal", evidence)

    def test_png_encoder_preserves_rgb_and_enforces_limits(self):
        pixels = bytes((255, 0, 0, 0, 255, 0))
        encoded = encode_rgb8_png(2, 1, pixels)
        self.assertTrue(encoded.startswith(b"\x89PNG\r\n\x1a\n"))
        offset = 8
        chunks = []
        while offset < len(encoded):
            length = struct.unpack(">I", encoded[offset:offset + 4])[0]
            kind = encoded[offset + 4:offset + 8]
            content = encoded[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", encoded[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(kind + content) & 0xFFFFFFFF)
            chunks.append((kind, content))
            offset += length + 12
        self.assertEqual(chunks[-1], (b"IEND", b""))
        self.assertEqual(zlib.decompress(b"".join(c for k, c in chunks if k == b"IDAT")), b"\x00" + pixels)
        with self.assertRaises(ValueError):
            encode_rgb8_png(1, 1, b"\x00\x00")
        with self.assertRaises(ValueError):
            encode_rgb8_png(2, 1, pixels, max_output_bytes=16)

    def test_source_page_preview_is_hash_bound_and_in_memory(self):
        record = self._record_with_absent_field()
        source = b"synthetic source bytes"
        record["source"]["sha256"] = hashlib.sha256(source).hexdigest()
        record["source"]["byte_length"] = len(source)
        record["source"]["media_type"] = "image/png"
        decoded = DecodedPage(RasterPage(1, 1, 1, b"\xff\x00\x00"), 1)
        with patch(
            "alfa_document_intelligence.local_intake_app.iter_decoded_pages",
            return_value=iter([decoded]),
        ) as decoder:
            preview = _source_page_png(record, source, 1)
            self.assertTrue(preview.startswith(b"\x89PNG\r\n\x1a\n"))
            decoder.assert_called_once()
        with patch("alfa_document_intelligence.local_intake_app.iter_decoded_pages") as decoder:
            with self.assertRaises(DocumentDecodeError):
                _source_page_png(record, source + b"tamper", 1)
            with self.assertRaises(DocumentDecodeError):
                _source_page_png(record, source, 2)
            decoder.assert_not_called()

    def _record_with_absent_field(self):
        record = json.loads((Path(__file__).parent / "fixtures" / "synthetic_invoice.json").read_text(encoding="utf-8"))
        record["pages"] = [{"page_number": 1, "orientation": "portrait"}]
        record["fields"]["merchant_name"] = {
            "value": None, "status": "absent", "evidence": [], "alternatives": [],
        }
        return record

    def test_absent_field_correction_appends_human_region_and_preserves_extraction(self):
        record = self._record_with_absent_field()
        original = json.loads(json.dumps(record["fields"]["merchant_name"]))
        corrected = _apply_field_correction(
            record,
            field_name="merchant_name",
            value="Negozio Sintetico",
            timestamp="2026-11-08T10:00:00Z",
            region_page_number=1,
            region_coordinates=("0.1", "0.2", "0.6", "0.35"),
        )
        candidate = reviewed_overlay(corrected)["reviewed_fields"]["merchant_name"]
        evidence = candidate["evidence"][0]
        self.assertEqual(candidate["value"], "Negozio Sintetico")
        self.assertEqual(record["fields"]["merchant_name"], original)
        self.assertEqual(evidence["source_sha256"], record["source"]["sha256"])
        self.assertEqual(evidence["page_number"], 1)
        self.assertEqual(evidence["producer"]["stage"], "human_review")
        self.assertNotIn("literal", evidence)

    def test_invalid_region_is_rejected_without_rewriting_source_candidate(self):
        record = self._record_with_absent_field()
        original = json.loads(json.dumps(record["fields"]["merchant_name"]))
        with self.assertRaises(IntakeRequestError):
            _apply_field_correction(
                record,
                field_name="merchant_name",
                value="Negozio Sintetico",
                timestamp="2026-11-08T10:00:00Z",
                region_page_number=1,
                region_coordinates=("0.4", "0.2", "0.4", "0.35"),
            )
        self.assertEqual(record["fields"]["merchant_name"], original)

    def test_review_form_exposes_page_and_no_script_coordinate_fallback(self):
        record = self._record_with_absent_field()
        page = _render_editable_record(record, document_id="synthetic-1", has_source=True)
        self.assertIn("/reviews/synthetic-1/pages/1.png", page)
        self.assertIn('name="region_x0"', page)
        self.assertIn('name="region_y1"', page)
        self.assertIn("revisione umana, non come testo OCR", page)
        self.assertIn('page.addEventListener("change"', page)
        self.assertIn('svg.addEventListener("pointerdown"', page)
        self.assertIn('svg.addEventListener("pointerup"', page)
        response = {}
        _page({}, lambda status, headers: response.update(status=status, headers=dict(headers)), "200 OK", page)
        csp = response["headers"]["Content-Security-Policy"]
        self.assertIn("img-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)


if __name__ == "__main__":
    unittest.main()
