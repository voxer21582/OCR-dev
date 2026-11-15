import io
import re
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence import local_intake_app
from alfa_document_intelligence.local_intake_app import create_expense_report_app


NOTE = b"%PDF-1.7\nsynthetic expense report\n"
RECEIPT = b"%PDF-1.7\nsynthetic receipt\n"


def _request(app, method="GET", path="/", body=b"", content_type=""):
    result = {}

    def start_response(status, headers):
        result["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": "http://127.0.0.1:8080",
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    return result, b"".join(app(environ, start_response))


def _upload(app):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zipped:
        zipped.writestr("private-note-name.pdf", NOTE)
        zipped.writestr("private-receipt-name.pdf", RECEIPT)
    boundary = "chatgpt-handoff-test"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="private-trip.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + archive.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    result, _ = _request(app, "POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
    assert result["status"] == "200 OK"


def test_handoff_internal_error_does_not_expose_exception_details(monkeypatch):
    app = create_expense_report_app()
    _upload(app)
    result, _ = _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
    assert result["status"] == "200 OK"
    secret = "INTERNAL_HANDOFF_TRACE_SENTINEL"
    monkeypatch.setattr(local_intake_app, "build_chatgpt_handoff_prompt", lambda *a, **k: (_ for _ in ()).throw(ValueError(secret)))
    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert secret.encode() not in page
    assert b"non disponibile" in page


def test_browser_shows_manual_prompt_only_after_human_field_confirmation(monkeypatch):
    original_create = local_intake_app.create_expense_report_intake_session

    def with_synthetic_candidate(*args, **kwargs):
        session = original_create(*args, **kwargs)
        record = session.documents["doc-001"]
        record["pages"] = [{"page_number": 1}]
        record["fields"]["total_amount"] = {
            "value": "99.99",
            "status": "uncertain",
            "alternatives": [],
            "evidence": [{
                "source_sha256": record["source"]["sha256"],
                "page_number": 1,
                "region": {"x": 1, "y": 1, "width": 10, "height": 4},
                "literal": "OCR raw total",
            }],
        }
        return session

    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", with_synthetic_candidate)
    app = create_expense_report_app()
    _upload(app)
    assign = urlencode({"note_document_id": "doc-001"}).encode()
    result, _ = _request(app, "POST", "/assign-note", assign, "application/x-www-form-urlencoded")
    assert result["status"] == "200 OK"

    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert b"confirm fields first" in page
    assert b"<textarea readonly" not in page

    result, review_page = _request(app, path="/reviews/doc-001")
    assert result["status"] == "200 OK"
    head = re.search(rb'name="expected_review_head" value="([a-f0-9]{64})"', review_page).group(1).decode()
    correction = urlencode({"value": "100.00", "expected_review_head": head}).encode()
    result, _ = _request(
        app,
        "POST",
        "/reviews/doc-001/fields/total_amount",
        correction,
        "application/x-www-form-urlencoded",
    )
    assert result["status"] == "200 OK"

    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert b"<textarea readonly" in page
    assert b"100.00" in page
    assert b"expense_note" in page
    assert b"private-note-name.pdf" not in page
    assert b"private-receipt-name.pdf" not in page
    assert b"private-trip.zip" not in page
    assert b"OCR raw total" not in page
    assert b"non lo invia" in page


def test_blocked_review_requires_confirmation_of_current_prompt(monkeypatch):
    from alfa_document_intelligence.review_ledger import append_review_event
    real = local_intake_app.create_expense_report_intake_session
    captured = {}
    def blocked(*args, **kwargs):
        session = real(*args, **kwargs)
        record = session.documents["doc-001"]
        for action in ("queued", "opened", "flagged"):
            kw = {"reason_code": "synthetic_block"} if action == "flagged" else {}
            record = append_review_event(record, actor_id="synthetic", action=action, timestamp="2026-11-15T12:00:00Z", **kw)
        session.documents["doc-001"] = record
        captured["session"] = session
        return session
    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", blocked)
    monkeypatch.setattr(local_intake_app, "build_chatgpt_handoff_prompt", lambda bundle, docs: "synthetic prompt " + docs["doc-001"]["document_family"])
    app = create_expense_report_app(); _upload(app)
    _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
    result, page = _request(app, path="/chatgpt")
    assert result["status"] == "200 OK"
    assert "revisione bloccata".encode() in page.lower()
    assert b"<textarea readonly" not in page
    digest = re.search(rb'name="prompt_sha256" value="([a-f0-9]{64})"', page).group(1).decode()
    form = urlencode({"prompt_sha256": digest, "confirmation": "1"}).encode()
    result, page = _request(app, "POST", "/chatgpt/confirm", form, "application/x-www-form-urlencoded")
    assert result["status"] == "200 OK" and b"<textarea readonly" in page
    draft_head = re.search(rb'name="draft_prompt_sha256" value="([a-f0-9]{64})"', page).group(1).decode()
    captured["session"].documents["doc-001"]["document_family"] = "other"
    stale = urlencode({"draft_prompt_sha256": draft_head, "draft": "testo sintetico"}).encode()
    result, _ = _request(app, "POST", "/chatgpt/return", stale, "application/x-www-form-urlencoded")
    assert result["status"] == "409 Conflict"
    result, page = _request(app, path="/chatgpt")
    assert b"<textarea readonly" not in page
    result, _ = _request(app, "POST", "/chatgpt/confirm", form, "application/x-www-form-urlencoded")
    assert result["status"] == "409 Conflict"


def test_clearing_session_during_draft_save_does_not_crash_or_save(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    real = local_intake_app.create_expense_report_intake_session
    def create(*args, **kwargs): return real(*args, **kwargs)
    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", create)
    monkeypatch.setattr(local_intake_app, "build_chatgpt_handoff_prompt", lambda bundle, docs: "synthetic")
    app = create_expense_report_app(); _upload(app)
    _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
    page = _request(app, path="/chatgpt")[1]
    digest = re.search(rb'name="draft_prompt_sha256" value="([a-f0-9]{64})"', page).group(1).decode()
    entered, release = threading.Event(), threading.Event()
    original = local_intake_app._handoff_state
    def delayed(state):
        result = original(state); entered.set()
        if not release.wait(3): raise RuntimeError("test release timed out")
        return result
    form = urlencode({"draft_prompt_sha256": digest, "draft": "synthetic"}).encode()
    try:
        monkeypatch.setattr(local_intake_app, "_handoff_state", delayed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(_request, app, "POST", "/chatgpt/return", form, "application/x-www-form-urlencoded")
            assert entered.wait(2)
            assert _request(app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")[0]["status"] == "200 OK"
            release.set()
            assert future.result(timeout=3)[0]["status"] == "409 Conflict"
    finally: release.set()


def test_old_page_cannot_erase_new_draft(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    real = local_intake_app.create_expense_report_intake_session
    captured = {}
    def create(*args, **kwargs):
        session = real(*args, **kwargs); captured["session"] = session; return session
    monkeypatch.setattr(local_intake_app, "create_expense_report_intake_session", create)
    monkeypatch.setattr(local_intake_app, "build_chatgpt_handoff_prompt", lambda bundle, docs: "synthetic " + docs["doc-001"]["document_family"])
    app=create_expense_report_app(); _upload(app)
    _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
    entered, release = threading.Event(), threading.Event()
    original = local_intake_app._handoff_state
    old_thread = [None]
    def delayed(session):
        result=original(session)
        if threading.get_ident() == old_thread[0]:
            entered.set()
            if not release.wait(3): raise RuntimeError("test release timed out")
        return result
    def old_get():
        old_thread[0] = threading.get_ident()
        return _request(app, path="/chatgpt")
    try:
        monkeypatch.setattr(local_intake_app, "_handoff_state", delayed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            old = pool.submit(old_get); assert entered.wait(2)
            captured["session"].documents["doc-001"]["document_family"] = "other"
            def save_new():
                page = _request(app, path="/chatgpt")[1]
                digest = re.search(rb'name="draft_prompt_sha256" value="([a-f0-9]{64})"', page).group(1).decode()
                form = urlencode({"draft_prompt_sha256": digest, "draft": "synthetic draft"}).encode()
                return _request(app, "POST", "/chatgpt/return", form, "application/x-www-form-urlencoded")
            saved = pool.submit(save_new)
            release.set(); old.result(timeout=3)
            assert saved.result(timeout=3)[0]["status"] == "200 OK"
            assert b"synthetic draft" in _request(app, path="/chatgpt")[1]
    finally: release.set()


def test_slow_handoff_render_does_not_block_clear(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(local_intake_app, "build_chatgpt_handoff_prompt", lambda bundle, docs: "synthetic")
    app=create_expense_report_app(); _upload(app)
    _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
    entered, release=threading.Event(), threading.Event()
    original=local_intake_app._handoff_state
    def delayed(session):
        entered.set()
        if not release.wait(3): raise RuntimeError("test release timed out")
        return original(session)
    try:
        monkeypatch.setattr(local_intake_app, "_handoff_state", delayed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            page=pool.submit(_request, app, path="/chatgpt"); assert entered.wait(2)
            clear=pool.submit(_request, app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
            assert clear.result(timeout=1)[0]["status"] == "200 OK"
            release.set(); assert page.result(timeout=3)[0]["status"] == "409 Conflict"
    finally: release.set()
