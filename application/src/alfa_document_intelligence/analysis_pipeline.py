"""In-memory coordinator for source-bound OCR proposals and document checks.

This module consumes OCR results produced elsewhere. It does not read files,
run OCR, scan malware, persist records, or authorize real-document processing.
Callers must complete bounded ingestion and decoding, then provide local OCR results. Antivirus scanning is not selected or required in the local scope.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import validate_document_record
from .document_validation import DocumentValidationError, validate_document_consistency
from .ocr_adapter import OCRPageResult
from .semantic_proposals import SemanticProposalError, propose_common_fields


class AnalysisPipelineError(ValueError):
    """The source record and OCR observations cannot be safely combined."""


@dataclass(frozen=True)
class AnalysisResult:
    document: dict[str, Any]
    unapplied_proposals: dict[str, dict[str, object]]


def analyze_ocr_results(
    document: dict[str, Any], pages: Iterable[OCRPageResult]
) -> AnalysisResult:
    """Create an enriched copy without changing existing field candidates.

    Every inventoried page must have exactly one OCR result bound to the same
    source hash. New proposal fields are added as uncertain candidates. If a
    field already exists, its proposal is returned separately rather than
    replacing or silently combining with the existing value.
    """
    contract_issues = validate_document_record(document)
    if contract_issues:
        raise AnalysisPipelineError("record contract failed: " + "; ".join(contract_issues))

    processing = document["processing"]
    if any(not isinstance(processing.get(stage), dict) for stage in processing):
        raise AnalysisPipelineError("processing stages must be objects")
    if processing["ingestion"].get("status") != "completed":
        raise AnalysisPipelineError("ingestion must be completed before OCR analysis")
    if processing["ocr"].get("status") != "completed":
        raise AnalysisPipelineError("OCR must be completed before semantic analysis")

    materialized_pages = tuple(pages)
    if not materialized_pages:
        raise AnalysisPipelineError("at least one OCR page is required")
    if any(not isinstance(page, OCRPageResult) for page in materialized_pages):
        raise AnalysisPipelineError("pages must contain OCRPageResult values")
    source_hash = document["source"]["sha256"]
    if any(page.source_sha256 != source_hash for page in materialized_pages):
        raise AnalysisPipelineError("OCR page source hash must match the document")

    expected_pages = {
        item["page_number"] for item in document["pages"]
        if isinstance(item, dict) and isinstance(item.get("page_number"), int)
        and not isinstance(item.get("page_number"), bool)
    }
    actual_pages = {page.page_number for page in materialized_pages}
    if actual_pages != expected_pages:
        raise AnalysisPipelineError("OCR results must cover every inventoried page exactly once")

    try:
        proposals = propose_common_fields(materialized_pages, document_family=document["document_family"])
    except SemanticProposalError as exc:
        raise AnalysisPipelineError(f"OCR proposal validation failed: {exc}") from exc

    result_document = deepcopy(document)
    unapplied: dict[str, dict[str, object]] = {}
    for field_name, candidate in proposals.items():
        if field_name in result_document["fields"]:
            unapplied[field_name] = candidate
        else:
            result_document["fields"][field_name] = candidate

    try:
        findings = validate_document_consistency(result_document)
    except DocumentValidationError as exc:
        raise AnalysisPipelineError(f"document validation failed: {exc}") from exc

    result_document["validation_findings"] = findings
    result_document["processing"]["semantic_extraction"]["status"] = "completed"
    result_document["processing"]["document_validation"]["status"] = "completed"
    final_issues = validate_document_record(result_document)
    if final_issues:
        raise AnalysisPipelineError("analysis output contract failed: " + "; ".join(final_issues))
    return AnalysisResult(result_document, unapplied)

