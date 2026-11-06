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
