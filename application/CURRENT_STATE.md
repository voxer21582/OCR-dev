# Document Intelligence current state

Updated: 2026-11-09

## R6 custom-family review integration candidate (2026-11-09)

The isolated canonical candidate binds manual custom-family selections to the validated immutable definition already stored in the record. It extends the review-event schema with an optional family snapshot, embeds that snapshot in the hash-chained event, and exposes a custom family in the local UI only when both the snapshot is valid and the family is an observed OCR alternative with matching evidence. Built-in family handling remains unchanged. The record's extracted family and fiscal classification remain separate.

Local synthetic checks: `PYTHONPATH=application\\src;application\\tests python -B -m unittest -q test_document_contract test_review_ledger` passed 48 tests; a direct invocation of the custom-family UI regression also passed. The two new regressions were first observed failing for the missing schema property and the UI's built-in-only allowlist. The document schema parsed as JSON and `git diff --check` passed. `pytest` is absent in this interpreter and was not installed.

This is a migration candidate, not R6 acceptance: public CI has not yet run the new test module; independent review, archive reopen/migration behavior, browser-level verification, and owner-approved merge remain pending. No real documents, OCR activation, R7/R8, Windows-native tests, or release are included.

## Accepted manual handoff correction (2026-11-09)

The accepted implementation retains the latest replacement review event per allowed field before selecting observed, non-null values. This prevents a superseded observed value from appearing after a non-observed correction. Local synthetic verification passed 9 targeted tests and 15 review-ledger tests; the initial 9-test regression produced 8 expected failures. The pre-existing pytest handoff tests were not run because pytest is absent from the specified interpreter. See the [manual handoff manifest](../docs/application/manual-handoff-latest-manifest.md) for commands, provenance and limits.

The allowlist and a `flagged` event do not constitute approval. A blocked review remains blocked, but the prompt does not necessarily display that state. No API call is made. PRs #61/#62 were merged by owner approval; main `e5cc34232702a164e24e0a6e4e2e959d43b29c63` passed 270 synthetic tests in [run 42536807942](https://github.com/voxer21582/OCR-dev/actions/runs/42536807942). No R7/R8 work is claimed.

## Verified

- This isolated TIFF-inventory candidate follows Classic TIFF directories beyond the initial prefix within a cumulative per-document metadata-read budget. It preserves upload/archive bounds and rejects duplicate dimension tags. The explicit synthetic regression run passed 43 tests after security-review additions; the [TIFF manifest](../docs/application/tiff-sparse-metadata-manifest.md) records memory changes, evidence and limits. No native TIFF decoder, browser or real document was used, and raster decoding is not verified.

- Accepted PRs #63/#64 correct context-dependent tax arithmetic using exact integer cents. Canonical amount strings longer than 128 characters intentionally produce the existing warning/indeterminate finding; the limit applies to the calculation, not the full input or evidence. Ten selected synthetic tests passed locally, with RED and the reproduction command recorded in the [exact arithmetic manifest](../docs/application/exact-tax-arithmetic-manifest.md). The refreshed PR run [42537191088](https://github.com/voxer21582/OCR-dev/actions/runs/42537191088) passed 276 synthetic tests before owner-approved integration. Evidence and input remain preserved; no fiscal or payment approval is implied.

- This separate candidate displays a fixed warning when semantic extraction failed. Known overflow codes receive a generic limit explanation; unknown codes are not reflected. Five selected synthetic tests passed locally. The [warning manifest](../docs/application/semantic-failure-warning-manifest.md) records scope and limitations: no browser, CSS visibility or accessibility verification is claimed.

- This isolated candidate distinguishes three proposal overflow causes with fixed non-sensitive error codes and retains failed semantic extraction without returning new partial proposals. The explicit local synthetic regression command passed 84 tests; see the scoped diagnostic manifest. This is diagnostic preparation, not partial extraction, bounded accumulation, UI acceptance or an operational release.

- Earlier main `0b486a40434b793f295b4e08b689f0d5de238b74` passed **230 synthetic tests** in [run 42527883161](https://github.com/voxer21582/OCR-dev/actions/runs/42527883161). The optional factory, explicit RGB bridge and page-progress callback are included, with no default launcher activation. See the [factory manifest](../docs/application/optional-runtime-factory-manifest.md) for source review, synthetic scope and pending worker integration.
- The integrated catalog and record contract preserve legacy 0.1.0 records and validate 0.2.0 embedded catalog snapshots, family references, field names and types. The [catalog manifest](../docs/application/document-family-catalog-manifest.md) and [record manifest](../docs/application/document-family-record-manifest.md) retain provenance, review and limits. This candidate connects the catalog to processing, semantic proposals and neutral required-field findings; UI/archive integration remains separate.
- The accepted progress prerequisite added an optional page-count callback to document processing. Three direct synthetic tests passed locally after two expected missing-keyword failures; the existing no-callback behavior already passed. Failure returns an unprocessed copy instead of publishing partial results. Independent review found missing timing coverage; the strengthened success test rejects early and delayed callbacks and verifies that invalid geometry emits no progress. Both local mutations failed as expected, and the restored production implementation passed all three cases. The public decoder default and legacy tests remain unchanged. See the [scoped manifest](../docs/application/document-processing-progress-manifest.md).
- Reproduction from `application/`: `PYTHONPATH=src:tests python -B -m unittest -v test_document_processing.DocumentProcessingProgressTests` (use `;` as the path separator on Windows). Only the three selected unittest cases ran; the four existing pytest-style free functions were not executed. Fake decoder/engine paths bypass all vendor and native decoders.
- Catalog propagation passed **137 explicitly selected synthetic tests locally**, including 19 new test methods and existing semantic, analysis, validation, record, catalog and callback regressions. Independent read-only technical review is READY on the final files and retained output. Its separate CI PR #55 passed **246 synthetic tests** on the earlier base in [run 42526849307](https://github.com/voxer21582/OCR-dev/actions/runs/42526849307), excluding the then-pending three progress cases. Reconciliation retains both sets of selectors and requires a fresh remote run; counts from different branches are not combined as evidence. The [propagation manifest](../docs/application/catalog-pipeline-manifest.md) gives the exact command, source pins, publication scope and limitations.

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

- The catalog tests remain proposed by the separate CI PR #55. This product contribution preserves the main progress selector; it does not add test discovery.
- The callback is a processor prerequisite, not a background-job implementation. No worker, UI, launcher, installer, production OCR runtime/model, real-document behavior or release is accepted here.
- Catalog findings remain warning/indeterminate and depend on observed family-title alternatives. A manually selected family without those alternatives is not covered by this required-field behavior. No automatic catalog migration, semantic confirmation, fiscal classification or administrative approval is introduced.
- Public migration remains selective; source ownership, privacy, licenses and scope require per-file review.

## Next steps

1. Reconcile PR #54 and CI PR #55 with the accepted main, preserving all reviewed source/test files and both explicit selector sets. The owner approved the conditional merge sequence; merge only after the refreshed checks pass.
2. Continue bounded worker-protocol preparation independently; no background worker is included here and native/runtime acceptance remains separate.
3. Preserve the original checkout and all R7/R8 stop/no-retry restrictions.
