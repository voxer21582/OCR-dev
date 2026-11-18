import json

import pytest

from alfa_document_intelligence import install_state
from alfa_document_intelligence.runtime_manifest import build_manifest


def test_installer_error_does_not_print_exception_details(tmp_path, monkeypatch, capsys):
    def fail(*args):
        raise OSError('SYNTHETIC_PRIVATE_PATH_841')
    monkeypatch.setattr(install_state, 'rollback', fail)
    assert install_state.main(['--base', str(tmp_path), 'rollback']) == 1
    err = capsys.readouterr().err
    assert 'SYNTHETIC_PRIVATE_PATH_841' not in err
    assert 'OCR2_INSTALL_ERROR' in err


def test_removal_error_does_not_print_exception_details(tmp_path, monkeypatch, capsys):
    from alfa_document_intelligence import removal_check
    def fail(*args):
        raise OSError('SYNTHETIC_PRIVATE_PATH_842')
    monkeypatch.setattr(removal_check, 'validate_removal', fail)
    assert removal_check.main(['--base', str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert 'SYNTHETIC_PRIVATE_PATH_842' not in err
    assert 'OCR2_REMOVE_ERROR' in err


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


def test_rejects_non_symlink_reparse_install_root(tmp_path, monkeypatch):
    import stat
    from pathlib import Path
    from types import SimpleNamespace
    _version(tmp_path, '0.6.0')
    original = Path.lstat
    def fake_lstat(path):
        if path == tmp_path:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original(path)
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    with pytest.raises(install_state.InstallStateError, match='Linked'):
        install_state.activate(tmp_path, '0.6.0')


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
    import os
    _version(tmp_path, '0.6.0')
    monkeypatch.setenv('OCR2_INSTALL_LOCK_HELD', '1')
    if os.name == 'nt':
        monkeypatch.setenv('OCR2_INSTALL_PARENT_PID', str(os.getpid()))
        monkeypatch.setenv('OCR2_INSTALL_PARENT_START', str(install_state._process_start(os.getpid())))
    with install_state._transaction(tmp_path):
        with pytest.raises(install_state.InstallStateError, match='in use'):
            install_state.activate(tmp_path, '0.6.0')


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows process identity')
def test_orphan_child_must_not_mutate_state(tmp_path, monkeypatch):
    _version(tmp_path, '0.6.0')
    monkeypatch.setenv('OCR2_INSTALL_LOCK_HELD', '1')
    monkeypatch.setenv('OCR2_INSTALL_PARENT_PID', '99999999')
    monkeypatch.setenv('OCR2_INSTALL_PARENT_START', '1')
    with pytest.raises(install_state.InstallStateError, match='parent'):
        install_state.activate(tmp_path, '0.6.0')
    assert not (tmp_path / 'active.json').exists()


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows process identity')
def test_child_transaction_blocks_launcher_if_parent_lock_is_lost(tmp_path, monkeypatch):
    import os
    from alfa_document_intelligence import app_instance
    base = tmp_path / 'Programs' / 'OCR2'; base.mkdir(parents=True)
    monkeypatch.setenv('OCR2_INSTALL_LOCK_HELD', '1')
    monkeypatch.setenv('OCR2_INSTALL_PARENT_PID', str(os.getpid()))
    monkeypatch.setenv('OCR2_INSTALL_PARENT_START', str(install_state._process_start(os.getpid())))
    with install_state._transaction(base):
        assert app_instance.acquire(tmp_path / 'OCR2') is None


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows process identity')
def test_child_started_by_dead_installer_does_not_mutate(tmp_path):
    import os
    import subprocess
    import sys
    import time
    _version(tmp_path, '0.6.0')
    child = tmp_path / 'child.py'
    child.write_text('''import sys,time\nfrom pathlib import Path\nfrom alfa_document_intelligence import install_state\nb=Path(sys.argv[1])\nwhile not (b/'go').exists(): time.sleep(.02)\ntry: install_state.activate(b,'0.6.0')\nexcept install_state.InstallStateError: (b/'result').write_text('refused')\nelse: (b/'result').write_text('activated')\n''', encoding='utf-8')
    parent = tmp_path / 'parent.py'
    parent.write_text('''import os,subprocess,sys\nfrom alfa_document_intelligence.install_state import _process_start\nenv=os.environ.copy();env['OCR2_INSTALL_LOCK_HELD']='1';env['OCR2_INSTALL_PARENT_PID']=str(os.getpid());env['OCR2_INSTALL_PARENT_START']=str(_process_start(os.getpid()))\nsubprocess.Popen([sys.executable,'-B',sys.argv[1],sys.argv[2]],env=env,creationflags=subprocess.CREATE_NO_WINDOW)\n''', encoding='utf-8')
    subprocess.run([sys.executable, '-B', str(parent), str(child), str(tmp_path)], check=True, timeout=10)
    (tmp_path / 'go').write_text('go', encoding='utf-8')
    deadline = time.monotonic() + 10
    while not (tmp_path / 'result').exists() and time.monotonic() < deadline:
        time.sleep(.02)
    assert (tmp_path / 'result').read_text() == 'refused'
    assert not (tmp_path / 'active.json').exists()


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


def test_uninstall_preflight_rejects_links_before_removing_anything(tmp_path, monkeypatch):
    from pathlib import Path
    versions = tmp_path / 'base/versions/0.6.0'; versions.mkdir(parents=True)
    data = tmp_path / 'data'; data.mkdir()
    linked = data / 'linked'; linked.mkdir()
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == linked or original(p))
    with pytest.raises(install_state.InstallStateError, match='Linked'):
        install_state.check_removal(tmp_path / 'base', data)
    assert versions.exists() and data.exists()
    install_state.check_removal(tmp_path / 'base', None)


def test_uninstall_preflight_rejects_nested_version_link(tmp_path, monkeypatch):
    from pathlib import Path
    nested = tmp_path / 'base/versions/0.6.0/nested'; nested.mkdir(parents=True)
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == nested or original(p))
    with pytest.raises(install_state.InstallStateError, match='Linked'):
        install_state.check_removal(tmp_path / 'base', None)


def test_standalone_removal_preflight_works_without_installed_package(tmp_path):
    import subprocess, sys
    from pathlib import Path
    script = Path(install_state.__file__).with_name('removal_check.py')
    base = tmp_path / 'base'; base.mkdir()
    valid = subprocess.run([sys.executable, '-I', '-B', str(script), '--base', str(base)], capture_output=True)
    assert valid.returncode == 0
    (base / 'versions').write_text('not a directory', encoding='utf-8')
    result = subprocess.run([sys.executable, '-I', '-B', str(script), '--base', str(base)], capture_output=True)
    assert result.returncode != 0
    assert (base / 'versions').is_file()


def test_standalone_cleanup_works_without_installed_package(tmp_path):
    import subprocess, sys
    from pathlib import Path
    script = Path(install_state.__file__).with_name('removal_check.py')
    base = tmp_path / 'base'; (base / 'staging/synthetic').mkdir(parents=True)
    (base / 'staging/synthetic/file.txt').write_text('synthetic', encoding='utf-8')
    (base / 'quarantine').mkdir()
    result = subprocess.run([sys.executable, '-I', '-B', str(script), '--base', str(base), '--cleanup-debris'], capture_output=True)
    assert result.returncode == 0
    assert not (base / 'staging').exists() and not (base / 'quarantine').exists()


def test_standalone_cleanup_checks_all_roots_before_deleting(tmp_path, monkeypatch):
    from alfa_document_intelligence import removal_check
    staging = tmp_path / 'staging'; staging.mkdir()
    linked = tmp_path / 'quarantine/linked'; linked.mkdir(parents=True)
    original = removal_check._linked
    monkeypatch.setattr(removal_check, '_linked', lambda path: path == linked or original(path))
    with pytest.raises(ValueError, match='Linked'):
        removal_check.cleanup_debris(tmp_path)
    assert staging.exists() and linked.exists()

@pytest.mark.parametrize('arguments', [
    ['SYNTHETIC_PRIVATE_ARGUMENT_843'],
    ['activate', '--SYNTHETIC_PRIVATE_ARGUMENT_843'],
    ['verify', '0.6.0', '--SYNTHETIC_PRIVATE_ARGUMENT_843'],
])
def test_invalid_install_arguments_do_not_echo_private_values(arguments, capsys):
    with pytest.raises(SystemExit) as exit_info:
        install_state.main(arguments)
    assert exit_info.value.code == 2
    output = capsys.readouterr()
    assert 'SYNTHETIC_PRIVATE_ARGUMENT_843' not in output.out + output.err
    assert 'OCR2_INSTALL_ARGUMENT_ERROR' in output.err


def test_install_cli_invalid_argument_is_sanitized_in_subprocess():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, '-B', '-m', 'alfa_document_intelligence.install_state',
         'SYNTHETIC_PRIVATE_ARGUMENT_843'],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert 'SYNTHETIC_PRIVATE_ARGUMENT_843' not in result.stdout + result.stderr
    assert result.stderr.strip() == 'OCR2_INSTALL_ARGUMENT_ERROR'


def test_removal_cli_invalid_argument_is_sanitized_in_subprocess(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, '-B', '-m', 'alfa_document_intelligence.removal_check',
         '--base', str(tmp_path), '--SYNTHETIC_PRIVATE_ARGUMENT_844'],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert 'SYNTHETIC_PRIVATE_ARGUMENT_844' not in result.stdout + result.stderr
    assert result.stderr.strip() == 'OCR2_REMOVE_ARGUMENT_ERROR'
