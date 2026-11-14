"""Synthetic storage tests for encrypted local expense-case manifests."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from alfa_document_intelligence.local_document_store import (
    LocalDocumentStore,
    StoreConcurrentUpdate,
    StoreIntegrityError,
    StoreRejected,
    StoreSourceConflict,
)
from test_local_document_store import SyntheticProtector


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_invoice.json"


def _source_record(document_id, source_bytes, family="expense_report"):
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    old_hash = record["source"]["sha256"]
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    record["document_id"] = document_id
    record["document_family"] = family
    record["source"]["sha256"] = source_hash
    record["source"]["storage_ref"] = f"volatile-session://{document_id}"
    record["source"]["byte_length"] = len(source_bytes)

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


def _case(statement_record):
    return {
        "schema_version": "0.1.0",
        "case_id": "case-001",
        "statement_document_id": statement_record["document_id"],
        "statement_sha256": statement_record["source"]["sha256"],
        "attachments": [],
        "chunks": [],
        "review_events": [],
        "inclusion_events": [],
        "processing": {"state": "not_started", "cursor": None, "result_bytes": 0},
    }


class ExpenseCaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "archive.sqlite3"
        self.protector = SyntheticProtector()
        self.store = LocalDocumentStore(self.path, protector=self.protector)

    def test_create_read_and_reopen_encrypted_case(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        created = self.store.create_case(_case(statement), statement, source)
        self.assertEqual(created["case_id"], "case-001")
        self.assertEqual(self.store.get_case("case-001"), created)
        reopened = LocalDocumentStore(self.path, protector=self.protector)
        self.assertEqual(reopened.get_case("case-001"), created)
        raw = self.path.read_bytes()
        self.assertNotIn(b"case-001", raw)
        self.assertNotIn(b"statement-001", raw)
        source_size = len(source)
        before = list(self.protector.unprotected_lengths)
        self.store.get_case("case-001")
        after = self.protector.unprotected_lengths[len(before):]
        self.assertNotIn(source_size, after, "case status reads must not decrypt source document bodies")

    def test_create_case_requires_safe_free_space_before_archiving_statement(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        with patch("alfa_document_intelligence.local_document_store.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(StoreRejected, "insufficient free space"):
                self.store.create_case(_case(statement), statement, source)
        self.assertIsNone(self.store.get_case("case-001"))
        self.assertIsNone(self.store.get("statement-001"))

    def test_save_case_uses_optimistic_revision_check(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        case = self.store.create_case(_case(statement), statement, source)
        changed = copy.deepcopy(case)
        changed["processing"]["state"] = "queued"
        saved = self.store.save_case(changed, expected_revision=case["case_revision"])
        self.assertEqual(saved["processing"]["state"], "queued")
        with self.assertRaises(StoreConcurrentUpdate):
            self.store.save_case(case, expected_revision=case["case_revision"])

    def test_v2_database_migrates_without_losing_independent_documents(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        self.store.save(statement, source)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("DROP TABLE cases")
            connection.execute("DROP TABLE case_documents")
            connection.execute("DROP TABLE document_retention")
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
        finally:
            connection.close()
        reopened = LocalDocumentStore(self.path, protector=self.protector)
        self.assertEqual(reopened.get("statement-001").source_bytes, source)
        self.assertEqual(reopened.get_case("case-001"), None)

    def test_case_payload_ciphertext_tampering_fails_closed(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        self.store.create_case(_case(statement), statement, source)
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute("SELECT entry_id, case_payload FROM cases").fetchone()
            damaged = bytes(row[1])[:-1] + bytes([bytes(row[1])[-1] ^ 1])
            connection.execute("UPDATE cases SET case_payload = ? WHERE entry_id = ?", (damaged, row[0]))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreIntegrityError):
            self.store.get_case("case-001")

    def test_case_document_binding_ciphertext_tampering_fails_closed(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        self.store.create_case(_case(statement), statement, source)
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute("SELECT entry_id, binding_payload FROM case_documents").fetchone()
            damaged = bytes(row[1])[:-1] + bytes([bytes(row[1])[-1] ^ 1])
            connection.execute("UPDATE case_documents SET binding_payload = ? WHERE entry_id = ?", (damaged, row[0]))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreIntegrityError):
            self.store.get_case("case-001")

    def test_case_creation_rejects_statement_source_mismatch_without_partial_write(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        with self.assertRaises(StoreRejected):
            self.store.create_case(_case(statement), statement, b"different")
        self.assertIsNone(self.store.get_case("case-001"))
        self.assertIsNone(self.store.get("statement-001"))

    def test_chunk_replay_is_idempotent_and_conflicting_replay_fails(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt one"
        record = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": record, "source_bytes": source}]
        digest = self.store.case_chunk_digest(chunk)
        updated = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", digest, chunk)
        replay = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", digest, chunk)
        self.assertEqual(replay, updated)
        with patch("alfa_document_intelligence.local_document_store.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            self.assertEqual(
                self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", digest, chunk),
                updated,
            )
        self.assertEqual(len(replay["attachments"]), 1)
        self.assertEqual(self.store.get("receipt-001").source_bytes, source)
        other = b"%PDF synthetic receipt changed"
        changed = [{"record": _source_record("receipt-001", other, family="fiscal_receipt"), "source_bytes": other}]
        with self.assertRaises(StoreSourceConflict):
            self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", self.store.case_chunk_digest(changed), changed)

    def test_oversized_record_metadata_is_rejected_before_storage(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        record = _source_record("receipt-001", source, family="fiscal_receipt")
        record["unbounded_metadata"] = "x" * (1024 * 1024 + 1)
        chunk = [{"record": record, "source_bytes": source}]
        with self.assertRaisesRegex(StoreRejected, "metadata.*limit"):
            self.store.case_chunk_digest(chunk)
        self.assertIsNone(self.store.get("receipt-001"))
        self.assertEqual(self.store.get_case(case["case_id"]), case)

    def test_chunk_digest_binds_record_metadata_not_only_source_bytes(self):
        source = b"%PDF synthetic receipt"
        original = _source_record("receipt-001", source, family="fiscal_receipt")
        changed_metadata = copy.deepcopy(original)
        changed_metadata["unbounded_metadata"] = "different"
        self.assertNotEqual(
            self.store.case_chunk_digest([{"record": original, "source_bytes": source}]),
            self.store.case_chunk_digest([{"record": changed_metadata, "source_bytes": source}]),
        )

    def test_chunk_digest_normalizes_server_generated_receipt_time_for_safe_retry(self):
        source = b"%PDF synthetic receipt"
        first = _source_record("receipt-001", source, family="fiscal_receipt")
        retry = copy.deepcopy(first)
        retry["source"]["received_at"] = "2026-11-11T12:34:56+00:00"
        self.assertEqual(
            self.store.case_chunk_digest([{"record": first, "source_bytes": source}]),
            self.store.case_chunk_digest([{"record": retry, "source_bytes": source}]),
        )

    def test_failed_chunk_does_not_leave_earlier_sources_or_manifest_references(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        existing_bytes = b"%PDF existing independent source"
        existing = _source_record("receipt-conflict", existing_bytes, family="fiscal_receipt")
        self.store.save(existing, existing_bytes)
        first_bytes = b"%PDF new source first in chunk"
        first = _source_record("receipt-new", first_bytes, family="fiscal_receipt")
        conflicting_bytes = b"%PDF different bytes for same id"
        conflicting = _source_record("receipt-conflict", conflicting_bytes, family="fiscal_receipt")
        chunk = [
            {"record": first, "source_bytes": first_bytes},
            {"record": conflicting, "source_bytes": conflicting_bytes},
        ]
        digest = self.store.case_chunk_digest(chunk)
        with self.assertRaises(StoreSourceConflict):
            self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-fails", digest, chunk)
        self.assertIsNone(self.store.get("receipt-new"))
        self.assertEqual(self.store.get_case(case["case_id"]), case)
        self.assertEqual(self.store.get("receipt-conflict").source_bytes, existing_bytes)

    def test_chunk_requires_twice_incoming_bytes_plus_64_mib_free_space(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        record = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": record, "source_bytes": source}]
        digest = self.store.case_chunk_digest(chunk)
        metadata_bytes = self.store._case_record_metadata_size(record)
        threshold = 2 * (len(source) + metadata_bytes) + 64 * 1024 * 1024
        with patch("alfa_document_intelligence.local_document_store.shutil.disk_usage", return_value=SimpleNamespace(free=threshold)):
            case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", digest, chunk)
        another = b"%PDF another synthetic receipt"
        second = [{"record": _source_record("receipt-002", another, family="fiscal_receipt"), "source_bytes": another}]
        with patch("alfa_document_intelligence.local_document_store.shutil.disk_usage", return_value=SimpleNamespace(free=2 * len(another) + 64 * 1024 * 1024 - 1)):
            with self.assertRaisesRegex(StoreRejected, "insufficient free space"):
                self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-2", self.store.case_chunk_digest(second), second)
        self.assertEqual(len(self.store.get_case(case["case_id"])["attachments"]), 1)

    def test_case_chunk_persists_in_five_bounded_chunks_up_to_one_hundred_attachments(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        for batch in range(5):
            records = []
            for offset in range(20):
                index = batch * 20 + offset
                source = f"%PDF synthetic receipt {index}".encode()
                records.append({
                    "record": _source_record(f"receipt-{index:03}", source, family="fiscal_receipt"),
                    "source_bytes": source,
                })
            digest = self.store.case_chunk_digest(records)
            case = self.store.append_case_chunk(case["case_id"], case["case_revision"], f"chunk-{batch}", digest, records)
        self.assertEqual(len(case["attachments"]), 100)
        source = b"%PDF synthetic receipt 101"
        record = _source_record("receipt-101", source, family="fiscal_receipt")
        chunk = [{"record": record, "source_bytes": source}]
        with self.assertRaisesRegex(StoreRejected, "100 supporting documents"):
            self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-101", self.store.case_chunk_digest(chunk), chunk)
        self.assertEqual(len(self.store.get_case(case["case_id"])["attachments"]), 100)

    def test_list_cases_filters_by_opaque_case_id(self):
        source = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", source)
        self.store.create_case(_case(statement), statement, source)
        self.assertEqual([item["case_id"] for item in self.store.list_cases("case-001")], ["case-001"])
        self.assertEqual(self.store.list_cases("absent"), [])

    def test_delete_case_preserves_shared_source_until_last_case_is_removed(self):
        statement_1_bytes = b"%PDF synthetic statement one"
        statement_1 = _source_record("statement-001", statement_1_bytes)
        case_1 = self.store.create_case(_case(statement_1), statement_1, statement_1_bytes)
        shared_bytes = b"%PDF synthetic shared receipt"
        shared_record = _source_record("receipt-shared", shared_bytes, family="fiscal_receipt")
        chunk = [{"record": shared_record, "source_bytes": shared_bytes}]
        case_1 = self.store.append_case_chunk(case_1["case_id"], case_1["case_revision"], "chunk-1", self.store.case_chunk_digest(chunk), chunk)

        statement_2_bytes = b"%PDF synthetic statement two"
        statement_2 = _source_record("statement-002", statement_2_bytes)
        manifest_2 = _case(statement_2)
        manifest_2["case_id"] = "case-002"
        case_2 = self.store.create_case(manifest_2, statement_2, statement_2_bytes)
        case_2 = self.store.append_case_chunk(case_2["case_id"], case_2["case_revision"], "chunk-2", self.store.case_chunk_digest(chunk), chunk)

        self.assertTrue(self.store.delete_case(case_1["case_id"]))
        self.assertIsNone(self.store.get("statement-001"))
        self.assertEqual(self.store.get("receipt-shared").source_bytes, shared_bytes)
        self.assertTrue(self.store.delete_case(case_2["case_id"]))
        self.assertIsNone(self.store.get("statement-002"))
        self.assertIsNone(self.store.get("receipt-shared"))

    def test_independently_saved_document_survives_case_deletion_and_direct_delete_is_blocked(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic independently saved receipt"
        receipt = _source_record("receipt-independent", source, family="fiscal_receipt")
        self.store.save(receipt, source)
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", self.store.case_chunk_digest(chunk), chunk)
        with self.assertRaisesRegex(StoreRejected, "bound to an active case"):
            self.store.delete("receipt-independent")
        self.assertTrue(self.store.delete_case(case["case_id"]))
        self.assertEqual(self.store.get("receipt-independent").source_bytes, source)

    def test_attachment_inclusion_changes_are_append_only_idempotent_and_source_bound(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1", self.store.case_chunk_digest(chunk), chunk)
        old_revision = case["case_revision"]
        excluded = self.store.append_attachment_inclusion_event(
            case["case_id"], old_revision, "receipt-001", receipt["source"]["sha256"],
            False, "not part of this expense", "event-1",
        )
        self.assertFalse(excluded["attachments"][0]["included"])
        self.assertEqual(len(excluded["inclusion_events"]), 1)
        replay = self.store.append_attachment_inclusion_event(
            case["case_id"], old_revision, "receipt-001", receipt["source"]["sha256"],
            False, "not part of this expense", "event-1",
        )
        self.assertEqual(replay, excluded)
        self.assertEqual(self.store.get("receipt-001").source_bytes, source)
        with self.assertRaises(StoreSourceConflict):
            self.store.append_attachment_inclusion_event(
                case["case_id"], old_revision, "receipt-001", receipt["source"]["sha256"],
                True, "changed replay", "event-1",
            )
        with self.assertRaises(StoreConcurrentUpdate):
            self.store.append_attachment_inclusion_event(
                case["case_id"], old_revision, "receipt-001", receipt["source"]["sha256"],
                True, "re-include", "event-2",
            )

    def test_processing_chunk_updates_records_and_case_in_one_revision(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "upload-1", self.store.case_chunk_digest(chunk), chunk)
        updated_record = copy.deepcopy(self.store.get("receipt-001").record)
        updated_record["language"] = "en"
        next_manifest = copy.deepcopy(case)
        next_manifest["processing"] = {
            "state": "completed", "cursor": "1", "result_bytes": 0,
            "committed_chunks": [],
        }
        saved = self.store.commit_case_processing_chunk(
            case["case_id"], case["case_revision"], "ocr-1", [updated_record], next_manifest,
            {"receipt-001": self.store.record_revision_sha256(self.store.get("receipt-001").record)},
        )
        self.assertEqual(self.store.get("receipt-001").record["language"], "en")
        self.assertEqual(saved["processing"]["state"], "completed")
        self.assertNotEqual(saved["case_revision"], case["case_revision"])

    def test_processing_chunk_failure_rolls_back_record_and_case(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "upload-1", self.store.case_chunk_digest(chunk), chunk)
        invalid_record = copy.deepcopy(self.store.get("receipt-001").record)
        invalid_record["source"]["sha256"] = "not-a-digest"
        next_manifest = copy.deepcopy(case)
        next_manifest["processing"] = {"state": "completed", "cursor": "1", "result_bytes": 0, "committed_chunks": []}
        with self.assertRaises(StoreRejected):
            self.store.commit_case_processing_chunk(
                case["case_id"], case["case_revision"], "ocr-1", [invalid_record], next_manifest,
                {"receipt-001": self.store.record_revision_sha256(self.store.get("receipt-001").record)},
            )
        self.assertEqual(self.store.get_case(case["case_id"]), case)
        self.assertNotEqual(self.store.get("receipt-001").record["source"]["sha256"], "not-a-digest")

    def test_processing_chunk_rejects_concurrent_same_source_record_edit(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-race", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-race", source, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(
            case["case_id"], case["case_revision"], "upload-race",
            self.store.case_chunk_digest(chunk), chunk,
        )
        original = self.store.get("receipt-race").record
        expected = self.store.record_revision_sha256(original)
        worker_output = copy.deepcopy(original)
        worker_output["language"] = "it"

        manual_edit = copy.deepcopy(original)
        manual_edit["language"] = "en"
        self.store.save(manual_edit, source, expected_record_sha256=expected)

        next_manifest = copy.deepcopy(case)
        next_manifest["processing"] = {
            "state": "completed", "cursor": "1", "result_bytes": 0,
            "committed_chunks": [],
        }
        with self.assertRaises(StoreConcurrentUpdate):
            self.store.commit_case_processing_chunk(
                case["case_id"], case["case_revision"], "ocr-race", [worker_output], next_manifest,
                {"receipt-race": expected},
            )
        self.assertEqual(self.store.get("receipt-race").record["language"], "en")
        self.assertEqual(self.store.get_case(case["case_id"]), case)


if __name__ == "__main__":
    unittest.main()
