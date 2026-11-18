"""Synthetic tests for the per-process cache of verified case-list references.

The cache maps the exact authenticated ciphertext bytes of a binding/record
pair to the derived values the case list needs. Every list still reads every
row inside one SQLite read snapshot; only bytes already authenticated and
validated by this process skip a repeated DPAPI decrypt and validation.
"""
import copy
import json
import os
import sqlite3
from unittest.mock import patch

import pytest
import alfa_document_intelligence.local_document_store as store_module

from alfa_document_intelligence.local_document_store import (
    LocalDocumentStore,
    StoreError,
    StoreIntegrityError,
)
from test_expense_case_store import _case, _source_record
from test_local_document_store import SyntheticProtector


def _cached_case_store(tmp_path, monkeypatch, attachments=3, protector_class=SyntheticProtector):
    # Route the synthetic protector through the Windows DPAPI case-list path.
    monkeypatch.setattr(store_module, 'WindowsDpapiProtector', protector_class)
    path = tmp_path / 'cached-case.sqlite'
    store = LocalDocumentStore(path, protector=protector_class())
    source = b'%PDF synthetic statement'
    statement = _source_record('cache-statement', source)
    case = store.create_case(_case(statement), statement, source)
    if attachments:
        chunk = []
        for i in range(attachments):
            data = f'%PDF synthetic receipt {i}'.encode('ascii')
            chunk.append({
                'record': _source_record(f'cache-receipt-{i}', data, family='fiscal_receipt'),
                'source_bytes': data,
            })
        case = store.append_case_chunk(
            case['case_id'], case['case_revision'], 'cache-chunk', store.case_chunk_digest(chunk), chunk,
        )
    return store, path, case


def _write(path, statements):
    connection = sqlite3.connect(path)
    try:
        with connection:
            for sql, params in statements:
                connection.execute(sql, params)
    finally:
        connection.close()


def _read(path, sql, params=()):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def test_repeat_list_skips_checks_of_unchanged_bytes(tmp_path, monkeypatch):
    store, _, case = _cached_case_store(tmp_path, monkeypatch)
    first = store.list_cases()
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records, \
         patch.object(store, '_decode_case_reference', wraps=store._decode_case_reference) as bindings:
        second = store.list_cases()
    assert second == first and second[0]['case_revision'] == case['case_revision']
    assert records.call_count == 0 and bindings.call_count == 0
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 4


def test_only_changed_bytes_are_checked_again(tmp_path, monkeypatch):
    store, _, _ = _cached_case_store(tmp_path, monkeypatch)
    store.list_cases()
    case = store.get_case('case-001')
    case['processing']['result_bytes'] = 10 * 1024 * 1024
    store.save_case(case, expected_revision=case['case_revision'])
    updated = store.get('cache-receipt-1').record
    updated['processing']['ocr']['status'] = 'completed'
    store.save(updated, b'%PDF synthetic receipt 1')
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        assert len(store.list_cases()) == 1
    assert records.call_count == 1


@pytest.mark.parametrize('damage', [
    'binding', 'record', 'missing', 'source_type', 'source_total', 'metadata_total', 'processed_total',
    'archive_reference',
])
def test_warm_cache_rejects_same_tampering_as_uncached_paths(tmp_path, monkeypatch, damage):
    monkeypatch.setattr(store_module, 'WindowsDpapiProtector', SyntheticProtector)
    path = tmp_path / 'warm-equivalence.sqlite'
    store = LocalDocumentStore(path, protector=SyntheticProtector())
    source = b'%PDF synthetic only'
    record = _source_record('equivalence-record', source)
    case = store.create_case(_case(record), record, source)
    assert len(store.list_cases()) == 1
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 1
    if damage in {'binding', 'record'}:
        table, column = ('case_documents', 'binding_payload') if damage == 'binding' else ('documents', 'record_payload')
        entry, value = _read(path, f'SELECT entry_id, {column} FROM {table} LIMIT 1')[0]
        altered = bytearray(value)
        altered[-1] ^= 1
        _write(path, [(f'UPDATE {table} SET {column} = ? WHERE entry_id = ?', (bytes(altered), entry))])
    elif damage == 'missing':
        _write(path, [('DELETE FROM documents', ())])
    elif damage == 'source_type':
        _write(path, [('UPDATE documents SET source_payload = ?', ('invalid text',))])
    elif damage == 'source_total':
        altered = copy.deepcopy(case)
        altered['retained_source_bytes'] += 1
        sealed = store._seal_case(altered)
        _write(path, [('UPDATE cases SET case_payload = ?', (store._protect_case_payload(sealed),))])
    elif damage == 'archive_reference':
        entry, payload = _read(path, 'SELECT entry_id, record_payload FROM documents LIMIT 1')[0]
        envelope = json.loads(store._protector.unprotect(payload).decode('utf-8'))
        envelope['record']['source']['storage_ref'] = 'local-archive://different-document'
        protected = store._protector.protect(store._canonical_json(envelope))
        _write(path, [('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (protected, entry))])
    elif damage == 'metadata_total':
        monkeypatch.setattr(store_module, '_MAX_CASE_TOTAL_METADATA_BYTES', 0)
    elif damage == 'processed_total':
        updated = store.get('equivalence-record').record
        updated['processing']['ocr']['status'] = 'completed'
        store.save(updated, source)
    with pytest.raises(StoreIntegrityError):
        store.list_cases()


def test_warm_cache_rejects_record_metadata_above_current_limit(tmp_path, monkeypatch):
    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=1)
    store.list_cases()
    monkeypatch.setattr(store_module, '_MAX_CASE_RECORD_METADATA_BYTES', 10)
    with pytest.raises(StoreError) as warm:
        store.list_cases()
    store_module._CASE_LIST_REFERENCE_CACHE.clear()
    with pytest.raises(StoreError) as cold:
        store.list_cases()
    assert type(warm.value) is type(cold.value)


@pytest.mark.parametrize('column', ['record_payload', 'binding_payload'])
def test_swapped_authentic_ciphertexts_are_rejected(tmp_path, monkeypatch, column):
    store, path, _ = _cached_case_store(tmp_path, monkeypatch, attachments=2)
    store.list_cases()
    table = 'documents' if column == 'record_payload' else 'case_documents'
    rows = _read(path, f'SELECT entry_id, {column} FROM {table} ORDER BY entry_id')
    # Both payloads were authenticated and cached while bound to their own rows;
    # the statement and a receipt differ in document, hash and role.
    (first_id, first), (second_id, second) = rows[0], rows[-1]
    _write(path, [
        (f'UPDATE {table} SET {column} = ? WHERE entry_id = ?', (second, first_id)),
        (f'UPDATE {table} SET {column} = ? WHERE entry_id = ?', (first, second_id)),
    ])
    with pytest.raises(StoreIntegrityError):
        store.list_cases()


@pytest.mark.parametrize('pair', ['receipts', 'statement_and_receipt'])
def test_whole_cached_pair_moved_to_another_reference_is_rejected(tmp_path, monkeypatch, pair):
    store, path, _ = _cached_case_store(tmp_path, monkeypatch, attachments=2)
    store.list_cases()
    bindings = dict(_read(path, 'SELECT document_id_index, binding_payload FROM case_documents'))
    records = dict(_read(path, 'SELECT document_id_index, record_payload FROM documents'))
    statement = store._document_id_index('cache-statement')
    receipts = [store._document_id_index(f'cache-receipt-{i}') for i in range(2)]
    first, second = receipts if pair == 'receipts' else (statement, receipts[0])
    # Each binding/record pair is an exact cache hit, but for a different reference.
    _write(path, [
        ('UPDATE case_documents SET binding_payload = ? WHERE document_id_index = ?', (bindings[second], first)),
        ('UPDATE case_documents SET binding_payload = ? WHERE document_id_index = ?', (bindings[first], second)),
        ('UPDATE documents SET record_payload = ? WHERE document_id_index = ?', (records[second], first)),
        ('UPDATE documents SET record_payload = ? WHERE document_id_index = ?', (records[first], second)),
    ])
    with patch.object(store, '_decode_case_reference', wraps=store._decode_case_reference) as full:
        with pytest.raises(StoreIntegrityError, match='binding does not match'):
            store.list_cases()
    assert full.call_count >= 1  # the mismatching hit fell back to the full check


def test_failed_checks_are_not_cached(tmp_path, monkeypatch):
    class AlternatingProtector(SyntheticProtector):
        corrupt_next = False

        def unprotect(self, data):
            plaintext = super().unprotect(data)
            if AlternatingProtector.corrupt_next:
                AlternatingProtector.corrupt_next = False
                return b'{"synthetic": "invalid"}'
            return plaintext

    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=0, protector_class=AlternatingProtector)
    original = store._decode_case_payload

    def corrupt_after_manifest(payload):
        decoded = original(payload)
        AlternatingProtector.corrupt_next = True
        return decoded

    with patch.object(store, '_decode_case_payload', side_effect=corrupt_after_manifest):
        with pytest.raises(StoreIntegrityError):
            store.list_cases()
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 0
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        assert len(store.list_cases()) == 1
    assert records.call_count == 1
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 1


def test_rolled_back_record_matches_uncached_outcome(tmp_path, monkeypatch):
    store, path, case = _cached_case_store(tmp_path, monkeypatch, attachments=1)
    old_rows = _read(path, 'SELECT entry_id, record_payload FROM documents')
    store.list_cases()  # the older bytes are now cached
    original = store.get('cache-statement').record
    updated = copy.deepcopy(original)
    updated['processing']['ocr']['status'] = 'completed'
    next_case = copy.deepcopy(case)
    next_case['processing'].update({
        'state': 'processing', 'cursor': '1', 'result_bytes': len(store._canonical_json(updated)),
    })
    store.commit_case_processing_chunk(
        case['case_id'], case['case_revision'], 'rollback-ocr', [updated], next_case,
        {'cache-statement': store.record_revision_sha256(original)},
    )
    store.list_cases()
    _write(path, [
        ('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (payload, entry_id))
        for entry_id, payload in old_rows
    ])

    def outcome():
        try:
            return ('ok', store.list_cases())
        except StoreError as exc:
            return ('error', type(exc))

    warm = outcome()
    store_module._CASE_LIST_REFERENCE_CACHE.clear()
    cold = outcome()
    store_module._CASE_LIST_REFERENCE_CACHE.clear()
    with patch.object(store_module._CASE_LIST_PARALLEL_GATE, 'acquire', return_value=False):
        sequential = outcome()
    assert warm == cold == sequential


def test_cache_holds_no_identifiers_and_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module._CASE_LIST_REFERENCE_CACHE, '_max_entries', 3)
    store, _, case = _cached_case_store(tmp_path, monkeypatch, attachments=4)
    store.list_cases()
    cache = store_module._CASE_LIST_REFERENCE_CACHE
    assert len(cache) == 3
    dump = repr(list(cache._entries.items())) + repr(vars(cache))
    sensitive = [case['case_id'], case['statement_document_id'], case['statement_sha256']]
    sensitive += [item['document_id'] for item in case['attachments']]
    sensitive += [item['source_sha256'] for item in case['attachments']]
    for entry in cache._entries.values():
        value, expires_at, generation = entry
        assert all(isinstance(field, (bytes, bool, int)) for field in value)
        assert isinstance(expires_at, float) and isinstance(generation, int)
    raw = b''.join(
        field for key, entry in cache._entries.items() for field in (key, *entry[0]) if isinstance(field, bytes)
    )
    for value in sensitive:
        assert value not in dump and value.encode() not in raw
        if len(value) == 64:
            assert bytes.fromhex(value) not in raw


def test_custom_protector_does_not_use_cache(tmp_path):
    store = LocalDocumentStore(tmp_path / 'custom-cache.sqlite', protector=SyntheticProtector())
    source = b'%PDF synthetic only'
    record = _source_record('custom-cache-record', source)
    store.create_case(_case(record), record, source)
    store.list_cases()
    store.list_cases()
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 0


def test_cache_is_cleared_after_delete_and_restore(tmp_path, monkeypatch):
    store, _, case = _cached_case_store(tmp_path, monkeypatch, attachments=1)
    store.backup_to(tmp_path / 'backup')
    store.list_cases()
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 2
    assert store.delete_case(case['case_id'])
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 0
    assert store.list_cases() == []
    store.restore_from(tmp_path / 'backup')
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 0
    assert store.list_cases()[0]['case_id'] == case['case_id']


def test_warm_cache_keeps_one_snapshot_during_concurrent_ocr_commit(tmp_path, monkeypatch):
    store, path, case = _cached_case_store(tmp_path, monkeypatch, attachments=0)
    assert _read(path, 'PRAGMA journal_mode=WAL')[0][0] == 'wal'
    assert store.list_cases()[0]['case_revision'] == case['case_revision']
    original_record = store.get('cache-statement').record
    updated = copy.deepcopy(original_record)
    updated['processing']['ocr']['status'] = 'completed'
    next_case = copy.deepcopy(case)
    next_case['processing'].update({
        'state': 'processing', 'cursor': '1', 'result_bytes': len(store._canonical_json(updated)),
    })
    decode = store._decode_case_payload
    triggered = False

    def commit_after_case_read(payload):
        nonlocal triggered
        decoded = decode(payload)
        if not triggered:
            triggered = True
            store.commit_case_processing_chunk(
                case['case_id'], case['case_revision'], 'warm-snapshot-ocr', [updated], next_case,
                {'cache-statement': store.record_revision_sha256(original_record)},
            )
        return decoded

    with patch.object(store, '_decode_case_payload', side_effect=commit_after_case_read):
        result = store.list_cases()[0]
    assert result['case_revision'] == case['case_revision']
    assert store.list_cases()[0]['processing']['cursor'] == '1'


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI required')
def test_dpapi_cache_skips_repeat_unprotect_and_rejects_alteration(tmp_path):
    path = tmp_path / 'dpapi-cache.sqlite'
    store = LocalDocumentStore(path)
    source = b'%PDF synthetic statement'
    statement = _source_record('dpapi-cache-statement', source)
    case = store.create_case(_case(statement), statement, source)
    attachments = []
    for i in range(3):
        data = f'%PDF synthetic receipt {i}'.encode('ascii')
        attachments.append({
            'record': _source_record(f'dpapi-cache-receipt-{i}', data, family='fiscal_receipt'),
            'source_bytes': data,
        })
    store.append_case_chunk(
        case['case_id'], case['case_revision'], 'dpapi-cache-chunk', store.case_chunk_digest(attachments), attachments,
    )
    first = store.list_cases()
    real = store_module.WindowsDpapiProtector.unprotect
    with patch.object(store_module.WindowsDpapiProtector, 'unprotect', autospec=True, side_effect=real) as unprotect:
        assert store.list_cases() == first
    # Only the case manifest is authenticated again; unchanged references are reused.
    assert unprotect.call_count == 1
    entry, payload = _read(path, 'SELECT entry_id, record_payload FROM documents ORDER BY entry_id LIMIT 1')[0]
    altered = bytearray(payload)
    altered[-1] ^= 1
    _write(path, [('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (bytes(altered), entry))])
    with pytest.raises(StoreIntegrityError):
        store.list_cases()
    _write(path, [('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (payload, entry))])
    assert store.list_cases() == first



# --- Review fixes (2026-11-19): restore, scan resistance, TTL, pinning, fail-closed ---

import hashlib as _hashlib
import inspect


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def fake_clock(monkeypatch):
    clock = _Clock()
    cache = store_module._CASE_LIST_REFERENCE_CACHE
    monkeypatch.setattr(cache, '_clock', clock)
    monkeypatch.setattr(cache, '_jitter', lambda: 0.0)
    return clock


def test_restore_candidate_check_does_not_use_cache(tmp_path, monkeypatch):
    store, _, case = _cached_case_store(tmp_path, monkeypatch, attachments=1)
    store.backup_to(tmp_path / 'backup')
    store.list_cases()  # warm with exactly the bytes held in the backup
    cache = store_module._CASE_LIST_REFERENCE_CACHE
    lookups = []
    original_get = cache.get

    def spy(*args, **kwargs):
        result = original_get(*args, **kwargs)
        lookups.append(result is not None)
        return result

    monkeypatch.setattr(cache, 'get', spy)
    decoded = []
    original_decode = LocalDocumentStore._decode_case_reference

    def counting_decode(self, payload):
        decoded.append(self.path.name)
        return original_decode(self, payload)

    monkeypatch.setattr(LocalDocumentStore, '_decode_case_reference', counting_decode)
    original_parallel = LocalDocumentStore._validate_case_references_parallel
    parallel_paths = []

    def tracking_parallel(self, *args, **kwargs):
        parallel_paths.append(self.path.name)
        return original_parallel(self, *args, **kwargs)

    monkeypatch.setattr(LocalDocumentStore, '_validate_case_references_parallel', tracking_parallel)
    store.restore_from(tmp_path / 'backup')
    assert not any(lookups)
    assert any(name.startswith('.restore-') for name in parallel_paths), 'the candidate list check did not run'
    staged_decodes = [name for name in decoded if name.startswith('.restore-')]
    # Constructor checks plus the candidate list both decrypt the two bindings.
    assert len(staged_decodes) >= 4
    assert store.list_cases()[0]['case_id'] == case['case_id']


def test_cache_stays_useful_when_references_exceed_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module._CASE_LIST_REFERENCE_CACHE, '_max_entries', 3)
    # One reference per batch, as in a large archive where batches flush mid-scan.
    monkeypatch.setattr(store_module, '_CASE_LIST_WORKERS', 1)
    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=4)  # five references
    store.list_cases()
    for _ in range(2):
        with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
            assert len(store.list_cases()) == 1
        assert records.call_count == 2  # three stay resident, two are checked fully
    assert len(store_module._CASE_LIST_REFERENCE_CACHE) == 3


def test_full_cache_replaces_entries_not_seen_in_current_list(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module._CASE_LIST_REFERENCE_CACHE, '_max_entries', 3)
    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=2)  # three references
    store.list_cases()
    case = store.get_case('case-001')
    case['processing']['result_bytes'] = 10 * 1024 * 1024
    store.save_case(case, expected_revision=case['case_revision'])
    updated = store.get('cache-receipt-0').record
    updated['processing']['ocr']['status'] = 'completed'
    store.save(updated, b'%PDF synthetic receipt 0')
    store.list_cases()  # the stale entry for the old bytes is replaced
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        store.list_cases()
    assert records.call_count == 0


class _DenyingProtector(SyntheticProtector):
    denied = set()

    def unprotect(self, data):
        if bytes(data) in _DenyingProtector.denied:
            raise OSError('synthetic DPAPI denial for one blob')
        return super().unprotect(data)


def test_selective_dpapi_denial_is_masked_only_until_entry_expiry(tmp_path, monkeypatch, fake_clock):
    """Pins the accepted trade-off: a partial master-key loss is hidden for at most the TTL."""
    _DenyingProtector.denied = set()
    store, path, case = _cached_case_store(tmp_path, monkeypatch, attachments=2, protector_class=_DenyingProtector)
    store.list_cases()
    denied = _read(path, 'SELECT record_payload FROM documents ORDER BY entry_id')[-1][0]
    _DenyingProtector.denied = {denied}
    try:
        fake_clock.now += store_module._CASE_LIST_REFERENCE_TTL_SECONDS - 1
        assert store.list_cases()[0]['case_id'] == case['case_id']  # masked inside the window
        with pytest.raises(StoreIntegrityError):
            store.get_case(case['case_id'])  # opening the case always authenticates
        fake_clock.now += 2
        with pytest.raises(StoreIntegrityError):
            store.list_cases()  # after expiry the denial is detected
    finally:
        _DenyingProtector.denied = set()


def test_entry_lifetime_has_bounded_random_jitter(monkeypatch):
    cache = store_module._VerifiedReferenceCache(8)
    clock = _Clock()
    monkeypatch.setattr(cache, '_clock', clock)
    ttl = store_module._CASE_LIST_REFERENCE_TTL_SECONDS
    jitter = store_module._CASE_LIST_REFERENCE_TTL_JITTER_SECONDS
    assert 0 < jitter < ttl
    for drawn in (0.0, jitter):
        monkeypatch.setattr(cache, '_jitter', lambda drawn=drawn: drawn)
        generation = cache.begin_list()
        key = bytes([int(drawn) % 256]) * 32
        cache.put(key, (b'tag', True, 1, 1, 0), generation)
        clock.now += ttl - drawn - 0.5
        assert cache.get(key, generation) is not None
        clock.now += 1
        assert cache.get(key, generation) is None
    samples = [store_module._VerifiedReferenceCache(1)._jitter() for _ in range(200)]
    assert all(0 <= value <= jitter for value in samples) and len(set(samples)) > 1


def _check_source_digests():
    from alfa_document_intelligence import contracts, document_family_catalog
    functions = {
        '_decode_record': LocalDocumentStore._decode_record,
        '_decode_case_reference': LocalDocumentStore._decode_case_reference,
        '_validate_record': LocalDocumentStore._validate_record,
        '_case_record_sizes_validated': LocalDocumentStore._case_record_sizes_validated,
        '_case_record_metadata_size_validated': LocalDocumentStore._case_record_metadata_size_validated,
        '_validate_case_references_parallel': LocalDocumentStore._validate_case_references_parallel,
        'validate_document_record': contracts.validate_document_record,
        'validate_family_snapshot': document_family_catalog.validate_family_snapshot,
    }
    return {
        name: _hashlib.sha256(inspect.getsource(fn).replace('\r\n', '\n').encode('utf-8')).hexdigest()
        for name, fn in functions.items()
    }


def test_cached_checks_are_pinned_to_check_version():
    assert store_module._CASE_LIST_REFERENCE_CHECK_VERSION == _PINNED_CHECK_VERSION
    changed = sorted(name for name, digest in _check_source_digests().items() if _PINNED_CHECK_SOURCES.get(name) != digest)
    assert not changed, (
        f'validation used by cached case-list checks changed ({changed}): '
        'bump _CASE_LIST_REFERENCE_CHECK_VERSION and update the pinned digests'
    )


@pytest.mark.parametrize('failing', ['get', 'tag', 'put'])
def test_cache_operation_errors_fail_closed(tmp_path, monkeypatch, failing):
    store, _, case = _cached_case_store(tmp_path, monkeypatch, attachments=2)
    store.list_cases()
    cache = store_module._CASE_LIST_REFERENCE_CACHE

    def broken(*args, **kwargs):
        raise RuntimeError('synthetic cache failure')

    if failing == 'put':
        cache.clear()  # a broken put must leave nothing behind
    monkeypatch.setattr(cache, failing, broken)
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        assert store.list_cases()[0]['case_revision'] == case['case_revision']
    assert records.call_count == 3  # nothing accepted from the cache; every reference checked fully
    if failing == 'put':
        assert len(cache) == 0


def test_cache_put_error_never_accepts_tampered_bytes(tmp_path, monkeypatch):
    store, path, _ = _cached_case_store(tmp_path, monkeypatch, attachments=1)
    store.list_cases()
    entry, payload = _read(path, 'SELECT entry_id, record_payload FROM documents ORDER BY entry_id LIMIT 1')[0]
    altered = bytearray(payload)
    altered[-1] ^= 1
    _write(path, [('UPDATE documents SET record_payload = ? WHERE entry_id = ?', (bytes(altered), entry))])

    def broken(*args, **kwargs):
        raise RuntimeError('synthetic cache failure')

    monkeypatch.setattr(store_module._CASE_LIST_REFERENCE_CACHE, 'put', broken)
    with pytest.raises(StoreIntegrityError):
        store.list_cases()


def test_check_version_change_forces_full_checks(tmp_path, monkeypatch):
    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=2)
    store.list_cases()
    monkeypatch.setattr(store_module, '_CASE_LIST_REFERENCE_CHECK_VERSION', store_module._CASE_LIST_REFERENCE_CHECK_VERSION + 1)
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        store.list_cases()
    assert records.call_count == 3


def test_protector_type_change_forces_full_checks(tmp_path, monkeypatch):
    store, _, _ = _cached_case_store(tmp_path, monkeypatch, attachments=2)
    store.list_cases()

    class OtherSyntheticProtector(SyntheticProtector):
        pass

    monkeypatch.setattr(store_module, 'WindowsDpapiProtector', OtherSyntheticProtector)
    store._protector = OtherSyntheticProtector()
    with patch.object(store, '_decode_record', wraps=store._decode_record) as records:
        store.list_cases()
    assert records.call_count == 3


def test_cache_key_includes_store_component():
    cache = store_module._CASE_LIST_REFERENCE_CACHE
    first = cache.key(b'store-a', SyntheticProtector, b'binding', b'record')
    assert first == cache.key(b'store-a', SyntheticProtector, b'binding', b'record')
    assert first != cache.key(b'store-b', SyntheticProtector, b'binding', b'record')
    assert first != cache.key(b'store-a', SyntheticProtector, b'bindingrecord', b'')


def test_two_stores_with_identical_ciphertexts_do_not_share_entries(tmp_path, monkeypatch):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    first, _, _ = _cached_case_store(tmp_path / 'a', monkeypatch, attachments=1)
    second, second_path, _ = _cached_case_store(tmp_path / 'b', monkeypatch, attachments=1)
    first_records = dict(_read(first.path, 'SELECT document_id_index, record_payload FROM documents'))
    first_bindings = dict(_read(first.path, 'SELECT document_id_index, binding_payload FROM case_documents'))
    # Give the second archive the first archive's exact authentic ciphertexts.
    updates = []
    for name in ('cache-statement', 'cache-receipt-0'):
        source, target = first._document_id_index(name), second._document_id_index(name)
        updates.append(('UPDATE documents SET record_payload = ? WHERE document_id_index = ?', (first_records[source], target)))
        updates.append(('UPDATE case_documents SET binding_payload = ? WHERE document_id_index = ?', (first_bindings[source], target)))
    _write(second_path, updates)
    first.list_cases()
    with patch.object(second, '_decode_record', wraps=second._decode_record) as records:
        second.list_cases()
    assert records.call_count == 2


_PINNED_CHECK_VERSION = 1
_PINNED_CHECK_SOURCES = {
    '_case_record_metadata_size_validated': '4fc32b1ebf1340be5ff9ab02cb5b7a1280ce5e5dd57b6aa07540b40410a0e468',
    '_case_record_sizes_validated': '431c05ac2767cc3e8646f42565faf124d255813c962e416131cc44ad7fc7aec4',
    '_decode_case_reference': '411bf08d74307a889670771b810df89c4125d7e66660079041c093874ca431e7',
    '_decode_record': 'b9bd14b2792a4a20a4094c65ba27768cceb859dc5a0ab8231ea3d67a8f30f1db',
    '_validate_case_references_parallel': 'b491f7157b737e35ba03acb2f5edeee636af02be5de03d1bd6673b67ef962047',
    '_validate_record': '55fc00fed5c741126c5ad64f75f6cd8a069dab9381d5b2f814366c8ba37d715a',
    'validate_document_record': '3a87f2ab1d3c68e9876f520a00e6e656f396b611bcbe3109ff67cdcefdb4a983',
    'validate_family_snapshot': '415a96859adcc9eda3a9fe69efe573e833f8fae597c67dcb86c914c41359d859',
}
