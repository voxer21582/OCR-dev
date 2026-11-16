"""Exit button, window heartbeat and information page in the local app (REQ-101, REQ-106)."""
from __future__ import annotations

from io import BytesIO
import platform
import re
import socket
import threading
import time
from urllib.parse import urlencode
import http.client

import pytest

import alfa_document_intelligence
from alfa_document_intelligence.app_lifetime import AppInfo, AppLifetime, WindowPresence
from alfa_document_intelligence.document_family_catalog import DocumentFamilyCatalogStore
from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import create_expense_report_app, serve_expense_report_local

from test_local_document_store import SyntheticProtector

HOST = "127.0.0.1:8080"
ORIGIN = "http://127.0.0.1:8080"


class _StopRecorder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def _invoke(app, method, path, *, query="", body=b"", origin=ORIGIN,
            content_type="application/x-www-form-urlencoded", host=HOST):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "HTTP_HOST": host}
    if method == "POST":
        if origin is not None:
            environ["HTTP_ORIGIN"] = origin
        environ.update(CONTENT_TYPE=content_type, CONTENT_LENGTH=str(len(body)), **{"wsgi.input": BytesIO(body)})
    response = {}
    payload = b"".join(app(environ, lambda status, headers: response.update(status=status, headers=dict(headers))))
    return response["status"], response["headers"], payload.decode("utf-8")


def _token(page: str) -> str:
    match = re.search(r'name="_ocr2_csrf" value="([A-Za-z0-9_-]+)"', page)
    assert match is not None
    return match.group(1)


@pytest.fixture
def lifetime():
    stop = _StopRecorder()
    presence = WindowPresence(_FakeClock())
    return AppLifetime(presence, stop, poll_seconds=0.01), stop


@pytest.fixture
def app_mode(tmp_path, lifetime):
    app_lifetime, stop = lifetime
    app = create_expense_report_app(
        archive_store=LocalDocumentStore(tmp_path / "archive.sqlite3", protector=SyntheticProtector()),
        family_catalog_store=DocumentFamilyCatalogStore(tmp_path / "family-catalog.json"),
        app_lifetime=app_lifetime,
    )
    yield app, app_lifetime, stop
    app.close()


def _assert_app_controls(page: str) -> None:
    assert '<form method="post" action="/app/exit">' in page
    assert '<button type="submit">Esci</button>' in page
    assert '<a href="/app/info">Informazioni</a>' in page
    assert "/app/heartbeat?w=" in page
    assert "sendBeacon('/app/closing'" in page
    exit_form = page[page.index('action="/app/exit"'):]
    assert 'name="_ocr2_csrf"' in exit_form.split("</form>", 1)[0]


def test_every_html_page_has_exit_button_and_heartbeat_in_app_mode(app_mode):
    app = app_mode[0]
    for path in ("/", "/archive", "/cases", "/catalog"):
        status, headers, page = _invoke(app, "GET", path)
        assert status.startswith("200"), path
        _assert_app_controls(page)
        controls = page.index('action="/app/exit"')
        if "</main>" in page:
            assert controls < page.rindex("</main>"), path
    # A 403 for a request that passed the Host and Origin checks (missing token on /app/exit).
    status, headers, page = _invoke(app, "POST", "/app/exit", body=b"x=1")
    assert status.startswith("403")
    _assert_app_controls(page)


def test_untrusted_request_pages_never_carry_the_token(app_mode):
    app, app_lifetime, stop = app_mode
    status, _, page = _invoke(app, "GET", "/", host="evil.example:8080")
    assert status.startswith("403")
    assert "_ocr2_csrf" not in page and "/app/exit" not in page and "<script" not in page
    status, _, page = _invoke(app, "POST", "/clear", body=b"clear=1", origin="https://untrusted.example")
    assert status.startswith("403")
    assert "_ocr2_csrf" not in page and "/app/exit" not in page and "<script" not in page
    app.close()
    status, _, page = _invoke(app, "GET", "/")
    assert status.startswith("503")
    assert "_ocr2_csrf" not in page and "/app/exit" not in page
    assert stop.calls == 0


def test_opaque_origin_exit_and_closing_need_the_token(app_mode):
    app, app_lifetime, stop = app_mode
    presence = app_lifetime.presence
    _, _, page = _invoke(app, "GET", "/")
    token = _token(page)
    presence._clock.now += 3  # past the navigation window after GET /
    _invoke(app, "GET", "/app/heartbeat", query="w=finestra")
    presence._clock.now += 3
    status, _, _ = _invoke(app, "POST", "/app/closing", body=b"w=finestra", origin="null")
    assert status.startswith("403")
    assert "finestra" in presence._last_beat
    status, _, _ = _invoke(app, "POST", "/app/closing", origin="null",
                           body=urlencode({"w": "finestra", "_ocr2_csrf": token}).encode())
    assert status.startswith("204")
    assert "finestra" not in presence._last_beat
    oversized = urlencode({"_ocr2_csrf": token, "pad": "x" * 5000}).encode()
    status, _, _ = _invoke(app, "POST", "/app/exit", body=oversized, origin="null")
    assert status.startswith("403")
    status, _, _ = _invoke(app, "POST", "/app/exit", body=b"x=1", origin="null")
    assert status.startswith("403")
    app_lifetime.start()
    time.sleep(0.1)
    assert stop.calls == 0
    status, _, page = _invoke(app, "POST", "/app/exit", body=urlencode({"_ocr2_csrf": token}).encode(), origin="null")
    assert status.startswith("200")
    assert "OCR2 si è chiuso." in page
    assert app_lifetime.stopped.wait(5)
    assert stop.calls == 1


def test_no_exit_button_without_app_mode(tmp_path):
    app = create_expense_report_app(
        archive_store=LocalDocumentStore(tmp_path / "archive.sqlite3", protector=SyntheticProtector()),
    )
    try:
        for path in ("/", "/archive", "/cases"):
            status, headers, page = _invoke(app, "GET", path)
            assert status.startswith("200")
            assert "/app/exit" not in page
            assert "/app/heartbeat" not in page
            assert "connect-src" not in headers["Content-Security-Policy"]
        for method, path in (("GET", "/app/heartbeat"), ("POST", "/app/exit"), ("POST", "/app/closing")):
            status, _, _ = _invoke(app, method, path, query="w=abc")
            assert status.startswith("404"), path
    finally:
        app.close()


def test_heartbeat_returns_204_and_marks_window(app_mode):
    app, app_lifetime, _ = app_mode
    presence = app_lifetime.presence
    status, _, body = _invoke(app, "GET", "/app/heartbeat", query="w=finestra_1")
    assert status.startswith("204")
    assert body == ""
    assert presence.should_stop() is False
    assert presence._last_beat.keys() == {"finestra_1"}
    for bad in ("", "w=", "w=" + "a" * 65, "w=a%2Fb", "w=a&w=b"):
        status, _, _ = _invoke(app, "GET", "/app/heartbeat", query=bad)
        assert status.startswith("400"), bad
    _, _, page = _invoke(app, "GET", "/")
    token = _token(page)
    presence._clock.now += 3  # past the navigation window after GET /
    status, _, _ = _invoke(app, "POST", "/app/closing", body=urlencode({"w": "finestra_1", "_ocr2_csrf": token}).encode())
    assert status.startswith("204")
    assert presence._last_beat == {}
    status, _, _ = _invoke(app, "POST", "/app/closing", body=urlencode({"w": "a/b", "_ocr2_csrf": token}).encode())
    assert status.startswith("400")
    status, _, _ = _invoke(app, "POST", "/app/closing", body=urlencode({"w": "finestra_2"}).encode())
    assert status.startswith("403")


def test_exit_requires_csrf(app_mode):
    app, app_lifetime, stop = app_mode
    app_lifetime.start()
    status, _, _ = _invoke(app, "POST", "/app/exit", body=b"x=1")
    assert status.startswith("403")
    status, _, _ = _invoke(app, "POST", "/app/exit", body=b"_ocr2_csrf=wrong")
    assert status.startswith("403")
    status, _, _ = _invoke(app, "POST", "/app/exit", body=b"x=1", origin=None)
    assert status.startswith("403")
    time.sleep(0.1)
    assert stop.calls == 0
    assert not app_lifetime.stopped.is_set()


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def test_exit_stops_server_after_response():
    holder: dict = {}
    app_lifetime = AppLifetime(WindowPresence(), lambda: holder["server"].shutdown(), poll_seconds=0.05)
    server = serve_expense_report_local(port=0, app_lifetime=app_lifetime)
    holder["server"] = server
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app_lifetime.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
        page = connection.getresponse().read().decode("utf-8")
        connection.close()
        body = urlencode({"_ocr2_csrf": _token(page)})
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("POST", "/app/exit", body=body, headers={
            "Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        response = connection.getresponse()
        exit_page = response.read().decode("utf-8")
        connection.close()
        assert response.status == 200
        assert "OCR2 si è chiuso. Puoi chiudere questa finestra." in exit_page
        assert app_lifetime.stopped.wait(5)
        thread.join(5)
        assert not thread.is_alive()
        server.server_close()
        deadline = time.monotonic() + 5
        while not _port_is_free(port):
            assert time.monotonic() < deadline, "port still in use"
            time.sleep(0.05)
    finally:
        if thread.is_alive():
            server.shutdown()
        server.server_close()
        server.ocr2_close()


def test_info_page_shows_version_python_and_engine(tmp_path):
    info = AppInfo(version="9.8.7", python_version="3.12.10", ocr_engine="rapidocr-v6",
                   runtime_status="verificato", instance_id='abc"<x>')
    stop = _StopRecorder()
    app = create_expense_report_app(app_lifetime=AppLifetime(WindowPresence(), stop), app_info=info)
    try:
        status, _, page = _invoke(app, "GET", "/app/info")
        assert status.startswith("200")
        assert "<title>Informazioni</title>" in page
        for text in ("Versione", "9.8.7", "Python", "3.12.10", "Motore OCR", "rapidocr-v6",
                     "Verifica del runtime", "verificato"):
            assert text in page
        assert '<meta name="ocr2-instance" content="abc&quot;&lt;x&gt;">' in page
        assert page.index('name="ocr2-instance"') < page.index("<main>")
    finally:
        app.close()
    plain = create_expense_report_app()
    try:
        status, _, page = _invoke(plain, "GET", "/app/info")
        assert status.startswith("200")
        assert alfa_document_intelligence.__version__ in page
        assert platform.python_version() in page
        assert "disattivato" in page
        assert "non verificato (avvio da sorgenti)" in page
        assert "/app/exit" not in page
    finally:
        plain.close()


def _script_start_tags(page):
    from html.parser import HTMLParser

    class ScriptParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.scripts = []

        def handle_starttag(self, tag, attrs):
            if tag == 'script':
                self.scripts.append(self.get_starttag_text())

    parser = ScriptParser()
    parser.feed(page)
    return parser.scripts


def test_script_respects_csp_nonce(app_mode):
    app = app_mode[0]
    status, headers, page = _invoke(app, "GET", "/")
    csp = headers["Content-Security-Policy"]
    nonce = re.search(r"script-src 'nonce-([^']+)'", csp).group(1)
    scripts = _script_start_tags(page)
    assert scripts
    assert all(f'nonce="{nonce}"' in tag for tag in scripts)
    assert "__CSP_NONCE__" not in page
    assert "connect-src 'self'" in csp


def test_script_tag_parser_handles_uppercase():
    assert _script_start_tags('<SCRIPT nonce="x"></SCRIPT>') == ['<SCRIPT nonce="x">']


def test_downloaded_html_does_not_include_session_controls_or_token(lifetime):
    from alfa_document_intelligence.local_intake_app import _page
    app_lifetime, _ = lifetime
    environ = {'_ocr2_app_lifetime': app_lifetime, '_ocr2_csrf_token': 'synthetic-session-token'}
    body = '<html><main><form method="post"></form></main></html>'
    headers = {}
    payload = b''.join(_page(environ, lambda status, fields: headers.update(dict(fields)), '200 OK', body,
                             download_filename='export.html')).decode('utf-8')
    assert payload == body
    assert 'synthetic-session-token' not in payload
    assert '/app/exit' not in payload
    assert headers['Content-Disposition'] == 'attachment; filename="export.html"'


def test_info_probe_does_not_revive_closed_window():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, 'GET', '/')
        _invoke(app, 'GET', '/app/heartbeat', query='w=finestra')
        clock.now += 3
        _invoke(app, 'POST', '/app/closing', body=urlencode({'w': 'finestra', '_ocr2_csrf': _token(page)}).encode())
        before = presence._last_activity
        clock.now += 2
        _invoke(app, 'GET', '/app/info', query='probe=1')
        assert presence._last_activity == before
        clock.now += 8
        assert presence.should_stop()
    finally:
        app.close()


def test_info_probe_before_closing_does_not_look_like_navigation():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, 'GET', '/')
        _invoke(app, 'GET', '/app/heartbeat', query='w=finestra')
        clock.now += 30
        _invoke(app, 'GET', '/app/info', query='probe=1')
        clock.now += 1
        _invoke(app, 'POST', '/app/closing', body=urlencode({'w': 'finestra', '_ocr2_csrf': _token(page)}).encode())
        clock.now += 10
        assert presence.should_stop()
    finally:
        app.close()


def test_navigating_to_info_keeps_window_alive():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, 'GET', '/')
        _invoke(app, 'GET', '/app/heartbeat', query='w=finestra')
        clock.now += 30
        _invoke(app, 'GET', '/app/info')
        clock.now += 1
        _invoke(app, 'POST', '/app/closing', body=urlencode({'w': 'finestra', '_ocr2_csrf': _token(page)}).encode())
        clock.now += 30
        assert not presence.should_stop()
    finally:
        app.close()


def test_original_document_in_app_mode_keeps_heartbeat_and_raw_response(app_mode):
    from test_local_intake_app import NOTE, _multipart, _zip_bytes
    app, _, _ = app_mode
    body, content_type = _multipart('synthetic.zip', _zip_bytes())
    status, _, _ = _invoke(app, 'POST', '/upload', body=body, content_type=content_type)
    assert status.startswith('200')
    status, _, _ = _invoke(app, 'POST', '/assign-note', body=urlencode({'note_document_id': 'doc-001'}).encode())
    assert status.startswith('200')
    status, headers, page = _invoke(app, 'GET', '/reviews/doc-001/source')
    assert status.startswith('200')
    assert '<iframe' in page and '/reviews/doc-001/source?raw=1' in page
    assert 'width: 100%' in page and 'height: 75vh' in page
    assert '/app/heartbeat' in page
    assert "frame-src 'self'" in headers['Content-Security-Policy']
    status, headers, raw = _invoke(app, 'GET', '/reviews/doc-001/source', query='raw=1')
    assert status.startswith('200') and headers['Content-Type'] == 'application/pdf'
    assert raw.encode() == NOTE
    assert "sandbox" in headers['Content-Security-Policy']


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_request_after_closing_beacon_keeps_window_alive():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, "GET", "/")
        token = _token(page)
        status, _, _ = _invoke(app, "GET", "/app/heartbeat", query="w=finestra")
        assert status.startswith("204")
        clock.now += 3  # past the navigation window after GET /
        status, _, _ = _invoke(app, "POST", "/app/closing",
                               body=urlencode({"w": "finestra", "_ocr2_csrf": token}).encode())
        assert status.startswith("204")
        clock.now += 1
        status, headers, _ = _invoke(app, "GET", "/risorsa-inesistente")
        assert status.startswith("404")
        assert headers["Content-Type"].startswith("text/plain")
        clock.now += 30
        assert presence.should_stop() is False
        clock.now += 160
        assert presence.should_stop() is True
    finally:
        app.close()


def test_closing_beacon_does_not_restore_its_own_window():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, "GET", "/")
        token = _token(page)
        _invoke(app, "GET", "/app/heartbeat", query="w=finestra")
        clock.now += 3  # past the navigation window after GET /
        _invoke(app, "POST", "/app/closing", body=urlencode({"w": "finestra", "_ocr2_csrf": token}).encode())
        clock.now += 10
        assert presence.should_stop() is True
    finally:
        app.close()


def test_closing_right_after_a_non_html_request_counts_as_navigation():
    clock = _FakeClock()
    presence = WindowPresence(clock)
    app = create_expense_report_app(app_lifetime=AppLifetime(presence, _StopRecorder()))
    try:
        _, _, page = _invoke(app, "GET", "/")
        token = _token(page)
        _invoke(app, "GET", "/app/heartbeat", query="w=finestra")
        clock.now += 30
        status, headers, _ = _invoke(app, "GET", "/risorsa-inesistente")
        assert status.startswith("404")
        assert headers["Content-Type"].startswith("text/plain")
        clock.now += 1.5
        status, _, _ = _invoke(app, "POST", "/app/closing",
                               body=urlencode({"w": "finestra", "_ocr2_csrf": token}).encode())
        assert status.startswith("204")
        clock.now += 30
        assert presence.should_stop() is False
        clock.now += 151
        assert presence.should_stop() is True
    finally:
        app.close()


def test_every_request_counts_as_activity(app_mode):
    app, app_lifetime, _ = app_mode
    presence = app_lifetime.presence
    assert presence._last_activity is None
    _invoke(app, "GET", "/")
    assert presence._last_activity is not None
