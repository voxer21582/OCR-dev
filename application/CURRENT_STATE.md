# Document Intelligence current state

Updated: 2026-11-08

## Verified

- PRs [#48](https://github.com/voxer21582/OCR-dev/pull/48) and [#49](https://github.com/voxer21582/OCR-dev/pull/49) were squash-merged after explicit owner approval and refreshed successful checks. Public `main` is `68fea56e51606f4efb122c5738dada7180a81aae`. [Run 42522647362](https://github.com/voxer21582/OCR-dev/actions/runs/42522647362) passed **217 synthetic tests**: 22 taxonomy + 195 application. [CodeQL 42522647351](https://github.com/voxer21582/OCR-dev/actions/runs/42522647351) passed. The required check and administrator protections remain enabled; force-push and deletion remain disabled.
- The integrated catalog and record contract support legacy 0.1.0 records and 0.2.0 records with self-verifying custom-family snapshots. Selected family identifiers, field names and typed values are validated against those definitions. The [catalog manifest](../docs/application/document-family-catalog-manifest.md) and [record manifest](../docs/application/document-family-record-manifest.md) preserve source provenance, review and the local static-only JSON Schema validation limit. Pipeline, UI and archive integration are not implied.
- Optional-runtime-factory PR [#50](https://github.com/voxer21582/OCR-dev/pull/50) fixes the default RGB bridge while preserving injected `image_decoder` callbacks. Its separately reviewed CI PR [#51](https://github.com/voxer21582/OCR-dev/pull/51) adds seven direct factory tests to the explicit allowlist. On their earlier catalog-only base, [run 42522413273](https://github.com/voxer21582/OCR-dev/actions/runs/42522413273) passed **215 synthetic tests** (22 + 193). That historical result predates the new record-contract base.
- After bringing the approved `main` changes into the factory candidate and reconciling only this status document, the unchanged factory/RGB source and tests pass **205 local application tests** through the explicit 14-module allowlist. No installed OCR engine is invoked. The [factory manifest](../docs/application/optional-runtime-factory-manifest.md) records the original 19 targeted tests, RED/GREEN regressions, review and pending worker test. A new remote result for this combined candidate must be read separately; 205 is a local application count, not a claim about `main` or full product acceptance.
- Reproduction from `application/`: `PYTHONPATH=src:tests python -B -m unittest -q test_public_data_guard test_contract_baseline test_document_contract test_document_decoder_contract test_ingestion test_ocr_adapter test_semantic_proposals test_analysis_pipeline test_document_validation test_loopback_csrf test_manual_region_review test_rapidocr_adapter test_document_family_catalog test_rapidocr_runtime_factory` (use `;` as the path separator on Windows).

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

- PRs #50/#51 are not merged. The seven direct factory tests require the separate CI extension; the RGB tests are already in the selected adapter module. No worker, launcher or UI integration is included, and no runtime is enabled by this candidate.
- No Windows installer, production OCR runtime/model, real-document behavior, or release is accepted by this state record.
- Public migration remains selective; other source files require file-level provenance, privacy, license, and scope review.

## Next steps

1. Review the refreshed factory/RGB candidate and its separate CI allowlist proposal; their merges remain subject to owner approval. PRs #41/#43/#44/#46/#47/#48/#49 are already integrated.
2. Continue scoped worker dependencies, including optional page progress, then catalog propagation. Do not copy unreviewed or concurrent changes.
3. Preserve the original checkout and all R7/R8 stop/no-retry restrictions.
