"""Expense case review history as CSV, one event per row (REQ-089)."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from ..exporter_registry import ExporterManifest

MANIFEST = ExporterManifest(
    exporter_id="case-review-csv",
    label_it="Esporta cronologia revisioni (CSV)",
    applies_to="case",
    media_type="text/csv; charset=utf-8",
    suffix="csv",
    function_ref="alfa_document_intelligence.exporters.case_review_csv:export_case_review_csv",
)


def export_case_review_csv(case_id: str, reconciliation: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=("export_format_version", "case_id", "review_event_json"), lineterminator="\r\n",
    )
    writer.writeheader()
    for event in reconciliation["review_events"] or [None]:
        writer.writerow({
            "export_format_version": "ocr2-case-review-csv-v1",
            "case_id": case_id,
            "review_event_json": json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        })
    return output.getvalue()
