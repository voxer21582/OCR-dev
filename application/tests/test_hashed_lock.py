from __future__ import annotations

import unittest

from tools.validate_hashed_lock import parse_lock


HASH_A = "a" * 64
HASH_B = "b" * 64


class ParseLockTests(unittest.TestCase):
    def test_accepts_exact_pin_with_sha256(self):
        self.assertEqual(
            parse_lock(f"paddlepaddle==3.2.0 --hash=sha256:{HASH_A}\n"),
            {"paddlepaddle": ("3.2.0", HASH_A)},
        )


    def test_rejects_unpinned_or_malformed_lines(self):
        invalid_locks = (
            "",
            "paddlepaddle>=3.2 --hash=sha256:" + HASH_A,
            "paddlepaddle==3.2.0",
            "paddlepaddle==3.2.0 --hash=sha256:abcd",
            "paddlepaddle==3.2.0 --hash=sha256:" + HASH_A + " extra",
        )
        for text in invalid_locks:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_lock(text)


    def test_rejects_normalized_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_lock(
                f"paddle_paddle==3.2.0 --hash=sha256:{HASH_A}\n"
                f"paddle-paddle==3.2.1 --hash=sha256:{HASH_B}\n"
            )
