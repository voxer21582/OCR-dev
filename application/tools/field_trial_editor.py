"""Local manual preparation of a private reference sheet; no OCR or network."""
from __future__ import annotations

import csv
import io
import os
import re
import secrets
from contextlib import ExitStack
from pathlib import Path

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


def add_reference_documents(rows, paths):
    if (not isinstance(rows, list) or not isinstance(paths, list) or not paths
            or len(rows) + len(paths) > 50
            or any(not isinstance(path, str) or not path.strip() or '\x00' in path for path in paths)):
        raise ValueError('invalid selection')
    normalized = [os.path.normcase(os.path.abspath(path.strip())).casefold() for path in paths]
    existing = {os.path.normcase(os.path.abspath(row['percorso_locale'].strip())).casefold() for row in rows}
    if len(set(normalized)) != len(normalized) or existing.intersection(normalized):
        raise ValueError('duplicate document')
    result = [dict(row) for row in rows]
    codes = {row['codice'] for row in result}
    for path in paths:
        code = secrets.token_hex(16)
        if code in codes:
            raise ValueError('duplicate code')
        codes.add(code)
        row = {name: '' for name in SHEET}
        row.update({'codice': code, 'percorso_locale': path.strip()})
        result.append(row)
    return result


def remove_reference_document(rows, index):
    if not isinstance(rows, list) or len(rows) <= 1 or type(index) is not int or not 0 <= index < len(rows):
        raise ValueError('invalid selection')
    return [dict(row) for position, row in enumerate(rows) if position != index]


def _validate_manual_matches(rows, matches):
    roles = {row['codice']: row['ruolo'] for row in rows}
    used_codes, used_positions = set(), set()
    if not isinstance(matches, list) or len(matches) > 1000:
        raise ValueError('invalid matches')
    for item in matches:
        if not isinstance(item, dict) or set(item) != {'codice_riga', 'codice_nota', 'codice_documento_corretto', 'pagina', 'posizione'}:
            raise ValueError('invalid match')
        code, note, receipt = item['codice_riga'], item['codice_nota'], item['codice_documento_corretto']
        page, position = item['pagina'], item['posizione']
        if (not isinstance(code, str) or not re.fullmatch(r'[0-9a-f]{32}', code) or code in used_codes
                or not isinstance(note, str) or not isinstance(receipt, str)
                or roles.get(note) != 'nota' or roles.get(receipt) != 'giustificativo'
                or not isinstance(page, str) or not re.fullmatch(r'[1-9][0-9]{0,2}', page)
                or not isinstance(position, str) or not re.fullmatch(r'[1-9][0-9]{0,3}', position)):
            raise ValueError('invalid match')
        position_key = (note, page, position)
        if position_key in used_positions:
            raise ValueError('duplicate position')
        used_codes.add(code); used_positions.add(position_key)


def add_manual_match(rows, matches, note_id, receipt_id, page, position):
    _validate_manual_matches(rows, matches)
    new_item = {'codice_riga': secrets.token_hex(16), 'codice_nota': note_id,
                'codice_documento_corretto': receipt_id, 'pagina': page, 'posizione': position}
    result = [dict(item) for item in matches] + [new_item]
    _validate_manual_matches(rows, result)
    return result


def save_matching_drafts(private_root, rows, matches):
    """Save a new pair of private matching files in a fresh directory."""
    from tools.field_trial_snapshot_store import _private_directory
    from tools.field_trial_sheet import MATCHES
    _validate_manual_matches(rows, matches)
    if not matches:
        raise ValueError('no matches')
    location_header = ('codice_riga', 'codice_nota', 'pagina', 'posizione')
    try:
        with _private_directory(private_root) as root:
            directory = root / ('abbinamenti-' + secrets.token_hex(8))
            directory.mkdir()
            for filename, header in (('corrispondenze.csv', MATCHES), ('posizioni-righe.csv', location_header)):
                with (directory / filename).open('x', encoding='utf-8-sig', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=header, delimiter=';', extrasaction='ignore', lineterminator='\r\n')
                    writer.writeheader(); writer.writerows(matches)
            return directory
    except Exception:
        raise ValueError('matching drafts could not be saved') from None


def load_matching_drafts(private_root, rows, directory):
    """Read a complete matching pair under the private root, without writing."""
    from tools.field_trial_local_files import _read_sheet, open_local_file
    from tools.field_trial_sheet import MATCHES, _rows_from_bytes
    location_header = ('codice_riga', 'codice_nota', 'pagina', 'posizione')
    try:
        directory = Path(directory)
        with ExitStack() as stack:
            pairs = _rows_from_bytes(_read_sheet(stack.enter_context(open_local_file(private_root, directory / 'corrispondenze.csv'))), MATCHES)
            locations = _rows_from_bytes(_read_sheet(stack.enter_context(open_local_file(private_root, directory / 'posizioni-righe.csv'))), location_header)
        indexed = {row['codice_riga']: row for row in locations}
        if len(indexed) != len(locations) or len(pairs) != len(locations):
            raise ValueError('invalid pair')
        result = []
        for row in pairs:
            loc = indexed.pop(row['codice_riga'])
            result.append({**loc, 'codice_documento_corretto': row['codice_documento_corretto']})
        if indexed:
            raise ValueError('invalid pair')
        _validate_manual_matches(rows, result)
        return result
    except Exception:
        raise ValueError('matching drafts unavailable') from None


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
