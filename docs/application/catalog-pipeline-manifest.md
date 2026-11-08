# Custom-family pipeline: publication manifest

Date: 2026-11-08. Related migration: #42. Initial base: the progress prerequisite in PR #52 at `153fb41246d6c770935089869d5620b7407d2085`. After owner-approved integration of #52/#53, this candidate is reconciled with accepted public main `0b486a40434b793f295b4e08b689f0d5de238b74`. The five catalog source/test files remain byte-identical to the reviewed candidate; the callback and its now-accepted CI selector are preserved. This contribution adds only optional catalog propagation; it does not include a worker or an application launcher.

## Exact publication scope

| File | Owner / provenance | Reason for inclusion |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/semantic_proposals.py` | Coordinator; selected current OCR2 catalog bridge, adapted to the public base | Combine built-in and custom alternatives without choosing a value; retain the 100-alternative bound |
| `application/src/alfa_document_intelligence/analysis_pipeline.py` | Coordinator; selected current OCR2 snapshot propagation with scoped corrections | Reuse stored definitions, compare version and hash, attach exact relevant definitions and preserve existing candidates |
| `application/src/alfa_document_intelligence/document_validation.py` | Coordinator; selected current OCR2 required-field helper | Produce neutral findings for missing or review-required custom fields |
| `application/src/alfa_document_intelligence/document_processing.py` | Coordinator; selected current OCR2 optional argument and forwarding only | Carry the catalog to analysis without changing the decoder default or callback |
| `application/tests/test_catalog_pipeline.py` | Assigned implementation agent; new synthetic fixtures and regression assertions | Nineteen unittest methods covering the approved propagation contract and existing-boundary interactions |
| `application/CURRENT_STATE.md` | Coordinator; observed test output and review | Separate local verification, remote CI and product acceptance |
| `docs/application/catalog-pipeline-manifest.md` | Coordinator; this inventory | Publication scope, provenance, reproduction and limitations |

Implementation and independent technical review used separate agents. The technical reviewer returned READY after checking the final diff, retained 137-test output, final file hashes and preserved contract/catalog files. Publication review checked all seven files and requested one correction to the fixture description; that wording is corrected below. This is agent review, not formal GitHub approval.

The source lineage is current OCR2 Document Intelligence at `df6f14a14d29f7d8cc792e1de62f42e42e895a2e`, with concurrent uncommitted changes. It is not the previous OCR project. The dirty files are identified by the following SHA-256 pins, not by HEAD alone:

| Current OCR2 source file | SHA-256 |
| --- | --- |
| `src/alfa_document_intelligence/semantic_proposals.py` | `b9210f396e9b32460ee0f4f011ec312778ff54d0ceda9c627e7cbef7fe569321` |
| `src/alfa_document_intelligence/analysis_pipeline.py` | `257bda83ab0fc0d8ed6a74d2ff5049cc303a9e186ece576e6fb7d1cd041c1edd` |
| `src/alfa_document_intelligence/document_validation.py` | `ddeadf83670828a5cab946c81aa97fe85187e0ecc44a3eee10c4366bfe849e5b` |
| `src/alfa_document_intelligence/document_processing.py` | `b0d73b9627b175a3ccfbff5a7d6e7c49fa557f65e5f540da05fc1581d120f9bd` |

The approved configurable-family design and its implementation plan supply the propagation requirement. Existing public catalog v2/record 0.2 contracts remain authoritative and unchanged. The original checkout is preserved. Only the selected hunks were adapted; no private history, dependencies, configuration or unrelated source changes were copied.

## Behavior and acceptance evidence

- Literal custom aliases retain uncertain alternatives, source hash, page, region and token evidence. Built-in and custom title alternatives coexist; a combined count of 100 is accepted and 101 is rejected.
- Stored snapshots can supply the catalog on reopening. Reusing a family ID with a changed definition or catalog version is rejected. Exact declared field ownership prevents prefix-related IDs from attaching unrelated snapshots.
- Existing candidates and snapshots remain unchanged; new proposals for occupied fields are returned as unapplied. Legacy records remain 0.1.0 when no custom definition applies. Invalid or mixed-version snapshots fail closed without mutating the input.
- Required-field findings remain warning/indeterminate, with deduplicated evidence for uncertain/unreadable candidates. Missing/absent values do not acquire invented evidence. Built-in hotel and tax checks are not inferred for a custom family.
- Processing forwards the catalog through an injected synthetic decoder and OCR adapter, preserves page progress, and returns the existing semantic-failure result on a catalog conflict.

From `application/`, with the already available interpreter:

```text
PYTHONPATH=src:tests python -B -m unittest -v test_catalog_pipeline.CatalogSemanticProposalTests test_catalog_pipeline.CatalogAnalysisPipelineTests test_catalog_pipeline.RequiredCustomFieldValidationTests test_catalog_pipeline.CatalogDocumentProcessingTests test_semantic_proposals.SemanticProposalTests test_analysis_pipeline.AnalysisPipelineTests test_document_validation.HotelDateValidationTests test_document_validation.TaxArithmeticValidationTests test_document_contract.DocumentContractTests test_document_family_catalog.CustomDocumentFamilyCatalogTests test_document_processing.DocumentProcessingProgressTests
```

Use `;` as the path separator on Windows. The final run, after all test edits, reports **137 tests, OK**. The exact command, full output and file hashes are retained locally. Semantic RED output is retained; earlier analysis/processing failure outputs were observed but not saved as separate raw artifacts, so this manifest does not claim otherwise. Source parsing and whitespace checks passed.

Import inspection and injected test doubles keep this execution within existing application modules and the standard library. Lazy image/PDF/native engine paths are not invoked. No worker, archive, UI or blocked R7/R8 module is imported by the new tests. The four existing pytest-style processing free functions are not run by the callback class selector.

## Publication and execution limits

Only the seven files above are included. Local plans, source checkouts, raw logs, private paths, session metadata and temporary artifacts are excluded. Fixtures use an existing synthetic JSON record and invented in-memory values; no real documents, personal data, OCR output, secrets, model artifacts or new third-party code are included. Existing project licensing is unchanged, and no dependency is added.

The product PR leaves the workflow untouched, so its existing CI does not yet select the 19 new cases. A separate CI-only PR must add explicit selectors and retain the required check, SHA-pinned actions, hash-locked dependencies, read-only permissions and standard runner. Remote test totals must be read from that run rather than inferred from the local count.

Required-field activation remains based on observed exact family-title alternatives. Manually selecting a family without retained title alternatives is outside this contract. No automatic catalog migration, fiscal confirmation or payment/reimbursement approval is implemented. Worker/UI/archive integration, native Windows behavior, runtime/model acceptance, installer, release and R7/R8 remain outside this contribution. Merge requires owner approval.
