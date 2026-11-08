# Document Intelligence current state

Updated: 2026-11-08

## Verified

- An isolated optional-runtime-factory candidate now also fixes the default RGB bridge while preserving injected `image_decoder` callbacks. The explicit application allowlist passes **193 local synthetic tests**, including **19 targeted factory/adapter tests** with fake vendor objects and distinct channel bytes. Independent review of the expanded factory/RGB diff is READY. The [scoped manifest](../docs/application/optional-runtime-factory-manifest.md) records provenance and the pending eighth worker test. Worker/launcher integration, real vendor inference and remote verification remain separate; no runtime is enabled by this candidate.

- API verification on 2026-11-08 confirms PRs #41/#43/#44/#46/#47 are merged. This candidate is based on public `main` `0a2fba0731e230f385e305826b66e4ce17df854d`; [run 42519804658](https://github.com/voxer21582/OCR-dev/actions/runs/42519804658) passed 22 taxonomy + 183 application tests (205 total) from its explicit allowlist. The dated pre-merge evidence below remains historical.
- The integrated document-family catalog adds configurable literal classifications, typed field proposals with source evidence, canonical version/hash snapshots and atomic local JSON catalog persistence. This is a library contribution, not a UI or archive implementation. Its [publication manifest](../docs/application/document-family-catalog-manifest.md) states provenance and exclusions. Separate record-binding PR #49 remains under review and is not assumed part of this candidate's base.
- On the canonical candidate base, the 12 existing synthetic application modules plus `test_document_family_catalog` pass **183 local tests** (142 existing + 41 catalog). The catalog regressions preserve valid large snapshot and save/reopen roundtrips while rejecting malformed/oversized input. No installed OCR engine is invoked.
- Reproduction from `application/` with the existing Python environment: `PYTHONPATH=src:tests python -B -m unittest -q test_public_data_guard test_contract_baseline test_document_contract test_document_decoder_contract test_ingestion test_ocr_adapter test_semantic_proposals test_analysis_pipeline test_document_validation test_loopback_csrf test_manual_region_review test_rapidocr_adapter test_document_family_catalog` (use `;` as the path separator on Windows).

### Earlier dated evidence

- Public `main` at `86c9398905fb4baf4a54b58b303ddf8325c4e768` contains the initial selective application snapshot under `application/` (PR #38); it is not the full private checkout.
- Product branch `codex/ocr2-manual-review-rapidocr` is under PR [#43](https://github.com/voxer21582/OCR-dev/pull/43), stacked on the explicit application-test baseline in PR #41. It adds loopback mutation protection, human-authored source-region evidence for absent fields, and an optional RapidOCR adapter around an already configured engine.
- The explicit synthetic local command completed 142 tests successfully on 2026-11-08. It names `test_public_data_guard`, `test_contract_baseline`, `test_document_contract`, `test_document_decoder_contract`, `test_ingestion`, `test_ocr_adapter`, `test_semantic_proposals`, `test_analysis_pipeline`, `test_document_validation`, `test_loopback_csrf`, `test_manual_region_review`, and `test_rapidocr_adapter`.
- GitHub Actions run [42466305469](https://github.com/voxer21582/OCR-dev/actions/runs/42466305469), for CI PR [#44](https://github.com/voxer21582/OCR-dev/pull/44), passed: 22 taxonomy tests and 142 explicitly allowlisted application tests (`OK`). The test log confirms both suite totals. PR #43's current required-check runs also pass, but its base allowlist predates the three modules added by PR #44.
- `py_compile` passed for the changed application modules/tests, and `git diff --check` passed.
- Independent read-only reviews of the product diff and the CI-only allowlist diff returned READY.
- Manual region correction is bound to the source hash/page, does not run OCR, and does not write to the archive. R7/R8 were not touched.
- `rapidocr_adapter.py` is dependency-lazy and accepts an already configured engine; no RapidOCR package/model was installed or downloaded, and no production OCR result is claimed.

## Not verified

- The seven direct factory tests are not yet selected by the published CI; a separate one-module extension is needed. The RGB tests reside in the already selected adapter module. The local 193-test application result is not a remote result for this candidate, and does not include the separate record-binding PR #49 changes.
- No Windows installer, production OCR runtime/model, real-document behavior, or release is accepted by this state record.
- Public migration remains selective; other source files require file-level provenance, privacy, license, and scope review.

## Next steps

1. Review the optional factory/RGB candidate and its separate CI allowlist proposal; merge remains subject to owner approval. PRs #41/#43/#44/#46/#47 no longer await integration. PR #49 is a separate record-binding contribution.
2. Continue the source-vs-public inventory and per-file manifest for remaining migration candidates; do not copy unreviewed or concurrent changes.
3. Continue without modifying the original checkout or resuming R7/R8 work.
