# Publication manifest — RapidOCR candidate source evidence

**Prepared:** 2026-11-12
**Base at initial branch preparation:** public `main` at `4271447da4505571ca9087264e18c4a15592b1c8`
**Current PR base (verified 2026-11-12):** public `main` at `4a2206a6b6c53f784277a45e195552dc33e66ed5
**Candidate branch:** `codex/r9-license-source-evidence`
**Related issue:** [#9](https://github.com/voxer21582/OCR-dev/issues/9)

## Included files

| File | Owner | Provenance | Review state | Reason |
| --- | --- | --- | --- | --- |
| `docs/runtime/rapidocr-3.10.0-source-evidence.md` | OCR2 coordinator | Authored from version-pinned upstream source files, official RapidOCR documentation, PyPI release metadata, and aggregate observations from already-present local candidate artifacts; no model, wheel, character content, code, OCR output, local path, or private dossier copied | Initial independent read-only review READY for wording, source metadata, compatibility tags, hash linkage, scope, and stated limits. Two editorial clarifications were added after that review; final-head re-review is pending. The reviewer did not reproduce the local Python/environment observation, protobuf scan, package metadata, RECORD counts, or license-file hashes | SHA-256 `216AF7871C9819F92A841E1F684483E852B74B00CE1385E8F4DCD1BD9FF3F706` (computed over the UTF-8 note content fetched from the PR branch after the wording correction). Records pinned source facts, PyPI expected wheel filenames/digests (not locally verified), hash-bound local model and installed-package observations, and remaining license, final-package inventory, and offline-verification gates. |

## Excluded material

- Runtime wheels, model files, native binaries, locally generated SBOMs and local environment inventories: not needed for this source-only note and not added.
- Real documents, OCR output, personal or confidential data, credentials and device identifiers: none used or included.
- Previous OCR project files or artifacts: excluded.
- R7/R8 implementation, tests and workflows: excluded and unchanged.

## Verification boundary

- Documentation-only change; `git diff --check` is applicable.
- Claims are linked to exact upstream tags where possible. The RapidOCR documentation pages on `main` are explicitly labeled unpinned and used only to identify a packaging question. PyPI wheel hashes come from public release metadata; the archives were not downloaded or validated locally.
- No legal review, schema validation of an SBOM, native Windows test, network/egress test, model acquisition or real-document evaluation is claimed.
- Source-note SHA-256 and independent-review status are recorded in the manifest table above. The manifest itself remains an auditable file but is not self-hashed.

Independent review confirmed that the linked versioned sources support the candidate version, routes, languages, hashes, top-level license declarations, and the explicit-model-path/dictionary-resolution claims. A follow-up read-only review found the local model and package observations accurately scoped and tied to their stated hashes; the reviewer did not reproduce the protobuf scan, distribution metadata, RECORD counts, license-file hashes, or local Python/platform observation. The reviewer independently confirmed the two PyPI wheel filenames, compatibility tags, and expected hashes from PyPI metadata, and confirmed that the note labels those hashes as unverified archive identities. The model inspection checked its expected SHA-256 before parsing only top-level ONNX metadata using Python's standard library; it emitted key presence and line count, not character values. Installed distribution metadata was read with `importlib.metadata`. No tests, downloads, installs, model inference, network/egress checks or real documents were used. The exact local model and installed-package observations are recorded; archive verification, complete dependency lock, final installer inventory, redistribution review, SBOM, offline behavior and Windows acceptance remain open.

