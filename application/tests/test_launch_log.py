"""Launch log of the app window: %LOCALAPPDATA%\\OCR2\\logs\\launcher-safe.log (DEC-035).

Every test points LOCALAPPDATA at a temporary folder: the real profile is never touched.
"""
from __future__ import annotations

import builtins
from enum import IntEnum
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types

import pytest

import alfa_document_intelligence.__main__ as launcher

HINT = "Dettagli in %LOCALAPPDATA%\\OCR2\\logs\\launcher-safe.log"
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@pytest.mark.parametrize('window', [False, True])
def test_cli_unexpected_exception_never_prints_private_traceback(tmp_path, window):
    script = '''
import sys
from alfa_document_intelligence import __main__ as launcher
def failed(argv):
    raise RuntimeError("SYNTHETIC_PRIVATE_PATH_AND_DOCUMENT")
launcher.main = failed
launcher._show_startup_error = lambda message: None
sys.argv = ["ocr2"] + (["--app-window"] if sys.argv[1] == "window" else [])
launcher._cli_entrypoint()
'''
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    result = subprocess.run([sys.executable, '-B', '-c', script, 'window' if window else 'console'],
                            env=environment, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 1
    assert 'OCR2_UNEXPECTED_ERROR' in result.stderr
    assert 'SYNTHETIC_PRIVATE_PATH_AND_DOCUMENT' not in result.stderr + result.stdout
    assert 'Traceback' not in result.stderr
    log = tmp_path / 'OCR2' / 'logs' / 'launcher-safe.log'
    if window:
        assert 'OCR2_START_EXCEPTION' in log.read_text(encoding='utf-8')
        assert 'SYNTHETIC_PRIVATE_PATH_AND_DOCUMENT' not in log.read_text(encoding='utf-8')


def test_cli_redacts_non_numeric_exit_message(tmp_path):
    script = '''
from alfa_document_intelligence import __main__ as launcher
def failed():
    raise SystemExit("SYNTHETIC_PRIVATE_EXIT")
launcher._run_entrypoint = failed
launcher._cli_entrypoint()
'''
    result = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True,
                            text=True, timeout=20, check=False)
    assert result.returncode == 1
    assert 'SYNTHETIC_PRIVATE_EXIT' not in result.stderr + result.stdout
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('window', [False, True])
def test_executed_bootstrap_redacts_application_import_failure(tmp_path, window):
    script = '''
import builtins, sys, types
from pathlib import Path
source = Path(sys.argv[1]).read_text(encoding="utf-8")
window = sys.argv[2] == "window"
sys.argv = ["ocr2"] + (["--app-window"] if window else [])
original = builtins.__import__
def intercept(name, *args, **kwargs):
    if name == "app_instance":
        raise ImportError("SYNTHETIC_PRIVATE_BOOTSTRAP_PATH")
    if name == "ctypes" and window:
        return types.SimpleNamespace(windll=types.SimpleNamespace(user32=types.SimpleNamespace(MessageBoxW=lambda *a: 0)))
    return original(name, *args, **kwargs)
builtins.__import__ = intercept
exec(compile(source, "synthetic_launcher", "exec"), {"__name__": "__main__", "__package__": "alfa_document_intelligence"})
'''
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    result = subprocess.run([sys.executable, '-B', '-c', script, launcher.__file__,
                             'window' if window else 'console'], env=env,
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 1
    assert 'OCR2_START_IMPORT' in result.stderr
    assert 'SYNTHETIC_PRIVATE_BOOTSTRAP_PATH' not in result.stdout + result.stderr
    assert 'Traceback' not in result.stderr


def test_python_module_entrypoint_redacts_bootstrap_import_failure(tmp_path):
    source_package = Path(launcher.__file__).parent
    copied_package = tmp_path / 'alfa_document_intelligence'
    shutil.copytree(source_package, copied_package, ignore=shutil.ignore_patterns('__pycache__'))
    (copied_package / 'app_instance.py').write_text(
        'raise ImportError("SYNTHETIC_PRIVATE_BOOTSTRAP_PATH")\n', encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    result = subprocess.run([sys.executable, '-B', '-m', 'alfa_document_intelligence'],
                            cwd=str(tmp_path), env=env, capture_output=True, text=True,
                            timeout=20, check=False)
    assert result.returncode == 1
    assert 'OCR2_START_IMPORT' in result.stderr
    assert 'SYNTHETIC_PRIVATE_BOOTSTRAP_PATH' not in result.stderr + result.stdout
    assert 'Traceback' not in result.stderr
    imported = subprocess.run([sys.executable, '-B', '-c', 'import alfa_document_intelligence.__main__'],
                              cwd=str(tmp_path), env=env, capture_output=True, text=True,
                              timeout=20, check=False)
    assert imported.returncode != 0
    assert 'SYNTHETIC_PRIVATE_BOOTSTRAP_PATH' in imported.stderr


class _ExitEnum(IntEnum):
    OK = 0
    FAILED = 3


class _ExitInt(int):
    def __eq__(self, other):
        raise RuntimeError('synthetic comparison must not run')
    def __int__(self):
        raise RuntimeError('synthetic conversion must not run')


@pytest.mark.parametrize('exit_code, expected', [(None, 0), (0, 0), (1, 1), (False, 0), (True, 1),
                                                (_ExitEnum.OK, 0), (_ExitEnum.FAILED, 3), (_ExitInt(0), 0)])
def test_cli_preserves_numeric_exit_status(exit_code, expected, monkeypatch):
    def exit_now():
        raise SystemExit(exit_code)
    monkeypatch.setattr(launcher, '_run_entrypoint', exit_now)
    with pytest.raises(SystemExit) as caught:
        launcher._cli_entrypoint()
    assert (0 if caught.value.code is None else int(caught.value.code)) == expected


@pytest.mark.parametrize('source', ['argument', 'runtime'])
def test_cli_does_not_echo_untrusted_startup_detail(tmp_path, source):
    script = '''
import sys
from types import SimpleNamespace
from alfa_document_intelligence import __main__ as launcher
if sys.argv[1] == 'argument':
    sys.argv = ['ocr2', '--ocr-engine', 'SYNTHETIC_PRIVATE_ARGUMENT']
else:
    launcher._runtime_check = lambda manifest: SimpleNamespace(
        problems=('SYNTHETIC_PRIVATE_RUNTIME_PATH',), warnings=(), ok=False)
    sys.argv = ['ocr2', '--ocr-engine', 'rapidocr-v6']
launcher._cli_entrypoint()
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, source], capture_output=True,
                            text=True, timeout=20, check=False)
    assert result.returncode == 2
    assert 'OCR2_' in result.stderr
    assert 'SYNTHETIC_PRIVATE_' not in result.stderr + result.stdout


@pytest.fixture
def local_app_data(tmp_path, monkeypatch):
    root = tmp_path / "LocalAppData"
    root.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(root))
    return root


def _log(root: Path) -> Path:
    return root / "OCR2" / "logs" / "launcher-safe.log"


def _dialogs(monkeypatch):
    shown = []
    monkeypatch.setattr(launcher, "_show_startup_error", shown.append)
    return shown


def test_new_log_preserves_both_legacy_files(local_app_data):
    folder = local_app_data / 'OCR2' / 'logs'
    folder.mkdir(parents=True)
    old = folder / 'launcher.log'
    backup = folder / 'launcher.log.1'
    old.write_bytes(b'LEGACY_SYNTHETIC' * 20000)
    backup.write_bytes(b'LEGACY_BACKUP_SYNTHETIC')
    safe = folder / 'launcher-safe.log'
    safe.write_bytes(b'SAFE_SYNTHETIC' * 20000)
    original = old.read_bytes(), backup.read_bytes()
    launcher._write_launch_log('eccezione', 'SYNTHETIC_SECRET')
    assert (old.read_bytes(), backup.read_bytes()) == original
    assert (folder / 'launcher-safe.log.1').read_bytes() == b'SAFE_SYNTHETIC' * 20000
    assert 'OCR2_START_EXCEPTION' in safe.read_text(encoding='utf-8')


def test_launch_log_records_only_safe_stable_code(local_app_data):
    try:
        raise ValueError('SYNTHETIC_DOCUMENT_921 C:\\private\\statement.pdf')
    except ValueError as exc:
        launcher._write_launch_log('eccezione', 'SYNTHETIC_IDENTIFIER_718', exc)
    text = _log(local_app_data).read_text(encoding='utf-8')
    assert 'OCR2_START_EXCEPTION' in text
    for private in ('SYNTHETIC_DOCUMENT_921', 'SYNTHETIC_IDENTIFIER_718', 'statement.pdf', 'Traceback'):
        assert private not in text


def test_unknown_log_kind_cannot_inject_content(local_app_data):
    launcher._write_launch_log('SYNTHETIC_PERSON_512', 'SYNTHETIC_DOCUMENT_921')
    text = _log(local_app_data).read_text(encoding='utf-8')
    assert 'OCR2_START_OTHER' in text
    assert 'SYNTHETIC_PERSON_512' not in text and 'SYNTHETIC_DOCUMENT_921' not in text


def test_unexpected_error_is_logged_without_message_or_traceback(local_app_data, monkeypatch):
    shown = _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError):
        launcher._run_entrypoint(["--app-window"])
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert TIMESTAMP.search(text)
    assert "OCR2_START_EXCEPTION" in text
    assert "synthetic failure" not in text and "Traceback" not in text
    assert len(shown) == 1 and "synthetic failure" not in shown[0]


def test_failed_exit_is_logged_without_console_messages(local_app_data, monkeypatch):
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
    assert "OCR2_START_EXIT" in text
    assert "synthetic reason on stderr" not in text


def test_window_exit_does_not_format_untrusted_exit_object(local_app_data, monkeypatch):
    shown = _dialogs(monkeypatch)
    class ExitValue:
        @property
        def __class__(self):
            return int
        def __repr__(self):
            raise RuntimeError("SYNTHETIC_PRIVATE_REPR")
        def __eq__(self, other):
            raise RuntimeError("SYNTHETIC_PRIVATE_COMPARISON")
    def failed(argv):
        raise SystemExit(ExitValue())
    monkeypatch.setattr(launcher, 'main', failed)
    with pytest.raises(SystemExit):
        launcher._run_entrypoint(['--app-window'])
    assert len(shown) == 1
    assert 'OCR2_START_EXIT' in _log(local_app_data).read_text(encoding='utf-8')


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
    assert "OCR2_START_INTEGRITY" in text and "Installazione non valida" not in text
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
    assert "OCR2_START_ARCHIVE_VERSION" in text and "versione più recente" not in text
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
    (log.parent / "launcher-safe.log.1").write_text("older backup\n", encoding="utf-8")
    _dialogs(monkeypatch)

    def failed(argv):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(launcher, "main", failed)
    with pytest.raises(RuntimeError):
        launcher._run_entrypoint(["--app-window"])
    backup = log.parent / "launcher-safe.log.1"
    assert backup.read_text(encoding="utf-8") == old
    assert "OCR2_START_EXCEPTION" in log.read_text(encoding="utf-8")
    assert log.stat().st_size < launcher._LAUNCH_LOG_LIMIT_BYTES
    assert sorted(path.name for path in log.parent.iterdir()) == ["launcher-safe.log", "launcher-safe.log.1"]


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
    assert "OCR2_START_IMPORT" in text and "synthetic missing module" not in text


def test_large_sensitive_entry_is_not_written(local_app_data):
    try:
        raise ValueError("final synthetic line")
    except ValueError as exc:
        launcher._write_launch_log("eccezione", "x" * 200_000, exc)
    text = _log(local_app_data).read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) <= launcher._LAUNCH_LOG_ENTRY_BYTES
    assert "OCR2_START_EXCEPTION" in text
    assert "final synthetic line" not in text and "x" * 100 not in text


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
    assert "OCR2_START_EXIT" in text
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
