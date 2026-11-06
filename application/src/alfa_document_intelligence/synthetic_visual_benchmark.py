"""Generate a tiny, deterministic PDF corpus for synthetic OCR integration checks.

The fixtures are generated from hand-authored cases and are not representative of
real receipts, scans, cameras, or OCR performance. Evidence polygons use normalized
page coordinates with a top-left origin and refer to the generated source PDF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .benchmark_manifest import validate_manifest


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LABEL_VERSION = "synthetic-visual-v1"
_PRODUCER = {"stage": "human_review", "name": "synthetic-pdf-fixture", "version": "1"}

# (visible text, x, baseline y, font size, canonical field/value pairs)
_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "synthetic-invoice-visual-001", "split": "development",
        "document_family": "invoice", "language": "it", "group": "invoice-layout-a",
        "lines": (
            ("FATTURA - ESEMPIO SINTETICO", 48, 742, 18, {"document_evidence_class": "fiscal_document_evidence"}),
            ("ALBERGO ESEMPIO SRL", 48, 694, 14, {"merchant_name": "Albergo Esempio S.r.l."}),
            ("DATA 12/10/2026", 48, 650, 12, {"issue_date": "2026-10-12"}),
            ("TOTALE 123,45 EUR", 48, 118, 16, {"total_amount": "123.45", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-fiscal-receipt-visual-001", "split": "development",
        "document_family": "fiscal_receipt", "language": "it", "group": "fiscal-layout-b",
        "lines": (
            ("RICEVUTA FISCALE - DEMO", 34, 748, 15, {"document_evidence_class": "fiscal_document_evidence"}),
            ("CAFFE ALFA SRL", 34, 714, 12, {"merchant_name": "Caffe Alfa SRL"}),
            ("08/09/2026", 34, 678, 11, {"issue_date": "2026-09-08"}),
            ("TOTALE 18,00 EUR", 34, 72, 13, {"total_amount": "18.00", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-parking-visual-001", "split": "development",
        "document_family": "parking_receipt", "language": "it", "group": "parking-layout-c",
        "lines": (
            ("RICEVUTA PARCHEGGIO - DEMO", 42, 742, 15, {"document_evidence_class": "fiscal_document_evidence"}),
            ("PARCHEGGI BETA SPA", 42, 705, 12, {"merchant_name": "Parcheggi Beta SPA"}),
            ("DATA 09/09/2026", 42, 668, 11, {"issue_date": "2026-09-09"}),
            ("TOTALE 6,00 EUR", 42, 96, 13, {"total_amount": "6.00", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-hotel-visual-001", "split": "development",
        "document_family": "hotel_document", "language": "en", "group": "hotel-layout-d",
        "lines": (
            ("HOTEL INVOICE - SYNTHETIC", 48, 742, 17, {"document_evidence_class": "fiscal_document_evidence"}),
            ("EXAMPLE HOTEL LTD", 48, 700, 13, {"merchant_name": "Example Hotel Ltd"}),
            ("ISSUED 10 September 2026", 48, 658, 11, {"issue_date": "2026-09-10"}),
            ("TOTAL EUR 110.00", 48, 118, 15, {"total_amount": "110.00", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-pos-visual-001", "split": "development",
        "document_family": "pos_slip", "language": "it", "group": "pos-layout-e",
        "lines": (
            ("PAGAMENTO CARTA - NON FISCALE", 30, 748, 12, {"document_evidence_class": "payment_only_evidence"}),
            ("CORNER CAFE DEMO", 30, 708, 11, {"payment_recipient_role": "merchant"}),
            ("18/09/2026", 30, 674, 10, {}),
            ("PAGATO 18,00 EUR", 30, 78, 12, {"payment_amount": "18.00", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-parking-visual-regression-001", "split": "regression",
        "document_family": "parking_receipt", "language": "it", "group": "parking-layout-f",
        "lines": (
            ("SOSTA - RICEVUTA DEMO", 45, 740, 15, {"document_evidence_class": "fiscal_document_evidence"}),
            ("AREA SINTETICA NORD", 45, 704, 12, {"merchant_name": "Area Sintetica Nord"}),
            ("DATA 19/09/2026", 45, 668, 11, {"issue_date": "2026-09-19"}),
            ("TOTALE 4,50 EUR", 45, 96, 13, {"total_amount": "4.50", "currency": "EUR"}),
        ),
    },
    {
        "case_id": "synthetic-hotel-visual-frozen-001", "split": "independent_frozen",
        "document_family": "hotel_document", "language": "en", "group": "hotel-layout-g",
        "lines": (
            ("GUEST FOLIO - DEMO", 48, 742, 17, {"document_evidence_class": "fiscal_document_evidence"}),
            ("SYNTHETIC INN WEST", 48, 700, 13, {"merchant_name": "Synthetic Inn West"}),
            ("DATE 21 September 2026", 48, 658, 11, {"issue_date": "2026-09-21"}),
            ("TOTAL EUR 86.00", 48, 118, 15, {"total_amount": "86.00", "currency": "EUR"}),
        ),
    },
)


def _pdf_literal(text: str) -> bytes:
    raw = text.encode("ascii")
    escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def _pdf_for_case(case: dict[str, Any]) -> bytes:
    commands = []
    for text, x, y, size, _fields in case["lines"]:
        commands.append(f"BT /F1 {size} Tf {x} {y} Td ".encode("ascii") + _pdf_literal(text) + b" Tj ET\n")
    stream = b"".join(commands)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] ".encode("ascii")
         + b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def _evidence_polygon(text: str, x: int, baseline: int, size: int) -> list[list[float]]:
    # Conservative deterministic box around the simple Helvetica text run.
    left = x / PAGE_WIDTH
    right = min(PAGE_WIDTH, x + max(size * 0.72 * len(text), size)) / PAGE_WIDTH
    # PDF font metrics extend slightly beyond nominal em height; keep padding so
    # source glyph bounds remain inside their evidence region across renderers.
    top = (PAGE_HEIGHT - (baseline + size * 1.25)) / PAGE_HEIGHT
    bottom = (PAGE_HEIGHT - (baseline - size * 0.6)) / PAGE_HEIGHT
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


def build_visual_corpus(output_dir: Path) -> dict[str, Any]:
    """Write generated PDF inputs, evidence-linked labels, and a split manifest."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    documents_dir = output_dir / "documents"
    documents_dir.mkdir()
    records = []
    labels = []
    for case in _CASES:
        pdf = _pdf_for_case(case)
        digest = hashlib.sha256(pdf).hexdigest()
        (documents_dir / f"{case['case_id']}.pdf").write_bytes(pdf)
        fields: dict[str, str] = {}
        evidence: dict[str, list[dict[str, Any]]] = {}
        for text, x, y, size, line_fields in case["lines"]:
            for field, value in line_fields.items():
                fields[field] = value
                evidence[field] = [{
                    "source_sha256": digest,
                    "page_number": 1,
                    "region": {"coordinate_space": "normalized_page", "polygon": _evidence_polygon(text, x, y, size)},
                    "literal": text,
                    "producer": dict(_PRODUCER),
                }]
        labels.append({
            "case_id": case["case_id"], "split": case["split"],
            "document_family": case["document_family"], "fields": fields, "evidence": evidence,
        })
        records.append({
            "case_id": case["case_id"], "sha256": digest, "split": case["split"],
            "document_family": case["document_family"], "language": case["language"],
            "label_version": LABEL_VERSION,
            "group_keys": [hashlib.sha256(("synthetic-group:" + case["group"]).encode("ascii")).hexdigest()],
        })
    manifest = {"manifest_version": "1", "records": records}
    validate_manifest(manifest)
    (output_dir / "labels.jsonl").write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in labels), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return {"cases": len(records), "split_counts": {split: sum(r["split"] == split for r in records) for split in ("development", "regression", "independent_frozen")}, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="new or empty directory for synthetic PDFs and labels")
    args = parser.parse_args()
    try:
        result = build_visual_corpus(args.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"cases": result["cases"], "split_counts": result["split_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
