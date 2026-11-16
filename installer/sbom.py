"""Produce a deterministic CycloneDX inventory from the runtime lock."""
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re

MODELS = {
    'PP-OCRv6_det_small.onnx': '090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f',
    'PP-OCRv6_rec_small.onnx': '6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884',
}


def _normal(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def build_sbom(payload_root: Path, lock: Path, pins: Path) -> dict:
    text = lock.read_text(encoding='utf-8').replace('\\\n', ' ')
    locked = {}
    for line in text.splitlines():
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s]+)\s+--hash=sha256:([0-9a-f]{64})\s*$', line.strip())
        if match:
            name, version, digest = match.groups()
            key = _normal(name)
            if key in locked:
                raise ValueError(f'duplicate package: {name}')
            locked[key] = (version, digest)
        elif line.strip() and not line.lstrip().startswith(('#', '--only-binary')):
            raise ValueError(f'Unsupported lock line: {line}')
    installed = {}
    for dist in (payload_root / 'python/Lib/site-packages').glob('*.dist-info'):
        meta = Parser().parsestr((dist / 'METADATA').read_text(encoding='utf-8'))
        key = _normal(meta['Name'])
        if key in installed:
            raise ValueError(f'duplicate installed package: {key}')
        installed[key] = meta
    if set(locked) != set(installed):
        raise ValueError('Installed packages do not match runtime lock')
    components = []
    for name in sorted(locked):
        version, digest = locked[name]
        meta = installed[name]
        if meta['Version'] != version:
            raise ValueError(f'{name}: version mismatch')
        item = {'type': 'library', 'name': name, 'version': version,
                'purl': f'pkg:pypi/{name}@{version}',
                'hashes': [{'alg': 'SHA-256', 'content': digest}]}
        licence = meta.get('License-Expression') or meta.get('License')
        if licence and len(licence) < 200:
            item['licenses'] = [{'license': {'name': licence}}]
        components.append(item)
    pin_data = json.loads(pins.read_text(encoding='utf-8'))
    pin = pin_data['python']
    components.append({'type': 'application', 'name': 'CPython', 'version': '3.13.18',
                       'hashes': [{'alg': 'SHA-256', 'content': pin['sha256']}]})
    for name, expected in sorted(MODELS.items()):
        path = payload_root / 'python/Lib/site-packages/rapidocr/models' / name
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected:
            raise ValueError(f'{name}: model hash mismatch')
        components.append({'type': 'file', 'name': name,
                           'hashes': [{'alg': 'SHA-256', 'content': digest}]})
    release_version = json.loads((payload_root / 'runtime-manifest.json').read_text(encoding='utf-8'))['version']
    components.append({'type': 'application', 'name': 'OCR2', 'version': release_version})
    nsis = pin_data['nsis']
    components.append({'type': 'application', 'name': 'NSIS', 'version': nsis['version'], 'scope': 'excluded',
                       'hashes': [{'alg': 'SHA-256', 'content': nsis['sha256']}]})
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1, 'components': components}
