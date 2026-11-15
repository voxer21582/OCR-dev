from pathlib import Path
import types

import pytest

from alfa_document_intelligence import app_window

_WRITE_FUNCTIONS = (
    "CreateKey", "CreateKeyEx", "DeleteKey", "DeleteKeyEx", "DeleteValue", "SetValue", "SetValueEx",
    "SaveKey", "LoadKey", "FlushKey", "ConnectRegistry", "DisableReflectionKey", "EnableReflectionKey",
)


def _no_program_files(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf86"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))


def _fake_winreg(calls, value):
    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def open_key(root, sub_key, reserved=0, access=None):
        calls.append(("OpenKey", root, sub_key, access))
        return _Key()

    def query_value(key, sub_key):
        calls.append(("QueryValue", sub_key))
        return value

    module = types.SimpleNamespace(
        HKEY_LOCAL_MACHINE="HKLM", KEY_READ="KEY_READ", OpenKey=open_key, QueryValue=query_value,
    )
    for name in _WRITE_FUNCTIONS:
        setattr(module, name, lambda *_a, _name=name, **_k: calls.append(("WRITE", _name)))
    return module


def test_find_edge_prefers_program_files(monkeypatch, tmp_path):
    _no_program_files(monkeypatch, tmp_path)
    edge = tmp_path / "pf" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    monkeypatch.setattr(app_window, "_winreg", lambda: pytest.fail("registry must not be read"))
    assert app_window.find_edge() == edge


def test_find_edge_never_writes_registry(monkeypatch, tmp_path):
    _no_program_files(monkeypatch, tmp_path)
    edge = tmp_path / "elsewhere" / "msedge.exe"
    edge.parent.mkdir()
    edge.write_bytes(b"")
    calls = []
    monkeypatch.setattr(app_window, "_winreg", lambda: _fake_winreg(calls, f'"{edge}"'))
    assert app_window.find_edge() == edge
    assert ("WRITE",) not in [call[:1] for call in calls]
    assert calls[0] == (
        "OpenKey", "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe", "KEY_READ",
    )
    source = Path(app_window.__file__).read_text(encoding="utf-8")
    for name in _WRITE_FUNCTIONS:
        assert name not in source


def test_find_edge_returns_none_without_edge(monkeypatch, tmp_path):
    _no_program_files(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(app_window, "_winreg", lambda: _fake_winreg(calls, str(tmp_path / "missing" / "msedge.exe")))
    assert app_window.find_edge() is None
    monkeypatch.setattr(app_window, "_winreg", lambda: None)
    assert app_window.find_edge() is None


def test_open_window_uses_dedicated_profile(monkeypatch, tmp_path):
    edge = tmp_path / "msedge.exe"
    launched = []

    class _FakePopen:
        def __init__(self, args, **kwargs):
            launched.append((args, kwargs))

    monkeypatch.setattr(app_window, "find_edge", lambda: edge)
    monkeypatch.setattr(app_window.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(app_window.webbrowser, "open", lambda *_a, **_k: pytest.fail("no default browser"))
    data_dir = tmp_path / "OCR2"

    assert app_window.open_window("http://127.0.0.1:5123/", data_dir) == "edge"

    assert len(launched) == 1
    args, kwargs = launched[0]
    assert args == [
        str(edge),
        "--app=http://127.0.0.1:5123/",
        f"--user-data-dir={data_dir / 'edge-profile'}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
    ]
    assert kwargs.get("shell", False) is False


def test_open_window_falls_back_to_default_browser(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(app_window, "find_edge", lambda: None)
    monkeypatch.setattr(app_window.subprocess, "Popen", lambda *_a, **_k: pytest.fail("no Edge to start"))
    monkeypatch.setattr(app_window.webbrowser, "open", lambda url, *_a, **_k: opened.append(url) or True)
    assert app_window.open_window("http://127.0.0.1:5123/", tmp_path) == "browser"
    assert opened == ["http://127.0.0.1:5123/"]


def test_open_window_falls_back_when_edge_cannot_start(monkeypatch, tmp_path):
    opened = []

    def failing_popen(*_a, **_k):
        raise OSError("cannot start")

    monkeypatch.setattr(app_window, "find_edge", lambda: tmp_path / "msedge.exe")
    monkeypatch.setattr(app_window.subprocess, "Popen", failing_popen)
    monkeypatch.setattr(app_window.webbrowser, "open", lambda url, *_a, **_k: opened.append(url) or True)
    assert app_window.open_window("http://127.0.0.1:5123/", tmp_path) == "browser"
    assert opened == ["http://127.0.0.1:5123/"]


@pytest.mark.parametrize("url", ["https://example.com/", "http://localhost:1/", "http://127.0.0.1:1/ --x", "file:///c:/x"])
def test_open_window_only_opens_the_local_server(monkeypatch, tmp_path, url):
    monkeypatch.setattr(app_window, "find_edge", lambda: pytest.fail("must not look for Edge"))
    with pytest.raises(ValueError):
        app_window.open_window(url, tmp_path)
