# OCR2 Document Intelligence — product requirements baseline

Status: **draft for owner review**. This document defines what the complete Windows product must do and records, for every requirement, what is actually verified today. It does not claim that any requirement is accepted; acceptance needs the evidence gates in section 12.

## 1. Purpose, scope and how to read this document

**Product statement.** OCR2 is a local Windows 11 application that imports documents (PDF, PNG, JPEG, WebP, multi-page TIFF and, after evaluation, other formats), runs local OCR per page with provenance, extracts structured fields with evidence, alternatives and explicit uncertainty, lets a person review and correct the result, and keeps the work in a persistent, searchable, exportable library. It supports expense-report work (a final expense statement reconciled against supporting documents) as its first use case. It never approves reimbursements, payments or accounting entries.

**Prototype versus product.** The repository today is a **prototype/candidate**: a loopback web app with an isolated OCR worker, contracts and synthetic tests. It is not a complete product until the milestones in section 11 close with evidence. Statements below use these status labels:

| Label | Meaning |
|---|---|
| `SYN-CI` | Covered by synthetic automated tests that run in the repository CI. |
| `SYN-LOCAL` | Synthetic tests pass locally but are not in the CI selector (or the module cannot run without `pytest`). |
| `LOCAL-RUN` | Exercised on Windows 11 with the real runtime and **synthetic** files on 2026-11-14; summarised in the linked PR/issue comments; detailed logs are not in the repository. |
| `IN-PR` | Implemented in an open, unmerged pull request. |
| `OPEN` | Not implemented or not evidenced. |
| `OWNED` | R7/R8 component: owned elsewhere, see section 2. |

`LOCAL-RUN` is not acceptance: it uses synthetic documents, one reference PC, and no independent review.

## 2. Constraints (inherited, binding)

1. Do not copy data, code or configuration from the earlier OCR project; use only fixtures created for this repository.
2. CI and repository tests use **synthetic fixtures only**; no company, personal or real documents, OCR text of real documents, or credentials.
3. Do not install dependencies or download models without explicit authorization; every runtime artifact needs a pinned version, hash, source and licence record.
4. Do not change Windows configuration or any Google deployment during development. Installer effects must be documented and per-user.
5. **R7/R8** (persistence/recovery and export activities) have separate owners and stop/no-retry rules: do not modify their implementation or tests, and do not repeat a failed attempt without a new discriminating observation. Requirements that depend on them (section 7) state the dependency and are not implemented by this work.
6. Preserve concurrent checkouts and open pull requests; work on separate branches/worktrees and never rewrite shared history.
7. Nothing is reported complete without evidence recorded against the requirement.

## 3. Assumptions (reversible defaults)

These choices fill gaps in the documentation. Each is reversible; the owner is asked to object, not to approve.

| ID | Assumption | How to reverse |
|---|---|---|
| A1 | Single user, single Windows account, one machine; no network service or multi-user mode. | Add authentication and a non-loopback listener behind a new requirement. |
| A2 | The UI stays the existing loopback web UI started by a launcher; core services sit behind the WSGI app and store APIs, so a native shell (for example WebView2) can replace the browser without changing the core. | Replace only the launcher/shell. |
| A3 | Python 3.13 x64 runtime bundled with the installer (owner-approved evaluation direction in the Windows plan). | Change the runtime bundle; the lock files isolate the choice. |
| A4 | RapidOCR 3.10.0 with the PP-OCRv6 small multilingual models is the default engine (owner decision on issue #9); PaddleOCR/medium research (A4) stays separate. | Select another engine through the adapter and registry (OCR-3). |
| A5 | No cloud OCR, no runtime model download, no telemetry or crash upload. | A new requirement with privacy review. |
| A6 | Italian and English are the first document and UI languages. | Add languages through engine manifests and UI catalogues. |
| A7 | Additional import formats are admitted by the rule in IMP-5, not by default. | Adjust the rule. |
| A8 | Ambiguous dates keep every reading as an alternative and stay `uncertain` until a person confirms. For documents recognised as Italian or mixed, the day/month reading is **preselected as a visible hint** (rule id `date-dmy-hint`) and the month/day reading remains an alternative; the hint order is a setting (day/month, month/day, none). Adopted on 2026-11-14 as the recommended default after the owner left the choice open (D3). | Change the setting default; no stored value is rewritten. |
| A9 | Performance budgets in section 9 are proposals derived from the measurements recorded there. | Replace with pilot-derived thresholds (issue #10). |

## 4. Import and intake (IMP)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| IMP-1 | Import PDF, PNG, JPEG, WebP, multi-page TIFF and ZIP containers of these. | MUST | Each format imports with correct page count and hash; wrong extension is detected by signature; unsupported types are rejected with a stable code. | `SYN-CI` (inventory, TIFF/WebP). `LOCAL-RUN`: PNG, JPEG, WebP, 2-page TIFF and 2-page PDF imported and OCR'd end to end. |
| IMP-2 | Bounded, fail-closed intake: size, member count, expanded size, compression ratio, pixel and page limits are explicit and configurable; nested archives, traversal and absolute paths are rejected. | MUST | Limit tests at and over each bound; no source written to disk during inventory. | `SYN-CI`. ZIP entry limit 100 → 150 proposed in PR #133 (`IN-PR`). |
| IMP-3 | One expense statement plus at least 100 supporting documents per case without losing earlier uploads; resumable chunked intake. | MUST | 5×20 chunks accepted, replay is idempotent, 101st attachment rejected, interrupted upload resumes. | In `main` since #142 (`SYN-LOCAL`: case intake routes and store tests, outside CI); `LOCAL-RUN` 100 attachments accepted in 5 chunks. |
| IMP-4 | Exact duplicates (SHA-256) are reported, never silently removed. | MUST | Duplicate sources and documents listed with both identities. | `SYN-CI`. |
| IMP-5 | Additional formats are admitted only after evaluation. Rule: licensed, hash-locked decoder; resource limits; synthetic malformed-input tests; provenance preserved. Evaluated: single-frame GIF and BMP recommended for M4 ([evaluation](format-evaluation-gif-bmp.md)); HEIC/HEIF and JPEG 2000 later. Office documents are out of scope (the user exports to PDF). | SHOULD | Per format: decision record, limits, tests. | Evaluation done (no code); implementation `OPEN`. |
| IMP-6 | Encrypted or password-protected PDFs are rejected with a clear message. | MUST | Stable error code, no crash. | Implemented in the decoder; tests need `pytest` (`SYN-LOCAL`). |
| IMP-7 | PDF rendering requires `pypdfium2`; it must be a pinned, hash-locked, licence-recorded dependency. | MUST | Present in the Windows lock with hash and notice. | `IN-PR` (#138): hash-locked in `requirements/ocr2-runtime-cp313-win-amd64.lock`; a fresh venv installed only from that file passes the runtime check (`LOCAL-RUN`). Licence and notice review `OPEN`. |

## 5. OCR with provenance and engine extensibility (OCR)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| OCR-1 | OCR runs per page and each observation keeps source SHA-256, 1-based page, normalized polygon, token id, optional confidence and the exact engine/model/runtime identity. | MUST | Contract tests; evidence in records resolves to original bytes. | `SYN-CI`; `LOCAL-RUN` (RapidOCR 3.10.0 recorded as producer in results). |
| OCR-2 | Engine-neutral adapter boundary (`OCREngineAdapter`). | MUST | A new engine needs no change to pipeline or review code. | RapidOCR and PaddleOCR adapters exist; only RapidOCR was run natively (`LOCAL-RUN`); Paddle is `SYN-LOCAL`. |
| OCR-3 | Engine registry: engines are declared by a manifest (name, version, languages, licence, artifact hashes, factory reference), selectable per installation and per job, verified inside the worker. | MUST | Adding an engine means adding a manifest and adapter; wrong hash or version fails closed with a stable code. | `OPEN`. Today the launcher accepts only `disabled` or `rapidocr-v6` with one fixed factory. |
| OCR-4 | Isolated worker with memory/time limits, cancellation, bounded IPC and one-shot result publication. | MUST | Limit, cancel, timeout and race tests. | `SYN-CI` is partial (job tests not all in the CI selector); `LOCAL-RUN`: 101 documents, peak 773 MB, `exitcode 0`. |
| OCR-5 | Partial or failed pages are represented with non-sensitive codes and never marked complete. | MUST | A failed page cannot produce semantic proposals. | In `main` since #142 (`SYN-CI`: OCR page status contract). |
| OCR-6 | Italian and English recognition at minimum. | MUST | Synthetic mixed-language fixtures recognised with agreed thresholds. | `LOCAL-RUN` on synthetic lines only; thresholds `OPEN`. |
| OCR-7 | Use a PDF's embedded text layer when present, recorded as a distinct producer. | SHOULD | Text-native PDF produces tokens without raster OCR; provenance names the producer. | `OPEN`. |
| OCR-8 | Orientation and quality handling (EXIF orientation, rotation, optional deskew). | SHOULD | Rotated fixtures recognised. | EXIF orientation implemented in the decoder; rotation/deskew `OPEN`. |
| OCR-9 | OCR is off unless explicitly enabled, and the app states clearly when it is off or when the runtime is incomplete (checked at start, not at the first job). | MUST | Start with a missing package/model shows a specific message. | Default off `SYN-LOCAL` (launcher contract test is outside the CI selector); the early check is `IN-PR` (#138: exit code 2 with every problem listed, nothing started; `LOCAL-RUN`). Without that PR a missing package surfaces at the first job. |

## 6. Classification, extraction, validation (CLS, EXT, VAL)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| CLS-1 | Built-in families: invoice, fiscal receipt, parking receipt, hotel document, expense report, POS slip, other, unknown. | MUST | Contract tests. | `SYN-CI`. |
| CLS-2 | Configurable families: a user-supplied catalog defines families, typed fields, required flags and aliases; a hash-bound snapshot is stored with each record. | MUST | Invalid catalogs rejected; changed definitions under the same id rejected; legacy records stay readable. | `SYN-CI` (41 catalog tests). UI and archive integration not evidenced (`OPEN`). |
| CLS-3 | Classification is a proposal with evidence and alternatives; a person selects the family; the selection is evidence-bound and in the review history. | MUST | No automatic confirmation. | `SYN-CI`/`SYN-LOCAL`. |
| CLS-4 | Versioned, hash-bound taxonomy contract (schemas v1/v2) governs field names and types. | MUST | Registry and binding tests. | `SYN-CI`. |
| CLS-5 | A catalog editor (create, import, export, version) in the UI. | SHOULD | Create a family, apply it to a record, reopen. | `OPEN`. |
| EXT-1 | Field candidate model: value, status (observed, uncertain, unreadable, absent, not applicable, rejected), alternatives, scoped confidence, evidence, normalization rule and version. | MUST | Schema and contract tests; no field confirmed without evidence. | `SYN-CI`. |
| EXT-2 | Common fields with evidence: dates by role, amounts, currency, totals, VAT and tax identifiers, document number, payment references, bill-to/sold-to, tips. | MUST | Per-field fixtures with positive and negative cases. | `SYN-CI`; `LOCAL-RUN`: amounts, dates, currency and totals extracted from synthetic scans. Label-driven and same-token only; no line items, merchant name or tables. |
| EXT-3 | Line items and tables with totals and evidence. | SHOULD | Synthetic invoices yield rows linked to regions. | `OPEN`. |
| EXT-4 | Expense-statement lines (date, description, amount, currency) with page/region evidence; uncertain or conflicting values stay alternatives. | MUST | Long statements keep their lines; attached currency such as `EUR11,37` is read. | In `main` since #142 (`SYN-CI`: `test_expense_line_extraction`), including the fixes for #134 (closed) and the attached-currency part of #135; page headers read as lines remain open (#135). `LOCAL-RUN`: 98-line, 4-page statement reconciled. |
| EXT-5 | Locale-aware normalization (decimal comma, thousands separators, day/month order) that keeps the literal and every ambiguous reading. | MUST | Table-driven fixtures for it-IT and en. | Partly `SYN-CI`; the preference policy for ambiguous dates is an open owner decision (#135). |
| EXT-6 | Missing, unreadable and overflow situations are explicit; proposal limits are bounded and reported with stable codes. | MUST | Overflow tests. | `SYN-CI`. |
| EXT-7 | Accuracy targets per field family, measured on synthetic fixtures and, only under the approved protocol, on an approved sample. | MUST | Thresholds approved before measurement. | `OPEN` (issues #10, #1). |
| VAL-1 | Deterministic findings (pass, fail, indeterminate) with stable rule ids; arithmetic in exact decimals. | MUST | Rule tests. | `SYN-CI` (tax arithmetic, trip dates, required fields). |
| VAL-2 | Cross-document reconciliation of statement lines with supporting documents: amount, currency and date conflicts, possible duplicates, missing support; suggestions only. | MUST | Known-answer synthetic cases. | In `main` since #142 (`SYN-CI`: `test_expense_reconciliation`). `LOCAL-RUN`: of 20 attached receipts, the 18 whose amount agreed with the statement were matched; the 2 receipts whose statement amount had been altered were left unmatched, and no amount-conflict finding was raised for them (a gap to review). |
| VAL-3 | No automatic approval: every match, validation or classification is a proposal until a person decides. | MUST | No code path writes a confirmed state without a human event. | `SYN-CI` invariants. |
| VAL-4 | Validation rules are versioned and extensible without changing records already reviewed. | SHOULD | Rule added; old records keep old findings. | `OPEN`. |

## 7. Review and manual correction (REV)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| REV-1 | Review view shows the original page, region, alternatives, uncertainty and reasons for each candidate. | MUST | Walkthrough with keyboard and browser. | Rendered in Edge (headless) and exercised by HTTP (`LOCAL-RUN`); interactive walkthrough `OPEN`. |
| REV-2 | Corrections are append-only; the earlier value is kept; stale derived results are invalidated or marked. | MUST | Correction, conflict and invalidation tests. | `SYN-CI` (R6 contracts); correction and completion exercised by HTTP (`LOCAL-RUN`). |
| REV-3 | Manual source-region selection for absent fields, by pointer and keyboard. | MUST | Ordered coordinates enforced; keyboard parity. | `SYN-CI` (DOM doubles). Browser behavior unverified. |
| REV-4 | Reconciliation review: confirm, reject candidates, ambiguous, missing support, possible duplicate, exclude with reason; bound to the revision. | MUST | Stale revisions rejected; history append-only. | In `main` since #142 (`SYN-LOCAL`: reconciliation UI tests, outside CI). Browser behaviour unverified. |
| REV-5 | Accessibility: complete keyboard operation, labels, focus order, contrast. | MUST | Documented checklist run with a screen reader. | `OPEN`. |
| REV-6 | Review time recorded and exportable, never used as a decision. | SHOULD | CSV export. | Implemented; tests only partly selected in CI. |

## 8. Library: persistence, reopen, search, management, export (LIB, EXP)

R7 (persistence/recovery) and R8 (export) have separate owners. This document states the product requirements; it does not change their implementation.

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| LIB-1 | Per-user encrypted local archive (Windows data protection); explicit save, open and delete. | MUST | Reopen after restart returns identical records and source bytes. | `OWNED`. `SYN-LOCAL` (27 store tests). `LOCAL-RUN`: save, restart, reopen and JSON export with OCR values on synthetic data. |
| LIB-2 | Search by text, family, date, status; bounded results with paging. | MUST | Known-answer search tests. | `OWNED`. Search exists (limit 100); acceptance `OPEN` (issue #8). |
| LIB-3 | Cases persist and resume: statement, attachments, chunks, review events. | MUST | Interrupt during intake/OCR and resume. | `OWNED`. In `main` since #142 by owner waiver of constraint 5 (store schema v3, not reviewed by the R7 owner); `SYN-LOCAL`. `LOCAL-RUN`: case with 100 attachments processed. |
| LIB-4 | Management: list, rename, delete (with documented secure-deletion limits), retention settings. | MUST | Delete removes records and sources; limits documented. | `OWNED`, partial. |
| LIB-5 | Integrity, backup/restore and schema migration across versions (0.1.0 → 0.3.0 and later), including interrupted writes. | MUST | Migration fixtures; fault-injection tests. | `OPEN` (issue #8). |
| EXP-1 | Export a record as complete JSON and a CSV projection, on explicit user action. | MUST | Deterministic output; CSV cells safe from formula injection. | `OWNED`. `SYN-LOCAL`; JSON export reachable from the archive page (`LOCAL-RUN`). Repository docs still say no UI export (PR #126 corrects). |
| EXP-2 | Export a reconciliation, with suggestions, review state and evidence references kept apart. | MUST | Round trip. | `OWNED`. Case export route in `main` since #142 by owner waiver of constraint 5 (not reviewed by the R8 owner); round trip `OPEN`. |
| EXP-3 | Additional reports (spreadsheet, PDF with evidence overlays) after evaluation. | COULD | Decision record. | `OPEN`. |

## 9. Security, privacy and performance (SEC, PRF)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| SEC-1 | Loopback-only listener, host check, same-origin and token checks on every mutation. | MUST | Wrong host/origin/token rejected. | `SYN-CI` and `SYN-LOCAL`. |
| SEC-2 | No runtime network egress: OCR local, no model download, no telemetry. | MUST | Packet-level or firewall-level evidence during a full case. | Partial: a Python-level socket hook saw no non-loopback attempt in server and worker (`LOCAL-RUN`); it does not see native code or UDP. Strong evidence `OPEN`. |
| SEC-3 | Native decoders run only inside bounded, isolated workers, including page previews. | MUST | A malformed PDF cannot stop the server. | OCR decoding is isolated (`SYN-CI`); the page-preview rendering in `local_intake_app.py` runs in the web process (`OPEN`). |
| SEC-4 | At rest: encrypted per Windows user; in memory: sessions expire when idle and clear on request. | MUST | Tests and manual check. | `OWNED`/`SYN-LOCAL`. |
| SEC-5 | Supply chain: hash-locked dependencies, model provenance hashes, licence inventory and notices, SBOM. | MUST | Lock, SBOM and notices attached to a release candidate. | Candidate lock with 21 wheel hashes; models match the pinned hashes (`LOCAL-RUN`); `pypdfium2`, notices review and SBOM `OPEN`. |
| SEC-6 | Previews and responses are sandboxed (CSP, nosniff, no-store). | MUST | Header tests. | `SYN-LOCAL`. |
| SEC-7 | Errors and logs contain stable non-sensitive codes, never document text, paths or identifiers. | MUST | Log review checklist. | Convention implemented; audit `OPEN`. |
| SEC-8 | Threat model and independent security review before release. | MUST | Signed-off review. | `OPEN`. |
| SEC-9 | Repository and CI contain only synthetic data. | MUST | Guard tests. | `SYN-CI` (public-data guard). |
| PRF-1 | Throughput on the reference PC: at most 3 s per page (proposal). | MUST | Median over the benchmark. | Measured 2.0–2.9 s per page for synthetic pages (`LOCAL-RUN`, CPU, one PC). |
| PRF-2 | A case of one statement plus 100 documents completes in at most 10 minutes, resumable, with live progress. | MUST | Benchmark and interruption run. | `LOCAL-RUN`: 101 documents, 102 pages in 200–293 s (single session); case flow completed (duration not measured exactly). |
| PRF-3 | At most 2 GiB per OCR worker; UI interaction p95 under 200 ms. | MUST | Memory and latency traces. | Peak 773–776 MB per worker (`LOCAL-RUN`); UI latency `OPEN`. |
| PRF-4 | Start time to a usable window at most 5 s; large inputs (100-page PDF) bounded. | SHOULD | Measurements. | `OPEN`. |

Measurements come from synthetic files with clean text on one development PC; they do not predict scans, photographs or real documents.

## 10. Installation, update and operation (INS, OPS)

| ID | Requirement | Priority | Acceptance criteria | Status today |
|---|---|---|---|---|
| INS-1 | Per-user, offline, no-elevation installer (NSIS 3.x with an embedded CPython 3.13 x64, per the Windows plan). | MUST | Clean install, documented file and registry scope, launch. | `OPEN`. |
| INS-2 | Runtime bundle: pinned wheels with hashes, model files with SHA-256, notices; no download at install or run time. | MUST | Hash verification at install; start-up check. | `OPEN` (evaluation lock only). |
| INS-3 | Update, interrupted-update recovery, rollback and uninstall; user data survives unless the user removes it. | MUST | Lifecycle test matrix. | `OPEN`. |
| INS-4 | Signed installer and binaries. | MUST | Signature verifies; the record names who signed. | `OPEN`; the owner signs with their own certificate (D1). |
| INS-5 | Single launcher entry (shortcut) with no change to Windows settings beyond per-user shortcuts; version and runtime identity visible in the app. | MUST | Checklist. | `OPEN`. |
| OPS-1 | Diagnostics that contain no content, exportable on request. | SHOULD | Diagnostics bundle review. | `OPEN`. |
| OPS-2 | Jobs follow stop/no-retry: a failed job reports a stable code and is not retried without a new observation or explicit user action; cancellation is reliable. | MUST | Cancel and failure tests. | `SYN-CI`/`SYN-LOCAL`; one unreproduced stuck job observed (see issue comment on #106). |
| OPS-3 | Localization: Italian and English UI text. | SHOULD | Catalogue check. | The UI is Italian only; English `OPEN`. |

## 11. Increments (each ends with an evidence gate)

| ID | Increment | Exit evidence |
|---|---|---|
| M0 | Baseline: this document, evidence register, issues for known defects. | Reviewed by the owner. |
| M1 | Trustworthy single-document pipeline: lock including `pypdfium2` (#138), start-up runtime check (#138), pytest-style modules in CI (#139: 9 of 13 run; the 4 that import the R7 archive/store path stay excluded), real decoder cases in CI (#140: Pillow and `pypdfium2` locks for Ubuntu; the pytest step runs 79 tests with none skipped), PDF/TIFF/WebP end to end with the real engine (done locally on synthetic files), PR #133 decided. | CI runs the previously unrun modules with no unexplained skips; local evidence recorded for each format. |
| M2 | Cases and reconciliation: integrate the #106 chain (done, #142), fixes for #134 and #135 (done, #142; #135 headers still open), owner decision on ambiguous dates, a 100-document case benchmark, a driven browser walkthrough (needs authorization to install a test driver). | Known-answer reconciliation fixtures; recorded benchmark. |
| M3 | Library acceptance (R7/R8 owners): import, reopen, search, review, export, delete, interruption and recovery (issue #8). | Evidence run on synthetic data, independently reviewed. |
| M4 | Extensibility: engine registry with manifests, a second engine behind the adapter, catalog editor, embedded PDF text. | Synthetic benchmark across engines; catalog round trip. |
| M5 | Installable product: installer, update/rollback, signing, SBOM and notices, threat model and security review. | Lifecycle matrix and review sign-off. |
| M6 | Pilot and acceptance: approved protocol (issue #10), pilot (issue #1), Windows acceptance sign-off. | Thresholds met on the approved sample. |

The product is complete only when M6 closes. Earlier increments are releasable candidates, not the product.

## 12. Evidence gates and traceability

A requirement moves to *accepted* only with: its acceptance criteria met; evidence recorded (command or procedure, host, timestamp, result, privacy-safe artifact); independent review; and, for runtime and installer items, the gates in `docs/runtime/windows11-acceptance-plan.md`.

Evidence recorded so far (all synthetic, one reference PC, 2026-11-14):

- PR #133 body: ZIP/timeout limits, single-session load result, CI run.
- Issue #106 comment: evaluation of the #106 → #114 → #125 chain, case-flow runs, one unreproduced stuck job.
- Issues #134 and #135: reproductions, causes, fixes, and what was deliberately not changed.
- PR #142 (2026-11-15): the #106 chain on `main`, R7/R8 commit merged by owner waiver; local run 629 passed, 1 skipped, 1 pre-existing launcher test failure, fixed in the follow-up that isolates launcher tests from the real `%LOCALAPPDATA%`.
- Earlier issue #9 comment (2026-11-12): the RapidOCR smoke summary; its log stays private.

## 13. Decisions

Recorded on 2026-11-14. Only items that change scope, cost or risk are listed; everything else uses section 3.

| ID | Decision | Outcome |
|---|---|---|
| D1 | Code-signing certificate and signing. | **Owner signs.** The owner holds the certificate and performs the signing; this work never holds signing keys. The build produces unsigned artifacts with checksums and a documented signing step. INS-4 stays open until the owner signs a candidate, and acceptance records who signed and when. This is an interpretation of the owner's reply ("firma mia"); it is to be corrected if a different arrangement was meant. |
| D2 | Redistribution of runtime and models. | **Recommended and adopted as the reversible default:** the first release is for the owner's own machines (no distribution to third parties), built from the hash-locked wheelhouse with the full licence and notice texts included. Before any distribution beyond that, a legal review must cover the points below. This is a technical recommendation, not legal advice. |
| D3 | Preference for ambiguous dates. | **Recommended and adopted as the reversible default** (see A8). |
| D4 | Formats beyond the five. | **Evaluate GIF** (and BMP); see [format-evaluation-gif-bmp.md](format-evaluation-gif-bmp.md). Recommendation: single-frame GIF and BMP in M4; HEIC and JPEG 2000 later. |

**Licence points for the review in D2**, from the installed package metadata of the 22-package runtime lock:

- `opencv-python-headless` 5.0.0.93 ships `cv2/opencv_videoio_ffmpeg500_64.dll`, an FFmpeg library (normally LGPL-2.1) that OCR2 does not use. Options: include it with the LGPL obligations met, or exclude that file from the installer after confirming OCR still works.
- `certifi` and `tqdm` are MPL-2.0; `numpy` bundles several licences (BSD-3-Clause, 0BSD, MIT, Zlib, CC0-1.0).
- `pypdfium2` is BSD-3-Clause and Apache-2.0 with bundled dependency licences, including CC-BY-4.0 (attribution).
- The two PP-OCRv6 models and RapidOCR are declared Apache-2.0 in the installed `MODEL_LICENSES.md`, with attribution to the upstream rights holders; the hashes establish provenance, not permission.
- Every notice text must ship with the installer.
