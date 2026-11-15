from __future__ import annotations

import pytest

from tools.validate_hashed_lock import parse_lock


HASH_A = "a" * 64
HASH_B = "b" * 64


def test_parse_lock_accepts_exact_pin_with_sha256():
    assert parse_lock(f"paddlepaddle==3.2.0 --hash=sha256:{HASH_A}\n") == {
        "paddlepaddle": ("3.2.0", HASH_A)
    }


@pytest.mark.parametrize("text", [
    "",
    "paddlepaddle>=3.2 --hash=sha256:" + HASH_A,
    "paddlepaddle==3.2.0",
    "paddlepaddle==3.2.0 --hash=sha256:abcd",
    "paddlepaddle==3.2.0 --hash=sha256:" + HASH_A + " extra",
])
def test_parse_lock_rejects_unpinned_or_malformed_lines(text):
    with pytest.raises(ValueError):
        parse_lock(text)


def test_parse_lock_rejects_normalized_duplicate_names():
    with pytest.raises(ValueError, match="duplicate"):
        parse_lock(
            f"paddle_paddle==3.2.0 --hash=sha256:{HASH_A}\n"
            f"paddle-paddle==3.2.1 --hash=sha256:{HASH_B}\n"
        )


def _repository_lock(name):
    from pathlib import Path

    return parse_lock((Path(__file__).resolve().parents[2] / "requirements" / name).read_text(encoding="utf-8"))


def _runtime_lock_entries():
    # The runtime lock uses multi-line entries; join continuation lines first.
    from pathlib import Path
    import re

    text = (Path(__file__).resolve().parents[2] / "requirements" / "ocr2-runtime-cp313-win-amd64.lock").read_text(encoding="utf-8")
    joined = "\n".join(
        line for line in re.sub(r"\s*\\\n\s*", " ", text).splitlines() if not line.startswith("--")
    )
    return parse_lock(joined)


def test_windows_ci_lock_matches_the_approved_versions():
    windows = _repository_lock("ci-tests-cp313-win-amd64.lock")
    ubuntu = {}
    for name in ("ci-taxonomy-cp313-ubuntu-24_04.lock", "ci-pytest-cp313-ubuntu-24_04.lock", "ci-decoder-cp313-ubuntu-24_04.lock"):
        ubuntu.update(_repository_lock(name))
    runtime = _runtime_lock_entries()
    assert set(windows) == set(ubuntu) | {"colorama"}
    for package, (version, _digest) in ubuntu.items():
        assert windows[package][0] == version
    for package in ("pillow", "pypdfium2", "colorama"):
        assert windows[package] == runtime[package]
    pure_python = ("attrs", "jsonschema", "jsonschema-specifications", "referencing",
                   "iniconfig", "packaging", "pluggy", "pygments", "pytest")
    for package in pure_python:
        assert windows[package] == ubuntu[package]
