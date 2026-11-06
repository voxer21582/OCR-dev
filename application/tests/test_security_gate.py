import hashlib
import io
from unittest.mock import patch
import alfa_document_intelligence.security_gate as security_gate
import tempfile
import unittest
import zipfile
from pathlib import Path

from alfa_document_intelligence.security_gate import ScanReceipt, scan_upload, scan_stream_upload
from alfa_document_intelligence.ingestion import UploadRejected

PDF = b"%PDF-1.7\nsynthetic-only\n"

class FakeScanner:
    def __init__(self, verdict="clean", short_read=False):
        self.verdict = verdict
        self.short_read = short_read
        self.calls = []

    def scan(self, media_kind, stream):
        self.calls.append(media_kind)
        data = stream.read(4) if self.short_read else stream.read()
        return ScanReceipt(self.verdict, "synthetic-test-scanner", "0", len(data), hashlib.sha256(data).hexdigest())

class SecurityGateTests(unittest.TestCase):
    def write_pdf(self, folder):
        path = Path(folder) / "sample.pdf"
        path.write_bytes(PDF)
        return path


    def test_nonseekable_stream_is_inventoried_and_scanned(self):
        class NonSeekable:
            def __init__(self, data):
                self._stream = io.BytesIO(data)

            def read(self, size=-1):
                return self._stream.read(size)

        scanner = FakeScanner()
        result = scan_stream_upload(NonSeekable(PDF), r"C:\fakepath\scan.pdf", scanner)
        self.assertEqual(result.status, "security_scan_clear")
        self.assertEqual(result.inventory.source.name, "scan.pdf")
        self.assertEqual(scanner.calls, ["pdf"])

    def test_path_replacement_after_inventory_cannot_change_scanned_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("original.pdf", PDF)
            original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            replacement = Path(folder) / "replacement.zip"
            with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("replacement.pdf", b"%PDF-1.7\nreplacement\n")
            replacement_bytes = replacement.read_bytes()
            actual_scan = security_gate._checked_scan

            def replace_before_scan(scanner, item, stream):
                path.write_bytes(replacement_bytes)
                return actual_scan(scanner, item, stream)

            scanner = FakeScanner()
            with patch.object(security_gate, "_checked_scan", side_effect=replace_before_scan):
                result = scan_upload(path, scanner)

        self.assertEqual(result.status, "security_scan_clear")
        self.assertEqual(result.inventory.source.sha256, original_hash)
        self.assertEqual([item.name for item in result.inventory.documents], ["original.pdf"])
        self.assertEqual(scanner.calls, ["zip", "pdf"])

    def test_absent_scanner_stays_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            result = scan_upload(self.write_pdf(folder), None)
        self.assertEqual(result.status, "pending_security_scan")
        self.assertEqual(result.scans, ())

    def test_all_clean_results_clear_gate_only_after_exact_bytes_scanned(self):
        with tempfile.TemporaryDirectory() as folder:
            scanner = FakeScanner()
            result = scan_upload(self.write_pdf(folder), scanner)
        self.assertEqual(result.status, "security_scan_clear")
        self.assertEqual(scanner.calls, ["pdf"])
        self.assertEqual(result.scans[0].bytes_scanned, len(PDF))

    def test_malicious_result_blocks_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            result = scan_upload(self.write_pdf(folder), FakeScanner("malicious"))
        self.assertEqual(result.status, "blocked_security_scan")

    def test_unavailable_result_never_clears_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            result = scan_upload(self.write_pdf(folder), FakeScanner("unavailable"))
        self.assertEqual(result.status, "pending_security_scan")

    def test_partial_scan_never_clears_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            result = scan_upload(self.write_pdf(folder), FakeScanner(short_read=True))
        self.assertEqual(result.status, "pending_security_scan")
        self.assertEqual(result.scans[0].verdict, "unavailable")

    def test_invalid_scanner_identity_stays_pending(self):
        class InvalidMetadataScanner(FakeScanner):
            def scan(self, media_kind, stream):
                data = stream.read()
                return ScanReceipt("clean", "", "0", len(data), hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            result = scan_upload(self.write_pdf(folder), InvalidMetadataScanner())
        self.assertEqual(result.status, "pending_security_scan")
    def test_zip_scans_container_and_every_member(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("receipt.pdf", PDF)
            scanner = FakeScanner()
            result = scan_upload(path, scanner)
        self.assertEqual(result.status, "security_scan_clear")
        self.assertEqual(scanner.calls, ["zip", "pdf"])

if __name__ == "__main__":
    unittest.main()
