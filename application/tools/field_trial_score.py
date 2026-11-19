"""Score a local field-trial sheet; output is numeric aggregates only."""
from __future__ import annotations
import json
import sys
from pathlib import Path

FIELDS = ('total_amount', 'issue_date', 'currency', 'document_number', 'vat_registration_number', 'merchant_name')
LANGUAGES = ('it', 'en')
_MAX_INPUT_BYTES = 10 * 1024 * 1024


def _documents(value):
    if not isinstance(value, dict) or set(value) - {'documents', 'matches'} or not isinstance(value.get('documents'), list):
        raise ValueError('invalid input')
    mapped = {}
    for doc in value['documents']:
        if not isinstance(doc, dict) or not isinstance(doc.get('id'), str) or not doc['id'] or doc['id'] in mapped:
            raise ValueError('invalid input')
        mapped[doc['id']] = doc
    return mapped


def _first_value(candidate):
    if candidate is None:
        return None
    status = candidate.get('status')
    if status not in ('observed', 'uncertain', 'unreadable', 'absent', 'not_applicable', 'rejected'):
        raise ValueError('invalid candidate status')
    if status == 'observed':
        value = candidate.get('value')
        if not isinstance(value, str):
            raise ValueError('invalid candidate')
        return value
    if status != 'uncertain':
        return None
    alternatives = candidate.get('alternatives')
    if not isinstance(alternatives, list):
        raise ValueError('invalid candidate')
    if not alternatives:
        return None
    first = alternatives[0]
    if not isinstance(first, dict) or not isinstance(first.get('value'), str):
        raise ValueError('invalid candidate')
    if first.get('status') in ('rejected', 'unreadable'):
        return None
    if first.get('status') not in (None, 'observed', 'uncertain'):
        raise ValueError('invalid candidate')
    return first['value']


def score(reference, results):
    gold, actual = _documents(reference), _documents(results)
    if not gold or set(actual) - set(gold):
        raise ValueError('invalid input')
    for doc in gold.values():
        if set(doc) - {'id', 'language', 'expected'} or doc.get('language') not in LANGUAGES:
            raise ValueError('invalid input')
        expected = doc.get('expected')
        if not isinstance(expected, dict) or set(expected) - set(FIELDS):
            raise ValueError('invalid input')
        if any(not isinstance(v, str) or not v for v in expected.values()):
            raise ValueError('invalid input')
    for doc in actual.values():
        if set(doc) - {'id', 'fields'} or not isinstance(doc.get('fields'), dict):
            raise ValueError('invalid input')
        if set(doc['fields']) - set(FIELDS) or any(not isinstance(v, dict) for v in doc['fields'].values()):
            raise ValueError('invalid input')
        for candidate in doc['fields'].values():
            _first_value(candidate)
    out = [len(gold), len(set(gold) - set(actual))]
    for language in (None, *LANGUAGES):
        for field in FIELDS:
            eligible = [(key, doc) for key, doc in gold.items() if (language is None or doc['language'] == language) and field in doc['expected']]
            correct = sum(_first_value(actual.get(key, {}).get('fields', {}).get(field)) == doc['expected'][field] for key, doc in eligible)
            out.extend((correct, len(eligible)))
    expected_matches = _matches(reference.get('matches', []))
    actual_matches = _matches(results.get('matches', []))
    if set(actual_matches) - set(expected_matches) or any(target not in gold for target in expected_matches.values()):
        raise ValueError('invalid input')
    out.extend(sum(doc['language'] == language and bool(doc['expected']) for doc in gold.values()) for language in LANGUAGES)
    out.extend((sum(actual_matches.get(key) == target for key, target in expected_matches.items()), len(expected_matches)))
    return out


def _matches(items):
    if not isinstance(items, list):
        raise ValueError('invalid input')
    result = {}
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'id', 'target'}
                or not isinstance(item['id'], str) or not item['id']
                or not isinstance(item['target'], str) or not item['target']
                or item['id'] in result):
            raise ValueError('invalid input')
        result[item['id']] = item['target']
    return result


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(_MAX_INPUT_BYTES + 1)
    if len(raw) > _MAX_INPUT_BYTES:
        raise ValueError('input too large')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid number')))


def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError('invalid arguments')
        result = score(_load(sys.argv[1]), _load(sys.argv[2]))
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except Exception:
        print('1', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
