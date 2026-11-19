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
