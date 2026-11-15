"""Interrupted writes leave the archive intact and retryable (REQ-082, REQ-012, REQ-087).

A fault is injected at every write statement, and at the commit, of ``save``,
``append_case_chunk`` and ``commit_case_processing_chunk``. After each fault the
archive is reopened (which runs its integrity checks), must equal its state
before the attempt, and the same operation must then succeed.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from alfa_document_intelligence import local_document_store as store_module
from alfa_document_intelligence.document_decoder import DecodeLimits
from alfa_document_intelligence.expense_case_processing import ExpenseCaseProcessingManager
from alfa_document_intelligence.local_document_store import LocalDocumentStore, StoreError

import test_expense_case_processing as processing
from test_expense_case_store import _case, _source_record
from test_local_document_store import SyntheticProtector

_WRITES = ("INSERT", "UPDATE", "DELETE", "REPLACE")
_real_connect = sqlite3.connect


class _Injected(sqlite3.OperationalError):
    pass


class _FaultyConnection:
    """Delegates to a real connection and fails at the chosen write or at commit."""

    def __init__(self, connection, plan):
        self._connection = connection
        self._plan = plan

    def execute(self, sql, *args):
        if sql.lstrip().upper().startswith(_WRITES):
            self._plan["writes"] += 1
            if self._plan["writes"] == self._plan.get("fail_write"):
                raise _Injected("injected write fault")
        return self._connection.execute(sql, *args)

    def executemany(self, sql, *args):
        if sql.lstrip().upper().startswith(_WRITES):
            self._plan["writes"] += 1
            if self._plan["writes"] == self._plan.get("fail_write"):
                raise _Injected("injected write fault")
        return self._connection.executemany(sql, *args)

    def commit(self):
        if self._plan.get("fail_commit"):
            raise _Injected("injected commit fault")
        return self._connection.commit()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, *exc):
        return self._connection.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class _FaultySqlite:
    """Stands in for the ``sqlite3`` module inside the store during one attempt."""

    def __init__(self, plan):
        self._plan = plan

    def connect(self, *args, **kwargs):
        return _FaultyConnection(_real_connect(*args, **kwargs), self._plan)

    def __getattr__(self, name):
        return getattr(sqlite3, name)


class InterruptedWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "archive.sqlite3"
        self.protector = SyntheticProtector()
        self.store = LocalDocumentStore(self.path, protector=self.protector)

    def _state(self):
        reopened = LocalDocumentStore(self.path, protector=self.protector)
        documents, _ = reopened.search_library(limit=200)
        state = []
        for summary in documents:
            stored = reopened.get(summary.document_id)
            state.append((summary.document_id, reopened.record_revision_sha256(stored.record),
                          hashlib.sha256(stored.source_bytes).hexdigest()))
        cases = [reopened.get_case(item["case_id"]) if isinstance(item, dict) else reopened.get_case(item.case_id)
                 for item in reopened.list_cases(limit=100)]
        return state, cases

    def _check_every_fault(self, operation_factory):
        """Count the writes of a clean run, then fail at each one and at commit, from the same starting file."""
        snapshot = self.path.read_bytes()
        plan = {"writes": 0}
        with patch.object(store_module, "sqlite3", _FaultySqlite(plan)):
            operation_factory(LocalDocumentStore(self.path, protector=self.protector))()
        total = plan["writes"]
        self.assertGreater(total, 0)
        faults = [{"fail_write": n} for n in range(1, total + 1)] + [{"fail_commit": True}]
        for fault in faults:
            with self.subTest(fault=fault):
                self.path.write_bytes(snapshot)
                before = self._state()
                store = LocalDocumentStore(self.path, protector=self.protector)
                plan = {"writes": 0, **fault}
                with patch.object(store_module, "sqlite3", _FaultySqlite(plan)):
                    with self.assertRaises((StoreError, sqlite3.Error)):
                        operation_factory(store)()
                self.assertEqual(self._state(), before, "a failed write must leave no trace")
                operation_factory(LocalDocumentStore(self.path, protector=self.protector))()
                self.assertNotEqual(self._state(), before, "the retried write succeeds")

    def test_document_save(self):
        source = b"%PDF synthetic interrupted save"
        record = _source_record("doc-fault", source, family="fiscal_receipt")
        self._check_every_fault(lambda store: lambda: store.save(copy.deepcopy(record), source))

    def test_append_case_chunk(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt one"
        record = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": record, "source_bytes": source}]
        digest = self.store.case_chunk_digest(chunk)
        self._check_every_fault(lambda store: lambda: store.append_case_chunk(
            case["case_id"], case["case_revision"], "chunk-1", digest, copy.deepcopy(chunk)))

    def test_commit_case_processing_chunk(self):
        statement_bytes = b"%PDF synthetic statement fixture"
        statement = _source_record("statement-001", statement_bytes)
        case = self.store.create_case(_case(statement), statement, statement_bytes)
        source = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-001", source, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": source}]
        case = self.store.append_case_chunk(case["case_id"], case["case_revision"], "upload-1",
                                            self.store.case_chunk_digest(chunk), chunk)
        current = self.store.get("receipt-001").record
        updated = copy.deepcopy(current)
        updated["language"] = "en"
        next_manifest = copy.deepcopy(case)
        next_manifest["processing"] = {"state": "completed", "cursor": "1", "result_bytes": 0, "committed_chunks": []}
        expected = {"receipt-001": self.store.record_revision_sha256(current)}
        self._check_every_fault(lambda store: lambda: store.commit_case_processing_chunk(
            case["case_id"], case["case_revision"], "ocr-1", [copy.deepcopy(updated)],
            copy.deepcopy(next_manifest), dict(expected)))


class ResumeAfterReopenTests(unittest.TestCase):
    """An interrupted case continues from its cursor after the archive is reopened (REQ-082)."""

    setUp = processing.ExpenseCaseProcessingManagerTests.setUp
    _run_to_terminal = processing.ExpenseCaseProcessingManagerTests._run_to_terminal
    _limits_for_one_document_frames = processing.ExpenseCaseProcessingManagerTests._limits_for_one_document_frames

    def test_resume_after_reopening_the_archive(self):
        limits = self._limits_for_one_document_frames()
        worker = processing._ImmediateWorker(limits, fail_on_call=2)
        manager = ExpenseCaseProcessingManager(self.store, worker, limits, DecodeLimits(), poll_interval=0.001)
        self.assertEqual(self._run_to_terminal(manager, manager.start(self.case["case_id"], self.case["case_revision"])).phase, "failed")
        manager.close()

        reopened = LocalDocumentStore(self.store.path, protector=SyntheticProtector())  # as after an app restart
        failed_case = reopened.get_case(self.case["case_id"])
        self.assertEqual((failed_case["processing"]["state"], failed_case["processing"]["cursor"]), ("failed", "1"))
        fresh_worker = processing._ImmediateWorker(limits)
        resumed = ExpenseCaseProcessingManager(reopened, fresh_worker, limits, DecodeLimits(), poll_interval=0.001)
        self.addCleanup(resumed.close)
        status = self._run_to_terminal(resumed, resumed.start(self.case["case_id"], failed_case["case_revision"]))
        self.assertEqual(status.phase, "succeeded")
        final = reopened.get_case(self.case["case_id"])
        self.assertEqual((final["processing"]["state"], final["processing"]["cursor"]), ("completed", "2"))
        self.assertEqual(fresh_worker.calls, 1, "only the unfinished group is processed again")


if __name__ == "__main__":
    unittest.main()
