"""Local-only, read-only WSGI review projection.

This module renders validated in-memory records and optionally the matching
source bytes. It does not ingest, persist, mutate, or authorize documents.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
from html import escape
from wsgiref.simple_server import make_server
from typing import Any, Callable
from urllib.parse import quote, unquote

from .contracts import validate_document_record
from .review_ledger import verify_review_ledger, reviewed_overlay

_MAX_SOURCE_BYTES = 25 * 1024 * 1024
_MEDIA_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tif",
    "image/webp": ".webp",
}


def _signature_matches(data: bytes, media_type: str) -> bool:
    if media_type == "application/pdf":
        return b"%PDF-" in data[:1024]
    if media_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if media_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/tiff":
        return data.startswith((b"II*\x00", b"MM\x00*"))
    if media_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _render_record(record: dict[str, Any], *, has_source: bool, key: str) -> str:
    overlay = reviewed_overlay(record)
    fields = overlay["reviewed_fields"]
    rows: list[str] = []
    for name, candidate in sorted(fields.items()):
        value = candidate.get("value")
        evidence = candidate.get("evidence", [])
        snippets = []
        for item in evidence:
            literal = item.get("literal", "")
            page = item.get("page_number", "?")
            digest = item.get("source_sha256", "")
            snippets.append(
                f'<li>Pagina {escape(str(page))}: <q>{escape(str(literal))}</q> '
                f'<small>SHA-256 {escape(str(digest))}</small></li>'
            )
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{escape(str(name))}</th>"
            f"<td>{escape(str(value)) if value is not None else '—'}</td>"
            f"<td>{escape(str(candidate.get('status', 'unknown')))}</td>"
            f"<td><ul>{''.join(snippets)}</ul></td>"
            "</tr>"
        )
    fiscal = overlay["reviewed_fiscal_document_state"]
    preview = (
        f'<p><a href="/reviews/{quote(key, safe="")}/source" target="_blank" '
        'rel="noopener noreferrer">Apri documento originale</a></p>'
        if has_source else
        "<p>Originale non disponibile nella sessione corrente.</p>"
    )
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Revisione documento</title><main>"
        f"<p><a href=\"/reviews/\">Coda</a></p>"
        f"<h1>Documento {escape(str(record.get('document_id', '')))}</h1>"
        f"<p>Stato revisione: <strong>{escape(str(overlay['review_status']))}</strong></p>"
        f"<p>Famiglia documento revisionata: {escape(str(overlay['reviewed_document_family']))}</p>"
        f"<p>Stato fiscale (decisione distinta): {escape(str(fiscal.get('status', 'unknown')))}</p>"
        "<p>Vista di sola lettura; nessuna decisione amministrativa.</p>"
        f"{preview}"
        "<table><thead><tr><th>Campo</th><th>Valore revisionato</th>"
        "<th>Stato estrazione</th><th>Evidenze testuali</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></main></html>"
    )


def _render_queue(records: Mapping[str, dict[str, Any]]) -> str:
    rows = []
    for key, record in sorted(records.items()):
        overlay = reviewed_overlay(record)
        rows.append(
            f'<li><a href="/reviews/{quote(key, safe="")}">Documento '
            f"{escape(str(record.get('document_id', key)))}</a> — "
            f"{escape(str(overlay['review_status']))} — "
            f"{escape(str(overlay['reviewed_document_family']))}</li>"
        )
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Coda di revisione</title><main><h1>Coda di revisione</h1>"
        "<p>Vista locale di sola lettura; nessuna decisione amministrativa.</p>"
        f"<ul>{''.join(rows)}</ul></main></html>"
    )


def create_review_app(
    records: Mapping[str, dict[str, Any]],
    source_bytes: Mapping[str, bytes] | None = None,
    *,
    max_source_bytes: int = _MAX_SOURCE_BYTES,
) -> Callable:
    """Create a GET-only app over validated records and optional verified bytes.

    Included source bytes must match record length, media type, and SHA-256.
    They remain in memory only. Unsupported, oversized, or mismatched sources
    fail closed. The server must be bound to loopback; use `serve_local`.
    """
    if not isinstance(max_source_bytes, int) or isinstance(max_source_bytes, bool) or max_source_bytes <= 0:
        raise ValueError("max_source_bytes must be a positive integer")
    snapshot = dict(records)
    for key, record in snapshot.items():
        if not isinstance(key, str) or not key or not isinstance(record, dict):
            raise ValueError("records must map non-empty string IDs to objects")
        issues = validate_document_record(record)
        if issues:
            raise ValueError(f"record {key!r} violates document contract: " + "; ".join(issues))
        verify_review_ledger(record)

    sources: dict[str, tuple[bytes, str]] = {}
    for key, value in (source_bytes or {}).items():
        if key not in snapshot:
            raise ValueError(f"source bytes supplied for unknown document {key!r}")
        if not isinstance(value, bytes):
            raise ValueError("source data must be immutable bytes")
        if len(value) > max_source_bytes:
            raise ValueError("source exceeds configured review preview limit")
        metadata = snapshot[key]["source"]
        media_type = str(metadata.get("media_type", "")).split(";", 1)[0].strip().lower()
        if media_type not in _MEDIA_TYPES:
            raise ValueError(f"unsupported source media type for {key!r}")
        if len(value) != metadata.get("byte_length"):
            raise ValueError(f"source length does not match document {key!r}")
        if hashlib.sha256(value).hexdigest() != metadata.get("sha256"):
            raise ValueError(f"source hash does not match document {key!r}")
        if not _signature_matches(value, media_type):
            raise ValueError(f"source signature does not match media type for {key!r}")
        sources[key] = (value, media_type)

    def app(environ: dict[str, Any], start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")
        headers: list[tuple[str, str]]
        if method != "GET":
            status, body = "405 Method Not Allowed", "Metodo non consentito"
            content_type = "text/plain; charset=utf-8"
            headers = []
        elif path in {"/", "/reviews", "/reviews/"}:
            status, body = "200 OK", _render_queue(snapshot)
            content_type = "text/html; charset=utf-8"
            headers = []
        elif path.startswith("/reviews/") and path.endswith("/source"):
            key = unquote(path[len("/reviews/"):-len("/source")].rstrip("/"))
            source = sources.get(key)
            if source is None or "/" in key:
                status, body = "404 Not Found", "Originale non disponibile"
                content_type = "text/plain; charset=utf-8"
                headers = []
            else:
                data, content_type = source
                suffix = _MEDIA_TYPES[content_type]
                start_response("200 OK", [
                    ("Content-Type", content_type),
                    ("Content-Length", str(len(data))),
                    ("Content-Disposition", f'inline; filename="document{suffix}"'),
                    ("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"),
                    ("Content-Security-Policy", "sandbox; default-src 'none'"),
                    ("Referrer-Policy", "no-referrer"),
                ])
                return [data]
        elif path.startswith("/reviews/"):
            key = unquote(path[len("/reviews/"):])
            record = snapshot.get(key)
            if record is None or "/" in key:
                status, body = "404 Not Found", "Documento non trovato"
            else:
                status, body = "200 OK", _render_record(record, has_source=key in sources, key=key)
            content_type = "text/html; charset=utf-8"
            headers = []
        else:
            status, body = "404 Not Found", "Risorsa non trovata"
            content_type = "text/plain; charset=utf-8"

        payload = body.encode("utf-8")
        start_response(status, [
            ("Content-Type", content_type),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'none'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'"),
            ("Referrer-Policy", "no-referrer"),
        ])
        return [payload]

    return app


def serve_local(
    records: Mapping[str, dict[str, Any]],
    source_bytes: Mapping[str, bytes] | None = None,
    *,
    port: int = 8000,
    max_source_bytes: int = _MAX_SOURCE_BYTES,
):
    """Build a local HTTP server bound exclusively to IPv4 loopback."""
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    app = create_review_app(records, source_bytes, max_source_bytes=max_source_bytes)
    return make_server("127.0.0.1", port, app)
