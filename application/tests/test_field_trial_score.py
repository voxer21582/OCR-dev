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


def test_manual_reference_editor_preserves_ids_and_paths_and_edits_only_allowed_fields():
    from tools.field_trial_editor import edit_reference, serialize_reference
    from tools.field_trial_sheet import SHEET, _rows_from_bytes
    sheet, _, _ = _freeze_fixture()
    rows = _rows_from_bytes(sheet, SHEET)
    old = dict(rows[0])
    edited = edit_reference(rows, 0, {'ruolo': 'nota', 'lingua': 'it', 'total_amount': '12.34'})
    assert edited[0]['codice'] == old['codice'] and edited[0]['percorso_locale'] == old['percorso_locale']
    assert edited[0]['total_amount'] == '12.34' and rows[0] == old
    assert _rows_from_bytes(serialize_reference(edited), SHEET) == edited
    with pytest.raises(ValueError): edit_reference(rows, 0, {'percorso_locale': 'different'})
    with pytest.raises(ValueError): edit_reference(rows, 0, {'ruolo': 'inventato'})
    with pytest.raises(ValueError): edit_reference(rows, 0, {'lingua': 'other'})


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows private directory checks')
def test_manual_reference_editor_saves_new_drafts_without_overwriting(tmp_path):
    from tools.field_trial_editor import save_reference_draft
    from tools.field_trial_sheet import SHEET, _rows_from_bytes
    sheet, _, _ = _freeze_fixture()
    private = tmp_path / 'private'; private.mkdir()
    rows = _rows_from_bytes(sheet, SHEET)
    first = save_reference_draft(private, rows)
    second = save_reference_draft(private, rows)
    assert first != second and _rows_from_bytes(first.read_bytes(), SHEET) == rows
    assert _rows_from_bytes(second.read_bytes(), SHEET) == rows


def test_manual_reference_editor_adds_and_removes_without_reusing_codes():
    from tools.field_trial_editor import add_reference_documents, remove_reference_document
    from tools.field_trial_sheet import SHEET, _rows_from_bytes
    sheet, _, _ = _freeze_fixture()
    rows = _rows_from_bytes(sheet, SHEET)
    original = [dict(row) for row in rows]
    updated = add_reference_documents(rows, ['new-synthetic.png'])
    assert len(updated) == 31 and rows == original
    assert updated[-1]['percorso_locale'] == 'new-synthetic.png'
    assert updated[-1]['codice'] not in {row['codice'] for row in rows}
    assert remove_reference_document(updated, 30) == original
    with pytest.raises(ValueError): add_reference_documents(rows, [rows[0]['percorso_locale']])
    with pytest.raises(ValueError): add_reference_documents(rows, ['duplicate', 'DUPLICATE'])
    with pytest.raises(ValueError): add_reference_documents(rows, [f'new-{i}' for i in range(21)])
    with pytest.raises(ValueError): remove_reference_document([rows[0]], 0)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_manual_reference_preview_reads_only_inside_authorised_root(tmp_path):
    from PIL import Image
    from tools.field_trial_editor_gui import _preview
    root = tmp_path / 'root'; root.mkdir()
    inside = root / 'synthetic.png'; Image.new('RGB', (100, 50), 'white').save(inside)
    outside = tmp_path / 'outside.png'; Image.new('RGB', (100, 50), 'white').save(outside)
    image, count = _preview(root, inside, 0)
    assert image.size == (100, 50) and count == 1
    with pytest.raises(ValueError): _preview(root, outside, 0)
    with pytest.raises(ValueError): _preview(root, inside, 1)
    pdf = root / 'synthetic.pdf'; Image.new('RGB', (100, 50), 'white').save(pdf, 'PDF')
    image, count = _preview(root, pdf, 0)
    assert image.width > 0 and image.height > 0 and count == 1


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


def test_frozen_sample_binds_row_locations_and_rejects_changes():
    from tools.field_trial_freeze import capture, verify_sheets, seal, unseal
    class Protector:
        def protect(self, data): return data
        def unprotect(self, data): return data
    sheet, pairs, documents = _freeze_fixture()
    lines = ['codice_riga;codice_nota;pagina;posizione']
    lines += [f'row-{index};{0:032x};1;{index+1}' for index in range(10)]
    locations = ('\n'.join(lines) + '\n').encode()
    snapshot = capture(sheet, pairs, documents, row_locations=locations)
    restored = unseal(seal(snapshot, protector=Protector()), protector=Protector())
    verify_sheets(restored, sheet, pairs, row_locations=locations)
    with pytest.raises(ValueError): verify_sheets(restored, sheet, pairs)
    with pytest.raises(ValueError): verify_sheets(restored, sheet, pairs, row_locations=locations + b'changed')


def test_legacy_snapshot_cannot_claim_to_bind_row_locations():
    from tools.field_trial_freeze import capture, verify_sheets
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    with pytest.raises(ValueError): verify_sheets(snapshot, sheet, pairs, row_locations=b'unbound')


def test_document_exports_score_only_bound_sources_and_numeric_results():
    import hashlib
    from tools.field_trial_freeze import capture
    from tools.field_trial_export_score import score_document_exports
    sheet, pairs, documents = _freeze_fixture()
    locations = ('codice_riga;codice_nota;pagina;posizione\n' + '\n'.join(
        f'row-{index};{0:032x};1;{index+1}' for index in range(10)) + '\n').encode()
    snapshot = capture(sheet, pairs, documents, row_locations=locations)
    source = hashlib.sha256(b'synthetic-document-1').hexdigest()
    record = {'source': {'sha256': source}, 'processing': {'ocr': {'status': 'completed'}},
              'fields': {'total_amount': {'status': 'observed', 'value': 'synthetic'}}}
    output = score_document_exports(snapshot, sheet, pairs, locations, [record])
    assert len(output) == 40 and all(type(item) is int for item in output)
    assert output[:4] == [30, 29, 1, 30]
    uncertain = {**record, 'fields': {'total_amount': {'status': 'uncertain', 'alternatives': [{'value': 'wrong'}, {'value': 'synthetic'}]}}}
    assert score_document_exports(snapshot, sheet, pairs, locations, [uncertain])[:4] == [30, 29, 0, 30]
    with pytest.raises(ValueError): score_document_exports(snapshot, sheet, pairs, locations, [record, record])
    with pytest.raises(ValueError): score_document_exports(snapshot, sheet, pairs, locations, [{**record, 'source': {'sha256': '0' * 64}}])
    with pytest.raises(ValueError): score_document_exports(snapshot, sheet, pairs, locations + b'changed', [record])
    failed = {**record, 'processing': {'ocr': {'status': 'failed'}}}
    assert score_document_exports(snapshot, sheet, pairs, locations, [failed])[:4] == [30, 30, 0, 30]


def test_case_matches_use_first_suggestion_for_manually_mapped_rows(monkeypatch):
    import hashlib
    import alfa_document_intelligence.case_export_reader as reader
    from tools.field_trial_freeze import capture
    from tools.field_trial_export_score import score_case_matches
    sheet, pairs, documents = _freeze_fixture()
    locations = ('codice_riga;codice_nota;pagina;posizione\n' + '\n'.join(
        f'row-{index};{0:032x};1;{index+1}' for index in range(10)) + '\n').encode()
    snapshot = capture(sheet, pairs, documents, row_locations=locations)
    digest = lambda index: hashlib.sha256(f'synthetic-document-{index}'.encode()).hexdigest()
    case = {'statement': {'document_id': 'note', 'source_sha256': digest(0)},
            'attachments': [{'document_id': f'doc-{i}', 'source_sha256': digest(i)} for i in range(1, 11)],
            'lines': [{'line_id': 'line-1', 'suggestions': [{'document_id': 'doc-1', 'source_sha256': digest(1)}]}]}
    monkeypatch.setattr(reader, 'read_case_export', lambda text: case)
    mapping = {f'row-{i}': None for i in range(10)}; mapping['row-0'] = 'line-1'
    assert score_case_matches(snapshot, sheet, pairs, locations, 'synthetic-export', mapping) == [1, 10]
    case['lines'][0]['suggestions'].insert(0, {'document_id': 'doc-2', 'source_sha256': digest(2)})
    assert score_case_matches(snapshot, sheet, pairs, locations, 'synthetic-export', mapping) == [0, 10]
    with pytest.raises(ValueError): score_case_matches(snapshot, sheet, pairs, locations, 'synthetic-export', {**mapping, 'row-1': 'line-1'})
    with pytest.raises(ValueError): score_case_matches(snapshot, sheet, pairs, locations, 'synthetic-export', {**mapping, 'row-1': 'unknown'})
    with pytest.raises(ValueError): score_case_matches(snapshot, sheet, pairs, locations + b'changed', 'synthetic-export', mapping)


def test_case_match_scoring_rejects_malformed_case_export():
    from tools.field_trial_freeze import capture
    from tools.field_trial_export_score import score_case_matches
    sheet, pairs, documents = _freeze_fixture()
    locations = ('codice_riga;codice_nota;pagina;posizione\n' + '\n'.join(
        f'row-{index};{0:032x};1;{index+1}' for index in range(10)) + '\n').encode()
    snapshot = capture(sheet, pairs, documents, row_locations=locations)
    with pytest.raises(ValueError):
        score_case_matches(snapshot, sheet, pairs, locations, '{}', {f'row-{i}': None for i in range(10)})


def test_frozen_sample_rejects_incomplete_or_duplicate_row_locations():
    from tools.field_trial_freeze import capture
    def locations(lines):
        return ('codice_riga;codice_nota;pagina;posizione\n' + '\n'.join(lines) + '\n').encode()
    valid = [f'row-{index};{0:032x};1;{index+1}' for index in range(10)]
    for rows in (valid[:-1], valid + [valid[0]], valid[:-1] + [f'row-9;{1:032x};1;10'], valid[:-1] + [f'row-9;{0:032x};1;1']):
        sheet, pairs, documents = _freeze_fixture()
        with pytest.raises(ValueError): capture(sheet, pairs, documents, row_locations=locations(rows))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_current_files_bind_row_locations_and_reject_later_changes(tmp_path):
    from tools.field_trial_local_files import capture_current, read_current
    from tools.field_trial_freeze import seal, unseal
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    private = tmp_path / 'private'; private.mkdir()
    reference = private / 'reference.csv'; reference.write_bytes(sheet)
    matches = private / 'matches.csv'; matches.write_bytes(pairs)
    mapping = private / 'locations.csv'
    lines = ['codice_riga;codice_nota;pagina;posizione']
    lines += [f'row-{index};{0:032x};1;{index+1}' for index in range(10)]
    mapping.write_bytes(('\n'.join(lines) + '\n').encode())
    snapshot = capture_current(private, reference, matches, root, row_locations_path=mapping)
    snapshot = unseal(seal(snapshot))
    assert read_current(snapshot, private, reference, matches, root, f'{1:032x}', row_locations_path=mapping) == b'synthetic-document-1'
    mapping.write_bytes(mapping.read_bytes() + b'changed')
    with pytest.raises(ValueError): read_current(snapshot, private, reference, matches, root, f'{1:032x}', row_locations_path=mapping)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_verified_batch_uses_only_frozen_bytes_and_pseudonymous_names(tmp_path):
    from tools.field_trial_local_files import capture_current, read_verified_batch
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    private = tmp_path / 'private'; private.mkdir()
    reference = private / 'reference.csv'; reference.write_bytes(sheet)
    matches = private / 'matches.csv'; matches.write_bytes(pairs)
    mapping = private / 'locations.csv'
    lines = ['codice_riga;codice_nota;pagina;posizione']
    lines += [f'row-{index};{0:032x};1;{index+1}' for index in range(10)]
    mapping.write_bytes(('\n'.join(lines) + '\n').encode())
    snapshot = capture_current(private, reference, matches, root, row_locations_path=mapping)
    ids = [f'{0:032x}', f'{1:032x}']
    result = read_verified_batch(snapshot, private, reference, matches, mapping, root, ids[:1], role='nota')
    assert result == [(f'{0:032x}.pdf', b'synthetic-document-0')]
    result = read_verified_batch(snapshot, private, reference, matches, mapping, root, ids[1:], role='giustificativo')
    assert result == [(f'{1:032x}.pdf', b'synthetic-document-1')]
    with pytest.raises(ValueError): read_verified_batch(snapshot, private, reference, matches, mapping, root, ids, role='giustificativo')
    with pytest.raises(ValueError): read_verified_batch(snapshot, private, reference, matches, mapping, root, ids * 11, role='giustificativo')
    with pytest.raises(ValueError): read_verified_batch(snapshot, private, reference, matches, mapping, root, ids[1:] * 2, role='giustificativo')
    legacy = capture_current(private, reference, matches, root)
    with pytest.raises(ValueError): read_verified_batch(legacy, private, reference, matches, mapping, root, ids[1:], role='giustificativo')
    original_mapping = mapping.read_bytes(); mapping.write_bytes(original_mapping + b'changed')
    with pytest.raises(ValueError): read_verified_batch(snapshot, private, reference, matches, mapping, root, ids[1:], role='giustificativo')
    mapping.write_bytes(original_mapping)
    (root / 'synthetic-1.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError): read_verified_batch(snapshot, private, reference, matches, mapping, root, ids[1:], role='giustificativo')


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


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_open_pins_content_and_enforces_root(tmp_path):
    import os
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'SYNTHETIC')
    outside = tmp_path / 'outside.pdf'; outside.write_bytes(b'OUTSIDE_SYNTHETIC')
    with open_local_file(root, path) as stream:
        assert stream.read() == b'SYNTHETIC'
        with pytest.raises(OSError): path.rename(root / 'moved.pdf')
        with pytest.raises(OSError): path.write_bytes(b'CHANGED')
    path.rename(root / 'moved.pdf')
    with pytest.raises(ValueError):
        with open_local_file(root, outside): pass


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_open_rejects_junction_hardlink_and_directories(tmp_path):
    import os, _winapi
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    target = outside / 'doc.pdf'; target.write_bytes(b'SYNTHETIC')
    junction = root / 'junction'; _winapi.CreateJunction(str(outside), str(junction))
    with pytest.raises(ValueError):
        with open_local_file(root, junction / 'doc.pdf'): pass
    link = root / 'hardlink.pdf'; os.link(target, link)
    with pytest.raises(ValueError):
        with open_local_file(root, link): pass
    with pytest.raises(ValueError):
        with open_local_file(root, root): pass


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_bytes_remain_identical_after_release(tmp_path):
    import io
    from tools.field_trial_freeze import capture, read_verified
    from tools.field_trial_local_files import open_local_file
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'synthetic-document-1')
    with open_local_file(root, path) as stream:
        verified = read_verified(snapshot, f'{1:032x}', stream, sheet, pairs)
    path.write_bytes(b'changed-after-close')
    assert verified == b'synthetic-document-1'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_errors_do_not_expose_paths(tmp_path):
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'SYNTHETIC_SECRET_ROOT'; root.mkdir()
    with pytest.raises(ValueError) as exc:
        with open_local_file(root, root / 'SYNTHETIC_SECRET_MISSING'): pass
    assert 'SYNTHETIC_SECRET' not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_preserves_caller_error_and_releases_handle(tmp_path):
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'SYNTHETIC')
    failure = RuntimeError('SYNTHETIC_CALLER_ERROR')
    with pytest.raises(RuntimeError) as caught:
        with open_local_file(root, path):
            raise failure
    assert caught.value is failure
    path.rename(root / 'after.pdf')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows NTFS streams')
def test_private_file_rejects_alternate_data_stream(tmp_path):
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'SYNTHETIC')
    ads = str(path) + ':synthetic'
    try:
        with open(ads, 'wb') as stream: stream.write(b'SYNTHETIC_ALTERNATE')
    except OSError:
        pytest.skip('alternate streams unavailable on this filesystem')
    with pytest.raises(ValueError):
        with open_local_file(root, ads): pass


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_private_file_pins_parent_against_concurrent_swap(tmp_path, monkeypatch):
    import os
    from contextlib import contextmanager
    import alfa_document_intelligence.__main__ as launcher
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'SYNTHETIC')
    original = launcher._lock_plain_windows_directory
    attempted = []
    @contextmanager
    def checked(directory):
        with original(directory):
            if os.path.normcase(str(directory)) == os.path.normcase(str(root)):
                with pytest.raises(OSError): root.rename(root.with_name('swapped'))
                attempted.append(True)
            yield
    monkeypatch.setattr(launcher, '_lock_plain_windows_directory', checked)
    with open_local_file(root, path) as stream:
        assert stream.read() == b'SYNTHETIC'
    assert attempted == [True]
    root.rename(root.with_name('after'))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows sharing rules')
def test_private_file_rejects_existing_writer_and_recovers(tmp_path):
    from tools.field_trial_local_files import open_local_file
    root = tmp_path / 'authorised'; root.mkdir()
    path = root / 'synthetic.pdf'; path.write_bytes(b'SYNTHETIC')
    with path.open('ab'):
        with pytest.raises(ValueError):
            with open_local_file(root, path): pass
    with open_local_file(root, path) as stream:
        assert stream.read() == b'SYNTHETIC'


def _local_freeze_fixture(tmp_path):
    import csv, io
    from tools.field_trial_sheet import SHEET, MATCHES
    root = tmp_path / 'authorised'; root.mkdir()
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=SHEET, delimiter=';'); writer.writeheader()
    for index in range(30):
        path = root / f'synthetic-{index}.pdf'; path.write_bytes(f'synthetic-document-{index}'.encode())
        row = {'codice': f'{index:032x}', 'percorso_locale': str(path), 'ruolo': 'nota' if index == 0 else 'giustificativo', 'lingua': 'en' if index < 5 else 'it'}
        row.update({field: 'synthetic' for field in ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')})
        writer.writerow(row)
    matches = io.StringIO(newline='')
    writer = csv.DictWriter(matches, fieldnames=MATCHES, delimiter=';'); writer.writeheader()
    writer.writerows({'codice_riga': f'row-{index}', 'codice_documento_corretto': f'{index+1:032x}'} for index in range(10))
    return root, stream.getvalue().encode(), matches.getvalue().encode()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_local_capture_binds_approved_sheet_to_correct_file(tmp_path):
    from tools.field_trial_local_files import capture_local, read_bound_local
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    snapshot = capture_local(sheet, pairs, root)
    assert read_bound_local(snapshot, sheet, pairs, root, f'{1:032x}') == b'synthetic-document-1'
    (root / 'synthetic-1.pdf').write_bytes(b'CHANGED_SYNTHETIC')
    with pytest.raises(ValueError): read_bound_local(snapshot, sheet, pairs, root, f'{1:032x}')
    with pytest.raises(ValueError): read_bound_local(snapshot, sheet + b'changed', pairs, root, f'{2:032x}')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_local_capture_rejects_document_outside_authorised_root(tmp_path):
    from tools.field_trial_local_files import capture_local
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    outside = tmp_path / 'synthetic-outside.pdf'; outside.write_bytes(b'OUTSIDE')
    altered = sheet.replace(str(root / 'synthetic-1.pdf').encode(), str(outside).encode())
    with pytest.raises(ValueError): capture_local(altered, pairs, root)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_local_capture_releases_handles_on_late_error_or_duplicate(tmp_path):
    from tools.field_trial_local_files import capture_local
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    (root / 'synthetic-29.pdf').unlink()
    with pytest.raises(ValueError): capture_local(sheet, pairs, root)
    root.rename(root.with_name('after-missing'))
    root = root.with_name('after-missing')
    root.rename(tmp_path / 'authorised')
    root = tmp_path / 'authorised'
    (root / 'synthetic-29.pdf').write_bytes(b'synthetic-document-0')
    with pytest.raises(ValueError): capture_local(sheet, pairs, root)
    root.rename(root.with_name('after-duplicate'))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_current_sheets_are_read_from_guarded_private_files(tmp_path):
    from tools.field_trial_local_files import capture_current, read_current
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    private = tmp_path / 'private'; private.mkdir()
    reference = private / 'reference.csv'; reference.write_bytes(sheet)
    matches = private / 'matches.csv'; matches.write_bytes(pairs)
    snapshot = capture_current(private, reference, matches, root)
    assert read_current(snapshot, private, reference, matches, root, f'{1:032x}') == b'synthetic-document-1'
    reference.write_bytes(sheet + b'changed')
    with pytest.raises(ValueError): read_current(snapshot, private, reference, matches, root, f'{1:032x}')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_current_sheets_reject_modified_matches_and_release_first_on_error(tmp_path):
    from tools.field_trial_local_files import capture_current, read_current
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    private = tmp_path / 'private'; private.mkdir()
    reference = private / 'reference.csv'; reference.write_bytes(sheet)
    matches = private / 'matches.csv'; matches.write_bytes(pairs)
    snapshot = capture_current(private, reference, matches, root)
    matches.write_bytes(pairs + b'changed')
    with pytest.raises(ValueError): read_current(snapshot, private, reference, matches, root, f'{1:032x}')
    matches.unlink()
    with pytest.raises(ValueError): capture_current(private, reference, matches, root)
    reference.rename(private / 'released.csv')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows handle protections')
def test_current_sheets_remain_locked_while_capture_runs(tmp_path, monkeypatch):
    import tools.field_trial_local_files as local_files
    root, sheet, pairs = _local_freeze_fixture(tmp_path)
    private = tmp_path / 'private'; private.mkdir()
    reference = private / 'reference.csv'; reference.write_bytes(sheet)
    matches = private / 'matches.csv'; matches.write_bytes(pairs)
    reached = []
    def probe(reference_bytes, matches_bytes, authorised_root):
        with pytest.raises(OSError): reference.write_bytes(b'changed')
        with pytest.raises(OSError): matches.write_bytes(b'changed')
        reached.append(True)
        return 'synthetic'
    monkeypatch.setattr(local_files, 'capture_local', probe)
    assert local_files.capture_current(private, reference, matches, root) == 'synthetic'
    assert reached == [True]
    reference.write_bytes(sheet)


def test_sheet_read_rejects_oversized_data():
    import io
    from tools.field_trial_local_files import _read_sheet
    with pytest.raises(ValueError): _read_sheet(io.BytesIO(b'x' * (10 * 1024 * 1024 + 1)))


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows DPAPI and handle protections')
def test_snapshot_private_persistence_authenticates_approved_ciphertext(tmp_path):
    import io, os
    from tools.field_trial_freeze import capture, read_verified
    from tools.field_trial_snapshot_store import save_snapshot, load_snapshot
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    private = tmp_path / 'private'; private.mkdir()
    path, approval_token = save_snapshot(private, snapshot)
    protected = path.read_bytes()
    assert b'secret-path' not in protected and b'synthetic-document' not in protected
    restored = load_snapshot(private, path, approval_token)
    assert read_verified(restored, f'{1:032x}', io.BytesIO(b'synthetic-document-1'), sheet, pairs) == b'synthetic-document-1'
    other, _ = save_snapshot(private, snapshot)
    os.replace(other, path)  # a different valid DPAPI blob, not the approved blob
    with pytest.raises(ValueError): load_snapshot(private, path, approval_token)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows DPAPI and handle protections')
def test_snapshot_persistence_rejects_repository_and_invalid_token(tmp_path):
    from tools.field_trial_freeze import capture
    from tools.field_trial_snapshot_store import save_snapshot, load_snapshot
    sheet, pairs, documents = _freeze_fixture()
    snapshot = capture(sheet, pairs, documents)
    project = tmp_path / 'project'; project.mkdir(); (project / '.git').mkdir()
    private = project / 'private'; private.mkdir()
    with pytest.raises(ValueError): save_snapshot(private, snapshot)
    assert list(private.iterdir()) == []
    safe = tmp_path / 'safe'; safe.mkdir()
    path, token = save_snapshot(safe, snapshot)
    for invalid in (b'', b'x' * 31, 'secret-token'):
        with pytest.raises(ValueError): load_snapshot(safe, path, invalid)
