from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from alfa_document_intelligence import __main__ as launcher
from alfa_document_intelligence import runtime_manifest as rm

FFMPEG_GLOB = "**/opencv_videoio_ffmpeg*.dll"
TESTS_DIR = Path(__file__).resolve().parent


def _tree(root: Path) -> Path:
    (root / "python" / "Lib").mkdir(parents=True)
    (root / "app" / "pkg").mkdir(parents=True)
    (root / "python" / "python.exe").write_bytes(b"MZ-synthetic-python")
    (root / "python" / "Lib" / "mod.py").write_text("x = 1\n")
    (root / "app" / "pkg" / "__init__.py").write_text("")
    (root / "app" / "pkg" / "main.py").write_text("print('hi')\n")
    return root


def _manifested(root: Path) -> Path:
    path = root / rm.MANIFEST_NAME
    rm.write_manifest(rm.build_manifest(root, version="1.0.0", excluded_globs=[FFMPEG_GLOB]), path)
    return path


def test_manifest_round_trip_ok(tmp_path):
    root = _tree(tmp_path)
    manifest = rm.build_manifest(root, version="1.0.0", excluded_globs=[])
    assert manifest["format"] == 1 and manifest["version"] == "1.0.0"
    assert set(manifest["files"]) == {
        "python/python.exe", "python/Lib/mod.py", "app/pkg/__init__.py", "app/pkg/main.py",
    }
    entry = manifest["files"]["app/pkg/main.py"]
    assert entry["size"] == (root / "app" / "pkg" / "main.py").stat().st_size and len(entry["sha256"]) == 64
    path = _manifested(root)
    assert json.loads(path.read_text())["files"].keys() == manifest["files"].keys()
    result = rm.verify_installation(root, path)
    assert result.ok and result.problems == () and result.seconds >= 0 and result.checked_files == 4


def test_excluded_globs_are_left_out(tmp_path):
    root = _tree(tmp_path)
    (root / "app" / "pkg" / "__pycache__").mkdir()
    (root / "app" / "pkg" / "__pycache__" / "m.pyc").write_bytes(b"x")
    manifest = rm.build_manifest(root, version="1", excluded_globs=["**/__pycache__/**"])
    assert not any("__pycache__" in name for name in manifest["files"])


def test_altered_missing_and_extra_files_are_reported(tmp_path):
    root = _tree(tmp_path)
    path = _manifested(root)
    (root / "app" / "pkg" / "main.py").write_text("print('evil')\n")
    (root / "python" / "Lib" / "mod.py").unlink()
    (root / "app" / "pkg" / "extra.py").write_text("")
    (root / "python" / "extra.pyd").write_bytes(b"x")
    result = rm.verify_installation(root, path)
    assert not result.ok
    assert set(result.problems) == {
        "File alterato: app/pkg/main.py",
        "File mancante: python/Lib/mod.py",
        "File in più: app/pkg/extra.py",
        "File in più: python/extra.pyd",
    }
    assert str(root) not in " ".join(result.problems)


def test_extra_file_in_pycache_is_ignored_but_altered_listed_one_is_not(tmp_path):
    root = _tree(tmp_path)
    cache = root / "app" / "pkg" / "__pycache__"
    cache.mkdir()
    (cache / "listed.pyc").write_bytes(b"1")
    path = _manifested(root)
    (cache / "new.pyc").write_bytes(b"2")
    assert rm.verify_installation(root, path).ok
    (cache / "listed.pyc").write_bytes(b"3")
    assert rm.verify_installation(root, path).problems == ("File alterato: app/pkg/__pycache__/listed.pyc",)


def test_files_outside_python_and_app_are_not_extra(tmp_path):
    root = _tree(tmp_path)
    path = _manifested(root)
    (root / "notes.txt").write_text("x")
    assert rm.verify_installation(root, path).ok


def test_ffmpeg_dll_is_always_a_problem(tmp_path):
    root = _tree(tmp_path)
    dll = root / "python" / "Lib" / "cv2" / "opencv_videoio_ffmpeg500_64.dll"
    dll.parent.mkdir()
    dll.write_bytes(b"dll")
    with pytest.raises(ValueError):
        rm.build_manifest(root, version="1", excluded_globs=[])
    path = _manifested(root)  # excluded when building
    assert any("opencv_videoio_ffmpeg500_64.dll" in p for p in rm.verify_installation(root, path).problems)
    # Even when a hand-made manifest lists it with the right hash.
    manifest = json.loads(path.read_text())
    manifest["files"]["python/Lib/cv2/opencv_videoio_ffmpeg500_64.dll"] = {
        "sha256": hashlib.sha256(b"dll").hexdigest(), "size": 3,
    }
    path.write_text(json.dumps(manifest))
    result = rm.verify_installation(root, path)
    assert not result.ok and any("FFmpeg" in p for p in result.problems)


def test_symlink_is_refused(tmp_path):
    root = _tree(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("secret")
    try:
        os.symlink(target, root / "app" / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links cannot be created here")
    with pytest.raises(ValueError):
        rm.build_manifest(root, version="1", excluded_globs=[])
    path = tmp_path / "m.json"
    rm.write_manifest({"format": 1, "version": "1", "files": {}}, path)
    assert any("Collegamento simbolico" in p for p in rm.verify_installation(root, path).problems)


@pytest.mark.parametrize(
    "content",
    ["", "not json", "[]", '{"format": 2, "files": {}}', '{"format": 1}', '{"format": 1, "files": {"a": 3}}'],
)
def test_bad_manifest_never_raises(tmp_path, content):
    root = _tree(tmp_path)
    path = tmp_path / "m.json"
    path.write_text(content)
    result = rm.verify_installation(root, path)
    assert not result.ok and len(result.problems) == 1
    assert not rm.verify_installation(root, tmp_path / "missing.json").ok


def test_traversal_path_in_manifest_is_a_problem(tmp_path):
    root = _tree(tmp_path)
    path = tmp_path / "m.json"
    rm.write_manifest({"format": 1, "version": "1", "files": {"../x": {"sha256": "0" * 64, "size": 1}}}, path)
    assert "Percorso non valido nel manifest: ../x" in rm.verify_installation(root, path).problems


@pytest.mark.parametrize("key", ["app/a\x00b", "app/" + "a" * 40000])
def test_malformed_path_keys_never_raise(tmp_path, key):
    root = _tree(tmp_path)
    path = tmp_path / "m.json"
    rm.write_manifest({"format": 1, "version": "1", "files": {key: {"sha256": "0" * 64, "size": 1}}}, path)
    result = rm.verify_installation(root, path)
    assert not result.ok and result.problems


def test_launcher_turns_unexpected_verification_error_into_exit_2(monkeypatch, capsys, tmp_path):
    _installed_folder(tmp_path, monkeypatch, tamper=False)

    def boom(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(launcher.runtime_manifest, "verify_installation", boom)
    with pytest.raises(SystemExit) as exit_info:
        launcher._verify_runtime(False)
    assert exit_info.value.code == 2
    assert "Verifica del runtime non riuscita" in capsys.readouterr().err


def test_problem_list_is_capped_at_twenty(tmp_path):
    root = _tree(tmp_path)
    path = _manifested(root)
    for index in range(30):
        (root / "app" / f"extra{index:02}.py").write_text("")
    result = rm.verify_installation(root, path)
    assert not result.ok and len(result.problems) == 21
    assert result.problems[-1] == "… e altri 10 problemi"


def _installed_folder(tmp_path, monkeypatch, *, tamper):
    program = _tree(tmp_path / "versions" / "1.0.0")
    _manifested(program)
    if tamper:
        (program / "app" / "pkg" / "main.py").write_text("tampered")
    monkeypatch.setattr(launcher, "_program_folder", lambda: program)
    return program


def test_launcher_refuses_to_start_on_failed_verification(monkeypatch, capsys, tmp_path):
    _installed_folder(tmp_path, monkeypatch, tamper=True)
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(launcher, "_APP_WINDOW_AVAILABLE", True)
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url) or True)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("no port, lock or window may be opened")

    class FakeLock:
        released = False

        def release(self):
            self.released = True

    lock = FakeLock()
    for name in ("serve_expense_report_local", "open_window"):
        monkeypatch.setattr(launcher, name, forbidden)
    monkeypatch.setattr(launcher, "running_instance", lambda _dir: None)
    monkeypatch.setattr(launcher, "acquire", lambda _dir: lock)
    with pytest.raises(SystemExit) as exit_info:
        launcher.main(["--app-window"])
    assert exit_info.value.code == 2 and lock.released
    assert "File alterato: app/pkg/main.py" in capsys.readouterr().err
    page = (local / "OCR2" / "runtime-error.html").read_text(encoding="utf-8")
    assert "File alterato: app/pkg/main.py" in page and "<script" not in page.lower()
    assert opened == [(local / "OCR2" / "runtime-error.html").resolve().as_uri()]
    # Without the app window there is no page, still exit 2 and nothing served.
    with pytest.raises(SystemExit) as exit_info:
        launcher.main(["--port", "0"])
    assert exit_info.value.code == 2


def test_second_launch_opens_window_without_verifying(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(launcher, "_APP_WINDOW_AVAILABLE", True)
    opened = []
    monkeypatch.setattr(launcher, "running_instance", lambda _dir: 4321)
    monkeypatch.setattr(launcher, "open_window", lambda url, data_dir: opened.append(url) or "edge")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("an already running instance must not trigger a verification")

    monkeypatch.setattr(launcher, "_verify_runtime", forbidden)
    launcher.main(["--app-window"])
    assert opened == ["http://127.0.0.1:4321/"]


def test_upper_case_ffmpeg_dll_is_refused(tmp_path):
    root = _tree(tmp_path)
    (root / "app" / "OPENCV_VIDEOIO_FFMPEG500_64.DLL").write_bytes(b"dll")
    with pytest.raises(ValueError):
        rm.build_manifest(root, version="1", excluded_globs=[])
    manifest = rm.build_manifest(root, version="1", excluded_globs=[FFMPEG_GLOB])
    assert "app/OPENCV_VIDEOIO_FFMPEG500_64.DLL" not in manifest["files"]
    path = tmp_path / "m.json"
    rm.write_manifest(manifest, path)
    assert any("FFmpeg" in p for p in rm.verify_installation(root, path).problems)


@pytest.mark.skipif(os.name != "nt", reason="NTFS junctions exist only on Windows")
def test_junction_is_refused_and_not_followed(tmp_path):
    root = _tree(tmp_path / "prog")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("outside")
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "app" / "j"), str(outside)], capture_output=True)
    assert made.returncode == 0, made.stderr
    with pytest.raises(ValueError):
        rm.build_manifest(root, version="1", excluded_globs=[])
    path = tmp_path / "m.json"
    digest = hashlib.sha256((outside / "f.txt").read_bytes()).hexdigest()
    files = rm.build_manifest(root, version="1", excluded_globs=["app/j"])["files"]
    files["app/j/f.txt"] = {"sha256": digest, "size": (outside / "f.txt").stat().st_size}
    rm.write_manifest({"format": 1, "version": "1", "files": files}, path)
    result = rm.verify_installation(root, path)
    assert not result.ok
    assert "Collegamento simbolico non ammesso: app/j/f.txt" in result.problems
    assert "Collegamento simbolico non ammesso: app/j" in result.problems


def test_unreadable_folder_is_a_problem(monkeypatch, tmp_path):
    root = _tree(tmp_path)
    path = _manifested(root)
    real_walk = os.walk

    def failing_walk(top, followlinks=False, onerror=None):
        if onerror is not None:
            onerror(OSError(13, "denied", str(Path(top) / "app" / "locked")))
        return real_walk(top, followlinks=followlinks, onerror=onerror)

    monkeypatch.setattr(rm.os, "walk", failing_walk)
    assert "Cartella non leggibile: app/locked" in rm.verify_installation(root, path).problems


def test_error_page_escapes_problems(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: True)
    launcher._show_runtime_error(["File mancante: <script>alert(1)</script>.py"], tmp_path)
    page = (tmp_path / "runtime-error.html").read_text(encoding="utf-8")
    assert "<script" not in page and "&lt;script&gt;" in page


def test_launcher_reports_verified_runtime_status(monkeypatch, tmp_path):
    _installed_folder(tmp_path, monkeypatch, tamper=False)
    status = launcher._verify_runtime(False)
    assert status.startswith("verificato (4 file, ") and status.endswith(" s)")


def test_launcher_from_sources_has_no_check(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "_program_folder", lambda: tmp_path)
    assert launcher._verify_runtime(False) == "non verificato (avvio da sorgenti)"


def _runtime_python() -> str | None:
    for candidate in (os.environ.get("OCR2_RUNTIME_PYTHON"), sys.executable):
        if not candidate or not Path(candidate).is_file():
            continue
        probe = subprocess.run(
            [candidate, "-I", "-c", "import rapidocr, cv2, PIL, numpy, onnxruntime"],
            capture_output=True, timeout=120,
        )
        if probe.returncode == 0:
            return candidate
    return None


def _probe(python: str, extra_path: Path | None, tmp_path: Path) -> dict:
    source = TESTS_DIR.parent / "src"
    paths = [str(source), str(TESTS_DIR)]
    if extra_path is not None:
        paths.insert(0, str(extra_path))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(paths), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [python, "-B", str(TESTS_DIR / "ffmpeg_probe.py")],
        capture_output=True, text=True, env=env, timeout=600, cwd=tmp_path,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_rapidocr_runs_without_ffmpeg_dll(tmp_path):
    python = _runtime_python()
    if python is None:
        pytest.skip("runtime with rapidocr and cv2 not available (set OCR2_RUNTIME_PYTHON)")
    original = _probe(python, None, tmp_path)
    cv2_folder = Path(original["cv2_folder"])
    copy_root = tmp_path / "no-ffmpeg"
    shutil.copytree(cv2_folder, copy_root / "cv2", ignore=shutil.ignore_patterns("opencv_videoio_ffmpeg*"))
    without = _probe(python, copy_root, tmp_path)
    assert Path(without["cv2_folder"]).resolve() == (copy_root / "cv2").resolve()
    assert without["ffmpeg_dlls"] == []
    assert original["texts"] and without["texts"] == original["texts"]
    assert any("FATTURA" in text for text in without["texts"])


def test_resolved_drops_the_extended_length_prefix_but_keeps_unc(monkeypatch):
    # A short (8.3) path can resolve to a long name beyond MAX_PATH, which realpath returns with the extended prefix.
    results = {"long": r"\\?\C:\Users\long-name\file.pyc", "unc": r"\\?\UNC\server\share\file.pyc"}
    monkeypatch.setattr(rm.Path, "resolve", lambda self, strict=False: type(self)(results[self.name]))
    assert str(rm._resolved(Path("long"))) == str(Path(r"C:\Users\long-name\file.pyc"))
    assert str(rm._resolved(Path("unc"))) == str(Path(results["unc"]))


def test_installed_layout_without_manifest_refuses_to_start(monkeypatch, capsys, tmp_path):
    # R37: an installed copy (versions/<x.y.z>/ with app/ and python/) never starts unverified.
    program = _installed_folder(tmp_path, monkeypatch, tamper=False)
    (program / rm.MANIFEST_NAME).unlink()
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url) or True)
    with pytest.raises(SystemExit) as exit_info:
        launcher._verify_runtime(True)
    assert exit_info.value.code == 2
    assert rm.MANIFEST_NAME in capsys.readouterr().err
    page = (local / "OCR2" / "runtime-error.html").read_text(encoding="utf-8")
    assert rm.MANIFEST_NAME in page and opened


@pytest.mark.parametrize("layout", ["no-python", "not-versions", "bad-version"])
def test_folders_that_are_not_an_installed_layout_still_run_from_sources(monkeypatch, tmp_path, layout):
    parent = {"not-versions": "elsewhere"}.get(layout, "versions")
    name = "1.0" if layout == "bad-version" else "1.0.0"
    program = _tree(tmp_path / parent / name)
    if layout == "no-python":
        shutil.rmtree(program / "python")
    monkeypatch.setattr(launcher, "_program_folder", lambda: program)
    assert launcher._verify_runtime(False) == "non verificato (avvio da sorgenti)"


def test_runtime_error_page_gives_the_remedies_that_work(monkeypatch, tmp_path):
    # R38: the installer refuses the active version, so no «Reinstalla» advice.
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: True)
    launcher._show_runtime_error(["File mancante: x.py"], tmp_path)
    page = (tmp_path / "runtime-error.html").read_text(encoding="utf-8")
    assert "Reinstalla" not in page
    assert "Torna alla versione precedente" in page
    assert "disinstalla OCR2 mantenendo i dati" in page and "installalo di nuovo" in page
