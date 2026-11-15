"""Synthetic field-accuracy benchmark: deterministic receipts and a numbers-only score (REQ-057)."""
from __future__ import annotations

import hashlib

import pytest

from tools.field_benchmark_fixtures import FIELDS, generate_field_benchmark
from tools.field_benchmark_score import first_value, score_records


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("field-benchmark")
    return root, generate_field_benchmark(root)


def test_sixty_receipts_half_italian_half_english(generated):
    root, manifest = generated
    documents = manifest["documents"]
    assert len(documents) == 60
    assert sum(1 for item in documents if item["language"] == "it") == 30
    assert {item["file"].rsplit(".", 1)[1] for item in documents} == {"png", "pdf"}
    for item in documents:
        assert set(item["expected"]) == set(FIELDS)
        assert hashlib.sha256((root / item["file"]).read_bytes()).hexdigest() == item["sha256"]


def test_generation_is_deterministic(generated, tmp_path):
    _root, manifest = generated
    assert [item["sha256"] for item in generate_field_benchmark(tmp_path)["documents"]] == [
        item["sha256"] for item in manifest["documents"]
    ]


def test_first_value_prefers_observed_then_first_alternative():
    assert first_value({"status": "observed", "value": "12.34", "alternatives": []}) == "12.34"
    assert first_value({"status": "uncertain", "value": None, "alternatives": [{"value": "a"}, {"value": "b"}]}) == "a"
    assert first_value(None) is None


def test_score_counts_matches_per_field_and_returns_numbers_only():
    manifest = {"documents": [
        {"document_id": "d1", "expected": {"total_amount": "12.34", "currency": "EUR"}},
        {"document_id": "d2", "expected": {"total_amount": "5.00", "currency": "EUR"}},
    ]}
    records = {
        "d1": {"fields": {"total_amount": {"status": "uncertain", "value": None, "alternatives": [{"value": "12.34"}]},
                          "currency": {"status": "uncertain", "value": None, "alternatives": [{"value": "EUR"}]}}},
        "d2": {"fields": {"total_amount": {"status": "uncertain", "value": None, "alternatives": [{"value": "50.00"}]}}},
    }
    score = score_records(manifest, records)
    assert score["total_amount"] == {"correct": 1, "total": 2, "rate": 0.5}
    assert score["currency"] == {"correct": 1, "total": 2, "rate": 0.5}
    assert all(isinstance(value, (int, float)) for item in score.values() for value in item.values())


def test_rules_find_every_field_when_the_text_is_read_perfectly():
    """Control for the OCR run: with ideal text the extraction rules score 100% on every field."""
    from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
    from alfa_document_intelligence.semantic_proposals import propose_common_fields
    from tools.field_benchmark_fixtures import _COUNT, _known

    documents, records = [], {}
    for index in range(_COUNT):
        known = _known(index)
        tokens = tuple(
            OCRToken(f"t{row}", line, ((0.05, 0.08 + row * 0.17), (0.9, 0.08 + row * 0.17),
                                       (0.9, 0.12 + row * 0.17), (0.05, 0.12 + row * 0.17)), 0.95)
            for row, line in enumerate(known["lines"])
        )
        page = OCRPageResult(source_sha256="c" * 64, page_number=1, engine_name="ideal", engine_version="1",
                             language="it+en", tokens=tokens)
        records[f"d{index}"] = {"fields": propose_common_fields([page])}
        documents.append({"document_id": f"d{index}", "expected": known["expected"]})
    score = score_records({"documents": documents}, records)
    assert {name: item["rate"] for name, item in score.items()} == {name: 1.0 for name in FIELDS}
