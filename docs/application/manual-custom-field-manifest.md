# Source-bound custom-field review — scoped manifest

Date: 2026-11-09. This isolated candidate is based on product branch `codex/manual-missing-field` at `af48c6a6b2d1433166701852132dad8b2164de4b`, proposed in PR #69. The code is new OCR2 work; no code or artifact from the prior OCR project was imported.

## Scope

A reviewer can add or correct a custom field declared in the validated immutable family snapshots embedded in the document. Review candidate validation uses the record's schema version and snapshots; the source extraction remains unchanged. Custom date and amount values must follow their declared canonical formats. If a region correction has an invalid typed value, the server returns a form with escaped submitted values and an Italian format hint without recording the correction. The client script reconstructs the selection and review timer on that response.

Files: `application/src/alfa_document_intelligence/local_intake_app.py`, `application/src/alfa_document_intelligence/review_ledger.py`, and the new synthetic tests `application/tests/test_manual_custom_field.py` and `application/tests/test_manual_custom_form_error.py`. State documentation is updated separately. No live catalog is used to define a stored document's fields.

## Evidence and limitations

From `application/` with `PYTHONPATH=src;tests` on Windows and the existing Python environment, `python -B -m unittest test_manual_custom_form_error test_manual_custom_field test_manual_missing_field test_manual_region_review.ManualRegionEvidenceTests test_review_ledger.ReviewLedgerTests test_document_contract` passed 70 synthetic tests. New WSGI tests mock preview generation. Independent static review was READY following corrections; it did not execute tests.

The tests inspect returned HTML and script presence but do not execute JavaScript, verify actual browser display, timing, native decoding or human observation. Archive reopening and real documents were not tested. Existing required-field findings describe extracted data and are not recomputed from the human review overlay. No new dependency, model, R7/R8 work, release or full-product acceptance is implied. This candidate depends on PR #69 and its CI extension #70; no merge is implied.
