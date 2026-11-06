import copy
import json
from pathlib import Path

import pytest

from alfa_document_intelligence.expense_reports import (
    ExpenseReportBundleError,
    build_expense_report_bundle,
    validate_expense_report_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _document(document_id, family="fiscal_receipt", source_hash="a" * 64):
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    old_hash = record["source"]["sha256"]
    record["document_id"] = document_id
    record["document_family"] = family
    record["source"]["sha256"] = source_hash

    def replace_hashes(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "source_sha256" and child == old_hash:
                    value[key] = source_hash
                else:
                    replace_hashes(child)
        elif isinstance(value, list):
            for child in value:
                replace_hashes(child)

    replace_hashes(record)
    return record


def _documents():
    note = _document("note-001", "expense_report", "b" * 64)
    receipt_1 = _document("receipt-001", "fiscal_receipt", "a" * 64)
    receipt_2 = _document("receipt-002", "parking_receipt", "a" * 64)
    hotel = _document("hotel-001", "hotel_document", "c" * 64)
    return {item["document_id"]: item for item in (note, receipt_1, receipt_2, hotel)}


def test_bundle_preserves_note_and_attachment_order_without_merging_documents():
    documents = _documents()
    original = copy.deepcopy(documents)
    bundle = build_expense_report_bundle(
        "expense-report-001",
        "note-001",
        ["receipt-002", "receipt-001", "hotel-001"],
        documents,
    )

    assert bundle["expense_report_id"] == "expense-report-001"
    assert bundle["note_document_id"] == "note-001"
    assert [item["document_id"] for item in bundle["attachments"]] == [
        "receipt-002", "receipt-001", "hotel-001"
    ]
    assert [item["position"] for item in bundle["attachments"]] == [1, 2, 3]
    assert bundle["attachments"][0]["role"] == "supporting_document"
    assert bundle["review_status"] == "not_started"
    assert documents == original
    assert bundle["note_source_sha256"] == documents["note-001"]["source"]["sha256"]
    validate_expense_report_bundle(bundle, documents)


def test_duplicate_content_is_flagged_without_dropping_either_attachment():
    bundle = build_expense_report_bundle(
        "expense-report-001", "note-001", ["receipt-001", "receipt-002"], _documents()
    )

    assert [item["document_id"] for item in bundle["attachments"]] == ["receipt-001", "receipt-002"]
    assert bundle["duplicate_content_groups"] == [{
        "source_sha256": "a" * 64,
        "document_ids": ["receipt-001", "receipt-002"],
    }]
    assert bundle["findings"][0]["code"] == "duplicate_source_in_bundle"
    assert bundle["findings"][0]["outcome"] == "indeterminate"


def test_empty_bundle_stays_unreviewed_and_has_missing_attachment_finding():
    bundle = build_expense_report_bundle("expense-report-001", "note-001", [], _documents())

    assert bundle["attachments"] == []
    assert bundle["review_status"] == "not_started"
    assert bundle["findings"] == [{
        "code": "no_supporting_documents",
        "severity": "review",
        "outcome": "indeterminate",
        "document_ids": [],
    }]


def test_missing_note_or_attachment_is_rejected():
    documents = _documents()
    with pytest.raises(ExpenseReportBundleError, match="missing"):
        build_expense_report_bundle("case-1", "absent", [], documents)
    with pytest.raises(ExpenseReportBundleError, match="missing"):
        build_expense_report_bundle("case-1", "note-001", ["absent"], documents)


def test_note_must_be_expense_report_and_cannot_be_repeated_as_attachment():
    documents = _documents()
    documents["note-001"]["document_family"] = "invoice"
    with pytest.raises(ExpenseReportBundleError, match="expense_report family"):
        build_expense_report_bundle("case-1", "note-001", [], documents)

    documents["note-001"]["document_family"] = "expense_report"
    with pytest.raises(ExpenseReportBundleError, match="cannot also be attached"):
        build_expense_report_bundle("case-1", "note-001", ["note-001"], documents)


def test_duplicate_document_references_and_nested_expense_notes_are_rejected():
    documents = _documents()
    with pytest.raises(ExpenseReportBundleError, match="must be unique"):
        build_expense_report_bundle("case-1", "note-001", ["receipt-001", "receipt-001"], documents)

    nested = _document("note-002", "expense_report", "d" * 64)
    documents[nested["document_id"]] = nested
    with pytest.raises(ExpenseReportBundleError, match="cannot be another expense report"):
        build_expense_report_bundle("case-1", "note-001", ["note-002"], documents)


def test_bundle_rejects_tampering_and_invalid_source_records():
    documents = _documents()
    bundle = build_expense_report_bundle("case-1", "note-001", ["receipt-001"], documents)

    tampered = copy.deepcopy(bundle)
    tampered["attachments"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ExpenseReportBundleError, match="does not match"):
        validate_expense_report_bundle(tampered, documents)

    documents["receipt-001"]["source"]["sha256"] = "not-a-sha"
    with pytest.raises(ExpenseReportBundleError, match="violates its contract"):
        build_expense_report_bundle("case-1", "note-001", ["receipt-001"], documents)


def test_identifiers_must_be_opaque_and_valid():
    with pytest.raises(ExpenseReportBundleError, match="opaque"):
        build_expense_report_bundle("../path", "note-001", [], _documents())
