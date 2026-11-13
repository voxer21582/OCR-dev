# OCR2 Document Intelligence application

This is a selective public snapshot of the local OCR2 application, not a product acceptance or release.

## Current launcher behavior

The command-line launcher supports `--port` (loopback, default 8000) and `--ocr-engine {disabled,rapidocr-v6}` (default `disabled`). The optional RapidOCR path requires the locally prepared package and model files; it does not download them automatically. The exact runtime and Windows acceptance remain open in [issue #9](https://github.com/voxer21582/OCR-dev/issues/9).

**Do not launch this Windows build, even with OCR disabled, or open/save real expense notes until the R7/R8 storage gates and Windows acceptance are cleared.** On Windows, startup constructs `LocalDocumentStore` at `%LOCALAPPDATA%\OCR2\document-archive.sqlite3` before serving the app, regardless of the OCR setting. This initializes the storage path and crosses the blocked archive boundary. See the current [application state](CURRENT_STATE.md) and [architecture notes](ARCHITECTURE.md).

The candidate remains a development build. The Python 3.11 preview instructions previously shown here are withdrawn; use only a runtime approved through issue #9 after its acceptance gates are complete.

## Real expense documents and external handoff

Real expense documents must remain local and must not be committed or used in public CI. The intended local pilot is not yet accepted; [issue #10](https://github.com/voxer21582/OCR-dev/issues/10) and its protocol proposal track the remaining approvals.

The optional ChatGPT drafting handoff is manual: it may contain only minimum human-verified fields and necessary context, never files or raw OCR, and only when organizational policy permits. No API call is made. Returned text is an untrusted draft requiring local human review.

## CI and verification limits

The required [`Taxonomy registry and binding`](../.github/workflows/ocr2-synthetic-taxonomy.yml) check runs taxonomy tests and an explicit allowlist of synthetic application tests. It does not use test discovery or real documents. Storage-dependent selectors and the three OCR worker/UI/launcher test modules are excluded; the successful check is not evidence of R7/R8, Windows runtime, browser workflow, native OCR or full-product acceptance. See [CURRENT_STATE.md](CURRENT_STATE.md) and the workflow for the current evidence boundary.

OCR proposals and reconciliation matches are not approvals for reimbursement, payment, or accounting entries.
