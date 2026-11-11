# Publication manifest — blocked-review ChatGPT handoff warning

**Repository:** `voxer21582/OCR-dev`  
**Proposed branch:** `codex/r6-blocked-review-consent-20261111`  
**Stacked base:** `codex/ci-document-export-20261110` at `6d8e73202842eb0de362e622b1c58664a3856237`  
**Related work:** PR #101; R6 / issue #34. This PR does not close the issue.

## Included

| Path | Provenance and purpose | Review and verification |
|---|---|---|
| `application/src/alfa_document_intelligence/chatgpt_handoff.py` | Existing OCR2 public source; adds a constant, privacy-safe alert for valid blocked review ledgers. | Independent exact-diff review READY; successful GitHub Actions run pending. |
| `application/src/alfa_document_intelligence/local_intake_app.py` | Existing OCR2 public source; renders the alert outside the prompt and requires volatile consent bound to the current prompt and alert before showing copyable text. Stale consent and stale drafts are rejected/hidden. | Independent exact-diff review READY; successful GitHub Actions run pending. |
| `application/tests/test_chatgpt_handoff.py` | Existing synthetic unittest module; covers blocked/non-blocked/malformed ledger warning behavior and sentinel non-disclosure. | Independent exact-diff review READY; successful GitHub Actions run pending. |
| `application/tests/test_manual_chatgpt_handoff_ui.py` | Existing synthetic WSGI UI test module; covers consent, blocked warning, manual copy after consent, changed-content invalidation, and draft gating. | Independent exact-diff review READY; successful GitHub Actions run pending. |
| This manifest | Release scope and exclusions. | Independent exact-diff review READY; successful GitHub Actions run pending. |

## Verification scope

Independent review of the exact candidate against PR #101 head returned READY before publication. Python 3.13 AST parsing passed for all four candidate Python files, including the corrected UI test. GitHub Actions run [#366](https://github.com/voxer21582/OCR-dev/actions/runs/43042602481) on the preceding candidate passed 22 taxonomy tests and ran 359 application tests, with one failure: an existing UI assertion still expected immediate prompt display. The test now follows the consent flow; a successful run for the corrected candidate is pending. The stacked base's existing workflow explicitly selects both test modules; no test discovery, workflow change, dependency change, permission change, or required-check change is proposed. The required check remains `Taxonomy registry and binding`.

## Excluded

- Real documents, OCR text, personal/company values, credentials, model artifacts, and derived real-data artifacts.
- OCR/runtime activation, browser automation, clipboard APIs, automatic transfer/network sending, Windows-native tests or configuration.
- R7/R8 code, tests, fixtures, and verification.
- Workflow/governance changes, dependency installation, merge, release, and issue closure.

## Limits and residual risks

The synthetic WSGI tests do not replace real-browser or screen-reader verification. The application cannot determine whether a user has authority to share a value externally; the user and organization remain responsible for that decision. A blocked-review warning does not approve the document or make earlier confirmed values current. Manual copying remains possible only after explicit confirmation bound to the exact current prompt and warning. Product acceptance, OCR accuracy, Windows 11 runtime acceptance, persistence/reopen behavior, and release remain unverified.


