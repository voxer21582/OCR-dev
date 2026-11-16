import json

import pytest

from alfa_document_intelligence import install_state
from alfa_document_intelligence.runtime_manifest import build_manifest


@pytest.fixture(autouse=True)
def _synthetic_profile(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))


def _version(base, name):
    root = base / 'versions' / name
    (root / 'python').mkdir(parents=True)
    for filename in ('python.exe', 'pythonw.exe', 'python313.zip'):
        (root / 'python' / filename).write_bytes(b'synthetic')
    package = root / 'app/alfa_document_intelligence'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    (root / 'runtime-manifest.json').write_text(json.dumps(build_manifest(root, version=name, excluded_globs=())), encoding='utf-8')
    return root


def test_activate_and_rollback_verify_before_switching(tmp_path):
    _version(tmp_path, '0.6.0'); newer = _version(tmp_path, '0.6.1')
    install_state.activate(tmp_path, '0.6.0')
    before = (tmp_path / 'active.json').read_bytes()
    (newer / 'python/python.exe').write_bytes(b'tampered')
    with pytest.raises(install_state.InstallStateError):
        install_state.activate(tmp_path, '0.6.1')
    assert (tmp_path / 'active.json').read_bytes() == before
    (newer / 'python/python.exe').write_bytes(b'synthetic')
    install_state.activate(tmp_path, '0.6.1')
    assert install_state.rollback(tmp_path) == '0.6.0'


def test_interrupted_atomic_activation_preserves_old_state(tmp_path, monkeypatch):
    _version(tmp_path, '0.6.0'); _version(tmp_path, '0.6.1')
    install_state.activate(tmp_path, '0.6.0')
    before = (tmp_path / 'active.json').read_bytes()
    def fail(*args):
        raise OSError('synthetic failure')
    monkeypatch.setattr(install_state.os, 'replace', fail)
    with pytest.raises(OSError):
        install_state.activate(tmp_path, '0.6.1')
    assert (tmp_path / 'active.json').read_bytes() == before


def test_rejects_unsafe_version(tmp_path):
    with pytest.raises(install_state.InstallStateError):
        install_state.activate(tmp_path, '../outside')


def test_prune_preserves_active_and_previous(tmp_path):
    for version in ('0.5.0', '0.6.0', '0.6.1'):
        _version(tmp_path, version)
    install_state.activate(tmp_path, '0.6.0')
    install_state.activate(tmp_path, '0.6.1')
    assert install_state.prune(tmp_path) == ['0.5.0']
    assert (tmp_path / 'versions/0.6.0').is_dir()
    assert (tmp_path / 'versions/0.6.1').is_dir()


def test_prune_rejects_unexpected_version_directory(tmp_path):
    _version(tmp_path, '0.6.0')
    install_state.activate(tmp_path, '0.6.0')
    (tmp_path / 'versions/unexpected').mkdir()
    with pytest.raises(install_state.InstallStateError):
        install_state.prune(tmp_path)
    assert (tmp_path / 'versions/unexpected').is_dir()


def test_cli_activates_with_explicit_base(tmp_path):
    _version(tmp_path, '0.6.0')
    assert install_state.main(['--base', str(tmp_path), 'activate', '0.6.0']) == 0
    assert json.loads((tmp_path / 'active.json').read_text())['active'] == '0.6.0'


def test_cli_active_only_reports_verified_version(tmp_path, capsys):
    root = _version(tmp_path, '0.6.0')
    install_state.activate(tmp_path, '0.6.0')
    assert install_state.main(['--base', str(tmp_path), 'active']) == 0
    assert capsys.readouterr().out.strip() == '0.6.0'
    (root / 'python/python.exe').write_bytes(b'tampered')
    assert install_state.main(['--base', str(tmp_path), 'active']) == 1
    assert capsys.readouterr().out == ''


def test_cli_verify_does_not_activate(tmp_path):
    _version(tmp_path, '0.6.0')
    assert install_state.main(['--base', str(tmp_path), 'verify', '0.6.0']) == 0
    assert not (tmp_path / 'active.json').exists()


def test_activation_is_blocked_while_app_holds_lock(tmp_path):
    from alfa_document_intelligence import app_instance
    base = tmp_path / 'Programs' / 'OCR2'
    _version(base, '0.6.0')
    lock = app_instance.acquire(tmp_path / 'OCR2')
    assert lock is not None
    try:
        with pytest.raises(install_state.InstallStateError, match='in use'):
            install_state.activate(base, '0.6.0')
        assert not (base / 'active.json').exists()
    finally:
        lock.release()
    install_state.activate(base, '0.6.0')


def test_child_transaction_remains_exclusive_when_parent_lock_is_bypassed(tmp_path, monkeypatch):
    _version(tmp_path, '0.6.0')
    monkeypatch.setenv('OCR2_INSTALL_LOCK_HELD', '1')
    with install_state._transaction(tmp_path):
        with pytest.raises(install_state.InstallStateError, match='in use'):
            install_state.activate(tmp_path, '0.6.0')


def test_prepare_repairs_unreferenced_damaged_candidate_without_deleting_it(tmp_path):
    broken = _version(tmp_path, '0.6.1')
    (broken / 'python/python.exe').write_bytes(b'broken')
    stage = _version(tmp_path, '0.6.2')
    (stage / 'runtime-manifest.json').write_text(json.dumps(build_manifest(stage, version='0.6.1', excluded_globs=())), encoding='utf-8')
    staging = tmp_path / 'staging'
    staging.mkdir()
    stage = stage.rename(staging / 'temporary')
    install_state.prepare(tmp_path, '0.6.1', stage)
    assert (tmp_path / 'versions/0.6.1/python/python.exe').read_bytes() == b'synthetic'
    assert any((p / 'python/python.exe').read_bytes() == b'broken' for p in (tmp_path / 'quarantine').iterdir())


def test_prepare_does_not_replace_active_version(tmp_path):
    active = _version(tmp_path, '0.6.0')
    install_state.activate(tmp_path, '0.6.0')
    staging = tmp_path / 'staging'; staging.mkdir()
    stage = _version(tmp_path, '0.6.1').rename(staging / 'temporary')
    (stage / 'runtime-manifest.json').write_text(json.dumps(build_manifest(stage, version='0.6.0', excluded_globs=())), encoding='utf-8')
    before = (active / 'python/python.exe').read_bytes()
    with pytest.raises(install_state.InstallStateError):
        install_state.prepare(tmp_path, '0.6.0', stage)
    assert (active / 'python/python.exe').read_bytes() == before


def test_prepare_can_restore_corrupt_active_version_from_verified_stage(tmp_path):
    active = _version(tmp_path, '0.6.0')
    install_state.activate(tmp_path, '0.6.0')
    (active / 'python/python.exe').write_bytes(b'broken')
    staging = tmp_path / 'staging'; staging.mkdir()
    stage = _version(tmp_path, '0.6.1').rename(staging / 'temporary')
    (stage / 'runtime-manifest.json').write_text(json.dumps(build_manifest(stage, version='0.6.0', excluded_globs=())), encoding='utf-8')
    install_state.prepare(tmp_path, '0.6.0', stage)
    assert (active / 'python/python.exe').read_bytes() == b'synthetic'
    assert json.loads((tmp_path / 'active.json').read_text())['active'] == '0.6.0'


def test_check_stage_does_not_move_candidate(tmp_path):
    stage = _version(tmp_path, '0.6.0')
    staging = tmp_path / 'staging'; staging.mkdir()
    stage = stage.rename(staging / 'temporary')
    assert install_state.main(['--base', str(tmp_path), 'check-stage', '0.6.0', str(stage)]) == 0
    assert stage.is_dir()
    assert not (tmp_path / 'versions/0.6.0').exists()


def test_cleanup_debris_removes_only_staging_and_quarantine(tmp_path):
    for directory in ('staging', 'quarantine'):
        path = tmp_path / directory / 'synthetic'
        path.mkdir(parents=True)
        (path / 'file.txt').write_text('synthetic', encoding='utf-8')
    keep = tmp_path / 'keep.txt'; keep.write_text('keep', encoding='utf-8')
    install_state.cleanup_debris(tmp_path)
    assert not (tmp_path / 'staging').exists()
    assert not (tmp_path / 'quarantine').exists()
    assert keep.read_text(encoding='utf-8') == 'keep'


def test_cleanup_debris_refuses_link_before_removing_anything(tmp_path, monkeypatch):
    from pathlib import Path
    staging = tmp_path / 'staging'; staging.mkdir()
    quarantine = tmp_path / 'quarantine'; quarantine.mkdir()
    linked = quarantine / 'linked'; linked.mkdir()
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == linked or original(p))
    with pytest.raises(install_state.InstallStateError):
        install_state.cleanup_debris(tmp_path)
    assert staging.exists() and quarantine.exists()
