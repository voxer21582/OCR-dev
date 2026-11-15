import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from wsgiref.simple_server import WSGIRequestHandler, make_server

from alfa_document_intelligence import app_instance

_SRC = Path(__file__).resolve().parents[1] / "src"

_HOLDER = """
import sys
from pathlib import Path
from alfa_document_intelligence import app_instance
lock = app_instance.acquire(Path(sys.argv[1]))
print("locked" if lock is not None else "busy", flush=True)
sys.stdin.readline()
if lock is not None:
    lock.release()
"""


def _holder(data_dir):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, [str(_SRC), environment.get("PYTHONPATH")]))
    return subprocess.Popen(
        [sys.executable, "-B", "-c", _HOLDER, str(data_dir)],
        env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )


def test_second_acquire_returns_none_while_first_holds(tmp_path):
    process = _holder(tmp_path)
    try:
        assert process.stdout.readline().strip() == "locked"
        assert app_instance.acquire(tmp_path) is None
    finally:
        process.communicate("\n", timeout=10)
    lock = app_instance.acquire(tmp_path)
    assert lock is not None
    lock.release()


def test_publish_writes_instance_file_and_release_removes_it(tmp_path):
    lock = app_instance.acquire(tmp_path / "nested")
    assert lock is not None
    try:
        lock.publish(4321, "abc_DEF-123")
        data = json.loads((tmp_path / "nested" / "instance.json").read_text(encoding="utf-8"))
        assert data == {"port": 4321, "instance_id": "abc_DEF-123"}
    finally:
        lock.release()
    assert not (tmp_path / "nested" / "instance.json").exists()
    again = app_instance.acquire(tmp_path / "nested")
    assert again is not None
    again.release()


def _info_server(instance_id):
    def app(environ, start_response):
        if environ.get("PATH_INFO") != "/app/info":
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"no"]
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [f'<!doctype html><meta name="ocr2-instance" content="{instance_id}"><title>x</title>'.encode()]

    class _Quiet(WSGIRequestHandler):
        def log_message(self, *_args):
            pass

    server = make_server("127.0.0.1", 0, app, handler_class=_Quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _write_instance(data_dir, port, instance_id):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "instance.json").write_text(json.dumps({"port": port, "instance_id": instance_id}), encoding="utf-8")


def test_running_instance_confirms_matching_server(tmp_path):
    server = _info_server("live-id_1")
    try:
        port = server.server_address[1]
        _write_instance(tmp_path, port, "live-id_1")
        assert app_instance.running_instance(tmp_path) == port
    finally:
        server.shutdown()
        server.server_close()


def test_running_instance_ignores_stale_file(tmp_path):
    # No file at all.
    assert app_instance.running_instance(tmp_path) is None
    # Port closed.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    closed_port = listener.getsockname()[1]
    listener.close()
    _write_instance(tmp_path, closed_port, "some-id")
    assert app_instance.running_instance(tmp_path, timeout=1.0) is None
    # A server answers but with another instance id.
    server = _info_server("other-id")
    try:
        _write_instance(tmp_path, server.server_address[1], "some-id")
        assert app_instance.running_instance(tmp_path, timeout=1.0) is None
        # Empty id never matches.
        _write_instance(tmp_path, server.server_address[1], "")
        assert app_instance.running_instance(tmp_path, timeout=1.0) is None
    finally:
        server.shutdown()
        server.server_close()
    # Corrupt or malformed files.
    (tmp_path / "instance.json").write_text("{not json", encoding="utf-8")
    assert app_instance.running_instance(tmp_path) is None
    (tmp_path / "instance.json").write_text(json.dumps({"port": "80", "instance_id": "x"}), encoding="utf-8")
    assert app_instance.running_instance(tmp_path) is None
    (tmp_path / "instance.json").write_text(json.dumps({"port": 70000, "instance_id": "x"}), encoding="utf-8")
    assert app_instance.running_instance(tmp_path) is None


def test_running_instance_refuses_redirects(tmp_path):
    target = _info_server("live-id_1")

    def redirect(environ, start_response):
        start_response("302 Found", [("Location", f"http://127.0.0.1:{target.server_address[1]}/app/info")])
        return [b""]

    class _Quiet(WSGIRequestHandler):
        def log_message(self, *_args):
            pass

    redirector = make_server("127.0.0.1", 0, redirect, handler_class=_Quiet)
    threading.Thread(target=redirector.serve_forever, daemon=True).start()
    try:
        _write_instance(tmp_path, redirector.server_address[1], "live-id_1")
        assert app_instance.running_instance(tmp_path, timeout=1.0) is None
    finally:
        for server in (redirector, target):
            server.shutdown()
            server.server_close()


def test_publish_retries_replace_on_sharing_violation(monkeypatch, tmp_path):
    lock = app_instance.acquire(tmp_path)
    assert lock is not None
    real_replace = app_instance.os.replace
    attempts = []

    def flaky_replace(source, target):
        attempts.append(target)
        if len(attempts) < 3:
            raise PermissionError("in use")
        real_replace(source, target)

    monkeypatch.setattr(app_instance.os, "replace", flaky_replace)
    monkeypatch.setattr(app_instance.time, "sleep", lambda _seconds: None)
    try:
        lock.publish(4321, "abc")
        assert len(attempts) == 3
        assert json.loads((tmp_path / "instance.json").read_text(encoding="utf-8"))["port"] == 4321
    finally:
        monkeypatch.setattr(app_instance.os, "replace", real_replace)
        lock.release()


def test_publish_gives_up_after_repeated_sharing_violations(monkeypatch, tmp_path):
    lock = app_instance.acquire(tmp_path)
    assert lock is not None

    def always_busy(_source, _target):
        raise PermissionError("in use")

    real_replace = app_instance.os.replace
    monkeypatch.setattr(app_instance.os, "replace", always_busy)
    monkeypatch.setattr(app_instance.time, "sleep", lambda _seconds: None)
    try:
        try:
            lock.publish(4321, "abc")
        except PermissionError:
            pass
        else:
            raise AssertionError("publish must not hide a persistent sharing violation")
    finally:
        monkeypatch.setattr(app_instance.os, "replace", real_replace)
        lock.release()
