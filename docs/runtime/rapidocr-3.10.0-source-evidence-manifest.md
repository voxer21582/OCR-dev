# Publication manifest — RapidOCR candidate source evidence

**Prepared:** 2026-11-12
**Base:** public `main` at `4271447da4505571ca9087264e18c4a15592b1c8`
**Candidate branch:** `codex/r9-license-source-evidence`
**Related issue:** [#9](https://github.com/voxer21582/OCR-dev/issues/9)

## Included files

| File | Owner | Provenance | Review state | Reason |
| --- | --- | --- | --- | --- |
| `docs/runtime/rapidocr-3.10.0-source-evidence.md` | OCR2 coordinator | Authored from version-pinned upstream source files and official RapidOCR documentation; no code, models, binaries, local inventory, OCR output, or private dossier copied | Independent read-only review READY on the updated source-loading and dictionary-fallback claims | SHA-256 `7500B893C85FAB496E8E0BEA65D0CD5F72EB8A839A7C02F1F8E580CD099FD6B1`. Records pinned source facts and precise remaining license, packaging, model-metadata, and offline-verification gates for the selected evaluation candidate. |

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

Independent review confirmed that the linked versioned sources support the candidate version, routes, languages, hashes, top-level license declarations, and the updated explicit-model-path/dictionary-resolution claims. It found the remaining exact model-metadata check, redistribution, package inventory, SBOM, offline behavior and Windows acceptance gates correctly left open. Review was read-only; no tests, downloads, installs, model inspection, network/egress checks or runtime checks were performed.

