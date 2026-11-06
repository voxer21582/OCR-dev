# Local Persistent Document Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated, dependency-free local store that securely saves and reopens a validated document record with its source bytes.

**Architecture:** A focused module wraps SQLite and a payload-protector interface. The Windows default uses CurrentUser DPAPI; tests inject a deterministic fake protector. The table contains only an opaque row key, an encrypted record envelope, and independently encrypted source bytes; search decrypts record envelopes only.

**Tech Stack:** Python standard library (`sqlite3`, `ctypes`, `hashlib`, `json`, `base64`), existing document contract validator, `unittest` for the new isolated tests.

**Spec:** `docs/superpowers/specs/2026-11-06-local-persistent-document-store-design.md`

## Global Constraints

- Do not install dependencies, download models, or change TLS settings.
- Use only synthetic document records and bytes in tests.
- Keep the existing 25 MiB source-input limit.
- Do not change the volatile UI flow or active PR files.
- Fail closed when DPAPI, schema, record validation, or integrity checks fail.
- Do not claim DPAPI or Windows acceptance from fake-protector tests.

## Review Focus

- Hash mismatch or source substitution must reject before persistence; test wrong bytes and changed bytes for a saved ID.
- DB contents must not contain source, OCR, filename, or record plaintext; inspect SQLite values in a synthetic test.
- Tampered ciphertext and unsupported `user_version` must fail closed; test both.
- Search strings must be data, not SQL; test SQL metacharacters and case-insensitive match.
- Delete and interrupted transactions must not return partial records; test deletion and transaction rollback behavior.

---

### Task 1: Encrypted local store core

**Files:**
- Create: `src/alfa_document_intelligence/local_document_store.py`
- Test: `tests/test_local_document_store.py`

**Interfaces:**
- `LocalDocumentStore(path, protector=None, max_document_bytes=25*1024*1024)`
- `save(record: dict, source_bytes: bytes) -> str`
- `get(document_id: str) -> StoredDocument | None`
- `search(query: str, limit: int = 100) -> list[StoredDocumentSummary]`
- `delete(document_id: str) -> bool`
- `PayloadProtector.protect(bytes) -> bytes` and `unprotect(bytes) -> bytes`

- [x] Write stdlib `unittest` regressions for save/reopen, source hash and length, 25 MiB max, update immutability, ciphertext-only DB contents, source-independent search, delete, schema mismatch, and ciphertext tampering.
- [x] Run the new tests first with `PYTHONPATH=src python -B -m unittest discover -s tests -p test_local_document_store.py -v`; confirmed expected missing-module failure.
- [x] Implement the SQLite store and Windows DPAPI adapter; the injected protector exercises non-Windows behavior and a synthetic native DPAPI round-trip passed on this Windows host.
- [x] Rerun targeted store tests; 20 passed, including native DPAPI protect/unprotect, same-profile archive reopen, and synthetic network-drive/reparse-point classification on the current Windows host.
- [x] Review transaction boundaries, plaintext leakage, exception handling, DPAPI declarations, and search behavior against the design; independent review found no remaining material implementation defect after the payload split.

### Task 2: Focused status evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-11-06-local-persistent-document-store-design.md`
- Modify: `docs/superpowers/plans/2026-11-06-local-persistent-document-store.md`

- [x] Record exact targeted store result: `PYTHONPATH=src python -B -m unittest discover -s tests -p test_local_document_store.py -v` — 20 passed, including native DPAPI smoke and synthetic network-drive/reparse-point classification. Filesystem ACLs, backup/recovery, crash recovery, actual network/reparse scenarios, and Windows 11 acceptance remain unverified.
- [x] Do not update shared `CURRENT_STATE.md` while concurrent PRs own it.
- [x] Keep the branch local until remote CI availability is confirmed; do not push to a known billing-blocked Actions environment.
