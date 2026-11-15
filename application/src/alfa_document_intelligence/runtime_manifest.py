"""Build and verify an offline installation's file inventory."""
from dataclasses import dataclass
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import time

FORBIDDEN_GLOBS = ("**/opencv_videoio_ffmpeg*.dll",)


@dataclass(frozen=True)
class RuntimeVerification:
    ok: bool
    problems: tuple[str, ...]
    seconds: float


def _inventory(root: Path, excluded_globs) -> dict:
    result = {}
    for directory in ("app", "python"):
        base = root / directory
        if base.is_symlink():
            raise ValueError("symbolic links are not allowed")
        if not base.exists():
            continue
        for current, dirs, files in os.walk(base, followlinks=False):
            for name in dirs + files:
                path = Path(current) / name
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
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
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("format") != 1
                or not isinstance(manifest.get("version"), str) or not manifest["version"]
                or not isinstance(manifest.get("files"), dict)):
            raise ValueError("invalid manifest")
        expected = manifest["files"]
        for name, info in expected.items():
            parts = name.split("/") if isinstance(name, str) else []
            if (len(parts) < 2 or parts[0] not in {"app", "python"}
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
