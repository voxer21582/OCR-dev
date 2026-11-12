import dataclasses
import hashlib
import unittest
from dataclasses import FrozenInstanceError

from alfa_document_intelligence.source_preflight import (
    SourcePreflightRejected,
    preflight_source_bytes,
)


class SourcePreflightTests(unittest.TestCase):
    def test_recognizes_synthetic_signatures_and_ignores_declared_extension(self):
        examples = (
            (b"%PDF-1.7\nsynthetic", "pdf", None),
            (b"\x89PNG\r\n\x1a\n", "png", None),
            (b"\xff\xd8\xffsynthetic", "jpeg", None),
            (b"RIFF\x00\x00\x00\x00WEBP", "webp", None),
            (b"II*\x00synthetic", "tiff", None),
            (b"MM\x00*synthetic", "tiff", None),
            (b"\x89PNG\r\n\x1a\n", "png", ".pdf"),
        )
        for content, expected, extension in examples:
            with self.subTest(expected=expected, extension=extension):
                result = preflight_source_bytes(
                    content, max_bytes=128, declared_extension=extension
                )
                self.assertEqual(result.media_kind, expected)

    def test_record_has_only_hash_size_and_kind_and_is_immutable(self):
        content = b"%PDF-1.7\nsynthetic"
        result = preflight_source_bytes(content, max_bytes=128)
        self.assertEqual(
            {field.name for field in dataclasses.fields(result)},
            {"sha256", "byte_count", "media_kind"},
        )
        self.assertEqual(result.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(result.byte_count, len(content))
        with self.assertRaises(FrozenInstanceError):
            result.byte_count = 0

    def assert_rejected(self, operation, code):
        with self.assertRaises(SourcePreflightRejected) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    def test_rejects_invalid_maximum(self):
        for limit in (0, -1, True, 1.5, "10"):
            with self.subTest(limit=limit):
                self.assert_rejected(
                    lambda: preflight_source_bytes(b"%PDF-", max_bytes=limit),
                    "invalid_limit",
                )

    def test_rejects_non_bytes(self):
        for value in ("%PDF-1.7", bytearray(b"%PDF-1.7"), memoryview(b"%PDF-1.7"), None):
            with self.subTest(type=type(value).__name__):
                self.assert_rejected(
                    lambda: preflight_source_bytes(value, max_bytes=128),
                    "invalid_input",
                )

    def test_rejects_empty_oversized_and_unrecognized_input_without_echo(self):
        self.assert_rejected(
            lambda: preflight_source_bytes(b"", max_bytes=128), "empty_input"
        )
        self.assert_rejected(
            lambda: preflight_source_bytes(b"%PDF-1.7", max_bytes=4),
            "content_too_large",
        )
        content = b"SYNTHETIC-UNSUPPORTED-CONTENT"
        with self.assertRaises(SourcePreflightRejected) as caught:
            preflight_source_bytes(content, max_bytes=128)
        self.assertEqual(caught.exception.code, "unsupported_signature")
        self.assertNotIn(content.decode(), str(caught.exception))


if __name__ == "__main__":
    unittest.main()
