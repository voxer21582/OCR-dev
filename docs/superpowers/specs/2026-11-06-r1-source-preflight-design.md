# R1 — Source preflight design

**Date:** 2026-11-06
**Status:** implementation scope approved by the standing product-development mandate; implementation does not accept R1 or A4.

## Intent

Add a small first step toward document intake: identify an in-memory byte sequence by its leading format signature, enforce a caller-supplied size ceiling, and compute the SHA-256 identity of the exact bytes. The record will let later import and OCR stages refer to the source without relying on a filename or a declared extension.

## Goals

- Recognize signatures for PDF, PNG, JPEG, WebP, classic TIFF, and BigTIFF.
- Preserve exact byte count and lowercase SHA-256 in an immutable source descriptor.
- Reject empty, non-bytes, over-limit, and unsupported inputs with stable error codes that do not include payload content or paths.
- Use only the Python standard library and synthetic in-memory fixtures.

## Non-goals and anti-goals

- This is not a file chooser, filesystem importer, decoder, renderer, OCR engine, validator, persistence layer, or user interface.
- A matching signature is only a preliminary format classification; it does not prove internal validity, page count, safety, or decoder compatibility.
- No filename or extension is accepted as evidence of format.
- No document bytes, path, or payload excerpt is retained in the descriptor or error message.
- Do not select an OCR runtime/model, install dependencies, run native Windows acceptance, access real documents, or touch R7/R8 / issue #8.

## Approaches considered

1. **Direct file/path ingestion:** useful for user functionality, but requires file access policy, cancellation, resource management, UI and decoder choices. It is too broad for an independently verifiable first tranche.
2. **Decoder-backed import:** would validate content more deeply, but requires a parser/decoder selection, dependency and licensing review, and runtime authorization under A4.
3. **In-memory bounded signature preflight (selected):** gives a small, reversible boundary that can be tested with synthetic bytes and does not claim more than it proves. It is not full R1 acceptance.

## Contract

The public API will be `inspect_source(payload: bytes, *, max_bytes: int) -> SourceDescriptor`. Both arguments are validated with exact built-in types (so `bool` is not accepted as an integer). The positive byte limit is mandatory and inclusive. Because the caller has already materialized `payload`, this limit does not bound upstream file reads or allocations. `SourceDescriptor` contains only `sha256`, `byte_count`, and `format_id`; it is frozen. Stable error codes distinguish invalid payload/limit, empty payload, over-limit input, and unsupported signature. PDF headers may occur within the first 1024 bytes; all other listed formats use their standard leading signature bytes. The original bytes are not retained.

## Quality and delivery

Synthetic tests cover each signature, both TIFF byte orders and BigTIFF, PDF header offset, extension independence (there is no extension input), invalid argument types, empty/oversized payloads, unsupported signatures, digest correctness, immutability, and data-free stable errors. The new test module is run explicitly locally. A separate CI PR will add exactly `test_source_intake` to the existing allowlist after this feature branch is reviewable; the existing required check name, action SHAs, lock hashes, triggers and permissions remain unchanged.

## Acceptance boundary

The tranche is complete when implementation and tests satisfy this design, independent review is READY, its public manifest matches the exact diff, and the feature PR passes the existing GitHub required check. The issue remains open for broader R1 work: file selection, actual decoding, multipage enumeration, corrupt/encrypted files, bounds inside decoders, Windows 11 behavior, and UX still require separate authorized designs and evidence.
