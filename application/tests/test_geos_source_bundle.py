import importlib.util
import hashlib
from pathlib import Path
import zipfile

import pytest


def _builder():
    path = Path(__file__).resolve().parents[2] / 'installer' / 'build_geos_source_bundle.py'
    spec = importlib.util.spec_from_file_location('geos_source_bundle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_bundle_is_offline_reproducible_and_checks_inputs(tmp_path, monkeypatch):
    builder = _builder()
    files = {}
    for name in ('geos-3.14.1.tar.bz2', 'install_geos.cmd', 'release.yml', 'SHAPELY-LICENSE.txt'):
        path = tmp_path / name
        path.write_bytes(('synthetic ' + name).encode())
        files[name] = path
    monkeypatch.setattr(builder, 'EXPECTED_SHA256', {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
    })
    a, b = tmp_path / 'a.zip', tmp_path / 'b.zip'
    builder.build_bundle(files, a)
    builder.build_bundle(files, b)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {*files, 'README.txt'}
        assert archive.read('geos-3.14.1.tar.bz2') == files['geos-3.14.1.tar.bz2'].read_bytes()
        assert b'not been verified' in archive.read('README.txt')
    files['install_geos.cmd'].write_text('altered')
    with pytest.raises(ValueError, match='digest'):
        builder.build_bundle(files, tmp_path / 'bad.zip')
    assert not (tmp_path / 'bad.zip').exists()
    with pytest.raises(FileExistsError):
        builder.build_bundle(files, a)


def test_source_bundle_does_not_leave_partial_output_on_write_failure(tmp_path, monkeypatch):
    builder = _builder()
    files = {}
    for name in builder.EXPECTED_SHA256:
        path = tmp_path / name
        path.write_bytes(b'synthetic')
        files[name] = path
    monkeypatch.setattr(builder, 'EXPECTED_SHA256', {name: hashlib.sha256(b'synthetic').hexdigest() for name in files})
    def fail(*args, **kwargs):
        raise OSError('synthetic failure')
    monkeypatch.setattr(builder.zipfile.ZipFile, 'writestr', fail)
    with pytest.raises(OSError, match='synthetic failure'):
        builder.build_bundle(files, tmp_path / 'bundle.zip')
    assert not (tmp_path / 'bundle.zip').exists()
    assert not list(tmp_path.glob('.geos-bundle-*'))


def test_source_bundle_preserves_output_created_concurrently(tmp_path, monkeypatch):
    builder = _builder()
    files = {}
    for name in builder.EXPECTED_SHA256:
        path = tmp_path / name
        path.write_bytes(b'synthetic')
        files[name] = path
    monkeypatch.setattr(builder, 'EXPECTED_SHA256', {name: hashlib.sha256(b'synthetic').hexdigest() for name in files})
    output = tmp_path / 'bundle.zip'
    def collision(source, target):
        output.write_bytes(b'existing')
        raise FileExistsError(target)
    monkeypatch.setattr(builder.os, 'link', collision)
    with pytest.raises(FileExistsError):
        builder.build_bundle(files, output)
    assert output.read_bytes() == b'existing'
    assert not list(tmp_path.glob('.geos-bundle-*'))
