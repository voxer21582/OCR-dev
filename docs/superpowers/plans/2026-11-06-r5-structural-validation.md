# R5 Structural Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report structural gaps in R4 field candidates against one versioned taxonomy snapshot without parsing or accepting field values.

**Architecture:** Add frozen report/finding records and a pure validator using the taxonomy binding and R4 candidate APIs. Keep field states and rule codes explicit and output ordering deterministic.

**Tech Stack:** Python 3.13, standard library, `unittest`; existing JSON Schema dependency through taxonomy validation.

**Spec:** `docs/superpowers/specs/2026-11-06-r5-structural-validation-design.md`

## Global Constraints

- Use only synthetic taxonomies, values, and page results.
- Preserve taxonomy schema/version/hash; do not parse locale-sensitive values or infer fiscal meaning.
- Do not implement OCR, human approval, UI, persistence, Windows runtime, or product release behavior.
- Do not touch R7/R8, issue #8, Windows/Google configuration, or original OCR projects.
- Do not add dependencies or alter CI in the feature PR; add one explicit test module in a separate CI PR.

## Review Focus

- Unknown/disabled/manual-only document types cannot produce validation reports: test eligible and ineligible type identities.
- A malformed R4 candidate must fail without leaking OCR text or taxonomy contents: test sanitized wrapper error.
- Required fields without proposed candidates remain visible, and candidate states remain distinct: test no candidate and each state.
- Duplicate candidates never silently overwrite one another: test conflicts and preserved state entries.
- Output order is deterministic and input records are unchanged: test reversed inputs and deep copies.

---

### Task 1: Implement the structural report

**Files:**
- Create: `src/alfa_document_intelligence/validation_contracts.py`
- Test: `tests/test_validation_contracts.py`
- Create: `docs/ocr/validation-contract.md`
- Modify: `README.md`
- Create: `docs/agent-work/issue-31-publication-manifest.md`

**Interfaces:**
- `ValidationContractError.code` exposes only stable sanitized codes.
- `FieldValidationEntry(field_id: str, states: tuple[CandidateState, ...])`
- `ValidationFinding(code: str, type_id: str, field_id: str)`
- `ValidationReport(taxonomy_schema_version, taxonomy_version, taxonomy_sha256, type_id, field_entries, findings)`
- `validate_document_fields(binding, type_id, candidates, page_results) -> ValidationReport`
- The report contains no boolean “valid” or acceptance property; no findings means structural completeness only.

- [x] Write 14 synthetic tests for required field absent/missing, each candidate state, duplicates, invalid binding/type/candidate, state/code distinction, deterministic ordering, and non-mutation.
- [x] Attempt the targeted unittest module. The run stopped during imports because `jsonschema` is unavailable in this worktree, before reaching the R5 behavior; this is not a valid TDD RED result. No dependency was installed.
- [x] Implement frozen report records and pure validation; preserve candidate objects and emit sanitized findings only.
- [x] The local targeted run could not import `jsonschema`; the locked GitHub runner passed the feature PR's existing 52-test check and the CI PR's explicit 66-test allowlist, including all 14 R5 tests. Both push and pull-request runs passed (`Ran 66 tests`, `OK`).
- [x] Independent review READY; API documentation and manifest are present; all six declared artifact hashes were independently confirmed.
- [x] Commit and prepare feature PR #32 on the R4 CI base. The separate CI PR #33 is also ready for review. Keep issue #31 open pending owner review and integration.

### Task 2: Extend CI separately

**Files:**
- Separate branch/PR modifying only the existing workflow, README test command/count, and an issue #31 CI manifest.

- [x] Add exactly `test_validation_contracts` to the explicit allowlist; no discovery or globs.
- [x] Preserve required check, triggers, SHA pins, hash lock, read-only permissions, runner, and timeout.
- [x] Push and pull-request runs execute all explicitly named modules: both report 66 tests, `OK`; independent CI review READY.
