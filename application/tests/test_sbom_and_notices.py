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


def test_notices_include_package_level_third_party_notices(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    site = tmp_path / 'python/Lib/site-packages'
    (site / 'sample').mkdir()
    (site / 'sample/ThirdPartyNotices.txt').write_text('Synthetic third-party notice', encoding='utf-8')
    (site / 'sample-1.0.dist-info/RECORD').write_text('sample/ThirdPartyNotices.txt,,\n', encoding='utf-8')
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    assert 'Synthetic third-party notice' in notices.build_notices(tmp_path)


def test_notices_reject_record_paths_outside_site_packages(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    dist = tmp_path / 'python/Lib/site-packages/sample-1.0.dist-info'
    (dist / 'RECORD').write_text('../secret/LICENSE.txt,,\n', encoding='utf-8')
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    with pytest.raises(ValueError, match='unsafe'):
        notices.build_notices(tmp_path)


def test_rapidocr_model_licence_is_required_even_if_record_omits_it(tmp_path):
    notices = _load('notices')
    _dist(tmp_path, 'rapidocr')
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    with pytest.raises(ValueError, match='model'):
        notices.build_notices(tmp_path)
    model = tmp_path / 'python/Lib/site-packages/rapidocr-1.0.dist-info/licenses/MODEL_LICENSES.md'
    model.write_text('Synthetic model licence', encoding='utf-8')
    assert 'Synthetic model licence' in notices.build_notices(tmp_path)


def test_sbom_records_locked_package_and_is_deterministic(tmp_path, monkeypatch):
    sbom = _load('sbom')
    monkeypatch.setattr(sbom, 'MODELS', {}, raising=False)
    _dist(tmp_path)
    lock = tmp_path / 'lock'
    lock.write_text('sample==1.0 \\\n    --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': 'a2aa39db83d68ec06f4f98908a55682685fa4696696549188b2dd333bfd03041'}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
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
    pins = tmp_path / 'pins.json'; pins.write_text(json.dumps({'python': {'sha256': 'a2aa39db83d68ec06f4f98908a55682685fa4696696549188b2dd333bfd03041'}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    result = sbom.build_sbom(tmp_path, lock, pins)
    assert any(c['name'] == 'synthetic.onnx' for c in result['components'])
    (model_dir / 'synthetic.onnx').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='synthetic.onnx'):
        sbom.build_sbom(tmp_path, lock, pins)


def test_notices_include_bundled_python_openssl_license(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    result = notices.build_notices(tmp_path)
    assert 'OpenSSL 3.5.9 (bundled with CPython)' in result
    assert 'Apache License' in result


def test_notices_identify_python_native_components(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    result = notices.build_notices(tmp_path)
    assert 'mpdecimal 4.0.0 (bundled with CPython)' in result
    assert 'Copyright (c) 2008-2024 Stefan Krah' in result
    assert 'zlib 1.3.1 (bundled with CPython)' in result
    assert 'XZ Utils 5.2.5 (bundled with CPython)' in result


def test_notices_include_bundled_expat(tmp_path):
    notices = _load('notices')
    _dist(tmp_path)
    (tmp_path / 'python/LICENSE.txt').write_text('Python licence', encoding='utf-8')
    result = notices.build_notices(tmp_path)
    assert 'Expat 2.9.0 (bundled with CPython)' in result
    assert 'Copyright (c) 2001-2025 Expat maintainers' in result


def test_sbom_includes_native_dependencies_for_verified_python_build(tmp_path, monkeypatch):
    sbom = _load('sbom')
    monkeypatch.setattr(sbom, 'MODELS', {})
    _dist(tmp_path)
    lock = tmp_path / 'lock'
    lock.write_text('sample==1.0 --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': 'a2aa39db83d68ec06f4f98908a55682685fa4696696549188b2dd333bfd03041'}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    result = sbom.build_sbom(tmp_path, lock, pins)
    native = {(c['name'], c['version']) for c in result['components']}
    assert {('OpenSSL', '3.5.9'), ('Expat', '2.9.0'), ('mpdecimal', '4.0.0'), ('zlib', '1.3.1'), ('libffi', '3.4.4'), ('bzip2', '1.0.8'), ('liblzma', '5.2.5'), ('SQLite', '3.50.4')} <= native


def test_sbom_rejects_python_build_without_native_inventory(tmp_path, monkeypatch):
    sbom = _load('sbom')
    monkeypatch.setattr(sbom, 'MODELS', {})
    _dist(tmp_path)
    lock = tmp_path / 'lock'
    lock.write_text('sample==1.0 --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': 'b'*64}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    with pytest.raises(ValueError, match='native inventory'):
        sbom.build_sbom(tmp_path, lock, pins)


def test_sbom_includes_native_components_for_verified_pillow_wheel(tmp_path, monkeypatch):
    sbom = _load('sbom')
    monkeypatch.setattr(sbom, 'MODELS', {})
    _dist(tmp_path, 'pillow')
    metadata = tmp_path / 'python/Lib/site-packages/pillow-1.0.dist-info/METADATA'
    metadata.write_text('Name: pillow\nVersion: 13.0.0\n', encoding='utf-8')
    lock = tmp_path / 'lock'
    lock.write_text('pillow==13.0.0 --hash=sha256:9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': 'a2aa39db83d68ec06f4f98908a55682685fa4696696549188b2dd333bfd03041'}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    result = sbom.build_sbom(tmp_path, lock, pins)
    native = {(c['name'], c['version']) for c in result['components']}
    assert {('FreeType', '2.14.3'), ('libwebp', '1.6.0'), ('libavif', '1.4.2'), ('libjpeg-turbo', '3.2.0'), ('OpenJPEG', '2.5.4'), ('zlib-ng', '2.3.3'), ('LibTIFF', '4.7.2')} <= native
    lock.write_text('pillow==13.0.0 --hash=sha256:' + 'd'*64 + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Pillow.*native inventory'):
        sbom.build_sbom(tmp_path, lock, pins)
