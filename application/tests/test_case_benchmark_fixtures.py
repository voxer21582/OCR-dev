"""Synthetic case benchmark fixtures: counts, known answers and determinism."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pypdfium2
import pytest

from tools.case_benchmark_fixtures import generate_case_benchmark


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("case-benchmark")
    return root, generate_case_benchmark(root)


def test_counts(generated):
    root, _manifest = generated
    receipts = sorted((root / "receipts").iterdir())
    suffixes = [path.suffix for path in receipts]
    assert len(receipts) == 100
    assert suffixes.count(".png") == 60
    assert suffixes.count(".jpg") == 25
    assert suffixes.count(".pdf") == 15
    document = pypdfium2.PdfDocument(str(root / "statement.pdf"))
    try:
        assert len(document) == 4
    finally:
        document.close()


def test_known_answers(generated):
    _root, manifest = generated
    rows = manifest["statement_rows"]
    receipts = {item["receipt"]: item for item in manifest["receipts"]}
    assert manifest["version"] == "ocr2-case-benchmark-v1"
    assert len(rows) == 98
    assert sorted(row["amount"] for row in rows if row["receipt"] is None) == ["777,77", "888,88", "999,99"]
    assert sorted(n for n, item in receipts.items() if item["expected"] == "amount_conflict") == [10, 20, 30]
    assert sorted(n for n, item in receipts.items() if item["expected"] == "unused") == [96, 97, 98, 99, 100]
    assert sum(1 for row in rows if int(row["date"][-2:]) <= 12) == 43
    assert all(row["date"].startswith("2026-11-") and row["currency"] == "EUR" for row in rows)
    receipt_amounts = {item["amount"] for item in receipts.values()}
    for row in rows:
        if row["receipt"] is None:
            assert row["amount"] not in receipt_amounts
            continue
        receipt = receipts[row["receipt"]]
        assert row["date"] == receipt["date"]
        if receipt["expected"] == "amount_conflict":
            assert row["amount"] not in receipt_amounts
        else:
            assert receipt["expected"] == "match"
            assert row["amount"] == receipt["amount"]


def test_deterministic(generated, tmp_path):
    _root, manifest = generated
    assert generate_case_benchmark(tmp_path)["files"] == manifest["files"]


def test_manifest_hashes_match_files(generated):
    root, manifest = generated
    assert len(manifest["files"]) == 101
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert json.loads((root / "manifest.json").read_text(encoding="utf-8")) == manifest
