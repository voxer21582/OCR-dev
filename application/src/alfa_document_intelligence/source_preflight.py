"""Privacy-minimal, bounded identification of a source document from bytes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .ingestion import _kind_from_header


class SourcePreflightRejected(ValueError):
    """A bounded byte preflight failed with a stable, non-sensitive code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SourcePreflight:
    """Immutable source identity: content digest, byte count, and signature kind."""

    sha256: str
    byte_count: int
    media_kind: str


def preflight_source_bytes(
    content: bytes,
    *,
    max_bytes: int,
    declared_extension: str | None = None,
) -> SourcePreflight:
    """Identify supported signature bytes without filesystem or decoder access.

    The declared extension is intentionally ignored; signature bytes determine
    the media kind. Only the digest, byte count, and recognized kind are returned.
    This does not validate the document's internal structure or decodability.
    """
    # Keep the parameter explicit to document that extensions never drive detection.
    _ = declared_extension
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise SourcePreflightRejected("invalid_limit")
    if not isinstance(content, bytes):
        raise SourcePreflightRejected("invalid_input")
    if not content:
        raise SourcePreflightRejected("empty_input")
    if len(content) > max_bytes:
        raise SourcePreflightRejected("content_too_large")
    media_kind = _kind_from_header(content[:1024])
    if media_kind is None:
        raise SourcePreflightRejected("unsupported_signature")
    return SourcePreflight(
        sha256=hashlib.sha256(content).hexdigest(),
        byte_count=len(content),
        media_kind=media_kind,
    )
