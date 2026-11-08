import copy
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alfa_document_intelligence.local_document_store import (
    LocalDocumentStore,
    WindowsDpapiProtector,
    _validate_local_archive_path,
    StoreIntegrityError,
    StoreRejected,
    StoreSchemaError,
    StoreSourceConflict,
    StoreConcurrentUpdate,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_invoice.json"


class SyntheticProtector:
    """Authenticated deterministic test double; not production cryptography."""

    _key = b"synthetic-only-protector-key"

    def __init__(self):
        self.unprotected_lengths = []

    def protect(self, plaintext: bytes) -> bytes:
        ciphertext = bytes(value ^ 0xA5 for value in plaintext)
        tag = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        return b"TESTP1" + tag + ciphertext

    def unprotect(self, protected: bytes) -> bytes:
        if not protected.startswith(b"TESTP1") or len(protected) < 38:
            raise ValueError("invalid test ciphertext")
        tag, ciphertext = protected[6:38], protected[38:]
        expected = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("tampered test ciphertext")
        plaintext = bytes(value ^ 0xA5 for value in ciphertext)
        self.unprotected_lengths.append(len(plaintext))
        return plaintext


class LocalDocumentStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "archive.sqlite3"
        self.protector = SyntheticProtector()
        self.source = b"%PDF-1.4 synthetic invoice fixture\n%%EOF"
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.record["source"]["sha256"] = hashlib.sha256(self.source).hexdigest()
        self.record["source"]["storage_ref"] = "volatile-session://not-for-archive"
        self.record["source"]["byte_length"] = len(self.source)
        self._replace_source_hashes(self.record, self.record["source"]["sha256"])
        self.store = LocalDocumentStore(self.database, protector=self.protector)

    @classmethod
    def _replace_source_hashes(cls, value, source_hash):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "source_sha256":
                    value[key] = source_hash
                else:
                    cls._replace_source_hashes(item, source_hash)
        elif isinstance(value, list):
            for item in value:
                cls._replace_source_hashes(item, source_hash)

    def test_saved_record_and_exact_source_bytes_reopen_after_store_recreation(self):
        self.store.save(self.record, self.source)
        reopened = LocalDocumentStore(self.database, protector=self.protector).get(
            "synthetic-invoice-001"
        )
        self.assertEqual(reopened.source_bytes, self.source)
        self.assertEqual(reopened.record["source"]["sha256"], hashlib.sha256(self.source).hexdigest())
        self.assertEqual(reopened.record["source"]["storage_ref"], "local-archive://synthetic-invoice-001")

    def test_source_hash_mismatch_is_rejected_before_storage(self):
        with self.assertRaises(StoreRejected):
            self.store.save(self.record, b"different synthetic bytes")
        self.assertIsNone(self.store.get("synthetic-invoice-001"))

    def test_source_above_configured_limit_is_rejected(self):
        store = LocalDocumentStore(self.database, protector=self.protector, max_document_bytes=8)
        with self.assertRaises(StoreRejected):
            store.save(self.record, self.source)

    def test_network_archive_path_is_rejected(self):
        with self.assertRaises(StoreRejected):
            LocalDocumentStore(r"\\server\share\archive.sqlite3", protector=self.protector)

    def test_mapped_network_drive_is_rejected_by_path_classifier(self):
        with self.assertRaises(StoreRejected):
            _validate_local_archive_path(
                r"Z:\archive.sqlite3", drive_type_lookup=lambda root: 4
            )

    def test_reparse_path_component_is_rejected_without_following_it(self):
        def synthetic_lstat(path):
            class Metadata:
                st_file_attributes = 0x400 if path.endswith("\\private") else 0
            return Metadata()

        with self.assertRaises(StoreRejected):
            _validate_local_archive_path(
                r"C:\synthetic\private\archive.sqlite3",
                drive_type_lookup=lambda root: 3,
                lstat_lookup=synthetic_lstat,
            )

    def test_configured_limit_cannot_exceed_import_ceiling(self):
        with self.assertRaises(ValueError):
            LocalDocumentStore(self.database, protector=self.protector, max_document_bytes=25 * 1024 * 1024 + 1)

    def test_recorded_byte_length_must_match_source(self):
        invalid = copy.deepcopy(self.record)
        invalid["source"]["byte_length"] += 1
        with self.assertRaises(StoreRejected):
            self.store.save(invalid, self.source)

    def test_non_json_record_data_is_rejected_before_protection(self):
        invalid = copy.deepcopy(self.record)
        invalid["unexpected"] = {"not": {1, 2}}
        with self.assertRaises(StoreRejected):
            self.store.save(invalid, self.source)
        self.assertIsNone(self.store.get("synthetic-invoice-001"))

    def test_empty_source_is_rejected(self):
        empty_record = copy.deepcopy(self.record)
        empty_record["source"]["sha256"] = hashlib.sha256(b"").hexdigest()
        empty_record["source"]["byte_length"] = 0
        self._replace_source_hashes(empty_record, empty_record["source"]["sha256"])
        with self.assertRaises(StoreRejected):
            self.store.save(empty_record, b"")

    def test_same_document_id_can_update_record_without_changing_source(self):
        self.store.save(self.record, self.source)
        revised = copy.deepcopy(self.record)
        revised["language"] = "en"
        self.store.save(revised, self.source)
        self.assertEqual(self.store.get("synthetic-invoice-001").record["language"], "en")
        self.assertEqual(len(self.store.search("synthetic-invoice-001")), 1)

    def test_compare_and_save_rejects_stale_record_atomically(self):
        self.store.save(self.record, self.source)
        original = self.store.get("synthetic-invoice-001").record
        original_digest = hashlib.sha256(
            json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        changed = copy.deepcopy(original)
        changed["source"]["original_filename"] = "updated-elsewhere.pdf"
        self.store.save(changed, self.source)
        stale = copy.deepcopy(original)
        stale["review"]["status"] = "in_progress"
        with self.assertRaises(StoreConcurrentUpdate):
            self.store.save(stale, self.source, expected_record_sha256=original_digest)
        self.assertEqual(
            self.store.get("synthetic-invoice-001").record["source"]["original_filename"],
            "updated-elsewhere.pdf",
        )

    def test_schema_v1_migrates_to_an_opaque_document_id_index(self):
        legacy_database = Path(self.temp.name) / "legacy-v1.sqlite3"
        legacy_record = copy.deepcopy(self.record)
        legacy_record["source"]["storage_ref"] = "local-archive://synthetic-invoice-001"
        envelope = {
            "format_version": 1,
            "record": legacy_record,
            "saved_at": "2026-11-06T00:00:00+00:00",
        }
        protected_record = self.protector.protect(
            json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        )
        protected_source = self.protector.protect(self.source)
        connection = sqlite3.connect(legacy_database)
        try:
            connection.execute(
                "CREATE TABLE documents (entry_id TEXT PRIMARY KEY, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
            )
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?)",
                ("legacy-entry", protected_record, protected_source),
            )
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        finally:
            connection.close()
        migrated = LocalDocumentStore(legacy_database, protector=self.protector)
        reopened = migrated.get("synthetic-invoice-001")
        self.assertIsNotNone(reopened)
        self.assertEqual(reopened.source_bytes, self.source)
        raw_database = legacy_database.read_bytes()
        self.assertNotIn(b"synthetic-invoice-001", raw_database)
        connection = sqlite3.connect(legacy_database)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
            indexes = connection.execute("PRAGMA index_list(documents)").fetchall()
            self.assertIn("document_id_index", columns)
            self.assertTrue(any(row[1] == "documents_document_id_index_unique" and row[2] for row in indexes))
            metadata_count = connection.execute("SELECT COUNT(*) FROM store_metadata").fetchone()[0]
            self.assertEqual(metadata_count, 1)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            connection.close()

    def test_schema_v1_without_entry_id_primary_key_is_rejected_before_migration(self):
        malformed = Path(self.temp.name) / "legacy-v1-without-primary-key.sqlite3"
        connection = sqlite3.connect(malformed)
        try:
            connection.execute(
                "CREATE TABLE documents (entry_id TEXT, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
            )
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreSchemaError):
            LocalDocumentStore(malformed, protector=self.protector)
        connection = sqlite3.connect(malformed)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertNotIn(
                "document_id_index",
                {row[1] for row in connection.execute("PRAGMA table_info(documents)")},
            )
        finally:
            connection.close()

    def test_schema_v1_with_null_entry_id_is_rejected_before_migration(self):
        malformed = Path(self.temp.name) / "legacy-v1-null-entry-id.sqlite3"
        connection = sqlite3.connect(malformed)
        try:
            connection.execute(
                "CREATE TABLE documents (entry_id TEXT PRIMARY KEY, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
            )
            connection.execute("INSERT INTO documents VALUES (NULL, ?, ?)", (b"encrypted", b"encrypted"))
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreSchemaError):
            LocalDocumentStore(malformed, protector=self.protector)
        connection = sqlite3.connect(malformed)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertIsNone(connection.execute("SELECT entry_id FROM documents").fetchone()[0])
        finally:
            connection.close()

    def test_schema_v2_without_entry_id_primary_key_fails_closed(self):
        malformed = Path(self.temp.name) / "v2-without-primary-key.sqlite3"
        LocalDocumentStore(malformed, protector=self.protector)
        connection = sqlite3.connect(malformed)
        try:
            connection.execute("DROP TABLE documents")
            connection.execute(
                "CREATE TABLE documents (entry_id TEXT, document_id_index TEXT NOT NULL, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX documents_document_id_index_unique ON documents(document_id_index)"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreSchemaError):
            LocalDocumentStore(malformed, protector=self.protector)

    def test_schema_v2_nullable_entry_id_fails_closed(self):
        malformed = Path(self.temp.name) / "v2-nullable-entry-id.sqlite3"
        LocalDocumentStore(malformed, protector=self.protector)
        connection = sqlite3.connect(malformed)
        try:
            connection.execute("DROP TABLE documents")
            connection.execute(
                "CREATE TABLE documents (entry_id TEXT PRIMARY KEY, document_id_index TEXT NOT NULL, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX documents_document_id_index_unique ON documents(document_id_index)"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreSchemaError):
            LocalDocumentStore(malformed, protector=self.protector)

    def test_tampered_document_id_index_fails_closed(self):
        self.store.save(self.record, self.source)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE documents SET document_id_index = ?",
                ("0" * 64,),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreIntegrityError):
            self.store.save(self.record, self.source)
        with self.assertRaises(StoreIntegrityError):
            self.store.search("synthetic")
        with self.assertRaises(StoreIntegrityError):
            LocalDocumentStore(self.database, protector=self.protector)

    def test_existing_document_id_cannot_replace_its_source_bytes(self):
        self.store.save(self.record, self.source)
        changed = copy.deepcopy(self.record)
        new_source = b"%PDF-1.4 different source\n%%EOF"
        changed["source"]["sha256"] = hashlib.sha256(new_source).hexdigest()
        changed["source"]["byte_length"] = len(new_source)
        self._replace_source_hashes(changed, changed["source"]["sha256"])
        with self.assertRaises(StoreSourceConflict):
            self.store.save(changed, new_source)
        self.assertEqual(self.store.get("synthetic-invoice-001").source_bytes, self.source)

    def test_sqlite_contains_ciphertext_not_record_or_source_plaintext(self):
        self.store.save(self.record, self.source)
        raw_database = self.database.read_bytes()
        self.assertNotIn(self.source, raw_database)
        self.assertNotIn(b"synthetic-invoice-001", raw_database)
        self.assertNotIn(b"synthetic-invoice.pdf", raw_database)

    def test_search_is_local_case_insensitive_and_treats_query_as_data(self):
        self.store.save(self.record, self.source)
        results = self.store.search("SYNTHETIC-INVOICE.PDF")
        self.assertEqual([item.document_id for item in results], ["synthetic-invoice-001"])
        self.assertEqual(self.store.search("%' OR 1=1 --"), [])

    def test_search_does_not_decrypt_the_large_source_blob(self):
        large_source = self.source + (b"X" * (128 * 1024))
        record = copy.deepcopy(self.record)
        record["source"]["sha256"] = hashlib.sha256(large_source).hexdigest()
        record["source"]["byte_length"] = len(large_source)
        self._replace_source_hashes(record, record["source"]["sha256"])
        self.store.save(record, large_source)
        self.protector.unprotected_lengths.clear()

        results = self.store.search("synthetic-invoice.pdf")

        self.assertEqual([item.document_id for item in results], ["synthetic-invoice-001"])
        self.assertEqual(len(self.protector.unprotected_lengths), 1)
        self.assertLess(self.protector.unprotected_lengths[0], 16 * 1024)

    def test_delete_removes_the_saved_document(self):
        self.store.save(self.record, self.source)
        self.assertTrue(self.store.delete("synthetic-invoice-001"))
        self.assertIsNone(self.store.get("synthetic-invoice-001"))
        self.assertFalse(self.store.delete("synthetic-invoice-001"))

    def test_tampered_ciphertext_fails_closed(self):
        self.store.save(self.record, self.source)
        connection = sqlite3.connect(self.database)
        try:
            entry_id, payload = connection.execute("SELECT entry_id, record_payload FROM documents").fetchone()
            changed = bytes(payload[:-1]) + bytes([payload[-1] ^ 1])
            connection.execute("UPDATE documents SET record_payload = ? WHERE entry_id = ?", (changed, entry_id))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreIntegrityError):
            self.store.get("synthetic-invoice-001")

    def test_tampered_source_ciphertext_fails_closed_when_opened(self):
        self.store.save(self.record, self.source)
        connection = sqlite3.connect(self.database)
        try:
            entry_id, payload = connection.execute("SELECT entry_id, source_payload FROM documents").fetchone()
            changed = bytes(payload[:-1]) + bytes([payload[-1] ^ 1])
            connection.execute("UPDATE documents SET source_payload = ? WHERE entry_id = ?", (changed, entry_id))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreIntegrityError):
            self.store.get("synthetic-invoice-001")

    def test_unsupported_database_schema_fails_closed(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("PRAGMA user_version = 99")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StoreSchemaError):
            LocalDocumentStore(self.database, protector=self.protector)

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI integration")
    def test_windows_dpapi_protects_and_reopens_synthetic_archive(self):
        protector = WindowsDpapiProtector()
        protected = protector.protect(b"synthetic DPAPI round-trip")
        self.assertNotEqual(protected, b"synthetic DPAPI round-trip")
        self.assertEqual(protector.unprotect(protected), b"synthetic DPAPI round-trip")

        dpapi_database = Path(self.temp.name) / "dpapi.sqlite3"
        store = LocalDocumentStore(dpapi_database)
        store.save(self.record, self.source)
        reopened = LocalDocumentStore(dpapi_database).get("synthetic-invoice-001")
        self.assertEqual(reopened.source_bytes, self.source)
        self.assertEqual(reopened.record["source"]["sha256"], hashlib.sha256(self.source).hexdigest())


if __name__ == "__main__":
    unittest.main()
