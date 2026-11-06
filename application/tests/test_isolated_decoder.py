import hashlib
import time

import pytest

from alfa_document_intelligence.document_decoder import (
    DecodeLimits,
    DecodedPage,
    DocumentDecodeError,
)
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.isolated_decoder import iter_decoded_pages_isolated


def _one_synthetic_page(source_bytes, media_kind, *, source_sha256, limits):
    del source_bytes, media_kind, source_sha256, limits
    yield DecodedPage(RasterPage(1, 1, 1, b"\x00\x00\x00"), 1)


def _failing_decoder(source_bytes, media_kind, *, source_sha256, limits):
    del source_bytes, media_kind, source_sha256, limits
    raise DocumentDecodeError("synthetic decode rejection")
    yield  # pragma: no cover


def _hanging_decoder(source_bytes, media_kind, *, source_sha256, limits):
    del source_bytes, media_kind, source_sha256, limits
    time.sleep(10)
    yield DecodedPage(RasterPage(1, 1, 1, b"\x00\x00\x00"), 1)


def _decode(decoder, *, timeout_seconds=5):
    data = b"synthetic decoder input"
    return list(iter_decoded_pages_isolated(
        data,
        "pdf",
        source_sha256=hashlib.sha256(data).hexdigest(),
        limits=DecodeLimits(),
        timeout_seconds=timeout_seconds,
        memory_limit_bytes=512 * 1024 * 1024,
        decoder=decoder,
    ))


def test_isolated_decoder_returns_pages_from_spawned_worker():
    pages = _decode(_one_synthetic_page)
    assert len(pages) == 1
    assert pages[0].page_count == 1
    assert pages[0].raster.image_bytes == b"\x00\x00\x00"


def test_isolated_decoder_preserves_expected_rejections():
    with pytest.raises(DocumentDecodeError, match="synthetic decode rejection"):
        _decode(_failing_decoder)


def test_isolated_decoder_terminates_worker_when_deadline_expires():
    with pytest.raises(DocumentDecodeError, match="timed out"):
        _decode(_hanging_decoder, timeout_seconds=3)


@pytest.mark.parametrize("timeout_seconds", [0, -1, float("inf"), True, 3601])
def test_isolated_decoder_rejects_invalid_timeout(timeout_seconds):
    with pytest.raises(ValueError, match="timeout_seconds"):
        list(iter_decoded_pages_isolated(
            b"x", "pdf", source_sha256="0" * 64,
            timeout_seconds=timeout_seconds,
        ))


@pytest.mark.parametrize("memory_limit_bytes", [0, 1024, True, 1.5])
def test_isolated_decoder_rejects_invalid_memory_limit(memory_limit_bytes):
    with pytest.raises(ValueError, match="memory_limit_bytes"):
        list(iter_decoded_pages_isolated(
            b"x", "pdf", source_sha256="0" * 64,
            memory_limit_bytes=memory_limit_bytes,
        ))
