"""Hash manifest of the installed runtime and its check at start-up (REQ-103, REQ-106, DEC-030).

The installer payload gets a ``runtime-manifest.json`` listing every file of the
bundled Python and application with its size and SHA-256.  The launcher checks it
before it opens a port.  Only relative POSIX paths ever appear in the manifest
and in the problem messages, so nothing here discloses a user profile path.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Sequence

MANIFEST_FORMAT = 1
MANIFEST_NAME = "runtime-manifest.json"
# Present in the folder is a problem even if a manifest listed it (DEC-030).
FORBIDDEN_GLOBS = ("**/opencv_videoio_ffmpeg*.dll",)
# Folders where an unlisted file is a problem.
_CLOSED_FOLDERS = ("python", "app")
MAX_PROBLEMS = 20
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class RuntimeVerification:
    ok: bool
    problems: tuple[str, ...]
    seconds: float
    checked_files: int = 0


def _matches(relative: str, patterns: Sequence[str]) -> bool:
    """Case-insensitive glob match (Windows file names; an upper-case FFmpeg DLL must not slip through)."""
    relative = relative.lower()
    for pattern in patterns:
        pattern = pattern.lower()
        candidates = (pattern, pattern[3:]) if pattern.startswith("**/") else (pattern,)
        if any(fnmatch.fnmatchcase(relative, candidate) for candidate in candidates):
            return True
    return False


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _is_link(path: Path) -> bool:
    """Symbolic link, NTFS junction or any other reparse point."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except (OSError, ValueError):
        return False
    return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def _walk(root: Path, errors: list[str] | None = None):
    """Yield ``(relative posix path, absolute path, is_link)`` for every file under ``root``.

    Linked folders are reported, not entered.  Unreadable folders are appended to ``errors``.
    """
    def on_error(error: OSError) -> None:
        if errors is not None:
            name = getattr(error, "filename", None)
            try:
                errors.append(Path(name).relative_to(root).as_posix())
            except (TypeError, ValueError):
                errors.append(".")

    for directory, dirnames, filenames in os.walk(root, followlinks=False, onerror=on_error):
        base = Path(directory)
        for name in list(dirnames):
            if _is_link(base / name):
                dirnames.remove(name)
                yield (base / name).relative_to(root).as_posix(), base / name, True
        for name in filenames:
            path = base / name
            yield path.relative_to(root).as_posix(), path, _is_link(path)


def build_manifest(root: Path, *, version: str, excluded_globs: Sequence[str]) -> dict:
    """Manifest of every file under ``root`` that ``excluded_globs`` does not exclude.

    Symbolic links are refused (``ValueError``), and so is a file that
    ``FORBIDDEN_GLOBS`` names and ``excluded_globs`` does not exclude.
    """
    root = Path(root)
    resolved_root = root.resolve()
    files: dict[str, dict] = {}
    errors: list[str] = []
    entries = sorted(_walk(root, errors))
    if errors:
        raise ValueError(f"cartella non leggibile: {errors[0]}")
    for relative, path, is_link in entries:
        if relative == MANIFEST_NAME or _matches(relative, excluded_globs):
            continue
        if is_link:
            raise ValueError(f"collegamento simbolico non ammesso: {relative}")
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"percorso fuori dalla cartella: {relative}") from exc
        if _matches(relative, FORBIDDEN_GLOBS):
            raise ValueError(f"file non ammesso: {relative}")
        digest, size = _hash_file(path)
        files[relative] = {"sha256": digest, "size": size}
    return {"format": MANIFEST_FORMAT, "version": version, "files": files}


def write_manifest(manifest: dict, path: Path) -> None:
    """Write ``manifest`` as UTF-8 JSON with sorted keys."""
    Path(path).write_text(json.dumps(manifest, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def _load(manifest_path: Path) -> dict | str:
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Manifest del runtime non leggibile o non valido"
    if not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT:
        return "Formato del manifest del runtime non supportato"
    files = data.get("files")
    if not isinstance(files, dict):
        return "Manifest del runtime non valido: elenco dei file mancante"
    for relative, entry in files.items():
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("sha256"), str)
            or not isinstance(entry.get("size"), int)
            or isinstance(entry.get("size"), bool)
        ):
            return "Manifest del runtime non valido: voce non corretta"
    return data


def verify_installation(root: Path, manifest_path: Path) -> RuntimeVerification:
    """Check ``root`` against the manifest; never raises.

    Problems: a listed file that is missing, resized or altered; an unlisted
    file under ``python/`` or ``app/``; any file matching ``FORBIDDEN_GLOBS``.
    Limit (R5): extra files inside a ``__pycache__`` directory are ignored,
    because Python may write bytecode there; a planted ``.pyc`` therefore goes
    undetected (the launcher runs Python with ``-B``).  Missing or altered
    listed files in ``__pycache__`` are still reported.  At most 20 problems
    are listed, followed by a summary line.
    """
    started = perf_counter()
    root = Path(root)
    resolved_root = root.resolve()
    problems: list[str] = []
    data = _load(manifest_path)
    if isinstance(data, str):
        return RuntimeVerification(False, (data,), perf_counter() - started, 0)
    listed = data["files"]
    for relative in sorted(listed):
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or "\\" in relative or ":" in relative or not relative:
            problems.append(f"Percorso non valido nel manifest: {relative}")
            continue
        path = root / pure
        try:
            contained = path.resolve().is_relative_to(resolved_root)
        except (OSError, ValueError):
            contained = False
        if _is_link(path) or not contained:
            problems.append(f"Collegamento simbolico non ammesso: {relative}")
            continue
        if not path.is_file():
            problems.append(f"File mancante: {relative}")
            continue
        try:
            digest, size = _hash_file(path)
        except OSError:
            problems.append(f"File non leggibile: {relative}")
            continue
        entry = listed[relative]
        if size != entry["size"] or digest != entry["sha256"]:
            problems.append(f"File alterato: {relative}")
    walk_errors: list[str] = []
    for relative, _path, is_link in sorted(_walk(root, walk_errors)):
        parts = relative.split("/")
        if _matches(relative, FORBIDDEN_GLOBS):
            problems.append(f"File non ammesso (FFmpeg di OpenCV): {relative}")
        elif is_link:
            problems.append(f"Collegamento simbolico non ammesso: {relative}")
        # Exact-name comparison: a case-only rename of a listed file shows up as missing plus extra (fails closed).
        elif relative not in listed and parts[0] in _CLOSED_FOLDERS and "__pycache__" not in parts[:-1]:
            problems.append(f"File in più: {relative}")
    problems.extend(f"Cartella non leggibile: {name}" for name in walk_errors)
    problems = list(dict.fromkeys(problems))
    total = len(problems)
    shown = problems[:MAX_PROBLEMS]
    if total > MAX_PROBLEMS:
        shown.append(f"… e altri {total - MAX_PROBLEMS} problemi")
    return RuntimeVerification(total == 0, tuple(shown), perf_counter() - started, len(listed))
