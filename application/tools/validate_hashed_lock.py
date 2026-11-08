"""Validate static, hash-pinned requirements files without installing packages."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ENTRY = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"==(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)"
    r" --hash=sha256:(?P<digest>[a-f0-9]{64})"
)


def parse_lock(text: str) -> dict[str, tuple[str, str]]:
    """Return normalized package names mapped to exact version and SHA-256."""
    entries: dict[str, tuple[str, str]] = {}
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENTRY.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid hash-pinned requirement at line {number}")
        name = re.sub(r"[-_.]+", "-", match["name"]).lower()
        if name in entries:
            raise ValueError(f"duplicate normalized package name at line {number}")
        entries[name] = (match["version"], match["digest"])
    if not entries:
        raise ValueError("requirements lock contains no package entries")
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    entries = parse_lock(args.lock.read_text(encoding="utf-8"))
    names = set(entries)
    required = {re.sub(r"[-_.]+", "-", name).lower() for name in args.require}
    excluded = {re.sub(r"[-_.]+", "-", name).lower() for name in args.exclude}
    if len(entries) != args.expected_count:
        raise SystemExit(
            f"{args.lock}: expected {args.expected_count} entries, found {len(entries)}"
        )
    if not required <= names or excluded & names:
        raise SystemExit(f"{args.lock}: required/excluded package constraints failed")
    print(f"{args.lock}: validated {len(entries)} exact pins with SHA-256 hashes")


if __name__ == "__main__":
    main()
