# M7 Responsive Case Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. The owner requested autonomous work; retain all project review gates.

**Goal:** Test whether same-document navigation can make the existing fully validated case list responsive without weakening archive checks or changing the no-JavaScript fallback.

**Scope:** `application/src/alfa_document_intelligence/local_intake_app.py` owns a narrowly scoped progressive enhancement for GET navigation between `/` and `/cases`. `application/tests/test_case_navigation.py` checks concurrency, history, response validation, lifecycle and fallback. The M7 evidence records separate DOM and actual presentation measurements.

## Tasks

- [ ] Write deterministic tests for successful navigation, stale response suppression, back/forward during a pending request, multiple clicks, redirects, unexpected content types, failures, ordinary modified clicks and browser fallback.
- [ ] Implement a small same-origin controller with an abortable request and monotonic generation. Never expose the case list until the normal server endpoint has completed all integrity checks; preserve native links and forms without JavaScript.
- [ ] Preserve existing app heartbeat, exit token, history, focus and screen-reader semantics; do not execute scripts from fetched markup. Limit response size and apply a narrowly scoped same-origin CSP.
- [ ] Verify actual browser interactions, keyboard navigation, back/forward, forms and app lifecycle on isolated synthetic data, then obtain an independent security/accessibility review and address concrete findings.
- [ ] Build an isolated test installer and measure actual presentation and memory under OCR in independent runs. Keep DOM-ready and HTTP measurements distinct from rendering; do not claim REQ-129 from either alone.
- [ ] Update the PR and CI, obtain required explicit R7/security approval, and close M7 only after every MUST gate is verified.
