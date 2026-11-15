"""In-memory document decoding, OCR, and proposal orchestration."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Callable, Iterable

from .analysis_pipeline import AnalysisPipelineError, AnalysisProposalLimitError, analyze_ocr_results
from .document_family_catalog import DocumentFamilyCatalog
from .document_decoder import DecodeLimits, DecodedPage, DocumentDecodeError, iter_decoded_pages
from dataclasses import replace

from .ocr_adapter import OCRContractError, OCREngineAdapter, OCRPageResult, OCRToken, RasterPage, run_ocr
from .pdf_text_layer import PDF_TEXT_PRODUCER_NAME, extract_text_tokens, producer_version


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
        "image/gif": "gif",
        "image/bmp": "bmp",
    }.get(media_type)
    if media_kind is None:
        return _failed_copy(document, "unsupported_media_type")

    decoded_results: list[OCRPageResult] = []
    page_inventory: list[dict[str, int]] = []
    declared_page_count: int | None = None
    text_layer_pages = 0
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
            page_adapter = adapter
            if media_kind == "pdf":
                text_tokens = extract_text_tokens(source_bytes, decoded.raster.page_number)
                if text_tokens is not None:
                    page_adapter = _TextLayerAdapter(text_tokens)
                    text_layer_pages += 1
            if page_adapter is adapter:
                result = recognize_with_orientation(adapter, decoded.raster, source_sha256=source_hash)
            else:
                result = run_ocr(
                    page_adapter,
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
        # Every page's evidence names its own producer. The document-level
        # producer is the text layer only when no page needed the OCR engine.
        "producer": {
            "stage": "ocr",
            "name": PDF_TEXT_PRODUCER_NAME if text_layer_pages == declared_page_count else adapter.name,
            "version": producer_version() if text_layer_pages == declared_page_count else adapter.version,
        },
    }
    try:
        return analyze_ocr_results(prepared, decoded_results, custom_family_catalog=custom_family_catalog).document
    except AnalysisProposalLimitError as exc:
        prepared["processing"]["semantic_extraction"] = {
            "status": "failed", "error_code": exc.code,
        }
        return prepared
    except AnalysisPipelineError:
        prepared["processing"]["semantic_extraction"] = {
            "status": "failed",
            "error_code": "semantic_extraction_failed",
        }
        return prepared


_WEAK_TOKEN_COUNT = 1  # a page with no tokens at all is weak
_WEAK_MEAN_CONFIDENCE = 0.5
# Inverse maps from a point of the page rotated counter-clockwise by the key
# (in degrees) back to the original page, in normalized coordinates.
_BACK_TO_ORIGINAL = {
    90: lambda x, y: (1.0 - y, x),
    180: lambda x, y: (1.0 - x, 1.0 - y),
    270: lambda x, y: (y, 1.0 - x),
}


def _is_weak(result: OCRPageResult) -> bool:
    if result.status != "complete" or len(result.tokens) < _WEAK_TOKEN_COUNT:
        return True
    scores = [token.confidence for token in result.tokens if token.confidence is not None]
    return bool(scores) and sum(scores) / len(scores) < _WEAK_MEAN_CONFIDENCE


def _strength(result: OCRPageResult) -> float:
    if result.status != "complete" or not result.tokens:
        return 0.0
    scores = [token.confidence for token in result.tokens if token.confidence is not None]
    mean = sum(scores) / len(scores) if scores else 1.0
    return sum(len(token.text) for token in result.tokens) * mean


def recognize_with_orientation(
    adapter: OCREngineAdapter, raster: RasterPage, *, source_sha256: str,
    languages: tuple[str, ...] = ("it", "en"),
) -> OCRPageResult:
    """Recognize a page; if the upright pass is weak, also try 90/180/270 degrees (REQ-028).

    The strongest reading wins. Its boxes are mapped back to the original page,
    so evidence always points at the page as stored.
    """
    upright = run_ocr(adapter, (raster,), source_sha256=source_sha256, languages=languages)[0]
    if not _is_weak(upright):
        return upright
    # Best effort: any failure while trying a rotation keeps the upright reading.
    try:
        from PIL import Image

        image = Image.frombytes("RGB", (raster.width_px, raster.height_px), raster.image_bytes)
    except Exception:
        return upright
    best, best_angle = upright, 0
    for angle in (90, 180, 270):
        try:
            turned = image.rotate(angle, expand=True)
            candidate = run_ocr(
                adapter,
                (RasterPage(raster.page_number, turned.width, turned.height, turned.tobytes()),),
                source_sha256=source_sha256, languages=languages,
            )[0]
        except OCRContractError:
            raise  # an engine breaking the contract is never hidden
        except Exception:
            continue
        if _strength(candidate) > _strength(best):
            best, best_angle = candidate, angle
    if best_angle == 0:
        return upright
    back = _BACK_TO_ORIGINAL[best_angle]
    tokens = tuple(
        OCRToken(
            token_id=token.token_id, text=token.text, confidence=token.confidence,
            polygon=tuple(back(x, y) for x, y in token.polygon),
        )
        for token in best.tokens
    )
    return replace(best, tokens=tokens)


class _TextLayerAdapter:
    """Presents tokens read from a PDF text layer through the OCR contract."""

    name = PDF_TEXT_PRODUCER_NAME

    def __init__(self, tokens):
        self.version = producer_version()
        self._tokens = tuple(tokens)

    def recognize(self, page, languages):
        return list(self._tokens)


def _failed_copy(document: dict[str, Any], error_code: str) -> dict[str, Any]:
    failed = deepcopy(document)
    failed["processing"]["ocr"] = {"status": "failed", "error_code": error_code}
    return failed
