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
