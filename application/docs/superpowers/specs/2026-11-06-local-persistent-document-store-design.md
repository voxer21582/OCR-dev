# Local Persistent Document Store Design

## Intent

The active OCR2 product objective requires saved documents to survive browser-session cleanup and be available for reopening and search. The current charter and app intentionally keep data volatile, so this design adds a separate local persistence capability without changing the existing intake flow yet.

## Goals

- Store a validated document record and its exact source bytes as one atomic, locally recoverable item.
- Reopen the original bytes and record with source SHA-256 integrity checked.
- Search saved records locally without sending data to a service.
- Delete a saved item explicitly and distinguish persistent archive data from volatile intake sessions.
- Add no third-party dependency and never put source bytes, OCR text, filenames, or record fields in plaintext SQLite columns.

## Non-goals

- This storage-core design did not itself implement UI integration. Explicit archive UI and JSON/CSV export were added in a later separately reviewed change; automatic saving, migration of volatile sessions, multi-user access, and cloud sync remain out of scope.
- No claim of forensic secure erasure after deletion; storage media, filesystem snapshots, and backups are outside the store's control.
- No change to OCR engines, fiscal rules, review acceptance, or blocked R7/R8 work.

## Product constraints

- The user requested persistence and selected retention until explicit deletion in the project conversation.
- The app remains local and single-user; no login or remote service is introduced.
- The store is a separate persistence capability; existing session cleanup semantics remain unchanged.
- Archive paths must be on a fixed local Windows drive. UNC and mapped drives are rejected, and existing reparse-point components are rejected before SQLite opens the path.
- SQLite is the standard-library container. A Windows CurrentUser DPAPI protector encrypts record metadata and original bytes separately. The database stores a random row key, a keyed HMAC index for document IDs, and the two protected payloads; the index key is itself protected by the configured protector. This allows direct ID lookup without storing document IDs in plaintext. Searches decrypt the small record payload in-process and never open original bytes or create plaintext search indexes.
- Same-Windows-user profile is the recovery boundary. Moving a database to another Windows profile/device is not supported by this phase.
- The existing 25 MiB per-input ceiling is enforced again by the store.

## Approaches

1. **SQLite with plaintext BLOBs:** simplest and searchable, but it would place sensitive OCR/source data on disk without at-rest protection. Rejected.
2. **SQLite with DPAPI-protected record and source payloads plus a keyed ID index:** local, dependency-free, and compatible with the single-user Windows product. Search is linear in archived record entries and decrypts one record at a time; direct get/update/delete uses the keyed index. The index is validated against decrypted records at store startup and entries are checked as they are accessed; source files are not decrypted by search.
3. **Encrypted files plus a separate metadata index:** supports independent payload management, but requires a second storage format and exposes index fields unless that index is also protected. Deferred until measured archive size justifies the added machinery.

## Data and operations

- Store schema version 2 uses SQLite `user_version` and a table containing a random entry key, a keyed HMAC document-ID index, an encrypted record payload, and an encrypted source payload. Opening a version-1 database transactionally migrates it to version 2 by generating and protecting an index key and backfilling keyed ID indexes; malformed schemas fail closed before migration.
- The record envelope contains the JSON document record; source bytes are protected separately without base64 expansion. Before save, validate the document contract, enforce the byte limit, require `source.byte_length` to match the bytes, and require the bytes' SHA-256 to equal `record.source.sha256`.
- A document ID may be updated only when the original source hash and bytes are unchanged; this supports later review-record updates without source substitution.
- `get` verifies DPAPI unprotection, record shape, source length, and source hash before returning a defensive copy.
- `search` streams records and performs case-insensitive matching over decrypted document ID, filename, document family, field values, and review content; it never decrypts source bytes, returns summaries only, and applies a caller-bounded result limit.
- `get`, `save`, and `delete` use the keyed document-ID index; updates and deletes are transactional, and optional expected-record SHA-256 compare-and-swap prevents overwriting a concurrently changed review record. `delete` does not promise physical erasure from filesystem snapshots, backups, or storage remanence.
- Unsupported database schema versions, decryption failures, invalid records, hash mismatches, and oversized data fail closed with a store-specific error.

## Acceptance evidence

- Synthetic tests show save/reopen preserves bytes and record, rejects hash/length mismatch and oversize inputs, rejects source substitution, searches without SQL query injection or source-payload decryption, deletes records, rejects stale compare-and-save, migrates a valid version-1 schema, and fails closed on tampered index/schema/ciphertext.
- Tests inject a deterministic fake protector to exercise storage behavior on non-Windows CI. On 2026-11-06, generated synthetic round-trip and load checks exercised native DPAPI and archive reopen on the current Windows host. These do not replace Windows 11 installation/user acceptance after UI integration.
- Database inspection confirms only random row identifiers and ciphertext are stored, with no source bytes or serialized record plaintext.
- On 2026-11-06, the local Windows synthetic load tool completed 1,000 generated records using DPAPI: 6.211 s total save time (6.211 ms mean per save), 0.617 s search for the final generated filename, 0.002 s direct reopen, and a temporary 4,259,840-byte database. This is a local synthetic measurement, not a capacity guarantee or application acceptance result.
- On 2026-11-06, the same tool completed 10,000 generated records using DPAPI on the current Windows/Python 3.13.15 host: 58.354 s total save time (5.835 ms mean), 5.934 s to search for the final generated filename, 0.002 s direct reopen, and a temporary 42,405,888-byte database. Search scans encrypted record metadata linearly; this worst-position lookup is evidence of that cost at this synthetic scale. The records are small copies of one authored fixture and contain short generated source bytes. The run does not measure store startup validation, native OCR, normal PDF sizes, user experience, or future capacity.
- Existing volatile intake behavior remains unchanged.

## Risks and remaining work

- Filesystem ACLs, backup/recovery policy, crash recovery, actual mapped-drive/reparse-point scenarios, and Windows 11 user acceptance remain unverified. Synthetic classifier tests cover remote-drive and reparse-point rejection; the native smoke used the current fixed local drive and covered DPAPI protect/unprotect plus same-profile archive reopen only.
- The current charter/data-schema statements that persistence is out of scope must be reconciled before treating persistence as product-accepted or release-ready.
- The UI integration provides explicit save/open/delete controls and export disclosures. It does not auto-save a live session. Windows 11 acceptance, operational recovery, backup policy, and the documentation/charter reconciliation remain outstanding.
