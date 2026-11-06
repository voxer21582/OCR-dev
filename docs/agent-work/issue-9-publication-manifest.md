# Issue #9 — Publication manifest

**Prepared:** 2026-11-06
**Base:** protected `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`
**Branch:** `codex/r1-windows-acceptance-plan`
**Review:** independent review READY after the final content correction.

## Included file

| File | SHA-256 | Owner and provenance | Reason |
| --- | --- | --- | --- |
| `docs/agent-work/issue-9-windows-acceptance-plan.md` | `6e2a36bc5411fc9a8a290fd784358be4c6cd6fefeb7c4fc2abd407d6aec8e7d9` | OCR2 coordinator; issue #9 acceptance requirements and official Tesseract, PaddleOCR, and Microsoft documentation | Defines staged, evidence-based acceptance without selecting an engine or authorizing runtime operations. |

## Exclusions and limits

- No code, workflow, dependency, runtime, model, installer, real/company data, or OCR output is included.
- No download, installation, native Windows test, security setting, or deployment was performed.
- This document is a proposal. It does not establish Windows readiness, OCR quality, security, licensing clearance for a selected artifact, or product acceptance.
- Owner decisions remain required for packaging, engine/model shortlist, languages/formats, quality thresholds, installation/network policy, resource budgets, and reference hardware.
- Independent review: READY; confirmed the plan SHA-256, scope, factual distinctions, and absence of sensitive content or unapproved product decisions.
- `git diff --cached --check`: passed after removing trailing spaces. No application tests are applicable to this documentation-only change.