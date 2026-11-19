import json
import subprocess
import sys
import pytest
from tools.field_trial_score import score


def _inputs():
    gold = {'documents': [
        {'id': 'secret-document-one', 'language': 'it', 'expected': {'total_amount': '12.34', 'issue_date': '2026-01-01'}},
        {'id': 'secret-document-two', 'language': 'en', 'expected': {'total_amount': '5.00'}},
    ], 'matches': [{'id': 'secret-row', 'target': 'secret-document-two'}, {'id': 'secret-row-two', 'target': 'secret-document-one'}]}
    results = {'documents': [{'id': 'secret-document-one', 'fields': {'total_amount': {'status': 'observed', 'value': '12.34'}, 'issue_date': {'status': 'uncertain', 'alternatives': [{'value': '2026-01-02'}]}}}], 'matches': [{'id': 'secret-row', 'target': 'secret-document-two'}]}
    return gold, results


def test_missing_results_remain_in_denominators_and_first_suggestion_is_used():
    gold, results = _inputs()
    data = score(gold, results)
    assert data[0:2] == [2, 1]
    assert data[2:4] == [1, 2]
    assert data[4:6] == [0, 1]
    assert data[-4:-2] == [1, 1]
    assert data[-2:] == [1, 2]
    assert all(type(value) is int for value in data)


@pytest.mark.parametrize('mutation', ['duplicate_gold', 'duplicate_result', 'unknown_result', 'unknown_field', 'invalid_language'])
def test_invalid_inputs_fail_closed(mutation):
    gold, results = _inputs()
    if mutation == 'duplicate_gold': gold['documents'].append(gold['documents'][0].copy())
    elif mutation == 'duplicate_result': results['documents'].append(results['documents'][0].copy())
    elif mutation == 'unknown_result': results['documents'][0]['id'] = 'unknown'
    elif mutation == 'unknown_field': gold['documents'][0]['expected']['secret-name'] = 'secret-value'
    elif mutation == 'invalid_language': gold['documents'][0]['language'] = 'unknown'
    with pytest.raises(ValueError): score(gold, results)


def test_cli_outputs_only_numeric_aggregates_and_hides_private_input(tmp_path):
    gold, results = _inputs()
    gold_path = tmp_path / 'secret-reference.json'
    results_path = tmp_path / 'secret-results.json'
    gold_path.write_text(json.dumps(gold), encoding='utf-8')
    results_path.write_text(json.dumps(results), encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.field_trial_score', str(gold_path), str(results_path)], capture_output=True, text=True)
    assert result.returncode == 0
    assert all(type(value) is int for value in json.loads(result.stdout))
    assert 'secret' not in result.stdout + result.stderr
    assert result.stderr == ''


def test_cli_error_never_echoes_path_or_document_content(tmp_path):
    broken = tmp_path / 'secret-private-name.json'
    broken.write_text('{ secret-content', encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.field_trial_score', str(broken), str(broken)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'secret' not in result.stdout + result.stderr
    assert result.stdout == ''


def test_duplicate_rows_and_unknown_reference_target_fail_closed():
    gold, results = _inputs()
    gold['matches'].append(gold['matches'][0].copy())
    with pytest.raises(ValueError): score(gold, results)
    gold, results = _inputs()
    gold['matches'][0]['target'] = 'not-in-reference'
    with pytest.raises(ValueError): score(gold, results)


def test_unknown_row_prediction_fails_closed():
    gold, results = _inputs()
    results['matches'][0]['id'] = 'not-in-reference'
    with pytest.raises(ValueError): score(gold, results)

@pytest.mark.parametrize('payload', [{}, {'matches': []}, {'documents': 'not-a-list'}, {'documents': [], 'matches': []}])
def test_invalid_root_never_prints_traceback_or_path(tmp_path, payload):
    source = tmp_path / 'secret-reference.json'
    source.write_text(json.dumps(payload), encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.field_trial_score', str(source), str(source)], capture_output=True, text=True)
    assert result.returncode != 0
    assert result.stdout == '' and result.stderr.strip() == '1'

@pytest.mark.parametrize('candidate', [
    {'status': 'rejected', 'alternatives': [{'value': '12.34'}]},
    {'status': 'unreadable', 'alternatives': [{'value': '12.34'}]},
    {'alternatives': [{'value': '12.34'}]},
    {'status': 'fake', 'alternatives': [{'value': '12.34'}]},
])
def test_invalid_or_rejected_states_never_count_as_correct(candidate):
    gold, results = _inputs()
    results['documents'][0]['fields']['total_amount'] = candidate
    try:
        assert score(gold, results)[2] == 0
    except ValueError:
        pass


def test_document_without_evaluable_fields_remains_in_sample():
    gold, results = _inputs()
    gold['documents'][1]['expected'] = {}
    counts = score(gold, results)
    assert counts[:4] == [2, 1, 1, 1]
    assert counts[-4:-2] == [1, 0]


def test_invalid_candidate_in_nonevaluable_field_fails_closed():
    gold, results = _inputs()
    results['documents'][0]['fields']['merchant_name'] = {'status': 'fake', 'value': 'secret'}
    with pytest.raises(ValueError):
        score(gold, results)


def test_reference_csv_conversion_preserves_counts_and_rejects_wrong_match_target():
    from tools.field_trial_sheet import convert_reference
    fields = ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')
    rows = []
    for index in range(30):
        row = {'codice': f'{index:032x}', 'percorso_locale': f'secret-path-{index}', 'ruolo': 'nota' if index == 0 else 'giustificativo', 'lingua': 'en' if index < 5 else 'it', 'esclusioni_motivo': ''}
        row.update({field: 'synthetic' for field in fields})
        rows.append(row)
    matches = [{'codice_riga': f'row-{i}', 'codice_documento_corretto': f'{i+1:032x}'} for i in range(10)]
    sheet = convert_reference(rows, matches)
    assert len(sheet['documents']) == 30 and len(sheet['matches']) == 10
    assert 'secret-path' not in json.dumps(sheet)
    matches[0]['codice_documento_corretto'] = rows[0]['codice']
    with pytest.raises(ValueError): convert_reference(rows, matches)


def test_reference_csv_conversion_rejects_insufficient_language_and_empty_metric():
    from tools.field_trial_sheet import convert_reference
    fields = ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')
    rows = []
    for index in range(30):
        row = {'codice': f'{index:032x}', 'percorso_locale': f'secret-path-{index}', 'ruolo': 'nota' if index == 0 else 'giustificativo', 'lingua': 'it', 'esclusioni_motivo': ''}
        row.update({field: 'synthetic' for field in fields})
        rows.append(row)
    matches = [{'codice_riga': f'row-{i}', 'codice_documento_corretto': f'{i+1:032x}'} for i in range(10)]
    with pytest.raises(ValueError): convert_reference(rows, matches)
    for row in rows[:5]: row['lingua'] = 'en'
    for row in rows: row['merchant_name'] = ''
    with pytest.raises(ValueError): convert_reference(rows, matches)


def test_reference_csv_cli_validates_without_writing_or_echoing_contents(tmp_path):
    import csv
    from tools.field_trial_sheet import SHEET, MATCHES
    fields = ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')
    reference = tmp_path / 'secret-reference.csv'
    pairs = tmp_path / 'secret-matches.csv'
    with reference.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=SHEET, delimiter=';'); writer.writeheader()
        for index in range(30):
            row = {'codice': f'{index:032x}', 'percorso_locale': f'secret-path-{index}', 'ruolo': 'nota' if index == 0 else 'giustificativo', 'lingua': 'en' if index < 5 else 'it'}
            row.update({field: 'secret-value' for field in fields}); writer.writerow(row)
    with pairs.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=MATCHES, delimiter=';'); writer.writeheader()
        writer.writerows({'codice_riga': f'row-{i}', 'codice_documento_corretto': f'{i+1:032x}'} for i in range(10))
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.field_trial_sheet', str(reference), str(pairs)], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == '0' and result.stderr == ''
    assert 'secret' not in result.stdout + result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ['secret-matches.csv', 'secret-reference.csv']
    results = tmp_path / 'secret-results.json'
    results.write_text(json.dumps({'documents': [], 'matches': []}), encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.field_trial_sheet', str(reference), str(pairs), str(results)], capture_output=True, text=True)
    assert result.returncode == 0 and result.stderr == ''
    assert len(json.loads(result.stdout)) == 42
    assert all(type(value) is int for value in json.loads(result.stdout))
    assert 'secret' not in result.stdout + result.stderr


def _freeze_fixture():
    import csv, io
    from tools.field_trial_sheet import SHEET, MATCHES
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=SHEET, delimiter=';'); writer.writeheader()
    documents = {}
    for index in range(30):
        code = f'{index:032x}'
        row = {'codice': code, 'percorso_locale': f'secret-path-{index}', 'ruolo': 'nota' if index == 0 else 'giustificativo', 'lingua': 'en' if index < 5 else 'it'}
        row.update({field: 'synthetic' for field in ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')})
        writer.writerow(row)
        documents[code] = io.BytesIO(f'synthetic-document-{index}'.encode())
    matches = io.StringIO(newline='')
    writer = csv.DictWriter(matches, fieldnames=MATCHES, delimiter=';'); writer.writeheader()
    writer.writerows({'codice_riga': f'row-{index}', 'codice_documento_corretto': f'{index+1:032x}'} for index in range(10))
    return stream.getvalue().encode(), matches.getvalue().encode(), documents


def test_frozen_sample_binds_sheets_and_returns_exact_verified_bytes():
    import io
    from tools.field_trial_freeze import capture, verify_sheets, read_verified
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    verify_sheets(snapshot, sheet, pairs)
    assert read_verified(snapshot, f'{1:032x}', io.BytesIO(b'synthetic-document-1'), sheet, pairs) == b'synthetic-document-1'
    with pytest.raises(ValueError): verify_sheets(snapshot, sheet + b'changed', pairs)
    with pytest.raises(ValueError): read_verified(snapshot, f'{1:032x}', io.BytesIO(b'synthetic-document-1'), sheet + b'changed', pairs)
    with pytest.raises(ValueError): read_verified(snapshot, f'{1:032x}', io.BytesIO(b'changed'), sheet, pairs)
    assert 'synthetic-document' not in repr(snapshot)
    assert 'secret-path' not in repr(snapshot)


def test_frozen_sample_rejects_missing_and_duplicate_content():
    import io
    from tools.field_trial_freeze import capture
    sheet, pairs, documents = _freeze_fixture()
    missing = dict(documents); missing.pop(next(iter(missing)))
    with pytest.raises(ValueError): capture(sheet, pairs, missing)
    sheet, pairs, documents = _freeze_fixture()
    documents[f'{1:032x}'] = io.BytesIO(b'synthetic-document-0')
    with pytest.raises(ValueError): capture(sheet, pairs, documents)


def test_frozen_sample_rejects_empty_oversized_and_unknown_inputs():
    import io
    from tools.field_trial_freeze import capture, read_verified
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    with pytest.raises(ValueError): read_verified(snapshot, 'unknown', io.BytesIO(b'data'), sheet, pairs)
    with pytest.raises(ValueError): read_verified(snapshot, f'{1:032x}', io.BytesIO(b''), sheet, pairs)
    class Oversized:
        called = False
        def tell(self): return 0
        def read(self, size):
            self.called = True
            return b'x' * (25 * 1024 * 1024 + 1)
    oversized = Oversized()
    with pytest.raises(ValueError, match='document too large'):
        read_verified(snapshot, f'{1:032x}', oversized, sheet, pairs)
    assert oversized.called
    class NoPosition:
        def read(self, size): return b'data'
    with pytest.raises(ValueError, match='position unavailable'):
        read_verified(snapshot, f'{1:032x}', NoPosition(), sheet, pairs)


def test_frozen_sample_rejects_streams_not_at_start():
    import io
    from tools.field_trial_freeze import capture, read_verified
    sheet, pairs, documents = _freeze_fixture()
    moved = documents[f'{1:032x}']; moved.read(1)
    with pytest.raises(ValueError): capture(sheet, pairs, documents)
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    moved = io.BytesIO(b'synthetic-document-1'); moved.read(1)
    with pytest.raises(ValueError): read_verified(snapshot, f'{1:032x}', moved, sheet, pairs)


def test_snapshot_seal_round_trip_and_tampering_is_rejected():
    import hashlib, hmac, io
    from tools.field_trial_freeze import capture, seal, unseal, verify_sheets, read_verified
    class SyntheticProtector:
        def protect(self, data): return hmac.digest(b'synthetic-key', data, 'sha256') + data
        def unprotect(self, data):
            if not hmac.compare_digest(data[:32], hmac.digest(b'synthetic-key', data[32:], 'sha256')):
                raise ValueError('secret-test-error')
            return data[32:]
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    blob = seal(snapshot, protector=SyntheticProtector())
    restored = unseal(blob, protector=SyntheticProtector())
    verify_sheets(restored, sheet, pairs)
    assert read_verified(restored, f'{1:032x}', io.BytesIO(b'synthetic-document-1'), sheet, pairs) == b'synthetic-document-1'
    with pytest.raises(ValueError): unseal(blob[:-1] + bytes([blob[-1] ^ 1]), protector=SyntheticProtector())
    assert b'secret-path' not in blob and b'synthetic-document' not in blob


def test_snapshot_unseal_rejects_malformed_or_oversized_payloads():
    from tools.field_trial_freeze import unseal
    class SyntheticProtector:
        def unprotect(self, data): return data
    for value in (b'{}', b'{"v":1,"v":1}', b'x' * (64 * 1024 + 1)):
        with pytest.raises(ValueError): unseal(value, protector=SyntheticProtector())


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows DPAPI')
def test_snapshot_real_dpapi_round_trip_and_tamper_rejection():
    import io
    from tools.field_trial_freeze import capture, seal, unseal, read_verified
    sheet, pairs, documents = _freeze_fixture()
    blob = seal(capture(sheet, pairs, documents))
    assert b'synthetic-document' not in blob and b'secret-path' not in blob
    snapshot = unseal(blob)
    assert read_verified(snapshot, f'{2:032x}', io.BytesIO(b'synthetic-document-2'), sheet, pairs) == b'synthetic-document-2'
    changed = bytearray(blob); changed[len(changed) // 2] ^= 1
    with pytest.raises(ValueError): unseal(bytes(changed))


def test_snapshot_unseal_rejects_full_but_invalid_records():
    from tools.field_trial_freeze import unseal
    class SyntheticProtector:
        def unprotect(self, data): return data
    digest = 'a' * 64
    base = {'version': 1, 'sheet': digest, 'matches': digest,
            'documents': {f'{index:032x}': f'{index:064x}' for index in range(30)}}
    invalid = []
    for version in (True, '1', 2): invalid.append({**base, 'version': version})
    invalid.append({**base, 'sheet': 'bad'})
    invalid.append({**base, 'documents': {**base['documents'], 'bad-id': digest}})
    invalid.append({**base, 'documents': dict(list(base['documents'].items())[:29])})
    invalid.append({**base, 'documents': {f'{index:032x}': f'{index:064x}' for index in range(51)}})
    invalid.append({**base, 'documents': {key: digest for key in base['documents']}})
    for payload in invalid:
        with pytest.raises(ValueError): unseal(json.dumps(payload).encode(), protector=SyntheticProtector())


def test_snapshot_protector_failure_is_generic():
    from tools.field_trial_freeze import capture, seal, unseal
    class FailingProtector:
        def protect(self, data): raise RuntimeError('SECRET_SYNTHETIC')
        def unprotect(self, data): raise RuntimeError('SECRET_SYNTHETIC')
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    for callback in (lambda: seal(snapshot, protector=FailingProtector()), lambda: unseal(b'cipher', protector=FailingProtector())):
        with pytest.raises(ValueError) as exc: callback()
        assert 'SECRET_SYNTHETIC' not in str(exc.value)
        assert exc.value.__cause__ is None
