"""Subprocess probe for ``test_rapidocr_runs_without_ffmpeg_dll`` (not a test module).

Prints one JSON line: where ``cv2`` was imported from, which FFmpeg DLLs sit in
that folder, and the text the pinned RapidOCR runtime reads from a synthetic
image.  The image is drawn here, so no document data is involved.
"""
from __future__ import annotations

import json
import os
import sys


def main() -> None:
    import cv2
    from PIL import Image, ImageDraw, ImageFont

    from alfa_document_intelligence.ocr_adapter import RasterPage
    from alfa_document_intelligence.rapidocr_runtime_factory import create_rapidocr_v6_multilingual_adapter

    image = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    draw.text((30, 25), "FATTURA N. 2024/0153", fill="black", font=font)
    draw.text((30, 120), "TOTALE EUR 1.234,50", fill="black", font=font)
    page = RasterPage(1, image.width, image.height, image.tobytes())
    tokens = create_rapidocr_v6_multilingual_adapter().recognize(page, ("it", "en"))
    folder = os.path.dirname(cv2.__file__)
    print(json.dumps({
        "cv2_folder": folder,
        "ffmpeg_dlls": sorted(n for n in os.listdir(folder) if n.lower().startswith("opencv_videoio_ffmpeg")),
        "texts": [token.text for token in tokens],
    }))


if __name__ == "__main__":
    sys.exit(main())
