"""Fail-closed privacy guard for synthetic JSON benchmark fixtures.

This is a narrow accidental-disclosure check, not a DLP or authorization system.
It scans only the explicitly allowlisted public benchmark inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

_ALLOWED_FILES = (
    "manifest.synthetic.json",
    "synthetic_development_labels.jsonl",
    "synthetic_development_predictions.jsonl",
    "synthetic_regression_labels.jsonl",
    "synthetic_regression_predictions.jsonl",
    "synthetic_frozen_smoke_labels.jsonl",
    "synthetic_frozen_smoke_predictions.jsonl",
)
_MAX_FILE_BYTES = 2 * 1024 * 1024
_FORBIDDEN_KEYS = {
    "employeeid", "employeeidentifier", "employeename", "personid",
    "personidentifier", "personname", "fullname", "personalname",
    "email", "emailaddress", "phone", "phonenumber", "filename",
    "filepath", "sourcepath", "storageref", "sourcetext", "ocrtext",
    "rawtext", "documentbytes", "documentimage", "claimid",
}
_PATTERNS = {
    "email-like value": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "Italian tax-code-like value": re.compile(r"(?i)\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"),
    "Italian IBAN-like value": re.compile(r"(?i)\bIT\d{2}[A-Z]\d{22}\b"),
    "Italian phone-like value": re.compile(r"(?<!\w)(?:\+39[ .-]?)?(?:0\d{1,3}|3\d{2})[ .-]?\d{5,8}(?!\w)"),
    "credential-like value": re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"),
    "private-key marker": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer credential": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}"),
}


class PublicDataGuardError(ValueError):
    """A public benchmark input violates the synthetic-only publication contract."""


def _walk(value: Any, path: str, issues: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold()) if isinstance(key, str) else ""
            if normalized_key in _FORBIDDEN_KEYS:
                issues.append(f"{path}: forbidden field name")
            _walk(child, path, issues)
    elif isinstance(value, list):
        for child in value:
            _walk(child, path, issues)
    elif isinstance(value, str):
        for description, pattern in _PATTERNS.items():
            if pattern.search(value):
                issues.append(f"{path}: contains {description}")


def scan_public_benchmark(root: str | Path) -> int:
    """Validate the allowlisted synthetic benchmark files and return file count."""
    directory = Path(root)
    issues: list[str] = []
    for name in _ALLOWED_FILES:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            issues.append(f"{name}: required regular file is missing")
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                issues.append(f"{name}: file exceeds size limit")
                continue
            content = path.read_text(encoding="utf-8")
            if name.endswith(".jsonl"):
                rows = []
                for line_no, line in enumerate(content.splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            issues.append(f"{name}:{line_no}: expected JSON object")
                        else:
                            rows.append(row)
                    except json.JSONDecodeError:
                        issues.append(f"{name}:{line_no}: invalid JSON")
                for index, row in enumerate(rows, 1):
                    _walk(row, f"{name}:record-{index}", issues)
            else:
                try:
                    document = json.loads(content)
                    if not isinstance(document, dict):
                        issues.append(f"{name}: expected JSON object")
                    else:
                        _walk(document, name, issues)
                except json.JSONDecodeError:
                    issues.append(f"{name}: invalid JSON")
        except (OSError, UnicodeError):
            issues.append(f"{name}: unreadable or non-UTF-8 file")
    if issues:
        raise PublicDataGuardError("\n".join(issues))
    return len(_ALLOWED_FILES)


_EVIDENCE_SUFFIXES = {".md", ".json", ".txt", ".csv"}
# Individually reviewed synthetic captures. A change requires a new review and hash.
# The guard cannot inspect pixels and does not establish that an image is synthetic.
_EVIDENCE_IMAGE_HASHES = {
    "M4/browser-alternatives.jpg": "4853149cf989f146423cad4ab6caa8851d29692a008e1a9b29787a8e73cf4fbf",
    "M4/browser-completed.jpg": "56cc37fa443c408e822db15704a4ae36999a1f9449a53e135ff00c578a6e5609",
    "M4/browser-screen.jpg": "2925d0366d7f375a0596a12cf01954b099d230b209bc266683a28bc4ee3ad183",
}
_EVIDENCE_PATTERNS = {
    # The phone pattern is omitted here: CI run ids and timings in evidence
    # files are long digit runs that would match it.
    **{k: v for k, v in _PATTERNS.items() if k != "Italian phone-like value"},
    # Windows (C:\Users\x), Git Bash (/c/Users/x) and POSIX (/home/x) forms.
    "user-profile path": re.compile(
        r"(?i)(?:\b[A-Z]:[\\/]+Users[\\/]+|(?<![\w.])/[A-Z]/Users/|(?<![\w.])/home/)(?!Public\b)[^\\/\s`'\"]+"
    ),
}


def scan_evidence_folder(root: str | Path) -> int:
    """Check every text evidence file under ``root`` and return how many were read.

    Messages name the file and the kind of match, never the matched text.
    """
    directory = Path(root)
    issues: list[str] = []
    checked = 0
    for path in sorted(directory.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            issues.append(f"{relative}: not an allowed evidence file")
            continue
        if path.suffix.casefold() == ".jpg":
            expected = _EVIDENCE_IMAGE_HASHES.get(relative)
            try:
                if not expected or path.stat().st_size > _MAX_FILE_BYTES:
                    raise ValueError("image not approved")
                data = path.read_bytes()
                if not data.startswith(b"\xff\xd8\xff") or hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError("image hash mismatch")
            except (OSError, ValueError):
                issues.append(f"{relative}: screenshot is not an approved exact image")
                continue
            checked += 1
            continue
        if path.suffix.casefold() not in _EVIDENCE_SUFFIXES:
            issues.append(f"{relative}: not an allowed evidence file")
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                issues.append(f"{relative}: file exceeds size limit")
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            issues.append(f"{relative}: unreadable or non-UTF-8 file")
            continue
        checked += 1
        for description, pattern in _EVIDENCE_PATTERNS.items():
            if pattern.search(content):
                issues.append(f"{relative}: contains {description}")
    if issues:
        raise PublicDataGuardError("\n".join(issues))
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("benchmark"))
    args = parser.parse_args()
    try:
        checked = scan_public_benchmark(args.root)
    except PublicDataGuardError as exc:
        print(f"public benchmark guard failed: {exc}")
        return 1
    print(f"public benchmark guard passed: {checked} allowlisted synthetic files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
