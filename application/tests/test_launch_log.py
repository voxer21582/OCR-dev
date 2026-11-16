"""Launch log of the app window: %LOCALAPPDATA%\\OCR2\\logs\\launcher.log (owner decision 2026-11-16).

Every test points LOCALAPPDATA at a temporary folder: the real profile is never touched.
"""
from __future__ import annotations

import builtins
import os
from pathlib import Path
import re
import sys
import types

import pytest

import alfa_document_intelligence.__main__ as launcher

HINT = "Dettagli in %LOCALAPPDATA%\\OCR2\\logs\\launcher.log"
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@pytest.fixture
def local_app_data(tmp_path, monkeypatch):
    root = tmp_path / "LocalAppData"
    root.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(root))
    return root


def _log(root: Path) -> Path:
    return root / "OCR2" / "logs" / "launcher.log"


def _dialogs(monkeypatch):
    shown = []
    monkeypatch.setattr(launcher, "_show_startup_error", shown.append)
    return shown


def test_unexpected_error_is_logged_with_type_and_traceback(local_app_data, monkeypatch):
    shown = _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError):
        launcher._run_entrypoint(["--app-window"])
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert TIMESTAMP.search(text)
    assert "eccezione" in text
    assert "RuntimeError" in text and "synthetic failure" in text
    assert "Traceback" in text
    assert len(shown) == 1 and "synthetic failure" not in shown[0]


def test_failed_exit_is_logged_with_code_and_console_messages(local_app_data, monkeypatch):
    _dialogs(monkeypatch)

    def failed(argv):
        print("synthetic reason on stderr", file=sys.stderr)
        raise SystemExit(1)

    monkeypatch.setattr(launcher, "main", failed)
    monkeypatch.setattr(sys, "stderr", None)  # pythonw has no console
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(["--app-window"])
    assert sys.stderr is None
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert TIMESTAMP.search(text)
    assert "uscita" in text and "1" in text
    assert "synthetic reason on stderr" in text
    assert "SystemExit" in text


def test_integrity_failure_is_logged_once(local_app_data, monkeypatch, tmp_path):
    install = tmp_path / "install"
    install.mkdir()
    (install / "runtime-manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "_installation_root", lambda: install)
    notices = []

    def integrity_dialog(message):
        notices.append(message)
        launcher._startup_error_shown = True  # as the real dialog does

    monkeypatch.setattr(launcher, "_show_integrity_error", integrity_dialog)
    monkeypatch.setattr(launcher, "_show_startup_error", lambda message: pytest.fail("no second dialog"))
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(["--app-window"])
    assert len(notices) == 1
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert "integrità" in text and "Installazione non valida" in text
    assert text.count("=== ") == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher archive")
def test_newer_archive_is_logged(local_app_data, monkeypatch):
    import sqlite3
    from alfa_document_intelligence.local_document_store import _SCHEMA_VERSION
    archive = local_app_data / "OCR2" / "document-archive.sqlite3"
    archive.parent.mkdir()
    with sqlite3.connect(archive) as db:
        db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION + 1}")
    dialogs = []

    def dialog(message, title):
        dialogs.append(message)
        launcher._startup_error_shown = True  # as the real dialog does

    monkeypatch.setattr(launcher, "_show_error_dialog", dialog)
    monkeypatch.setattr(launcher, "_show_startup_error", lambda message: pytest.fail("no second dialog"))
    monkeypatch.setattr(launcher, "serve_expense_report_local", lambda **kwargs: pytest.fail("server must not start"))
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(["--app-window"])
    assert len(dialogs) == 1
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert "archivio più recente" in text and "versione più recente" in text
    assert text.count("=== ") == 1


def test_clean_start_and_clean_exit_write_no_log(local_app_data, monkeypatch):
    _dialogs(monkeypatch)
    monkeypatch.setattr(launcher, "main", lambda argv: None)
    launcher._run_entrypoint(["--app-window"])

    def clean_exit(argv):
        raise SystemExit(0)

    monkeypatch.setattr(launcher, "main", clean_exit)
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(["--app-window"])
    assert not (local_app_data / "OCR2").exists()


def test_console_mode_writes_no_log(local_app_data, monkeypatch):
    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError):
        launcher._run_entrypoint([])
    assert not (local_app_data / "OCR2").exists()


@pytest.mark.parametrize("value", [None, "", "relative-folder"])
def test_missing_or_relative_local_app_data_skips_the_log(value, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    if value is None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.setenv("LOCALAPPDATA", value)
    shown = _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        launcher._run_entrypoint(["--app-window"])
    assert len(shown) == 1
    assert list(tmp_path.iterdir()) == []


def test_unwritable_log_never_raises_and_dialog_still_shows(local_app_data, monkeypatch):
    (local_app_data / "OCR2").mkdir()
    (local_app_data / "OCR2" / "logs").write_text("not a folder", encoding="utf-8")
    shown = _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        launcher._run_entrypoint(["--app-window"])
    assert len(shown) == 1
    launcher._write_launch_log("eccezione", "direct call")  # returns quietly


def test_log_rotates_to_one_backup_above_the_limit(local_app_data, monkeypatch):
    log = _log(local_app_data)
    log.parent.mkdir(parents=True)
    old = "old entry\n" * (launcher._LAUNCH_LOG_LIMIT_BYTES // 10)
    log.write_text(old, encoding="utf-8")
    (log.parent / "launcher.log.1").write_text("older backup\n", encoding="utf-8")
    _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError):
        launcher._run_entrypoint(["--app-window"])
    backup = log.parent / "launcher.log.1"
    assert backup.read_text(encoding="utf-8") == old
    assert "synthetic failure" in log.read_text(encoding="utf-8")
    assert log.stat().st_size < launcher._LAUNCH_LOG_LIMIT_BYTES
    assert sorted(path.name for path in log.parent.iterdir()) == ["launcher.log", "launcher.log.1"]


def test_one_huge_entry_stays_within_the_limit(local_app_data):
    launcher._write_launch_log("integrità", "File mancante: x; " * 100_000)
    assert 0 < _log(local_app_data).stat().st_size <= launcher._LAUNCH_LOG_LIMIT_BYTES


def test_dialog_names_the_log_without_expanding_the_variable(local_app_data, monkeypatch):
    calls = []
    fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(
        user32=types.SimpleNamespace(MessageBoxW=lambda *args: calls.append(args))))
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(launcher.os, "name", "nt")
    launcher._show_startup_error(launcher._START_FAILURE_MESSAGE)
    launcher._show_integrity_error("Installazione non valida: sintetica.")
    for _, text, _, _ in calls:
        assert HINT in text
        assert str(local_app_data) not in text
    assert not (local_app_data / "OCR2").exists(), "the dialog itself writes nothing"


def test_bootstrap_import_failure_is_logged_and_names_the_log(local_app_data, monkeypatch):
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    real_import = builtins.__import__
    messages = []
    fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(
        user32=types.SimpleNamespace(MessageBoxW=lambda *args: messages.append(args))))

    def intercept(name, *args, **kwargs):
        if name == "app_instance":
            raise ImportError("synthetic missing module")
        if name == "ctypes":
            return fake_ctypes
        return real_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", intercept)
        patch.setattr(os, "name", "nt")
        patch.setattr(sys, "argv", ["ocr2", "--app-window"])
        with pytest.raises(ImportError):
            exec(compile(source, launcher.__file__, "exec"),
                 {"__name__": "synthetic_bootstrap", "__package__": "alfa_document_intelligence"})
    assert len(messages) == 1 and HINT in messages[0][1]
    assert "synthetic missing module" not in messages[0][1]
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert "import" in text and "ImportError" in text and "synthetic missing module" in text


def test_truncated_entry_keeps_the_head_and_the_final_exception_line(local_app_data):
    try:
        raise ValueError("final synthetic line")
    except ValueError as exc:
        launcher._write_launch_log("eccezione", "x" * 200_000, exc)
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) <= launcher._LAUNCH_LOG_ENTRY_BYTES
    assert "eccezione" in text.splitlines()[0]
    assert "[…troncato]" in text
    assert text.rstrip().endswith("ValueError: final synthetic line")


@pytest.mark.parametrize("console", [False, True], ids=["pythonw", "console"])
def test_requests_after_start_up_never_reach_the_log(local_app_data, monkeypatch, console):
    """The stderr capture covers start-up only: request lines carry search terms and ids."""
    import io
    import threading
    import urllib.request
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    _dialogs(monkeypatch)
    original = io.StringIO() if console else None
    monkeypatch.setattr(sys, "stderr", original)

    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    class Handler(WSGIRequestHandler):
        def handle(self):
            try:
                super().handle()
            except AttributeError:
                pass  # pythonw: sys.stderr is None, as before the capture existed

    def started_then_failed(argv):
        print("synthetic start-up warning", file=sys.stderr)
        server = make_server("127.0.0.1", 0, app, handler_class=Handler)
        launcher._end_startup_capture()
        assert sys.stderr is original  # under pythonw: None again, unchanged behaviour
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        port = server.server_address[1]
        urllib.request.urlopen(f"http://127.0.0.1:{port}/archive?q=Mario+Rossi+IBAN").read()
        thread.join(10)
        server.server_close()
        print("after start-up: tag Riservato", file=sys.stderr) if sys.stderr is not None else None
        raise SystemExit(1)

    monkeypatch.setattr(launcher, "main", started_then_failed)
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(["--app-window"])
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert "uscita anomala" in text
    for secret in ("Mario", "IBAN", "/archive", "Riservato", "synthetic start-up warning"):
        assert secret not in text
    if console:
        assert "Mario+Rossi+IBAN" in original.getvalue()  # the console still sees requests


def test_server_ends_the_start_up_capture_right_before_serving():
    import inspect

    source = inspect.getsource(launcher._serve)
    assert source.count("_end_startup_capture()") == 1
    assert source.index("_end_startup_capture()") < source.index("server.serve_forever()")
    assert source.index("app_lifetime.start()") < source.index("_end_startup_capture()")
