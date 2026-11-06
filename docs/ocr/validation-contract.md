# Structural validation contract

`validate_document_fields` produces a deterministic report for one selected,
enabled built-in document type and one exact taxonomy binding. It validates
each supplied `FieldCandidate` with the R4 contract before reporting its state.

The report includes the taxonomy schema version, catalog version, and digest;
an entry for each built-in extraction field; and content-free findings. It
reports required fields that do not have exactly one proposed candidate,
state-specific findings for missing, uncertain, unreadable, and rejected
candidates, and a conflict when multiple candidates address the same field.
Duplicate candidate states remain visible in the report. Output fields and
findings have stable ordering independent of the input order.

A proposed candidate means only that one candidate is structurally present.
It does not mean that its value is correct, accepted, reviewed, or suitable
for accounting. A report without findings means only structural completeness
for this taxonomy snapshot and document type. It does not validate date, amount,
currency, identifier, tax, POS, or cross-field semantics.

The report and its nested records are immutable and contain no candidate text,
source paths, OCR payloads, or raw exception messages. Candidate and page-result
inputs are not modified. Unknown, disabled, `unknown`, and manual-only document
types are not eligible. The module performs no classification, OCR, persistence,
file or network access, UI, or runtime selection.

The dedicated public tests use synthetic taxonomy records and candidate values.
They are integrated into GitHub Actions by a separate CI change; a passing
contract check does not establish application-level acceptance or OCR quality.
