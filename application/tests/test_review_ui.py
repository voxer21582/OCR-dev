import copy
import hashlib
import json
from pathlib import Path

import pytest

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


def test_queue_and_detail_render_review_projection_with_source_bound_evidence():
    record = _record()
    app = create_review_app({record["document_id"]: record})

    status, headers, queue = _request(app)
    assert status == "200 OK"
    assert record["document_id"].encode() in queue
    assert b"sola lettura" in queue

    status, headers, detail = _request(app, "/reviews/" + record["document_id"])
    assert status == "200 OK"
    assert record["fields"]["merchant_name"]["evidence"][0]["literal"].encode() in detail
    assert record["source"]["sha256"].encode() in detail
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert b"Originale non disponibile" in detail


def test_source_preview_serves_only_matching_in_memory_pdf_bytes():
    data = b"%PDF-1.7\nsynthetic-only\n%%EOF\n"
    record = _record_with_source(data)
    key = record["document_id"]
    app = create_review_app({key: record}, {key: data})

    status, _, detail = _request(app, "/reviews/" + key)
    assert status == "200 OK"
    assert b"Apri documento originale" in detail

    status, headers, body = _request(app, "/reviews/" + key + "/source")
    assert status == "200 OK"
    assert body == data
    assert headers["Content-Type"] == "application/pdf"
    assert headers["Content-Disposition"] == 'inline; filename="document.pdf"'
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "sandbox; default-src 'none'"


def test_source_preview_serves_allowed_raster_with_nosniff():
    data = b"\x89PNG\r\n\x1a\nsynthetic"
    record = _record_with_source(data, "image/png")
    key = record["document_id"]
    app = create_review_app({key: record}, {key: data})

    status, headers, body = _request(app, "/reviews/" + key + "/source")
    assert status == "200 OK"
    assert body == data
    assert headers["Content-Type"] == "image/png"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_source_bytes_are_rejected_when_hash_length_or_signature_do_not_match():
    data = b"%PDF-1.7\nsynthetic-only\n%%EOF\n"
    record = _record_with_source(data)
    key = record["document_id"]

    tampered = data + b"tamper"
    record["source"]["byte_length"] = len(tampered)
    with pytest.raises(ValueError, match="source hash"):
        create_review_app({key: record}, {key: tampered})

    wrong_length = copy.deepcopy(record)
    wrong_length["source"]["byte_length"] += 1
    with pytest.raises(ValueError, match="source length"):
        create_review_app({key: wrong_length}, {key: data})

    wrong_signature = _record_with_source(b"plain text", "application/pdf")
    with pytest.raises(ValueError, match="signature"):
        create_review_app({key: wrong_signature}, {key: b"plain text"})


def test_source_preview_rejects_unsupported_oversized_and_unknown_sources():
    key = "synthetic-invoice-001"
    html = b"%PDF-1.7\n%%EOF"
    unsupported = _record_with_source(html, "text/html")
    with pytest.raises(ValueError, match="unsupported"):
        create_review_app({key: unsupported}, {key: html})

    record = _record_with_source(html)
    with pytest.raises(ValueError, match="exceeds"):
        create_review_app({key: record}, {key: html}, max_source_bytes=len(html) - 1)
    with pytest.raises(ValueError, match="unknown document"):
        create_review_app({key: record}, {"other": html})


def test_untrusted_text_is_html_escaped():
    record = _record()
    record["document_id"] = "<script>alert(1)</script>"
    record["fields"]["merchant_name"]["value"] = "<img src=x onerror=alert(1)>"
    record["fields"]["merchant_name"]["evidence"][0]["literal"] = "<svg onload=alert(1)>"
    app = create_review_app({"id<&": record})

    _, _, queue = _request(app)
    _, _, detail = _request(app, "/reviews/id%3C%26")
    assert b"<script>" not in queue
    assert b"href=\"/reviews/id%3C%26\"" in queue
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in queue
    assert b"<img" not in detail
    assert b"<svg" not in detail
    assert b"&lt;img" in detail
    assert b"&lt;svg" in detail


def test_review_view_is_get_only_and_does_not_mutate_record():
    record = _record()
    original = copy.deepcopy(record)
    app = create_review_app({record["document_id"]: record})
    status, _, body = _request(app, "/reviews/", method="POST")
    assert status == "405 Method Not Allowed"
    assert b"non consentito" in body
    assert record == original


def test_missing_document_and_source_return_404():
    app = create_review_app({})
    status, _, body = _request(app, "/reviews/missing")
    assert status == "404 Not Found"
    assert b"non trovato" in body
    status, _, body = _request(app, "/reviews/missing/source")
    assert status == "404 Not Found"
    assert b"non disponibile" in body


def test_invalid_or_unverified_record_is_rejected_at_app_creation():
    record = _record()
    record["source"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="violates document contract"):
        create_review_app({"doc": record})


def test_server_factory_binds_only_ipv4_loopback(monkeypatch):
    expected = object()
    called = {}

    def fake_make_server(host, port, app):
        called.update(host=host, port=port, app=app)
        return expected

    monkeypatch.setattr(review_ui, "make_server", fake_make_server)
    assert serve_local({}, port=8123) is expected
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8123
    assert callable(called["app"])
    with pytest.raises(ValueError, match="port"):
        serve_local({}, port=65536)
