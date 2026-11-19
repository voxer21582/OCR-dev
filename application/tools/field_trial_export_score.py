"""Score individual exports in memory against a frozen field-trial sample.

An export's source hash does not authenticate its contents or prove that it
came from the approved execution. Callers must establish that provenance and
keep both the reference and records private. Matching is not scored here.
"""
from __future__ import annotations

import re

from tools.field_trial_freeze import verify_sheets
from tools.field_trial_score import FIELDS, score
from tools.field_trial_sheet import MATCHES, SHEET, _rows_from_bytes, convert_reference


def score_document_exports(snapshot, sheet, matches, row_locations, records):
    """Return 40 field counts; matching must be evaluated separately."""
    try:
        if snapshot._row_locations_digest is None:
            raise ValueError('unbound reference')
        verify_sheets(snapshot, sheet, matches, row_locations=row_locations)
        reference = convert_reference(_rows_from_bytes(sheet, SHEET), _rows_from_bytes(matches, MATCHES))
        if not isinstance(records, list) or len(records) > len(snapshot._documents):
            raise ValueError('invalid records')
        source_ids = {digest.hex(): code for code, digest in snapshot._documents.items()}
        actual, seen = [], set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get('source'), dict):
                raise ValueError('invalid record')
            digest = record['source'].get('sha256')
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) or digest not in source_ids or digest in seen:
                raise ValueError('invalid source')
            seen.add(digest)
            processing = record.get('processing')
            if not isinstance(processing, dict) or not isinstance(processing.get('ocr'), dict):
                raise ValueError('invalid processing status')
            if processing['ocr'].get('status') != 'completed':
                continue
            fields = record.get('fields')
            if not isinstance(fields, dict):
                raise ValueError('invalid fields')
            actual.append({'id': source_ids[digest], 'fields': {key: fields[key] for key in FIELDS if key in fields}})
        return score(reference, {'documents': actual, 'matches': []})[:40]
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError('invalid trial exports') from None


def score_case_matches(snapshot, sheet, matches, row_locations, case_export, row_mapping):
    """Score first suggestions for one note using an independently checked row map.

    This cannot authenticate the case export or validate the human row map.
    Unrecognized rows are represented by None and remain in the denominator.
    """
    from alfa_document_intelligence.case_export_reader import read_case_export
    try:
        if snapshot._row_locations_digest is None:
            raise ValueError('unbound reference')
        verify_sheets(snapshot, sheet, matches, row_locations=row_locations)
        reference_rows = _rows_from_bytes(sheet, SHEET)
        match_rows = _rows_from_bytes(matches, MATCHES)
        location_rows = _rows_from_bytes(row_locations, ('codice_riga', 'codice_nota', 'pagina', 'posizione'))
        case = read_case_export(case_export)
        source_ids = {digest.hex(): code for code, digest in snapshot._documents.items()}
        roles = {row['codice'].strip(): row['ruolo'].strip().lower() for row in reference_rows}
        note_id = source_ids.get(case['statement']['source_sha256'])
        if roles.get(note_id) != 'nota':
            raise ValueError('unknown note')
        attached = [source_ids.get(item['source_sha256']) for item in case['attachments']]
        if any(roles.get(item) != 'giustificativo' for item in attached) or len(set(attached)) != len(attached):
            raise ValueError('invalid attachments')
        expected = {row['codice_riga'].strip(): row['codice_documento_corretto'].strip() for row in match_rows}
        row_ids = {row['codice_riga'].strip() for row in location_rows if row['codice_nota'].strip() == note_id}
        if not row_ids or not row_ids <= expected.keys() or not isinstance(row_mapping, dict) or set(row_mapping) != row_ids:
            raise ValueError('invalid row map')
        if any(expected[row_id] not in attached for row_id in row_ids):
            raise ValueError('missing expected attachments')
        mapped = [value for value in row_mapping.values() if value is not None]
        lines = {line['line_id']: line for line in case['lines']}
        if (any(not isinstance(value, str) or value not in lines for value in mapped)
                or len(set(mapped)) != len(mapped)):
            raise ValueError('invalid mapped line')
        correct = 0
        for row_id in row_ids:
            line_id = row_mapping[row_id]
            suggestions = lines[line_id]['suggestions'] if line_id is not None else []
            if suggestions and source_ids.get(suggestions[0]['source_sha256']) == expected[row_id]:
                correct += 1
        return [correct, len(row_ids)]
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError('invalid trial case') from None
