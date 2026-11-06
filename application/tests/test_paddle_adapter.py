from types import SimpleNamespace

import pytest

from alfa_document_intelligence.ocr_adapter import OCRContractError, RasterPage, run_ocr
from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter


class FakeEngine:
    def __init__(self, results):
        self.results = results
        self.seen = []

    def predict(self, image):
        self.seen.append(image)
        return self.results


class FakeResult:
    def __init__(self, payload):
        self.json = {"res": payload}


def test_paddle_adapter_normalizes_polygons_and_binds_page():
    marker = object()
    engine = FakeEngine([
        FakeResult({
            "rec_texts": ["EUR 24,50"],
            "rec_scores": [0.91],
            "rec_polys": [[[10, 20], [50, 20], [50, 40], [10, 40]]],
        })
    ])
    adapter = PaddleOCRAdapter(engine, "3.7.0", image_decoder=lambda page: marker)
    page = RasterPage(3, 100, 80, b"synthetic")
    result = run_ocr(adapter, [page], source_sha256="a" * 64)[0]

    assert engine.seen == [marker]
    assert result.page_number == 3
    assert result.engine_name == "PaddleOCR"
    assert result.engine_version == "3.7.0"
    assert result.tokens[0].text == "EUR 24,50"
    assert result.tokens[0].polygon == (
        (0.1, 0.25), (0.5, 0.25), (0.5, 0.5), (0.1, 0.5)
    )


def test_paddle_adapter_accepts_json_string_and_detection_polygon_fallback():
    engine = FakeEngine([
        SimpleNamespace(json='{"res":{"rec_texts":["Hotel"],"rec_scores":[0.8],"dt_polys":[[[0,0],[20,0],[20,10],[0,10]]]}}')
    ])
    adapter = PaddleOCRAdapter(engine, "3.7.0", image_decoder=lambda page: None)
    tokens = adapter.recognize(RasterPage(1, 40, 20, b"data"), ("it", "en"))
    assert tokens[0].polygon[-2:] == ((0.5, 0.5), (0.0, 0.5))


def test_paddle_adapter_rejects_misaligned_arrays():
    engine = FakeEngine([FakeResult({
        "rec_texts": ["EUR 1"], "rec_scores": [], "rec_polys": []
    })])
    adapter = PaddleOCRAdapter(engine, "3.7.0", image_decoder=lambda page: None)
    with pytest.raises(ValueError, match="do not align"):
        adapter.recognize(RasterPage(1, 10, 10, b"data"), ("it", "en"))


def test_paddle_adapter_rejects_out_of_bounds_geometry_via_contract():
    engine = FakeEngine([FakeResult({
        "rec_texts": ["x"], "rec_scores": [0.5],
        "rec_polys": [[[0,0],[11,0],[11,1],[0,1]]],
    })])
    adapter = PaddleOCRAdapter(engine, "3.7.0", image_decoder=lambda page: None)
    with pytest.raises(OCRContractError, match="normalized"):
        run_ocr(adapter, [RasterPage(1, 10, 10, b"data")], source_sha256="b" * 64)


def test_paddle_adapter_requires_explicit_model_language_pair():
    adapter = PaddleOCRAdapter(FakeEngine([]), "3.7.0", image_decoder=lambda page: None)
    with pytest.raises(ValueError, match="expects"):
        adapter.recognize(RasterPage(1, 10, 10, b"data"), ("it",))
