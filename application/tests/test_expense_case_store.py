"""Synthetic storage tests for encrypted local expense-case manifests."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import alfa_document_intelligence.local_document_store as store_module

from alfa_document_intelligence.local_document_store import (
    LocalDocumentStore,
    StoreConcurrentUpdate,
    StoreIntegrityError,
    StoreError,
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


@pytest.mark.parametrize('lines', [None, [], {}, False, 0, 'é😀\n"\\', {'z': [-3.25, {'a': '漢字'}], 'a': []}])
def test_authenticated_record_size_accounting_matches_canonical_bytes(lines):
    record = _source_record('size-unicode', b'%PDF synthetic')
    record['source']['storage_ref'] = 'local-archive://size-unicode'
    record['processing']['ocr']['status'] = 'completed'
    record['expense_lines'] = lines
    metadata, processed = LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])
    assert metadata == LocalDocumentStore._case_record_metadata_size_validated(record, record['document_id'])
    assert processed == len(LocalDocumentStore._canonical_json(record))


def test_authenticated_record_size_accounting_optional_and_nonfinite_content():
    record = _source_record('size-optional', b'%PDF synthetic')
    record['source']['storage_ref'] = 'local-archive://size-optional'
    record['processing']['ocr']['status'] = 'completed'
    record.pop('expense_lines', None)
    _, processed = LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])
    assert processed == len(LocalDocumentStore._canonical_json(record))
    record['expense_lines'] = [float('nan')]
    with pytest.raises(ValueError):
        LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])
    record['processing']['ocr']['status'] = 'pending'
    metadata, processed = LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])
    assert metadata == LocalDocumentStore._case_record_metadata_size_validated(record, record['document_id'])
    assert processed == 0


def test_authenticated_record_size_accounting_exact_metadata_limit():
    record = _source_record('size-limit', b'%PDF synthetic')
    record['source']['storage_ref'] = 'local-archive://size-limit'
    record['processing']['ocr']['status'] = 'completed'
    record['padding'] = ''
    base = LocalDocumentStore._case_record_metadata_size_validated(record, record['document_id'])
    record['padding'] = 'x' * (1024 * 1024 - base)
    metadata, processed = LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])
    assert metadata == 1024 * 1024
    assert processed == len(LocalDocumentStore._canonical_json(record))
    record['padding'] += 'x'
    with pytest.raises(StoreRejected):
        LocalDocumentStore._case_record_sizes_validated(record, record['document_id'])


def test_reused_case_workers_drain_before_propagating_validation_error():
    started, release, errors = threading.Event(), threading.Event(), []
    def check(row):
        if row == 'slow':
            started.set()
            assert release.wait(5)
            return row
        assert started.wait(5)
        raise ValueError('synthetic failure')
    def run():
        try:
            store_module._checked_case_list_batch(check, ['slow', 'bad'])
        except Exception as exc:
            errors.append(exc)
    reader = threading.Thread(target=run)
    reader.start()
    try:
        assert started.wait(5)
        reader.join(.1)
        assert reader.is_alive()
    finally:
        release.set()
        reader.join(5)
    assert not reader.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], ValueError)


def test_closed_case_executor_is_reported_as_store_error(monkeypatch):
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown(wait=True)
    monkeypatch.setattr(store_module, '_get_case_list_executor', lambda: executor)
    with pytest.raises(StoreError, match='workers are unavailable'):
        store_module._checked_case_list_batch(lambda _: None, ['record'])


def test_case_executor_submission_failure_drains_existing_work(monkeypatch):
    started, release, errors = threading.Event(), threading.Event(), []
    executor = ThreadPoolExecutor(max_workers=1)
    class FailingExecutor:
        calls = 0
        def submit(self, fn, row):
            self.calls += 1
            if self.calls == 2:
                assert started.wait(5)
                raise RuntimeError('synthetic executor failure')
            return executor.submit(fn, row)
    monkeypatch.setattr(store_module, '_get_case_list_executor', lambda: FailingExecutor())
    def check(_):
        started.set()
        assert release.wait(5)
    def run():
        try:
            store_module._checked_case_list_batch(check, ['first', 'second'])
        except Exception as exc:
            errors.append(exc)
    reader = threading.Thread(target=run)
    reader.start()
    try:
        assert started.wait(5)
        reader.join(.1)
        assert reader.is_alive()
    finally:
        release.set()
        reader.join(5)
        executor.shutdown(wait=True)
    assert not reader.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], StoreError)


def test_reused_case_executor_does_not_prevent_normal_process_exit():
    code = (
        'from alfa_document_intelligence.local_document_store import _checked_case_list_batch; '
        'assert _checked_case_list_batch(lambda value: value + 1, [1, 2]) == [2, 3]'
    )
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def parallel_case_store(tmp_path, monkeypatch):
    # Force the isolated parallel branch with an authenticated synthetic protector.
    monkeypatch.setattr(store_module, 'WindowsDpapiProtector', SyntheticProtector)
    store = LocalDocumentStore(tmp_path / 'parallel-case.sqlite', protector=SyntheticProtector())
    with sqlite3.connect(store.path) as connection:
        connection.execute('PRAGMA journal_mode=WAL')
    source = b'%PDF synthetic only'
    record = _source_record('parallel-record', source)
    return store, store.create_case(_case(record), record, source)


def test_parallel_case_gate_busy_falls_back_without_waiting(parallel_case_store):
    store, case = parallel_case_store
    gate = store_module._CASE_LIST_PARALLEL_GATE
    assert gate.acquire(blocking=False)
    try:
        with patch.object(store, '_validate_case_references', wraps=store._validate_case_references) as sequential:
            assert store.list_cases()[0]['case_id'] == case['case_id']
            assert sequential.call_count == 1
    finally:
        gate.release()


def test_parallel_case_gate_released_after_error(parallel_case_store):
    store, _ = parallel_case_store
    with patch.object(store, '_validate_case_references_parallel', side_effect=StoreIntegrityError('synthetic failure')):
        with pytest.raises(StoreIntegrityError):
            store.list_cases()
    assert store_module._CASE_LIST_PARALLEL_GATE.acquire(blocking=False)
    store_module._CASE_LIST_PARALLEL_GATE.release()
    assert len(store.list_cases()) == 1


def test_partial_submission_failure_drains_and_releases_gate(parallel_case_store, monkeypatch):
    store, case = parallel_case_store
    source = b'%PDF synthetic receipt'
    record = _source_record('gate-receipt', source, family='fiscal_receipt')
    chunk = [{'record': record, 'source_bytes': source}]
    store.append_case_chunk(case['case_id'], case['case_revision'], 'gate-chunk', store.case_chunk_digest(chunk), chunk)
    started, release, errors = threading.Event(), threading.Event(), []
    executor = ThreadPoolExecutor(max_workers=1)
    class FailingExecutor:
        calls = 0
        def submit(self, fn, row):
            self.calls += 1
            if self.calls == 2:
                assert started.wait(5)
                raise RuntimeError('synthetic partial submission failure')
            def delayed():
                started.set()
                assert release.wait(5)
                return fn(row)
            return executor.submit(delayed)
    failing = FailingExecutor()
    original_get = store_module._get_case_list_executor
    monkeypatch.setattr(store_module, '_get_case_list_executor', lambda: failing)
    def read():
        try:
            store.list_cases()
        except Exception as exc:
            errors.append(exc)
    reader = threading.Thread(target=read)
    reader.start()
    try:
        assert started.wait(5)
        reader.join(.1)
        assert reader.is_alive()
        unexpectedly_free = store_module._CASE_LIST_PARALLEL_GATE.acquire(blocking=False)
        if unexpectedly_free:
            store_module._CASE_LIST_PARALLEL_GATE.release()
        assert not unexpectedly_free
    finally:
        release.set()
        reader.join(5)
        executor.shutdown(wait=True)
    assert not reader.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], StoreError)
    assert store_module._CASE_LIST_PARALLEL_GATE.acquire(blocking=False)
    store_module._CASE_LIST_PARALLEL_GATE.release()
    monkeypatch.setattr(store_module, '_get_case_list_executor', original_get)
    assert store.list_cases()[0]['case_id'] == case['case_id']


def test_case_writer_does_not_wait_for_parallel_gate(parallel_case_store):
    store, case = parallel_case_store
    gate = store_module._CASE_LIST_PARALLEL_GATE
    assert gate.acquire(blocking=False)
    done, errors = threading.Event(), []
    def write():
        try:
            store.save_case(copy.deepcopy(case), expected_revision=case['case_revision'])
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()
    worker = threading.Thread(target=write)
    try:
        worker.start()
        assert done.wait(5), 'writer waited on the parallel read gate'
    finally:
        gate.release()
        worker.join(10)
    assert not worker.is_alive() and not errors


def test_custom_protector_case_list_stays_sequential(tmp_path):
    store = LocalDocumentStore(tmp_path / 'custom.sqlite', protector=SyntheticProtector())
    source = b'%PDF synthetic only'
    record = _source_record('custom-record', source)
    store.create_case(_case(record), record, source)
    with patch.object(store, '_validate_case_references_parallel', side_effect=AssertionError('unexpected parallel')):
        assert len(store.list_cases()) == 1


def test_parallel_case_list_accepts_single_ciphertext_above_batch_limit(tmp_path, monkeypatch):
    class PaddedProtector(SyntheticProtector):
        def protect(self, data):
            raw = super().protect(data)
            return len(raw).to_bytes(4, 'big') + raw + b'X' * (9 * 1024 * 1024)

        def unprotect(self, data):
            length = int.from_bytes(data[:4], 'big')
            return super().unprotect(data[4:4 + length])

    monkeypatch.setattr(store_module, 'WindowsDpapiProtector', PaddedProtector)
    store = LocalDocumentStore(tmp_path / 'large.sqlite', protector=PaddedProtector())
    source = b'%PDF synthetic only'
    record = _source_record('large-record', source)
    store.create_case(_case(record), record, source)
    with patch.object(store, '_validate_case_references_parallel', wraps=store._validate_case_references_parallel) as parallel:
        assert len(store.list_cases()) == 1
        assert parallel.call_count == 1


@pytest.mark.parametrize('parallel', [False, True], ids=['sequential', 'parallel'])
@pytest.mark.parametrize('damage', [
    'binding', 'record', 'missing', 'source_type', 'source_total', 'metadata_total', 'processed_total',
])
def test_case_list_validation_paths_reject_same_tampering(tmp_path, monkeypatch, parallel, damage):
    if parallel:
        monkeypatch.setattr(store_module, 'WindowsDpapiProtector', SyntheticProtector)
    path = tmp_path / 'equivalence.sqlite'
    store = LocalDocumentStore(path, protector=SyntheticProtector())
    source = b'%PDF synthetic only'
    record = _source_record('equivalence-record', source)
    case = store.create_case(_case(record), record, source)
    with sqlite3.connect(path) as connection:
        if damage in {'binding', 'record'}:
            table, column = ('case_documents', 'binding_payload') if damage == 'binding' else ('documents', 'record_payload')
            entry, value = connection.execute(f'SELECT entry_id, {column} FROM {table} LIMIT 1').fetchone()
            altered = bytearray(value)
            altered[-1] ^= 1
            connection.execute(f'UPDATE {table} SET {column} = ? WHERE entry_id = ?', (bytes(altered), entry))
        elif damage == 'missing':
            connection.execute('DELETE FROM documents')
        elif damage == 'source_type':
            connection.execute('UPDATE documents SET source_payload = ?', ('invalid text',))
        elif damage == 'source_total':
            altered = copy.deepcopy(case)
            altered['retained_source_bytes'] += 1
            sealed = store._seal_case(altered)
            connection.execute('UPDATE cases SET case_payload = ?', (store._protect_case_payload(sealed),))
    if damage == 'metadata_total':
        monkeypatch.setattr(store_module, '_MAX_CASE_TOTAL_METADATA_BYTES', 0)
    elif damage == 'processed_total':
        updated = store.get('equivalence-record').record
        updated['processing']['ocr']['status'] = 'completed'
        store.save(updated, source)
    with patch.object(store, '_validate_case_references_parallel', wraps=store._validate_case_references_parallel) as path_spy:
        with pytest.raises(StoreIntegrityError):
            store.list_cases()
        assert path_spy.call_count == int(parallel)


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI required')
def test_dpapi_case_list_parallel_rejects_altered_record(tmp_path):
    path = tmp_path / 'dpapi-parallel.sqlite'
    store = LocalDocumentStore(path)
    source = b'%PDF synthetic statement'
    statement = _source_record('dpapi-statement', source)
    case = store.create_case(_case(statement), statement, source)
    attachments = []
    for i in range(3):
        data = f'%PDF synthetic receipt {i}'.encode('ascii')
        attachments.append({'record': _source_record(f'dpapi-receipt-{i}', data, family='fiscal_receipt'), 'source_bytes': data})
    case = store.append_case_chunk(case['case_id'], case['case_revision'], 'dpapi-chunk', store.case_chunk_digest(attachments), attachments)
    with patch.object(store, '_validate_case_references_parallel', wraps=store._validate_case_references_parallel) as parallel:
        assert store.list_cases()[0]['case_revision'] == case['case_revision']
        assert parallel.call_count == 1
    with sqlite3.connect(path) as connection:
        entry, payload = connection.execute('SELECT entry_id, record_payload FROM documents ORDER BY entry_id LIMIT 1').fetchone()
        altered = bytearray(payload)
        altered[-1] ^= 1
        connection.execute('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (bytes(altered), entry))
    with patch.object(store, '_validate_case_references_parallel', wraps=store._validate_case_references_parallel) as parallel:
        with pytest.raises(StoreIntegrityError):
            store.list_cases()
        assert parallel.call_count == 1
    assert store_module._CASE_LIST_PARALLEL_GATE.acquire(blocking=False)
    store_module._CASE_LIST_PARALLEL_GATE.release()


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI required')
def test_dpapi_parallel_list_keeps_wal_snapshot_during_write(tmp_path):
    path = tmp_path / 'dpapi-parallel-wal.sqlite'
    store = LocalDocumentStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    source = b'%PDF synthetic statement'
    record = _source_record('dpapi-wal-statement', source)
    case = store.create_case(_case(record), record, source)
    entered, release = threading.Event(), threading.Event()
    result, errors = [], []
    original_decode = store._decode_record

    def hold_parallel_record(payload):
        if threading.current_thread().name.startswith('ThreadPoolExecutor'):
            entered.set()
            if not release.wait(10):
                raise AssertionError('parallel read was not released')
        return original_decode(payload)

    def read():
        try:
            result.extend(store.list_cases())
        except Exception as exc:
            errors.append(exc)

    reader = threading.Thread(target=read)
    try:
        with patch.object(store, '_decode_record', side_effect=hold_parallel_record):
            reader.start()
            assert entered.wait(5), 'parallel DPAPI branch did not start'
            updated = copy.deepcopy(case)
            updated['processing']['state'] = 'processing'
            saved = store.save_case(updated, expected_revision=case['case_revision'])
            assert saved['case_revision'] != case['case_revision']
            release.set()
            reader.join(10)
    finally:
        release.set()
        reader.join(10)
    assert not reader.is_alive() and not errors
    assert result[0]['case_revision'] == case['case_revision']
    assert store.list_cases()[0]['case_revision'] == saved['case_revision']


@pytest.mark.parametrize('read_method', ['get_case', 'list_cases'])
@pytest.mark.parametrize('parallel', [False, True], ids=['sequential', 'parallel'])
def test_case_read_uses_one_snapshot_during_concurrent_ocr_commit(tmp_path, read_method, parallel, monkeypatch):
    """Readers see one consistent case version while an OCR commit is published."""
    if parallel:
        monkeypatch.setattr(store_module, 'WindowsDpapiProtector', SyntheticProtector)
    path = tmp_path / 'snapshot.sqlite3'
    store = LocalDocumentStore(path, protector=SyntheticProtector())
    with sqlite3.connect(path) as connection:
        assert connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    source = b'%PDF synthetic statement'
    statement = _source_record('snapshot-statement', source)
    case = store.create_case(_case(statement), statement, source)
    original_record = store.get('snapshot-statement').record
    updated = copy.deepcopy(original_record)
    updated['processing']['ocr']['status'] = 'completed'
    next_case = copy.deepcopy(case)
    next_case['processing'].update({
        'state': 'processing', 'cursor': '1',
        'result_bytes': len(store._canonical_json(updated)),
    })
    expected_hash = store.record_revision_sha256(original_record)
    decode = store._decode_case_payload
    triggered = False

    def commit_after_case_read(payload):
        nonlocal triggered
        decoded = decode(payload)
        if not triggered:
            triggered = True
            store.commit_case_processing_chunk(
                case['case_id'], case['case_revision'], 'snapshot-ocr', [updated],
                next_case, {'snapshot-statement': expected_hash},
            )
        return decoded

    with patch.object(store, '_decode_case_payload', side_effect=commit_after_case_read):
        result = store.get_case(case['case_id']) if read_method == 'get_case' else store.list_cases()[0]
    assert result['case_revision'] == case['case_revision']
    assert store.get_case(case['case_id'])['processing']['cursor'] == '1'


@pytest.mark.parametrize('parallel', [False, True], ids=['sequential', 'parallel'])
def test_case_read_in_default_journal_releases_writer_after_snapshot(tmp_path, parallel, monkeypatch):
    if parallel:
        monkeypatch.setattr(store_module, 'WindowsDpapiProtector', SyntheticProtector)
    path = tmp_path / 'snapshot-delete.sqlite3'
    store = LocalDocumentStore(path, protector=SyntheticProtector())
    with sqlite3.connect(path) as connection:
        assert connection.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    source = b'%PDF synthetic statement'
    statement = _source_record('snapshot-statement', source)
    case = store.create_case(_case(statement), statement, source)
    original_record = store.get('snapshot-statement').record
    updated = copy.deepcopy(original_record)
    updated['processing']['ocr']['status'] = 'completed'
    next_case = copy.deepcopy(case)
    next_case['processing'].update({
        'state': 'processing', 'cursor': '1',
        'result_bytes': len(store._canonical_json(updated)),
    })
    expected_hash = store.record_revision_sha256(original_record)
    decode = store._decode_case_payload
    started = threading.Event()
    finished = threading.Event()
    errors = []

    def writer():
        started.set()
        try:
            store.commit_case_processing_chunk(
                case['case_id'], case['case_revision'], 'snapshot-ocr', [updated],
                next_case, {'snapshot-statement': expected_hash},
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    triggered = False
    thread = threading.Thread(target=writer)

    def begin_concurrent_write(payload):
        nonlocal triggered
        decoded = decode(payload)
        if not triggered:
            triggered = True
            thread.start()
            assert started.wait(2)
            assert not finished.wait(0.2), 'writer should wait for the read snapshot'
        return decoded

    try:
        with patch.object(store, '_decode_case_payload', side_effect=begin_concurrent_write):
            result = store.list_cases()[0]
    finally:
        thread.join(12)
    assert not thread.is_alive() and not errors
    assert result['case_revision'] == case['case_revision']
    assert store.get_case(case['case_id'])['processing']['cursor'] == '1'


def test_metadata_size_does_not_mutate_nested_record():
    record = _source_record('metadata-synthetic', b'%PDF synthetic source')
    original = copy.deepcopy(record)
    legacy = copy.deepcopy(record)
    legacy['source']['storage_ref'] = 'local-archive://metadata-synthetic'
    legacy.pop('expense_lines', None)
    expected = len(LocalDocumentStore._canonical_json({
        'format_version': 1, 'record': legacy, 'saved_at': '2000-01-01T00:00:00+00:00',
    }))
    assert LocalDocumentStore._case_record_metadata_size(record) == expected
    assert record == original


def test_decoded_records_are_independent_between_reads(tmp_path):
    store = LocalDocumentStore(tmp_path / 'fresh.sqlite3', protector=SyntheticProtector())
    source = b'%PDF synthetic source'
    statement = _source_record('independent-record', source)
    store.create_case(_case(statement), statement, source)
    first = store.get('independent-record').record
    first['source']['original_filename'] = 'modified-only-in-memory.pdf'
    second = store.get('independent-record').record
    assert second['source']['original_filename'] != 'modified-only-in-memory.pdf'


@pytest.mark.parametrize('invalid_source', [b'', 'synthetic text instead of ciphertext'])
@pytest.mark.parametrize('reader', ['get_case', 'list_cases'])
def test_case_read_rejects_missing_or_wrong_type_source_ciphertext(tmp_path, invalid_source, reader):
    path = tmp_path / 'invalid-source.sqlite3'
    store = LocalDocumentStore(path, protector=SyntheticProtector())
    source = b'%PDF synthetic source'
    statement = _source_record('invalid-source-record', source)
    store.create_case(_case(statement), statement, source)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE documents SET source_payload = ?', (invalid_source,))
    connection.close()
    with pytest.raises(StoreIntegrityError, match='source ciphertext'):
        store.get_case('case-001') if reader == 'get_case' else store.list_cases()
















def test_failed_restore_restores_original_index_key(tmp_path):
    protector = SyntheticProtector()
    first = LocalDocumentStore(tmp_path / 'first.sqlite3', protector=protector)
    second = LocalDocumentStore(tmp_path / 'second.sqlite3', protector=protector)
    source = b'%PDF synthetic source'
    statement = _source_record('rollback-record', source)
    first.create_case(_case(statement), statement, source)
    second.create_case(_case(statement), statement, source)
    old_key = first._index_key
    backup = tmp_path / 'backup'
    second.backup_to(backup)
    with patch.object(first, '_verify_index_integrity', side_effect=StoreIntegrityError('synthetic failure')):
        with pytest.raises(StoreError, match='previous archive was put back'):
            first.restore_from(backup)
    assert first._index_key == old_key
    assert first.get_case('case-001')






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
            connection.execute("DROP TABLE document_library")  # schema 4 table, absent in a real v2 archive
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
