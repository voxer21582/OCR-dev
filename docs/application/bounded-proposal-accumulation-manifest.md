# Bounded common proposal accumulation

Date: 2026-11-08. Base: public main `6facee4b814b4bffbe0f80a463d9077532313364`, related to #42.

## Scope and provenance

| File | Ownership and purpose |
| --- | --- |
| `application/src/alfa_document_intelligence/semantic_proposals.py` | Assigned implementer; bound each existing common proposal list before adding the 101st item and iterate date matches lazily |
| `application/tests/test_semantic_proposals.py` | Same implementer; add synthetic evidence-count and threshold regression |
| `application/CURRENT_STATE.md` | Coordinator; record local evidence and limitations |
| `docs/application/bounded-proposal-accumulation-manifest.md` | Coordinator; this inventory |

This is an incremental change to the reviewed public application, not a copy from the previous OCR project. No dependency, model, native decoder, real data, archive, worker, UI or R7/R8 operation is included.

## Contract and evidence

Each existing common proposal accumulator retains at most 100 entries. At the first attempted addition beyond that bound, generation raises the existing `semantic_proposal_field_limit` error; it does not truncate or publish a partial result. The first excluded item's evidence is still constructed temporarily before the append guard. Date matches are iterated without materializing the entire match list, preserving ISO-before-numeric iteration order. Built-in page validation completes before accumulation; catalog-specific additional validation normally occurs later and can therefore be bypassed by an earlier built-in overflow. No partial fields are returned in that case. When several fields overflow, the first diagnosed field can follow scanning order rather than the old final-candidate order; the public error code remains the same.

The cap applies to proposal lists, not to all OCR tokens, input pages or total process memory. Catalog and family-merge caps remain separate and unchanged. This change does not implement bounded partial results, omitted-evidence recovery, a new document schema or a complete resource budget.

From `application/`, with `PYTHONPATH=src:tests` (`;` on Windows):

```text
python -B -m unittest test_semantic_proposals.SemanticProposalTests test_semantic_proposals.OverflowDiagnosticTests
```

The targeted synthetic RED showed continued evidence creation after saturation before this change. After the fix, the selected run passed **36 tests**. The new test uses evidence-call counting to verify stopping at the first exclusion; it does not directly measure the internal list. Full command, raw outputs and hashes are retained locally. Independent read-only technical review is READY; this is not formal GitHub approval. Publication review, remote CI and owner-approved merge are separate steps.
