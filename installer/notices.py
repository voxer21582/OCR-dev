"""``THIRD_PARTY_NOTICES.txt`` from the built payload (M6 Task 7, REQ-107)."""
from __future__ import annotations

from pathlib import Path

import _distinfo

_RULE = "=" * 78


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def build_notices(payload_root: Path, overrides: dict | None = None) -> str:
    """Return the notices text; raise ``LicenceTextMissingError`` listing every package without a licence file."""
    payload_root = Path(payload_root)
    infos = _distinfo.read_all(payload_root, overrides)
    missing = [info.label for info in infos if not info.licence_files]
    python_licence = payload_root / "python" / "LICENSE.txt"
    if not python_licence.is_file():
        missing.append("cpython (python/LICENSE.txt)")
    rapidocr = [i for i in infos if _distinfo.normalise(i.name) == "rapidocr"]
    if rapidocr and not any(f.name == "MODEL_LICENSES.md" for f in rapidocr[0].licence_files):
        missing.append("rapidocr (MODEL_LICENSES.md)")
    if missing:
        raise _distinfo.LicenceTextMissingError(missing)
    parts = ["OCR2 - THIRD PARTY NOTICES", "", f"Components: {len(infos)} Python packages and CPython.", ""]
    parts += [_RULE, "CPython (python/LICENSE.txt)", _RULE, "", _text(python_licence), ""]
    for info in infos:
        parts += [_RULE, f"{info.name} {info.version} - declared licence: {info.licence}", _RULE, ""]
        for file in info.licence_files:
            parts += [f"--- {info.display(file)} ---", "", _text(file), ""]
    return "\n".join(parts) + "\n"


def write_notices(text: str, path: Path) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")
