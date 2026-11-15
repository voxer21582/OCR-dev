"""Synthetic invoices with known line items, and a local OCR measurement (REQ-053).

From ``application/``::

    python -m tools.line_item_benchmark OUTPUT_DIR [--measure]

Without ``--measure`` it only writes the invoices and ``manifest.json``.
With ``--measure`` it also reads them with the registry's RapidOCR engine
through the app's processing path and prints a numbers-only report.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont

_COUNT = 12
_ITEMS = ("Consulenza", "Trasferta", "Materiale", "Licenza software", "Assistenza", "Formazione", "Noleggio sala")


def _invoice(index: int) -> dict[str, Any]:
    count = 3 + index % 4
    items = []
    for row in range(count):
        quantity = 1 + (index + row) % 3
        unit_cents = ((index + 1) * 977 + row * 1531) % 9000 + 500
        items.append({
            "description": _ITEMS[(index + row) % len(_ITEMS)],
            "quantity": str(quantity),
            "unit_price": f"{unit_cents // 100}.{unit_cents % 100:02d}",
            "amount": f"{(unit_cents * quantity) // 100}.{(unit_cents * quantity) % 100:02d}",
        })
    total = sum(int(item["amount"].replace(".", "")) for item in items)
    return {"items": items, "total": f"{total // 100}.{total % 100:02d}"}


def _comma(value: str) -> str:
    return value.replace(".", ",")


def _render(invoice: dict[str, Any], index: int) -> bytes:
    image = Image.new("RGB", (1240, 900), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=30)
    draw.text((60, 40), f"Fattura n. 2026/{index + 1:03d}", fill="black", font=font)
    columns = (60, 640, 800, 1000)
    for x, text in zip(columns, ("Descrizione", "Qtà", "Prezzo", "Importo")):
        draw.text((x, 140), text, fill="black", font=font)
    y = 200
    for item in invoice["items"]:
        for x, text in zip(columns, (item["description"], item["quantity"], _comma(item["unit_price"]), _comma(item["amount"]))):
            draw.text((x, y), text, fill="black", font=font)
        y += 60
    draw.text((60, y + 30), "Totale", fill="black", font=font)
    draw.text((1000, y + 30), _comma(invoice["total"]), fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def generate(output_dir: Path) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    documents = []
    for index in range(_COUNT):
        invoice = _invoice(index)
        name = f"invoice-{index + 1:03d}.png"
        (root / name).write_bytes(_render(invoice, index))
        documents.append({"file": name, **invoice})
    manifest = {"version": "ocr2-line-item-benchmark-v1", "documents": documents}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _first(candidate: Any) -> Any:
    if not isinstance(candidate, dict):
        return None
    if candidate.get("status") == "observed":
        return candidate.get("value")
    alternatives = candidate.get("alternatives") or []
    return alternatives[0].get("value") if alternatives else None


def measure(output_dir: Path) -> dict[str, Any]:
    from importlib import import_module

    from alfa_document_intelligence.document_processing import process_document_record
    from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
    from alfa_document_intelligence.ingestion import materialize_stream_batch
    from alfa_document_intelligence.ocr_engine_registry import get_engine

    root = Path(output_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    engine = get_engine("rapidocr-v6")
    module_name, attribute = engine.factory_ref.split(":")
    adapter = getattr(import_module(module_name), attribute)()
    note = BytesIO()
    Image.new("RGB", (8, 8), "white").save(note, "PNG")
    counts = {"documents": 0, "item_count_correct": 0, "items_expected": 0, "items_found": 0,
              "amount_correct": 0, "description_correct": 0, "quantity_correct": 0, "unit_price_correct": 0,
              "sum_finding_matches": 0}
    started = time.monotonic()
    for document in manifest["documents"]:
        batch = materialize_stream_batch([("nota.png", BytesIO(note.getvalue())),
                                          (document["file"], BytesIO((root / document["file"]).read_bytes()))])
        intake = create_expense_report_intake_session(
            batch, expense_report_id="items", note_document_id="note", document_ids=["note", "invoice"],
            session_id="items", received_at="2026-11-15T00:00:00+00:00",
        )
        record = process_document_record(intake.documents["invoice"], intake.source_bytes["invoice"], adapter)
        found = record.get("line_items", [])
        expected = document["items"]
        counts["documents"] += 1
        counts["items_expected"] += len(expected)
        counts["items_found"] += len(found)
        counts["item_count_correct"] += int(len(found) == len(expected))
        for want, got in zip(expected, found):
            counts["amount_correct"] += int(_first(got["amount"]) == want["amount"])
            counts["description_correct"] += int(_first(got["description"]) == want["description"])
            counts["quantity_correct"] += int(_first(got["quantity"]) == want["quantity"])
            counts["unit_price_correct"] += int(_first(got["unit_price"]) == want["unit_price"])
        findings = [item for item in record.get("validation_findings", []) if item.get("rule_id") == "line-items-sum-total"]
        counts["sum_finding_matches"] += int(bool(findings) and findings[0]["message_code"] in {
            "line_items_sum_matches_total", "line_items_sum_matches_total_requires_review"})
    counts["seconds"] = round(time.monotonic() - started, 1)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args()
    generate(args.output_dir)
    if args.measure:
        print(json.dumps(measure(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
