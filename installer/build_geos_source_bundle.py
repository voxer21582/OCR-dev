"""Build a reproducible offline evidence bundle from previously acquired files."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import zipfile


EXPECTED_SHA256 = {
    'geos-3.14.1.tar.bz2': '3c20919cda9a505db07b5216baa980bacdaa0702da715b43f176fb07eff7e716',
    'install_geos.cmd': '540ece44323dfdff7cabd8cee8c4206fd086cfeeda9d9672845c6be251f2b89e',
    'release.yml': '2f6c2cfe1954b6b969519badd332f64b17f089d8dbd18475089bf6f1bdd7578f',
    'SHAPELY-LICENSE.txt': 'e8cd7d34604d2758ff589f0f34d6ed79c3f7fb14aaf5e12fb09221421391a3bf',
}

README = '''OCR2 - GEOS source evidence bundle\n\nThis bundle contains the published GEOS 3.14.1 source archive and the\nShapely 2.2.0 build script and workflow from commit\n229c71f7128713b37201f3c77336d32b52467454.\n\nThe precise source used to build the installed GEOS binary has not been verified.\nThis bundle alone does not establish compliance with distribution obligations.\nThe build script is informational and was not run; it downloads files and requires\nbuild tools. Sources: https://libgeos.org/usage/download/ and\nhttps://github.com/shapely/shapely/tree/229c71f7128713b37201f3c77336d32b52467454\n'''


def build_bundle(files: dict[str, Path], output: Path) -> None:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if set(files) != set(EXPECTED_SHA256):
        raise ValueError('Missing or unexpected source input')
    contents = {}
    for name, expected in EXPECTED_SHA256.items():
        path = Path(files[name])
        st = path.lstat()
        if path.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400 or not path.is_file():
            raise ValueError(f'Unsafe source input: {name}')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Source digest mismatch: {name}')
        contents[name] = data
    fd, temporary = tempfile.mkstemp(prefix='.geos-bundle-', dir=output.parent)
    try:
        with os.fdopen(fd, 'w+b') as stream:
            with zipfile.ZipFile(stream, 'w') as archive:
                for name, data in [('README.txt', README.encode('utf-8')), *sorted(contents.items())]:
                    entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = 0o100644 << 16
                    archive.writestr(entry, data, compresslevel=9)
        # Linking in the same directory publishes only a complete file and never
        # overwrites an output another process created after the initial check.
        os.link(temporary, output)
    finally:
        os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--install-script', type=Path, required=True)
    parser.add_argument('--workflow', type=Path, required=True)
    parser.add_argument('--shapely-license', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build_bundle({'geos-3.14.1.tar.bz2': args.source, 'install_geos.cmd': args.install_script,
                  'release.yml': args.workflow, 'SHAPELY-LICENSE.txt': args.shapely_license}, args.output)


if __name__ == '__main__':
    main()
