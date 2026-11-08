"""In-memory document decoding, OCR, and proposal orchestration."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Callable, Iterable

from .analysis_pipeline import AnalysisPipelineError, analyze_ocr_results
from .document_family_catalog import DocumentFamilyCatalog
from .document_decoder import DecodeLimits, DecodedPage, DocumentDecodeError, iter_decoded_pages
from .ocr_adapter import OCRContractError, OCREngineAdapter, OCRPageResult, run_ocr


Decoder = Callable[..., Iterable[DecodedPage]]


def process_document_record(
    document: dict[str, Any],
    source_bytes: bytes,
    adapter: OCREngineAdapter,
    *,
    decoder: Decoder = iter_decoded_pages,
    decode_limits: DecodeLimits = DecodeLimits(),
    custom_family_catalog: DocumentFamilyCatalog | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Process one materialized source in memory and return an evidence-bound copy.

    OCR and semantic proposals are completed only after every source page
    decodes and passes the OCR contract. A failed stage gets a non-sensitive
    error code; source bytes, model construction, and raw OCR output are never
    written to disk or sent over a network by this function.
    """
    from .contracts import validate_document_record

    initial_issues = validate_document_record(document)
    if initial_issues:
        raise ValueError("document record contract failed: " + "; ".join(initial_issues))
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValueError("source_bytes must be non-empty bytes")
    source = document["source"]
    source_hash = source["sha256"]
    if hashlib.sha256(source_bytes).hexdigest() != source_hash.lower():
        return _failed_copy(document, "source_hash_mismatch")

    media_type = source.get("media_type")
    media_kind = {
        "application/pdf": "pdf",
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/tiff": "tiff",
        "image/webp": "webp",
    }.get(media_type)
    if media_kind is None:
        return _failed_copy(document, "unsupported_media_type")

    decoded_results: list[OCRPageResult] = []
    page_inventory: list[dict[str, int]] = []
    declared_page_count: int | None = None
    try:
        pages = decoder(
            source_bytes,
            media_kind,
            source_sha256=source_hash,
            limits=decode_limits,
        )
        for decoded in pages:
            if not isinstance(decoded, DecodedPage):
                raise DocumentDecodeError("decoder returned an invalid page record")
            if declared_page_count is None:
                declared_page_count = decoded.page_count
                inventoried_count = source.get("page_count")
                if inventoried_count is not None and inventoried_count != declared_page_count:
                    raise DocumentDecodeError("decoded page count differs from inventory")
            elif decoded.page_count != declared_page_count:
                raise DocumentDecodeError("decoder page count changed during iteration")
            expected_page_number = len(decoded_results) + 1
            if decoded.raster.page_number != expected_page_number:
                raise DocumentDecodeError("decoded page numbering is not contiguous")
            result = run_ocr(
                adapter,
                (decoded.raster,),
                source_sha256=source_hash,
                languages=("it", "en"),
            )[0]
            decoded_results.append(result)
            page_inventory.append({
                "page_number": result.page_number,
                "width_px": decoded.raster.width_px,
                "height_px": decoded.raster.height_px,
            })
            if progress_callback is not None:
                progress_callback(expected_page_number, declared_page_count)
        if declared_page_count is None or len(decoded_results) != declared_page_count:
            raise DocumentDecodeError("decoder did not produce every declared page")
    except DocumentDecodeError:
        return _failed_copy(document, "decode_failed")
    except OCRContractError:
        return _failed_copy(document, "ocr_contract_failed")
    except Exception:
        return _failed_copy(document, "ocr_failed")

    prepared = deepcopy(document)
    prepared["source"]["page_count"] = declared_page_count
    prepared["pages"] = page_inventory
    prepared["processing"]["ocr"] = {
        "status": "completed",
        "producer": {
            "stage": "ocr",
            "name": adapter.name,
            "version": adapter.version,
        },
    }
    try:
        return analyze_ocr_results(prepared, decoded_results, custom_family_catalog=custom_family_catalog).document
    except AnalysisPipelineError:
        prepared["processing"]["semantic_extraction"] = {
            "status": "failed",
            "error_code": "semantic_extraction_failed",
        }
        return prepared


def _failed_copy(document: dict[str, Any], error_code: str) -> dict[str, Any]:
    failed = deepcopy(document)
    failed["processing"]["ocr"] = {"status": "failed", "error_code": error_code}
    return failed
