"""Local browser intake with volatile sessions and explicit optional archiving."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.parser import BytesParser
from html import escape
import csv
import hashlib
import io
import json
import re
import secrets
import threading
import time
from typing import Any, Callable
from urllib.parse import parse_qs, quote
from wsgiref.simple_server import make_server

from .chatgpt_handoff import ChatGPTHandoffError, build_chatgpt_handoff_prompt
from .contracts import validate_document_record
from .expense_reports import ExpenseReportIntakeSession, create_expense_report_intake_session
from .ingestion import IngestionLimits, MaterializedBatch, UploadRejected, materialize_stream_batch
from .review_ledger import append_review_event, reviewed_overlay
from .review_ui import create_review_app
from .document_export import export_document_csv, export_document_json
from .document_decoder import DecodeLimits, DocumentDecodeError, iter_decoded_pages
from .local_document_store import LocalDocumentStore, StoreConcurrentUpdate, StoreError
from .manual_region_review import build_human_region_evidence, encode_rgb8_png
from .ocr_processing import (
    OCRJobProtocolError,
    OCRProcessingManager,
    decode_frame,
)


_MAX_UPLOAD_REQUEST_BYTES = 100 * 1024 * 1024
_MAX_UPLOAD_FILES = 20
_MAX_URLENCODED_FIELDS = 16
_SESSION_IDLE_SECONDS = 30 * 60
_ACCEPT = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.zip"


@dataclass
class _VolatileSession:
    session_id: str
    batch: MaterializedBatch
    document_ids: tuple[str, ...]
    last_activity: float
    intake: ExpenseReportIntakeSession | None = None
    chatgpt_draft: str | None = None
    review_seconds: dict[str, int] = field(default_factory=dict)
    archive_ids: dict[str, str] = field(default_factory=dict)
    archive_baselines: dict[str, str] = field(default_factory=dict)
    archive_loaded_document_id: str | None = None
    archive_only: bool = False
    generation_id: str = field(default_factory=lambda: secrets.token_hex(24))
    ocr_job_id: str | None = None
    ocr_starting: bool = False
    ocr_publish_failed: bool = False
    ocr_result_published: bool = False


_ARCHIVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _record_fingerprint(record: dict[str, Any]) -> str:
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _loopback_host_parts(value: Any) -> tuple[str, int | None] | None:
    """Parse a strict loopback authority without accepting suffixes or invalid ports."""
    match = re.fullmatch(r"(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?", str(value).lower())
    if match is None:
        return None
    raw_port = match.group(2)
    if raw_port is None:
        return match.group(1), None
    port = int(raw_port)
    if not 1 <= port <= 65535:
        return None
    return match.group(1), port


def _same_origin_loopback_post(environ: dict[str, Any]) -> bool:
    """Require explicit matching loopback Host and Origin authorities for POSTs."""
    if environ.get("_opaque_origin_csrf_validated") is True:
        return _loopback_host_parts(environ.get("HTTP_HOST", "")) is not None
    host = _loopback_host_parts(environ.get("HTTP_HOST", ""))
    origin = str(environ.get("HTTP_ORIGIN", "")).lower()
    match = re.fullmatch(r"http://(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?", origin)
    if host is None or match is None:
        return False
    authority = match.group(1) + (f":{match.group(2)}" if match.group(2) is not None else "")
    return host == _loopback_host_parts(authority)


class _PrefixedInput:
    """Replay a bounded prefix already inspected by the opaque-origin gate."""

    def __init__(self, prefix: bytes, stream: Any) -> None:
        self._prefix = io.BytesIO(prefix)
        self._stream = stream

    def read(self, size: int = -1) -> bytes:
        head = self._prefix.read(size)
        if size < 0:
            return head + self._stream.read()
        if len(head) == size:
            return head
        return head + self._stream.read(size - len(head))


def _validate_loopback_post(environ: dict[str, Any], csrf_token: str) -> bool:
    """Allow exact same-origin loopback posts or bounded token-verified opaque-origin forms."""
    if _same_origin_loopback_post(environ):
        return True
    if str(environ.get("HTTP_ORIGIN", "")).lower() != "null":
        return False
    if _loopback_host_parts(environ.get("HTTP_HOST", "")) is None:
        return False
    header = Message()
    header["content-type"] = environ.get("CONTENT_TYPE", "")
    stream = environ.get("wsgi.input")
    if stream is None or not hasattr(stream, "read"):
        return False
    if header.get_content_type() == "application/x-www-form-urlencoded":
        try:
            length = int(environ.get("CONTENT_LENGTH", ""))
        except (TypeError, ValueError):
            return False
        if length <= 0 or length > 64 * 1024:
            return False
        body = stream.read(length)
        if not isinstance(body, bytes) or len(body) != length:
            return False
        try:
            values = parse_qs(body.decode("ascii"), strict_parsing=True,
                              keep_blank_values=True, max_num_fields=_MAX_URLENCODED_FIELDS)
        except (UnicodeDecodeError, ValueError):
            return False
        tokens = values.pop("_ocr2_csrf", [])
        if len(tokens) != 1 or not tokens[0].isascii() or not secrets.compare_digest(tokens[0], csrf_token):
            return False
        if sum(len(items) for items in values.values()) >= _MAX_URLENCODED_FIELDS:
            return False
        environ["_parsed_form_values"] = values
        environ["_opaque_origin_csrf_validated"] = True
        return True
    if header.get_content_type() != "multipart/form-data":
        return False
    try:
        length = int(environ.get("CONTENT_LENGTH", ""))
    except (TypeError, ValueError):
        return False
    boundary = header.get_param("boundary", header="content-type")
    if length <= 0 or length > _MAX_UPLOAD_REQUEST_BYTES or not isinstance(boundary, str) or not boundary or len(boundary) > 200:
        return False
    prefix = stream.read(min(length, 4096))
    if not isinstance(prefix, bytes) or len(prefix) != min(length, 4096):
        return False
    marker = b"--" + boundary.encode("ascii", errors="ignore") + b"\r\n"
    if not prefix.startswith(marker):
        return False
    header_end = prefix.find(b"\r\n\r\n", len(marker))
    if header_end < 0:
        return False
    part_headers = BytesParser(policy=policy.default).parsebytes(prefix[len(marker):header_end] + b"\r\n\r\n")
    if (part_headers.get_content_disposition() != "form-data"
            or part_headers.get_param("name", header="content-disposition") != "_ocr2_csrf"
            or part_headers.get_filename() is not None):
        return False
    value_start = header_end + 4
    value_end = prefix.find(b"\r\n", value_start)
    if value_end < 0 or value_end - value_start > 256:
        return False
    try:
        submitted_token = prefix[value_start:value_end].decode("ascii")
    except UnicodeDecodeError:
        return False
    if not secrets.compare_digest(submitted_token, csrf_token):
        return False
    environ["wsgi.input"] = _PrefixedInput(prefix, stream)
    environ["_opaque_origin_csrf_validated"] = True
    return True


class IntakeRequestError(ValueError):
    """A browser request did not meet the local intake contract."""


def _multipart_files(environ: dict[str, Any]) -> list[tuple[str, bytes]]:
    content_length = environ.get("CONTENT_LENGTH", "")
    try:
        length = int(content_length)
    except (TypeError, ValueError) as exc:
        raise IntakeRequestError("Content-Length non valido") from exc
    if length <= 0 or length > _MAX_UPLOAD_REQUEST_BYTES:
        raise IntakeRequestError("Dimensione totale della richiesta non valida o superiore al limite")
    content_type = environ.get("CONTENT_TYPE", "")
    header = Message()
    header["content-type"] = content_type
    if header.get_content_type() != "multipart/form-data":
        raise IntakeRequestError("È richiesta una richiesta multipart/form-data")
    boundary = header.get_param("boundary", header="content-type")
    if not isinstance(boundary, str) or not boundary or len(boundary) > 200:
        raise IntakeRequestError("Boundary multipart non valido")
    stream = environ.get("wsgi.input")
    if stream is None or not hasattr(stream, "read"):
        raise IntakeRequestError("Corpo della richiesta assente")
    body = stream.read(length)
    if not isinstance(body, bytes) or len(body) != length:
        raise IntakeRequestError("Corpo della richiesta incompleto")
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            b"MIME-Version: 1.0\r\nContent-Type: "
            + content_type.encode("ascii")
            + b"\r\n\r\n"
            + body
        )
    except (UnicodeEncodeError, ValueError) as exc:
        raise IntakeRequestError("Intestazione multipart non valida") from exc
    if not message.is_multipart():
        raise IntakeRequestError("Corpo multipart non valido")
    files: list[tuple[str, bytes]] = []
    csrf_count = 0
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            raise IntakeRequestError("Sono accettati soltanto campi file denominati 'files'")
        field_name = part.get_param("name", header="content-disposition")
        if field_name == "_ocr2_csrf" and part.get_filename() is None:
            csrf_count += 1
            continue
        if field_name != "files":
            raise IntakeRequestError("Sono accettati soltanto campi file denominati 'files'")
        filename = part.get_filename()
        if not isinstance(filename, str) or not filename:
            raise IntakeRequestError("Ogni file deve avere un nome")
        transfer_encoding = str(part.get("Content-Transfer-Encoding", "binary")).lower()
        if transfer_encoding not in {"binary", "8bit", "7bit"}:
            raise IntakeRequestError("Codifica di trasferimento del file non supportata")
        data = part.get_payload(decode=True)
        if not isinstance(data, bytes) or not data:
            raise IntakeRequestError("I file vuoti non sono accettati")
        files.append((filename, data))
        if len(files) > _MAX_UPLOAD_FILES:
            raise IntakeRequestError("Numero massimo di file superato")
    if not files:
        raise IntakeRequestError("Seleziona almeno un PDF, un'immagine o uno ZIP")
    if csrf_count > 1 or (environ.get("_opaque_origin_csrf_validated") is True and csrf_count != 1):
        raise IntakeRequestError("Richiesta locale non valida")
    return files


def _page(
    environ: dict[str, Any], start_response: Callable, status: str, body: str,
    content_type: str = "text/html; charset=utf-8", *, download_filename: str | None = None,
) -> list[bytes]:
    nonce = secrets.token_urlsafe(18)
    token = str(environ.get("_ocr2_csrf_token", ""))
    csrf_field = f'<input type="hidden" name="_ocr2_csrf" value="{escape(token, quote=True)}">'
    body = re.sub(
        r'(<form\b(?=[^>]*\bmethod\s*=\s*["\']?post\b)[^>]*>)',
        lambda match: match.group(1) + csrf_field,
        body,
        flags=re.IGNORECASE,
    )
    payload = body.replace('nonce="__CSP_NONCE__"', f'nonce="{nonce}"').encode("utf-8")
    has_region_editor = 'data-region-image' in body
    inline_style_nonce = '<style nonce="__CSP_NONCE__">' in body
    style_policy = f"style-src 'self' 'nonce-{nonce}'; " if inline_style_nonce else "style-src 'self'; "
    image_policy = "img-src 'self'; " if has_region_editor else ""
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(payload))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", f"default-src 'none'; {style_policy}{image_policy}script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'"),
        ("Referrer-Policy", "no-referrer"),
    ]
    if download_filename is not None:
        headers.append(("Content-Disposition", f'attachment; filename="{download_filename}"'))
    start_response(status, headers)
    return [payload]


def _source_page_png(record: dict[str, Any], source_bytes: bytes, page_number: int) -> bytes:
    """Render one verified source page to a bounded, in-memory PNG response."""
    source = record.get("source")
    if (
        not isinstance(source, dict) or not isinstance(source_bytes, bytes)
        or not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1
    ):
        raise DocumentDecodeError("source page is unavailable")
    limits = DecodeLimits()
    expected_length = source.get("byte_length")
    digest = source.get("sha256")
    if (
        not isinstance(expected_length, int) or isinstance(expected_length, bool)
        or expected_length != len(source_bytes) or len(source_bytes) > limits.max_source_bytes
        or not isinstance(digest, str) or hashlib.sha256(source_bytes).hexdigest() != digest
    ):
        raise DocumentDecodeError("source page integrity check failed")
    pages = record.get("pages")
    page_numbers = {
        item.get("page_number") for item in pages if isinstance(item, dict)
        and isinstance(item.get("page_number"), int) and not isinstance(item.get("page_number"), bool)
    } if isinstance(pages, list) else set()
    if page_number not in page_numbers:
        raise DocumentDecodeError("source page is not in the record")
    media_kind = {
        "application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpeg",
        "image/tiff": "tiff", "image/webp": "webp",
    }.get(source.get("media_type"))
    if media_kind is None:
        raise DocumentDecodeError("source media type is not supported")
    decoded_pages = iter_decoded_pages(source_bytes, media_kind, source_sha256=digest, limits=limits)
    try:
        for decoded in decoded_pages:
            if decoded.raster.page_number == page_number:
                return encode_rgb8_png(
                    decoded.raster.width_px, decoded.raster.height_px, decoded.raster.image_bytes
                )
    finally:
        close = getattr(decoded_pages, "close", None)
        if callable(close):
            close()
    raise DocumentDecodeError("source page is not available")


def _upload_page(*, archive_enabled: bool = False) -> str:
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Nuova nota spese</title><main><h1>Carica nota spese e giustificativi</h1>"
        "<p>Seleziona insieme la nota e i relativi documenti. Puoi includere file ZIP. "
        "I file sono elaborati in memoria nella sessione locale.</p>"
        f'<form method="post" action="/upload" enctype="multipart/form-data">'
        f'<label>Documenti <input type="file" name="files" accept="{_ACCEPT}" multiple required></label>'
        '<button type="submit">Carica e continua</button></form>'
        "<p>Dimensione massima della richiesta: 100 MiB; massimo 20 file.</p>"
        + ('<p><a href="/archive">Apri archivio locale</a></p>' if archive_enabled else "")
        + "</main></html>"
    )


def _choose_note_page(state: _VolatileSession) -> str:
    choices = []
    for document_id, materialized in zip(state.document_ids, (
        item for upload in state.batch.uploads for item in upload.documents
    ), strict=True):
        name = escape(materialized.inventory.name)
        choices.append(
            f'<label><input type="radio" name="note_document_id" value="{escape(document_id)}" required> '
            f'{name} — {materialized.inventory.media_kind}, {materialized.inventory.byte_length} byte</label>'
        )
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Seleziona la nota spese</title><main><h1>Quale file è la nota spese?</h1>"
        "<p>Gli altri documenti resteranno collegati come giustificativi indipendenti.</p>"
        '<form method="post" action="/assign-note">'
        f'{"".join(choices)}<button type="submit">Conferma nota spese</button></form>'
        '<form method="post" action="/clear"><button type="submit">Annulla e cancella la sessione</button></form>'
        "</main></html>"
    )


def _bundle_page(state: _VolatileSession, *, archive_enabled: bool = False) -> str:
    assert state.intake is not None
    note_id = state.intake.bundle["note_document_id"]
    rows = []
    visible_ids = [note_id] + [
        item.get("document_id") for item in state.intake.bundle.get("attachments", [])
        if isinstance(item, dict) and isinstance(item.get("document_id"), str)
    ]
    for document_id in visible_ids:
        record = state.intake.documents.get(document_id)
        if record is None:
            continue
        role = "Nota spese" if document_id == note_id else "Giustificativo"
        href = f"/reviews/{quote(document_id, safe='')}"
        filename = escape(record["source"]["original_filename"])
        ocr_status = escape(record["processing"]["ocr"]["status"])
        case_id = f"{state.session_id}-{document_id}"
        rows.append(
            f'<li><strong>{role}</strong> — <a href="{href}">{filename}</a> '
            f'({record["source"]["media_type"]}; OCR: {ocr_status}; SHA-256 {record["source"]["sha256"]}) '
            f'<small>Riferimento benchmark: {case_id}</small>'
            + (f'<form method="post" action="/archive/save/{quote(document_id, safe="")}">'
               '<button type="submit">Salva in archivio</button></form>' if archive_enabled else "")
            + '</li>'
        )
    archive_link = '<p><a href="/archive">Apri archivio locale</a></p>' if archive_enabled else ""
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Nota spese e giustificativi</title><main><h1>Documenti collegati</h1>"
        "<p>Ogni file mantiene la propria evidenza originale. La classificazione resta da verificare.</p>"
        f"<ul>{''.join(rows)}</ul>"
        + archive_link
        + '<p><a href="/review-times.csv">Scarica i tempi di revisione (CSV)</a></p>'
        '<p><a href="/chatgpt">Prepara testo da copiare in ChatGPT</a></p>'
        '<form method="post" action="/clear"><button type="submit">Chiudi e cancella la sessione</button></form>'
        "</main></html>"
    )


def _ocr_job_page(
    job_id: str, status: Any, *, archive_enabled: bool = False,
    publish_failed: bool = False,
) -> str:
    labels = {
        "queued": "In coda",
        "starting_engine": "Avvio del motore",
        "processing": "Elaborazione in corso",
        "cancelling": "Annullamento in corso",
        "succeeded": "Elaborazione completata",
        "failed": "Elaborazione non riuscita",
        "cancelled": "Elaborazione annullata",
    }
    phase = labels.get(getattr(status, "phase", ""), "Stato non disponibile")
    if publish_failed:
        phase = "Risultato rifiutato: cancella la sessione e ricarica i documenti"
    completed = getattr(status, "completed_documents", 0)
    total = getattr(status, "total_documents", 0)
    page = getattr(status, "current_page", 0)
    pages = getattr(status, "total_pages", 0)
    if phase == "Elaborazione completata":
        actions = '<p><a href="/">Apri i documenti elaborati</a></p>'
    elif publish_failed or phase in {"Elaborazione non riuscita", "Elaborazione annullata"}:
        actions = '<form method="post" action="/clear"><button type="submit">Chiudi e cancella la sessione</button></form>'
    else:
        actions = (
            f'<form method="post" action="/ocr/jobs/{quote(job_id, safe="")}/cancel">'
            '<button type="submit">Annulla elaborazione</button></form>'
        )
    archive_link = '<p><a href="/archive">Apri archivio locale</a></p>' if archive_enabled else ""
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + ('<meta http-equiv="refresh" content="2">' if phase in {
            "In coda", "Avvio del motore", "Elaborazione in corso", "Annullamento in corso",
        } else "")
        + '<title>Elaborazione OCR</title><main><h1>Elaborazione OCR</h1>'
        f'<p>Stato: {escape(phase)}.</p>'
        f'<p>Documenti: {completed} / {total} · Pagine: {page} / {pages}</p>'
        f'<p><a href="/ocr/jobs/{quote(job_id, safe="")}">Aggiorna stato</a></p>'
        f'{actions}{archive_link}</main></html>'
    )


def _archive_list_page(store: LocalDocumentStore, query: str = "") -> str:
    summaries = store.search(query, limit=100)
    rows = []
    for item in summaries:
        identifier = quote(item.document_id, safe="")
        rows.append(
            f'<li><strong>{escape(item.filename)}</strong> — {escape(item.document_family)}; '
            f'{item.page_count} pagine; salvato {escape(item.saved_at)}; SHA-256 {escape(item.source_sha256)} '
            f'<form method="post" action="/archive/open/{identifier}"><button type="submit">Apri</button></form> '
            f'<a href="/archive/export/{identifier}.json">JSON</a> '
            f'<a href="/archive/export/{identifier}.csv">CSV</a> '
            f'<a href="/archive/delete/{identifier}">Elimina</a></li>'
        )
    empty = "<p>Nessun documento trovato.</p>" if not rows else ""
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Archivio locale</title><main><h1>Archivio documenti locale</h1>'
        '<p>Ricerca limitata ai primi 100 risultati. I dati restano su questo dispositivo.</p>'
        '<form method="get" action="/archive"><label>Cerca <input name="q" maxlength="200" value="'
        + escape(query, quote=True) + '"></label><button type="submit">Cerca</button></form>'
        + empty + f'<ul>{"".join(rows)}</ul>'
        + '<form method="post" action="/archive/return"><button type="submit">Torna alla sessione corrente</button></form>'
        + '</main></html>'
    )


def _archive_document_page(document_id: str, record: dict[str, Any]) -> str:
    safe_id = quote(document_id, safe="")
    filename = escape(str(record["source"].get("original_filename", "documento")))
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Documento archiviato</title><main><h1>Documento in archivio</h1>'
        f'<p>{filename} — SHA-256 {escape(record["source"]["sha256"])}</p>'
        f'<form method="post" action="/reviews/{safe_id}/open"><button type="submit">Apri revisione</button></form>'
        f'<a href="/reviews/{safe_id}/source">Apri documento originale</a> · '
        f'<a href="/archive/export/{safe_id}.json">Esporta JSON</a> · '
        f'<a href="/archive/export/{safe_id}.csv">Esporta CSV</a> · '
        '<p>JSON contiene il record completo, CSV è una proiezione tabellare; entrambi escludono i byte del documento originale.</p>'
        f'<a href="/archive/delete/{safe_id}">Elimina documento</a> · <a href="/archive">Archivio</a>'
        + '<form method="post" action="/archive/return"><button type="submit">Torna alla sessione corrente</button></form>'
        + '</main></html>'
    )


def _render_document_family_review(
    record: dict[str, Any], overlay: dict[str, Any], *, document_id: str, elapsed_seconds: int
) -> str:
    if record.get("document_family") == "expense_report":
        return ""
    candidate = overlay["reviewed_fields"].get("document_family_candidates")
    alternatives = candidate.get("alternatives", []) if isinstance(candidate, dict) else []
    if not isinstance(alternatives, list) or not alternatives:
        return ""
    choices = []
    selected = overlay.get("reviewed_document_family", "unknown")
    selected_available = any(
        isinstance(item, dict) and item.get("value") == selected
        for item in alternatives
    )
    if not selected_available:
        choices.append('<option value="" selected disabled>Seleziona famiglia</option>')
    for alternative in alternatives:
        if not isinstance(alternative, dict) or alternative.get("status") != "observed":
            continue
        family = alternative.get("value")
        if not isinstance(family, str):
            continue
        label = family.replace("_", " ")
        selected_attr = " selected" if family == selected else ""
        choices.append(
            f'<option value="{escape(family)}"{selected_attr}>{escape(label)}</option>'
        )
    if not choices:
        return ""
    return (
        "<section><h2>Famiglia del documento</h2>"
        f'<p>Famiglia attualmente revisionata: {escape(str(selected))}. '
        "La famiglia non determina da sola lo stato fiscale.</p>"
        f'<form method="post" data-review-timer action="/reviews/{quote(document_id, safe="")}/document-family">'
        f'<label>Seleziona solo una proposta supportata da evidenza <select name="document_family" required>{"".join(choices)}</select></label>'
        f'<input type="hidden" name="review_seconds" data-review-seconds value="{elapsed_seconds}">'
        '<button type="submit">Registra famiglia revisionata</button></form></section>'
    )

def _reviewable_evidence(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[Any, ...]] = set()
    fields = record.get("fields", {})
    if not isinstance(fields, dict):
        return result
    for field_name, candidate in sorted(fields.items(), key=lambda pair: str(pair[0])):
        if not isinstance(candidate, dict):
            continue
        references = list(candidate.get("evidence", [])) if isinstance(candidate.get("evidence"), list) else []
        alternatives = candidate.get("alternatives", [])
        if isinstance(alternatives, list):
            for alternative in alternatives:
                if isinstance(alternative, dict) and isinstance(alternative.get("evidence"), list):
                    references.extend(alternative["evidence"])
        for item in references:
            if not isinstance(item, dict):
                continue
            token_ids = item.get("token_ids", [])
            key = (item.get("source_sha256"), item.get("page_number"), item.get("literal"), repr(token_ids), repr(item.get("region")), repr(item.get("text_span")))
            if key not in seen:
                seen.add(key)
                result.append((field_name, item))
    fiscal = record.get("fiscal_document_state", {})
    if isinstance(fiscal, dict) and isinstance(fiscal.get("evidence"), list):
        for item in fiscal["evidence"]:
            if isinstance(item, dict):
                key = (item.get("source_sha256"), item.get("page_number"), item.get("literal"), repr(item.get("token_ids", [])), repr(item.get("region")), repr(item.get("text_span")))
                if key not in seen:
                    seen.add(key)
                    result.append(("fiscal_document_state", item))
    return result


def _render_fiscal_state_review(
    record: dict[str, Any], overlay: dict[str, Any], *, document_id: str, elapsed_seconds: int
) -> str:
    if record.get("document_family") == "expense_report":
        return ""
    references = _reviewable_evidence(record)
    if not references:
        return ""
    current = overlay["reviewed_fiscal_document_state"]
    current_status = current.get("status", "unknown")
    labels = {
        "fiscal_document": "Documento fiscale",
        "payment_evidence": "Prova di pagamento",
        "not_fiscal": "Non fiscale",
        "uncertain": "Incerto",
    }
    if overlay.get("reviewed_document_family") == "pos_slip":
        labels.pop("fiscal_document")
    options = []
    if current_status not in labels:
        options.append('<option value="" selected disabled>Seleziona stato fiscale</option>')
    for value, label in labels.items():
        selected = " selected" if current_status == value else ""
        options.append(f'<option value="{value}"{selected}>{label}</option>')
    current_evidence = current.get("evidence", [])
    selected_ref = current_evidence[0] if isinstance(current_evidence, list) and current_evidence else None
    evidence_options = []
    selected_index = None
    for index, (field_name, item) in enumerate(references):
        label = f"{field_name} — pagina {item.get('page_number', '?')}: {item.get('literal', '')}"
        selected = " selected" if selected_ref == item else ""
        if selected:
            selected_index = index
        evidence_options.append(f'<option value="{index}"{selected}>{escape(label)}</option>')
    if selected_index is None:
        evidence_options.insert(0, '<option value="" selected disabled>Seleziona evidenza</option>')
    return (
        "<section><h2>Stato fiscale</h2>"
        f'<p>Stato attuale: {escape(str(current_status))}. Rivedilo separatamente dalla famiglia del documento e confronta la fonte originale.</p>'
        f'<form method="post" data-review-timer action="/reviews/{quote(document_id, safe="")}/fiscal-state">'
        f'<label>Classificazione <select name="fiscal_status" required>{"".join(options)}</select></label>'
        f'<label>Evidenza originale <select name="evidence_index" required>{"".join(evidence_options)}</select></label>'
        f'<input type="hidden" name="review_seconds" data-review-seconds value="{elapsed_seconds}">'
        '<button type="submit">Registra classificazione fiscale revisionata</button></form></section>'
    )
def _render_region_correction_form(
    *, document_id: str, field_name: str, page_numbers: list[int], elapsed_seconds: int,
) -> str:
    safe_id = quote(document_id, safe="")
    safe_field = quote(field_name, safe="")
    options = "".join(f'<option value="{number}">{number}</option>' for number in page_numbers)
    return (
        f'<form method="post" data-review-timer data-region-review action="/reviews/{safe_id}/fields/{safe_field}">'
        "<h3>Correzione manuale con riferimento alla pagina</h3>"
        "<p>Leggi il documento originale, delimita la regione del valore e digita la trascrizione. "
        "Il valore sarà registrato come revisione umana, non come testo OCR.</p>"
        f'<label>Pagina sorgente <select name="region_page" data-region-page>{options}</select></label>'
        f'<div class="region-viewer"><img data-region-image alt="Pagina del documento; trascina per delimitare il valore da correggere" '
        f'data-preview-base="/reviews/{safe_id}/pages" src="/reviews/{safe_id}/pages/{page_numbers[0]}.png" loading="lazy">'
        '<svg data-region-overlay viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">'
        '<rect data-region-selection x="0" y="0" width="0" height="0"></rect></svg></div>'
        '<p data-region-status aria-live="polite">Trascina sulla pagina oppure inserisci le coordinate normalizzate.</p>'
        '<fieldset><legend>Coordinate normalizzate da 0 a 1</legend>'
        '<label>X iniziale <input type="number" name="region_x0" min="0" max="1" step="any" required></label>'
        '<label>Y iniziale <input type="number" name="region_y0" min="0" max="1" step="any" required></label>'
        '<label>X finale <input type="number" name="region_x1" min="0" max="1" step="any" required></label>'
        '<label>Y finale <input type="number" name="region_y1" min="0" max="1" step="any" required></label></fieldset>'
        '<label>Valore letto e verificato sulla pagina <input name="value" maxlength="512" required></label>'
        f'<input type="hidden" name="review_seconds" data-review-seconds value="{elapsed_seconds}">'
        '<button type="submit">Registra correzione umana</button></form>'
    )


_REGION_REVIEW_STYLE = (
    '<style nonce="__CSP_NONCE__">'
    '.region-viewer{position:relative;display:inline-block;width:min(100%,800px)}'
    '.region-viewer img{display:block;width:100%;height:auto}'
    '.region-viewer svg{position:absolute;inset:0;width:100%;height:100%;touch-action:none}'
    '.region-viewer rect{fill:rgba(20,110,180,.22);stroke:#146eb4;stroke-width:.004}'
    '</style>'
)

_REGION_REVIEW_SCRIPT = (
    '(()=>{document.querySelectorAll("[data-region-review]").forEach(form=>{'
    'const svg=form.querySelector("[data-region-overlay]"),img=form.querySelector("[data-region-image]"),'
    'rect=form.querySelector("[data-region-selection]"),page=form.querySelector("[data-region-page]"),'
    'status=form.querySelector("[data-region-status]"),fields=["x0","y0","x1","y1"].map(k=>form.querySelector(`[name=region_${k}]`));let start=null;'
    'const clear=()=>{rect.setAttribute("width","0");rect.setAttribute("height","0");start=null};'
    'page.addEventListener("change",()=>{img.src=`${img.dataset.previewBase}/${page.value}.png`;clear()});'
    'const point=e=>{const r=svg.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]};'
    'svg.addEventListener("pointerdown",e=>{if(e.button!==0)return;start=point(e);svg.setPointerCapture(e.pointerId);rect.setAttribute("x",start[0]);rect.setAttribute("y",start[1]);rect.setAttribute("width","0");rect.setAttribute("height","0")});'
    'svg.addEventListener("pointermove",e=>{if(!start)return;const p=point(e),x0=Math.min(start[0],p[0]),y0=Math.min(start[1],p[1]),x1=Math.max(start[0],p[0]),y1=Math.max(start[1],p[1]);rect.setAttribute("x",x0);rect.setAttribute("y",y0);rect.setAttribute("width",x1-x0);rect.setAttribute("height",y1-y0)});'
    'svg.addEventListener("pointerup",e=>{if(!start)return;const p=point(e),x0=Math.min(start[0],p[0]),y0=Math.min(start[1],p[1]),x1=Math.max(start[0],p[0]),y1=Math.max(start[1],p[1]);if(x1>x0&&y1>y0){[x0,y0,x1,y1].forEach((v,i)=>fields[i].value=v.toFixed(6));status.textContent=`Regione selezionata nella pagina ${page.value}. Verifica il testo e registra la correzione.`}else{clear();status.textContent="Selezione troppo piccola: trascina una regione più ampia."}start=null});'
    '});})();'
)


def _render_editable_record(
    record: dict[str, Any], *, document_id: str, has_source: bool, elapsed_seconds: int = 0,
    archive_save_enabled: bool = False,
) -> str:
    overlay = reviewed_overlay(record)
    fields = overlay["reviewed_fields"]
    page_numbers = sorted({
        item.get("page_number") for item in record.get("pages", [])
        if isinstance(item, dict) and isinstance(item.get("page_number"), int)
        and not isinstance(item.get("page_number"), bool) and item.get("page_number") > 0
    })
    rows = []
    for name, candidate in sorted(fields.items()):
        value = candidate.get("value")
        evidence = candidate.get("evidence", [])
        snippets = []
        for item in evidence:
            literal = item.get("literal", "")
            page = item.get("page_number", "?")
            detail = f"<q>{escape(str(literal))}</q>" if literal else (
                "regione selezionata e verificata da una persona"
                if isinstance(item.get("region"), dict) else "riferimento sorgente senza testo OCR"
            )
            snippets.append(f"<li>Pagina {escape(str(page))}: {detail}</li>")
        correction = ""
        if evidence and name != "document_family_candidates":
            correction = (
                f'<form method="post" data-review-timer action="/reviews/{quote(document_id, safe="")}/fields/{quote(name, safe="")}">'
                f'<label>Valore corretto <input name="value" value="{escape(str(value)) if value is not None else ""}" maxlength="512" required></label>'
                f'<input type="hidden" name="review_seconds" data-review-seconds value="{elapsed_seconds}">'
                '<button type="submit">Registra correzione</button></form>'
            )
        elif candidate.get("status") == "absent" and name not in {
            "document_family_candidates", "fiscal_document_state",
        }:
            correction = "<p>Non sono disponibili evidenze OCR per questo valore. Verifica la pagina originale e trascrivi la regione come revisione umana.</p>"
            if has_source and page_numbers:
                correction += _render_region_correction_form(
                    document_id=document_id, field_name=name, page_numbers=page_numbers,
                    elapsed_seconds=elapsed_seconds,
                )
            else:
                correction += "<p>La selezione di una nuova regione non è disponibile: la pagina originale non è presente nella sessione corrente.</p>"
        rows.append(
            f"<section><h2>{escape(name)}</h2>"
            f"<p>Valore verificato: {escape(str(value)) if value is not None else '—'} "
            f"({escape(str(candidate.get('status', 'unknown')))}).</p>"
            f"<ul>{''.join(snippets)}</ul>{correction}</section>"
        )
    family_review = _render_document_family_review(
        record, overlay, document_id=document_id, elapsed_seconds=elapsed_seconds
    )
    fiscal_review = _render_fiscal_state_review(
        record, overlay, document_id=document_id, elapsed_seconds=elapsed_seconds
    )
    source_link = (
        f'<p><a href="/reviews/{quote(document_id, safe="")}/source" target="_blank" rel="noopener noreferrer">Apri documento originale</a></p>'
        if has_source else "<p>Originale non disponibile nella sessione corrente.</p>"
    )
    empty = "<p>Non sono ancora disponibili campi estratti da correggere.</p>" if not rows else ""
    completion = (
        f'<form method="post" data-review-timer action="/reviews/{quote(document_id, safe="")}/complete">'
        f'<input type="hidden" name="review_seconds" data-review-seconds value="{elapsed_seconds}">'
        '<button type="submit">Concludi revisione</button></form>'
        if overlay["review_status"] == "in_progress" else ""
    )
    archive_save = (
        f'<form method="post" action="/archive/save/{quote(document_id, safe="")}">'
        '<button type="submit">Salva modifiche in archivio</button></form>'
        if archive_save_enabled else ""
    )
    has_region_editor = has_source and bool(page_numbers) and any(
        candidate.get("status") == "absent" and name not in {"document_family_candidates", "fiscal_document_state"}
        for name, candidate in fields.items()
    )
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Revisione documento</title><main><p><a href=\"/\">Torna al fascicolo</a></p>"
        f"<h1>Revisione {escape(document_id)}</h1>"
        f"<p>Stato revisione: {escape(str(overlay['review_status']))}. Le correzioni si aggiungono al registro; i dati OCR non vengono sovrascritti.</p>"
        f"{source_link}{family_review}{fiscal_review}{empty}{''.join(rows)}{completion}{archive_save}"
        + (_REGION_REVIEW_STYLE if has_region_editor else "")
        + '<script nonce="__CSP_NONCE__">'
        + (_REGION_REVIEW_SCRIPT if has_region_editor else "")
        + '(()=>{let active=0,last=performance.now(),wasVisible=!document.hidden;const tick=()=>{const now=performance.now();if(wasVisible)active+=now-last;last=now;wasVisible=!document.hidden};'
        'document.addEventListener("visibilitychange",tick);setInterval(tick,1000);'
        'document.querySelectorAll("[data-review-timer]").forEach(form=>form.addEventListener("submit",()=>{tick();'
        'const input=form.querySelector("[data-review-seconds]");if(input)input.value=String(Math.floor(Number(input.value||0)+active/1000))}));})();'
        '</script></main></html>'
    )


def _begin_document_review(record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
    """Start a review once a reviewer opens the editable document page."""
    updated = record
    status = updated["review"]["status"]
    if status == "not_started":
        updated = append_review_event(updated, actor_id="local-session", action="queued", timestamp=timestamp)
        status = "queued"
    if status in {"queued", "blocked"}:
        updated = append_review_event(updated, actor_id="local-session", action="opened", timestamp=timestamp)
    return updated


def _read_review_seconds(environ: dict[str, Any], *, required: bool = True) -> int:
    raw = _multipart_scalar(environ, "review_seconds", required=required)
    if not raw and not required:
        return 0
    if not raw.isascii() or not raw.isdecimal():
        raise IntakeRequestError("Durata di revisione non valida")
    seconds = int(raw)
    if seconds > 86_400:
        raise IntakeRequestError("Durata di revisione oltre il limite di 24 ore")
    return seconds


def _apply_field_correction(
    record: dict[str, Any],
    *,
    field_name: str,
    value: str,
    timestamp: str,
    region_page_number: int | None = None,
    region_coordinates: tuple[str, str, str, str] | None = None,
) -> dict[str, Any]:
    """Append a source-bound correction while preserving the extracted record."""
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise IntakeRequestError("Il valore corretto deve contenere da 1 a 512 caratteri")
    original = record.get("fields", {}).get(field_name)
    if not isinstance(original, dict):
        raise IntakeRequestError("Il campo non dispone di evidenze sorgente da revisionare")
    original_evidence = original.get("evidence")
    if isinstance(original_evidence, list) and original_evidence:
        if region_page_number is not None or region_coordinates is not None:
            raise IntakeRequestError("Il campo dispone già di evidenze sorgente specifiche")
        correction_evidence = deepcopy(original_evidence)
    else:
        if original.get("status") != "absent" or field_name in {
            "document_family_candidates", "fiscal_document_state",
        }:
            raise IntakeRequestError("Il campo non dispone di evidenze sorgente da revisionare")
        if not isinstance(region_page_number, int) or isinstance(region_page_number, bool):
            raise IntakeRequestError("Riferimento manuale alla pagina non valido")
        if not isinstance(region_coordinates, tuple) or len(region_coordinates) != 4:
            raise IntakeRequestError("Seleziona una regione della pagina originale")
        page_numbers = {
            item.get("page_number") for item in record.get("pages", [])
            if isinstance(item, dict) and isinstance(item.get("page_number"), int)
            and not isinstance(item.get("page_number"), bool)
        }
        if region_page_number not in page_numbers:
            raise IntakeRequestError("La pagina selezionata non appartiene al documento")
        try:
            correction_evidence = [build_human_region_evidence(
                record.get("source", {}).get("sha256"), region_page_number, *region_coordinates
            )]
        except ValueError as exc:
            raise IntakeRequestError("Regione della pagina non valida") from exc
    candidate = {
        "value": value.strip(),
        "status": "observed",
        "alternatives": [],
        "evidence": correction_evidence,
    }
    if isinstance(original.get("confidence"), (int, float)) and not isinstance(original.get("confidence"), bool):
        candidate["confidence"] = original["confidence"]
    if isinstance(original.get("normalization"), dict):
        candidate["normalization"] = {
            **original["normalization"],
            "normalized_value": value.strip(),
        }

    updated = record
    status = updated["review"]["status"]
    if status == "not_started":
        updated = append_review_event(
            updated, actor_id="local-session", action="queued", timestamp=timestamp
        )
        status = "queued"
    if status in {"queued", "blocked"}:
        updated = append_review_event(
            updated, actor_id="local-session", action="opened", timestamp=timestamp
        )
    return append_review_event(
        updated,
        actor_id="local-session",
        action="field_corrected",
        timestamp=timestamp,
        field_name=field_name,
        reason_code="human_corrected",
        candidate=candidate,
    )


def _apply_document_family_selection(
    record: dict[str, Any], *, family: str, timestamp: str
) -> dict[str, Any]:
    if record.get("document_family") == "expense_report":
        raise IntakeRequestError("La famiglia della nota spese non può essere cambiata da questa revisione")
    if not isinstance(family, str) or family not in {
        "invoice", "fiscal_receipt", "parking_receipt", "hotel_document",
        "pos_slip", "other", "unknown",
    }:
        raise IntakeRequestError("Famiglia documento non supportata")
    proposal = record.get("fields", {}).get("document_family_candidates")
    alternatives = proposal.get("alternatives") if isinstance(proposal, dict) else None
    selected = next((
        item for item in alternatives or []
        if isinstance(item, dict) and item.get("value") == family
        and item.get("status") == "observed" and isinstance(item.get("evidence"), list)
    ), None)
    if selected is None:
        raise IntakeRequestError("La famiglia selezionata non ha un'evidenza OCR corrispondente")
    candidate = {
        "value": family, "status": "observed", "alternatives": [],
        "evidence": deepcopy(selected["evidence"]),
    }
    updated = record
    status = updated["review"]["status"]
    if status == "not_started":
        updated = append_review_event(updated, actor_id="local-session", action="queued", timestamp=timestamp)
        status = "queued"
    if status in {"queued", "blocked"}:
        updated = append_review_event(updated, actor_id="local-session", action="opened", timestamp=timestamp)
    return append_review_event(
        updated, actor_id="local-session", action="field_corrected",
        timestamp=timestamp, field_name="document_family",
        reason_code="human_selected_evidence_bound_family", candidate=candidate,
    )

def _apply_fiscal_state_correction(
    record: dict[str, Any], *, status: str, evidence_index: str, timestamp: str
) -> dict[str, Any]:
    allowed_statuses = {"fiscal_document", "payment_evidence", "not_fiscal", "uncertain"}
    if not isinstance(status, str) or status not in allowed_statuses:
        raise IntakeRequestError("Stato fiscale non supportato")
    if not isinstance(evidence_index, str) or not evidence_index.isascii() or not evidence_index.isdecimal():
        raise IntakeRequestError("Evidenza non valida")
    references = _reviewable_evidence(record)
    index = int(evidence_index)
    if index >= len(references):
        raise IntakeRequestError("Evidenza non disponibile nella sessione")
    overlay = reviewed_overlay(record)
    if status == "fiscal_document" and overlay.get("reviewed_document_family") == "pos_slip":
        raise IntakeRequestError("Una ricevuta POS non può essere classificata come documento fiscale")
    fiscal_state = {"status": status, "evidence": [deepcopy(references[index][1])] }
    return append_review_event(
        record, actor_id="local-session", action="fiscal_state_corrected",
        timestamp=timestamp, reason_code="human_reviewed_fiscal_state",
        fiscal_state=fiscal_state,
    )

def _chatgpt_handoff_page(state: _VolatileSession) -> str:
    assert state.intake is not None
    try:
        prompt = build_chatgpt_handoff_prompt(state.intake.bundle, state.intake.documents)
        prompt_section = (
            "<p>Questo testo usa soltanto campi confermati. L'app non lo invia: selezionalo e copialo "
            "in ChatGPT manualmente. Non contiene i file originali né il testo OCR grezzo.</p>"
            "<p><strong>Trasferimento esterno:</strong> incollando questo testo in ChatGPT, i dati aziendali inclusi escono da questa app locale. "
            "Procedi solo se la tua organizzazione autorizza l'uso di ChatGPT con questi dati. L'app non invia nulla automaticamente.</p>"
            f'<textarea readonly rows="30" cols="100">{escape(prompt)}</textarea>'
        )
    except ChatGPTHandoffError as exc:
        prompt_section = f"<p>{escape(str(exc))} Dopo la revisione potrai tornare qui e incollare la bozza.</p>"
    draft_section = (
        f'<section><h2>Bozza restituita — non approvata</h2><pre>{escape(state.chatgpt_draft)}</pre>'
        '<p>Controlla ogni frase sugli originali. La bozza non modifica campi estratti o verificati '
        'e non autorizza rimborsi, pagamenti o registrazioni.</p></section>'
        if state.chatgpt_draft is not None else ""
    )
    return (
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Testo da copiare in ChatGPT</title><main><h1>ChatGPT manuale</h1>"
        "<p>La risposta sarà una bozza non verificata da controllare sugli originali.</p>"
        + prompt_section
        + '<form method="post" action="/chatgpt/return">'
        + '<label>Incolla qui la risposta (massimo 20.000 caratteri)'
        + '<textarea name="draft" rows="16" cols="100" maxlength="20000" required></textarea></label>'
        + '<button type="submit">Salva bozza nella sessione</button></form>'
        + draft_section
        + "<p><a href=\"/\">Torna al fascicolo</a></p></main></html>"
    )

def create_expense_report_app(
    *,
    limits: IngestionLimits = IngestionLimits(),
    max_batch_document_bytes: int = 100 * 1024 * 1024,
    idle_timeout_seconds: int = _SESSION_IDLE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    document_processor: Callable[[dict[str, Any], bytes], dict[str, Any]] | None = None,
    archive_store: LocalDocumentStore | None = None,
    ocr_processing_manager: OCRProcessingManager | None = None,
    custom_family_catalog: Any | None = None,
) -> Callable:
    """Create a loopback WSGI app with an idle-expiring session and optional explicit archive."""
    if not isinstance(idle_timeout_seconds, int) or isinstance(idle_timeout_seconds, bool) or idle_timeout_seconds <= 0:
        raise ValueError("idle_timeout_seconds must be a positive integer")
    if ocr_processing_manager is not None and document_processor is not None:
        raise ValueError("choose either a synchronous document processor or an OCR job manager")
    state: _VolatileSession | None = None
    csrf_token = secrets.token_urlsafe(32)
    state_lock = threading.RLock()
    app_closed = False

    def cancel_session(current: _VolatileSession | None) -> None:
        if current is not None and current.ocr_job_id is not None and ocr_processing_manager is not None:
            with state_lock:
                ocr_processing_manager.mark_cancelled(current.generation_id)

    def reject_result(current: _VolatileSession) -> bool:
        with state_lock:
            if state is current:
                current.ocr_publish_failed = True
        return False

    def publish_completed_result(current: _VolatileSession) -> bool:
        """Validate worker output outside the state lock, then atomically bind it to its generation."""
        if (ocr_processing_manager is None or current.intake is None
                or current.ocr_job_id is None):
            return False
        if current.ocr_result_published:
            return True
        job_id = current.ocr_job_id
        snapshot = ocr_processing_manager.snapshot(job_id)
        if snapshot is None or snapshot.phase != "succeeded":
            return False
        frame = ocr_processing_manager.result_frame(current.generation_id, job_id)
        if frame is None:
            return reject_result(current)
        try:
            envelope = decode_frame(
                frame, max_bytes=100 * 1024 * 1024, expected_kind="result",
            )
            payload = envelope["payload"]
            if (not isinstance(payload, dict) or payload.get("job_id") != job_id
                    or payload.get("generation_id") != current.generation_id):
                return reject_result(current)
            documents = payload.get("documents")
            if not isinstance(documents, dict) or set(documents) != set(current.intake.documents):
                return reject_result(current)
            validated: dict[str, dict[str, Any]] = {}
            for document_id, candidate in documents.items():
                original = current.intake.documents[document_id]
                source = candidate.get("source") if isinstance(candidate, dict) else None
                processing = candidate.get("processing") if isinstance(candidate, dict) else None
                ocr = processing.get("ocr") if isinstance(processing, dict) else None
                if (not isinstance(candidate, dict) or candidate.get("document_id") != document_id
                        or not isinstance(source, dict)
                        or source.get("sha256") != original["source"]["sha256"]
                        or not isinstance(ocr, dict) or ocr.get("status") != "completed"
                        or validate_document_record(candidate)):
                    return reject_result(current)
                validated[document_id] = candidate
        except (AttributeError, OCRJobProtocolError, KeyError, TypeError, ValueError):
            return reject_result(current)
        digest = hashlib.sha256(frame).hexdigest()
        with state_lock:
            if state is not current or current.generation_id != snapshot.generation_id:
                return False
            if current.ocr_result_published:
                return True
            if not ocr_processing_manager.publish_if_current(current.generation_id, job_id, digest):
                current.ocr_publish_failed = True
                return False
            current.intake = replace(current.intake, documents=validated)
            current.last_activity = clock()
            current.ocr_result_published = True
            return True

    def manager_status(current: _VolatileSession, job_id: str):
        if ocr_processing_manager is None or current.ocr_job_id != job_id:
            return None
        status = ocr_processing_manager.snapshot(job_id)
        if status is not None and status.generation_id != current.generation_id:
            return None
        return status

    def app(environ: dict[str, Any], start_response: Callable) -> list[bytes]:
        nonlocal state
        with state_lock:
            if app_closed:
                return _page(environ, start_response, "503 Service Unavailable", "Servizio locale in arresto")
        environ["_ocr2_csrf_token"] = csrf_token
        if _loopback_host_parts(environ.get("HTTP_HOST", "")) is None:
            return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
        if environ.get("REQUEST_METHOD", "") == "POST" and not _validate_loopback_post(environ, csrf_token):
            return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
        now = clock()
        if state is not None and now - state.last_activity > idle_timeout_seconds:
            expired = state
            with state_lock:
                if state is expired:
                    state = None
            cancel_session(expired)
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")
        if state is not None and state.ocr_starting and path not in {"/clear", "/upload", "/assign-note"}:
            return _page(environ, start_response, "409 Conflict", "<p>L’elaborazione OCR sta per iniziare. Attendi o cancella la sessione.</p>")
        if state is not None and state.ocr_job_id is not None:
            status = manager_status(state, state.ocr_job_id)
            is_cancel_request = re.fullmatch(
                r"/ocr/jobs/[0-9a-fA-F-]{1,64}/cancel", path,
            ) is not None
            if (status is not None and status.phase == "succeeded"
                    and path not in {"/clear", "/upload"} and not is_cancel_request):
                publish_completed_result(state)
            if state is not None and state.ocr_publish_failed and path not in {"/clear", "/upload"}:
                status = manager_status(state, state.ocr_job_id or "")
                if status is not None:
                    return _page(environ, start_response, "409 Conflict", _ocr_job_page(
                        status.job_id, status, archive_enabled=archive_store is not None,
                        publish_failed=True,
                    ))
        job_path = re.fullmatch(r"/ocr/jobs/([0-9a-fA-F-]{1,64})(?:/(cancel))?", path)
        if job_path is not None:
            if state is None or job_path.group(1) != state.ocr_job_id:
                return _page(environ, start_response, "404 Not Found", "Elaborazione non disponibile")
            job_id = job_path.group(1)
            status = manager_status(state, job_id)
            if status is None:
                return _page(environ, start_response, "404 Not Found", "Elaborazione non disponibile")
            if job_path.group(2) == "cancel":
                if method != "POST":
                    return _page(environ, start_response, "405 Method Not Allowed", "Metodo non consentito")
                if status.phase not in {"failed", "cancelled"} and not state.ocr_result_published:
                    cancel_session(state)
                status = manager_status(state, job_id) or status
                return _page(environ, start_response, "200 OK", _ocr_job_page(
                    job_id, status, archive_enabled=archive_store is not None,
                    publish_failed=state.ocr_publish_failed,
                ))
            if method != "GET":
                return _page(environ, start_response, "405 Method Not Allowed", "Metodo non consentito")
            if status.phase == "succeeded":
                publish_completed_result(state)
                status = manager_status(state, job_id) or status
            return _page(environ, start_response, "200 OK", _ocr_job_page(
                job_id, status, archive_enabled=archive_store is not None,
                publish_failed=state.ocr_publish_failed,
            ))
        if state is not None and state.ocr_job_id is not None:
            status = manager_status(state, state.ocr_job_id)
            if status is None and path not in {"/clear", "/upload"}:
                return _page(environ, start_response, "409 Conflict", "<p>Stato dell’elaborazione non verificabile. Cancella la sessione prima di continuare.</p>")
            pending = status is not None and status.phase not in {"succeeded", "failed", "cancelled"}
            terminal_unavailable = (
                status is not None and status.phase in {"failed", "cancelled"}
                and path not in {"/clear", "/upload"}
                and not path.startswith("/ocr/jobs/")
            )
            if terminal_unavailable:
                return _page(environ, start_response, "409 Conflict", _ocr_job_page(
                    status.job_id, status, archive_enabled=archive_store is not None,
                ))
            mutating_review = (
                path.startswith("/reviews/") or path.startswith("/chatgpt")
                or path.startswith("/archive/save/")
                or path.startswith("/archive/open/")
                or path.startswith("/archive/delete/")
                or path == "/archive/return"
            )
            if pending and mutating_review:
                return _page(environ, start_response, "409 Conflict", "<p>Elaborazione OCR in corso: attendi o annulla prima di rivedere o modificare i documenti.</p>")
        if archive_store is not None and method == "GET" and path == "/archive":
            raw_query = environ.get("QUERY_STRING", "")
            try:
                params = parse_qs(raw_query, keep_blank_values=True, max_num_fields=4)
                query = params.get("q", [""])
                if len(query) != 1 or len(query[0]) > 200:
                    raise ValueError
                return _page(environ, start_response, "200 OK", _archive_list_page(archive_store, query[0]))
            except ValueError:
                return _page(environ, start_response, "400 Bad Request", "<p>Ricerca non valida</p>")
            except StoreError:
                return _page(environ, start_response, "500 Internal Server Error", "<p>Archivio non disponibile</p>")
        if archive_store is not None and path.startswith("/archive/") and path != "/archive/return":
            parts = path.split("/")
            if len(parts) != 4:
                return _page(environ, start_response, "404 Not Found", "Risorsa non trovata")
            if len(parts) == 4:
                document_id = parts[3].removesuffix(".json").removesuffix(".csv")
                if not _ARCHIVE_ID.fullmatch(document_id):
                    return _page(environ, start_response, "404 Not Found", "Risorsa non trovata")
                try:
                    if method == "GET" and parts[2] == "export" and parts[3].endswith((".json", ".csv")):
                        stored = archive_store.get(document_id)
                        if stored is None:
                            return _page(environ, start_response, "404 Not Found", "Documento non trovato")
                        is_json = parts[3].endswith(".json")
                        output = export_document_json(stored.record) if is_json else export_document_csv(stored.record)
                        extension = "json" if is_json else "csv"
                        content_type = "application/json; charset=utf-8" if is_json else "text/csv; charset=utf-8"
                        return _page(environ, start_response, "200 OK", output, content_type,
                                     download_filename=f"ocr2-{document_id}.{extension}")
                    if method == "GET" and parts[2] == "delete":
                        stored = archive_store.get(document_id)
                        if stored is None:
                            return _page(environ, start_response, "404 Not Found", "Documento non trovato")
                        filename = escape(str(stored.record["source"].get("original_filename", "documento")))
                        return _page(environ, start_response, "200 OK",
                                     f'<h1>Conferma eliminazione</h1><p>{filename}</p>'
                                     f'<form method="post" action="/archive/delete/{quote(document_id, safe="")}">'
                                     '<button type="submit">Elimina definitivamente</button></form>'
                                     '<a href="/archive">Annulla</a>')
                    if method == "POST" and parts[2] == "open":
                        if not _same_origin_loopback_post(environ):
                            return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
                        stored = archive_store.get(document_id)
                        if stored is None:
                            return _page(environ, start_response, "404 Not Found", "Documento non trovato")
                        if state is None:
                            replacement = _VolatileSession(
                                secrets.token_hex(18), MaterializedBatch((), (), ()), (), now,
                                archive_only=True,
                            )
                            with state_lock:
                                state = replacement
                        elif state.intake is None:
                            return _page(environ, start_response, "409 Conflict",
                                         "<p>Completa o annulla prima la selezione dei documenti correnti.</p>")
                        if state.intake is None:
                            state.intake = ExpenseReportIntakeSession(
                                {"expense_report_id": f"archive-{state.session_id}", "note_document_id": document_id,
                                 "attachment_document_ids": []}, {}, {},
                            )
                        documents = dict(state.intake.documents)
                        sources = dict(state.intake.source_bytes)
                        documents[document_id] = deepcopy(stored.record)
                        sources[document_id] = stored.source_bytes
                        state.intake = replace(state.intake, documents=documents, source_bytes=sources)
                        state.archive_loaded_document_id = document_id
                        state.archive_baselines[document_id] = _record_fingerprint(stored.record)
                        state.last_activity = now
                        return _page(environ, start_response, "200 OK", _archive_document_page(document_id, stored.record))
                    if method == "POST" and parts[2] == "delete":
                        if not _same_origin_loopback_post(environ):
                            return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
                        deleted = archive_store.delete(document_id)
                        if state is not None and state.intake is not None:
                            documents = dict(state.intake.documents)
                            sources = dict(state.intake.source_bytes)
                            documents.pop(document_id, None)
                            sources.pop(document_id, None)
                            state.intake = replace(state.intake, documents=documents, source_bytes=sources)
                            state.archive_baselines.pop(document_id, None)
                            state.archive_ids = {
                                session_id: archived_id
                                for session_id, archived_id in state.archive_ids.items()
                                if archived_id != document_id
                            }
                            if state.archive_loaded_document_id == document_id:
                                state.archive_loaded_document_id = None
                        if not deleted:
                            return _page(environ, start_response, "404 Not Found", "Documento non trovato")
                        return _page(environ, start_response, "200 OK",
                                     '<p>Documento eliminato.</p><a href="/archive">Archivio</a>'
                                     '<form method="post" action="/archive/return"><button type="submit">Torna alla sessione corrente</button></form>')
                except StoreError:
                    return _page(environ, start_response, "500 Internal Server Error", "<p>Operazione archivio non riuscita</p>")
        if archive_store is not None and method == "POST" and path.startswith("/archive/save/"):
            if not _same_origin_loopback_post(environ):
                return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
            document_id = path[len("/archive/save/"):]
            if not _ARCHIVE_ID.fullmatch(document_id) or state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>Documento non disponibile nella sessione</p>")
            record = state.intake.documents.get(document_id)
            source_bytes = state.intake.source_bytes.get(document_id)
            if not isinstance(record, dict) or not isinstance(source_bytes, bytes):
                return _page(environ, start_response, "404 Not Found", "Documento non trovato")
            archive_id = state.archive_ids.get(document_id, document_id if document_id == state.archive_loaded_document_id else "")
            is_update = bool(archive_id)
            if not archive_id:
                archive_id = "archive-" + secrets.token_hex(16)
            baseline = None
            try:
                latest = archive_store.get(archive_id) if is_update else None
                if is_update:
                    baseline = state.archive_baselines.get(archive_id)
                    if latest is None or baseline is None or _record_fingerprint(latest.record) != baseline:
                        return _page(environ, start_response, "409 Conflict", "<p>Il documento è cambiato nell’archivio. Riaprilo prima di salvare.</p>")
                archived_record = deepcopy(record)
                archived_record["document_id"] = archive_id
                archived_record["source"]["storage_ref"] = f"local-archive://{archive_id}"
                archive_store.save(
                    archived_record,
                    source_bytes,
                    expected_record_sha256=baseline if is_update else None,
                )
                state.archive_ids[document_id] = archive_id
                state.archive_baselines[archive_id] = _record_fingerprint(archived_record)
                state.archive_loaded_document_id = archive_id if is_update else state.archive_loaded_document_id
                state.last_activity = now
                label = "Documento aggiornato" if is_update else "Documento salvato"
                return _page(environ, start_response, "200 OK", f'<p>{label} nell’archivio locale.</p><a href="/archive">Apri archivio</a>')
            except StoreConcurrentUpdate:
                return _page(environ, start_response, "409 Conflict", "<p>Il documento è cambiato durante il salvataggio. Riaprilo prima di riprovare.</p>")
            except StoreError:
                return _page(environ, start_response, "400 Bad Request", "<p>Il documento non può essere salvato nell’archivio</p>")
        if archive_store is not None and method == "POST" and path == "/archive/return":
            if not _same_origin_loopback_post(environ):
                return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
            if state is not None:
                state.archive_loaded_document_id = None
                state.last_activity = now
                if state.archive_only or not state.document_ids:
                    previous = state
                    with state_lock:
                        state = None
                    cancel_session(previous)
            if state is None:
                return _page(environ, start_response, "200 OK", _upload_page(archive_enabled=True))
            if state.intake is None:
                return _page(environ, start_response, "200 OK", _choose_note_page(state))
            return _page(environ, start_response, "200 OK", _bundle_page(state, archive_enabled=True))
        if method == "GET" and path == "/review-times.csv":
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["case_id", "review_seconds"])
            for document_id, seconds in sorted(state.review_seconds.items()):
                record = state.intake.documents.get(document_id)
                if isinstance(record, dict) and record["review"]["status"] == "completed":
                    writer.writerow([f"{state.session_id}-{document_id}", seconds])
            return _page(
                environ, start_response, "200 OK", output.getvalue(),
                "text/csv; charset=utf-8", download_filename="review-times.csv",
            )
        if method == "GET" and path in {"/", "/upload"}:
            if state is None:
                return _page(environ, start_response, "200 OK", _upload_page(archive_enabled=archive_store is not None))
            state.last_activity = now
            if state.intake is None:
                return _page(environ, start_response, "200 OK", _choose_note_page(state))
            if state.archive_loaded_document_id is not None:
                record = state.intake.documents.get(state.archive_loaded_document_id)
                if record is not None:
                    return _page(environ, start_response, "200 OK", _archive_document_page(state.archive_loaded_document_id, record))
            if state.archive_only:
                return _page(environ, start_response, "200 OK", _upload_page(archive_enabled=True))
            return _page(environ, start_response, "200 OK", _bundle_page(state, archive_enabled=archive_store is not None))
        if method == "POST" and path == "/upload":
            try:
                files = _multipart_files(environ)
                batch = materialize_stream_batch(
                    [(name, io.BytesIO(data)) for name, data in files],
                    limits,
                    max_batch_document_bytes=max_batch_document_bytes,
                )
            except (IntakeRequestError, UploadRejected, OSError, ValueError) as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p><p><a href=\"/\">Torna all'inizio</a></p>")
            payloads = tuple(document for upload in batch.uploads for document in upload.documents)
            if len(payloads) > _MAX_UPLOAD_FILES * 100:
                return _page(environ, start_response, "400 Bad Request", "<p>Numero di documenti estratti superato</p>")
            cancel_session(state)
            session_id = secrets.token_hex(18)
            document_ids = tuple(f"doc-{index + 1:03d}" for index in range(len(payloads)))
            replacement = _VolatileSession(session_id, batch, document_ids, now)
            previous = state
            with state_lock:
                state = replacement
            cancel_session(previous)
            return _page(environ, start_response, "200 OK", _choose_note_page(state))
        if method == "POST" and path == "/chatgpt/return":
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            try:
                draft = _multipart_scalar(environ, "draft", max_form_bytes=128 * 1024)
                if len(draft) > 20_000:
                    raise IntakeRequestError("La bozza supera il limite di 20.000 caratteri")
                state.chatgpt_draft = draft
                state.last_activity = now
            except IntakeRequestError as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p>")
            return _page(environ, start_response, "200 OK", _chatgpt_handoff_page(state))
        if method == "GET" and path == "/chatgpt" and state is not None and state.intake is not None:
            state.last_activity = now
            return _page(environ, start_response, "200 OK", _chatgpt_handoff_page(state))
        if method == "POST" and path == "/assign-note":
            session = state
            if session is None or session.intake is not None or session.ocr_starting:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di caricamento non è disponibile.</p>")
            try:
                note_id = _multipart_scalar(environ, "note_document_id")
                intake = create_expense_report_intake_session(
                    session.batch,
                    expense_report_id=f"report-{session.session_id}",
                    note_document_id=note_id,
                    document_ids=session.document_ids,
                    session_id=session.session_id,
                    received_at=datetime.now(timezone.utc).isoformat(),
                )
                if ocr_processing_manager is not None:
                    with state_lock:
                        if (app_closed or state is not session or session.ocr_starting
                                or session.intake is not None):
                            return _page(environ, start_response, "409 Conflict", "<p>La sessione è stata sostituita prima dell’avvio OCR.</p>")
                        session.ocr_starting = True
                    try:
                        job_id = ocr_processing_manager.start(
                            session.generation_id,
                            intake,
                            decode_limits=DecodeLimits(),
                            custom_family_catalog=custom_family_catalog,
                        )
                    except BaseException:
                        with state_lock:
                            if state is session:
                                session.ocr_starting = False
                        raise
                    with state_lock:
                        still_current = not app_closed and state is session
                        if still_current:
                            session.intake = intake
                            session.ocr_job_id = job_id
                            session.ocr_starting = False
                            session.last_activity = now
                    if not still_current:
                        ocr_processing_manager.mark_cancelled(session.generation_id)
                        return _page(environ, start_response, "409 Conflict", "<p>La sessione è stata sostituita; l’elaborazione associata è stata annullata.</p>")
                    job_status = ocr_processing_manager.snapshot(job_id)
                    if job_status is None or job_status.generation_id != session.generation_id:
                        cancel_session(session)
                        return _page(environ, start_response, "409 Conflict", "<p>Stato del nuovo job non disponibile; sessione annullata.</p>")
                    return _page(environ, start_response, "200 OK", _ocr_job_page(
                        job_id,
                        job_status,
                        archive_enabled=archive_store is not None,
                    ))
                if document_processor is not None:
                    processed_documents: dict[str, dict[str, Any]] = {}
                    for document_id, record in intake.documents.items():
                        try:
                            processed = document_processor(
                                deepcopy(record), intake.source_bytes[document_id]
                            )
                        except Exception as exc:
                            raise IntakeRequestError("Elaborazione OCR non riuscita") from exc
                        if not isinstance(processed, dict):
                            raise IntakeRequestError("Il processore OCR ha restituito un record non valido")
                        if processed.get("document_id") != document_id:
                            raise IntakeRequestError("Il processore OCR ha modificato l'identità del documento")
                        if processed.get("source", {}).get("sha256") != record["source"]["sha256"]:
                            raise IntakeRequestError("Il processore OCR ha modificato il legame alla fonte")
                        issues = validate_document_record(processed)
                        if issues:
                            raise IntakeRequestError("Il processore OCR ha restituito un record fuori contratto")
                        processed_documents[document_id] = processed
                    intake = replace(intake, documents=processed_documents)
                state.intake = intake
            except RuntimeError:
                with state_lock:
                    if state is session:
                        session.ocr_starting = False
                return _page(environ, start_response, "409 Conflict", "<p>Un'elaborazione precedente è ancora in chiusura. Attendi prima di avviarne un'altra.</p>")
            except (IntakeRequestError, ValueError) as exc:
                with state_lock:
                    if state is session:
                        session.ocr_starting = False
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p><p><a href=\"/\">Riprova</a></p>")
            state.last_activity = now
            return _page(environ, start_response, "200 OK", _bundle_page(state, archive_enabled=archive_store is not None))
        if method == "POST" and path == "/clear":
            previous = state
            with state_lock:
                state = None
            cancel_session(previous)
            return _page(environ, start_response, "200 OK", _upload_page(archive_enabled=archive_store is not None))
        preview_match = re.fullmatch(r"/reviews/([^/]+)/pages/([1-9][0-9]{0,4})\.png", path)
        if method == "GET" and preview_match is not None:
            if state is None or state.intake is None:
                return _page(environ, start_response, "404 Not Found", "Pagina non disponibile")
            document_id, raw_page = preview_match.groups()
            record = state.intake.documents.get(document_id)
            source_bytes = state.intake.source_bytes.get(document_id)
            if not isinstance(record, dict) or not isinstance(source_bytes, bytes):
                return _page(environ, start_response, "404 Not Found", "Pagina non disponibile")
            try:
                page_png = _source_page_png(record, source_bytes, int(raw_page))
            except (DocumentDecodeError, ValueError, OverflowError):
                return _page(environ, start_response, "422 Unprocessable Content", "Pagina non disponibile per la revisione")
            state.last_activity = now
            headers = [
                ("Content-Type", "image/png"),
                ("Content-Length", str(len(page_png))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Content-Security-Policy", "default-src 'none'; sandbox"),
                ("Referrer-Policy", "no-referrer"),
            ]
            start_response("200 OK", headers)
            return [page_png]
        if method == "GET" and path.startswith("/reviews/") and state is not None and state.intake is not None:
            review_app = create_review_app(state.intake.documents, state.intake.source_bytes)
            if path.endswith("/source"):
                return review_app(environ, start_response)
            document_id = path[len("/reviews/"):].rstrip("/")
            if document_id and "/" not in document_id:
                record = state.intake.documents.get(document_id)
                if record is not None:
                    if document_id == state.archive_loaded_document_id:
                        return _page(environ, start_response, "200 OK", _archive_document_page(document_id, record))
                    timestamp = datetime.now(timezone.utc).isoformat()
                    record = _begin_document_review(record, timestamp=timestamp)
                    state.intake.documents[document_id] = record
                    state.last_activity = now
                    return _page(
                        environ, start_response, "200 OK",
                        _render_editable_record(
                            record,
                            document_id=document_id,
                            has_source=document_id in state.intake.source_bytes,
                            elapsed_seconds=state.review_seconds.get(document_id, 0),
                            archive_save_enabled=archive_store is not None,
                        ),
                    )
            return review_app(environ, start_response)
        if method == "POST" and path.startswith("/reviews/") and path.endswith("/open"):
            if not _same_origin_loopback_post(environ):
                return _page(environ, start_response, "403 Forbidden", "Richiesta locale non valida")
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>Documento non disponibile</p>")
            document_id = path[len("/reviews/"):-len("/open")].rstrip("/")
            record = state.intake.documents.get(document_id)
            if document_id != state.archive_loaded_document_id or not isinstance(record, dict):
                return _page(environ, start_response, "404 Not Found", "Documento archiviato non trovato")
            record = _begin_document_review(record, timestamp=datetime.now(timezone.utc).isoformat())
            state.intake = replace(state.intake, documents={**state.intake.documents, document_id: record})
            state.last_activity = now
            editable = _render_editable_record(record, document_id=document_id,
                                               has_source=document_id in state.intake.source_bytes,
                                               elapsed_seconds=state.review_seconds.get(document_id, 0),
                                               archive_save_enabled=archive_store is not None)
            return _page(environ, start_response, "200 OK", editable)
        if method == "POST" and path.startswith("/reviews/") and path.endswith("/complete"):
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            document_id = path[len("/reviews/"):-len("/complete")].rstrip("/")
            try:
                record = state.intake.documents.get(document_id)
                if not document_id or "/" in document_id or not isinstance(record, dict):
                    raise IntakeRequestError("Documento non trovato")
                if record["review"]["status"] != "in_progress":
                    raise IntakeRequestError("La revisione non è aperta o è già conclusa")
                seconds = _read_review_seconds(environ)
                if seconds < state.review_seconds.get(document_id, 0):
                    raise IntakeRequestError("La durata non può diminuire durante la revisione")
                record = append_review_event(
                    record, actor_id="local-session", action="completed",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                state.intake.documents[document_id] = record
                state.review_seconds[document_id] = seconds
                state.last_activity = now
            except (IntakeRequestError, ValueError) as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p>")
            return _page(
                environ, start_response, "200 OK",
                f'<h1>Revisione conclusa</h1><p>Tempo con la scheda in primo piano: {seconds} secondi.</p>'
                '<p>La revisione non approva rimborsi né registrazioni.</p><p><a href="/review-times.csv">Scarica CSV benchmark</a></p>'
                '<p><a href="/">Torna al fascicolo</a></p>',
            )
        if method == "POST" and path.startswith("/reviews/") and path.endswith("/fiscal-state"):
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            document_id = path[len("/reviews/"):-len("/fiscal-state")].rstrip("/")
            try:
                fiscal_status = _multipart_scalar(environ, "fiscal_status")
                evidence_index = _multipart_scalar(environ, "evidence_index")
                seconds = _read_review_seconds(environ, required=False)
                record = state.intake.documents.get(document_id)
                if not document_id or "/" in document_id or not isinstance(record, dict):
                    raise IntakeRequestError("Documento non trovato")
                if seconds < state.review_seconds.get(document_id, 0):
                    raise IntakeRequestError("La durata non può diminuire durante la revisione")
                updated = _apply_fiscal_state_correction(
                    record, status=fiscal_status, evidence_index=evidence_index,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                state.intake.documents[document_id] = updated
                state.review_seconds[document_id] = seconds
                state.last_activity = now
            except (IntakeRequestError, ValueError) as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p>")
            return _page(environ, start_response, "200 OK", _render_editable_record(
                state.intake.documents[document_id], document_id=document_id,
                has_source=document_id in state.intake.source_bytes,
                elapsed_seconds=state.review_seconds.get(document_id, 0),
                archive_save_enabled=archive_store is not None,
            ))
        if method == "POST" and path.startswith("/reviews/") and path.endswith("/document-family"):
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            document_id = path[len("/reviews/"):-len("/document-family")].rstrip("/")
            try:
                family = _multipart_scalar(environ, "document_family")
                seconds = _read_review_seconds(environ, required=False)
                record = state.intake.documents.get(document_id)
                if not document_id or "/" in document_id or not isinstance(record, dict):
                    raise IntakeRequestError("Documento non trovato")
                if seconds < state.review_seconds.get(document_id, 0):
                    raise IntakeRequestError("La durata non può diminuire durante la revisione")
                updated = _apply_document_family_selection(record, family=family, timestamp=datetime.now(timezone.utc).isoformat())
                state.intake.documents[document_id] = updated
                state.review_seconds[document_id] = seconds
                state.last_activity = now
            except (IntakeRequestError, ValueError) as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p>")
            return _page(environ, start_response, "200 OK", _render_editable_record(
                state.intake.documents[document_id], document_id=document_id,
                has_source=document_id in state.intake.source_bytes,
                elapsed_seconds=state.review_seconds.get(document_id, 0),
                archive_save_enabled=archive_store is not None,
            ))
        if method == "POST" and path.startswith("/reviews/") and "/fields/" in path:
            if state is None or state.intake is None:
                return _page(environ, start_response, "409 Conflict", "<p>La sessione di revisione non è disponibile.</p>")
            prefix, field_name = path.split("/fields/", 1)
            document_id = prefix[len("/reviews/"):] if prefix.startswith("/reviews/") else ""
            try:
                value = _multipart_scalar(environ, "value")
                region_page_raw = _multipart_scalar(environ, "region_page", required=False)
                coordinate_names = ("region_x0", "region_y0", "region_x1", "region_y1")
                coordinate_values = tuple(
                    _multipart_scalar(environ, name, required=False) for name in coordinate_names
                )
                has_region_values = bool(region_page_raw) or any(coordinate_values)
                if has_region_values:
                    if (
                        not region_page_raw.isascii() or not region_page_raw.isdecimal()
                        or len(region_page_raw) > 5 or not all(coordinate_values)
                        or any(len(item) > 64 for item in coordinate_values)
                    ):
                        raise IntakeRequestError("Riferimento alla pagina o coordinate non valide")
                    region_page_number = int(region_page_raw)
                    region_coordinates = coordinate_values
                else:
                    region_page_number = None
                    region_coordinates = None
                seconds = _read_review_seconds(environ, required=False)
                record = state.intake.documents.get(document_id)
                if not document_id or "/" in document_id or not isinstance(record, dict):
                    raise IntakeRequestError("Documento non trovato")
                if region_page_number is not None:
                    source_bytes = state.intake.source_bytes.get(document_id)
                    source = record.get("source", {})
                    if (
                        not isinstance(source_bytes, bytes)
                        or source.get("byte_length") != len(source_bytes)
                        or source.get("sha256") != hashlib.sha256(source_bytes).hexdigest()
                    ):
                        raise IntakeRequestError("Il documento originale non è disponibile o non corrisponde al record")
                if seconds < state.review_seconds.get(document_id, 0):
                    raise IntakeRequestError("La durata non può diminuire durante la revisione")
                updated = _apply_field_correction(
                    record,
                    field_name=field_name,
                    value=value,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    region_page_number=region_page_number,
                    region_coordinates=region_coordinates,
                )
                if region_page_number is not None and validate_document_record(updated):
                    raise IntakeRequestError("La correzione manuale non soddisfa il contratto del documento")
                state.intake.documents[document_id] = updated
                state.review_seconds[document_id] = seconds
                state.last_activity = now
            except (IntakeRequestError, ValueError) as exc:
                return _page(environ, start_response, "400 Bad Request", f"<p>{escape(str(exc))}</p>")
            return _page(
                environ, start_response, "200 OK",
                _render_editable_record(
                    state.intake.documents[document_id],
                    document_id=document_id,
                    has_source=document_id in state.intake.source_bytes,
                    elapsed_seconds=state.review_seconds.get(document_id, 0),
                    archive_save_enabled=archive_store is not None,
                ),
            )
        if method != "GET" and method != "POST":
            return _page(environ, start_response, "405 Method Not Allowed", "Metodo non consentito", "text/plain; charset=utf-8")
        return _page(environ, start_response, "404 Not Found", "Risorsa non trovata", "text/plain; charset=utf-8")

    def close() -> None:
        nonlocal app_closed, state
        with state_lock:
            app_closed = True
            current = state
            state = None
        cancel_session(current)
        if ocr_processing_manager is not None:
            ocr_processing_manager.close()

    app.close = close
    return app


def _multipart_form_values(environ: dict[str, Any], *, max_form_bytes: int = 64 * 1024) -> dict[str, list[str]]:
    cached = environ.get("_parsed_form_values")
    if isinstance(cached, dict):
        return cached
    content_length = environ.get("CONTENT_LENGTH", "")
    try:
        length = int(content_length)
    except (TypeError, ValueError) as exc:
        raise IntakeRequestError("Content-Length non valido") from exc
    if length <= 0 or length > max_form_bytes:
        raise IntakeRequestError("Dimensione del modulo non valida")
    content_type = environ.get("CONTENT_TYPE", "")
    header = Message()
    header["content-type"] = content_type
    if header.get_content_type() != "application/x-www-form-urlencoded":
        raise IntakeRequestError("Modulo di assegnazione non valido")
    body = environ["wsgi.input"].read(length)
    if not isinstance(body, bytes) or len(body) != length:
        raise IntakeRequestError("Corpo del modulo incompleto")
    try:
        from urllib.parse import parse_qs
        values = parse_qs(
            body.decode("ascii"), strict_parsing=True, keep_blank_values=True,
            max_num_fields=_MAX_URLENCODED_FIELDS,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise IntakeRequestError("Modulo di assegnazione non valido") from exc
    tokens = values.pop("_ocr2_csrf", [])
    if len(tokens) > 1 or sum(len(items) for items in values.values()) >= _MAX_URLENCODED_FIELDS:
        raise IntakeRequestError("Modulo di assegnazione non valido")
    environ["_parsed_form_values"] = values
    return values


def _multipart_scalar(
    environ: dict[str, Any], field_name: str, *, max_form_bytes: int = 64 * 1024, required: bool = True
) -> str:
    values = _multipart_form_values(environ, max_form_bytes=max_form_bytes).get(field_name, [])
    if not values and not required:
        return ""
    if len(values) != 1 or not values[0]:
        raise IntakeRequestError("Seleziona esattamente una nota spese")
    return values[0]

def serve_expense_report_local(
    *,
    port: int = 8000,
    limits: IngestionLimits = IngestionLimits(),
    max_batch_document_bytes: int = 100 * 1024 * 1024,
    document_processor: Callable[[dict[str, Any], bytes], dict[str, Any]] | None = None,
    archive_store: LocalDocumentStore | None = None,
    ocr_processing_manager: OCRProcessingManager | None = None,
    custom_family_catalog: Any | None = None,
):
    """Create a local HTTP server bound exclusively to IPv4 loopback."""
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    app = create_expense_report_app(
        limits=limits,
        max_batch_document_bytes=max_batch_document_bytes,
        document_processor=document_processor,
        archive_store=archive_store,
        ocr_processing_manager=ocr_processing_manager,
        custom_family_catalog=custom_family_catalog,
    )
    server = make_server("127.0.0.1", port, app)
    server.ocr2_close = app.close
    return server
