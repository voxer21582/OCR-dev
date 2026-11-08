# Document Intelligence current state

Updated: 2026-11-08

## Verified

- Owner-approved PRs #48 through #55 and #58/#59 are merged. Public main `6facee4b814b4bffbe0f80a463d9077532313364` passes **261 synthetic tests** in [run 42531784209](https://github.com/voxer21582/OCR-dev/actions/runs/42531784209): 22 taxonomy + 239 application. [CodeQL run 42531783875](https://github.com/voxer21582/OCR-dev/actions/runs/42531783875) also succeeded. The optional factory, page-progress callback, catalog propagation and overflow diagnostics are included, with no default launcher activation. The required check and administrator protections remain enabled; force-push and deletion remain disabled.
- The integrated catalog and record contract preserve legacy 0.1.0 records and validate 0.2.0 embedded catalog snapshots, family references, field names and types. The [catalog manifest](../docs/application/document-family-catalog-manifest.md) and [record manifest](../docs/application/document-family-record-manifest.md) retain provenance, review and limits. The accepted pipeline connects the catalog to processing, semantic proposals and neutral required-field findings; UI/archive integration remains separate.
- The accepted progress prerequisite added an optional page-count callback to document processing. Three direct synthetic tests passed locally after two expected missing-keyword failures; the existing no-callback behavior already passed. Failure returns an unprocessed copy instead of publishing partial results. Independent review found missing timing coverage; the strengthened success test rejects early and delayed callbacks and verifies that invalid geometry emits no progress. Both local mutations failed as expected, and the restored production implementation passed all three cases. The public decoder default and legacy tests remain unchanged. See the [scoped manifest](../docs/application/document-processing-progress-manifest.md).
- Reproduction from `application/`: `PYTHONPATH=src:tests python -B -m unittest -v test_document_processing.DocumentProcessingProgressTests` (use `;` as the path separator on Windows). Only the three selected unittest cases ran; the four existing pytest-style free functions were not executed. Fake decoder/engine paths bypass all vendor and native decoders.
- Catalog propagation passed **137 explicitly selected synthetic tests locally**, including 19 new test methods and existing semantic, analysis, validation, record, catalog and callback regressions. These and the progress cases are included in the observed main run above. The [propagation manifest](../docs/application/catalog-pipeline-manifest.md) retains the exact local command, provenance and limitations.
- Accepted overflow diagnostics identify three limit causes while retaining failed semantic extraction. They do not implement partial extraction or bound all candidate accumulation; see the [diagnostic manifest](../docs/application/overflow-diagnostic-manifest.md).
- This separate candidate implements only the approved worker plan's explicit limits and bounded JSON framing. The final selected local run passed **11 synthetic tests**, after independent review identified and the implementation corrected pre-cap encoding allocations and missing boundary coverage. Final code review is READY. The [protocol manifest](../docs/application/bounded-ocr-protocol-manifest.md) records new authorship, the command and remaining responsibilities; no worker or process is started.

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

- The 11 new protocol tests are not yet selected by main CI. A separate reviewed allowlist addition is required; this product contribution does not change workflows or add discovery.
- The callback is a processor prerequisite, not a background-job implementation. No worker, UI, launcher, installer, production OCR runtime/model, real-document behavior or release is accepted here.
- Catalog findings remain warning/indeterminate and depend on observed family-title alternatives. A manually selected family without those alternatives is not covered by this required-field behavior. No automatic catalog migration, semantic confirmation, fiscal classification or administrative approval is introduced.
- Public migration remains selective; source ownership, privacy, licenses and scope require per-file review.

## Next steps

1. Review the new pure protocol contribution and its separate explicit CI proposal. Publication review and remote evidence are separate from the observed local result; merge requires owner approval.
2. Prepare worker supervision, catalog/source/result integrity and trusted caller integration separately. Native/runtime acceptance remains outside the protocol tests.
3. Preserve the original checkout and all R7/R8 stop/no-retry restrictions.
