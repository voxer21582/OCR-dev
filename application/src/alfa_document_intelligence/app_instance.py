"""Single running instance per user (REQ-100).

The first ``--app-window`` launcher takes an exclusive lock on
``<data dir>/instance.lock`` and publishes its loopback port and a random
instance id in ``<data dir>/instance.json``.  A later launcher finds that
instance with ``running_instance``: the file alone is never trusted, the server
on the port must answer ``/app/info`` with the same id
(``<meta name="ocr2-instance">``).  The lock is held by an open file handle, so
the operating system releases it when the process ends, even after a crash; a
stale ``instance.json`` then fails the confirmation and is overwritten.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import BinaryIO
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

LOCK_NAME = "instance.lock"
INSTANCE_NAME = "instance.json"
_MAX_INSTANCE_FILE_BYTES = 4096
_MAX_INFO_BYTES = 64 * 1024
_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_SECONDS = 0.05
_INSTANCE_META = re.compile(rb'<meta name="ocr2-instance" content="([A-Za-z0-9_-]{1,128})">')

if os.name == "nt":  # pragma: no cover - exercised on Windows
    import msvcrt

    def _lock(handle: BinaryIO) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle: BinaryIO) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:  # pragma: no cover - exercised on Linux CI
    import fcntl

    def _lock(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class InstanceLock:
    """The held instance lock; ``release`` removes the published file and unlocks."""

    def __init__(self, data_dir: Path, handle: BinaryIO) -> None:
        self._data_dir = data_dir
        self._handle: BinaryIO | None = handle

    def publish(self, port: int, instance_id: str) -> None:
        if self._handle is None:
            raise RuntimeError("instance lock already released")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not isinstance(instance_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", instance_id) is None:
            raise ValueError("invalid instance id")
        target = self._data_dir / INSTANCE_NAME
        temporary = self._data_dir / (INSTANCE_NAME + ".tmp")
        temporary.write_text(json.dumps({"port": port, "instance_id": instance_id}), encoding="utf-8")
        # A concurrent reader can briefly block the replace on Windows.
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, target)
                return
            except PermissionError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_REPLACE_RETRY_SECONDS)

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            (self._data_dir / INSTANCE_NAME).unlink(missing_ok=True)
        finally:
            try:
                _unlock(handle)
            except OSError:
                pass
            handle.close()


def acquire(data_dir: Path) -> InstanceLock | None:
    """Take the exclusive instance lock; ``None`` when another process holds it."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    handle = open(data_dir / LOCK_NAME, "a+b")
    try:
        _lock(handle)
    except OSError:
        handle.close()
        return None
    return InstanceLock(data_dir, handle)


def _published(data_dir: Path) -> tuple[int, str] | None:
    try:
        raw = (Path(data_dir) / INSTANCE_NAME).read_bytes()
    except OSError:
        return None
    if len(raw) > _MAX_INSTANCE_FILE_BYTES:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    port, instance_id = data.get("port"), data.get("instance_id")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return None
    if not isinstance(instance_id, str) or not instance_id:
        return None
    return port, instance_id


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def running_instance(data_dir: Path, timeout: float = 2.0) -> int | None:
    """Port of the live OCR2 server published in ``data_dir``, confirmed by its instance id."""
    published = _published(data_dir)
    if published is None:
        return None
    port, instance_id = published
    # Never through a proxy (the server listens on loopback only) and never
    # follow a redirect: only the published port itself can confirm the id.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(f"http://127.0.0.1:{port}/app/info", timeout=timeout) as response:
            if response.status != 200:
                return None
            body = response.read(_MAX_INFO_BYTES)
    except (OSError, ValueError):
        return None
    match = _INSTANCE_META.search(body)
    if match is None:
        return None
    if not secrets.compare_digest(match.group(1), instance_id.encode("utf-8", "replace")):
        return None
    return port
