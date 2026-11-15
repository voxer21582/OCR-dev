"""Measure per-field accuracy on the synthetic field benchmark with a real local OCR engine.

Local only (needs the approved runtime). From ``application/``::

    python -m tools.run_field_benchmark --fixtures DIR --out REPORT.json [--engine rapidocr-v6]

Each receipt goes through the same ingestion and ``process_document_record``
path as the app, in this process; the report holds only counts and rates.
"""
from __future__ import annotations

import argparse
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path
import time

from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.ocr_engine_registry import get_engine

from tools.field_benchmark_score import score_records


def run_field_benchmark(fixtures: Path, *, engine_id: str = "rapidocr-v6") -> dict:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    engine = get_engine(engine_id)
    module_name, attribute = engine.factory_ref.split(":")
    adapter = getattr(import_module(module_name), attribute)()
    records = {}
    failures = 0
    started = time.monotonic()
    for document in manifest["documents"]:
        data = (fixtures / document["file"]).read_bytes()
        batch = materialize_stream_batch([(document["file"], BytesIO(data))])
        intake = create_expense_report_intake_session(
            batch, expense_report_id="field-benchmark", note_document_id=document["document_id"],
            document_ids=[document["document_id"]], session_id="field-benchmark",
            received_at="2026-11-15T00:00:00+00:00",
        )
        record = process_document_record(
            intake.documents[document["document_id"]], intake.source_bytes[document["document_id"]], adapter,
        )
        if record["processing"]["ocr"].get("status") != "completed":
            failures += 1
        records[document["document_id"]] = record
    return {
        "fixtures_version": manifest["version"],
        "engine": [engine.name, engine.version],
        "documents": len(manifest["documents"]),
        "ocr_failures": failures,
        "seconds": round(time.monotonic() - started, 1),
        "fields": score_records(manifest, records),
        "fields_by_language": {
            language: score_records(
                {"documents": [item for item in manifest["documents"] if item["language"] == language]}, records,
            )
            for language in ("it", "en")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--engine", default="rapidocr-v6")
    args = parser.parse_args()
    report = run_field_benchmark(args.fixtures, engine_id=args.engine)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["fields"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
