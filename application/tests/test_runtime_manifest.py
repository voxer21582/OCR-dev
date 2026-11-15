import json
from pathlib import Path

import pytest

from alfa_document_intelligence.runtime_manifest import build_manifest, verify_installation


def test_manifest_detects_changed_missing_extra_and_forbidden_files(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    (tmp_path / "app" / "a.py").write_bytes(b"original")
    (tmp_path / "python" / "p.dll").write_bytes(b"runtime")
    manifest = build_manifest(tmp_path, version="1", excluded_globs=())
    path = tmp_path / "runtime-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_installation(tmp_path, path).ok
    (tmp_path / "app" / "a.py").write_bytes(b"changed")
    (tmp_path / "python" / "p.dll").unlink()
    (tmp_path / "python" / "opencv_videoio_ffmpeg123.dll").write_bytes(b"x")
    result = verify_installation(tmp_path, path)
    assert not result.ok
    assert any("a.py" in item for item in result.problems)
    assert any("p.dll" in item for item in result.problems)
    assert any("ffmpeg" in item for item in result.problems)


def test_manifest_rejects_symlink(tmp_path):
    (tmp_path / "app").mkdir()
    target = tmp_path / "target"
    target.write_bytes(b"x")
    try:
        (tmp_path / "app" / "link").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        build_manifest(tmp_path, version="1", excluded_globs=())


def test_launcher_refuses_invalid_runtime_before_opening_server(monkeypatch, tmp_path):
    from alfa_document_intelligence import __main__ as launcher
    (tmp_path / "runtime-manifest.json").write_text('{"format":1,"version":"1","files":{}}', encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "injected.py").write_text("bad", encoding="utf-8")
    monkeypatch.setattr(launcher, "_installation_root", lambda: tmp_path)
    server_calls = []
    monkeypatch.setattr(launcher, "serve_expense_report_local", lambda **kw: server_calls.append(kw))
    with pytest.raises(SystemExit) as exc:
        launcher.main([])
    assert exc.value.code == 2
    assert not server_calls


def test_ffmpeg_forbidden_even_if_listed(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "opencv_videoio_ffmpeg123.dll").write_bytes(b"x")
    manifest = build_manifest(tmp_path, version="1", excluded_globs=())
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not verify_installation(tmp_path, path).ok


def test_missing_payload_directories_are_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"format": 1, "version": "1", "files": {}}), encoding="utf-8")
    assert not verify_installation(tmp_path, path).ok


def test_walk_errors_fail_closed(monkeypatch, tmp_path):
    from alfa_document_intelligence import runtime_manifest
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(build_manifest(tmp_path, version="1", excluded_globs=())), encoding="utf-8")
    def failed_walk(_path, *, followlinks, onerror=None):
        if onerror:
            onerror(PermissionError("synthetic"))
        return iter(())
    monkeypatch.setattr(runtime_manifest.os, "walk", failed_walk)
    assert not verify_installation(tmp_path, path).ok


def test_launcher_reports_integrity_failure_in_window_mode(monkeypatch, tmp_path):
    from alfa_document_intelligence import __main__ as launcher
    (tmp_path / "runtime-manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "_installation_root", lambda: tmp_path)
    notices = []
    monkeypatch.setattr(launcher, "_show_integrity_error", notices.append)
    with pytest.raises(SystemExit) as exc:
        launcher.main(["--app-window"])
    assert exc.value.code == 2
    assert notices and "installazione" in notices[0].lower()


def test_launcher_window_error_works_without_stderr(monkeypatch, tmp_path):
    from alfa_document_intelligence import __main__ as launcher
    (tmp_path / "runtime-manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "_installation_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "stderr", None)
    notices = []
    monkeypatch.setattr(launcher, "_show_integrity_error", notices.append)
    with pytest.raises(SystemExit) as exc:
        launcher.main(["--app-window"])
    assert exc.value.code == 2 and notices


def test_link_entries_are_refused_without_creating_windows_symlinks(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    entry = tmp_path / "app" / "file"
    entry.write_text("synthetic", encoding="utf-8")
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == entry or real_is_symlink(path))
    with pytest.raises(ValueError, match="symbolic links"):
        build_manifest(tmp_path, version="1", excluded_globs=())
