from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SPLITS = {"development", "regression", "independent_frozen"}
FAMILIES = {"invoice", "fiscal_receipt", "parking_receipt", "hotel_document", "pos_slip", "other", "unknown"}
LANGUAGES = {"it", "en", "mixed", "unknown"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_TOP_LEVEL = {"manifest_version", "records"}
_REQUIRED_RECORD = {"case_id", "sha256", "split", "document_family", "language", "label_version", "group_keys"}


def _canonical_bytes(records: list[dict[str, Any]]) -> bytes:
    ordered = sorted(records, key=lambda row: row["case_id"])
    return json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_manifest(
    manifest: dict[str, Any],
    expected_frozen_sha256: str | None = None,
    *,
    required_splits: set[str] | None = None,
) -> dict[str, Any]:
    """Validate a privacy-preserving split manifest and optionally pin its frozen set."""
    if not isinstance(manifest, dict) or set(manifest) != _REQUIRED_TOP_LEVEL or manifest.get("manifest_version") != "1":
        raise ValueError("manifest must contain only manifest_version and records, with version '1'")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list")

    ids: set[str] = set()
    hashes: set[str] = set()
    group_split: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for index, row in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(row, dict) or set(row) != _REQUIRED_RECORD:
            raise ValueError(f"{prefix} must contain only the required manifest fields")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in ids:
            raise ValueError(f"{prefix}.case_id must be unique and non-empty")
        ids.add(case_id)
        digest = row.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError(f"{prefix}.sha256 must be lowercase hexadecimal SHA-256")
        if digest in hashes:
            raise ValueError(f"{prefix}.sha256 duplicates another document")
        hashes.add(digest)
        split = row.get("split")
        if not isinstance(split, str) or split not in SPLITS:
            raise ValueError(f"{prefix}.split is unsupported")
        counts[split] += 1
        if not isinstance(row.get("document_family"), str) or row["document_family"] not in FAMILIES:
            raise ValueError(f"{prefix}.document_family is unsupported")
        if not isinstance(row.get("language"), str) or row["language"] not in LANGUAGES:
            raise ValueError(f"{prefix}.language is unsupported")
        label_version = row.get("label_version")
        if not isinstance(label_version, str) or not label_version.strip():
            raise ValueError(f"{prefix}.label_version is required")
        groups = row.get("group_keys")
        if not isinstance(groups, list) or any(not isinstance(key, str) or not _SHA256.fullmatch(key) for key in groups):
            raise ValueError(f"{prefix}.group_keys must be a list of 64-character keyed opaque hashes")
        if len(set(groups)) != len(groups):
            raise ValueError(f"{prefix}.group_keys must be unique within a record")
        for key in groups:
            previous = group_split.setdefault(key, split)
            if previous != split:
                raise ValueError(f"{prefix}.group_keys cross benchmark splits")

    required = SPLITS if required_splits is None else required_splits
    if not isinstance(required, set) or not required or not required <= SPLITS:
        raise ValueError("required_splits must be a non-empty subset of supported splits")
    missing = required - counts.keys()
    if missing:
        raise ValueError("required benchmark splits are missing")

    frozen_records = [row for row in records if row["split"] == "independent_frozen"]
    frozen_sha256 = hashlib.sha256(_canonical_bytes(frozen_records)).hexdigest()
    if expected_frozen_sha256 is not None:
        if not _SHA256.fullmatch(expected_frozen_sha256):
            raise ValueError("expected frozen manifest SHA-256 is malformed")
        if frozen_sha256 != expected_frozen_sha256:
            raise ValueError("independent frozen manifest SHA-256 mismatch")

    return {
        "records": len(records),
        "split_counts": {split: counts[split] for split in sorted(SPLITS)},
        "frozen_manifest_sha256": frozen_sha256,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a privacy-preserving OCR benchmark split manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-frozen-sha256")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = validate_manifest(manifest, args.expected_frozen_sha256)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
