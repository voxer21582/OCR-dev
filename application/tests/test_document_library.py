"""Library metadata: schema 4 migration, rename, tags and filtered search (REQ-081, 083, 084, 087)."""
from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from alfa_document_intelligence import local_document_store as store_module
from alfa_document_intelligence.local_document_store import LocalDocumentStore, StoreRejected

from test_local_document_store import FIXTURE, SyntheticProtector


def _record(index: int, *, family: str = "invoice", status: str = "not_started") -> tuple[dict, bytes]:
    source = f"%PDF-1.4 synthetic library fixture {index}\n%%EOF".encode()
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    digest = hashlib.sha256(source).hexdigest()

    def rebind(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "source_sha256":
                    value[key] = digest
                else:
                    rebind(item)
        elif isinstance(value, list):
            for item in value:
                rebind(item)

    rebind(record)
    record["document_id"] = f"doc-{index:03d}"
    record["source"].update({"sha256": digest, "byte_length": len(source), "original_filename": f"ricevuta-{index:03d}.pdf"})
    record["source"]["storage_ref"] = "volatile-session://not-for-archive"
    record["document_family"] = family
    record["review"]["status"] = status
    return record, source


class LibraryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "archive.sqlite3"
        self.protector = SyntheticProtector()
        self.store = LocalDocumentStore(self.database, protector=self.protector)


class SchemaV4MigrationTests(LibraryTestCase):
    def _make_v3_archive(self) -> tuple[str, str]:
        record, source = _record(1)
        self.store.save(record, source)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DROP TABLE document_library")
            connection.execute("PRAGMA user_version = 3")
        before = self.store.get("doc-001")
        return json.dumps(before.record, sort_keys=True), hashlib.sha256(before.source_bytes).hexdigest()

    def test_new_archives_use_schema_4(self):
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)

    def test_a_version_3_archive_migrates_without_changes(self):
        record_json, source_hash = self._make_v3_archive()
        migrated = LocalDocumentStore(self.database, protector=self.protector)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)
        stored = migrated.get("doc-001")
        self.assertEqual(json.dumps(stored.record, sort_keys=True), record_json)
        self.assertEqual(hashlib.sha256(stored.source_bytes).hexdigest(), source_hash)
        self.assertEqual(migrated.search_library()[0][0].tags, ())

    def test_an_interrupted_migration_leaves_version_3_usable(self):
        record_json, _ = self._make_v3_archive()
        with patch.object(store_module, "_LIBRARY_TABLE_SQL", "CREATE TABLE broken ("):
            with self.assertRaises(store_module.StoreSchemaError):
                LocalDocumentStore(self.database, protector=self.protector)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)
        reopened = LocalDocumentStore(self.database, protector=self.protector)
        self.assertEqual(json.dumps(reopened.get("doc-001").record, sort_keys=True), record_json)


class RenameAndTagTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        record, source = _record(1)
        self.store.save(record, source)

    def test_rename_and_tags_are_kept_with_who_and_when(self):
        self.store.set_display_name("doc-001", "  Cena cliente Rossi ", actor="synthetic-user")
        self.store.set_tags("doc-001", ["Trasferta Milano", "trasferta milano", " Cene ", "x" * 41], actor="synthetic-user")
        summary = self.store.search_library()[0][0]
        self.assertEqual(summary.display_name, "Cena cliente Rossi")
        self.assertEqual(summary.tags, ("Trasferta Milano", "Cene"))
        events = self.store.library_events("doc-001")
        self.assertEqual([event["kind"] for event in events], ["rename", "tags"])
        self.assertTrue(all(event["actor"] == "synthetic-user" and event["at"].endswith("+00:00") for event in events))
        self.assertEqual(self.store.get("doc-001").record["document_id"], "doc-001")  # the record itself is unchanged

    def test_metadata_is_encrypted_on_disk(self):
        self.store.set_display_name("doc-001", "Nome molto riconoscibile", actor="synthetic-user")
        self.assertNotIn(b"riconoscibile", self.database.read_bytes())

    def test_limits_and_unknown_documents(self):
        with self.assertRaises(StoreRejected):
            self.store.set_display_name("doc-001", "", actor="u")
        with self.assertRaises(StoreRejected):
            self.store.set_display_name("doc-001", "x" * 121, actor="u")
        with self.assertRaises(StoreRejected):
            self.store.set_tags("doc-001", [f"tag{n}" for n in range(21)], actor="u")
        with self.assertRaises(StoreRejected):
            self.store.set_tags("doc-999", ["a"], actor="u")

    def test_deleting_a_document_removes_its_metadata(self):
        self.store.set_tags("doc-001", ["privato"], actor="u")
        self.assertTrue(self.store.delete("doc-001"))
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_library").fetchone()[0], 0)


class FilteredSearchTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        for index in range(1, 13):
            family = "invoice" if index % 2 else "fiscal_receipt"
            status = "completed" if index % 3 == 0 else "not_started"
            record, source = _record(index, family=family, status=status)
            self.store.save(record, source)
        for index in (2, 4, 6):
            self.store.set_tags(f"doc-{index:03d}", ["Trasferta"], actor="u")
        self.store.set_display_name("doc-005", "Hotel Aurora", actor="u")

    def ids(self, **filters):
        results, total = self.store.search_library(**filters)
        return [item.document_id for item in results], total

    def test_filters_combine(self):
        self.assertEqual(self.ids(family="fiscal_receipt", tag="trasferta"), (["doc-002", "doc-004", "doc-006"], 3))
        self.assertEqual(self.ids(review_status="completed", family="invoice"), (["doc-003", "doc-009"], 2))
        self.assertEqual(self.ids(query="aurora"), (["doc-005"], 1))
        self.assertEqual(self.ids(query="ricevuta-011"), (["doc-011"], 1))

    def test_pages_and_offsets(self):
        first, total = self.ids(limit=5)
        second, _ = self.ids(limit=5, offset=5)
        third, _ = self.ids(limit=5, offset=10)
        self.assertEqual(total, 12)
        self.assertEqual(len(first + second + third), 12)
        self.assertEqual(len(set(first + second + third)), 12)
        self.assertEqual(self.ids(offset=50), ([], 12))

    def test_saved_date_range(self):
        today = self.store.search_library()[0][0].saved_at[:10]
        self.assertEqual(self.ids(saved_from=today, saved_to=today)[1], 12)
        self.assertEqual(self.ids(saved_to="2000-01-01")[1], 0)

    def test_bad_filters_are_rejected(self):
        for filters in ({"limit": 0}, {"offset": -1}, {"saved_from": "ieri"}):
            with self.subTest(filters=filters):
                with self.assertRaises(ValueError):
                    self.store.search_library(**filters)


class CaseLabelTests(LibraryTestCase):
    def _create_case(self):
        from test_expense_case_store import _case, _source_record

        source = b"%PDF synthetic statement for a case label"
        statement = _source_record("statement-label", source)
        return self.store.create_case(_case(statement), statement, source)

    def test_a_case_label_is_stored_without_changing_the_case(self):
        case = self._create_case()
        self.store.set_case_label(case["case_id"], "  Trasferta   Milano ", actor="synthetic-user")
        self.assertEqual(self.store.case_label(case["case_id"]), "Trasferta Milano")
        self.assertEqual(self.store.get_case(case["case_id"]), case, "identity, revision and history are unchanged")
        self.assertNotIn(b"Trasferta", self.database.read_bytes())

    def test_unknown_cases_and_bad_names_are_rejected(self):
        case = self._create_case()
        with self.assertRaises(StoreRejected):
            self.store.set_case_label("case-" + "0" * 36, "Trasferta", actor="u")
        with self.assertRaises(StoreRejected):
            self.store.set_case_label(case["case_id"], " ", actor="u")
        self.assertIsNone(self.store.case_label(case["case_id"]))

    def test_deleting_a_case_removes_its_label_and_its_documents_metadata(self):
        from test_expense_case_store import _source_record

        case = self._create_case()
        source = b"%PDF synthetic case-owned receipt"
        chunk = [{"record": _source_record("receipt-label", source, family="fiscal_receipt"), "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "chunk-1",
                                            self.store.case_chunk_digest(chunk), chunk)
        self.store.set_display_name("receipt-label", "Ricevuta del fascicolo", actor="u")
        self.store.set_tags("statement-label", ["privato"], actor="u")
        self.store.set_case_label(case["case_id"], "Trasferta", actor="u")
        self.assertTrue(self.store.delete_case(case["case_id"]))
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_library").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
