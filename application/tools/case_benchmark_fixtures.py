"""Generate the synthetic expense-case benchmark: one statement and 100 receipts.

Everything is a pure function of the row/receipt index, so two runs with the
same Pillow version write byte-identical files. The known answers go to
``manifest.json`` next to the files. Usage, from ``application/``::

    python -m tools.case_benchmark_fixtures OUTPUT_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

VERSION = "ocr2-case-benchmark-v1"
_RECEIPTS = 100
_MATCHED = 95
_CONFLICTS = (10, 20, 30)
_UNSUPPORTED_ROWS = (("777,77", 5), ("888,88", 21), ("999,99", 7))
_ROWS_PER_PAGE = (25, 25, 24, 24)
_FIXED_PDF_DATE = time.strptime("2026-11-01 00:00:00", "%Y-%m-%d %H:%M:%S")  # Pillow default is "now"
_PAGE_SIZE = (1240, 1754)  # A4 at 150 dpi
_RECEIPT_SIZE = (620, 420)


def _cents(receipt: int) -> int:
    # 7919 is coprime with 9000, so every receipt gets a distinct amount
    # between 5,00 and 94,99.
    return (receipt * 7919) % 9000 + 500


def _amount(cents: int) -> str:
    return f"{cents // 100},{cents % 100:02d}"


def _day(receipt: int) -> int:
    return (receipt - 1) % 30 + 1


def _suffix(receipt: int) -> str:
    slot = (receipt - 1) % 20
    return ".png" if slot < 12 else ".jpg" if slot < 17 else ".pdf"


def _italian(day: int) -> str:
    return f"{day:02d}/11/2026"


def _iso(day: int) -> str:
    return f"2026-11-{day:02d}"


def _known_answers() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    used_cents = {_cents(n) for n in range(1, _RECEIPTS + 1)}
    for n in range(1, _RECEIPTS + 1):
        expected = "unused" if n > _MATCHED else "amount_conflict" if n in _CONFLICTS else "match"
        receipts.append({
            "receipt": n,
            "file": f"receipts/receipt-{n:03d}{_suffix(n)}",
            "date": _iso(_day(n)),
            "amount": _amount(_cents(n)),
            "expected": expected,
        })
        if n > _MATCHED:
            continue
        cents = _cents(n)
        if n in _CONFLICTS:
            cents += 111
            while cents in used_cents:
                cents += 1
        rows.append({"date": _iso(_day(n)), "amount": _amount(cents), "currency": "EUR", "receipt": n})
    for amount, day in _UNSUPPORTED_ROWS:
        rows.append({"date": _iso(day), "amount": amount, "currency": "EUR", "receipt": None})
    for index, row in enumerate(rows, 1):
        row["row"] = index
    return rows, receipts


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _receipt_image(item: dict[str, Any]) -> Image.Image:
    image = Image.new("RGB", _RECEIPT_SIZE, "white")
    draw = ImageDraw.Draw(image)
    font = _font(34)
    day = int(item["date"][-2:])
    lines = (f"Ricevuta {item['receipt']:03d}", f"Data: {_italian(day)}", f"Totale: EUR {item['amount']}")
    for index, text in enumerate(lines):
        draw.text((40, 50 + index * 110), text, fill="black", font=font)
    return image


def _statement_pages(rows: list[dict[str, Any]]) -> list[Image.Image]:
    pages: list[Image.Image] = []
    font = _font(28)
    start = 0
    for page_number, count in enumerate(_ROWS_PER_PAGE, 1):
        page = Image.new("RGB", _PAGE_SIZE, "white")
        draw = ImageDraw.Draw(page)
        draw.text((80, 60), f"Nota spese sintetica   Pagina {page_number} di {len(_ROWS_PER_PAGE)}", fill="black", font=font)
        for offset, row in enumerate(rows[start:start + count]):
            day = int(row["date"][-2:])
            y = 160 + offset * 62
            draw.text((80, y), _italian(day), fill="black", font=font)
            draw.text((330, y), f"Spesa {row['row']:03d}", fill="black", font=font)
            draw.text((900, y), f"EUR {row['amount']}", fill="black", font=font)
        pages.append(page)
        start += count
    return pages


def _pdf_bytes(images: list[Image.Image]) -> bytes:
    buffer = io.BytesIO()
    images[0].save(
        buffer, "PDF", resolution=150.0, save_all=True, append_images=images[1:],
        creationDate=_FIXED_PDF_DATE, modDate=_FIXED_PDF_DATE,
    )
    return buffer.getvalue()


def _encoded(image: Image.Image, suffix: str) -> bytes:
    if suffix == ".pdf":
        return _pdf_bytes([image])
    buffer = io.BytesIO()
    if suffix == ".jpg":
        image.save(buffer, "JPEG", quality=90)
    else:
        image.save(buffer, "PNG")
    return buffer.getvalue()


def generate_case_benchmark(output_dir: Path) -> dict[str, Any]:
    """Write the statement, the 100 receipts and ``manifest.json``; return the manifest."""
    root = Path(output_dir)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    rows, receipts = _known_answers()
    files: dict[str, str] = {}

    def write(name: str, data: bytes) -> None:
        (root / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()

    write("statement.pdf", _pdf_bytes(_statement_pages(rows)))
    for item in receipts:
        write(item["file"], _encoded(_receipt_image(item), Path(item["file"]).suffix))
    manifest = {"version": VERSION, "files": files, "statement_rows": rows, "receipts": receipts}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    manifest = generate_case_benchmark(args.output_dir)
    digest = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True).encode("utf-8")).hexdigest()
    print(f"{len(manifest['files'])} files written; files digest {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
