import hashlib
import os
import subprocess
import sys
import time

import pytest

from alfa_document_intelligence.document_decoder import (
    DecodeLimits,
    DecodedPage,
    DocumentDecodeError,
)
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.isolated_decoder import iter_decoded_pages_isolated


def test_spawned_decoder_does_not_forward_direct_worker_output(tmp_path):
    script = '''
import hashlib
import os
from alfa_document_intelligence.document_decoder import DecodeLimits, DocumentDecodeError
from alfa_document_intelligence.isolated_decoder import iter_decoded_pages_isolated

def decoder(source_bytes, media_kind, *, source_sha256, limits):
    os.write(1, b"SYNTHETIC_PRIVATE_STDOUT\\n")
    os.write(2, b"SYNTHETIC_PRIVATE_STDERR\\n")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel32.WriteFile.restype = wintypes.BOOL
        marker = b"SYNTHETIC_NATIVE_HANDLE\\n"
        count = wintypes.DWORD()
        assert kernel32.WriteFile(kernel32.GetStdHandle(-12 & 0xffffffff), marker, len(marker),
                                  ctypes.byref(count), None)
        assert count.value == len(marker)
    raise DocumentDecodeError("synthetic rejection")
    yield

if __name__ == "__main__":
    data = b"synthetic input"
    try:
        list(iter_decoded_pages_isolated(data, "pdf", source_sha256=hashlib.sha256(data).hexdigest(),
                                        limits=DecodeLimits(), decoder=decoder, timeout_seconds=30))
    except DocumentDecodeError as exc:
        assert str(exc) == "synthetic rejection"
        print("rejected")
    else:
        raise AssertionError("expected rejection")
'''
    script_path = tmp_path / "direct_output_probe.py"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(script_path)], capture_output=True,
                            text=True, timeout=40, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == "rejected"
    assert result.stderr == ""


def test_output_isolation_with_closed_standard_descriptors(tmp_path):
    script = '''
import os
from alfa_document_intelligence.isolated_decoder import _isolate_worker_standard_output
os.close(1)
os.close(2)
_isolate_worker_standard_output()
assert os.write(1, b"synthetic") == 9
assert os.write(2, b"synthetic") == 9
if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    count = wintypes.DWORD()
    assert kernel32.WriteFile(kernel32.GetStdHandle(-12 & 0xffffffff), b"synthetic", 9,
                              ctypes.byref(count), None)
    assert count.value == 9
'''
    script_path = tmp_path / "closed_output_probe.py"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(script_path)], capture_output=True,
                            timeout=30, check=False)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_isolation_replaces_python_streams_bound_to_the_old_handle(tmp_path, stream):
    # M8: launched from a console window, the worker's sys.stdout/sys.stderr
    # stay console objects writing through the redirected descriptor. Their
    # final flush then fails and the worker exits with status 120 after a
    # successful result, which the manager reports as worker_protocol_failed.
    # The synthetic stream below fails like such a console object.
    script = f'''
import io, sys
from alfa_document_intelligence.isolated_decoder import _isolate_worker_standard_output

class LostConsole(io.RawIOBase):
    def writable(self):
        return True
    def write(self, data):
        raise OSError(6, "synthetic invalid handle")

sys.{stream} = io.TextIOWrapper(io.BufferedWriter(LostConsole()), encoding="utf-8")
_isolate_worker_standard_output()
sys.{stream}.write("synthetic pending output without newline")
'''
    script_path = tmp_path / "console_stream_probe.py"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(script_path)], capture_output=True,
                            timeout=30, check=False)
    assert result.returncode == 0
    assert result.stdout == b""
    assert b"synthetic pending" not in result.stderr


def test_spawned_decoder_does_not_emit_pillow_runtime_path_on_corrupt_tiff(tmp_path):
    pytest.importorskip("PIL.Image")
    script = '''
import hashlib
from alfa_document_intelligence.document_decoder import DecodeLimits, DocumentDecodeError
from alfa_document_intelligence.isolated_decoder import iter_decoded_pages_isolated
if __name__ == "__main__":
    data = b"II\\x2a\\x00\\x08\\x00\\x00\\x00OCR2SYNTHETICMARKER0123456789"
    try:
        list(iter_decoded_pages_isolated(data, "tiff", source_sha256=hashlib.sha256(data).hexdigest(),
                                        limits=DecodeLimits(), timeout_seconds=30))
    except DocumentDecodeError:
        print("rejected")
    else:
        raise AssertionError("corrupt TIFF accepted")
'''
    script_path = tmp_path / "probe.py"
    script_path.write_text(script, encoding="utf-8")
    environment = dict(os.environ, PYTHONWARNINGS="always")
    result = subprocess.run([sys.executable, "-B", str(script_path)], env=environment,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == "rejected"
    assert result.stderr == ""


def test_spawned_ocr_worker_filters_pillow_warning_before_reading_input(tmp_path):
    script = '''
import multiprocessing
import os
import sys
import warnings
from pathlib import Path
from alfa_document_intelligence.ocr_processing import OCRProcessLimits, _ocr_worker_entry
class Receiver:
    def recv_bytes(self, **kwargs):
        os.write(1, b"SYNTHETIC_OCR_STDOUT\\n")
        os.write(2, b"SYNTHETIC_OCR_STDERR\\n")
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
            kernel32.GetStdHandle.restype = wintypes.HANDLE
            kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            kernel32.WriteFile.restype = wintypes.BOOL
            marker = b"SYNTHETIC_OCR_NATIVE\\n"
            count = wintypes.DWORD()
            assert kernel32.WriteFile(kernel32.GetStdHandle(-12 & 0xffffffff), marker, len(marker),
                                      ctypes.byref(count), None)
            assert count.value == len(marker)
        warnings.warn_explicit("synthetic warning", UserWarning, "synthetic-path.py", 1, module="PIL.synthetic")
        Path(sys.argv[1]).write_text("reached", encoding="ascii")
        raise EOFError()
    def close(self): pass
class Sender:
    def close(self): pass
class Gate:
    def wait(self): pass
if __name__ == "__main__":
    limits = OCRProcessLimits(60, 2, 1024 * 1024 * 1024, 4096, 4096, 4096, 4096, 4096, 20)
    process = multiprocessing.get_context("spawn").Process(
        target=_ocr_worker_entry, args=(Receiver(), Sender(), Gate(), "unused:factory", limits))
    process.start()
    process.join(30)
    assert process.exitcode == 0
'''
    script_path = tmp_path / "ocr_probe.py"
    script_path.write_text(script, encoding="utf-8")
    environment = dict(os.environ, PYTHONWARNINGS="always")
    marker_path = tmp_path / "worker_reached.txt"
    result = subprocess.run([sys.executable, "-B", str(script_path), str(marker_path)], env=environment,
                            capture_output=True, text=True, timeout=40, check=False)
    assert result.returncode == 0
    assert marker_path.read_text(encoding="ascii") == "reached"
    assert result.stdout == ""
    assert result.stderr == ""


def test_workers_fail_closed_if_output_isolation_fails(monkeypatch):
    from alfa_document_intelligence import isolated_decoder, ocr_processing

    def fail_isolation():
        raise OSError('SYNTHETIC_PRIVATE_ISOLATION_ERROR')

    class Gate:
        def wait(self): pass

    class Connection:
        def __init__(self):
            self.messages = []
            self.closed = False
            self.received = False
        def send(self, value): self.messages.append(value)
        def send_bytes(self, value): self.messages.append(value)
        def recv_bytes(self, **kwargs):
            self.received = True
            raise AssertionError('input must not be read')
        def close(self): self.closed = True

    invoked = []
    def decoder(*args, **kwargs):
        invoked.append(True)
        return iter(())

    monkeypatch.setattr(isolated_decoder, '_isolate_worker_standard_output', fail_isolation)
    output = Connection()
    isolated_decoder._decode_worker(output, Gate(), b'synthetic', 'pdf', '0' * 64,
                                    DecodeLimits(), decoder, 512 * 1024 * 1024, 5)
    assert not invoked
    assert output.messages == [('error', 'isolated document decoding failed')]
    assert output.closed

    monkeypatch.setattr(ocr_processing, '_apply_worker_os_limits', lambda limits: None)
    incoming, outgoing = Connection(), Connection()
    limits = ocr_processing.OCRProcessLimits(60, 2, 1024 * 1024 * 1024, 4096,
                                             4096, 4096, 4096, 4096, 20)
    ocr_processing._ocr_worker_entry(incoming, outgoing, Gate(), 'unused:factory', limits)
    assert not incoming.received
    assert incoming.closed and outgoing.closed
    assert outgoing.messages == []


def test_spawned_decoder_reports_isolation_failure_to_parent(tmp_path):
    script = '''
import hashlib
from pathlib import Path
import sys
from alfa_document_intelligence import isolated_decoder as isolated
from alfa_document_intelligence.document_decoder import DecodeLimits, DocumentDecodeError

def failed():
    Path(sys.argv[2]).write_text('reached', encoding='ascii')
    raise OSError('SYNTHETIC_PRIVATE_ISOLATION_ERROR')
def decoder(*args, **kwargs):
    Path(sys.argv[1]).write_text('unexpected', encoding='ascii')
    return iter(())
isolated._isolate_worker_standard_output = failed

if __name__ == '__main__':
    data = b'synthetic'
    try:
        list(isolated.iter_decoded_pages_isolated(data, 'pdf', source_sha256=hashlib.sha256(data).hexdigest(),
             limits=DecodeLimits(), decoder=decoder, timeout_seconds=30))
    except DocumentDecodeError as exc:
        assert str(exc) == 'isolated document decoding failed'
        print('rejected')
    else:
        raise AssertionError('worker unexpectedly succeeded')
'''
    script_path = tmp_path / 'isolation_failure_probe.py'
    script_path.write_text(script, encoding='utf-8')
    marker_path = tmp_path / 'unexpected_decoder.txt'
    failure_marker = tmp_path / 'isolation_failure_reached.txt'
    result = subprocess.run([sys.executable, '-B', str(script_path), str(marker_path), str(failure_marker)],
                            capture_output=True, text=True, timeout=40, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == 'rejected'
    assert result.stderr == ''
    assert not marker_path.exists()
    assert failure_marker.read_text(encoding='ascii') == 'reached'


@pytest.mark.skipif(os.name != 'nt', reason='Windows OCR worker uses a Job Object')
def test_ocr_supervisor_reports_spawned_isolation_failure(tmp_path):
    script = '''
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from alfa_document_intelligence import isolated_decoder
from alfa_document_intelligence.document_decoder import DecodeLimits
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.ocr_processing import OCRProcessLimits, OCRProcessingManager

def failed():
    Path(os.environ['OCR2_SYNTHETIC_FAILURE_MARKER']).write_text('reached', encoding='ascii')
    raise OSError('SYNTHETIC_PRIVATE_ISOLATION_ERROR')
isolated_decoder._isolate_worker_standard_output = failed

if __name__ == '__main__':
    intake = create_expense_report_intake_session(
        materialize_stream_batch([('synthetic.pdf', BytesIO(b'%PDF-1.7\\nsynthetic'))]),
        expense_report_id='synthetic-report', note_document_id='synthetic-doc',
        document_ids=['synthetic-doc'], session_id='synthetic-session',
        received_at='2026-11-11T10:00:00+00:00')
    limits = OCRProcessLimits(30, 2, 1024 * 1024 * 1024, 1024 * 1024,
                              4096, 1024 * 1024, 1024 * 1024, 4096, 100)
    manager = OCRProcessingManager('alfa_document_intelligence.rapidocr_runtime_factory:create_rapidocr_v6_multilingual_adapter', limits)
    try:
        job_id = manager.start('synthetic-generation', intake, decode_limits=DecodeLimits())
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            status = manager.snapshot(job_id)
            if status and status.phase in ('failed', 'cancelled', 'succeeded'):
                break
            time.sleep(.02)
        else:
            raise AssertionError('worker did not terminate')
        assert status.phase == 'failed'
        assert status.error_code == 'worker_protocol_failed'
        assert manager.result_frame('synthetic-generation', job_id) is None
        assert not manager._job.process.is_alive()
        print('rejected')
    finally:
        manager.close()
'''
    script_path = tmp_path / 'ocr_isolation_failure_probe.py'
    script_path.write_text(script, encoding='utf-8')
    failure_marker = tmp_path / 'ocr_isolation_failure_reached.txt'
    env = dict(os.environ, OCR2_SYNTHETIC_FAILURE_MARKER=str(failure_marker))
    result = subprocess.run([sys.executable, '-B', str(script_path)], env=env,
                            capture_output=True, text=True, timeout=40, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == 'rejected'
    assert result.stderr == ''
    assert failure_marker.read_text(encoding='ascii') == 'reached'


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
