# Neutral review label — scoped evidence

Date: 2026-11-09. Based on public main `7486989d556503fa07c66ccce52bc13a5be4effd`. This change replaces the blanket label “verified value” with “current value” in the local review page: extracted candidates are not automatically human verified. Status, review ledger, escaping and source evidence remain unchanged.

From `application/`, existing Python with `PYTHONPATH=src;tests`: `python -B -m unittest test_review_neutral_label test_manual_region_review.ManualRegionEvidenceTests test_review_ledger.ReviewLedgerTests` passed 26 synthetic tests. An initial new test failed on the old label. Independent static review READY. No browser, native decoder, real documents or R7/R8 tests were used. This is not complete product acceptance. Other open PRs change the same UI module and must be reconciled before integration.
