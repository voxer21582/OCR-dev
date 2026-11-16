import json

import pytest

from alfa_document_intelligence import install_state
from alfa_document_intelligence.runtime_manifest import build_manifest


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
