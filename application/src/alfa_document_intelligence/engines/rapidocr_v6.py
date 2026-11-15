"""Manifest of the approved RapidOCR 3.10.0 engine with the PP-OCRv6 small multilingual models."""
from __future__ import annotations

from ..ocr_engine_registry import EngineManifest
from ..rapidocr_runtime_factory import MODEL_ARTIFACTS, RAPIDOCR_VERSION

MANIFEST = EngineManifest(
    engine_id="rapidocr-v6",
    name="RapidOCR",
    version=RAPIDOCR_VERSION,
    languages=("it", "en"),
    license="Apache-2.0",
    artifacts=MODEL_ARTIFACTS,
    factory_ref="alfa_document_intelligence.rapidocr_runtime_factory:create_rapidocr_v6_multilingual_adapter",
    runtime_check_ref="alfa_document_intelligence.rapidocr_runtime_factory:check_rapidocr_runtime",
)
