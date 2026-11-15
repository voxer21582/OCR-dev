"""Open the OCR2 window: Microsoft Edge in app mode with a dedicated profile (REQ-100).

Edge always runs with ``--user-data-dir=<data dir>\\edge-profile``, so the
user's own Edge profile and settings are never touched.  Edge is looked up in
the Program Files folders and then, read-only, in the HKLM "App Paths" key; the
registry is never written (V4).  Without Edge the default browser opens the
same address.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import webbrowser

_APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
_LOCAL_URL = re.compile(r"http://127\.0\.0\.1:[0-9]{1,5}/")


def _winreg():
    try:
        import winreg
    except ImportError:
        return None
    return winreg


def _edge_from_app_paths() -> Path | None:
    registry = _winreg()
    if registry is None:
        return None
    try:
        with registry.OpenKey(registry.HKEY_LOCAL_MACHINE, _APP_PATHS_KEY, 0, registry.KEY_READ) as key:
            value = registry.QueryValue(key, None)
    except OSError:
        return None
    if not isinstance(value, str):
        return None
    candidate = Path(value.strip().strip('"'))
    if candidate.name.lower() != "msedge.exe" or not candidate.is_file():
        return None
    return candidate


def find_edge() -> Path | None:
    """Path of ``msedge.exe``, or ``None`` when Edge is not installed."""
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if not base:
            continue
        candidate = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if candidate.is_file():
            return candidate
    return _edge_from_app_paths()


def open_window(url: str, data_dir: Path) -> str:
    """Open ``url`` (the local server) in an Edge app window; ``"edge"`` or ``"browser"``."""
    if not isinstance(url, str) or _LOCAL_URL.fullmatch(url) is None:
        raise ValueError("only the local OCR2 server can be opened")
    edge = find_edge()
    if edge is not None:
        try:
            subprocess.Popen(
                [
                    str(edge),
                    f"--app={url}",
                    f"--user-data-dir={Path(data_dir) / 'edge-profile'}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return "edge"
        except OSError:
            pass
    webbrowser.open(url)
    return "browser"
