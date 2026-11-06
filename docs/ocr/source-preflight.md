# Source preflight contract

`alfa_document_intelligence.source_intake.inspect_source` accepts an in-memory `bytes` value and a required positive `max_bytes` integer. It rejects empty, over-limit, non-bytes and unrecognized inputs with stable codes that do not include the path or payload. `bool` is not accepted as a size limit. The byte limit is inclusive and checked before hashing. Since the caller has already materialized the `bytes`, this convenience API does not bound memory used by an upstream file read.

`inspect_stream(stream, *, max_bytes)` performs the same classification and hashing while asking a caller-owned binary stream for chunks of at most 64 KiB. It accepts short reads and requests at most one byte beyond the limit to distinguish an exact-limit source from an oversized one. It rejects a stream that returns a non-bytes chunk or more bytes than requested, and converts `OSError` or `ValueError` from reading (including a closed stream) into `source_stream_read_failed` without exposing exception details. The stream is consumed but is not opened, closed, rewound or retained; the caller controls its lifetime. The API reads no path itself.

For accepted bytes, the function returns an immutable `SourceDescriptor` with the SHA-256 digest of the exact byte sequence, its byte count, and a `SourceFormat` identifier. It retains no bytes, filename or path.

## Recognized signatures

- PDF versions 1.0 through 1.7 and 2.0, when the header starts within the first 1024 bytes.
- PNG, JPEG and WebP leading signatures.
- Classic TIFF in little-endian or big-endian byte order, and BigTIFF signatures in both byte orders.

This is signature recognition only. A matching signature does not prove that a file is internally valid, safe to decode, compatible with a selected decoder, or multipage. A file with a misleading extension is classified from its bytes because the API does not accept a filename or extension.

## Stable failures

| Code | Meaning |
| --- | --- |
| `source_descriptor_invalid` | An invalid descriptor was constructed directly. |
| `source_format_unsupported` | No recognized signature was found. |
| `source_limit_invalid` | The caller did not provide a positive exact integer limit. |
| `source_payload_empty` | The supplied byte sequence is empty. |
| `source_payload_invalid` | The value is not exactly `bytes`. |
| `source_stream_invalid` | The stream has no callable `read` method or returns a non-bytes/oversized chunk. |
| `source_stream_read_failed` | The stream read raised `OSError` or `ValueError`; its details are suppressed. |
| `source_too_large` | The byte sequence exceeds the caller's limit. |

The implementation has no path opening, parsers, decoders, rendering, OCR, persistence, network, UI or dependencies. The bytes API cannot bound allocations performed before the call; the stream API depends on the caller-owned stream honoring `read(size)`. Synthetic unit tests do not establish the behavior of actual PDFs or images or satisfy full R1/A4 acceptance.
