"""Collect attribution texts from installed package metadata."""
from email.parser import Parser
import csv
from pathlib import Path, PurePosixPath


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='cp1252')


def build_notices(payload_root: Path) -> str:
    package_dir = payload_root / 'python' / 'Lib' / 'site-packages'
    blocks = []
    python_license = payload_root / 'python' / 'LICENSE.txt'
    if not python_license.is_file():
        raise ValueError('Missing Python licence')
    blocks.append('Python\n\n' + python_license.read_text(encoding='utf-8'))
    openssl_license = Path(__file__).parent / 'licenses' / 'openssl-3.5.9.txt'
    if not openssl_license.is_file():
        raise ValueError('Missing bundled OpenSSL licence')
    blocks.append('OpenSSL 3.5.9 (bundled with CPython)\n\n' + _text(openssl_license))
    for dist in sorted(package_dir.glob('*.dist-info')):
        metadata = Parser().parsestr((dist / 'METADATA').read_text(encoding='utf-8'))
        name, version = metadata['Name'], metadata['Version']
        paths = []
        for declared in metadata.get_all('License-File', []):
            candidate = dist / 'licenses' / declared
            if not candidate.is_file():
                candidate = dist / declared
            if not candidate.resolve().is_relative_to(dist.resolve()) or not candidate.is_file():
                raise ValueError(f'{name}: missing declared licence {declared}')
            paths.append(candidate)
        if not paths:
            paths = sorted(p for p in dist.rglob('*') if p.is_file() and p.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING')))
        record = dist / 'RECORD'
        if record.is_file():
            with record.open(encoding='utf-8', newline='') as stream:
                for row in csv.reader(stream):
                    if not row:
                        continue
                    raw = row[0]
                    name_part = PurePosixPath(raw).name.lower()
                    suffix = PurePosixPath(raw).suffix.lower()
                    if not any(word in name_part for word in ('license', 'licence', 'notice', 'copying')) or suffix not in ('', '.txt', '.md', '.rst', '.ijg'):
                        continue
                    parts = PurePosixPath(raw).parts
                    if not parts or raw.startswith('/') or '\\' in raw or ':' in raw or any(p in ('.', '..') for p in parts):
                        raise ValueError(f'{name}: unsafe licence path')
                    candidate = package_dir.joinpath(*parts)
                    if not candidate.resolve().is_relative_to(package_dir.resolve()) or not candidate.is_file():
                        raise ValueError(f'{name}: unsafe or missing licence path')
                    paths.append(candidate)
        if name.lower().replace('_', '-') == 'rapidocr':
            model_candidates = (dist / 'licenses' / 'MODEL_LICENSES.md', dist / 'MODEL_LICENSES.md',
                                package_dir / 'rapidocr' / 'MODEL_LICENSES.md')
            model = next((p for p in model_candidates if p.is_file() and p.resolve().is_relative_to(package_dir.resolve())), None)
            if model is None:
                raise ValueError('rapidocr: missing model licence text')
            paths.append(model)
        paths = sorted(set(paths))
        if not paths:
            fallback = Path(__file__).parent / 'licenses' / f'{name.lower()}-{version}.txt'
            if fallback.is_file():
                paths = [fallback]
        if not paths:
            raise ValueError(f'{name}: missing licence text')
        blocks.append(f'{name} {version}\n\n' + '\n\n'.join(_text(p) for p in paths))
    return '\n\n' + ('\n\n' + '=' * 72 + '\n\n').join(blocks) + '\n'
