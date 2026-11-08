# Document Intelligence current state

Updated: 2026-11-08

## Verified

- Public `main` at `86c9398905fb4baf4a54b58b303ddf8325c4e768` contains the initial selective application snapshot under `application/` (PR #38); it is not the full private checkout.
- The isolated branch `codex/ocr2-manual-review-rapidocr` is based on the explicit synthetic application test baseline from PR #41 (`64bd4f4444bfc8c6f9c2a0358b13f857961fbb8e`). It adds loopback mutation protection, human-authored source-region evidence for absent fields, and an optional RapidOCR adapter around an already configured engine.
- The explicit synthetic test command for this branch completed 142 tests successfully on 2026-11-08. It names `test_public_data_guard`, `test_contract_baseline`, `test_document_contract`, `test_document_decoder_contract`, `test_ingestion`, `test_ocr_adapter`, `test_semantic_proposals`, `test_analysis_pipeline`, `test_document_validation`, `test_loopback_csrf`, `test_manual_region_review`, and `test_rapidocr_adapter`.
- `py_compile` passed for the changed application modules/tests, and `git diff --check` passed.
- Manual region correction is bound to the source hash/page, does not run OCR, and does not write to the archive. R7/R8 were not touched.
- `rapidocr_adapter.py` is dependency-lazy and accepts an already configured engine; no RapidOCR package/model was installed or downloaded, and no production OCR result is claimed.

## Not verified

- The follow-up branch is local and has not yet run through GitHub Actions; the 142-test result is local evidence only.
- No Windows installer, production OCR runtime/model, real-document behavior, or release is accepted by this state record.
- Public migration remains selective; other source files require file-level provenance, privacy, license, and scope review.

## Next steps

1. Publish the product changes as a reviewable PR stacked on PR #41, then verify its exact diff and triggered checks.
2. Prepare a separate CI PR that adds only the three new synthetic test modules to the explicit allowlist; verify Actions before asking for integration.
3. Do not merge either PR without the owner's merge approval; continue the migration file by file without modifying the original checkout or resuming R7/R8 work.
