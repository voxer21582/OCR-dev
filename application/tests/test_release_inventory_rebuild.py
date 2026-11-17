import importlib.util
import json
from pathlib import Path

import pytest


def _load(name):
    path = Path(__file__).resolve().parents[2] / 'installer' / (name + '.py')
    spec = importlib.util.spec_from_file_location('release_test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rebuild_gate_detects_changed_inventory_and_notices(tmp_path, monkeypatch):
    checker, sbom, notices = (_load(n) for n in ('verify_release_inventory', 'sbom', 'notices'))
    monkeypatch.setattr(sbom, 'MODELS', {})
    dist = tmp_path / 'python/Lib/site-packages/sample-1.0.dist-info'
    (dist / 'licenses').mkdir(parents=True)
    (dist / 'METADATA').write_text('Name: sample\nVersion: 1.0\nLicense-File: LICENSE\n', encoding='utf-8')
    (dist / 'licenses/LICENSE').write_text('Synthetic license', encoding='utf-8')
    (tmp_path / 'python/LICENSE.txt').write_text('Synthetic Python license', encoding='utf-8')
    (tmp_path / 'runtime-manifest.json').write_text('{"version":"0.6.0"}', encoding='utf-8')
    lock = tmp_path / 'lock'
    lock.write_text('sample==1.0 --hash=sha256:' + 'a'*64 + '\n', encoding='utf-8')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'sha256': sbom.PYTHON_BUILD_SHA256}, 'nsis': {'version': '3.13', 'sha256': 'c'*64}}), encoding='utf-8')
    expected = sbom.build_sbom(tmp_path, lock, pins)
    (tmp_path / 'sbom.json').write_text(json.dumps(expected), encoding='utf-8')
    (tmp_path / 'THIRD_PARTY_NOTICES.txt').write_text(notices.build_notices(tmp_path), encoding='utf-8')
    checker.verify_rebuilt_inventory(tmp_path, lock, pins, sbom, notices)
    expected['components'] = expected['components'][1:]
    (tmp_path / 'sbom.json').write_text(json.dumps(expected), encoding='utf-8')
    with pytest.raises(ValueError, match='inventory'):
        checker.verify_rebuilt_inventory(tmp_path, lock, pins, sbom, notices)
    (tmp_path / 'sbom.json').write_text(json.dumps(sbom.build_sbom(tmp_path, lock, pins)), encoding='utf-8')
    (tmp_path / 'THIRD_PARTY_NOTICES.txt').write_text('truncated but nonempty', encoding='utf-8')
    with pytest.raises(ValueError, match='notices'):
        checker.verify_rebuilt_inventory(tmp_path, lock, pins, sbom, notices)
