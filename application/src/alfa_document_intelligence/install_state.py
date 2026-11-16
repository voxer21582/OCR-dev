"""Manage version activation only after checking the candidate installation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .runtime_manifest import verify_installation


class InstallStateError(ValueError):
    pass


def _version(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', name):
        raise InstallStateError('Invalid version')
    return name


def _read(base: Path) -> dict:
    path = base / 'active.json'
    if not path.exists():
        return {'active': None, 'previous': None}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or set(state) != {'active', 'previous'}:
            raise ValueError('Invalid state')
        for value in state.values():
            if value is not None:
                _version(value)
        return state
    except (ValueError, OSError, TypeError) as exc:
        raise InstallStateError('Invalid installation state') from exc


def _check(base: Path, version: str) -> None:
    version = _version(version)
    versions = base / 'versions'
    root = versions / version
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (base, versions, root)):
        raise InstallStateError('Linked installation directories are not allowed')
    result = verify_installation(root, root / 'runtime-manifest.json')
    if not result.ok:
        raise InstallStateError('Installation verification failed: ' + '; '.join(result.problems))
    try:
        manifest_version = json.loads((root / 'runtime-manifest.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallStateError('Invalid installation manifest') from exc
    if manifest_version != version:
        raise InstallStateError('Installation version mismatch')


def _write(base: Path, state: dict) -> None:
    base.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.active-', suffix='.tmp', dir=base)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(state, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, base / 'active.json')
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def activate(base: Path, version: str) -> None:
    base = Path(base)
    _check(base, version)
    state = _read(base)
    if state['active'] == version:
        return
    _write(base, {'active': version, 'previous': state['active']})


def rollback(base: Path) -> str:
    base = Path(base)
    state = _read(base)
    previous = state['previous']
    if previous is None:
        raise InstallStateError('No previous version')
    _check(base, previous)
    _write(base, {'active': previous, 'previous': state['active']})
    return previous


def prune(base: Path) -> list[str]:
    base = Path(base)
    state = _read(base)
    if state['active'] is None:
        raise InstallStateError('No active version')
    versions = base / 'versions'
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (base, versions)):
        raise InstallStateError('Linked installation directories are not allowed')
    keep = {state['active'], state['previous']}
    entries = sorted(versions.iterdir())
    for entry in entries:
        _version(entry.name)
        if entry.is_symlink() or getattr(entry, 'is_junction', lambda: False)() or not entry.is_dir():
            raise InstallStateError('Invalid version directory')
    removed = []
    for entry in entries:
        if entry.name not in keep:
            shutil.rmtree(entry)
            removed.append(entry.name)
    return removed
