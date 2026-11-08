# Proposal overflow diagnostics: candidate scope

Date: 2026-11-08. Base: public main `1f4e835999b50cd73d8d4d337a975946609137a6`. Related migration: #42.

This candidate identifies per-field proposal overflow, global catalog overflow and combined family-candidate overflow with distinct fixed non-sensitive codes. The failures remain fail-closed and propagate to failed semantic extraction. Existing fields in the input record are preserved; no new partial extraction results are published. Invalid non-overflow input keeps its generic failure behavior. Existing schema accepts the error-code strings; no schema version is changed.

The change and synthetic tests were authored for this isolated public-base branch. The original checkout and previous OCR project were not modified or copied. No new dependency, model, native decoder or external service is introduced. Code review and publication review are distinct; this local candidate is not a GitHub approval or product acceptance.

Independent read-only technical review found the three causes propagate through compatible exception subclasses, before adding new proposals. Its suggested test placement correction was applied before the final run. The explicitly selected local regression run reports **84 synthetic tests, OK**; command and raw output are retained locally. No remote CI coverage is claimed for the new cases until the actual workflow selector and logs are checked.

From `application/`, with `PYTHONPATH=src:tests` (`;` on Windows):

```text
python -B -m unittest test_semantic_proposals.OverflowDiagnosticTests test_semantic_proposals.SemanticProposalTests test_document_family_catalog.CustomDocumentFamilyCatalogTests test_analysis_pipeline.AnalysisPipelineTests test_analysis_pipeline.OverflowPipelineTests.test_overflow_code_propagates_without_output test_document_processing.OverflowProcessingTests
```

This is a diagnostic prerequisite, not the solution to partial extraction. Candidate collection can still accumulate observations before its limit check; no claim of bounded accumulation, partial completeness, retained omitted evidence, automatic absence, UI/export disclosure, worker acceptance or operational readiness is made. R7/R8, archive, UI, native OCR and Windows configuration remain outside scope. The source record may contain existing fields; those are not new results from the failed analysis.
