# R2 OCR Observation Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add an engine-neutral, validated page input/result contract that preserves OCR provenance and uncertainty without executing OCR.

**Architecture:** Standard-library frozen dataclasses define the input, engine identity, polygon, observation, and page result. A `Protocol` describes a future single-page engine boundary. Validation raises one stable sanitized contract error.

**Tech Stack:** Python 3.13, standard library, `unittest`; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-06-r2-ocr-observation-contract-design.md`

## Global Constraints

- Synthetic data only; no document fixtures or OCR text from real sources.
- Do not implement, load, or activate OCR, a model, renderer, launcher, or runtime.
- Do not change GitHub Actions in this feature branch; CI expansion is a separate PR.
- CI must invoke an explicit allowlist only: `test_taxonomy_registry`, `test_taxonomy_binding`, and `test_ocr_contracts`. Do not use test discovery or glob-based selection.
- Do not touch R7/R8, issue #8, Windows configuration, Google deployment, or the original OCR project.

## Review Focus

- Malformed source digest or non-positive page number must fail with a stable sanitized error.
- Degenerate, non-finite, or out-of-bounds polygon coordinates must fail.
- Self-intersecting polygons must fail even when their signed area is nonzero.
- Polygons with more than 256 vertices must fail before pairwise geometry validation to bound work on untrusted inputs.
- Non-finite or out-of-range confidence must fail; absent confidence remains valid.
- Failed results must not expose observations; failure codes must not carry exception text or paths.
- Frozen records must not permit mutation of nested polygon or observation collections.

---

### Task 1: Define and verify the OCR boundary

**Files:**
- Create: `src/alfa_document_intelligence/ocr_contracts.py`
- Test: `tests/test_ocr_contracts.py`
- Create: `docs/agent-work/issue-17-publication-manifest.md`
- Modify: `README.md` only to link the new contract and state it is non-operational.

**Interfaces:**
- `EngineIdentity(engine_id, engine_version, model_id, model_version, runtime_id, runtime_version)`
- `PageProvenance(source_sha256, page_number)`
- `PageInput(provenance, media_type, image_bytes)`
- `TextRegion(polygon)` where polygon is at least three normalized finite points with nonzero area.
- `TextObservation(text, region, confidence=None)`
- `PageOCRResult(provenance, engine, observations, status="complete", error_code=None)`
- `validate_page_result(page, result, expected_engine=identity)` rejects results whose provenance or identity differs from the expected input/engine.
- `OCREngine.identity` and `OCREngine.recognize_page(page: PageInput) -> PageOCRResult`
- `OCRContractError.code` exposes only a stable code.

- [ ] Write tests first for one valid immutable result, valid absent confidence, bad source hashes/pages, malformed polygons, invalid confidence, status/error consistency, and sanitized error codes.
- [ ] Run `python -B -m unittest -v test_ocr_contracts` and confirm the expected import failure before implementation.
- [ ] Implement the frozen standard-library data model and explicit validation.
- [ ] Run the new test module, then the explicit allowlist `test_taxonomy_registry test_taxonomy_binding test_ocr_contracts`; do not use test discovery.
- [ ] Review the final diff for absence of dependencies, engine execution, file/network access, real data, and workflow changes.
- [ ] Create a manifest with paths, SHA-256 hashes, owner/provenance, review state, and scope exclusions; link the contract from the README.
- [ ] Commit the feature and prepare a PR for issue #17. Keep the issue open until the separate CI expansion includes and verifies this test module.

### Task 2: Extend the existing synthetic CI separately

**Files:**
- Separate branch/PR modifying only `.github/workflows/ocr2-synthetic-taxonomy.yml` and any workflow-specific manifest.

**Interfaces:**
- CI invokes only `test_taxonomy_registry`, `test_taxonomy_binding`, and `test_ocr_contracts` using the existing hash-locked environment and read-only permissions. Test discovery is prohibited to avoid running unapproved or blocked tests.

- [ ] Confirm the workflow runs only synthetic tests, does not activate OCR, uses no new secrets/actions/dependencies, and retains the exact required check name.
- [ ] Validate on GitHub Actions and document that taxonomy plus OCR-contract tests remain a limited synthetic slice.

This second task does not claim application acceptance and must not change branch protection or merge itself.
