"""Manage version activation only after checking the candidate installation."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile

from .runtime_manifest import verify_installation
from .app_instance import _lock, _unlock


class InstallStateError(ValueError):
    pass


@contextmanager
def _file_lock(path: Path):
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise InstallStateError('Linked lock is not allowed')
    with path.open('a+b') as handle:
        try:
            _lock(handle)
        except OSError as exc:
            raise InstallStateError('OCR2 is in use or another installation is running') from exc
        try:
            yield
        finally:
            _unlock(handle)


@contextmanager
def _transaction(base: Path):
    if base.is_symlink() or getattr(base, 'is_junction', lambda: False)():
        raise InstallStateError('Linked installation directory is not allowed')
    base.mkdir(parents=True, exist_ok=True)
    child_lock = base / '.child.lock'
    if os.environ.get('OCR2_INSTALL_LOCK_HELD') == '1':
        with _file_lock(child_lock):
            yield
    else:
        if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
            path = Path(os.environ['LOCALAPPDATA']) / 'OCR2.instance.lock'
        elif base.name.casefold() == 'ocr2' and base.parent.name.casefold() == 'programs':
            path = base.parent.parent / 'OCR2.instance.lock'
        else:
            path = base / '.install.lock'
        with _file_lock(path), _file_lock(child_lock):
            yield


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
    _check_root(root, version)


def _check_root(root: Path, version: str) -> None:
    result = verify_installation(root, root / 'runtime-manifest.json')
    if not result.ok:
        raise InstallStateError('Installation verification failed: ' + '; '.join(result.problems))
    try:
        manifest_version = json.loads((root / 'runtime-manifest.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallStateError('Invalid installation manifest') from exc
    if manifest_version != version:
        raise InstallStateError('Installation version mismatch')


def _check_stage(base: Path, version: str, staged: Path) -> None:
    staging, versions, quarantine = base / 'staging', base / 'versions', base / 'quarantine'
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (base, staging, staged, versions, quarantine)):
        raise InstallStateError('Linked installation directories are not allowed')
    if staged.resolve().parent != staging.resolve() or not staged.is_dir():
        raise InstallStateError('Invalid staging directory')
    _check_root(staged, version)
    state = _read(base)
    target = versions / version
    if target.is_symlink() or getattr(target, 'is_junction', lambda: False)():
        raise InstallStateError('Linked candidate is not allowed')
    if target.exists() and version in (state['active'], state['previous']):
        try:
            _check_root(target, version)
        except InstallStateError:
            pass
        else:
            raise InstallStateError('Cannot replace a healthy active or previous version')


def prepare(base: Path, version: str, staged: Path) -> None:
    base, staged = Path(base), Path(staged)
    _version(version)
    with _transaction(base):
        _check_stage(base, version, staged)
        versions, quarantine = base / 'versions', base / 'quarantine'
        target = versions / version
        backup = None
        if target.exists():
            quarantine.mkdir(parents=True, exist_ok=True)
            backup = quarantine / (version + '-' + secrets.token_hex(16))
            os.replace(target, backup)
        try:
            versions.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
        except OSError:
            if backup is not None:
                os.replace(backup, target)
            raise


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
    _version(version)
    with _transaction(base):
        _check(base, version)
        state = _read(base)
        if state['active'] == version:
            return
        _write(base, {'active': version, 'previous': state['active']})


def rollback(base: Path) -> str:
    base = Path(base)
    with _transaction(base):
        state = _read(base)
        previous = state['previous']
        if previous is None:
            raise InstallStateError('No previous version')
        _check(base, previous)
        _write(base, {'active': previous, 'previous': state['active']})
        return previous


def prune(base: Path) -> list[str]:
    base = Path(base)
    with _transaction(base):
        return _prune_locked(base)


def _prune_locked(base: Path) -> list[str]:
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


def cleanup_debris(base: Path) -> None:
    base = Path(base)
    with _transaction(base):
        roots = [base / 'staging', base / 'quarantine']
        for root in [base, *roots]:
            if root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
                raise InstallStateError('Linked cleanup directory is not allowed')
        def fail(error):
            raise error
        for root in roots:
            if not root.exists():
                continue
            if not root.is_dir():
                raise InstallStateError('Invalid cleanup directory')
            for current, dirs, files in os.walk(root, followlinks=False, onerror=fail):
                for name in dirs + files:
                    entry = Path(current) / name
                    if entry.is_symlink() or getattr(entry, 'is_junction', lambda: False)():
                        raise InstallStateError('Linked cleanup entry is not allowed')
        for root in roots:
            if root.exists():
                shutil.rmtree(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Gestione versioni installate OCR2')
    parser.add_argument('--base', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('activate').add_argument('version')
    sub.add_parser('verify').add_argument('version')
    prepare_parser = sub.add_parser('prepare')
    prepare_parser.add_argument('version')
    prepare_parser.add_argument('staged', type=Path)
    check_parser = sub.add_parser('check-stage')
    check_parser.add_argument('version')
    check_parser.add_argument('staged', type=Path)
    sub.add_parser('rollback')
    sub.add_parser('prune')
    sub.add_parser('cleanup-debris')
    sub.add_parser('active')
    args = parser.parse_args(argv)
    if args.base is None:
        local = os.environ.get('LOCALAPPDATA')
        if not local:
            parser.error('LOCALAPPDATA non disponibile')
        args.base = Path(local) / 'Programs' / 'OCR2'
    try:
        if args.command == 'activate':
            activate(args.base, args.version)
        elif args.command == 'verify':
            _check(args.base, args.version)
        elif args.command == 'prepare':
            prepare(args.base, args.version, args.staged)
        elif args.command == 'check-stage':
            with _transaction(args.base):
                _check_stage(args.base, _version(args.version), args.staged)
        elif args.command == 'rollback':
            print(rollback(args.base))
        elif args.command == 'active':
            active = _read(args.base)['active']
            if active is None:
                raise InstallStateError('No active version')
            _check(args.base, active)
            print(active)
        elif args.command == 'cleanup-debris':
            cleanup_debris(args.base)
        else:
            for name in prune(args.base):
                print(name)
    except (InstallStateError, OSError) as exc:
        print(f'OCR2: {exc}', file=__import__('sys').stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
