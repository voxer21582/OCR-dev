"""Validate a completed private reference CSV, or score it in memory.

Only numeric exit codes are printed. Never put input or output in a repository.
"""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path
import re
import sys
from tools.field_trial_score import FIELDS, _load, score

SHEET = ('codice', 'percorso_locale', 'ruolo', 'lingua', *FIELDS, 'esclusioni_motivo')
MATCHES = ('codice_riga', 'codice_documento_corretto')
_LIMIT = 10 * 1024 * 1024


def _rows(path, header):
    with Path(path).open('rb') as stream:
        raw = stream.read(_LIMIT + 1)
    return _rows_from_bytes(raw, header)


def _rows_from_bytes(raw, header):
    if not isinstance(raw, bytes) or len(raw) > _LIMIT:
        raise ValueError('input too large')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=';', strict=True)
    if reader.fieldnames != list(header):
        raise ValueError('invalid header')
    rows = list(reader)
    if any(None in row or any(not isinstance(value, str) for value in row.values()) for row in rows):
        raise ValueError('invalid row')
    return rows


def convert_reference(rows, matches):
    if not 30 <= len(rows) <= 50:
        raise ValueError('invalid sample size')
    documents, roles, paths = [], {}, set()
    for row in rows:
        if set(row) != set(SHEET):
            raise ValueError('invalid row')
        doc_id = row['codice'].strip()
        local_path = row['percorso_locale'].strip().casefold()
        role, language = row['ruolo'].strip().lower(), row['lingua'].strip().lower()
        if not re.fullmatch(r'[0-9a-f]{32}', doc_id) or doc_id in roles or not local_path or local_path in paths:
            raise ValueError('invalid document')
        if role not in ('nota', 'giustificativo') or language not in ('it', 'en'):
            raise ValueError('invalid document')
        expected = {field: row[field].strip() for field in FIELDS if row[field].strip()}
        documents.append({'id': doc_id, 'language': language, 'expected': expected})
        roles[doc_id] = role
        paths.add(local_path)
    if 'nota' not in roles.values() or 'giustificativo' not in roles.values():
        raise ValueError('missing roles')
    if any(sum(doc['language'] == language and bool(doc['expected']) for doc in documents) < 5 for language in ('it', 'en')):
        raise ValueError('insufficient language coverage')
    if any(not any(field in doc['expected'] for doc in documents) for field in FIELDS):
        raise ValueError('field not evaluable')
    result, seen = [], set()
    for row in matches:
        if set(row) != set(MATCHES):
            raise ValueError('invalid match')
        row_id, target = row['codice_riga'].strip(), row['codice_documento_corretto'].strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row_id) or row_id in seen or roles.get(target) != 'giustificativo':
            raise ValueError('invalid match')
        seen.add(row_id)
        result.append({'id': row_id, 'target': target})
    if len(result) < 10:
        raise ValueError('insufficient matches')
    return {'documents': documents, 'matches': result}


def main():
    try:
        if len(sys.argv) not in (3, 4):
            raise ValueError('invalid arguments')
        reference = convert_reference(_rows(sys.argv[1], SHEET), _rows(sys.argv[2], MATCHES))
        if len(sys.argv) == 3:
            print('0')
        else:
            print(json.dumps(score(reference, _load(sys.argv[3])), separators=(',', ':')))
        return 0
    except Exception:
        print('1', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
