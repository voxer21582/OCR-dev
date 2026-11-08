# Document Intelligence current state

Updated: 2026-11-08

## Verified

- A separate record-binding candidate based on PR #46 supports legacy 0.1.0 records and 0.2.0 records with self-verifying custom-family snapshots. Custom selections, field names and typed values are checked against those definitions. The existing 13-module local synthetic allowlist passes **195 tests**, including 28 document-contract and 41 catalog tests. Independent review is READY, with 69 targeted tests and 35 synthetic probes also passed; remote verification is pending. The [scoped manifest](../docs/application/document-family-record-manifest.md) records hashes and the static-only JSON Schema validation limit. Pipeline/UI/archive integration is outside this contribution.

- API verification on 2026-11-08 confirms PRs [#41](https://github.com/voxer21582/OCR-dev/pull/41), [#43](https://github.com/voxer21582/OCR-dev/pull/43), and [#44](https://github.com/voxer21582/OCR-dev/pull/44) are merged. Public `main` is `5d07041366bd3875099a3667b5de0fa57a12a2d4`; it includes the selective application migration and the explicit 12-module application CI allowlist. The dated pre-merge evidence below remains historical.
- The document-family catalog candidate adds configurable literal classifications, typed field proposals with source evidence, canonical version/hash snapshots and atomic local JSON catalog persistence. This is a library contribution awaiting integration review, not a UI or archive implementation. Its [publication manifest](../docs/application/document-family-catalog-manifest.md) states provenance and exclusions.
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

- The catalog's 41 tests are not yet in the published CI allowlist; its 183-test result above is local. A separate workflow PR is needed to add only this synthetic module.
- No Windows installer, production OCR runtime/model, real-document behavior, or release is accepted by this state record.
- Public migration remains selective; other source files require file-level provenance, privacy, license, and scope review.

## Next steps

1. Review the catalog candidate and its separate CI allowlist proposal; merge remains subject to owner approval. PRs #41/#43/#44 no longer await integration.
2. Continue the source-vs-public inventory and per-file manifest for remaining migration candidates; do not copy unreviewed or concurrent changes.
3. Continue without modifying the original checkout or resuming R7/R8 work.
