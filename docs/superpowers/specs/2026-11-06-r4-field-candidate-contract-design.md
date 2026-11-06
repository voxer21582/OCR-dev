# R4 Field Candidate Contract Design

## Intent

Represent structured values proposed from OCR without turning a text observation into a confirmed business value. Each candidate is tied to the exact taxonomy snapshot and to synthetic, page-level OCR evidence so later extraction and review layers can preserve alternatives and uncertainty.

## Goals and acceptance

- Immutable values represent a field candidate, one or more candidate alternatives, and references to OCR observations.
- Each observation reference carries the source SHA-256, 1-based page, normalized region, and observation index; validation checks it against supplied `PageOCRResult` values.
- A candidate identifies its document type and field and is bound to a validated taxonomy snapshot by schema version, version number, and SHA-256.
- Literal observed text remains separate from an opaque normalized string. This layer applies no locale, date, amount, currency, or fiscal interpretation.
- Distinct states represent proposed, uncertain, missing, unreadable, and rejected values. These states never mean human confirmation; human decisions and history remain R6.
- Taxonomy and provenance failures return stable, sanitized errors.
- Tests use synthetic taxonomy snapshots, page results, observations, and values only.

## Non-goals

- No extraction algorithm, OCR engine/model, normalization policy, confidence threshold, fiscal rule, UI, persistence, real document, or Windows/runtime test.
- No change to taxonomy schemas or R7/R8/issue #8.
- No acceptance of R4 accuracy on real documents, A4, A5, or the complete product.

## Constraints

- Use the existing `PageProvenance`, `TextRegion`, `PageOCRResult`, and taxonomy binding APIs from the reviewed R2 base.
- Only fields present in the supplied validated snapshot may be addressed; `manual_only` fields must not be represented as OCR-derived proposals.
- Each `literal_segments` entry is an exact synthetic OCR observation string. `normalized_value` remains `str | None` and is opaque.
- Missing candidates carry no value/evidence; unreadable candidates may carry page-region evidence without an OCR observation; rejected candidates retain the rejected alternative and evidence but do not encode who rejected it.
- A caller supplies the page-result set used to validate references. This contract does not assert that those results cover every document page.

## Approaches considered

1. **Add extraction algorithms or a selected model now.** Rejected: A4 has not accepted a runtime/model and synthetic contract work cannot establish extraction accuracy.
2. **Store free-form dictionaries.** Rejected: it would allow values to drift from the taxonomy version and lose typed status/provenance invariants.
3. **Add a small immutable candidate contract over existing R2 and taxonomy bindings.** Chosen: it advances a core product boundary with synthetic evidence and remains compatible with future engine and review choices.

## Technical choices

- One `FieldCandidate` contains a tuple of `CandidateAlternative` records; each alternative stores `literal_segments: tuple[str, ...]`, optional opaque normalized text, and an equal-length tuple of `OCRObservationReference` records. Each segment must match its indexed observation exactly, preserving boundaries without guessing how multiple observations should be joined.
- An unreadable candidate carries a `SourceRegionReference` tied to a page provenance, but no OCR observation index or text.
- Candidate state validation is structural only. The contract does not set review/approval state or infer that a missing state is a complete search result.
- `validate_field_candidate(candidate, binding, page_results)` validates the taxonomy binding, checks the candidate's embedded taxonomy identity, confirms the type/field exists and is eligible for OCR proposals, and matches each observation reference to the exact indexed result observation.

## Open for later design

Locale-aware normalization, field-specific parsing, confidence calibration, model provenance, candidate ranking, adjudication and human-edit history remain separate follow-on decisions. Runtime use remains disabled until A4 and any other applicable authorization is complete.
