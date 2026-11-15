"""Run the synthetic case benchmark against a real local server and OCR worker.

Local only: it needs the approved Windows OCR runtime. From ``application/``::

    python -m tools.run_case_benchmark --fixtures DIR --work-dir DIR --out REPORT.json

The server runs as a child process with ``LOCALAPPDATA`` pointed at a fresh
folder inside ``--work-dir``, so the user's real archive is never opened. A
``sitecustomize`` hook in the child (and its OCR workers) records every
non-loopback connection or DNS attempt; the report holds only counts.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any
import uuid

from tools.case_benchmark_score import score_case_export

_HOOK = '''import os, socket
_LOG = os.environ["OCR2_BENCHMARK_NET_LOG"]
_LOOPBACK = ("127.0.0.1", "::1", "localhost", None)
def _w(kind):
    with open(_LOG, "a", encoding="ascii") as f:
        f.write(kind + "\\n")
_connect = socket.socket.connect
def connect(self, addr, *a, **k):
    host = addr[0] if isinstance(addr, tuple) else None
    if isinstance(addr, tuple) and host not in _LOOPBACK:
        _w("connect")
    return _connect(self, addr, *a, **k)
socket.socket.connect = connect
_gai = socket.getaddrinfo
def getaddrinfo(host, *a, **k):
    if host not in _LOOPBACK:
        _w("dns")
    return _gai(host, *a, **k)
socket.getaddrinfo = getaddrinfo
'''
_JOB_LINK = re.compile(r"/cases/[^/\"]+/jobs/([A-Za-z0-9]+)")
_PHASE = re.compile(r"Stato: ([^<]+)<")
_CHUNK = 20


class BenchmarkError(RuntimeError):
    """The benchmark could not complete; the message names the step."""


class _Client:
    def __init__(self, port: int):
        self.port = port
        self.origin = f"http://127.0.0.1:{port}"

    def request(self, method: str, path: str, body: bytes = b"", content_type: str = "") -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        headers = {"Host": f"127.0.0.1:{self.port}", "Origin": self.origin}
        if content_type:
            headers["Content-Type"] = content_type
        try:
            connection.request(method, path, body=body or None, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()


def _multipart(files: list[tuple[str, bytes]], fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "ocr2-benchmark-" + secrets.token_hex(8)
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for filename, data in files:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode() + data + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _start_server(python: str, application_dir: Path, work_dir: Path) -> tuple[subprocess.Popen, int, Path]:
    local_app_data = work_dir / "localappdata"
    hook_dir = work_dir / "hook"
    local_app_data.mkdir(parents=True)
    hook_dir.mkdir()
    real = os.environ.get("LOCALAPPDATA")
    if real and Path(real).resolve() == local_app_data.resolve():
        raise BenchmarkError("work directory resolves to the real LOCALAPPDATA")
    (hook_dir / "sitecustomize.py").write_text(_HOOK, encoding="utf-8")
    net_log = work_dir / "net.log"
    net_log.write_text("", encoding="ascii")
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(local_app_data)
    env["PYTHONPATH"] = os.pathsep.join([str(hook_dir), str(application_dir / "src")])
    env["OCR2_BENCHMARK_NET_LOG"] = str(net_log)
    # The server logs every request. Its output goes to a file: an undrained
    # pipe fills up and blocks the server mid-benchmark.
    server_log = work_dir / "server.log"
    with server_log.open("wb") as log:
        process = subprocess.Popen(
            [python, "-u", "-B", "-m", "alfa_document_intelligence", "--ocr-engine", "rapidocr-v6", "--port", "0"],
            cwd=str(application_dir), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and process.poll() is None:
        match = re.search(r"http://127\.0\.0\.1:(\d+)/", server_log.read_text(encoding="utf-8", errors="replace"))
        if match:
            return process, int(match.group(1)), net_log
        time.sleep(0.5)
    process.kill()
    raise BenchmarkError("server did not report a loopback port (runtime check failed or timed out)")


def run_case_benchmark(fixtures: Path, work_dir: Path, *, python: str = sys.executable) -> dict[str, Any]:
    """Drive one case through upload, OCR and export; return the numeric report."""
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    application_dir = Path(__file__).resolve().parents[1]
    if work_dir.exists() and any(work_dir.iterdir()):
        raise BenchmarkError("work directory must be empty")
    work_dir.mkdir(parents=True, exist_ok=True)
    process, port, net_log = _start_server(python, application_dir, work_dir)
    client = _Client(port)
    timings: dict[str, float] = {}
    try:
        case_id = "case-" + uuid.uuid4().hex + "0000"
        started = time.monotonic()
        body, content_type = _multipart([("statement.pdf", (fixtures / "statement.pdf").read_bytes())], {"_case_id": case_id})
        status, _ = client.request("POST", "/cases", body, content_type)
        if status != 201:
            raise BenchmarkError(f"case creation answered {status}")
        receipts = [item["file"] for item in manifest["receipts"]]
        for index in range(0, len(receipts), _CHUNK):
            status, snapshot = client.request("GET", f"/cases/{case_id}")
            revision = json.loads(snapshot)["case_revision"]
            files = [(Path(name).name, (fixtures / name).read_bytes()) for name in receipts[index:index + _CHUNK]]
            body, content_type = _multipart(files, {"_case_revision": revision, "_chunk_id": f"chunk-{index // _CHUNK + 1:02d}"})
            status, _ = client.request("POST", f"/cases/{case_id}/attachments", body, content_type)
            if status != 200:
                raise BenchmarkError(f"attachment chunk {index // _CHUNK + 1} answered {status}")
        timings["upload_seconds"] = round(time.monotonic() - started, 1)

        snapshot = json.loads(client.request("GET", f"/cases/{case_id}")[1])
        accepted = snapshot["attachment_count"]
        form = f"_case_revision={snapshot['case_revision']}".encode("ascii")
        started = time.monotonic()
        status, page = client.request("POST", f"/cases/{case_id}/process", form, "application/x-www-form-urlencoded")
        match = _JOB_LINK.search(page.decode("utf-8", "replace"))
        if status != 202 or not match:
            raise BenchmarkError(f"processing start answered {status}")
        job_path = f"/cases/{case_id}/jobs/{match.group(1)}"
        phase = ""
        while time.monotonic() - started < 1800:
            page = client.request("GET", job_path)[1].decode("utf-8", "replace")
            found = _PHASE.search(page)
            phase = found.group(1) if found else ""
            if phase not in {"In coda", "Elaborazione locale in corso", "Annullamento in corso"}:
                break
            time.sleep(2)
        timings["ocr_seconds"] = round(time.monotonic() - started, 1)
        pages = re.search(r"Pagine: (\d+)", page)
        if phase != "OCR completato":
            code = re.search(r"Codice: ([A-Za-z0-9_]+)", page)
            raise BenchmarkError(
                f"OCR job did not complete (phase {phase or 'unknown'}, code {code.group(1) if code else 'none'})"
            )

        status, exported = client.request("GET", f"/cases/{case_id}/export")
        if status != 200:
            raise BenchmarkError(f"export answered {status}")
        # Synthetic data only: kept in the work directory for diagnosis, never in evidence.
        (work_dir / "export.json").write_bytes(exported)
        score = score_case_export(json.loads(exported), manifest)
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
    attempts = net_log.read_text(encoding="ascii").split()
    report = {
        "fixtures_version": manifest["version"],
        "attachments_accepted": [accepted, len(receipts)],
        "pages_processed": int(pages.group(1)) if pages else None,
        **timings,
        "seconds_per_page": round(timings["ocr_seconds"] / int(pages.group(1)), 2) if pages and int(pages.group(1)) else None,
        "non_loopback_connect_attempts": attempts.count("connect"),
        "non_loopback_dns_attempts": attempts.count("dns"),
        "score": score,
    }
    shutil.rmtree(work_dir / "localappdata", ignore_errors=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable, help="interpreter with the approved OCR runtime")
    args = parser.parse_args()
    try:
        report = run_case_benchmark(args.fixtures, args.work_dir, python=args.python)
    except BenchmarkError as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
