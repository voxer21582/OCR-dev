# Manual handoff: latest review event

## Scope and provenance

This is a new change based on public base `6facee4b814b4bffbe0f80a463d9077532313364` in the isolated `OCR-dev-handoff-latest` worktree. The user and Punti assigned the destination for this work; the original checkout was not modified. The change uses no real documents, raw OCR or external service, and does not call an API. It has not been merged; R7/R8 are outside its scope.

The earlier builder retained the last *observed* correction, allowing that value to survive a later correction to a non-observed status. It now retains the latest `field_corrected` or `alternative_selected` event per allowed field in ledger order, and then includes the candidate only when observed and non-null. Other events, including `flagged`, do not replace a candidate. Existing bundle and ledger validation and role-specific allowlists remain in place. Allowed fields and review events are not approvals. A flagged review stays blocked, but the generated prompt does not guarantee display of that state. The prompt remains a manual draft requiring human review.

## Local synthetic evidence

The targeted regression produced 8 failures across 9 test methods before the fix, and passed all 9 afterward. It covers non-observed corrections, the absence of any remaining confirmed field, equal timestamps, later observed selection and its page evidence, field and document isolation, an unreviewed observed field, a flagged review, and rejection of a tampered ledger. The existing review-ledger class passed 15 tests. The pre-existing pytest handoff tests were not run because pytest is unavailable in the specified interpreter; no dependency was installed. These are local results only: remote tests and CI have not run for this candidate.

From `application/` in PowerShell, using the existing interpreter:

```powershell
$env:PYTHONPATH='src;tests'
& 'C:/Users/voxer/.codex/worktrees/local-document-store/OCR2-Document-Intelligence-GitHub/.ocr2-rapidocr-demo-venv/Scripts/python.exe' -B -m unittest -v test_handoff_latest_correction.HandoffLatestCorrectionTests
& 'C:/Users/voxer/.codex/worktrees/local-document-store/OCR2-Document-Intelligence-GitHub/.ocr2-rapidocr-demo-venv/Scripts/python.exe' -B -m unittest -v test_review_ledger.ReviewLedgerTests
```

The reviewer identified that the explicit CI selector for the new class is missing. It is to be addressed in a separate CI PR; no CI coverage is claimed here. The local RED, GREEN, ledger output and file hashes are retained under `.local-evidence/handoff-latest-20261109` in the main workspace, outside this candidate's tracked files.
