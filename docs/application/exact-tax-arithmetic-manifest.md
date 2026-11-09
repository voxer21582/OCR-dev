# Exact tax arithmetic manifest

Date: 2026-11-09. Candidate based on public commit `6facee4b814b4bffbe0f80a463d9077532313364`; Punti assigned the destination in this isolated worktree. The original checkout remains unchanged. This is a local candidate, not a release.

The former Decimal addition depended on the caller's Decimal context. With synthetic large amounts it could report `pass` for unequal sums or `indeterminate` for exact sums; restricted precision and traps also affected the outcome. Canonical observed amounts now convert to integer cents and compare exactly, independently of that context. Inputs and source-bound evidence remain unchanged. Findings do not establish fiscal validity or approve reimbursements, payments, or accounting entries.

A candidate amount longer than 128 characters is intentionally `indeterminate` with the existing warning, even if its text is otherwise valid and its sum exact; it is never truncated. The bound is checked before the amount regex or integer conversion. This limits this calculation only, not total input size or evidence handling. The schema, findings and message codes are unchanged.

## Local verification

Synthetic fixtures only. The original RED run produced six failing subtests across three test methods. The expanded RED run produced seven failures and one error across six methods before the correction; it covers the boundary and restrictive Decimal traps. The selected local regression below passed **10 tests**, including the six new methods and four existing `TaxArithmeticValidationTests`. The new cases cover large false matches, exact sums, carry, negatives and zero, 128/129-character boundaries, exponential notation, precision and traps, preservation of input and evidence, and contract preflight. Logs, commands and hashes are retained locally in `.local-evidence/tax-exact-20261109`.

From `application/` on Windows PowerShell, using the existing interpreter:

```powershell
$env:PYTHONPATH='src;tests'
& 'C:/Users/voxer/.codex/worktrees/local-document-store/OCR2-Document-Intelligence-GitHub/.ocr2-rapidocr-demo-venv/Scripts/python.exe' -B -m unittest -v test_tax_exact_arithmetic.TaxExactArithmeticTests test_document_validation.TaxArithmeticValidationTests
```

The independent technical reviewer returned READY. Remote CI has not run for this candidate. The new test file needs an explicit selector in a separate CI PR; merge remains the owner's decision after the required checks. No R7/R8 or native runtime verification is claimed.
