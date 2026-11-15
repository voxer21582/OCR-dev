"""The synthetic invoice generator for the line-item measurement is consistent (REQ-053)."""
from __future__ import annotations

from decimal import Decimal

from tools.line_item_benchmark import generate


def test_invoices_have_items_whose_amounts_add_up(tmp_path):
    manifest = generate(tmp_path)
    assert len(manifest["documents"]) == 12
    for document in manifest["documents"]:
        assert (tmp_path / document["file"]).read_bytes().startswith(b"\x89PNG")
        assert 3 <= len(document["items"]) <= 6
        for item in document["items"]:
            assert Decimal(item["unit_price"]) * int(item["quantity"]) == Decimal(item["amount"])
        assert sum(Decimal(item["amount"]) for item in document["items"]) == Decimal(document["total"])
