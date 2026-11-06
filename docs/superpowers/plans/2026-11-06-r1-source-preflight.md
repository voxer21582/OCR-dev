# R1 Source Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded, signature-only source identity for bytes and caller-owned binary streams for the R1 formats listed in the design.

**Architecture:** A standard-library-only module validates bytes or caller-owned streams and an explicit size limit, classifies the signature, and computes the exact-byte digest. Stream reads are bounded and the module does not open paths or invoke parsers, renderers, OCR, persistence or network.

**Tech Stack:** CPython 3.13, `dataclasses`, `enum`, `hashlib`, `re`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-06-r1-source-preflight-design.md`

## Global Constraints

- Synthetic in-memory bytes and streams only; no real document data.
- Standard library only; no installation or dependency changes.
- R7/R8 and issue #8 stay untouched; no native Windows/runtime tests.
- CI workflow changes belong to a separate PR and use an explicit module allowlist.
- Required check `Taxonomy registry and binding`, action SHA pins, hashes, permissions, triggers and main protections remain unchanged.

## Review Focus

- Forged or truncated bytes must be described only as signature matches, never as internally valid documents.
- Size limit is mandatory, inclusive and checked before hashing.
- Exact type checks reject `bool`, bytearray and custom integer/byte-like values.
- Stream reads never request more than 64 KiB or one byte beyond the supplied limit; short reads are accepted, oversized chunks rejected, and the caller retains stream lifecycle ownership.
- Stable failures must not contain payload bytes or paths.
- PDF signature at a permitted offset must be distinguished from arbitrary unsupported content.

---

### Task 1: Add synthetic contract tests

**Files:**
- Test: `tests/test_source_intake.py`
- Test: `tests/test_source_stream.py`

**Interfaces:** consumes public API planned in the spec: `inspect_source(payload, *, max_bytes)`, `SourceDescriptor`, `SourceInspectionError`.

- [ ] Add tests for PDF, PNG, JPEG, WebP, classic TIFF in both byte orders, BigTIFF, and PDF header offsets 0, 1023 and 1024 (last accepted start offset and first rejected offset).
- [ ] Add tests for digest/byte count, frozen descriptor, mandatory positive limit, exact type checks, empty/over-limit data, unsupported signature, and stable content-free error codes.
- [ ] Add stream tests for short reads, hash identity, exact-limit EOF, at most one byte beyond limit, invalid/oversized chunks, read errors without leaked details, and caller-owned close/rewind lifecycle.
- [ ] Run `PYTHONPATH=src:tests python -B -m unittest -v test_source_intake`; confirm expected failures are due to missing implementation.

### Task 2: Implement the minimum source preflight

**Files:**
- Create: `src/alfa_document_intelligence/source_intake.py`

**Interfaces:** exports `SourceDescriptor`, `SourceFormat`, `SourceInspectionError`, `inspect_source`, and `inspect_stream`.

- [ ] Implement exact type and limit checks with stable errors.
- [ ] Implement the signature classification fixed by the design, including bounded PDF header search.
- [ ] Compute SHA-256 over exact input bytes and return only immutable metadata.
- [ ] Implement bounded streaming reads, handling short reads, enforcing max-bytes-plus-one detection, and suppressing `OSError` details without closing or rewinding the stream.
- [ ] Re-run `test_source_intake` and `test_source_stream` and confirm all cases pass.

### Task 3: Document scope and manifest

**Files:**
- Create: `docs/ocr/source-preflight.md`
- Create: `docs/agent-work/issue-22-stream-manifest.md`
- Modify: `README.md`

- [ ] Document signature-only behavior, format scope, limits, stable errors, and explicit non-goals; make no claim of valid decode or full R1.
- [ ] Document that the bytes API checks after materialization and the stream API depends on the supplied stream honoring bounded `read(size)` calls.
- [ ] Link the document from README while preserving its description of the existing CI allowlist.
- [ ] Record each changed file, owner, provenance, exact hash, review state, inclusion reason, and exclusions in a public-safe manifest.

### Task 4: Verify and review the feature diff

**Files:** all feature and documentation files above.

- [ ] Run only `test_source_intake`, `test_source_stream`, `test_ocr_contracts`, `git diff --check`, and hash/manifest checks in the feature branch.
- [ ] Obtain independent review of the exact final diff, verifying no filesystem, decoder, OCR, real-data or blocked-scope path.
- [ ] Create a feature PR stacked on the current R1 CI PR #24 branch; do not merge.

### Task 5: Prepare the separate CI follow-up

**Files:** separate CI branch/PR only.

- [ ] Keep the existing `test_source_intake` entry and add only `test_source_stream` to the explicit allowlist after the stream feature base is available.
- [ ] Verify workflow diff for unchanged check name, action pins, dependency hashes, permissions, triggers and runner.
- [ ] Run GitHub Actions, record run URLs and test count, and obtain independent workflow review. Do not merge.

The current feature branch is expected to run 43 tests (the existing 42 plus the PDF offset-1024 regression); the separate stream CI follow-up is expected to run 52 (43 plus 9 stream tests).
