# OCR observation contract

This document describes a passive data boundary for future OCR engine integration. It does not provide an engine or make OCR operational.

## Page input and identity

`PageInput` contains already-rendered page bytes, their media type, and `PageProvenance`. Provenance records the lowercase SHA-256 of the original document and a 1-based page number. The caller supplies the original document hash; this contract does not open files, render pages, or verify that hash against source bytes.

`EngineIdentity` identifies the engine and runtime by nonempty version strings. Model identity is a name/version pair and may be absent together when the selected engine has no separate model artifact. The existence of this record does not establish that any named runtime or model is installed, licensed, safe, or accepted.

## Observations

Each `TextObservation` preserves literal recognized text, a polygon region in normalized page coordinates, and optional confidence. Confidence is not a validation or review decision. Missing confidence remains unknown; this contract has no confirmed/approved state.

Regions must contain 3 to 256 ordered vertices and form simple polygons: non-adjacent edges may not cross, touch, or overlap. The 256-vertex ceiling bounds the pairwise geometry check before it begins; larger polygons are rejected with the same stable code. The regression test constructs a synthetic normalized 257-vertex polygon on a circle; the old implementation accepted it and started the quadratic edge check, while the bounded contract rejects it immediately. A separate invalid example, `((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.8, 0.0))`, has nonzero signed shoelace area but its first and third edges cross. Constructing either invalid region raises `OCRContractError` with the stable code `ocr_region_invalid`.

`PageOCRResult` carries the source provenance and declared engine identity. The caller must pass the registered `EngineIdentity` to `validate_page_result`; the validator rejects a result whose source page or identity differs from the request. Result status is `complete`, `partial`, or `failed`. A failed result contains no observations and must use a stable lowercase error code rather than exception text, paths, or document content.

## Limitations and next gates

- The `OCREngine` protocol has no implementation. No OCR operation occurs in this package.
- The page byte payload is not decoded, bounded, persisted, or transmitted by these types. Resource limits, rendering, cancellation, isolation, and error lifecycle belong to later designs.
- Synthetic unit tests verify contract validation only. They do not establish model accuracy, OCR provenance in a running application, Windows compatibility, offline behavior, A4 acceptance, or full R2 completion.
- Runtime/model selection, licensing, integration, and native Windows 11 checks remain subject to A4 and their own review and authorization.
