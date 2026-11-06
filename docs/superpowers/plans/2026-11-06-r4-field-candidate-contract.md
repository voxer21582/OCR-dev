# R4 Field Candidate Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a synthetic-testable, taxonomy-bound contract for structured field candidates with evidence references and explicit uncertainty states.

**Architecture:** Add frozen standard-library dataclasses in a new extraction contract module. Validate taxonomy identity against `validate_taxonomy_binding` and observation references against the supplied R2 page results. Do not introduce extraction, persistence, UI, or runtime behavior.

**Tech Stack:** Python 3.13, standard library, `unittest`; existing JSON Schema dependency through taxonomy validation.

**Spec:** `docs/superpowers/specs/2026-11-06-r4-field-candidate-contract-design.md`

## Global Constraints

- Use synthetic fixtures only; no real document/OCR text, personal data, credentials, or derived sensitive values.
- Preserve source hash, page, and region evidence and the exact taxonomy schema/version/hash.
- Do not implement OCR, extraction algorithms, locale normalization, fiscal interpretation, review UI/history, persistence, or Windows runtime behavior.
- Do not touch R7/R8, issue #8, Windows/Google configuration, or original OCR projects.
- Do not add dependencies or modify CI in the feature PR; CI expansion is a separate PR with explicit test modules only.
- No merge. The feature PR is stacked on the reviewed R2/CI branch until its base is integrated.

## Review Focus

- A candidate referencing a missing or manual-only taxonomy field must fail: test with unknown and custom manual-only fields.
- A reference to a different source/page, observation index, or region must fail: test each mismatch against synthetic `PageOCRResult` inputs.
- Missing, unreadable, rejected, uncertain, and proposed states must remain distinct: test their allowed value/evidence shapes and reject contradictory shapes.
- Taxonomy snapshot version/hash mismatch must fail without exposing catalog content: test modified identity and invalid binding.
- Frozen candidate and nested tuples must not be mutable: test assignment and input collection behavior.

---

### Task 1: Define the candidate contract

**Files:**
- Create: `src/alfa_document_intelligence/extraction_contracts.py`
- Test: `tests/test_extraction_contracts.py`
- Modify: `docs/ocr/field-candidate-contract.md`
- Modify: `README.md`
- Create: `docs/agent-work/issue-28-publication-manifest.md`

**Interfaces:**
- `SourceRegionReference(provenance: PageProvenance, region: TextRegion)`
- `OCRObservationReference(provenance: PageProvenance, observation_index: int, region: TextRegion)`
- `CandidateState`: `PROPOSED`, `UNCERTAIN`, `MISSING`, `UNREADABLE`, `REJECTED`
- `CandidateAlternative(literal_segments: tuple[str, ...], normalized_value: str | None, evidence: tuple[OCRObservationReference, ...])`; literal segments and evidence references have equal length and are matched in order.
- `FieldCandidate(taxonomy_schema_version: str, taxonomy_version: int, taxonomy_sha256: str, type_id: str, field_id: str, state: CandidateState, alternatives: tuple[CandidateAlternative, ...], unreadable_region: SourceRegionReference | None = None)`
- `ExtractionContractError.code` exposes only stable non-sensitive codes.
- `validate_field_candidate(candidate, binding, page_results) -> FieldCandidate` returns the same validated candidate or raises `ExtractionContractError`.

- [x] Write synthetic tests for one proposed value, alternatives/uncertainty, missing, unreadable, rejected, taxonomy field lookup, manual-only rejection, exact provenance/index/region validation, malformed identities, status-shape invariants, and immutability.
- [x] Run `PYTHONPATH=src;tests python -B -m unittest -v test_extraction_contracts` and confirm the expected import failure before production implementation.
- [x] Implement the frozen records and validator with stable errors; keep normalization opaque and contain no file/network/runtime access.
- [ ] Run `PYTHONPATH=src;tests python -B -m unittest -v test_extraction_contracts` and the explicit existing allowlist `test_taxonomy_registry test_taxonomy_binding test_ocr_contracts`.
- [ ] Review the complete diff for privacy, provenance, validation, prohibited paths, and unnecessary dependencies.
- [x] Update public API documentation and a manifest with candidate file hashes, owner/provenance, review status, evidence, and exclusions.
- [ ] Commit and prepare a feature PR linked to issue #28; keep issue open while its separate CI PR is pending.

### Task 2: Extend CI separately

**Files:**
- Separate branch/PR: modify only `.github/workflows/ocr2-synthetic-taxonomy.yml`, README test command/count, and a CI manifest.

- [ ] Add exactly `test_extraction_contracts` to the explicit allowlist; do not use discovery or globs.
- [ ] Preserve the required check, triggers, SHA-pinned actions, hash-locked dependencies, read-only permissions, and standard Ubuntu runner.
- [ ] Verify push and pull-request Actions both report the exact test count; document that the result covers synthetic contracts only.

## Self-review

- Every field-candidate acceptance item has tests in Task 1; R4 accuracy labels and real-document evaluation are deferred because A5/A4 do not authorize them.
- Task boundaries separate product contract from workflow governance; no CI change occurs in the feature PR.
- Types remain tied to existing R2 and taxonomy-binding interfaces; code/tests must verify exact indexed observation identity.
- The five failure classes are covered by named synthetic test groups in Task 1.
