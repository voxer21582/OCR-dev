# Benchmark group-key coverage — candidate

The manifest validation summary reports counts of records with and without supplied group keys and labels their interpretation `provided_keys_only`. Cross-split collisions in supplied keys are still rejected; manifest contents, split assignments and frozen digest are unchanged. The count reveals no group key values.

Even when every record has a key, this does not prove that every relevant merchant, template, source or time relationship was identified, that custodians used a consistent HMAC key, or that undeclared correlations are absent. A report with records lacking keys cannot demonstrate their group separation. This check does not accept a benchmark or assess model quality.

On 2026-11-09, the explicit local synthetic `unittest` selection `test_benchmark_group_coverage` passed four tests using the existing demo Python environment. It covers empty, partial and full key coverage, unchanged frozen digest, duplicate-group rejection and CLI output without group hashes. No real documents or independent frozen samples were used. GitHub CI and manifest-preparation integration were not run for this candidate.
