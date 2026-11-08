# Document Intelligence current state

Updated: 2026-11-08

## Verified

- Owner-approved PRs #48 and #49 are merged. Public main `68fea56e51606f4efb122c5738dada7180a81aae` passes **217 synthetic tests** in [run 42522647362](https://github.com/voxer21582/OCR-dev/actions/runs/42522647362): 22 taxonomy + 195 application. [CodeQL run 42522647351](https://github.com/voxer21582/OCR-dev/actions/runs/42522647351) also passed. The required check and administrator protections remain enabled; force-push and deletion remain disabled.
- The integrated catalog and record contract preserve legacy 0.1.0 records and validate 0.2.0 embedded catalog snapshots, family references, field names and types. The [catalog manifest](../docs/application/document-family-catalog-manifest.md) and [record manifest](../docs/application/document-family-record-manifest.md) retain provenance, review and limits. Pipeline/UI/archive integration is separate.
- This isolated candidate adds an optional page-count callback to document processing. Three direct synthetic tests passed locally after two expected missing-keyword failures; the existing no-callback behavior already passed. Failure returns an unprocessed copy instead of publishing partial results. The public decoder default and legacy tests remain unchanged. See the [scoped manifest](../docs/application/document-processing-progress-manifest.md).
- Reproduction from `application/`: `PYTHONPATH=src:tests python -B -m unittest -v test_document_processing.DocumentProcessingProgressTests` (use `;` as the path separator on Windows). Only the three selected unittest cases ran; the four existing pytest-style free functions were not executed. Fake decoder/engine paths bypass all vendor and native decoders.

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

- The new progress tests are not yet selected by main CI. A separately reviewed explicit class selector is required; no discovery or workflow change is included in this product contribution.
- The callback is a processor prerequisite, not a background-job implementation. No worker, UI, launcher, installer, production OCR runtime/model, real-document behavior or release is accepted here.
- Public migration remains selective; source ownership, privacy, licenses and scope require per-file review.

## Next steps

1. Review this progress callback and its separate CI proposal. Merge requires owner approval.
2. Continue bounded catalog propagation and worker dependency preparation, preserving existing public fixes and excluding unrelated source changes.
3. Preserve the original checkout and all R7/R8 stop/no-retry restrictions.
