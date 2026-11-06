import tempfile
import io
import unittest
import zipfile
import struct
import zlib
import hashlib
from unittest.mock import patch
import alfa_document_intelligence.ingestion as ingestion
from pathlib import Path

from alfa_document_intelligence.ingestion import IngestionLimits, UploadRejected, inventory_upload, inventory_stream, inventory_batch, _safe_member_name

def _png_chunk(kind, data):
    return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")


def make_png(width=2, height=2, animated=False):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunks = [_png_chunk(b"IHDR", ihdr)]
    if animated:
        chunks.append(_png_chunk(b"acTL", struct.pack(">II", 2, 0)))
    chunks.extend([
        _png_chunk(b"IDAT", zlib.compress((b"\x00" + b"\x00" * (width * 3)) * height)),
        _png_chunk(b"IEND", b""),
    ])
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def make_webp(width=2, height=2, animated=False):
    flags = 0x02 if animated else 0
    payload = bytes([flags, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    chunk = b"VP8X" + len(payload).to_bytes(4, "little") + payload
    return b"RIFF" + (4 + len(chunk)).to_bytes(4, "little") + b"WEBP" + chunk


def make_jpeg(width=2, height=2):
    data = b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    return b"\xff\xd8\xff\xc0" + (len(data) + 2).to_bytes(2, "big") + data + b"\xff\xd9"


def make_tiff(pages, endian="little", short=False):
    order = b"II" if endian == "little" else b"MM"
    offsets = [8 + i * 30 for i in range(len(pages))]
    output = bytearray(order + (42).to_bytes(2, endian) + offsets[0].to_bytes(4, endian))
    for index, (width, height) in enumerate(pages):
        output.extend((2).to_bytes(2, endian))
        for tag, value in ((256, width), (257, height)):
            field_type = 3 if short else 4
            raw = value.to_bytes(2 if short else 4, endian) + (b"\x00\x00" if short else b"")
            output.extend(tag.to_bytes(2, endian) + field_type.to_bytes(2, endian) + (1).to_bytes(4, endian) + raw)
        next_offset = offsets[index + 1] if index + 1 < len(offsets) else 0
        output.extend(next_offset.to_bytes(4, endian))
    return bytes(output)


PNG = make_png()
PDF = b"%PDF-1.7\nsynthetic-only\n"
WEBP = make_webp()

class IngestionTests(unittest.TestCase):
    def make_file(self, folder, name, data):
        path = Path(folder) / name
        path.write_bytes(data)
        return path

    def make_zip(self, folder, entries):
        path = Path(folder) / "bundle.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return path

    def test_ingestion_limits_reject_non_positive_integer_values(self):
        for name in ("max_upload_bytes", "max_archive_entries", "chunk_bytes", "max_image_pixels", "max_tiff_pages"):
            for value in (0, -1, True):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        IngestionLimits(**{name: value})

    def test_compression_ratio_limit_must_be_finite_and_positive(self):
        for value in (0, -1, float("nan"), float("inf"), float("-inf"), True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite and positive"):
                    IngestionLimits(max_compression_ratio=value)


    def test_stream_inventory_accepts_nonseekable_upload_and_sanitizes_filename(self):
        class NonSeekable:
            def __init__(self, data):
                self._stream = io.BytesIO(data)

            def read(self, size=-1):
                return self._stream.read(size)

        result = inventory_stream(NonSeekable(PDF), r"C:\fakepath\scan.pdf")
        self.assertEqual(result.source.name, "scan.pdf")
        self.assertEqual(result.source.media_kind, "pdf")
        self.assertEqual(result.status, "pending_security_scan")
        self.assertEqual(result.source.sha256, hashlib.sha256(PDF).hexdigest())

    def test_stream_inventory_enforces_upload_size_and_bytes_contract(self):
        with self.assertRaisesRegex(UploadRejected, "upload exceeds"):
            inventory_stream(io.BytesIO(PDF), "scan.pdf", IngestionLimits(max_upload_bytes=4))
        with self.assertRaisesRegex(UploadRejected, "return bytes"):
            inventory_stream(io.StringIO("%PDF-1.7"), "scan.pdf")

    def test_pdf_is_hashed_and_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "scan.pdf", PDF))
        self.assertEqual(result.status, "pending_security_scan")
        self.assertFalse(result.archive)
        self.assertEqual(result.source.media_kind, "pdf")
        self.assertEqual(result.documents[0].sha256, result.source.sha256)


    def test_archive_hash_and_inventory_use_the_same_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_zip(folder, [("original.pdf", PDF)])
            original_bytes = source.read_bytes()
            original_hash = hashlib.sha256(original_bytes).hexdigest()
            replacement = Path(folder) / "replacement.zip"
            with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("replacement.pdf", PDF)
            replacement_bytes = replacement.read_bytes()
            original_inventory = ingestion._inventory_archive

            def replace_path_after_snapshot(snapshot, limits):
                source.write_bytes(replacement_bytes)
                return original_inventory(snapshot, limits)

            with patch.object(ingestion, "_inventory_archive", side_effect=replace_path_after_snapshot):
                result = inventory_upload(source)

        self.assertEqual(result.source.sha256, original_hash)
        self.assertEqual([item.name for item in result.documents], ["original.pdf"])


    def test_archive_entry_limit_counts_directories_before_indexing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "directory-heavy.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("one/", b"")
                archive.writestr("two/", b"")
                archive.writestr("receipt.pdf", PDF)
            with self.assertRaisesRegex(UploadRejected, "too many entries"):
                inventory_upload(path, IngestionLimits(max_archive_entries=2))

    def test_archive_preflight_rejects_multidisk_and_zip64_directory(self):
        for field_offset, value, message in (
            (4, 1, "multi-disk"),
            (10, 0xFFFF, "ZIP64"),
        ):
            with self.subTest(field_offset=field_offset):
                with tempfile.TemporaryDirectory() as folder:
                    path = self.make_zip(folder, [("receipt.pdf", PDF)])
                    data = bytearray(path.read_bytes())
                    eocd = data.rfind(b"PK\x05\x06")
                    data[eocd + field_offset:eocd + field_offset + 2] = value.to_bytes(2, "little")
                    path.write_bytes(data)
                    with self.assertRaisesRegex(UploadRejected, message):
                        inventory_upload(path)

    def test_zip_inventories_supported_files_without_extracting(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_zip(folder, [("one/receipt.pdf", PDF), ("photo.png", PNG)]))
            self.assertEqual([item.media_kind for item in result.documents], ["pdf", "png"])
            self.assertTrue(result.archive)
            self.assertFalse((Path(folder) / "one").exists())

    def test_webp_photo_signature_is_inventoried(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "photo.webp", WEBP))
        self.assertEqual(result.source.media_kind, "webp")
        self.assertEqual(result.status, "pending_security_scan")

    def test_zip_accepts_webp_photo_by_extension_and_signature(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_zip(folder, [("hotel/photo.webp", WEBP)]))
        self.assertEqual([item.media_kind for item in result.documents], ["webp"])

    def test_raster_dimensions_are_reported_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "photo.png", make_png(320, 200)))
        self.assertEqual((result.source.width_px, result.source.height_px, result.source.page_count), (320, 200, 1))
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, "large.png", make_png(4000, 4000))
            with self.assertRaisesRegex(UploadRejected, "pixel count"):
                inventory_upload(path, IngestionLimits(max_image_pixels=1_000_000))

    def test_jpeg_dimensions_are_inspected_from_bounded_header(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "photo.jpg", make_jpeg(640, 480)))
        self.assertEqual((result.source.width_px, result.source.height_px), (640, 480))

    def test_tiff_dimensions_and_page_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "multi.tiff", make_tiff([(40, 20), (10, 8)])))
        self.assertEqual((result.source.width_px, result.source.height_px, result.source.page_count), (40, 20, 2))
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, "multi.tiff", make_tiff([(40, 20), (10, 8)]))
            with self.assertRaisesRegex(UploadRejected, "page count"):
                inventory_upload(path, IngestionLimits(max_tiff_pages=1))

    def test_big_endian_tiff_short_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inventory_upload(self.make_file(folder, "photo.tiff", make_tiff([(640, 480)], endian="big", short=True)))
        self.assertEqual((result.source.width_px, result.source.height_px), (640, 480))

    def test_animated_rasters_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(UploadRejected, "animated PNG"):
                inventory_upload(self.make_file(folder, "animated.png", make_png(animated=True)))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(UploadRejected, "animated WebP"):
                inventory_upload(self.make_file(folder, "animated.webp", make_webp(animated=True)))

    def test_zip_rejects_webp_extension_signature_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("photo.webp", PNG)])
            with self.assertRaisesRegex(UploadRejected, "extension"):
                inventory_upload(path)

    def test_rejects_traversal_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("../outside.pdf", PDF)])
            with self.assertRaisesRegex(UploadRejected, "traversal"):
                inventory_upload(path)

    def test_rejects_windows_absolute_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("C:\\temp\\receipt.pdf", PDF)])
            with self.assertRaisesRegex(UploadRejected, "absolute"):
                inventory_upload(path)

    def test_rejects_extension_content_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("receipt.pdf", PNG)])
            with self.assertRaisesRegex(UploadRejected, "extension"):
                inventory_upload(path)

    def test_rejects_expansion_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("receipt.pdf", PDF)])
            limits = IngestionLimits(max_entry_uncompressed_bytes=4)
            with self.assertRaisesRegex(UploadRejected, "size limit"):
                inventory_upload(path, limits)

    def test_rejects_entry_count_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("a.pdf", PDF), ("b.pdf", PDF)])
            with self.assertRaisesRegex(UploadRejected, "too many"):
                inventory_upload(path, IngestionLimits(max_archive_entries=1))

    def test_rejects_empty_or_unsupported_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("notes.txt", b"synthetic")])
            with self.assertRaisesRegex(UploadRejected, "unsupported"):
                inventory_upload(path)

    def test_rejects_upload_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, "image.png", PNG)
            with self.assertRaisesRegex(UploadRejected, "upload exceeds"):
                inventory_upload(path, IngestionLimits(max_upload_bytes=4))

    def test_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.zip"
            link = zipfile.ZipInfo("link.pdf")
            link.create_system = 3
            link.external_attr = (0o120777 << 16)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(link, "target.pdf")
            with self.assertRaisesRegex(UploadRejected, "non-regular"):
                inventory_upload(path)

    def test_rejects_duplicate_casefolded_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("Receipt.pdf", PDF), ("receipt.PDF", PDF)])
            with self.assertRaisesRegex(UploadRejected, "duplicate"):
                inventory_upload(path)
    def test_rejects_relative_backslash_path(self):
        with self.assertRaisesRegex(UploadRejected, "backslash"):
            _safe_member_name("folder\\receipt.pdf")

    def test_rejects_total_expanded_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("a.pdf", PDF), ("b.pdf", PDF)])
            limits = IngestionLimits(max_archive_uncompressed_bytes=len(PDF) + 1)
            with self.assertRaisesRegex(UploadRejected, "expanded-size"):
                inventory_upload(path, limits)

    def test_rejects_extreme_compression_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "compressed.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("receipt.pdf", b"%PDF-1.7\\n" + b"A" * 12000)
            with self.assertRaisesRegex(UploadRejected, "compression ratio"):
                inventory_upload(path)
    def test_flags_exact_duplicate_documents_in_zip_without_dropping_them(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [("first.pdf", PDF), ("copy.pdf", PDF)])
            result = inventory_upload(path)
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(result.duplicate_content_sha256, (result.documents[0].sha256,))

    def test_batch_flags_duplicate_source_and_document_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            first = self.make_file(folder, "first.pdf", PDF)
            second = self.make_file(folder, "second.pdf", PDF)
            result = inventory_batch([first, second])
        self.assertEqual(result.duplicate_source_sha256, (result.uploads[0].source.sha256,))
        self.assertEqual(result.duplicate_document_sha256, (result.uploads[0].source.sha256,))
        self.assertEqual(len(result.uploads), 2)
    def test_rejects_malformed_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, "bad.zip", b"PK\\x03\\x04broken")
            with self.assertRaises(UploadRejected):
                inventory_upload(path)

    def test_zip_preflight_counts_central_records_when_eocd_count_is_forged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_zip(folder, [
                ("one.pdf", PDF),
                ("two.pdf", PDF),
                ("three.pdf", PDF),
            ])
            data = bytearray(path.read_bytes())
            eocd = data.rfind(b"PK\x05\x06")
            data[eocd + 8:eocd + 10] = (1).to_bytes(2, "little")
            data[eocd + 10:eocd + 12] = (1).to_bytes(2, "little")
            path.write_bytes(data)

            with patch.object(ingestion, "_inventory_archive") as build_index:
                with self.assertRaisesRegex(UploadRejected, "too many entries"):
                    inventory_upload(path, IngestionLimits(max_archive_entries=2))
                build_index.assert_not_called()

if __name__ == "__main__":
    unittest.main()
