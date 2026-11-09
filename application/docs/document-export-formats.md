# Local document export formats

This module provides local serialization for a validated document record. It
does not write files, open source documents, or transmit data. The calling UI is
responsible for presenting an explicit save action and a destination.

## JSON record export

`export_document_json(record)` returns the complete record in its existing
schema-defined shape (`0.1.0`) as deterministic UTF-8-compatible JSON text.
It retains candidate values, uncertainty, alternatives, validation and review
state, and evidence references including source SHA-256 and page or region
information. Source file bytes are never included; the schema's `storage_ref`
remains an opaque local reference and is not converted into a path or URL. The
JSON text is a record export, not a self-contained document backup; it cannot
reopen the original source by itself.

## CSV field projection

`export_document_csv(record)` returns one row per field candidate, or one
document-identity row when no field candidates exist. Columns include the
`ocr2-document-csv-v1` format marker, document and schema identity, family,
source SHA-256, source filename as JSON, field name, and the complete candidate
object as JSON. Candidate JSON retains the value, status, alternatives,
normalization, and evidence as one parseable cell. This is an analysis view, not
a round-trip representation of every document-level property; use JSON when
complete record round-tripping is needed.

Free-text values are JSON-encoded within CSV cells rather than emitted as raw
cell contents. Candidate cells begin with a JSON object marker (`{`); a literal
such as `=...` remains inside a JSON string value rather than at the start of
the cell as a spreadsheet formula. Consumers should parse the JSON columns
instead of treating them as display-ready plain text.

## Reviewed CSV projection candidate

`export_reviewed_document_csv(record)` is a separate `ocr2-reviewed-csv-v1` projection. It verifies the review ledger and includes extracted and effective candidate JSON side by side, review status, source hash, and extracted/effective family and fiscal-state information. Missing counterparts are JSON `null`; unchanged effective values are not thereby human-confirmed. The JSON record remains the complete audit representation. This function does not change CSV v1 and is not connected to a UI in this candidate. Spreadsheet import may reinterpret text and must be configured carefully.

## Privacy and validation

All three functions check the repository's cross-record invariants and the presence
of the top-level required properties, raising `ExportValidationError` when
those checks fail. They do not independently execute the JSON Schema validator;
callers remain responsible for structural schema validation before exporting.
Exports can contain sensitive document metadata, OCR literals, and review
details. Keep them in approved local storage; do not upload them to public CI,
repositories, cloud OCR, or external services. These serializers do not provide
encryption, access control, or secure deletion.

## Availability

The serializers are currently a local Python capability only. They are not
connected to a browser UI, save dialog, archive selection flow, or import path.
No user-facing export operation is available until that integration is
implemented and verified.
