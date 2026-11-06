from __future__ import annotations

import hashlib
import unittest

from alfa_document_intelligence.source_intake import (
    SourceFormat,
    SourceInspectionError,
    inspect_source,
)


class SourceIntakeTests(unittest.TestCase):
    def test_recognizes_supported_signatures_without_claiming_decode(self) -> None:
        fixtures = (
            (b"%PDF-1.7\nsynthetic", "pdf"),
            (b"\x89PNG\r\n\x1a\nsynthetic", "png"),
            (b"\xff\xd8\xffsynthetic", "jpeg"),
            (b"RIFF\x04\x00\x00\x00WEBPsynthetic", "webp"),
            (b"II*\x00synthetic", "tiff"),
            (b"MM\x00*synthetic", "tiff"),
            (b"II+\x00synthetic", "tiff"),
            (b"MM\x00+synthetic", "tiff"),
        )

        for payload, format_id in fixtures:
            with self.subTest(format_id=format_id, signature=payload[:12]):
                descriptor = inspect_source(payload, max_bytes=len(payload))
                self.assertEqual(descriptor.format_id.value, format_id)
                self.assertEqual(descriptor.byte_count, len(payload))
                self.assertIsInstance(descriptor.format_id, SourceFormat)

    def test_accepts_pdf_header_at_offset_1023_and_rejects_after_limit(self) -> None:
        payload = b" " * 1023 + b"%PDF-2.0\n"
        self.assertEqual(inspect_source(payload, max_bytes=len(payload)).format_id.value, "pdf")

        with self.assertRaises(SourceInspectionError) as caught:
            inspect_source(payload, max_bytes=len(payload) - 1)
        self.assertEqual(caught.exception.code, "source_too_large")

    def test_rejects_pdf_header_starting_after_offset_1023(self) -> None:
        payload = b" " * 1024 + b"%PDF-2.0\n"
        with self.assertRaises(SourceInspectionError) as caught:
            inspect_source(payload, max_bytes=len(payload))
        self.assertEqual(caught.exception.code, "source_format_unsupported")

    def test_digest_is_for_exact_bytes_and_descriptor_is_immutable(self) -> None:
        payload = b"\x89PNG\r\n\x1a\nsynthetic image payload"
        descriptor = inspect_source(payload, max_bytes=len(payload))
        self.assertEqual(descriptor.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(descriptor.byte_count, len(payload))
        with self.assertRaises((AttributeError, TypeError)):
            descriptor.sha256 = "0" * 64  # type: ignore[misc]

    def test_rejects_invalid_payload_types_and_empty_bytes_with_stable_codes(self) -> None:
        for payload in (None, "%PDF-1.7", bytearray(b"%PDF-1.7"), memoryview(b"%PDF-1.7")):
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaises(SourceInspectionError) as caught:
                    inspect_source(payload, max_bytes=100)  # type: ignore[arg-type]
                self.assertEqual(caught.exception.code, "source_payload_invalid")

        with self.assertRaises(SourceInspectionError) as caught:
            inspect_source(b"", max_bytes=100)
        self.assertEqual(caught.exception.code, "source_payload_empty")

    def test_requires_positive_exact_integer_limit(self) -> None:
        for max_bytes in (True, False, 0, -1, 1.5, "100"):
            with self.subTest(max_bytes=max_bytes):
                with self.assertRaises(SourceInspectionError) as caught:
                    inspect_source(b"%PDF-1.7", max_bytes=max_bytes)  # type: ignore[arg-type]
                self.assertEqual(caught.exception.code, "source_limit_invalid")

    def test_unsupported_signature_does_not_expose_payload(self) -> None:
        payload = b"SYNTHETIC_PRIVATE_MARKER"
        with self.assertRaises(SourceInspectionError) as caught:
            inspect_source(payload, max_bytes=len(payload))
        self.assertEqual(caught.exception.code, "source_format_unsupported")
        self.assertEqual(str(caught.exception), "source_format_unsupported")
        self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
