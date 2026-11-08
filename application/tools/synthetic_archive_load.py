"""Measure encrypted local archive operations using only a synthetic fixture."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from alfa_document_intelligence.local_document_store import LocalDocumentStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_invoice.json"
DEFAULT_COUNT = 1_000
MAX_COUNT = 10_000


def _count(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    if not 1 <= count <= MAX_COUNT:
        raise argparse.ArgumentTypeError(f"count must be from 1 to {MAX_COUNT}")
    return count


def _replace_source_hashes(value: object, source_hash: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_sha256":
                value[key] = source_hash
            else:
                _replace_source_hashes(item, source_hash)
    elif isinstance(value, list):
        for item in value:
            _replace_source_hashes(item, source_hash)


def run(count: int = DEFAULT_COUNT) -> dict[str, float | int]:
    if os.name != "nt":
        raise RuntimeError("the archive load benchmark requires Windows DPAPI")
    if not 1 <= count <= MAX_COUNT:
        raise ValueError(f"count must be from 1 to {MAX_COUNT}")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ocr2-synthetic-archive-load-") as temp:
        store = LocalDocumentStore(Path(temp) / "archive.sqlite3")
        started = time.perf_counter()
        last_id = ""
        last_source = b""
        for index in range(count):
            last_id = f"archive-bench-{index:06d}"
            last_source = f"%PDF-1.4\nsynthetic archive document {index}\n%%EOF".encode("ascii")
            record = copy.deepcopy(fixture)
            record["document_id"] = last_id
            record["source"]["original_filename"] = f"synthetic-{index:06d}.pdf"
            record["source"]["storage_ref"] = f"memory://archive-benchmark/{index}"
            record["source"]["sha256"] = hashlib.sha256(last_source).hexdigest()
            record["source"]["byte_length"] = len(last_source)
            _replace_source_hashes(record, record["source"]["sha256"])
            store.save(record, last_source)
        save_seconds = time.perf_counter() - started

        search_started = time.perf_counter()
        matches = store.search(f"synthetic-{count - 1:06d}.pdf")
        search_seconds = time.perf_counter() - search_started
        if len(matches) != 1 or matches[0].document_id != last_id:
            raise RuntimeError("synthetic archive search did not return exactly the expected record")

        get_started = time.perf_counter()
        reopened = store.get(last_id)
        get_seconds = time.perf_counter() - get_started
        if reopened is None or reopened.source_bytes != last_source:
            raise RuntimeError("synthetic archive record did not reopen with the exact source bytes")

        return {
            "documents": count,
            "save_total_seconds": round(save_seconds, 6),
            "save_mean_milliseconds": round(save_seconds * 1000 / count, 6),
            "search_seconds": round(search_seconds, 6),
            "get_seconds": round(get_seconds, 6),
            "temporary_database_bytes": store.path.stat().st_size,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure local encrypted archive save/search/reopen with synthetic documents only."
    )
    parser.add_argument("--documents", type=_count, default=DEFAULT_COUNT)
    args = parser.parse_args()
    print(json.dumps(run(args.documents), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
