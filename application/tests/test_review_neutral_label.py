import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.local_intake_app import _render_editable_record
from alfa_document_intelligence.review_ledger import append_review_event


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
TIMESTAMP = "2026-10-14T10:00:00Z"


def _append(record, action, event_id, **kwargs):
    return append_review_event(
        record, actor_id="synthetic-reviewer", action=action,
        timestamp=TIMESTAMP, event_id=event_id, **kwargs,
    )


def _render(record):
    return _render_editable_record(record, document_id="synthetic-doc", has_source=False)


class ReviewNeutralLabelTests(unittest.TestCase):
    def test_review_labels_extracted_and_human_corrected_values_neutrally(self):
        record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        record["fields"]["merchant_name"]["value"] = "Originale <negozio>"
        record["fields"]["merchant_name"]["status"] = "uncertain"
        original = copy.deepcopy(record)
        opened = _append(_append(record, "queued", "queued-1"), "opened", "opened-1")

        page = _render(opened)
        assert "Valore verificato:" not in page
        assert "Valore corrente: Originale &lt;negozio&gt; (uncertain)" in page
        assert "Valore corrente: 2026-10-12 (observed)" in page
        assert "Originale <negozio>" not in page
        assert opened["fields"] == original["fields"]
        assert opened["source"] == original["source"]

        candidate = copy.deepcopy(opened["fields"]["merchant_name"])
        candidate["value"] = "Corretto <negozio>"
        candidate["status"] = "observed"
        corrected = _append(
            opened, "field_corrected", "corrected-1", field_name="merchant_name",
            reason_code="visual_correction", candidate=candidate,
        )
        page = _render(corrected)
        assert "Valore verificato:" not in page
        assert "Valore corrente: Corretto &lt;negozio&gt; (observed)" in page
        assert "Corretto <negozio>" not in page
        assert corrected["fields"] == original["fields"]
        assert corrected["source"] == original["source"]
        assert corrected["review"]["events"][-1]["candidate"] == candidate
        assert candidate["evidence"] == original["fields"]["merchant_name"]["evidence"]


