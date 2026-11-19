"""Private Windows storage for sealed trial snapshots.

The digest must be retained in an independently trusted approval record. This
module does not record or establish the owner's approval, or detect cloud sync.
"""
from contextlib import ExitStack, contextmanager
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from tools.field_trial_freeze import _MAX_SEALED_BYTES, seal, unseal
from tools.field_trial_local_files import open_local_file


@contextmanager
def _private_directory(root):
    stack = ExitStack()
    try:
        if os.name != 'nt':
            raise ValueError('unsupported platform')
        import ctypes
        from ctypes import wintypes
        from alfa_document_intelligence.__main__ import _lock_plain_windows_directory

        root = Path(root)
        if not root.is_absolute() or '..' in root.parts:
            raise ValueError('invalid directory')
        name = os.path.abspath(root)
        if name.startswith(('\\\\', '//')) or ':' in name[2:]:
            raise ValueError('nonlocal directory')
        get_drive_type = ctypes.WinDLL('kernel32', use_last_error=True).GetDriveTypeW
        get_drive_type.argtypes = [wintypes.LPCWSTR]
        get_drive_type.restype = wintypes.UINT
        if get_drive_type(os.path.splitdrive(name)[0] + '\\') != 3:
            raise ValueError('nonlocal drive')
        root = Path(name)
        directories = (root, *root.parents)
        for directory in reversed(directories):
            stack.enter_context(_lock_plain_windows_directory(str(directory)))
        if any((directory / '.git').exists() for directory in directories):
            raise ValueError('repository directory')
    except Exception:
        stack.close()
        raise ValueError('private storage unavailable') from None
    with stack:
        yield root


def save_snapshot(private_root, snapshot, *, protector=None):
    """Store ciphertext exclusively; return its path and private digest."""
    blob = seal(snapshot, protector=protector)
    try:
        with _private_directory(private_root) as root:
            path = root / ('m8-' + secrets.token_hex(16) + '.bin')
            with open(path, 'xb') as stream:
                if stream.write(blob) != len(blob):
                    raise OSError('short write')
                stream.flush()
                os.fsync(stream.fileno())
            return path, hashlib.sha256(blob).digest()
    except Exception:
        raise ValueError('private storage unavailable') from None


def load_snapshot(private_root, path, approved_digest, *, protector=None):
    """Load only the exact ciphertext bound to a trusted approval record."""
    if not isinstance(approved_digest, bytes) or len(approved_digest) != 32:
        raise ValueError('invalid approval reference')
    try:
        with _private_directory(private_root) as root:
            with open_local_file(root, path) as stream:
                blob = stream.read(_MAX_SEALED_BYTES + 1)
            if len(blob) > _MAX_SEALED_BYTES or not hmac.compare_digest(
                hashlib.sha256(blob).digest(), approved_digest
            ):
                raise ValueError('snapshot mismatch')
            return unseal(blob, protector=protector)
    except Exception:
        raise ValueError('private snapshot unavailable') from None
