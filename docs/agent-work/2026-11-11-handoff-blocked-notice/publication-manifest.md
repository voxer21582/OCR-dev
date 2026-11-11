# Publication manifest — blocked-review ChatGPT handoff warning

**Repository:** `voxer21582/OCR-dev`  
**Proposed branch:** `codex/r6-blocked-review-consent-20261111`  
**Stacked base:** `codex/ci-document-export-20261110` at `6d8e73202842eb0de362e622b1c58664a3856237`  
**Related work:** PR #101; R6 / issue #34. This PR does not close the issue.

## Included

| Path | Provenance and purpose | Review and verification |
|---|---|---|
| `application/src/alfa_document_intelligence/chatgpt_handoff.py` | Existing OCR2 public source; adds a constant, privacy-safe alert for valid blocked review ledgers. | Independent exact-diff review READY; GitHub Actions pending. |
| `application/src/alfa_document_intelligence/local_intake_app.py` | Existing OCR2 public source; renders the alert outside the prompt and requires volatile consent bound to the current prompt and alert before showing copyable text. Stale consent and stale drafts are rejected/hidden. | Independent exact-diff review READY; GitHub Actions pending. |
| `application/tests/test_chatgpt_handoff.py` | Existing synthetic unittest module; covers blocked/non-blocked/malformed ledger warning behavior and sentinel non-disclosure. | Independent exact-diff review READY; GitHub Actions pending. |
| `application/tests/test_manual_chatgpt_handoff_ui.py` | Existing synthetic WSGI UI test module; covers consent, blocked warning, manual copy after consent, changed-content invalidation, and draft gating. | Independent exact-diff review READY; GitHub Actions pending. |
| This manifest | Release scope and exclusions. | Independent exact-diff review READY; GitHub Actions pending. |

## Verification scope

Independent review of the exact candidate against PR #101 head returned READY before publication. Python 3.13 AST parsing passed for the four candidate Python files; the unittest modules have not been executed locally. The stacked base's existing GitHub Actions job explicitly selects both test modules; no test discovery, workflow change, dependency change, permission change, or required-check change is proposed. The expected check is `Taxonomy registry and binding`. No run for this proposed branch exists yet.

## Excluded

- Real documents, OCR text, personal/company values, credentials, model artifacts, and derived real-data artifacts.
- OCR/runtime activation, browser automation, clipboard APIs, automatic transfer/network sending, Windows-native tests or configuration.
- R7/R8 code, tests, fixtures, and verification.
- Workflow/governance changes, dependency installation, merge, release, and issue closure.

## Limits and residual risks

The synthetic WSGI tests do not replace real-browser or screen-reader verification. The application cannot determine whether a user has authority to share a value externally; the user and organization remain responsible for that decision. A blocked-review warning does not approve the document or make earlier confirmed values current. Manual copying remains possible only after explicit confirmation bound to the exact current prompt and warning. Product acceptance, OCR accuracy, Windows 11 runtime acceptance, persistence/reopen behavior, and release remain unverified.


