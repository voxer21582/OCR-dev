"""Local manual preparation of a private reference sheet; no OCR or network."""
from __future__ import annotations

import csv
import io
import secrets

from tools.field_trial_score import FIELDS
from tools.field_trial_sheet import SHEET

EDITABLE = ('ruolo', 'lingua', *FIELDS, 'esclusioni_motivo')


def edit_reference(rows, index, changes):
    if (not isinstance(rows, list) or type(index) is not int or not 0 <= index < len(rows)
            or not isinstance(changes, dict) or set(changes) - set(EDITABLE)):
        raise ValueError('invalid edit')
    if any(not isinstance(value, str) or len(value) > 2048 or '\x00' in value for value in changes.values()):
        raise ValueError('invalid value')
    if changes.get('ruolo', '') not in ('', 'nota', 'giustificativo') or changes.get('lingua', '') not in ('', 'it', 'en'):
        raise ValueError('invalid selection')
    result = [dict(row) for row in rows]
    result[index].update(changes)
    return result


def serialize_reference(rows):
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != set(SHEET) for row in rows):
        raise ValueError('invalid reference')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=SHEET, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def save_reference_draft(private_root, rows):
    """Write a new private draft; never replace an existing sheet."""
    from tools.field_trial_snapshot_store import _private_directory
    data = serialize_reference(rows)
    try:
        with _private_directory(private_root) as root:
            path = root / ('bozza-risposte-' + secrets.token_hex(8) + '.csv')
            with path.open('xb') as stream:
                if stream.write(data) != len(data):
                    raise OSError('short write')
            return path
    except Exception:
        raise ValueError('draft could not be saved') from None
