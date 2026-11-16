"""Collect attribution texts from installed package metadata."""
from email.parser import Parser
from pathlib import Path


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
        if not paths:
            fallback = Path(__file__).parent / 'licenses' / f'{name.lower()}-{version}.txt'
            if fallback.is_file():
                paths = [fallback]
        if not paths:
            raise ValueError(f'{name}: missing licence text')
        blocks.append(f'{name} {version}\n\n' + '\n\n'.join(_text(p) for p in paths))
    return '\n\n' + ('\n\n' + '=' * 72 + '\n\n').join(blocks) + '\n'
