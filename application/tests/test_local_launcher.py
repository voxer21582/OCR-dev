import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest

from alfa_document_intelligence import app_instance
import alfa_document_intelligence.__main__ as launcher


class _FakeServer:
    server_address = ("127.0.0.1", 8765)

    def __init__(self):
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


@pytest.mark.skipif(os.name != 'nt', reason='Windows launcher archive')
def test_newer_archive_stops_with_clear_message_and_without_writing(tmp_path, monkeypatch, capsys):
    import hashlib
    import sqlite3
    from alfa_document_intelligence.local_document_store import _SCHEMA_VERSION
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    archive = tmp_path / 'OCR2' / 'document-archive.sqlite3'
    archive.parent.mkdir()
    with sqlite3.connect(archive) as db:
        db.execute(f'PRAGMA user_version = {_SCHEMA_VERSION + 1}')
    before = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(launcher, 'serve_expense_report_local', lambda **kwargs: pytest.fail('server must not start'))
    with pytest.raises(SystemExit):
        launcher.main(['--port', '0'])
    assert 'versione più recente' in capsys.readouterr().err
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == before


@pytest.mark.skipif(os.name != 'nt', reason='Windows launcher archive')
def test_headless_launcher_refuses_running_instance(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    held = app_instance.acquire(tmp_path / 'OCR2')
    assert held is not None
    monkeypatch.setattr(launcher, 'serve_expense_report_local', lambda **kwargs: pytest.fail('server must not start'))
    try:
        with pytest.raises(SystemExit):
            launcher.main(['--port', '0'])
    finally:
        held.release()


def test_launcher_serves_on_configured_port_and_closes_cleanly(monkeypatch, capsys, tmp_path):
    # Keep the Windows archive inside a temporary folder, never the real profile.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    server = _FakeServer()
    calls = []

    def fake_serve(*, port, **_services):
        calls.append(port)
        return server

    monkeypatch.setattr(launcher, "serve_expense_report_local", fake_serve)

    launcher.main(["--port", "8765"])

    assert calls == [8765]
    assert server.served and server.closed
    output = capsys.readouterr().out
    assert "http://127.0.0.1:8765/" in output
    assert "loopback" in output
    assert "OCR resta disattivato" in output


@pytest.mark.parametrize("value", ["-1", "65536", "not-a-port"])
def test_launcher_rejects_invalid_port(value):
    with pytest.raises(SystemExit):
        launcher.main(["--port", value])



def test_launcher_serves_real_loopback_http_request_and_stops(tmp_path):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(tmp_path)
    process = subprocess.Popen(
        [sys.executable, "-m", "alfa_document_intelligence", "--port", str(port)],
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    response = None
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _stdout, stderr = process.communicate(timeout=1)
                raise AssertionError(f"local launcher exited early: {stderr}")
            try:
                response = urlopen(f"http://127.0.0.1:{port}/", timeout=0.5)
                break
            except (URLError, TimeoutError):
                time.sleep(0.05)
        assert response is not None, "local launcher did not accept loopback HTTP"
        with response:
            assert response.status == 200
            assert response.headers.get("Cache-Control") == "no-store"
            assert b"Carica nota spese" in response.read()
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def _app_window_environment(monkeypatch, tmp_path):
    """--app-window with a temporary LOCALAPPDATA and a fake window opener (never a real Edge)."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher, "_APP_WINDOW_AVAILABLE", True)
    opened = []
    monkeypatch.setattr(launcher, "open_window", lambda url, data_dir: opened.append((url, data_dir)) or "edge")
    lifetimes = []
    real_lifetime = launcher.AppLifetime

    def recording_lifetime(*args, **kwargs):
        lifetime = real_lifetime(*args, **kwargs)
        lifetimes.append(lifetime)
        return lifetime

    monkeypatch.setattr(launcher, "AppLifetime", recording_lifetime)
    served = []
    real_serve = launcher.serve_expense_report_local

    def recording_serve(**kwargs):
        served.append(kwargs)
        server = real_serve(**kwargs)
        closes = []
        original_close = server.ocr2_close

        def close():
            closes.append(True)
            original_close()

        server.ocr2_close = close
        server.test_closes = closes
        return server

    monkeypatch.setattr(launcher, "serve_expense_report_local", recording_serve)
    return opened, lifetimes, served


def _run_main_in_thread(argv):
    errors = []

    def run():
        try:
            launcher.main(argv)
        except BaseException as exc:  # pragma: no cover - surfaced by the assertions
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def _start_first_instance(tmp_path):
    thread, errors = _run_main_in_thread(["--app-window"])
    data_dir = tmp_path / "OCR2"
    deadline = time.monotonic() + 15
    port = None
    while time.monotonic() < deadline and port is None and thread.is_alive():
        port = app_instance.running_instance(data_dir, timeout=0.5)
        if port is None:
            time.sleep(0.05)
    assert not errors, errors
    assert port is not None, "first --app-window instance did not publish itself"
    return thread, data_dir, port, errors


def _port_is_free(port):
    probe = socket.socket()
    try:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0
    except OSError:
        return False
    finally:
        probe.close()


def test_port_check_reports_no_listener_even_when_rebind_is_unavailable(monkeypatch):
    class Probe:
        def bind(self, address):
            raise OSError('synthetic TIME_WAIT')
        def connect_ex(self, address):
            return 1
        def settimeout(self, timeout):
            pass
        def close(self):
            pass
    monkeypatch.setattr(socket, 'socket', lambda: Probe())
    assert _port_is_free(12345)


def test_launcher_app_window_reuses_running_instance(monkeypatch, tmp_path):
    opened, lifetimes, served = _app_window_environment(monkeypatch, tmp_path)
    thread, data_dir, port, errors = _start_first_instance(tmp_path)
    try:
        assert len(served) == 1
        assert served[0]["port"] == 0
        assert served[0]["app_lifetime"] is lifetimes[0]
        assert served[0]["app_info"].instance_id
        assert opened == [(f"http://127.0.0.1:{port}/", data_dir)]

        launcher.main(["--app-window"])  # returns normally: exit code 0

        assert len(served) == 1, "the second launch must not create a server"
        assert opened == [(f"http://127.0.0.1:{port}/", data_dir)] * 2
    finally:
        lifetimes[0].request_exit()
        thread.join(15)
    assert not thread.is_alive() and not errors


def test_launcher_app_window_stops_when_lifetime_requests_exit(monkeypatch, tmp_path):
    _opened, lifetimes, served = _app_window_environment(monkeypatch, tmp_path)
    thread, data_dir, port, errors = _start_first_instance(tmp_path)
    assert (data_dir / "instance.json").exists()

    lifetimes[0].request_exit()
    thread.join(15)

    assert not thread.is_alive(), "launcher did not stop after the exit request"
    assert not errors, errors
    assert lifetimes[0].stopped.is_set()
    assert served[0]["app_info"] is not None
    assert _port_is_free(port)
    assert not (data_dir / "instance.json").exists()
    assert app_instance.running_instance(data_dir, timeout=0.5) is None
    lock = app_instance.acquire(data_dir)
    assert lock is not None, "the instance lock must be released"
    lock.release()


def test_launcher_app_window_respects_explicit_port(monkeypatch, tmp_path):
    _app_window_environment(monkeypatch, tmp_path)
    ports = []
    server = _FakeServer()
    server.shutdown = lambda: None

    def fake_serve(*, port, **_services):
        ports.append(port)
        return server

    monkeypatch.setattr(launcher, "serve_expense_report_local", fake_serve)
    launcher.main(["--app-window", "--port", "8765"])
    assert ports == [8765]
    assert server.closed
    lock = app_instance.acquire(tmp_path / "OCR2")
    assert lock is not None
    lock.release()


def test_launcher_app_window_reports_browser_fallback(monkeypatch, capsys, tmp_path):
    _app_window_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(launcher, "open_window", lambda url, data_dir: "browser")
    server = _FakeServer()
    server.shutdown = lambda: None
    monkeypatch.setattr(launcher, "serve_expense_report_local", lambda **_kwargs: server)
    launcher.main(["--app-window"])
    assert "Edge non trovato: OCR2 si apre nel browser predefinito." in capsys.readouterr().err


def test_launcher_app_window_requires_windows(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher, "_APP_WINDOW_AVAILABLE", False)
    with pytest.raises(SystemExit) as raised:
        launcher.main(["--app-window"])
    assert raised.value.code == 2
    assert "La finestra dell'app è disponibile solo su Windows" in capsys.readouterr().err
    assert not (tmp_path / "OCR2" / "instance.lock").exists()


_LOCK_HOLDER = """
import sys
from pathlib import Path
from alfa_document_intelligence import app_instance
lock = app_instance.acquire(Path(sys.argv[1]))
print("locked" if lock is not None else "busy", flush=True)
sys.stdin.readline()
if lock is not None:
    lock.release()
"""


def test_launcher_app_window_serves_when_starting_instance_releases_lock(monkeypatch, tmp_path):
    # A previous instance holds the lock without answering (it is closing after
    # Esci, or crashed before publishing); once it lets go, the new launch serves.
    _opened, lifetimes, served = _app_window_environment(monkeypatch, tmp_path)
    data_dir = tmp_path / "OCR2"
    data_dir.mkdir()
    environment = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, [source, environment.get("PYTHONPATH")]))
    holder = subprocess.Popen(
        [sys.executable, "-B", "-c", _LOCK_HOLDER, str(data_dir)],
        env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        thread, errors = _run_main_in_thread(["--app-window"])
        time.sleep(1.0)
        assert served == [], "must not serve while another process holds the lock"
        assert thread.is_alive(), "must keep waiting while the lock is held"
    finally:
        holder.communicate("\n", timeout=10)
    deadline = time.monotonic() + 15
    port = None
    while time.monotonic() < deadline and port is None and thread.is_alive():
        port = app_instance.running_instance(data_dir, timeout=0.5)
        if port is None:
            time.sleep(0.05)
    try:
        assert not errors, errors
        assert port is not None, "the waiting launcher did not take over after the lock was released"
        assert len(served) == 1
    finally:
        if lifetimes:
            lifetimes[0].request_exit()
        thread.join(15)
    assert not thread.is_alive() and not errors


def test_launcher_app_window_gives_up_when_lock_stays_held(monkeypatch, capsys, tmp_path):
    _opened, _lifetimes, served = _app_window_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(launcher, "_STARTING_INSTANCE_WAIT_SECONDS", 0.5)
    held = app_instance.acquire(tmp_path / "OCR2")
    monkeypatch.setattr(launcher, "acquire", lambda _data_dir: None)
    try:
        with pytest.raises(SystemExit) as raised:
            launcher.main(["--app-window"])
    finally:
        held.release()
    assert raised.value.code == 1
    assert served == []
    assert "OCR2 è già in avvio ma non risponde" in capsys.readouterr().err
