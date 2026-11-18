import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from alfa_document_intelligence.runtime_manifest import build_manifest, verify_installation


@pytest.fixture(autouse=True)
def _isolated_local_app_data(tmp_path_factory, monkeypatch):
    """Failures in window mode write a launch log: keep it out of the real profile."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path_factory.mktemp("LocalAppData")))


def _required_payload(root):
    (root / "app" / "alfa_document_intelligence").mkdir(parents=True, exist_ok=True)
    (root / "app" / "alfa_document_intelligence" / "__init__.py").write_bytes(b"synthetic")
    (root / "python").mkdir(exist_ok=True)
    for name in ("python.exe", "pythonw.exe", "python313.zip"):
        (root / "python" / name).write_bytes(b"synthetic")


def test_manifest_detects_changed_root_notices(tmp_path):
    _required_payload(tmp_path)
    notice = tmp_path / 'THIRD_PARTY_NOTICES.txt'
    notice.write_text('licences', encoding='utf-8')
    (tmp_path / 'sbom.json').write_text('{}', encoding='utf-8')
    manifest = build_manifest(tmp_path, version='1', excluded_globs=())
    path = tmp_path / 'runtime-manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert verify_installation(tmp_path, path).ok
    notice.write_text('modified', encoding='utf-8')
    assert not verify_installation(tmp_path, path).ok


def test_manifest_rejects_other_windows_reparse_points(tmp_path, monkeypatch):
    import stat
    from types import SimpleNamespace
    _required_payload(tmp_path)
    entry = tmp_path / 'python' / 'python.exe'
    original = Path.lstat
    def fake_lstat(path):
        if path == entry:
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        return original(path)
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    with pytest.raises(ValueError, match='links|reparse'):
        build_manifest(tmp_path, version='1', excluded_globs=())


@pytest.mark.parametrize('target_name', ['root', 'manifest'])
def test_verification_rejects_reparse_root_and_manifest(tmp_path, monkeypatch, target_name):
    import stat
    from types import SimpleNamespace
    _required_payload(tmp_path)
    manifest = build_manifest(tmp_path, version='1', excluded_globs=())
    path = tmp_path / 'runtime-manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    target = tmp_path if target_name == 'root' else path
    original = Path.lstat
    def fake_lstat(item):
        if item == target:
            mode = stat.S_IFDIR if target_name == 'root' else stat.S_IFREG
            return SimpleNamespace(st_mode=mode, st_file_attributes=0x400)
        return original(item)
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    assert not verify_installation(tmp_path, path).ok


def test_manifest_detects_changed_missing_extra_and_forbidden_files(tmp_path):
    _required_payload(tmp_path)
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
    _required_payload(tmp_path)
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
    _required_payload(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(build_manifest(tmp_path, version="1", excluded_globs=())), encoding="utf-8")
    def failed_walk(_path, *, followlinks, onerror=None):
        if onerror:
            onerror(PermissionError("synthetic"))
        return iter(())
    monkeypatch.setattr(runtime_manifest.os, "walk", failed_walk)
    assert not verify_installation(tmp_path, path).ok


def test_empty_payload_with_valid_manifest_is_rejected(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(build_manifest(tmp_path, version="1", excluded_globs=())), encoding="utf-8")
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


def test_launcher_integrity_error_does_not_disclose_runtime_paths(monkeypatch, tmp_path, capsys):
    from types import SimpleNamespace
    from alfa_document_intelligence import __main__ as launcher
    (tmp_path / 'runtime-manifest.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(launcher, '_installation_root', lambda: tmp_path)
    monkeypatch.setattr(launcher, 'verify_installation', lambda *args: SimpleNamespace(
        ok=False, problems=['File aggiuntivo: app/SYNTHETIC_PRIVATE_PATH_731']))
    notices = []
    monkeypatch.setattr(launcher, '_show_integrity_error', notices.append)
    with pytest.raises(SystemExit):
        launcher.main(['--app-window'])
    assert 'SYNTHETIC_PRIVATE_PATH_731' not in capsys.readouterr().err
    assert notices and 'SYNTHETIC_PRIVATE_PATH_731' not in notices[0]


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


def test_installed_launcher_rejects_missing_manifest(monkeypatch, tmp_path):
    from alfa_document_intelligence import __main__ as launcher
    monkeypatch.setattr(launcher, "_installation_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "_is_installed", lambda root: True)
    calls = []
    monkeypatch.setattr(launcher, "serve_expense_report_local", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(SystemExit) as exc:
        launcher.main([])
    assert exc.value.code == 2 and not calls


def test_inventory_rejects_root_junction(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    monkeypatch.setattr(Path, "is_junction", lambda path: path == tmp_path / "app")
    with pytest.raises(ValueError):
        build_manifest(tmp_path, version="1", excluded_globs=())


def test_link_entries_are_refused_without_creating_windows_symlinks(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    entry = tmp_path / "app" / "file"
    entry.write_text("synthetic", encoding="utf-8")
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == entry or real_is_symlink(path))
    with pytest.raises(ValueError, match="symbolic links"):
        build_manifest(tmp_path, version="1", excluded_globs=())


@pytest.mark.skipif(not os.environ.get("OCR2_TEST_RAPIDOCR_WITHOUT_FFMPEG"), reason="requires approved local RapidOCR runtime and opt-in")
def test_rapidocr_runs_without_ffmpeg_dll(tmp_path):
    """Compare OCR tokens with and without FFmpeg using generated data only."""
    runtime = Path(os.environ["OCR2_TEST_RAPIDOCR_WITHOUT_FFMPEG"])
    python = runtime / "Scripts" / "python.exe"
    cv2 = runtime / "Lib" / "site-packages" / "cv2"
    assert python.is_file() and cv2.is_dir()
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    shutil.copytree(cv2, shadow / "cv2", ignore=shutil.ignore_patterns("opencv_videoio_ffmpeg*.dll", "__pycache__"))
    script = tmp_path / "recognize.py"
    script.write_text('''from PIL import Image, ImageDraw, ImageFont\nimport json\nfrom alfa_document_intelligence.ocr_adapter import RasterPage\nfrom alfa_document_intelligence.rapidocr_runtime_factory import create_rapidocr_v6_multilingual_adapter\nimage = Image.new("RGB", (1000, 250), "white")\ndraw = ImageDraw.Draw(image)\nfont = ImageFont.truetype("arial.ttf", 48)\ndraw.text((40, 60), "TOTALE 123.45 EUR", font=font, fill="black")\npage = RasterPage(1, image.width, image.height, image.tobytes())\ntokens = create_rapidocr_v6_multilingual_adapter().recognize(page, ("it", "en"))\nprint("OCR2_RESULT=" + json.dumps([token.text for token in tokens], ensure_ascii=True))\n''', encoding="utf-8")
    app_src = str(Path(__file__).resolve().parents[1] / "src")
    results = []
    for prefix in (None, shadow):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(prefix) if prefix else None, app_src]))
        run = subprocess.run([str(python), "-B", str(script)], capture_output=True, text=True, env=env, timeout=180)
        assert run.returncode == 0, "synthetic OCR subprocess failed"
        lines = [line for line in run.stdout.splitlines() if line.startswith("OCR2_RESULT=")]
        assert len(lines) == 1
        results.append(json.loads(lines[0].split("=", 1)[1]))
    assert results[0] and results[1] == results[0]
    assert any("123" in text for text in results[1])


def test_unusable_manifest_names_are_reported_not_raised(tmp_path):
    """From #151 ae12b8f: names the OS rejects (ENAMETOOLONG on Linux) never raise."""
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    manifest = build_manifest(tmp_path, version="1", excluded_globs=())
    entry = {"sha256": "0" * 64, "size": 0}
    for name in ("python/python.exe", "python/pythonw.exe", "python/python313.zip",
                 "app/alfa_document_intelligence/__init__.py",
                 "app/" + "a" * 5000, "app/" + "b" * 300 + "/" + "c" * 300):
        manifest["files"][name] = entry
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = verify_installation(tmp_path, path)
    assert not result.ok
    assert "File mancante: app/" + "a" * 5000 in result.problems
