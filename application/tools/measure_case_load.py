"""Measure local synthetic case processing and HTTP response times under OCR load.

Run from application/ with generated synthetic fixtures and an empty work dir.
No network-observation claim is made; route timings exclude browser rendering.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import threading
import time

from tools import run_case_benchmark as bench


def summarize_route(rows: list[tuple[int, float]]) -> dict:
    successes = sorted(elapsed for status, elapsed in rows if status == 200)
    other = sorted({status for status, _ in rows if status != 200})
    return {
        'samples': len(rows), 'http_200': len(successes),
        'other_statuses': {str(status): sum(code == status for code, _ in rows) for status in other},
        'p95_ms': round(successes[math.ceil(.95 * len(successes)) - 1], 2) if successes else None,
        'max_ms': round(max(successes), 2) if successes else None,
    }


def measure(fixtures: Path, work_dir: Path, *, python: str) -> dict:
    original = bench._Client.request
    stop = threading.Event()
    observations: dict[str, list[tuple[int, float]]] = {'/': [], '/cases': []}
    errors: list[str] = []
    load_thread: threading.Thread | None = None

    def load(port: int) -> None:
        client = bench._Client(port)
        while not stop.is_set():
            for route in observations:
                try:
                    started = time.perf_counter()
                    status, _ = original(client, 'GET', route)
                    observations[route].append((status, (time.perf_counter() - started) * 1000))
                except Exception as exc:
                    errors.append(type(exc).__name__)
            stop.wait(.5)

    def observed_request(client, method, path, *args, **kwargs):
        nonlocal load_thread
        result = original(client, method, path, *args, **kwargs)
        if method == 'GET' and '/jobs/' in path:
            if load_thread is None and b'Elaborazione locale in corso' in result[1]:
                load_thread = threading.Thread(target=load, args=(client.port,), daemon=True)
                load_thread.start()
            if load_thread is not None and any(phase in result[1] for phase in (
                b'OCR completato', b'Elaborazione non riuscita', b'Elaborazione annullata',
            )):
                stop.set()
                load_thread.join(30)
        return result

    bench._Client.request = observed_request
    try:
        report = bench.run_case_benchmark(fixtures, work_dir, python=python, observe_network=False)
    finally:
        stop.set()
        if load_thread is not None:
            load_thread.join(30)
        bench._Client.request = original
    if load_thread is None or load_thread.is_alive() or errors:
        raise bench.BenchmarkError('HTTP load measurement did not complete cleanly')
    return {
        'routes': {route: summarize_route(rows) for route, rows in observations.items()},
        'pages_processed': report['pages_processed'], 'ocr_seconds': report['ocr_seconds'],
        'scope': 'synthetic HTTP GETs during OCR; p95 excludes errors and browser rendering',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()
    try:
        report = measure(args.fixtures, args.work_dir, python=args.python)
    except bench.BenchmarkError as exc:
        print(f'benchmark failed: {exc}', file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
