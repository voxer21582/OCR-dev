# Field candidate contract

This module represents structured values without performing extraction or human review. A `FieldCandidate` records its document type and field against the exact taxonomy schema version, catalog version, and SHA-256 binding. It holds one or more `CandidateAlternative` records, which keep literal OCR text segments separate from an optional opaque normalized string.

## Evidence references

Each `OCRObservationReference` identifies a source-document SHA-256, 1-based page, observation index, and normalized region. A candidate alternative stores `literal_segments` and evidence references as equal-length tuples; each segment exactly matches its indexed observation, retaining observation boundaries instead of guessing how separate snippets should be joined. `validate_field_candidate` checks the references against supplied page results. An unreadable candidate can instead identify a source region without claiming an OCR observation. Duplicate page identities are rejected as ambiguous.

## States

- `proposed`: exactly one value alternative.
- `uncertain`: one or more alternatives without selecting a confirmed value.
- `missing`: no value alternative and no region reference. This records an absence assertion; it does not prove that all pages were searched.
- `unreadable`: a source page region is identified, with no text alternative.
- `rejected`: rejected alternatives and their source evidence remain available; this record does not encode who rejected them or establish a human approval decision.

These are extraction-candidate states only. Human edits, actors, reasons, history, field-specific parsing, fiscal rules, confidence thresholds, and accepted values belong to separate product layers. `normalized_value` is an opaque string: this contract does not parse dates, decimal separators, amounts, or currency.

Only enabled document types and fields marked `built_in` in the exact validated taxonomy snapshot may be addressed by OCR candidates. Custom `manual_only` fields are rejected. The contract performs no OCR, extraction, file or network access, persistence, UI, or runtime selection; all public tests use synthetic values.

## Verification limits

The dedicated synthetic tests are added to GitHub Actions through a separate workflow PR. A passing contract test does not establish extraction accuracy on documents, runtime readiness under A4, review acceptance under R6, or full product acceptance.
