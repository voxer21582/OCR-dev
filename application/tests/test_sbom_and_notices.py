import importlib.util
import json
from pathlib import Path

import pytest


def _load(name):
    path = Path(__file__).resolve().parents[2] / 'installer' / (name + '.py')
    spec = importlib.util.spec_from_file_location('m6_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dist(root, name='sample', license_text=True):
    d = root / 'python/Lib/site-packages' / (name + '-1.0.dist-info')
    d.mkdir(parents=True)
    (d / 'METADATA').write_text('Name: ' + name + '\nVersion: 1.0\nLicense-Expression: MIT\nLicense-File: LICENSE\n', encoding='utf-8')
    if license_text:
        (d / 'licenses').mkdir()
        (d / 'licenses/LICENSE').write_text('Synthetic licence text', encoding='utf-8')


def test_notices_include_licence_and_reject_missing(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    assert 'Synthetic licence text' in notices.build_notices(tmp_path)
    _dist(tmp_path, 'missing', False)
    with pytest.raises(ValueError, match='missing'):
        notices.build_notices(tmp_path)


def test_notices_accept_legacy_licence_location(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    d = tmp_path / 'python/Lib/site-packages/sample-1.0.dist-info'
    (d / 'licenses/LICENSE').rename(d / 'LICENSE')
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    assert 'Synthetic licence text' in notices.build_notices(tmp_path)


def test_notices_reads_windows_legacy_license_text(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    (tmp_path / 'python/Lib/site-packages/sample-1.0.dist-info/licenses/LICENSE').write_bytes(b'Copyright \xa9')
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    assert 'Copyright ©' in notices.build_notices(tmp_path)


def test_sbom_records_locked_package_and_is_deterministic(tmp_path, monkeypatch):
    sbom = _load('sbom')
    monkeypatch.setattr(sbom, 'MODELS', {}, raising=False)
    _dist(tmp_path)
    lock = tmp_path / 'lock'
    lock.write_text('sample==1.0 \\\n    --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': 'b'*64}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    first = sbom.build_sbom(tmp_path, lock, pins)
    assert first == sbom.build_sbom(tmp_path, lock, pins)
    component = next(c for c in first['components'] if c['name'] == 'sample')
    assert component['version'] == '1.0'
    assert component['hashes'][0]['content'] == 'a'*64
    assert component['purl'] == 'pkg:pypi/sample@1.0'
    assert next(c for c in first['components'] if c['name'] == 'OCR2')['version'] == '0.6.0'
    assert next(c for c in first['components'] if c['name'] == 'NSIS')['scope'] == 'excluded'


def test_sbom_lists_and_checks_ocr_models(tmp_path, monkeypatch):
    import hashlib
    sbom = _load('sbom')
    _dist(tmp_path)
    model_dir = tmp_path / 'python/Lib/site-packages/rapidocr/models'
    model_dir.mkdir(parents=True)
    (model_dir / 'synthetic.onnx').write_bytes(b'model')
    monkeypatch.setattr(sbom, 'MODELS', {'synthetic.onnx': hashlib.sha256(b'model').hexdigest()}, raising=False)
    lock = tmp_path / 'lock'; lock.write_text('sample==1.0 --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'; pins.write_text(json.dumps({'python': {'sha256': 'b'*64}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    result = sbom.build_sbom(tmp_path, lock, pins)
    assert any(c['name'] == 'synthetic.onnx' for c in result['components'])
    (model_dir / 'synthetic.onnx').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='synthetic.onnx'):
        sbom.build_sbom(tmp_path, lock, pins)
