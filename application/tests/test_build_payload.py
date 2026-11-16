import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def _builder():
    path = Path(__file__).resolve().parents[2] / "installer" / "build_payload.py"
    spec = importlib.util.spec_from_file_location("ocr2_build_payload", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_rejects_unpinned_embed_before_extraction(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", "0" * 64)
    assert not (tmp_path / "payload" / "python.exe").exists()


def test_payload_rejects_zip_traversal_and_preserves_destination(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside", b"synthetic")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", digest)
    assert not (tmp_path / "outside").exists()


def test_payload_python_path_is_offline_and_enables_application(tmp_path):
    builder = _builder()
    python = tmp_path / "python"
    python.mkdir()
    builder._configure_python_path(python)
    lines = (python / "python313._pth").read_text(encoding="utf-8").splitlines()
    assert lines == ["python313.zip", ".", "..\\app", "Lib\\site-packages", "import site"]


@pytest.mark.parametrize("name", ["a/../outside", "dir//file", "CON.txt", "dir/NUL", "dir/file ", "C:/escape"])
def test_payload_rejects_ambiguous_windows_archive_names(tmp_path, name):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"synthetic")
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", hashlib.sha256(archive.read_bytes()).hexdigest())


def test_payload_refuses_existing_destination(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    destination = tmp_path / "payload"
    destination.mkdir()
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, destination, hashlib.sha256(archive.read_bytes()).hexdigest())


def test_extraction_uses_same_open_file_that_was_hashed(monkeypatch, tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    original_zip = zipfile.ZipFile
    def require_open_handle(file, *args, **kwargs):
        assert hasattr(file, "read") and hasattr(file, "seek")
        return original_zip(file, *args, **kwargs)
    monkeypatch.setattr(builder.zipfile, "ZipFile", require_open_handle)
    builder._extract_embeddable(archive, tmp_path / "payload", digest)
    assert (tmp_path / "payload" / "python.exe").read_bytes() == b"synthetic"


def test_build_payload_excludes_tests_caches_and_ffmpeg_and_verifies(monkeypatch, tmp_path):
    from alfa_document_intelligence.runtime_manifest import verify_installation
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
        output.writestr("pythonw.exe", b"synthetic")
        output.writestr("python313.zip", b"synthetic")
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps({"python": {"filename": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}), encoding="utf-8")
    src = tmp_path / "source"
    package = src / "alfa_document_intelligence"
    (package / "__pycache__").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__pycache__" / "cache.pyc").write_bytes(b"x")
    (package / "tests").mkdir()
    (package / "tests" / "private.py").write_text("", encoding="utf-8")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    lock = tmp_path / "requirements.lock"
    lock.write_text("", encoding="utf-8")
    def install(_wheels, _lock, target):
        (target / "cv2").mkdir(parents=True)
        (target / "cv2" / "opencv_videoio_ffmpeg123.dll").write_bytes(b"x")
        (target / "cv2" / "other.pyd").write_bytes(b"y")
    monkeypatch.setattr(builder, "_install_wheels", install)
    finalized = []
    monkeypatch.setattr(builder, "_finalize", lambda root, lock, pins, version: finalized.append(root))
    result = builder.build_payload(embeddable_zip=archive, wheel_dir=wheels, app_src=src,
                                   out_dir=tmp_path / "out", version="0.6.0", pins_path=pins, lock_path=lock)
    assert (result / "app" / "alfa_document_intelligence" / "__init__.py").is_file()
    assert '__version__ = "0.6.0"' in (result / "app" / "alfa_document_intelligence" / "__init__.py").read_text(encoding='utf-8')
    assert not (result / "app" / "alfa_document_intelligence" / "tests").exists()
    assert not (result / "app" / "alfa_document_intelligence" / "__pycache__").exists()
    assert not list(result.rglob("opencv_videoio_ffmpeg*.dll"))
    assert verify_installation(result, result / "runtime-manifest.json").ok
    assert finalized == [result]


def test_wheel_install_disables_bytecode_compilation(monkeypatch, tmp_path):
    builder = _builder()
    commands = []
    def run(command, check):
        commands.append(command)
        class Result:
            returncode = 0
        return Result()
    monkeypatch.setattr(builder.subprocess, "run", run)
    builder._install_wheels(tmp_path / "wheels", tmp_path / "lock", tmp_path / "target")
    assert "--no-compile" in commands[0]
