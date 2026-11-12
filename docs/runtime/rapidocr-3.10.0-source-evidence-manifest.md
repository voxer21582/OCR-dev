# Publication manifest — RapidOCR candidate source evidence

**Prepared:** 2026-11-12
**Base:** public `main` at `4271447da4505571ca9087264e18c4a15592b1c8`
**Candidate branch:** `codex/r9-license-source-evidence`
**Related issue:** [#9](https://github.com/voxer21582/OCR-dev/issues/9)

## Included files

| File | Owner | Provenance | Review state | Reason |
| --- | --- | --- | --- | --- |
| `docs/runtime/rapidocr-3.10.0-source-evidence.md` | OCR2 coordinator | Authored from version-pinned upstream source files and official RapidOCR documentation; adds only hashes and aggregate metadata/inventory results from already-present local candidate artifacts; no model, character content, code, OCR output, local path, or private dossier copied | Independent read-only review READY for wording, scope, hash linkage, and stated limits. The reviewer did not reproduce the local protobuf scan, package metadata, RECORD counts, or license-file hashes | SHA-256 `642835861369F2FE97FF6CBD18FF95E767D05847EC5E4822E463771D9D18AA58`. Records pinned source facts, hash-bound local model and installed-package observations, and remaining license, final-package inventory, and offline-verification gates. |

## Excluded material

- Runtime wheels, model files, native binaries, locally generated SBOMs and local environment inventories: not needed for this source-only note and not added.
- Real documents, OCR output, personal or confidential data, credentials and device identifiers: none used or included.
- Previous OCR project files or artifacts: excluded.
- R7/R8 implementation, tests and workflows: excluded and unchanged.

## Verification boundary

- Documentation-only change; `git diff --check` is applicable.
- Claims are linked to exact upstream tags where possible. The RapidOCR documentation pages on `main` are explicitly labeled unpinned and used only to identify a packaging question.
- No legal review, schema validation of an SBOM, native Windows test, network/egress test, model acquisition or real-document evaluation is claimed.
- Source-note SHA-256 and independent-review status are recorded in the manifest table above. The manifest itself remains an auditable file but is not self-hashed.

Independent review confirmed that the linked versioned sources support the candidate version, routes, languages, hashes, top-level license declarations, and the explicit-model-path/dictionary-resolution claims. A follow-up read-only review found the local model and package observations accurately scoped and tied to their stated hashes; the reviewer did not reproduce the protobuf scan, distribution metadata, RECORD counts, or license-file hashes. The model inspection checked its expected SHA-256 before parsing only top-level ONNX metadata using Python's standard library; it emitted key presence and line count, not character values. Installed distribution metadata was read with `importlib.metadata`. No tests, downloads, installs, model inference, network/egress checks or real documents were used. The exact local model and installed-package observations are recorded; original wheel identity, final installer inventory, redistribution review, SBOM, offline behavior and Windows acceptance remain open.

