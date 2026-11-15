"""A deterministic synthetic OCR engine for tests (REQ-023).

It "recognizes" one fixed token covering the page, needs no model and no
package, and is hidden from the launcher (``selectable=False``). It exists to
prove that an engine is added with new files only: this module and its test.
"""
from __future__ import annotations

from ..ocr_adapter import OCRToken, RasterPage
from ..ocr_engine_registry import EngineManifest

NAME = "synthetic-fixed"
VERSION = "1"

MANIFEST = EngineManifest(
    engine_id="synthetic-fixed",
    name=NAME,
    version=VERSION,
    languages=("it", "en"),
    license="Apache-2.0",
    artifacts=(),
    factory_ref="alfa_document_intelligence.engines.synthetic_fixed:create_adapter",
    runtime_check_ref=None,
    selectable=False,
)


class SyntheticFixedAdapter:
    """Returns the token ``SYNTHETIC`` over the whole page with confidence 1.0."""

    name = NAME
    version = VERSION

    def recognize(self, page: RasterPage, languages: tuple[str, ...]) -> list[OCRToken]:
        return [OCRToken(
            token_id=f"p{page.page_number}-t1",
            text="SYNTHETIC",
            polygon=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            confidence=1.0,
        )]


def create_adapter() -> SyntheticFixedAdapter:
    return SyntheticFixedAdapter()
