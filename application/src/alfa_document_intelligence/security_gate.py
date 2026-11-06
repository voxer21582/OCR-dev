"""Fail-closed malware-scan gate contract; no scanner implementation is bundled."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import BinaryIO, Literal, Protocol
import zipfile

from .ingestion import (
    FileInventory,
    IngestionLimits,
    UploadInventory,
    _inventory_snapshot,
    _snapshot_stream,
)

Verdict = Literal["clean", "malicious", "unavailable"]


@dataclass(frozen=True)
class ScanReceipt:
    verdict: Verdict
    scanner_id: str
    scanner_version: str
    bytes_scanned: int
    sha256: str


class Scanner(Protocol):
    """Private scanner adapter; it must consume the entire non-seekable stream."""
    def scan(self, media_kind: str, stream: BinaryIO) -> ScanReceipt: ...


@dataclass(frozen=True)
class ScanRecord:
    source_sha256: str
    verdict: str
    scanner_id: str | None
    scanner_version: str | None
    bytes_scanned: int | None


@dataclass(frozen=True)
class SecurityGateResult:
    status: str
    inventory: UploadInventory
    scans: tuple[ScanRecord, ...]


class _HashingReader:
    """Read-only facade that measures exactly what the scanner consumes."""
    def __init__(self, stream: BinaryIO):
        self._stream = stream
        self._digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        block = self._stream.read(size)
        self.bytes_read += len(block)
        self._digest.update(block)
        return block

    def readinto(self, buffer: bytearray) -> int:
        block = self.read(len(buffer))
        buffer[:len(block)] = block
        return len(block)

    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def seek(self, *_: object) -> int:
        raise OSError("scanner stream is not seekable")


def _checked_scan(scanner: Scanner, item: FileInventory, stream: BinaryIO) -> ScanRecord:
    reader = _HashingReader(stream)
    try:
        receipt = scanner.scan(item.media_kind, reader)  # type: ignore[arg-type]
    except Exception:
        return ScanRecord(item.sha256, "unavailable", None, None, reader.bytes_read)
    if not isinstance(receipt, ScanReceipt):
        return ScanRecord(item.sha256, "unavailable", None, None, reader.bytes_read)
    valid_metadata = (
        isinstance(receipt.scanner_id, str) and bool(receipt.scanner_id.strip())
        and isinstance(receipt.scanner_version, str) and bool(receipt.scanner_version.strip())
        and isinstance(receipt.bytes_scanned, int) and not isinstance(receipt.bytes_scanned, bool)
        and isinstance(receipt.sha256, str)
    )
    if not valid_metadata or receipt.verdict not in {"clean", "malicious", "unavailable"}:
        return ScanRecord(item.sha256, "unavailable", None, None, reader.bytes_read)
    exact_stream = reader.bytes_read == item.byte_length and reader.hexdigest() == item.sha256
    exact_receipt = receipt.bytes_scanned == item.byte_length and receipt.sha256.lower() == item.sha256
    if not exact_stream or not exact_receipt:
        return ScanRecord(item.sha256, "unavailable", receipt.scanner_id, receipt.scanner_version, reader.bytes_read)
    return ScanRecord(item.sha256, receipt.verdict, receipt.scanner_id, receipt.scanner_version, reader.bytes_read)


def scan_stream_upload(
    stream: BinaryIO,
    filename: str,
    scanner: Scanner | None,
    limits: IngestionLimits = IngestionLimits(),
) -> SecurityGateResult:
    """Inventory and scan one bounded in-memory upload snapshot and its ZIP members."""
    snapshot, size, source_hash, prefix = _snapshot_stream(stream, limits)
    try:
        inventory = _inventory_snapshot(snapshot, filename, size, source_hash, prefix, limits)
        if scanner is None:
            return SecurityGateResult("pending_security_scan", inventory, ())

        records: list[ScanRecord] = []
        snapshot.seek(0)
        records.append(_checked_scan(scanner, inventory.source, snapshot))

        if inventory.archive:
            try:
                snapshot.seek(0)
                with zipfile.ZipFile(snapshot) as archive:
                    for item in inventory.documents:
                        with archive.open(item.name, "r") as member_stream:
                            records.append(_checked_scan(scanner, item, member_stream))
            except (OSError, zipfile.BadZipFile, KeyError, RuntimeError):
                records.append(ScanRecord(inventory.source.sha256, "unavailable", None, None, None))

        expected_scans = 1 + (len(inventory.documents) if inventory.archive else 0)
        if any(record.verdict == "malicious" for record in records):
            status = "blocked_security_scan"
        elif len(records) != expected_scans or any(record.verdict != "clean" for record in records):
            status = "pending_security_scan"
        else:
            status = "security_scan_clear"
        return SecurityGateResult(status, inventory, tuple(records))
    finally:
        snapshot.close()



def scan_upload(path: str | Path, scanner: Scanner | None, limits: IngestionLimits = IngestionLimits()) -> SecurityGateResult:
    """Path convenience wrapper; inventory and scans consume the same byte snapshot."""
    source_path = Path(path)
    if source_path.is_symlink() or not source_path.is_file():
        raise UploadRejected("upload must be a regular file")
    with source_path.open("rb") as stream:
        return scan_stream_upload(stream, source_path.name, scanner, limits)
