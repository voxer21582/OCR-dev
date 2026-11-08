# Document-family catalog publication manifest

Prepared 2026-11-08 for migration issue [#42](https://github.com/voxer21582/OCR-dev/issues/42).
Base: public OCR-dev `main` at `5d07041366bd3875099a3667b5de0fa57a12a2d4`.
Owner for every included file: OCR2 development coordinator, with explicit user ownership for the catalog source/test and scoped ownership for six OCR-limit constants.

## Included files

| File | Provenance and inclusion reason |
| --- | --- |
| `application/src/alfa_document_intelligence/document_family_catalog.py` | Current OCR2 development, isolated and independently reviewed. Adds bounded data-only family definitions, version/hash snapshots, evidence-bound uncertain proposals and local catalog persistence. No previous OCR project source used. |
| `application/src/alfa_document_intelligence/ocr_adapter.py` | Existing public file plus exactly six declarative limit constants. No adapter implementation or native engine change. |
| `application/tests/test_document_family_catalog.py` | Current OCR2 development and synthetic regression cases, independently reviewed. Uses standard-library fixtures and temporary catalog files only. |
| `application/CURRENT_STATE.md` | Existing public status plus dated API-confirmed merge status and bounded local test results. |
| `docs/application/document-family-catalog-manifest.md` | New public inclusion/exclusion and verification record; no local paths or private dossier contents. |

SHA-256 of source/test contents after LF newline normalization:

| File | SHA-256 |
| --- | --- |
| `document_family_catalog.py` | `287d1ff682f4596302c82aa0f5cce810a896c400f6901c9539a84bb265a10509` |
| `ocr_adapter.py` | `a3db37d5eef88e080dc4fcada7a5b6c7a1233d874a7258be9f5999837c6bec41` |
| `test_document_family_catalog.py` | `c9abccf8dce3c6a89b16ff3dc79529cee5dab5839400df350e865254ded32df3` |

## Verification and effects

- 41 catalog tests passed locally, including successful large catalog snapshot/save/reopen regressions and bounded malformed-input rejection.
- On the canonical application base, the 12 existing explicitly allowed modules plus this module passed 183 tests. See the exact reproduction command in `application/CURRENT_STATE.md`.
- Independent code review found no actionable issue in the final roundtrip corrections; reviewer additionally passed 61 encoding-size comparisons and seven malformed-input/depth/cycle probes. This is an agent review, not a formal GitHub approval.
- Import chain: test module -> catalog -> public `ocr_adapter` dataclasses/constants and standard library. Neither module loads an OCR engine, decoder, archive library, credentials or external service. Test fixtures contain synthetic hashes, token text and geometries only.
- The new module is not yet listed in CI. Push/PR triggers the existing unchanged workflow: 22 taxonomy tests and the 12-module application allowlist. A separate CI proposal will add only the catalog module, with no discovery or new dependency.
- Existing SHA-pinned actions, hash-locked dependencies, `contents: read`, Ubuntu standard runner, required check `Taxonomy registry and binding`, and main protections remain unchanged.

## Exclusions and limitations

Excluded: private Git history, local paths/dossiers/raw outputs, runtime/model/native binaries, installer notices, real documents or derived OCR, secrets, dependencies, workflows, UI/launcher wiring, archive/restore code, R7/R8 and tests for blocked components.

These checks establish catalog-library behavior. UI integration, application-wide acceptance, Windows installer readiness and real OCR quality remain unverified. This contribution neither closes issue #42 nor authorizes a merge or a release. Privacy review is limited to the five named files; no assertion is made about unreviewed local artifacts.
