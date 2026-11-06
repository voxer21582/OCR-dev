from __future__ import annotations

from io import BytesIO
import unittest

from alfa_document_intelligence.source_intake import (
    SourceInspectionError,
    inspect_source,
    inspect_stream,
)


class ShortReadStream:
    def __init__(self, payload: bytes, *, max_chunk: int = 17) -> None:
        self._stream = BytesIO(payload)
        self.max_chunk = max_chunk
        self.requested_sizes: list[int] = []
        self.bytes_returned = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        self.requested_sizes.append(size)
        if size < 0:
            raise AssertionError("unbounded read requested")
        result = self._stream.read(min(size, self.max_chunk))
        self.bytes_returned += len(result)
        return result


class SourceStreamTests(unittest.TestCase):
    def test_short_reads_hash_exact_bytes_and_leave_stream_open(self) -> None:
        payload = b"RIFF\x04\x00\x00\x00WEBP" + b"synthetic" * 1000
        stream = ShortReadStream(payload)

        streamed = inspect_stream(stream, max_bytes=len(payload))
        buffered = inspect_source(payload, max_bytes=len(payload))

        self.assertEqual(streamed, buffered)
        self.assertGreater(len(stream.requested_sizes), 1)
        self.assertTrue(all(size > 0 for size in stream.requested_sizes))
        self.assertFalse(stream.closed)

    def test_over_limit_reads_at_most_one_byte_past_the_limit(self) -> None:
        payload = b"X" * 256
        stream = ShortReadStream(payload, max_chunk=11)
        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(stream, max_bytes=64)

        self.assertEqual(caught.exception.code, "source_too_large")
        self.assertEqual(stream.bytes_returned, 65)

    def test_exact_limit_is_accepted_after_eof_check(self) -> None:
        payload = b"%PDF-1.7"
        stream = BytesIO(payload)
        descriptor = inspect_stream(stream, max_bytes=len(payload))
        self.assertEqual(descriptor, inspect_source(payload, max_bytes=len(payload)))
        self.assertEqual(stream.tell(), len(payload))
        self.assertFalse(stream.closed)

    def test_empty_stream_has_a_stable_error(self) -> None:
        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(BytesIO(), max_bytes=10)
        self.assertEqual(caught.exception.code, "source_payload_empty")

    def test_invalid_stream_and_non_bytes_chunks_are_rejected(self) -> None:
        for stream in (None, object()):
            with self.subTest(stream_type=type(stream).__name__):
                with self.assertRaises(SourceInspectionError) as caught:
                    inspect_stream(stream, max_bytes=10)  # type: ignore[arg-type]
                self.assertEqual(caught.exception.code, "source_stream_invalid")

        class NonBytesStream:
            def read(self, size: int) -> bytearray:
                return bytearray(b"%PDF-1.7")

        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(NonBytesStream(), max_bytes=20)
        self.assertEqual(caught.exception.code, "source_stream_invalid")

    def test_stream_that_ignores_read_bound_is_rejected(self) -> None:
        class OversizedChunkStream:
            def read(self, size: int) -> bytes:
                return b"%PDF-1.7" * 10

        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(OversizedChunkStream(), max_bytes=100)
        self.assertEqual(caught.exception.code, "source_stream_invalid")

    def test_read_failure_does_not_expose_exception_details(self) -> None:
        class FailingStream:
            def read(self, size: int) -> bytes:
                raise OSError("synthetic-secret-path")

        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(FailingStream(), max_bytes=100)
        self.assertEqual(caught.exception.code, "source_stream_read_failed")
        self.assertEqual(str(caught.exception), "source_stream_read_failed")
        self.assertNotIn("synthetic-secret-path", repr(caught.exception))

    def test_closed_stream_has_stable_read_failure(self) -> None:
        stream = BytesIO(b"%PDF-1.7")
        stream.close()
        with self.assertRaises(SourceInspectionError) as caught:
            inspect_stream(stream, max_bytes=100)
        self.assertEqual(caught.exception.code, "source_stream_read_failed")
        self.assertEqual(str(caught.exception), "source_stream_read_failed")

    def test_stream_limit_requires_positive_exact_integer(self) -> None:
        for max_bytes in (True, False, 0, -1, 1.5, "10"):
            with self.subTest(max_bytes=max_bytes):
                with self.assertRaises(SourceInspectionError) as caught:
                    inspect_stream(BytesIO(b"%PDF-1.7"), max_bytes=max_bytes)  # type: ignore[arg-type]
                self.assertEqual(caught.exception.code, "source_limit_invalid")


if __name__ == "__main__":
    unittest.main()
