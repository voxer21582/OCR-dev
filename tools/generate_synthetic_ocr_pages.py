"""Generate seven authored synthetic text-only raster pages for OCR smoke tests."""
from __future__ import annotations

from pathlib import Path


SYNTHETIC_PAGES = (
    ("invoice-it", (
        "FATTURA",
        "FORNITORE: HOTEL AURORA",
        "N DOCUMENTO: 2026-001",
        "IMPONIBILE EUR 100.00",
        "IVA 22%",
        "TOTALE EUR 122.00",
    )),
    ("fiscal-receipt-it", (
        "RICEVUTA FISCALE",
        "ESERCENTE: CAFE ROMA",
        "DATA 14 10 2026",
        "TOTALE EUR 12.50",
    )),
    ("parking-receipt-it", (
        "RICEVUTA PARCHEGGIO",
        "INGRESSO 14 10 2026",
        "USCITA 14 10 2026",
        "TOTALE EUR 8.00",
    )),
    ("hotel-invoice-en", (
        "HOTEL INVOICE",
        "SUPPLIER: CITY HOTEL",
        "CHECK IN 12 10 2026",
        "CHECK OUT 14 10 2026",
        "TOTAL EUR 244.00",
    )),
    ("hotel-receipt-en", (
        "HOTEL RECEIPT",
        "MERCHANT: NORTH HOTEL",
        "DATE 14 10 2026",
        "TOTAL EUR 180.00",
    )),
    ("pos-payment-slip", (
        "CARD PAYMENT SLIP",
        "MERCHANT: CAFE ROMA",
        "DATE 14 10 2026",
        "AMOUNT EUR 12.50",
        "PAYMENT APPROVED",
    )),
    ("invoice-en", (
        "INVOICE",
        "SUPPLIER: ACME SERVICES",
        "INVOICE NUMBER A-2026-19",
        "TAXABLE BASE EUR 50.00",
        "VAT 22%",
        "GRAND TOTAL EUR 61.00",
    )),
)


def _load_synthetic_font(image_font_module):
    """Use Pillow's embedded, sized font so fixture generation is OS-independent."""
    try:
        return image_font_module.load_default(size=44)
    except TypeError as exc:
        raise RuntimeError("synthetic pages require Pillow 10.1 or newer") from exc


def generate_pages(output_dir: Path) -> tuple[Path, ...]:
    """Generate exactly seven clean synthetic pages into a fresh directory."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    from PIL import Image, ImageDraw, ImageFont

    pages = []
    for case_id, lines in SYNTHETIC_PAGES:
        page = Image.new("RGB", (1275, 1650), color=(250, 250, 248))
        drawing = ImageDraw.Draw(page)
        font = _load_synthetic_font(ImageFont)
        for index, line in enumerate(lines):
            drawing.text((90, 110 + index * 190), line, fill=(20, 20, 20), font=font)
        destination = output_dir / f"{case_id}.png"
        page.save(destination, format="PNG", optimize=False)
        page.close()
        pages.append(destination)
    if len(pages) != 7 or any(not path.is_file() or path.stat().st_size == 0 for path in pages):
        raise RuntimeError("synthetic page generation did not produce exactly seven PNGs")
    return tuple(pages)
