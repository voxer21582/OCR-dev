"""Rotated pages are read by trying 90/180/270 degrees when the first pass is weak (REQ-028)."""
from __future__ import annotations

from alfa_document_intelligence.document_processing import recognize_with_orientation
from alfa_document_intelligence.ocr_adapter import OCRToken, RasterPage

_SHA = "a" * 64
_RED = b"\xff\x00\x00"
_WHITE = b"\xff\xff\xff"


def _page(marker: tuple[int, int], size: int = 4) -> RasterPage:
    pixels = bytearray(_WHITE * size * size)
    x, y = marker
    offset = (y * size + x) * 3
    pixels[offset:offset + 3] = _RED
    return RasterPage(1, size, size, bytes(pixels))


class _ReadsOnlyUpright:
    """Synthetic engine: reads three words only when the red marker is at the top-left pixel."""

    name = "Upright"
    version = "1"

    def __init__(self):
        self.calls = 0

    def recognize(self, page, languages):
        self.calls += 1
        if page.image_bytes[:3] != _RED:
            return []
        box = ((0.0, 0.0), (0.25, 0.0), (0.25, 0.5), (0.0, 0.5))
        return [OCRToken(f"t{i}", f"parola{i}", box, 0.9) for i in range(3)]


def test_upright_page_is_recognized_once():
    adapter = _ReadsOnlyUpright()
    result = recognize_with_orientation(adapter, _page((0, 0)), source_sha256=_SHA)
    assert adapter.calls == 1
    assert len(result.tokens) == 3
    assert result.tokens[0].polygon == ((0.0, 0.0), (0.25, 0.0), (0.25, 0.5), (0.0, 0.5))


def test_rotated_page_is_read_and_boxes_return_to_the_original_page():
    adapter = _ReadsOnlyUpright()
    # Marker at the top-right: the page content was turned 90 degrees clockwise.
    result = recognize_with_orientation(adapter, _page((3, 0)), source_sha256=_SHA)
    assert len(result.tokens) == 3
    xs = [x for x, _ in result.tokens[0].polygon]
    ys = [y for _, y in result.tokens[0].polygon]
    # The box near the rotated image's top-left lies near the original's top-right.
    assert (min(xs), max(xs)) == (0.5, 1.0)
    assert (min(ys), max(ys)) == (0.0, 0.25)
    assert result.page_number == 1


def test_unreadable_page_keeps_the_upright_result():
    class _NeverReads(_ReadsOnlyUpright):
        def recognize(self, page, languages):
            self.calls += 1
            return []

    adapter = _NeverReads()
    result = recognize_with_orientation(adapter, _page((1, 1)), source_sha256=_SHA)
    assert adapter.calls == 4
    assert result.tokens == ()


def test_engine_contract_violation_during_a_rotation_is_not_hidden():
    import pytest

    from alfa_document_intelligence.ocr_adapter import OCRContractError

    class _BreaksWhenTurned(_ReadsOnlyUpright):
        def recognize(self, page, languages):
            self.calls += 1
            if self.calls == 1:
                return []
            return [OCRToken("t1", "x", ((-1.0, 0.0), (0.5, 0.0), (0.5, 0.5)), 0.9)]

    with pytest.raises(OCRContractError):
        recognize_with_orientation(_BreaksWhenTurned(), _page((1, 1)), source_sha256=_SHA)


def test_blank_page_is_not_retried():
    class _NeverReads(_ReadsOnlyUpright):
        def recognize(self, page, languages):
            self.calls += 1
            return []

    adapter = _NeverReads()
    blank = RasterPage(1, 4, 4, _WHITE * 16)
    recognize_with_orientation(adapter, blank, source_sha256=_SHA)
    assert adapter.calls == 1


def test_engine_failure_during_a_rotation_is_not_swallowed():
    import pytest

    class _FailsWhenTurned(_ReadsOnlyUpright):
        def recognize(self, page, languages):
            self.calls += 1
            if self.calls == 1:
                return []
            raise RuntimeError("synthetic engine failure")

    with pytest.raises(RuntimeError):
        recognize_with_orientation(_FailsWhenTurned(), _page((1, 1)), source_sha256=_SHA)
