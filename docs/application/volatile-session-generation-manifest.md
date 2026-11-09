# Volatile session generation — scoped manifest

Date: 2026-11-09. Based on public main `7486989d556503fa07c66ccce52bc13a5be4effd`. New OCR2 work and synthetic fixtures; no old OCR project code or data copied.

For the app configuration without an archive store, session-specific emitted links and forms carry an opaque generation. A successful new upload, explicit clear, or idle expiry rotates it; stale or invalid generations are rejected before session-specific access or mutation. A second upload during active volatile intake is rejected. Existing Host, Origin and CSRF checks remain separate. Unbound GET `/` and `/upload` are intentional local bootstrap entry points, not authentication. Generation may appear in local access logs and browser history. The archive-enabled configuration is not protected by this candidate; it is not silently disabled. The supplied server is serial; no guarantee is made for concurrent WSGI hosting or multiple processes.

From `application/` with the existing Windows Python environment and `$env:PYTHONPATH='src;tests'`, selected synthetic unittest runs passed 84 tests for stale requests, volatile protection, loopback/CSRF, manual-region, review-ledger, ingestion and document export. A separate test run executed 10 pre-existing pytest-style intake functions via `unittest.FunctionTestCase`; the monkeypatch-dependent case and 1,000-document test were excluded.  Initial stale-link and clear tests failed before implementation. Independent scoped static security and publication reviews found no remaining blocker for the described scope; reviewers did not run tests. Some stale review actions use constructed test forms, while preview is mocked.

No browser JavaScript or CSP execution, real OCR, native decoder, archive-enabled flow, real document, R7/R8 operation, multiworker scenario or product acceptance is established. Existing UI/workflow PRs touch overlapping files and must be reconciled before integration. Existing test clients following direct URLs require adaptation to emitted generation-bound URLs.

Reproduction of the 84-test run from `application/` (select the existing authorized Python environment first):

```powershell
$env:PYTHONPATH='src;tests'
python -B -m unittest test_volatile_session_protection test_stale_session_isolation test_manual_region_review.ManualRegionEvidenceTests test_loopback_csrf test_review_ledger.ReviewLedgerTests test_ingestion test_document_export
```

The separate 10-function run used:

```powershell
$env:PYTHONPATH='src;tests'
python -B -c "import unittest, test_local_intake_app as t; names=[n for n in dir(t) if n.startswith('test_') and n not in {'test_chatgpt_prompt_page_warns_before_manual_external_transfer','test_local_browser_accepts_a_1000_document_synthetic_bundle'}]; r=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(unittest.FunctionTestCase(getattr(t,n)) for n in names)); raise SystemExit(not r.wasSuccessful())"
```
