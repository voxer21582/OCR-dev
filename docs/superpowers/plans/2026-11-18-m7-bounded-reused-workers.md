# M7 Bounded Reused Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. User has authorized autonomous execution; follow project review gates before merging.

**Goal:** Reduce repeated case-list overhead while preserving full DPAPI authentication and archive invariants, then verify REQ-129 on the installed application.

**Scope:** `application/src/alfa_document_intelligence/local_document_store.py` owns the process-wide gated worker pool and authenticated-record size calculation. `application/tests/test_expense_case_store.py` verifies byte-equivalent size accounting, batch failure/drain behavior, subsequent reads, snapshots and real Windows DPAPI. M7 evidence records measurements and limitations.

## Tasks

- [x] Add failing tests for canonical size equivalence, including Unicode, optional line data, non-finite values and exact limits; verify unchanged authentication and both sequential/parallel paths.
- [x] Implement size accounting only after `_decode_record` has checked the archive reference. Calculate envelope overhead using the same canonical serializer; preserve error and quota behavior.
- [x] Add failing tests for a reused bounded executor: wait for already submitted work on validation/submission error; convert executor unavailability to a safe store error; ensure gate release, later reads and process exit.
- [x] Implement a process-wide, lazily initialized executor with at most 12 workers, guarded by the existing nonblocking gate. Drain work before gate release; describe interpreter-shutdown and plaintext-lifetime limits. Keep existing ciphertext budget and oversized-record behavior.
- [x] Run storage and full application tests, independently review the final diff, and address concrete findings.
- [ ] Build and install offline in an isolated synthetic environment; measure UI interaction p95 across independent runs, OCR throughput, worker/server memory, and behavior under errors and concurrent writes. Do not use instrumented copies as proof of the released binary.
- [ ] Update evidence and CI for the exact final revision. Obtain required explicit owner approval for the changed R7 scope and renewed security sign-off before merge/closure; do not claim M7 complete unless every MUST gate is met.
