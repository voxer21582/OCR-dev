import hashlib
import io
import json
import re
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
from alfa_document_intelligence.local_intake_app import create_expense_report_app


NOTE = b"%PDF-1.7\nsynthetic expense report\n"
RECEIPT = b"%PDF-1.7\nsynthetic fiscal receipt\n"


def _zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("Trasferta/nota.pdf", NOTE)
        archive.writestr("Trasferta/ricevuta.pdf", RECEIPT)
    return buffer.getvalue()


def _multipart(filename, data, boundary="test-boundary"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _review_head(page):
    match = re.search(rb'name="expected_review_head" value="([a-f0-9]*)"', page)
    assert match, "review page must bind forms to the current review ledger"
    return match.group(1).decode("ascii")


def _review_payload(page, values):
    return urlencode({**values, "expected_review_head": _review_head(page)}).encode()


def _assert_review_forms_bound(page):
    forms = re.findall(rb'<form\b(?=[^>]*\bdata-review-timer\b)[^>]*>(.*?)</form>', page, re.IGNORECASE | re.DOTALL)
    assert forms, "review page must contain at least one review form"
    assert all(re.search(rb'name="expected_review_head" value="[a-f0-9]*"', form) for form in forms)


def _request(app, method="GET", path="/", body=b"", content_type=""):
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": "http://127.0.0.1:8080",
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    result = b"".join(app(environ, start_response))
    return response["status"], response["headers"], result


def test_browser_upload_selects_expense_note_from_zip_and_shows_linked_sources():
    app = create_expense_report_app()
    status, headers, page = _request(app)
    assert status == "200 OK"
    assert b'type="file"' in page and b'multiple' in page
    assert headers["Cache-Control"] == "no-store"

    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    status, _, page = _request(app, "POST", "/upload", body, content_type)
    assert status == "200 OK"
    assert b"Trasferta/nota.pdf" in page
    assert b"Trasferta/ricevuta.pdf" in page
    assert b"Quale file" in page

    assign = urlencode({"note_document_id": "doc-001"}).encode()
    status, _, bundle = _request(
        app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded"
    )
    assert status == "200 OK"
    assert b"Nota spese" in bundle
    assert b"Giustificativo" in bundle
    assert b"SHA-256" in bundle

    status, headers, detail = _request(app, path="/reviews/doc-001")
    assert status == "200 OK"
    assert b"Apri documento originale" in detail
    status, headers, original = _request(app, path="/reviews/doc-001/source")
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/pdf"
    assert original == NOTE


def test_reviewer_can_select_only_an_evidence_bound_document_family():
    def processor(record, _source_bytes):
        record["pages"] = [{"page_number": 1, "width_px": 1000, "height_px": 1400}]
        record["processing"]["ocr"]["status"] = "completed"
        evidence = {
            "source_sha256": record["source"]["sha256"],
            "page_number": 1,
            "token_ids": ["synthetic-family-cue"],
            "literal": "CARD PAYMENT SLIP",
            "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
        }
        fiscal_evidence = {
            "source_sha256": record["source"]["sha256"],
            "page_number": 1,
            "token_ids": ["synthetic-fiscal-status"],
            "literal": "SYNTHETIC FISCAL STATUS REGION",
            "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
        }
        record["fiscal_document_state"] = {"status": "unknown", "evidence": [fiscal_evidence]}
        record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain",
            "alternatives": [{"value": "pos_slip", "status": "observed", "evidence": [evidence]}],
            "evidence": [evidence],
        }
        return record

    app = create_expense_report_app(document_processor=processor)
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")

    status, _, review = _request(app, path="/reviews/doc-002")
    assert status == "200 OK"
    assert b"Famiglia del documento" in review
    assert b"Seleziona famiglia" in review
    assert b"pos_slip" in review
    assert b"La famiglia non determina da sola lo stato fiscale" in review
    assert b"Proposta automatica iniziale" in review
    assert b"Non determinato" in review
    assert b"SYNTHETIC FISCAL STATUS REGION" in review
    assert b'<option value="unknown"' not in review
    initial_head = _review_head(review)
    _assert_review_forms_bound(review)
    missing_head = urlencode({"document_family": "pos_slip", "review_seconds": "1"}).encode()
    status, _, conflict = _request(app, "POST", "/reviews/doc-002/document-family", missing_head, "application/x-www-form-urlencoded")
    assert status == "409 Conflict"
    assert b"altra scheda" in conflict

    invalid = _review_payload(review, {"document_family": "fiscal_document", "review_seconds": "0"})
    status, _, error = _request(app, "POST", "/reviews/doc-002/document-family", invalid, "application/x-www-form-urlencoded")
    assert status == "400 Bad Request"
    assert b"Famiglia documento non supportata" in error

    selected = _review_payload(review, {"document_family": "pos_slip", "review_seconds": "1"})
    status, _, reviewed = _request(app, "POST", "/reviews/doc-002/document-family", selected, "application/x-www-form-urlencoded")
    assert status == "200 OK"
    assert b"Famiglia attualmente revisionata: pos_slip" in reviewed
    assert b"<h2>document_family_candidates</h2>" in reviewed
    assert b"Stato fiscale" in reviewed
    current_head = _review_head(reviewed)
    stale = urlencode({"document_family": "pos_slip", "review_seconds": "1", "expected_review_head": initial_head}).encode()
    status, _, conflict = _request(app, "POST", "/reviews/doc-002/document-family", stale, "application/x-www-form-urlencoded")
    assert status == "409 Conflict"
    assert b"altra scheda" in conflict
    status, _, current = _request(app, path="/reviews/doc-002")
    assert status == "200 OK"
    assert _review_head(current) == current_head
    assert b"Famiglia attualmente revisionata: pos_slip" in current

    invalid_fiscal = _review_payload(current, {"fiscal_status": "fiscal_document", "evidence_index": "0", "review_seconds": "1"})
    status, _, error = _request(app, "POST", "/reviews/doc-002/fiscal-state", invalid_fiscal, "application/x-www-form-urlencoded")
    assert status == "400 Bad Request"
    assert b"ricevuta POS" in error

    invalid_evidence = _review_payload(current, {"fiscal_status": "payment_evidence", "evidence_index": "99", "review_seconds": "1"})
    status, _, error = _request(app, "POST", "/reviews/doc-002/fiscal-state", invalid_evidence, "application/x-www-form-urlencoded")
    assert status == "400 Bad Request"
    assert b"Evidenza non disponibile" in error

    decreasing = _review_payload(current, {"fiscal_status": "payment_evidence", "evidence_index": "0", "review_seconds": "0"})
    status, _, error = _request(app, "POST", "/reviews/doc-002/fiscal-state", decreasing, "application/x-www-form-urlencoded")
    assert status == "400 Bad Request"
    assert b"durata non pu" in error

    payment = _review_payload(current, {"fiscal_status": "payment_evidence", "evidence_index": "0", "review_seconds": "2"})
    status, _, fiscal_reviewed = _request(app, "POST", "/reviews/doc-002/fiscal-state", payment, "application/x-www-form-urlencoded")
    assert status == "200 OK"
    assert b"Stato dopo revisione umana" in fiscal_reviewed
    assert b"Stato attuale: Prova di pagamento" in fiscal_reviewed
    assert b"Proposta automatica iniziale" in fiscal_reviewed
    assert b"Storia delle classificazioni fiscali" in fiscal_reviewed
    assert b"human_reviewed_fiscal_state" in fiscal_reviewed
    assert b"Risultati automatici non aggiornati" in fiscal_reviewed
    assert b"Famiglia attualmente revisionata: pos_slip" in fiscal_reviewed


def test_review_view_separates_ocr_proposal_from_human_correction_and_marks_results_stale():
    def processor(record, _source_bytes):
        if record.get("document_family") == "expense_report":
            return record
        record["pages"] = [{"page_number": 1, "width_px": 1000, "height_px": 1400}]
        record["processing"]["ocr"]["status"] = "completed"
        evidence = {
            "source_sha256": record["source"]["sha256"],
            "page_number": 1,
            "token_ids": ["synthetic-merchant"],
            "literal": "HOTEL ALFA",
            "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
        }
        alternative_evidence = {
            "source_sha256": record["source"]["sha256"],
            "page_number": 1,
            "region": {
                "coordinate_space": "normalized_page",
                "polygon": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.3], [0.1, 0.3]],
            },
            "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
        }
        record["fields"]["merchant_name"] = {
            "value": "HOTEL ALFA", "status": "uncertain",
            "alternatives": [
                {"value": "HOTEL ALFA", "status": "uncertain", "evidence": [evidence]},
                {"value": "HOTEL BETA", "status": "uncertain", "evidence": [alternative_evidence]},
            ],
            "evidence": [evidence],
        }
        return record

    app = create_expense_report_app(document_processor=processor)
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")

    status, _, page = _request(app, path="/reviews/doc-002")
    assert status == "200 OK"
    assert b"Proposta automatica iniziale" in page
    assert b"incerto" in page
    assert b"Alternative proposte" in page
    assert b"HOTEL BETA" in page
    assert hashlib.sha256(RECEIPT).hexdigest().encode() in page
    assert b"normalized_page" in page
    assert b"Risultati automatici non aggiornati" not in page

    correction = _review_payload(page, {"value": "HOTEL GAMMA", "review_seconds": "1"})
    status, _, reviewed = _request(
        app, "POST", "/reviews/doc-002/fields/merchant_name", correction,
        "application/x-www-form-urlencoded",
    )
    assert status == "200 OK"
    assert b"Proposta automatica iniziale" in reviewed
    assert b"HOTEL ALFA" in reviewed
    assert b"HOTEL GAMMA" in reviewed
    assert b"Correzione umana" in reviewed
    assert hashlib.sha256(RECEIPT).hexdigest().encode() in reviewed
    assert b"human_corrected" in reviewed
    assert b"risultati automatici" in reviewed.lower()
    assert b"non aggiornati" in reviewed.lower()


def test_reviewer_can_select_a_custom_family_with_its_validated_snapshot():
    catalog = load_custom_family_catalog(json.dumps({
        "catalog_version": "1",
        "families": [{
            "id": "custom_taxi_receipt",
            "label": "Ricevuta taxi",
            "title_cues": ["RICEVUTA TAXI"],
            "fields": [{"id": "pickup_city", "label": "Città", "aliases": ["Partenza"]}],
        }],
    }, ensure_ascii=False))

    def processor(record, _source_bytes):
        if record.get("document_family") != "expense_report":
            record["schema_version"] = "0.2.0"
            record["document_family"] = "unknown"
            record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
            record["pages"] = [{"page_number": 1, "width_px": 1000, "height_px": 1400}]
            record["processing"]["ocr"]["status"] = "completed"
            evidence = {
                "source_sha256": record["source"]["sha256"],
                "page_number": 1,
                "token_ids": ["synthetic-family-cue"],
                "literal": "RICEVUTA TAXI",
                "producer": {"stage": "ocr", "name": "synthetic", "version": "1"},
            }
            record["fields"]["document_family_candidates"] = {
                "value": None,
                "status": "uncertain",
                "alternatives": [{
                    "value": "custom_taxi_receipt",
                    "status": "observed",
                    "evidence": [evidence],
                }],
                "evidence": [evidence],
            }
        return record

    app = create_expense_report_app(document_processor=processor)
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")

    status, _, review = _request(app, path="/reviews/doc-002")
    assert status == "200 OK"
    assert b'<option value="custom_taxi_receipt">Ricevuta taxi</option>' in review
    _assert_review_forms_bound(review)

    unsupported = _review_payload(review, {"document_family": "custom_wrong_family", "review_seconds": "1"})
    status, _, error = _request(
        app, "POST", "/reviews/doc-002/document-family", unsupported,
        "application/x-www-form-urlencoded",
    )
    assert status == "400 Bad Request"
    assert b"snapshot valido" in error

    selected = _review_payload(review, {"document_family": "custom_taxi_receipt", "review_seconds": "1"})
    status, _, reviewed = _request(
        app, "POST", "/reviews/doc-002/document-family", selected,
        "application/x-www-form-urlencoded",
    )

    assert status == "200 OK"
    assert b"Famiglia attualmente revisionata: custom_taxi_receipt" in reviewed
def test_clear_releases_volatile_session_and_returns_to_upload_form():
    app = create_expense_report_app()
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")

    status, _, page = _request(
        app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded"
    )
    assert status == "200 OK"
    assert b"Carica nota spese" in page
    status, _, missing = _request(app, path="/reviews/doc-001")
    assert status == "404 Not Found"


def test_invalid_uploads_and_note_assignment_fail_without_creating_a_bundle():
    app = create_expense_report_app()
    status, _, error = _request(app, "POST", "/upload", b"x", "text/plain")
    assert status == "400 Bad Request"
    assert b"multipart" in error

    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "not-in-session"}).encode()
    status, _, error = _request(
        app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded"
    )
    assert status == "400 Bad Request"
    assert b"note" in error

    status, _, page = _request(app)
    assert status == "200 OK"
    assert b"Quale file" in page
    assert b"Documenti collegati" not in page


def test_in_memory_session_expires_after_idle_timeout():
    now = [100.0]
    app = create_expense_report_app(idle_timeout_seconds=10, clock=lambda: now[0])
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    now[0] += 11

    status, _, page = _request(app)
    assert status == "200 OK"
    assert b"Carica nota spese" in page
    assert b"Quale file" not in page



def test_chatgpt_prompt_page_warns_before_manual_external_transfer(monkeypatch):
    app = create_expense_report_app()
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")
    monkeypatch.setattr(
        "alfa_document_intelligence.local_intake_app.build_chatgpt_handoff_prompt",
        lambda _bundle, _documents: "verified sample prompt",
    )

    status, _, page = _request(app, path="/chatgpt")

    assert status == "200 OK"
    assert b"verified sample prompt" in page
    assert b"Trasferimento esterno" in page
    assert b"dati aziendali inclusi escono da questa app locale" in page
    assert b"organizzazione autorizza l'uso di ChatGPT con questi dati" in page
    assert b"non invia nulla automaticamente" in page



def test_chatgpt_response_is_returned_as_escaped_unapproved_volatile_draft():
    app = create_expense_report_app()
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")

    status, _, page = _request(app, path="/chatgpt")
    assert status == "200 OK"
    assert b"copiarlo in ChatGPT" not in page
    assert b' action="/chatgpt/return"' in page
    assert b"bozza" in page

    returned = "<script>alert('x')</script> rimborso approvato"
    status, headers, page = _request(
        app, "POST", "/chatgpt/return", urlencode({"draft": returned}).encode(),
        "application/x-www-form-urlencoded",
    )
    assert status == "200 OK"
    assert headers["Cache-Control"] == "no-store"
    assert b"<script>" not in page
    assert b"&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in page
    assert b"Bozza restituita" in page
    assert b"non approvata" in page
    assert b"non autorizza rimborsi" in page

    status, _, detail = _request(app, path="/reviews/doc-001")
    assert status == "200 OK"
    assert b"rimborso approvato" not in detail


def test_chatgpt_return_rejects_oversized_drafts_and_requires_active_session():
    app = create_expense_report_app()
    oversized = urlencode({"draft": "x" * 20_001}).encode()
    status, _, error = _request(
        app, "POST", "/chatgpt/return", oversized,
        "application/x-www-form-urlencoded",
    )
    assert status == "409 Conflict"

    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")
    status, _, error = _request(
        app, "POST", "/chatgpt/return", oversized,
        "application/x-www-form-urlencoded",
    )
    assert status == "400 Bad Request"
    assert b"20.000" in error

    _request(app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
    status, _, error = _request(
        app, "POST", "/chatgpt/return", urlencode({"draft": "test"}).encode(),
        "application/x-www-form-urlencoded",
    )
    assert status == "409 Conflict"


def test_browser_can_use_an_explicit_processor_for_every_bundle_document():
    from copy import deepcopy

    processed = []

    def processor(record, source_bytes):
        assert source_bytes
        result = deepcopy(record)
        result["processing"]["ocr"] = {"status": "completed"}
        processed.append(result["document_id"])
        return result

    app = create_expense_report_app(document_processor=processor)
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    status, _, _ = _request(app, "POST", "/upload", body, content_type)
    assert status == "200 OK"

    assign = urlencode({"note_document_id": "doc-001"}).encode()
    status, _, bundle = _request(
        app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded"
    )

    assert status == "200 OK"
    assert processed == ["doc-001", "doc-002"]
    assert bundle.count(b"OCR: completed") == 2


def _multipart_many(files, boundary="many-boundary"):
    chunks = []
    for filename, data in files:
        headers = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode()
        chunks.append(headers + data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"



def test_review_timer_counts_active_tab_time_and_exports_only_opaque_completed_rows():
    app = create_expense_report_app()
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    _request(
        app, "POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode(),
        "application/x-www-form-urlencoded",
    )

    status, headers, page = _request(app, path="/reviews/doc-001")
    assert status == "200 OK"
    assert "script-src 'nonce-" in headers["Content-Security-Policy"]
    assert b'data-review-timer' in page
    assert b'Concludi revisione' in page
    assert b'__CSP_NONCE__' not in page
    assert b'document.addEventListener("visibilitychange"' in page
    assert b'wasVisible=!document.hidden' in page
    _assert_review_forms_bound(page)

    status, _, done = _request(
        app, "POST", "/reviews/doc-001/complete",
        _review_payload(page, {"review_seconds": "12"}),
        "application/x-www-form-urlencoded",
    )
    assert status == "200 OK"
    assert b"Tempo con la scheda in primo piano: 12 secondi" in done

    status, headers, report = _request(app, path="/review-times.csv")
    assert status == "200 OK"
    assert headers["Content-Type"] == "text/csv; charset=utf-8"
    assert headers["Content-Disposition"] == 'attachment; filename="review-times.csv"'
    assert report.startswith(b"case_id,review_seconds\n")
    assert b"-doc-001,12\n" in report
    assert b"Trasferta" not in report
    assert b"nota.pdf" not in report


def test_review_timer_rejects_invalid_or_decreasing_duration_and_clears_volatile_values():
    app = create_expense_report_app()
    body, content_type = _multipart("trasferta.zip", _zip_bytes())
    _request(app, "POST", "/upload", body, content_type)
    _request(
        app, "POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode(),
        "application/x-www-form-urlencoded",
    )
    status, _, page = _request(app, path="/reviews/doc-001")
    assert status == "200 OK"
    _assert_review_forms_bound(page)

    for duration in ("-1", "86401", "1.5"):
        status, _, _ = _request(
            app, "POST", "/reviews/doc-001/complete",
            _review_payload(page, {"review_seconds": duration}),
            "application/x-www-form-urlencoded",
        )
        assert status == "400 Bad Request"

    status, _, _ = _request(
        app, "POST", "/reviews/doc-001/complete",
        _review_payload(page, {"review_seconds": "12"}),
        "application/x-www-form-urlencoded",
    )
    assert status == "200 OK"
    status, _, conflict = _request(
        app, "POST", "/reviews/doc-001/complete",
        _review_payload(page, {"review_seconds": "11"}),
        "application/x-www-form-urlencoded",
    )
    assert status == "409 Conflict"
    assert b"altra scheda" in conflict

    status, _, _ = _request(app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
    assert status == "200 OK"
    status, _, unavailable = _request(app, path="/review-times.csv")
    assert status == "409 Conflict"
    assert b"sessione di revisione" in unavailable


def test_local_browser_accepts_a_1000_document_synthetic_bundle():
    archives = []
    for archive_number in range(10):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for member_number in range(100):
                unique = archive_number * 100 + member_number
                archive.writestr(
                    f"trip-{archive_number:02d}/receipt-{member_number:03d}.pdf",
                    f"%PDF-1.7\\nsynthetic receipt {unique:04d}\\n".encode(),
                )
        archives.append((f"trip-{archive_number:02d}.zip", buffer.getvalue()))

    app = create_expense_report_app()
    body, content_type = _multipart_many(archives)
    status, _, choice_page = _request(app, "POST", "/upload", body, content_type)
    assert status == "200 OK"
    assert b"doc-1000" in choice_page

    assignment = urlencode({"note_document_id": "doc-001"}).encode()
    status, _, bundle = _request(
        app, "POST", "/assign-note", assignment, "application/x-www-form-urlencoded"
    )
    assert status == "200 OK"
    assert bundle.count(b"Riferimento benchmark:") == 1000
    assert b"doc-1000" in bundle
