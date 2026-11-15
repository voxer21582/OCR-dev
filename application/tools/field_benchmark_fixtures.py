"""Generate 60 synthetic receipts (30 Italian, 30 English) with known field values.

Each receipt has a merchant line, a document date, a document number, a VAT
registration number and a total with currency. Values come from a pure
function of the index, so two runs with the same Pillow version give the same
bytes. Usage, from ``application/``::

    python -m tools.field_benchmark_fixtures OUTPUT_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont

VERSION = "ocr2-field-benchmark-v1"
FIELDS = ("merchant_name", "issue_date", "document_number", "vat_registration_number", "total_amount", "currency")
_COUNT = 60
_SIZE = (1000, 520)
_FIXED_PDF_DATE = time.strptime("2026-11-01 00:00:00", "%Y-%m-%d %H:%M:%S")
_IT_FIRST = ("Trattoria", "Bar", "Albergo", "Farmacia", "Libreria", "Pasticceria")
_IT_SECOND = ("Centrale", "Del Porto", "Bella Vista", "San Marco", "Aurora")
_EN_FIRST = ("Corner", "Harbour", "Station", "Riverside", "Market", "Union")
_EN_SECOND = ("Coffee", "Books", "Hotel", "Pharmacy", "Bakery")


def _known(index: int) -> dict[str, Any]:
    italian = index % 2 == 0
    pick = index // 2
    first, second = (_IT_FIRST, _IT_SECOND) if italian else (_EN_FIRST, _EN_SECOND)
    merchant = f"{first[pick % len(first)]} {second[(pick // len(first)) % len(second)]}"
    day = pick % 28 + 1
    cents = (index * 6151) % 19000 + 150
    euros, rest = divmod(cents, 100)
    vat = f"{(index * 104729) % 10**11:011d}"
    if italian:
        number = f"2026/{index + 1:04d}"
        lines = [
            merchant,
            f"Data documento: {day:02d}/11/2026",
            f"Numero documento: {number}",
            f"P.IVA {vat}",
            f"Totale: EUR {euros},{rest:02d}",
        ]
    else:
        number = f"A-{1000 + index}"
        lines = [
            merchant,
            f"Invoice date: 2026-11-{day:02d}",
            f"Invoice No. {number}",
            f"VAT number: {vat}",
            f"Total: EUR {euros}.{rest:02d}",
        ]
    expected = {
        "merchant_name": merchant,
        "issue_date": f"2026-11-{day:02d}",
        "document_number": number,
        "vat_registration_number": vat,
        "total_amount": f"{euros}.{rest:02d}",
        "currency": "EUR",
    }
    return {"language": "it" if italian else "en", "lines": lines, "expected": expected}


def _image(lines: list[str]) -> Image.Image:
    image = Image.new("RGB", _SIZE, "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    for row, text in enumerate(lines):
        draw.text((50, 40 + row * 90), text, fill="black", font=font)
    return image


def _encode(image: Image.Image, suffix: str) -> bytes:
    buffer = io.BytesIO()
    if suffix == "pdf":
        image.save(buffer, "PDF", resolution=150.0, creationDate=_FIXED_PDF_DATE, modDate=_FIXED_PDF_DATE)
    else:
        image.save(buffer, "PNG")
    return buffer.getvalue()


def generate_field_benchmark(output_dir: Path) -> dict[str, Any]:
    """Write the receipts and ``manifest.json``; return the manifest."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    documents = []
    for index in range(_COUNT):
        known = _known(index)
        suffix = "pdf" if index % 4 >= 2 else "png"  # 30 PNG, 30 raster PDF
        name = f"receipt-{index + 1:03d}.{suffix}"
        data = _encode(_image(known["lines"]), suffix)
        (root / name).write_bytes(data)
        documents.append({
            "document_id": f"field-{index + 1:03d}", "file": name, "language": known["language"],
            "sha256": hashlib.sha256(data).hexdigest(), "expected": known["expected"],
        })
    manifest = {"version": VERSION, "fields": list(FIELDS), "documents": documents}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output_dir", type=Path)
    manifest = generate_field_benchmark(parser.parse_args().output_dir)
    print(f"{len(manifest['documents'])} receipts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
