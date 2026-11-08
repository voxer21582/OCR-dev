# Manual Annotation Guide

Status: draft protocol. Applies to labeled benchmark records; it does not grant authorization to access company documents. Do not put real documents, source text, OCR text, names, or label-to-identity mappings in this repository or CI. Use only synthetic material until the data boundary, authorized annotators, retention rules, fiscal owner, and frozen-set custodian are approved.

## 1. Annotation unit and provenance

- One case is one logical submitted document; preserve original page order and keep each file in the same case.
- Assign opaque case IDs. Keep source hashes and source-to-case mappings in the approved protected registry, not in Git.
- Record dataset version, label version, annotator pseudonymous ID, annotation timestamp, adjudication status, and the schema/normalization guide version in the authorized labeling system.
- Annotators work from original document pixels/pages. Do not derive gold values from OCR output, invoice templates, employee claims, bank data, or expected accounting treatment.
- Keep document-family and language coverage balanced across invoice, fiscal receipt, parking receipt, hotel document, Italian, English, mixed, and unknown cases as the authorized corpus permits.
- Mark the split before annotation. Development may inform iteration; regression is stable and change-controlled; the independent frozen split stays with its custodian and is not exposed during tuning.

## 2. Field-level labels

For every in-scope field record a status, value or null, zero or more alternatives, exact source evidence reference(s), and an adjudication note when needed.

- `observed`: the value is legible and directly supported by the source. Capture literal text and page/region before normalization.
- `uncertain`: more than one plausible reading remains. Preserve the alternatives and evidence; do not force a single gold value.
- `unreadable`: the field appears present but cannot be read reliably.
- `absent`: inspected relevant pages contain no evidence for the field.
- `not_applicable`: the field does not apply to this document/family.
- `rejected`: a visible candidate was considered and rejected with an adjudication rationale; do not use for ordinary absence.

A confirmed system value is scored correct only against adjudicated `observed` gold. Uncertain/unreadable/absent/not-applicable values are not converted into guessed gold values. Preserve multiple plausible values as alternatives instead of choosing one silently.

## 3. Evidence capture and normalization

- Evidence refers to the original source hash and a 1-based page number. When possible, draw a normalized polygon in page coordinates within [0,1] and preserve the exact literal. Text offsets or OCR token IDs may supplement, not replace, page-bound source evidence.
- Capture all evidence needed to support roles and values, not just the closest numeric string. Record evidence references separately for each field.
- Dates normalize to ISO `YYYY-MM-DD` only when day/month/year are unambiguous. Preserve the printed literal. Do not infer service, stay, issue, or payment dates from context without direct support.
- Money uses decimal strings with a period and no grouping separator after normalization. Preserve the original literal and distinguish subtotal, taxable base, tax amount, total, tip, paid amount, and currency.
- Record currency from visible evidence. Do not silently fill EUR from project defaults where the document does not establish it; retain missing/uncertain status.
- VAT rates, tax bases, and VAT amounts are independent observations. Do not calculate a missing field to make totals reconcile. Record multiple rates/lines separately when the schema supports them.
- Normalize names conservatively. Preserve legal name and trade name as alternatives or separate fields only when each is supported.

## 4. Fiscal-document and payment evidence

Annotate document evidence class as `fiscal_document_evidence`, `payment_only_evidence`, or `unknown`, with the visible evidence and rationale. This is a description of the document presented, not a legal opinion that it satisfies tax requirements.

A POS slip/card receipt is payment evidence. It does not by itself establish a fiscal invoice or receipt. Do not use a payment recipient as issuer/supplier, or infer the employee as payer unless the document identifies them. Keep merchant/supplier, customer, tax-ID owner, payment recipient, payer, and cardholder roles distinct. Ambiguous role assignment remains uncertain and goes to adjudication.

## 5. Double review and adjudication

- Two annotators independently label critical fields: fiscal/document class, issuer/supplier/customer/payment roles, issue date, total, currency, tax identifiers, taxable base, VAT rates/amounts, and payment amount.
- Compare normalized labels and evidence references only after independent work is saved. A designated adjudicator resolves differences using the original source and records the reason and final evidence.
- Track initial agreement, adjudicated disagreement rate, unresolved fields, and evidence disagreement by field/family. Keep both original annotations in the controlled system.
- If a document is illegible or its meaning cannot be resolved from source evidence, adjudicate as uncertain/unreadable rather than consulting an expected value from another business system.

## 6. Frozen split controls

An authorized custodian assigns and retains the independent frozen set. Use keyed opaque group hashes for merchant/template/source/time grouping; keep HMAC keys and mapping tables outside the repository. Validate no source hash or group key crosses splits. Pin the canonical frozen manifest digest at the agreed release checkpoint. The evaluator and digest do not replace access controls, custody, legal authorization, or a planned evaluation schedule.

## 7. Required acceptance before real-data labeling

Record approvals for the processing environment and data owner, annotator access, purpose/minimization, retention/deletion, permitted derived artifacts, labeling/adjudication owner, fiscal-rule owner, and frozen-set custodian. Until that approval is recorded, use synthetic fixtures only.
