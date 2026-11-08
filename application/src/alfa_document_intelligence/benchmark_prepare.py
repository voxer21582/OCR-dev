"""Prepare a private, source-hash benchmark manifest without copying documents.

This tool reads only local file bytes for SHA-256 calculation. It never decodes,
renders, OCRs, or uploads the files. Run it only after the benchmark governance
record authorizes the local source and output environment.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

from .benchmark_manifest import FAMILIES, LANGUAGES, SPLITS, validate_manifest


_REQUIRED_COLUMNS = {
    "relative_path",
    "split",
    "document_family",
    "language",
    "label_version",
    "group_keys_json",
}
_ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
_DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024
_GROUP_VALUE = re.compile(r"^[a-z][a-z0-9_-]{0,31}:.{1,256}$", re.IGNORECASE)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_repository_path(path: Path, repository_root: Path, *, description: str) -> None:
    resolved = path.resolve()
    if _inside(resolved, repository_root):
        raise ValueError(f"{description} must be outside the project repository")


def _sha256_file(path: Path, *, max_file_bytes: int) -> str:
    try:
        before = path.stat()
        if not path.is_file() or path.is_symlink():
            raise ValueError("source file is not a regular file")
        if before.st_size <= 0 or before.st_size > max_file_bytes:
            raise ValueError("source file is empty or exceeds the configured byte limit")
        digest = hashlib.sha256()
        read_bytes = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                read_bytes += len(chunk)
                if read_bytes > max_file_bytes:
                    raise ValueError("source file exceeds the configured byte limit")
                digest.update(chunk)
        after = path.stat()
        before_identity = (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_ino)
        after_identity = (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino)
        if before_identity != after_identity:
            raise ValueError("source file changed while being hashed")
        if read_bytes != before.st_size:
            raise ValueError("source file size changed while being hashed")
        return digest.hexdigest()
    except OSError as exc:
        raise ValueError("source file could not be read") from exc


def _opaque_hmac(key: bytes, purpose: str, value: str) -> str:
    message = b"alfa-benchmark-manifest-v1\0" + purpose.encode("ascii") + b"\0" + value.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _read_assignments(path: Path, *, selected_split: str) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if (
                reader.fieldnames is None
                or len(reader.fieldnames) != len(_REQUIRED_COLUMNS)
                or set(reader.fieldnames) != _REQUIRED_COLUMNS
            ):
                raise ValueError("assignment CSV columns do not match the required contract")
            rows = []
            for index, row in enumerate(reader, start=2):
                if row is None or None in row or any(value is None for value in row.values()):
                    raise ValueError(f"assignment row {index} is malformed")
                if row["split"] not in SPLITS:
                    raise ValueError(f"assignment row {index} has an unsupported split")
                if row["split"] != selected_split:
                    raise ValueError(f"assignment row {index} is outside the selected split")
                if row["document_family"] not in FAMILIES:
                    raise ValueError(f"assignment row {index} has an unsupported document family")
                if row["language"] not in LANGUAGES:
                    raise ValueError(f"assignment row {index} has an unsupported language")
                label_version = row["label_version"].strip()
                if not label_version or len(label_version) > 64:
                    raise ValueError(f"assignment row {index} has an invalid label version")
                try:
                    raw_groups = json.loads(row["group_keys_json"])
                except json.JSONDecodeError as exc:
                    raise ValueError(f"assignment row {index} group_keys_json is invalid") from exc
                if not isinstance(raw_groups, list) or not raw_groups:
                    raise ValueError(f"assignment row {index} requires at least one group key")
                if any(not isinstance(item, str) or not _GROUP_VALUE.fullmatch(item.strip()) for item in raw_groups):
                    raise ValueError(f"assignment row {index} has an invalid group key")
                groups = [item.strip() for item in raw_groups]
                if len(set(groups)) != len(groups):
                    raise ValueError(f"assignment row {index} repeats a group key")
                rows.append({
                    "relative_path": row["relative_path"],
                    "split": row["split"],
                    "document_family": row["document_family"],
                    "language": row["language"],
                    "label_version": label_version,
                    "group_keys": groups,
                    "row_number": index,
                })
    except OSError as exc:
        raise ValueError("assignment CSV could not be read") from exc
    if not rows:
        raise ValueError("assignment CSV contains no data rows")
    return rows


def _resolve_source(root: Path, relative_path: str) -> Path:
    if not relative_path or "\0" in relative_path or "\\" in relative_path:
        raise ValueError("assignment contains an invalid relative source path")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("assignment contains an unsafe relative source path")
    candidate = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("symbolic links are not permitted in the source tree")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError("assignment source is missing or outside the source root") from exc
    if resolved.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError("assignment source format is unsupported")
    return resolved


def prepare_manifest(
    *,
    source_root: Path,
    assignment_csv: Path,
    output_dir: Path,
    hmac_key: bytes,
    repository_root: Path,
    split: str,
    max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Hash locally assigned source files and write manifest plus private path map."""
    if split not in SPLITS:
        raise ValueError("selected split is unsupported")
    root = source_root.resolve(strict=True)
    repo = repository_root.resolve(strict=True)
    assignments_candidate = assignment_csv.resolve()
    out = output_dir.resolve()
    if not root.is_dir():
        raise ValueError("source root must be a directory")
    _reject_repository_path(root, repo, description="source root")
    _reject_repository_path(assignments_candidate, repo, description="assignment CSV")
    _reject_repository_path(out, repo, description="private output directory")
    assignments_path = assignment_csv.resolve(strict=True)
    if not isinstance(hmac_key, bytes) or len(hmac_key) < 32:
        raise ValueError("HMAC key must contain at least 32 bytes")
    if not isinstance(max_file_bytes, int) or isinstance(max_file_bytes, bool) or max_file_bytes <= 0:
        raise ValueError("max_file_bytes must be a positive integer")
    if out.exists():
        raise ValueError("private output directory already exists")

    assignments = _read_assignments(assignments_path, selected_split=split)
    manifest_rows = []
    mapping_rows = []
    seen_paths: set[str] = set()
    for row in assignments:
        relative_path = row["relative_path"]
        if relative_path in seen_paths:
            raise ValueError(f"assignment row {row['row_number']} duplicates a source path")
        seen_paths.add(relative_path)
        source = _resolve_source(root, relative_path)
        digest = _sha256_file(source, max_file_bytes=max_file_bytes)
        case_id = "case-" + _opaque_hmac(hmac_key, "case-id", relative_path)[:32]
        group_keys = sorted({
            _opaque_hmac(hmac_key, "group-key", value)
            for value in row["group_keys"]
        })
        manifest_rows.append({
            "case_id": case_id,
            "sha256": digest,
            "split": row["split"],
            "document_family": row["document_family"],
            "language": row["language"],
            "label_version": row["label_version"],
            "group_keys": group_keys,
        })
        mapping_rows.append({
            "case_id": case_id,
            "relative_path": relative_path,
            "sha256": digest,
        })

    manifest = {"manifest_version": "1", "records": manifest_rows}
    summary = validate_manifest(manifest, required_splits={split})
    if split != "independent_frozen":
        summary.pop("frozen_manifest_sha256", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".alfa-benchmark-", dir=out.parent))
    try:
        manifest_path = temp_dir / "manifest.fragment.private.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        mapping_path = temp_dir / "source-map.private.csv"
        with mapping_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["case_id", "relative_path", "sha256"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(mapping_rows)
        os.chmod(manifest_path, 0o600)
        os.chmod(mapping_path, 0o600)
        temp_dir.rename(out)
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create private OCR benchmark metadata from locally authorized documents"
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--assignments", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--split", required=True, choices=sorted(SPLITS))
    parser.add_argument("--max-file-bytes", type=int, default=_DEFAULT_MAX_FILE_BYTES)
    args = parser.parse_args()

    first = getpass.getpass("HMAC key (at least 32 characters; do not reuse a public key): ")
    second = getpass.getpass("Confirm HMAC key: ")
    if first != second:
        parser.error("HMAC key confirmation did not match")
    try:
        result = prepare_manifest(
            source_root=args.source_root,
            assignment_csv=args.assignments,
            output_dir=args.output_dir,
            hmac_key=first.encode("utf-8"),
            repository_root=Path(__file__).resolve().parents[2],
            split=args.split,
            max_file_bytes=args.max_file_bytes,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
