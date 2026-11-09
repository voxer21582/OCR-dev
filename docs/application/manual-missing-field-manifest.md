# Manual review of missing fields — scoped manifest

Date: 2026-11-09. Base: public main `7486989d556503fa07c66ccce52bc13a5be4effd`. This change was developed in an isolated worktree for OCR2 and does not reuse artifacts from the prior OCR project.

## Scope

- `application/src/alfa_document_intelligence/local_intake_app.py`: allow a reviewer to transcribe selected built-in fields that were not proposed, with human region evidence. A bounded, volatile record of page previews is checked before a new region correction. The original extracted fields remain unchanged.
- `application/tests/test_manual_missing_field.py`: invented records and in-memory requests test missing fields, rejected input, review event preservation and preview gate.
- `application/tests/test_manual_region_review.py`: the existing in-memory test now requests a mocked preview before submitting its region.

The preview gate requires the same session, document identifier, source hash and page; it stores at most 128 keys. It proves that the server produced a preview, not that it reached the browser or that a person inspected it. Evicted entries require another preview request. The existing server maintains one volatile session and does not distinguish browser identities. Manually adding custom-family fields is not included; special fiscal and family classification remain separately handled.

## Evidence and limitations

Synthetic local test run from `application/` with the pre-existing Python environment and `PYTHONPATH=src;tests` on Windows: `python -B -m unittest -v test_manual_missing_field test_manual_region_review.ManualRegionEvidenceTests`: 20 passed. The tests for the new preview gate mock image generation; no native decoder or browser was exercised. Static independent review returned READY for the scoped diff, with these limitations. Separate publication review found no real documents or credentials in the change.

No new dependency, model, native test, actual OCR, archive migration or R7/R8 operation is included. Reset/timeout, archive reopen and actual browser rendering of this feature are not verified by the new tests. This evidence is not product acceptance. CI remains separately scoped and no merge is implied.
