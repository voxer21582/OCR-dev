"""Check removal trees without loading application code or reading file contents."""
from pathlib import Path
import argparse
import os
import shutil
import sys


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Do not echo untrusted arguments or the program path to stderr.
        self.exit(2, 'OCR2_REMOVE_ARGUMENT_ERROR\n')


def _linked(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except FileNotFoundError:
        return False


def _validate_roots(base: Path, roots: list[Path]) -> None:
    if _linked(base):
        raise ValueError("Linked installation directory is not allowed")
    def fail(error):
        raise error
    for root in roots:
        if _linked(root):
            raise ValueError("Linked removal directory is not allowed")
        if not root.exists():
            continue
        if not root.is_dir():
            raise ValueError("Invalid removal directory")
        for current, dirs, files in os.walk(root, followlinks=False, onerror=fail):
            for name in dirs + files:
                if _linked(Path(current) / name):
                    raise ValueError("Linked removal entry is not allowed")


def validate_removal(base: Path, data: Path | None) -> None:
    base = Path(base)
    roots = [base / "versions"]
    if data is not None:
        roots.append(Path(data))
    _validate_roots(base, roots)


def cleanup_debris(base: Path) -> None:
    base = Path(base)
    roots = [base / "staging", base / "quarantine"]
    _validate_roots(base, roots)
    for root in roots:
        if root.exists():
            shutil.rmtree(root)


def main(argv=None) -> int:
    parser = _SafeArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--cleanup-debris", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.cleanup_debris:
            if args.data is not None:
                raise ValueError("Data cannot be selected for debris cleanup")
            cleanup_debris(args.base)
        else:
            validate_removal(args.base, args.data)
    except (ValueError, OSError):
        print("OCR2_REMOVE_ERROR", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
