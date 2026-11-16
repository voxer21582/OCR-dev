"""Build the offline OCR2 installation payload from pinned local artifacts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import zipfile


class PayloadBuildError(ValueError):
    """An input is unsafe or does not match its approved digest."""


def _extract_embeddable(archive: Path, destination: Path, expected_sha256: str) -> None:
    if destination.exists() or destination.is_symlink():
        raise PayloadBuildError("Payload destination already exists")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise PayloadBuildError("Invalid pinned SHA-256")
    digest = hashlib.sha256()
    with archive.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            raise PayloadBuildError("Embeddable Python digest mismatch")
        source_file.seek(0)
        with zipfile.ZipFile(source_file) as source:
            entries = source.infolist()
            if len(entries) > 10000 or sum(item.file_size for item in entries) > 1024 * 1024 * 1024:
                raise PayloadBuildError("Embeddable archive exceeds limits")
            names = set()
            for item in entries:
                name = item.filename
                parts = PurePosixPath(name).parts
                reserved = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
                if (not name or name.startswith("/") or "//" in name or "\\" in name or ":" in name
                        or any(part in (".", "..") or part.endswith((".", " ")) for part in parts)
                        or any(reserved.fullmatch(part) for part in parts)
                        or stat.S_ISLNK(item.external_attr >> 16)
                        or name.casefold() in names):
                    raise PayloadBuildError("Unsafe or duplicate archive path")
                names.add(name.casefold())
            destination.mkdir(parents=True, exist_ok=False)
            for item in entries:
                path = destination.joinpath(*PurePosixPath(item.filename).parts)
                if item.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(item) as entry_file, path.open("xb") as target:
                        while chunk := entry_file.read(1024 * 1024):
                            target.write(chunk)


def _configure_python_path(python_dir: Path) -> None:
    (python_dir / "python313._pth").write_text(
        "python313.zip\n.\n..\\app\nLib\\site-packages\nimport site\n", encoding="utf-8"
    )


def _install_wheels(wheel_dir: Path, lock_path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile",
               "--require-hashes", "--find-links", str(wheel_dir), "--target", str(target),
               "-r", str(lock_path)]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise PayloadBuildError("Offline wheel installation failed")


def _finalize(root: Path, lock_path: Path, pins_path: Path, version: str) -> None:
    from alfa_document_intelligence.runtime_manifest import build_manifest

    def load(name):
        spec = importlib.util.spec_from_file_location('ocr2_installer_' + name, Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    sbom = load('sbom').build_sbom(root, lock_path, pins_path)
    notices = load('notices').build_notices(root)
    (root / 'sbom.json').write_text(json.dumps(sbom, ensure_ascii=True, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    (root / 'THIRD_PARTY_NOTICES.txt').write_text(notices, encoding='utf-8')
    manifest = build_manifest(root, version=version, excluded_globs=())
    (root / 'runtime-manifest.json').write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def build_payload(*, embeddable_zip: Path, wheel_dir: Path, app_src: Path, out_dir: Path,
                  version: str, pins_path: Path | None = None, lock_path: Path | None = None) -> Path:
    from alfa_document_intelligence.runtime_manifest import build_manifest

    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise PayloadBuildError("Invalid version")
    repository = Path(__file__).resolve().parents[1]
    pins_path = pins_path or repository / "installer" / "pins.json"
    lock_path = lock_path or repository / "requirements" / "ocr2-runtime-cp313-win-amd64.lock"
    try:
        pin = json.loads(pins_path.read_text(encoding="utf-8"))["python"]
        if not isinstance(pin, dict) or pin.get("filename") != embeddable_zip.name:
            raise PayloadBuildError("Embeddable Python filename does not match pin")
        sha = pin["sha256"]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise PayloadBuildError("Invalid Python pin") from exc
    result = out_dir / version
    if result.exists() or result.is_symlink():
        raise PayloadBuildError("Payload version already exists")
    if not wheel_dir.is_dir() or not lock_path.is_file() or not (app_src / "alfa_document_intelligence").is_dir():
        raise PayloadBuildError("Missing local payload inputs")
    _extract_embeddable(embeddable_zip, result / "python", sha)
    _configure_python_path(result / "python")
    _install_wheels(wheel_dir, lock_path, result / "python" / "Lib" / "site-packages")
    source = app_src / "alfa_document_intelligence"
    for item in source.rglob("*"):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise PayloadBuildError("Application source contains a link")
    shutil.copytree(source, result / "app" / "alfa_document_intelligence",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    for dll in (result / "python" / "Lib" / "site-packages").rglob("opencv_videoio_ffmpeg*.dll"):
        if dll.is_symlink() or not dll.is_file():
            raise PayloadBuildError("Invalid FFmpeg payload entry")
        dll.unlink()
    manifest = build_manifest(result, version=version, excluded_globs=())
    (result / "runtime-manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _finalize(result, lock_path, pins_path, version)
    return result
