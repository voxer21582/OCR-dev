"""PaddleOCR adapter that converts engine observations to normalized OCR tokens.

The optional Pillow/NumPy dependencies are imported only when recognizing a
page. This module never constructs an engine or downloads models.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Iterable

from .ocr_adapter import OCRToken, RasterPage


def _decode_rgb(page: RasterPage) -> Any:
    """Decode tightly packed RGB8 pixels. The caller owns safe image decoding."""
    import numpy as np

    expected = page.width_px * page.height_px * 3
    if len(page.image_bytes) != expected:
        raise ValueError("RasterPage must contain tightly packed RGB8 pixel bytes")
    return np.frombuffer(page.image_bytes, dtype=np.uint8).reshape(
        (page.height_px, page.width_px, 3)
    )


def _result_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict):
        payload = payload.get("res", payload)
    elif isinstance(result, dict):
        payload = result.get("res", result)
    else:
        raise ValueError("Unexpected PaddleOCR result representation")
    if not isinstance(payload, dict):
        raise ValueError("PaddleOCR result payload must be an object")
    return payload


class PaddleOCRAdapter:
    """Adapt a preconfigured local PaddleOCR engine to the OCR contract.

    Engine construction, model acquisition, and decoder safety are deliberately
    outside this adapter. The supplied engine must already be configured for
    the selected local model and CPU/device policy.
    """

    name = "PaddleOCR"

    def __init__(
        self,
        engine: Any,
        version: str,
        *,
        image_decoder: Callable[[RasterPage], Any] = _decode_rgb,
    ) -> None:
        if engine is None:
            raise ValueError("a preconfigured local PaddleOCR engine is required")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("PaddleOCR version is required")
        self.engine = engine
        self.version = version
        self.image_decoder = image_decoder

    def recognize(
        self, page: RasterPage, languages: tuple[str, ...]
    ) -> tuple[OCRToken, ...]:
        if languages != ("it", "en"):
            raise ValueError("the configured PP-OCRv5 Latin model expects ('it', 'en')")
        if page.width_px < 1 or page.height_px < 1:
            raise ValueError("page dimensions must be positive")
        image = self.image_decoder(page)
        results = self.engine.predict(image)
        texts: list[Any] = []
        scores: list[Any] = []
        polygons: list[Any] = []
        for result in results:
            payload = _result_payload(result)
            result_texts = payload.get("rec_texts", [])
            result_scores = payload.get("rec_scores", [])
            result_polygons = payload.get("rec_polys", payload.get("dt_polys", []))
            def sequence(value: Any) -> bool:
                return not isinstance(value, (str, bytes, dict)) and hasattr(value, "__len__") and hasattr(value, "__iter__")

            if not all(sequence(value) for value in (result_texts, result_scores, result_polygons)):
                raise ValueError("PaddleOCR text, confidence, and geometry must be sequences")
            if not (len(result_texts) == len(result_scores) == len(result_polygons)):
                raise ValueError("PaddleOCR text, confidence, and geometry arrays do not align")
            texts.extend(result_texts)
            scores.extend(result_scores)
            polygons.extend(result_polygons)

        tokens: list[OCRToken] = []
        for index, (text, score, polygon) in enumerate(
            zip(texts, scores, polygons), start=1
        ):
            if not isinstance(text, str) or not text.strip():
                raise ValueError("PaddleOCR returned an empty or non-text token")
            points = []
            for point in polygon:
                if len(point) != 2:
                    raise ValueError("PaddleOCR polygon points must contain x and y")
                x, y = float(point[0]), float(point[1])
                if not math.isfinite(x) or not math.isfinite(y):
                    raise ValueError("PaddleOCR polygon coordinates must be finite")
                points.append((x / page.width_px, y / page.height_px))
            tokens.append(
                OCRToken(
                    token_id=f"p{page.page_number}-t{index}",
                    text=text,
                    polygon=tuple(points),
                    confidence=float(score),
                )
            )
        return tuple(tokens)
