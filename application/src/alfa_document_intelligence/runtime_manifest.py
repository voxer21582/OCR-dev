"""Build and verify an offline installation's file inventory."""
from dataclasses import dataclass
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import time

FORBIDDEN_GLOBS = ("**/opencv_videoio_ffmpeg*.dll",)
_ROOT_FILES = frozenset({"sbom.json", "THIRD_PARTY_NOTICES.txt"})
_REQUIRED_FILES = frozenset({"python/python.exe", "python/pythonw.exe", "python/python313.zip",
                             "app/alfa_document_intelligence/__init__.py"})


@dataclass(frozen=True)
class RuntimeVerification:
    ok: bool
    problems: tuple[str, ...]
    seconds: float


def _linked(path: Path) -> bool:
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        return True
    try:
        return bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    except FileNotFoundError:
        return False


def _inventory(root: Path, excluded_globs) -> dict:
    result = {}
    if _linked(root):
        raise ValueError('symbolic links or reparse points are not allowed')
    def fail(error):
        raise error
    for directory in ("app", "python"):
        base = root / directory
        if _linked(base):
            raise ValueError("symbolic links are not allowed")
        if not base.is_dir():
            raise ValueError("payload directory missing")
        for current, dirs, files in os.walk(base, followlinks=False, onerror=fail):
            for name in dirs + files:
                path = Path(current) / name
                if _linked(path):
                    raise ValueError("symbolic links are not allowed")
            for name in files:
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                if any(fnmatch.fnmatchcase(relative, pattern) for pattern in excluded_globs):
                    continue
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                result[relative] = {"sha256": digest.hexdigest(), "size": size}
    for name in _ROOT_FILES:
        path = root / name
        if _linked(path):
            raise ValueError("symbolic links are not allowed")
        if path.exists():
            if not path.is_file():
                raise ValueError("invalid root file")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result[name] = {"sha256": digest, "size": path.stat().st_size}
    return dict(sorted(result.items()))


def build_manifest(root: Path, *, version: str, excluded_globs) -> dict:
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version required")
    return {"format": 1, "version": version, "files": _inventory(Path(root), excluded_globs)}


def verify_installation(root: Path, manifest_path: Path) -> RuntimeVerification:
    import json
    start = time.monotonic()
    problems = []
    try:
        if _linked(Path(root)) or _linked(Path(manifest_path)):
            raise ValueError('symbolic links or reparse points are not allowed')
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("format") != 1
                or not isinstance(manifest.get("version"), str) or not manifest["version"]
                or not isinstance(manifest.get("files"), dict)):
            raise ValueError("invalid manifest")
        expected = manifest["files"]
        if not _REQUIRED_FILES <= set(expected):
            raise ValueError("manifest missing required runtime files")
        for name, info in expected.items():
            parts = name.split("/") if isinstance(name, str) else []
            if ((name not in _ROOT_FILES and (len(parts) < 2 or parts[0] not in {"app", "python"}))
                    or any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in parts)
                    or not isinstance(info, dict) or set(info) != {"sha256", "size"}
                    or not isinstance(info["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", info["sha256"])
                    or type(info["size"]) is not int or info["size"] < 0):
                raise ValueError("invalid manifest entry")
        actual = _inventory(Path(root), ())
        for name in sorted(set(expected) | set(actual)):
            if name not in actual:
                problems.append(f"File mancante: {name}")
            elif name not in expected:
                problems.append(f"File aggiuntivo: {name}")
            elif actual[name] != expected[name]:
                problems.append(f"File modificato: {name}")
            if any(fnmatch.fnmatchcase(name.lower(), pattern) for pattern in FORBIDDEN_GLOBS):
                problems.append(f"File vietato: {name}")
    except (OSError, ValueError, TypeError, UnicodeError):
        problems.append("Manifest o installazione non validi")
    return RuntimeVerification(not problems, tuple(problems[:20]), time.monotonic() - start)
