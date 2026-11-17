"""Produce a deterministic CycloneDX inventory from the runtime lock."""
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re

PYTHON_BUILD_SHA256 = 'a2aa39db83d68ec06f4f98908a55682685fa4696696549188b2dd333bfd03041'
NATIVE_COMPONENTS = (('OpenSSL', '3.5.9'), ('Expat', '2.9.0'), ('mpdecimal', '4.0.0'),
                     ('zlib', '1.3.1'), ('libffi', '3.4.4'), ('bzip2', '1.0.8'),
                     ('liblzma', '5.2.5'), ('SQLite', '3.50.4'))

PILLOW_WHEEL_SHA256 = '9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42'
PILLOW_NATIVE_COMPONENTS = (('FreeType', '2.14.3'), ('libwebp', '1.6.0'),
                            ('libavif', '1.4.2'), ('libjpeg-turbo', '3.2.0'),
                            ('OpenJPEG', '2.5.4'), ('zlib-ng', '2.3.3'),
                            ('LibTIFF', '4.7.2'))

# Values observed in the pinned Windows wheels' runtime/build metadata.
WHEEL_NATIVE_COMPONENTS = {
    'numpy': ('2.5.4', '8b4d2fd2d34e5f8c9235ee787de5631a37a28402b15cb80814df973d2be54129', (('OpenBLAS', '0.3.34.106.0'),)),
    'shapely': ('2.2.0', '1eaa2cb64cdedaf65d6bc86f2819c9cd7d6d68f969aa3ebfdc93743ab581f437', (('GEOS', '3.14.1'),)),
    'pypdfium2': ('5.15.2', '74d1bace34fb01c660d0b64344d5a4b7d276942b7c6623c88ab59ea21c5acfbd', (('PDFium', '159.0.8149.0'),)),
    'pyclipper': ('1.4.0', 'd4b2d7c41086f1927d14947c563dfc7beed2f6c0d9af13c42fe3dcdc20d35832', (('Clipper', '6.4.2'),)),
    'pyyaml': ('6.0.3', '79005a0d97d5ddabfeeea4cf676af11e647e41d81c9a7722a193022accdb6b7c', (('libyaml', '0.2.5'),)),
    'opencv-python-headless': ('5.0.0.93', '829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e',
                               (('libprotobuf', '3.19.1'), ('flatbuffers', '25.9.23'),
                                ('zlib', '1.3.2'), ('libjpeg-turbo', '3.1.2-70'),
                                ('libpng', '1.6.57'), ('LibTIFF', '4.7.1'),
                                ('OpenJPEG', '2.5.3'), ('Intel IPP', '2026.0.0'),
                                ('Intel ITT', '3.25.4'))),
}

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
    if 'pillow' in locked:
        if locked['pillow'] != ('13.0.0', PILLOW_WHEEL_SHA256):
            raise ValueError('Pillow wheel has no verified native inventory')
        components.extend({'type': 'library', 'name': name, 'version': version,
                           'properties': [{'name': 'ocr2:inventory-source',
                                           'value': 'Pillow wheel runtime features and bundled license'}]}
                          for name, version in PILLOW_NATIVE_COMPONENTS)
        components.append({'type': 'library', 'name': 'LittleCMS',
                           'properties': [{'name': 'ocr2:inventory-source',
                                           'value': 'Pillow wheel runtime features and bundled license'},
                                          {'name': 'ocr2:reported-version',
                                           'value': '2.19 (patch unknown)'}]})
    for package, (version, digest, native) in WHEEL_NATIVE_COMPONENTS.items():
        if package not in locked:
            continue
        if locked[package] != (version, digest):
            raise ValueError(f'{package}: wheel has no verified native inventory')
        components.extend({'type': 'library', 'name': name, 'version': native_version,
                           'properties': [{'name': 'ocr2:inventory-source',
                                           'value': f'{package} pinned Windows wheel runtime/build metadata'}]}
                          for name, native_version in native)
    pin_data = json.loads(pins.read_text(encoding='utf-8'))
    pin = pin_data['python']
    if pin['sha256'] != PYTHON_BUILD_SHA256:
        raise ValueError('Python build has no verified native inventory')
    components.extend({'type': 'library', 'name': name, 'version': version,
                       'properties': [{'name': 'ocr2:inventory-source',
                                       'value': 'CPython local build dependency records'}]}
                      for name, version in NATIVE_COMPONENTS)
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
