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

## Privacy and validation

Both functions check the repository's cross-record invariants and the presence
of the top-level required properties, raising `ExportValidationError` when
those checks fail. They do not independently execute the JSON Schema validator;
callers remain responsible for structural schema validation before exporting.
Exports can contain sensitive document metadata, OCR literals, and review
details. Keep them in approved local storage; do not upload them to public CI,
repositories, cloud OCR, or external services. These serializers do not provide
encryption, access control, or secure deletion.

## Availability

The local archive UI exposes explicit JSON and CSV download links for archived
records. The request handler retrieves the selected record from the configured
`LocalDocumentStore`, serializes it with the functions above, and returns it as
a download; it does not export an unarchived volatile session. The UI also
states that JSON contains the complete record while CSV is a tabular projection
and neither includes the original source bytes.

This integration is visible in
`src/alfa_document_intelligence/local_intake_app.py` in
`_archive_list_page`, `_archive_document_page`, and the
`GET /archive/export/{id}.{json|csv}` handler. The focused synthetic coverage
is in `tests/test_local_document_archive_ui.py::LocalDocumentArchiveUITests.test_archive_list_open_and_json_csv_exports_keep_evidence`.
On 2026-11-11, the complete focused module passed locally with:
```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -p test_local_document_archive_ui.py -v
```
The run reported 8 passing tests. This module remains outside the hosted CI
allowlist. The local unittest result does not verify a browser download on
Windows or user acceptance. On Windows, the test setup instantiated
`LocalDocumentStore` in ordinary temporary directories and therefore exercised
its fixed-drive and reparse-path validation. It created no junctions and did
not run the dedicated R7 probe; this result is not R7 acceptance evidence or
authorization to repeat that probe.
