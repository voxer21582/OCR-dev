# Publication manifest — RapidOCR candidate source evidence

**Prepared:** 2026-11-12
**Base:** public `main` at `4271447da4505571ca9087264e18c4a15592b1c8`
**Candidate branch:** `codex/r9-license-source-evidence`
**Related issue:** [#9](https://github.com/voxer21582/OCR-dev/issues/9)

## Included files

| File | Owner | Provenance | Review state | Reason |
| --- | --- | --- | --- | --- |
| `docs/runtime/rapidocr-3.10.0-source-evidence.md` | OCR2 coordinator | Authored from version-pinned upstream source files and official RapidOCR documentation; no code, models, binaries, local inventory, OCR output, or private dossier copied | Independent read-only review READY; reviewed source facts, hash pins and scope; no findings | SHA-256 `9083CD9B86C4D6B3BE6DD38368F14698393A213007AF7CE53EC19BF865398B46`. Records public-source facts and precise remaining license/packaging gates for the already selected evaluation candidate. |

## Excluded material

- Runtime wheels, model files, native binaries, locally generated SBOMs and local environment inventories: not needed for this source-only note and not added.
- Real documents, OCR output, personal or confidential data, credentials and device identifiers: none used or included.
- Previous OCR project files or artifacts: excluded.
- R7/R8 implementation, tests and workflows: excluded and unchanged.

## Verification boundary

- Documentation-only change; `git diff --check` is applicable.
- Claims are linked to exact upstream tags where possible. The RapidOCR documentation pages on `main` are explicitly labeled unpinned and used only to identify a packaging question.
- No legal review, schema validation of an SBOM, native Windows test, network/egress test, model acquisition or real-document evaluation is claimed.
- The manifest SHA-256 and final review result must be added to the PR after the content is final.

Independent review confirmed that the linked versioned sources support the stated candidate version, model routes, language codes, hashes and top-level license declarations. The reviewer found the remaining redistribution, complete-package inventory, SBOM, offline behavior and Windows acceptance gates correctly left open. Review was read-only; no tests, downloads, installs or runtime checks were performed.
