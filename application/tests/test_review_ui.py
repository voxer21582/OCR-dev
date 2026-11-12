import copy
import hashlib
import json
from pathlib import Path

import unittest
from unittest.mock import patch

from alfa_document_intelligence import review_ui
from alfa_document_intelligence.review_ui import create_review_app, serve_local


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _request(app, path="/reviews/", method="GET"):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
    }
    chunks = app(environ, start_response)
    body = b"".join(chunks)
    return captured["status"], captured["headers"], body


def _record():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _record_with_source(data, media_type="application/pdf"):
    record = _record()
    digest = hashlib.sha256(data).hexdigest()
    record["source"]["sha256"] = digest
    record["source"]["byte_length"] = len(data)
    record["source"]["media_type"] = media_type
    record["source"]["storage_ref"] = None
    record["fiscal_document_state"]["evidence"][0]["source_sha256"] = digest
    for candidate in record["fields"].values():
        for evidence in candidate["evidence"]:
            evidence["source_sha256"] = digest
    return record


class ReviewUITests(unittest.TestCase):
    def test_queue_and_detail_render_review_projection_with_source_bound_evidence(self):
        record = _record()
        app = create_review_app({record["document_id"]: record})

        status, headers, queue = _request(app)
        self.assertEqual(status, "200 OK")
        self.assertIn(record["document_id"].encode(), queue)
        self.assertIn(b"sola lettura", queue)

        status, headers, detail = _request(app, "/reviews/" + record["document_id"])
        self.assertEqual(status, "200 OK")
        self.assertIn(record["fields"]["merchant_name"]["evidence"][0]["literal"].encode(), detail)
        self.assertIn(record["source"]["sha256"].encode(), detail)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn(b"Originale non disponibile", detail)

    def test_source_preview_serves_only_matching_in_memory_pdf_bytes(self):
        data = b"%PDF-1.7\nsynthetic-only\n%%EOF\n"
        record = _record_with_source(data)
        key = record["document_id"]
        app = create_review_app({key: record}, {key: data})

        status, _, detail = _request(app, "/reviews/" + key)
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Apri documento originale", detail)

        status, headers, body = _request(app, "/reviews/" + key + "/source")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, data)
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(headers["Content-Disposition"], 'inline; filename="document.pdf"')
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Content-Security-Policy"], "sandbox; default-src 'none'")

    def test_source_preview_serves_allowed_raster_with_nosniff(self):
        data = b"\x89PNG\r\n\x1a\nsynthetic"
        record = _record_with_source(data, "image/png")
        key = record["document_id"]
        app = create_review_app({key: record}, {key: data})

        status, headers, body = _request(app, "/reviews/" + key + "/source")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, data)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_source_bytes_are_rejected_when_hash_length_or_signature_do_not_match(self):
        data = b"%PDF-1.7\nsynthetic-only\n%%EOF\n"
        record = _record_with_source(data)
        key = record["document_id"]

        tampered = data + b"tamper"
        record["source"]["byte_length"] = len(tampered)
        with self.assertRaisesRegex(ValueError, "source hash"):
            create_review_app({key: record}, {key: tampered})

        wrong_length = copy.deepcopy(record)
        wrong_length["source"]["byte_length"] += 1
        with self.assertRaisesRegex(ValueError, "source length"):
            create_review_app({key: wrong_length}, {key: data})

        wrong_signature = _record_with_source(b"plain text", "application/pdf")
        with self.assertRaisesRegex(ValueError, "signature"):
            create_review_app({key: wrong_signature}, {key: b"plain text"})

    def test_source_preview_rejects_unsupported_oversized_and_unknown_sources(self):
        key = "synthetic-invoice-001"
        html = b"%PDF-1.7\n%%EOF"
        unsupported = _record_with_source(html, "text/html")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            create_review_app({key: unsupported}, {key: html})

        record = _record_with_source(html)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            create_review_app({key: record}, {key: html}, max_source_bytes=len(html) - 1)
        with self.assertRaisesRegex(ValueError, "unknown document"):
            create_review_app({key: record}, {"other": html})

    def test_untrusted_text_is_html_escaped(self):
        record = _record()
        record["document_id"] = "<script>alert(1)</script>"
        record["fields"]["merchant_name"]["value"] = "<img src=x onerror=alert(1)>"
        record["fields"]["merchant_name"]["evidence"][0]["literal"] = "<svg onload=alert(1)>"
        app = create_review_app({"id<&": record})

        _, _, queue = _request(app)
        _, _, detail = _request(app, "/reviews/id%3C%26")
        self.assertNotIn(b"<script>", queue)
        self.assertIn(b"href=\"/reviews/id%3C%26\"", queue)
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", queue)
        self.assertNotIn(b"<img", detail)
        self.assertNotIn(b"<svg", detail)
        self.assertIn(b"&lt;img", detail)
        self.assertIn(b"&lt;svg", detail)

    def test_review_view_is_get_only_and_does_not_mutate_record(self):
        record = _record()
        original = copy.deepcopy(record)
        app = create_review_app({record["document_id"]: record})
        status, _, body = _request(app, "/reviews/", method="POST")
        self.assertEqual(status, "405 Method Not Allowed")
        self.assertIn(b"non consentito", body)
        self.assertEqual(record, original)

    def test_missing_document_and_source_return_404(self):
        app = create_review_app({})
        status, _, body = _request(app, "/reviews/missing")
        self.assertEqual(status, "404 Not Found")
        self.assertIn(b"non trovato", body)
        status, _, body = _request(app, "/reviews/missing/source")
        self.assertEqual(status, "404 Not Found")
        self.assertIn(b"non disponibile", body)

    def test_invalid_or_unverified_record_is_rejected_at_app_creation(self):
        record = _record()
        record["source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "violates document contract"):
            create_review_app({"doc": record})

    def test_server_factory_binds_only_ipv4_loopback(self):
        expected = object()
        called = {}

        def fake_make_server(host, port, app):
            called.update(host=host, port=port, app=app)
            return expected

        with patch.object(review_ui, "make_server", side_effect=fake_make_server):
            self.assertIs(serve_local({}, port=8123), expected)
            self.assertEqual(called["host"], "127.0.0.1")
            self.assertEqual(called["port"], 8123)
            self.assertTrue(callable(called["app"]))
            with self.assertRaisesRegex(ValueError, "port"):
                serve_local({}, port=65536)
