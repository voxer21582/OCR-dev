# R5 Structural Validation Design

## Intent

Turn taxonomy-bound R4 candidates into a deterministic, content-free report of structural gaps. This makes missing, uncertain, unreadable, rejected, conflicting, and required fields visible while preserving the distinction between machine checks and human/business decisions.

## Goals and acceptance

- Validate a selected enabled built-in document type and every supplied R4 candidate against the same taxonomy binding and page results.
- Produce immutable, deterministic field-state entries and findings containing only stable rule codes and taxonomy field identifiers.
- Report required fields without a candidate, and preserve distinct findings for `missing`, `uncertain`, `unreadable`, `rejected`, and duplicate candidates.
- Preserve the exact taxonomy schema version, catalog version, and hash in each report.
- Never modify candidates or infer a field value.

## Non-goals

- No parsing or validation of date, amount, currency, percentage, identifier, tax, POS, or accounting semantics.
- No confidence threshold, ranking, severity score, human review state/history, UI, persistence, OCR engine, runtime, or real-document evaluation.
- No R7/R8/issue #8, Windows configuration, or Google deployment.

## Constraints

- Use the existing validated taxonomy binding and R4 candidate APIs; no new dependency.
- Required means only the `required` flag in the exact taxonomy snapshot. A report with no findings means structural completeness for this selected taxonomy type only, not correctness, fiscal validity, or human acceptance.
- Findings contain no OCR text, source paths, exception text, or document content.
- Public tests use only synthetic taxonomy records, candidate values, and page observations.

## Approaches considered

1. **Add date/money/fiscal rules in the validator.** Rejected because locale and policy thresholds are not approved and belong to distinct interpretation layers.
2. **Return a boolean valid/invalid flag.** Rejected because it would collapse uncertainty, absence, and review decisions into one misleading outcome.
3. **Return immutable field states and rule-coded findings.** Chosen because it gives the UI and later validation layers useful, deterministic evidence without accepting values or changing product policy.

## Technical choices

- `validate_document_fields(binding, type_id, candidates, page_results)` takes the selected document family explicitly; it does not classify a document.
- Finding codes are stable and non-sensitive: `required_field_missing`, `field_missing`, `field_uncertain`, `field_unreadable`, `field_rejected`, and `field_candidate_conflict`.
- Required non-proposed values can produce both their state-specific finding and `required_field_missing`.
- Field entries and findings are sorted by field identifier and code, independent of candidate input order.
- Invalid binding/candidate inputs raise one sanitized `ValidationContractError`; they do not return partial reports.

## Open for later design

Field-specific parsing, cross-field consistency, confidence policy, fiscal interpretation, severity/priority, human review, and stale-candidate handling remain separate layers requiring their own acceptance criteria.
