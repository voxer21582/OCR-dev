# R1 — Source preflight design

**Date:** 2026-11-06
**Status:** implementation scope approved by the standing product-development mandate; implementation does not accept R1 or A4.

## Intent

Add a small first step toward document intake: identify byte input by its leading format signature, enforce a caller-supplied size ceiling, and compute the SHA-256 identity of the exact bytes. Support both a materialized bytes convenience API and a caller-owned binary stream API that applies the ceiling during bounded reads. The record will let later import and OCR stages refer to the source without relying on a filename or a declared extension.

## Goals

- Recognize signatures for PDF, PNG, JPEG, WebP, classic TIFF, and BigTIFF.
- Preserve exact byte count and lowercase SHA-256 in an immutable source descriptor.
- Reject empty, non-bytes, over-limit, and unsupported inputs with stable error codes that do not include payload content or paths.
- Read streams in bounded chunks, accept short reads, stop after at most one byte beyond the limit, and leave opening, positioning, closing and stream lifetime to the caller.
- Use only the Python standard library and synthetic in-memory fixtures.

## Non-goals and anti-goals

- This is not a file chooser, filesystem path opener, decoder, renderer, OCR engine, validator, persistence layer, or user interface. A caller may pass an already-open binary stream, but this function neither opens nor closes it.
- A matching signature is only a preliminary format classification; it does not prove internal validity, page count, safety, or decoder compatibility.
- No filename or extension is accepted as evidence of format.
- No document bytes, path, or payload excerpt is retained in the descriptor or error message.
- Do not select an OCR runtime/model, install dependencies, run native Windows acceptance, access real documents, or touch R7/R8 / issue #8.

## Approaches considered

1. **Direct file/path ingestion:** useful for user functionality, but requires file access policy, cancellation, resource management, UI and decoder choices. It is too broad for an independently verifiable first tranche.
2. **Decoder-backed import:** would validate content more deeply, but requires a parser/decoder selection, dependency and licensing review, and runtime authorization under A4.
3. **Bytes and caller-owned bounded stream preflight (selected):** gives a small, reversible boundary that can be tested with synthetic bytes and streams without selecting a decoder or opening paths. It does not claim more than signatures and exact-byte identity, and is not full R1 acceptance.

## Contract

The APIs are `inspect_source(payload: bytes, *, max_bytes: int) -> SourceDescriptor` and `inspect_stream(stream: BinaryIO, *, max_bytes: int) -> SourceDescriptor`. Both require an exact positive integer limit and reject `bool`. The bytes convenience API checks after the caller has materialized its payload, so it cannot bound upstream allocations. The stream API requests at most 64 KiB per read, accepts short reads, and requests at most one byte beyond the inclusive limit to distinguish exact-limit EOF from oversize. It rejects a stream that returns a non-bytes value or more than requested, consumes but does not close or rewind the stream, and suppresses `OSError` and `ValueError` details. The caller owns stream opening, positioning and closure. `SourceDescriptor` contains only `sha256`, `byte_count`, and `format_id`; it is frozen. Stable error codes distinguish invalid payload/stream/limit, empty payload, over-limit input, unsupported signature and read failure. PDF headers may start at offsets 0 through 1023; all other listed formats use their leading signature bytes. Source bytes are not retained.

## Quality and delivery

Synthetic tests cover each signature, both TIFF byte orders and BigTIFF, PDF header offsets 1023 and 1024, digest/byte count, frozen descriptor, mandatory positive limit, exact type checks, empty/over-limit data, short stream reads, exact-limit EOF, one-byte-over-limit behavior, invalid and oversized chunks, read failures, unsupported signatures, and stable content-free errors. A separate CI PR will add exactly `test_source_stream` to the existing explicit allowlist; the required check name, action SHAs, lock hashes, triggers and permissions remain unchanged.

## Acceptance boundary

The tranche is complete when implementation and tests satisfy this design, independent review is READY, its public manifest matches the exact diff, and the feature PR passes the existing GitHub required check. The issue remains open for broader R1 work: file selection, actual decoding, multipage enumeration, corrupt/encrypted files, bounds inside decoders, Windows 11 behavior, and UX still require separate authorized designs and evidence.
