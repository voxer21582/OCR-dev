# OCR Analysis Coordinator

## Scope

`analysis_pipeline.py` coordinates already produced `OCRPageResult` values with the semantic proposal and deterministic document-validation layers. It is an in-memory application service, not an OCR engine, file decoder, malware scanner, uploader, storage layer, or authorization system.

An upload adapter can pass a non-seekable request body and its client filename to `inventory_stream`; the upload is size-bounded and staged only in a per-call in-memory snapshot before hash/inventory checks. This API does not itself provide authentication, durable private storage, malware scanning, or network-server protections.

The caller must supply a structurally valid document record whose ingestion and OCR stages are completed. In the selected local scope, antivirus scanning is not required. All OCR page results must bind to that record's SHA-256 and cover its inventoried page numbers exactly. The coordinator reads no source file and makes no network or storage calls.

## Output behavior

- Returns a copied document record; the input object is not mutated.
- Adds generated fields only when the field name is not already present.
- Returns colliding proposals separately in `unapplied_proposals`; it never replaces or silently combines an existing field.
- Keeps proposals uncertain and preserves source/page/token/region evidence and alternatives.
- `document_number` is proposed only when an Italian or English invoice/document-number label and a single identifier occur in the same OCR token; the observed identifier is preserved without invented normalization.
- `vat_registration_number` requires an explicit Italian `P.IVA`/`Partita IVA` or English `VAT ID`/`VAT number` label and exactly 11 digits in one token. It remains uncertain and evidence-bound; it does not establish checksum or fiscal validity.
- `document_family_candidates` recognizes only explicit same-token title cues for the scoped families. It remains uncertain and does not populate the top-level document family or fiscal-document status; POS payment evidence stays distinct from fiscal receipt cues.
- `bill_to_name` and `sold_to_name` are separate uncertain proposals from matching explicit English role labels and values in one OCR token. Generic `Cliente`/`Customer`, `Destinatario`, payment recipient, and unlabelled names are not mapped to those roles; no buyer identity is merged with merchant or supplier.
- `tip_amount` requires an explicit same-token tip/gratuity label at the token start and stays separate from `payment_amount` and `total_amount`; it remains uncertain and evidence-bound.
- `payment_reference` requires an explicit same-token transaction/payment-reference label and preserves the identifier as an uncertain candidate. Generic references, authorization codes, and invoice numbers are not mapped to it.
- `payment_amount` is proposed only from explicit same-token paid-amount labels and stays distinct from `total_amount` and amounts due. `payment_method` requires an explicit cue at the token start plus a controlled same-token value (cash, card, bank transfer, or cheque); generic payment/POS wording, authorization codes, and payee names do not produce these candidates. Both remain uncertain and evidence-bound.
- Runs cross-record contract checks and document consistency rules, then records the findings and completed semantic/document-validation stage statuses on the copied record. The arithmetic-only taxable-base + VAT amount = total rule applies to invoice, fiscal receipt, and hotel documents when all three fields are present. It passes only on exact addition of observed canonical decimal strings; differences, uncertain values, and malformed amounts are indeterminate review signals, never fiscal failure findings.
- A validation finding describes a document relation. It does not confirm a field, establish fiscal correctness, or approve payment/accounting.

## Operational boundary

This coordinator does not itself prove that the required ingestion, malware scan, decoding, OCR, private-location, or authorization controls actually ran. Production callers must enforce those upstream controls and persist records only in an approved private system. No real company document is included in the tests.

## Verification

Synthetic unit tests cover stage prerequisites, source/page binding, full inventoried page coverage, non-mutation, existing-field collision preservation, and hotel-date validation with uncertain proposals. The full repository CI remains the supported-runtime check.


## Optional browser processor path

PR #70 added `document_processing.py` to verify that materialized source bytes match their SHA-256, decode each page under configured limits, adapt OCR results through the contract, update source-bound page metadata, and run uncertain semantic proposals plus deterministic document checks. Any failure discards partial proposals and uses a non-sensitive stage error code. `create_expense_report_app` and `serve_expense_report_local` accept an optional `document_processor(record, source_bytes)` callback; when supplied, it runs for the selected expense note and every attachment during explicit assignment. The callback must return a contract-valid record preserving document ID and source hash. With no callback, OCR remains `not_started`.

Authorized run [#18](https://github.com/voxer21582/alfa-document-intelligence/actions/runs/38657765160) exercised the complete generated-PDF WSGI flow with the temporary Paddle runtime and produced seven-page source-bound review. This is synthetic-only. The project declares no OCR/PDF runtime dependencies, no model is bundled, and the default app stays disabled until dependency, license, native decoder isolation, and packaging review are complete.
