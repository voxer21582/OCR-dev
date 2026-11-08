"""Optional adapter for an already-configured local RapidOCR engine.

This module does not construct RapidOCR, select or download models, or change
the application's default OCR-off behavior. The caller supplies an engine
whose recognition route is configured for a model covering Italian and English.
"""
from __future__ import annotations

import ctypes
import math
import re
from numbers import Real
from typing import Any, Callable

from .ocr_adapter import OCRToken, RasterPage


def _decode_rgb(page: RasterPage) -> Any:
    """Retained array decoder; recognize replaces this default with the RGB bridge."""
    import numpy as np

    expected = page.width_px * page.height_px * 3
    if len(page.image_bytes) != expected:
        raise ValueError("RasterPage must contain tightly packed RGB8 pixel bytes")
    return np.frombuffer(page.image_bytes, dtype=np.uint8).reshape(
        (page.height_px, page.width_px, 3)
    )


def _build_rgb_memory_image(page: RasterPage) -> tuple[Any, Any]:
    """Build RapidOCR 3.10's explicit RGB view and retain its backing buffer."""
    expected = page.width_px * page.height_px * 3
    if not isinstance(page.image_bytes, bytes) or len(page.image_bytes) != expected:
        raise ValueError("RasterPage must contain tightly packed RGB8 pixel bytes")
    if page.width_px < 1 or page.height_px < 1:
        raise ValueError("page dimensions must be positive")

    # Delayed import keeps the engine optional and does not initialize or fetch
    # any models. RawMemoryImage avoids RapidOCR's OpenCV-style ndarray BGR path.
    from rapidocr.utils.load_image import RawMemoryImage

    buffer = ctypes.create_string_buffer(page.image_bytes, len(page.image_bytes))
    image = RawMemoryImage(
        address=ctypes.addressof(buffer),
        length=len(page.image_bytes),
        width=page.width_px,
        height=page.height_px,
        pixel_format="RGB",
        stride=page.width_px * 3,
    )
    return image, buffer


def _output_sequences(result: Any) -> tuple[Any, Any, Any]:
    if result is None:
        return (), (), ()
    boxes = getattr(result, "boxes", None)
    texts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if boxes is None and texts is None and scores is None:
        return (), (), ()

    values = (boxes, texts, scores)
    if any(
        value is None or isinstance(value, (str, bytes, dict))
        or not hasattr(value, "__len__") or not hasattr(value, "__iter__")
        for value in values
    ):
        raise ValueError("RapidOCR boxes, texts, and scores must be sequences")
    if not (len(boxes) == len(texts) == len(scores)):
        raise ValueError("RapidOCR boxes, texts, and scores do not align")
    return boxes, texts, scores


class RapidOCRAdapter:
    """Adapt RapidOCR's callable result into source-page OCR token observations.

    RapidOCR's current API reports four-point `boxes`, `txts`, and `scores`.
    For the selected `("it", "en")` pair, configure a compatible multilingual
    route such as PP-OCRv6 `multi`; a PP-OCRv6 `latin` route is not assumed.
    Engine creation and model provenance remain outside this class so merely
    importing this optional adapter cannot load a runtime or acquire a model.
    The default bridge requires RapidOCR 3.10 and declares RGB explicitly;
    injected image_decoder callbacks still return one engine-input object.
    """

    name = "RapidOCR"

    def __init__(
        self,
        engine: Callable[[Any], Any],
        version: str,
        *,
        image_decoder: Callable[[RasterPage], Any] = _decode_rgb,
    ) -> None:
        if not callable(engine):
            raise ValueError("a preconfigured local RapidOCR engine is required")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("RapidOCR version is required")
        if not callable(image_decoder):
            raise ValueError("image_decoder must be callable")
        if image_decoder is _decode_rgb:
            match = re.match(r"^(\d+)\.(\d+)(?:\.|$)", version)
            if match is None or tuple(map(int, match.groups())) < (3, 10):
                raise ValueError("RapidOCR RawMemoryImage input requires RapidOCR >=3.10")
        self.engine = engine
        self.version = version
        self.image_decoder = image_decoder

    def recognize(self, page: RasterPage, languages: tuple[str, ...]) -> tuple[OCRToken, ...]:
        if languages != ("it", "en"):
            raise ValueError("the configured RapidOCR multilingual route expects ('it', 'en')")
        if page.width_px < 1 or page.height_px < 1:
            raise ValueError("page dimensions must be positive")

        if self.image_decoder is _decode_rgb:
            image, image_owner = _build_rgb_memory_image(page)
            try:
                result = self.engine(image)
            finally:
                # The raw address stays valid throughout synchronous inference.
                del image_owner
        else:
            result = self.engine(self.image_decoder(page))
        boxes, texts, scores = _output_sequences(result)
        tokens: list[OCRToken] = []
        for index, (box, text, score) in enumerate(zip(boxes, texts, scores), start=1):
            if not isinstance(text, str) or not text.strip():
                raise ValueError("RapidOCR returned an empty or non-text token")
            try:
                points_list = []
                for point in box:
                    if isinstance(point, (str, bytes)) or len(point) != 2:
                        raise ValueError("each box point must contain exactly x and y")
                    x, y = point[0], point[1]
                    if (
                        isinstance(x, bool) or isinstance(y, bool)
                        or not isinstance(x, Real) or not isinstance(y, Real)
                    ):
                        raise ValueError("coordinates must be numeric values")
                    x, y = float(x), float(y)
                    if not math.isfinite(x) or not math.isfinite(y):
                        raise ValueError("coordinates must be finite values")
                    points_list.append((x, y))
                points = tuple(points_list)
            except ValueError:
                raise
            except (TypeError, IndexError, OverflowError) as exc:
                raise ValueError("RapidOCR boxes must contain x,y points") from exc
            if len(points) < 3 or any(
                not math.isfinite(x) or not math.isfinite(y) for x, y in points
            ):
                raise ValueError("RapidOCR boxes must contain finite polygons")
            normalized = tuple((x / page.width_px, y / page.height_px) for x, y in points)
            if score is None:
                confidence = None
            else:
                if isinstance(score, bool) or not isinstance(score, Real):
                    raise ValueError("RapidOCR confidence must be numeric")
                confidence = float(score)
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError("RapidOCR confidence must be finite and in [0, 1]")
            tokens.append(OCRToken(
                token_id=f"p{page.page_number}-t{index}",
                text=text,
                polygon=normalized,
                confidence=confidence,
            ))
        return tuple(tokens)
