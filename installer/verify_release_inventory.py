"""Compare release inventory and notices with freshly regenerated output."""
import json
from pathlib import Path
import sys


def verify_rebuilt_inventory(root, lock, pins, sbom_module, notices_module):
    root = Path(root)
    try:
        actual_sbom = json.loads((root / 'sbom.json').read_text(encoding='utf-8'))
        actual_notices = (root / 'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')
        expected_sbom = sbom_module.build_sbom(root, Path(lock), Path(pins))
        expected_notices = notices_module.build_notices(root)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('Unable to regenerate release inventory and notices') from exc
    if actual_sbom != expected_sbom:
        raise ValueError('Release inventory differs from regenerated inventory')
    if actual_notices != expected_notices:
        raise ValueError('Release notices differ from regenerated notices')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Expected payload directory')
    import sbom
    import notices
    repository = Path(__file__).resolve().parents[1]
    try:
        verify_rebuilt_inventory(Path(sys.argv[1]), repository / 'requirements/ocr2-runtime-cp313-win-amd64.lock',
                                 repository / 'installer/pins.json', sbom, notices)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print('Release inventory and notices match regenerated output')
