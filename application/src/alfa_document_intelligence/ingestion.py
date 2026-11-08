"""Bounded, non-extracting upload inventory for PDFs, raster images, and ZIP bundles."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from typing import BinaryIO, Iterable

from .image_safety import ImageHeaderError, ImageInfo, inspect_image_header


@dataclass(frozen=True)
class IngestionLimits:
    max_upload_bytes: int = 25 * 1024 * 1024
    max_archive_entries: int = 100
    max_archive_uncompressed_bytes: int = 100 * 1024 * 1024
    max_entry_uncompressed_bytes: int = 25 * 1024 * 1024
    max_compression_ratio: float = 100.0
    chunk_bytes: int = 64 * 1024
    max_image_header_bytes: int = 1024 * 1024
    max_image_dimension: int = 12_000
    max_image_pixels: int = 50_000_000
    max_tiff_pages: int = 100

    def __post_init__(self) -> None:
        integer_limits = (
            "max_upload_bytes", "max_archive_entries", "max_archive_uncompressed_bytes",
            "max_entry_uncompressed_bytes", "chunk_bytes", "max_image_header_bytes",
            "max_image_dimension", "max_image_pixels", "max_tiff_pages",
        )
        for name in integer_limits:
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        ratio = self.max_compression_ratio
        if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not math.isfinite(ratio) or ratio <= 0:
            raise ValueError("max_compression_ratio must be finite and positive")


@dataclass(frozen=True)
class FileInventory:
    name: str
    media_kind: str
    byte_length: int
    sha256: str
    width_px: int | None = None
    height_px: int | None = None
    page_count: int | None = None


@dataclass(frozen=True)
class UploadInventory:
    status: str
    source: FileInventory
    documents: tuple[FileInventory, ...]
    archive: bool
    duplicate_content_sha256: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchInventory:
    uploads: tuple[UploadInventory, ...]
    duplicate_source_sha256: tuple[str, ...]
    duplicate_document_sha256: tuple[str, ...]


class UploadRejected(ValueError):
    """Input failed a deterministic pre-OCR safety or format check."""


_MAGIC = {
    "webp_riff": b"RIFF",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "tiff_le": b"II*\x00",
    "tiff_be": b"MM\x00*",
}

_ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP_EOCD_MIN_SIZE = 22
_ZIP_EOCD_SEARCH_SIZE = _ZIP_EOCD_MIN_SIZE + 0xFFFF


def _preflight_zip_entry_count(stream: BinaryIO, max_entries: int) -> None:
    """Validate the complete central directory before ZipFile builds its index."""
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    tail_start = max(0, size - _ZIP_EOCD_SEARCH_SIZE)
    stream.seek(tail_start)
    tail = stream.read()
    position = tail.rfind(_ZIP_EOCD_SIGNATURE)
    eocd = None
    while position >= 0:
        if position + _ZIP_EOCD_MIN_SIZE <= len(tail):
            comment_length = int.from_bytes(tail[position + 20:position + 22], "little")
            if position + _ZIP_EOCD_MIN_SIZE + comment_length == len(tail):
                eocd = tail[position:position + _ZIP_EOCD_MIN_SIZE]
                break
        position = tail.rfind(_ZIP_EOCD_SIGNATURE, 0, position)
    if eocd is None:
        raise UploadRejected("invalid ZIP archive")
    if int.from_bytes(eocd[4:6], "little") != 0 or int.from_bytes(eocd[6:8], "little") != 0:
        raise UploadRejected("multi-disk ZIP archives are not supported")
    entries_on_disk = int.from_bytes(eocd[8:10], "little")
    total_entries = int.from_bytes(eocd[10:12], "little")
    central_size = int.from_bytes(eocd[12:16], "little")
    central_offset = int.from_bytes(eocd[16:20], "little")
    if 0xFFFF in (entries_on_disk, total_entries) or 0xFFFFFFFF in (central_size, central_offset):
        raise UploadRejected("ZIP64 archives are not supported")
    if entries_on_disk != total_entries:
        raise UploadRejected("multi-disk ZIP archives are not supported")
    if total_entries > max_entries:
        raise UploadRejected("archive contains too many entries")

    eocd_offset = tail_start + position
    central_start = eocd_offset - central_size
    if central_start < 0 or central_start < central_offset:
        raise UploadRejected("invalid ZIP central directory")
    central_end = eocd_offset
    entry_count = 0
    stream.seek(central_start)
    try:
        while stream.tell() < central_end:
            signature = stream.read(4)
            if signature == b"PK\x01\x02":
                header = signature + stream.read(42)
                if len(header) != 46:
                    raise UploadRejected("invalid ZIP central directory")
                name_length = int.from_bytes(header[28:30], "little")
                extra_length = int.from_bytes(header[30:32], "little")
                comment_length = int.from_bytes(header[32:34], "little")
                variable_length = name_length + extra_length + comment_length
                if stream.tell() + variable_length > central_end:
                    raise UploadRejected("invalid ZIP central directory")
                stream.seek(variable_length, os.SEEK_CUR)
                entry_count += 1
                if entry_count > max_entries:
                    raise UploadRejected("archive contains too many entries")
                continue
            if signature == b"PK\x05\x05":
                signature_length = stream.read(2)
                if len(signature_length) != 2:
                    raise UploadRejected("invalid ZIP central directory")
                signature_data_length = int.from_bytes(signature_length, "little")
                if stream.tell() + signature_data_length != central_end:
                    raise UploadRejected("invalid ZIP central directory")
                stream.seek(signature_data_length, os.SEEK_CUR)
                break
            raise UploadRejected("invalid ZIP central directory")
        if stream.tell() != central_end or entry_count != total_entries:
            raise UploadRejected("ZIP central directory entry count does not match its directory")
    finally:
        stream.seek(0)


_DRIVE_PREFIX = re.compile(r"^[a-zA-Z]:")
_ALLOWED_ENTRY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def _image_info(stream: BinaryIO, kind: str, limits: IngestionLimits) -> ImageInfo:
    header = stream.read(limits.max_image_header_bytes)
    try:
        return inspect_image_header(
            header,
            kind,
            max_header_bytes=limits.max_image_header_bytes,
            max_dimension=limits.max_image_dimension,
            max_pixels=limits.max_image_pixels,
            max_tiff_pages=limits.max_tiff_pages,
        )
    except ImageHeaderError as exc:
        raise UploadRejected(str(exc)) from exc


def _hash_stream(stream: BinaryIO, limit: int, chunk_bytes: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        block = stream.read(chunk_bytes)
        if not block:
            break
        size += len(block)
        if size > limit:
            raise UploadRejected("content exceeds configured size limit")
        digest.update(block)
    return size, digest.hexdigest()


def _kind_from_header(header: bytes) -> str | None:
    if len(header) >= 12 and header.startswith(_MAGIC["webp_riff"]) and header[8:12] == b"WEBP":
        return "webp"
    if header.startswith(b"%PDF-") or b"%PDF-" in header[:1024]:
        return "pdf"
    if header.startswith(_MAGIC["png"]):
        return "png"
    if header.startswith(_MAGIC["jpeg"]):
        return "jpeg"
    if header.startswith(_MAGIC["tiff_le"]) or header.startswith(_MAGIC["tiff_be"]):
        return "tiff"
    return None


def _safe_member_name(name: str) -> str:
    if not name or "\x00" in name:
        raise UploadRejected("archive contains an invalid member name")
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//") or _DRIVE_PREFIX.match(normalized):
        raise UploadRejected("archive contains an absolute member path")
    if "\\" in name:
        raise UploadRejected("archive contains an ambiguous backslash member path")
    path = PurePosixPath(normalized)
    if any(part in {"..", "."} for part in path.parts):
        raise UploadRejected("archive contains a traversal member path")
    if path.is_absolute() or not path.parts:
        raise UploadRejected("archive contains an invalid member path")
    return path.as_posix()


def _inventory_archive(source: BinaryIO, limits: IngestionLimits) -> tuple[tuple[FileInventory, ...], tuple[str, ...]]:
    documents: list[FileInventory] = []
    seen_names: set[str] = set()
    total_uncompressed = 0
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            file_infos = [info for info in infos if not info.is_dir()]
            if len(file_infos) > limits.max_archive_entries:
                raise UploadRejected("archive contains too many files")
            for info in infos:
                mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise UploadRejected("archive contains a non-regular file")
                if info.is_dir():
                    _safe_member_name(info.filename.rstrip("/"))
                    continue
                name = _safe_member_name(info.filename)
                key = name.casefold()
                if key in seen_names:
                    raise UploadRejected("archive contains duplicate member paths")
                seen_names.add(key)
                suffix = PurePosixPath(name).suffix.lower()
                if suffix == ".zip":
                    raise UploadRejected("nested ZIP archives are not supported")
                if suffix not in _ALLOWED_ENTRY_SUFFIXES:
                    raise UploadRejected("archive contains an unsupported file type")
                if info.flag_bits & 0x1:
                    raise UploadRejected("encrypted archive entries are not supported")
                if info.file_size < 0 or info.file_size > limits.max_entry_uncompressed_bytes:
                    raise UploadRejected("archive member exceeds configured size limit")
                total_uncompressed += info.file_size
                if total_uncompressed > limits.max_archive_uncompressed_bytes:
                    raise UploadRejected("archive exceeds configured expanded-size limit")
                compressed = max(info.compress_size, 1)
                if info.file_size / compressed > limits.max_compression_ratio:
                    raise UploadRejected("archive member exceeds configured compression ratio")
                try:
                    with archive.open(info, "r") as stream:
                        size, digest = _hash_stream(stream, limits.max_entry_uncompressed_bytes, limits.chunk_bytes)
                except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                    raise UploadRejected("archive member could not be safely read") from exc
                if size != info.file_size:
                    raise UploadRejected("archive member size does not match its directory entry")
                with archive.open(info, "r") as stream:
                    prefix = stream.read(1024)
                kind = _kind_from_header(prefix)
                if kind is None or (suffix == ".pdf" and kind != "pdf") or (suffix in {".jpg", ".jpeg"} and kind != "jpeg") or (suffix == ".png" and kind != "png") or (suffix == ".webp" and kind != "webp") or (suffix in {".tif", ".tiff"} and kind != "tiff"):
                    raise UploadRejected("archive member extension does not match supported file content")
                image = None
                if kind in {"png", "jpeg", "tiff", "webp"}:
                    with archive.open(info, "r") as stream:
                        image = _image_info(stream, kind, limits)
                documents.append(FileInventory(name, kind, size, digest, image.width_px if image else None, image.height_px if image else None, image.page_count if image else None))
    except zipfile.BadZipFile as exc:
        raise UploadRejected("invalid ZIP archive") from exc
    if not documents:
        raise UploadRejected("archive contains no supported documents")
    duplicates = tuple(sorted(value for value, count in Counter(item.sha256 for item in documents).items() if count > 1))
    return tuple(documents), duplicates


def _snapshot_stream(
    stream: BinaryIO,
    limits: IngestionLimits,
) -> tuple[io.BytesIO, int, str, bytes]:
    """Read one upload stream into a bounded in-memory byte snapshot."""
    if not hasattr(stream, "read"):
        raise UploadRejected("upload stream must provide read(n)")
    digest = hashlib.sha256()
    size = 0
    prefix = bytearray()
    snapshot = io.BytesIO()
    try:
        while True:
            try:
                block = stream.read(limits.chunk_bytes)
            except (OSError, ValueError) as exc:
                raise UploadRejected("upload stream could not be read") from exc
            if not isinstance(block, bytes):
                raise UploadRejected("upload stream must return bytes")
            if not block:
                break
            size += len(block)
            if size > limits.max_upload_bytes:
                raise UploadRejected("upload exceeds configured size limit")
            if len(prefix) < 1024:
                prefix.extend(block[:1024 - len(prefix)])
            digest.update(block)
            snapshot.write(block)
        snapshot.seek(0)
        return snapshot, size, digest.hexdigest(), bytes(prefix)
    except Exception:
        snapshot.close()
        raise


def _inventory_snapshot(
    snapshot: BinaryIO,
    filename: str,
    size: int,
    source_hash: str,
    prefix: bytes,
    limits: IngestionLimits,
) -> UploadInventory:
    """Inventory a previously bounded snapshot without making another copy."""
    if not isinstance(filename, str) or not filename or "\x00" in filename:
        raise UploadRejected("upload filename must be non-empty text")
    safe_name = PurePosixPath(filename.replace("\\", "/").rstrip("/")).name
    if not safe_name or safe_name in {".", ".."}:
        raise UploadRejected("upload filename must contain a basename")

    snapshot.seek(0)
    is_archive = zipfile.is_zipfile(snapshot)
    snapshot.seek(0)
    if is_archive:
        _preflight_zip_entry_count(snapshot, limits.max_archive_entries)
        snapshot.seek(0)
    source_kind = "zip" if is_archive else _kind_from_header(prefix)
    source = FileInventory(safe_name, source_kind or "unknown", size, source_hash)

    if source_kind == "zip":
        docs, duplicates = _inventory_archive(snapshot, limits)
        return UploadInventory("pending_security_scan", source, docs, True, duplicates)
    if source_kind is None:
        raise UploadRejected("unsupported or unrecognized file format")
    if source_kind in {"png", "jpeg", "tiff", "webp"}:
        snapshot.seek(0)
        image = _image_info(snapshot, source_kind, limits)
        source = FileInventory(source.name, source.media_kind, source.byte_length, source.sha256, image.width_px, image.height_px, image.page_count)
    return UploadInventory("pending_security_scan", source, (source,), False)


def inventory_stream(
    stream: BinaryIO,
    filename: str,
    limits: IngestionLimits = IngestionLimits(),
) -> UploadInventory:
    """Inventory a non-seekable upload stream without writing source bytes to disk."""
    snapshot, size, source_hash, prefix = _snapshot_stream(stream, limits)
    try:
        return _inventory_snapshot(snapshot, filename, size, source_hash, prefix, limits)
    finally:
        snapshot.close()

def inventory_upload(path: str | os.PathLike[str], limits: IngestionLimits = IngestionLimits()) -> UploadInventory:
    """Inventory a regular path through the same bounded stream contract."""
    source_path = Path(path)
    if source_path.is_symlink() or not source_path.is_file():
        raise UploadRejected("upload must be a regular file")
    with source_path.open("rb") as input_stream:
        return inventory_stream(input_stream, source_path.name, limits)


def inventory_batch(paths: Iterable[str | os.PathLike[str]], limits: IngestionLimits = IngestionLimits()) -> BatchInventory:
    """Inventory a batch and report exact-content duplicates without deleting or merging them."""
    uploads = tuple(inventory_upload(path, limits) for path in paths)
    sources = Counter(upload.source.sha256 for upload in uploads)
    documents = Counter(item.sha256 for upload in uploads for item in upload.documents)
    return BatchInventory(
        uploads=uploads,
        duplicate_source_sha256=tuple(sorted(value for value, count in sources.items() if count > 1)),
        duplicate_document_sha256=tuple(sorted(value for value, count in documents.items() if count > 1)),
    )

@dataclass(frozen=True)
class MaterializedDocument:
    """One supported source document held as bounded in-memory bytes."""

    inventory: FileInventory
    data: bytes


@dataclass(frozen=True)
class MaterializedUpload:
    """An upload container and its independent materialized documents."""

    inventory: UploadInventory
    documents: tuple[MaterializedDocument, ...]


@dataclass(frozen=True)
class MaterializedBatch:
    """A bounded multi-file session with duplicate hashes reported, not removed."""

    uploads: tuple[MaterializedUpload, ...]
    duplicate_source_sha256: tuple[str, ...]
    duplicate_document_sha256: tuple[str, ...]


def materialize_stream_upload(
    stream: BinaryIO,
    filename: str,
    limits: IngestionLimits = IngestionLimits(),
) -> MaterializedUpload:
    """Validate one stream and retain supported source/member bytes in memory.

    ZIP members are materialized only after the existing archive preflight and
    bounded inventory checks. No bytes are written to disk.
    """
    snapshot, size, source_hash, prefix = _snapshot_stream(stream, limits)
    try:
        upload_inventory = _inventory_snapshot(snapshot, filename, size, source_hash, prefix, limits)
        if not upload_inventory.archive:
            source = upload_inventory.documents[0]
            data = snapshot.getvalue()
            return MaterializedUpload(upload_inventory, (MaterializedDocument(source, data),))

        expected = {item.name: item for item in upload_inventory.documents}
        found: dict[str, bytes] = {}
        try:
            snapshot.seek(0)
            with zipfile.ZipFile(snapshot) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    name = _safe_member_name(info.filename)
                    metadata = expected.get(name)
                    if metadata is None:
                        continue
                    try:
                        with archive.open(info, "r") as member:
                            data = member.read(limits.max_entry_uncompressed_bytes + 1)
                    except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                        raise UploadRejected("archive member could not be materialized") from exc
                    if (
                        len(data) != metadata.byte_length
                        or hashlib.sha256(data).hexdigest() != metadata.sha256
                    ):
                        raise UploadRejected("archive member changed after bounded inventory")
                    found[name] = data
        except zipfile.BadZipFile as exc:
            raise UploadRejected("invalid ZIP archive") from exc

        if set(found) != set(expected):
            raise UploadRejected("archive member set changed after bounded inventory")
        documents = tuple(
            MaterializedDocument(item, found[item.name])
            for item in upload_inventory.documents
        )
        return MaterializedUpload(upload_inventory, documents)
    finally:
        snapshot.close()


def materialize_stream_batch(
    uploads: Iterable[tuple[str, BinaryIO]],
    limits: IngestionLimits = IngestionLimits(),
    *,
    max_batch_document_bytes: int = 100 * 1024 * 1024,
) -> MaterializedBatch:
    """Materialize a local multi-file upload session with a cumulative byte cap."""
    if (
        not isinstance(max_batch_document_bytes, int)
        or isinstance(max_batch_document_bytes, bool)
        or max_batch_document_bytes <= 0
    ):
        raise ValueError("max_batch_document_bytes must be a positive integer")

    materialized: list[MaterializedUpload] = []
    total_document_bytes = 0
    for filename, stream in uploads:
        item = materialize_stream_upload(stream, filename, limits)
        total_document_bytes += sum(len(document.data) for document in item.documents)
        if total_document_bytes > max_batch_document_bytes:
            raise UploadRejected("batch documents exceed configured in-memory limit")
        materialized.append(item)

    source_hashes = Counter(item.inventory.source.sha256 for item in materialized)
    document_hashes = Counter(
        document.inventory.sha256
        for item in materialized
        for document in item.documents
    )
    return MaterializedBatch(
        uploads=tuple(materialized),
        duplicate_source_sha256=tuple(sorted(
            digest for digest, count in source_hashes.items() if count > 1
        )),
        duplicate_document_sha256=tuple(sorted(
            digest for digest, count in document_hashes.items() if count > 1
        )),
    )
