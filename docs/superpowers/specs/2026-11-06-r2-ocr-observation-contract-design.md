# R2 OCR observation contract design

## Intent

Define a small, engine-neutral Python boundary for one page entering OCR and the observations returned for that page. It makes source hash, page, region, declared engine/model/runtime identity, and uncertainty part of the data contract before any engine or runtime is selected.

## Goals and acceptance

- Immutable typed values represent engine identity, page input, normalized polygon region, text observation, and page result.
- A shared validator confirms both that the result belongs to the requested source page and that it matches the registered engine identity.
- Reject malformed source hashes, invalid page numbers, invalid regions, invalid confidence values, and inconsistent failed/partial results with stable, sanitized error codes.
- Reject self-intersecting polygons even if their signed shoelace area is nonzero. Regression fixture: `((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.8, 0.0))`; its non-adjacent edges cross, so construction must raise `OCRContractError` with code `ocr_region_invalid`.
- Bound polygon validation to at most 256 vertices, rejecting larger regions before pairwise edge checks with `ocr_region_invalid`.
- Provide a `Protocol` for future engine implementations without implementing or loading one.
- Unit tests use synthetic byte strings and metadata only.

## Non-goals and anti-goals

- No OCR engine, model, renderer, file import, persistence, UI, network, process launcher, or Windows runtime integration.
- No claim of OCR readiness, A4 acceptance, accuracy, or full R2 completion.
- No changes to R7/R8, issue #8, GitHub Actions, dependencies, or original OCR project.

## Constraints

- Use the public repository's existing Python style and standard library only.
- Each observation carries the original document SHA-256 and 1-based page number through its page result; text regions use normalized page coordinates.
- If an engine has no separate model artifact, both model identity values may be absent; a partial model identity is invalid.
- Confidence may be absent; when present it is a finite number in `[0, 1]`.
- Failure metadata contains only a stable code, never exception text, paths, or document content.

## Approaches considered

1. **Select an engine-specific API now.** Rejected because A4 has not selected or licensed a runtime/model tuple and this would prematurely couple OCR2 to one engine.
2. **Add metadata classes without an engine boundary.** Rejected because each future integration would invent its own input/result contract and provenance fields.
3. **Add minimal immutable page/result contracts plus a `Protocol`.** Chosen as a reversible boundary: it standardizes evidence shape while remaining non-operational until an authorized implementation is selected.

## Technical choices

- A page region is a polygon of normalized `(x, y)` float pairs, allowing non-axis-aligned text boxes without tying the contract to an OCR vendor.
- Page results carry `complete`, `partial`, or `failed` status. A failed result has no observations and requires a sanitized error code; a complete result has no error code, while a partial result may include one.
- The engine protocol exposes an immutable identity and a synchronous single-page `recognize_page` call. Scheduling, cancellation, isolation, and async execution belong to a later runtime design and are not implied here.
- Results are checked against both the input page provenance and the registered `EngineIdentity` before consumption.
- `PageInput` carries rendered page bytes but performs no decoding, hashing of the source, file access, or persistence. The caller supplies the source document hash.

## Open for later design

Exact engine/runtime identity values, rendering, page lifecycle, cancellation, confidence calibration, result persistence, and Windows isolation remain future decisions under A4 and the relevant product acceptance criteria.
