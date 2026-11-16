"""«Apri documento originale» from the archive page after OCR2 restarts (R7).

The first instance saves a synthetic document; a new instance on the same
archive file (a new store object, a new app, no shared session) opens it from
the archive page and follows the link to the original document.
"""
from __future__ import annotations

from html import unescape
from io import BytesIO
import re
from urllib.parse import urlencode

import pytest

from alfa_document_intelligence.app_lifetime import AppLifetime, WindowPresence
from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import create_expense_report_app

from test_local_document_store import SyntheticProtector
from test_local_intake_app import NOTE, _multipart, _zip_bytes

HOST = "127.0.0.1:8080"
ORIGIN = "http://127.0.0.1:8080"


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _invoke(app, method, path, *, query="", body=b"", origin=ORIGIN, host=HOST,
            content_type="application/x-www-form-urlencoded"):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "HTTP_HOST": host}
    if method == "POST":
        if origin is not None:
            environ["HTTP_ORIGIN"] = origin
        environ.update(CONTENT_TYPE=content_type, CONTENT_LENGTH=str(len(body)), **{"wsgi.input": BytesIO(body)})
    response = {}
    payload = b"".join(app(environ, lambda status, headers: response.update(status=status, headers=dict(headers))))
    return response["status"], response["headers"], payload


def _new_app(archive_path, app_mode):
    store = LocalDocumentStore(archive_path, protector=SyntheticProtector())
    lifetime = AppLifetime(WindowPresence(_Clock()), lambda: None, poll_seconds=0.01) if app_mode else None
    return create_expense_report_app(archive_store=store, app_lifetime=lifetime), store


def _save_in_first_instance(archive_path, app_mode):
    app, store = _new_app(archive_path, app_mode)
    try:
        body, content_type = _multipart("synthetic.zip", _zip_bytes())
        assert _invoke(app, "POST", "/upload", body=body, content_type=content_type)[0].startswith("200")
        assignment = urlencode({"note_document_id": "doc-001"}).encode()
        assert _invoke(app, "POST", "/assign-note", body=assignment)[0].startswith("200")
        assert _invoke(app, "GET", "/reviews/doc-001")[0].startswith("200")
        status, _, page = _invoke(app, "POST", "/archive/save/doc-001")
        assert status.startswith("200"), page
        [match] = store.search("")
        return match.document_id
    finally:
        app.close()


def _original_link(page: bytes) -> str:
    match = re.search(rb'<a href="([^"]+)"[^>]*>Apri documento originale</a>', page)
    assert match is not None, "the archive page must offer the original document"
    return unescape(match.group(1).decode())


def _open_from_archive_page(app, document_id):
    status, _, listing = _invoke(app, "GET", "/archive")
    assert status.startswith("200")
    action = f'/archive/open/{document_id}'
    assert f'action="{action}"'.encode() in listing
    status, _, page = _invoke(app, "POST", action)
    assert status.startswith("200"), page
    assert b"Documento in archivio" in page
    return page


def _fetch(app, link):
    path, _, query = link.partition("?")
    return _invoke(app, "GET", path, query=query)


@pytest.mark.parametrize("app_mode", [False, True], ids=["browser", "app-window"])
def test_original_document_opens_from_archive_page_after_restart(tmp_path, app_mode):
    archive_path = tmp_path / "archive.sqlite3"
    document_id = _save_in_first_instance(archive_path, app_mode)

    app, _ = _new_app(archive_path, app_mode)  # a new OCR2 instance on the same archive
    try:
        page = _open_from_archive_page(app, document_id)
        status, headers, body = _fetch(app, _original_link(page))
        assert status.startswith("200"), body
        if app_mode:
            frame = re.search(rb'<iframe title="Documento originale" src="([^"]+)"', body)
            assert frame is not None
            status, headers, body = _fetch(app, unescape(frame.group(1).decode()))
            assert status.startswith("200"), body
        assert headers["Content-Type"] == "application/pdf"
        assert body == NOTE
        assert "sandbox" in headers["Content-Security-Policy"]
    finally:
        app.close()
