import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest

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


def test_launcher_serves_on_configured_port_and_closes_cleanly(monkeypatch, capsys):
    server = _FakeServer()
    calls = []
    monkeypatch.setattr(
        launcher,
        "serve_expense_report_local",
        lambda *, port: calls.append(port) or server,
    )

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



def test_launcher_serves_real_loopback_http_request_and_stops():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
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
