"""Prepare a minimal, human-confirmed prompt for manual ChatGPT handoff."""
from __future__ import annotations

import json
from typing import Any, Mapping

from .expense_reports import validate_expense_report_bundle
from .review_ledger import verify_review_ledger


class ChatGPTHandoffError(ValueError):
    """A bundle has no eligible human-confirmed fields for a manual handoff."""


def _human_confirmed_fields(
    record: Mapping[str, Any], allowed_fields: frozenset[str]
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in record["review"]["events"]:
        if event.get("action") not in {"field_corrected", "alternative_selected"}:
            continue
        candidate = event.get("candidate")
        field_name = event.get("field_name")
        if (
            isinstance(field_name, str)
            and field_name in allowed_fields
            and isinstance(candidate, dict)
            and candidate.get("status") == "observed"
            and candidate.get("value") is not None
        ):
            latest[field_name] = candidate

    fields: dict[str, dict[str, Any]] = {}
    for field_name, candidate in sorted(latest.items()):
        page_numbers = sorted({
            item["page_number"]
            for item in candidate.get("evidence", [])
            if isinstance(item, dict)
            and isinstance(item.get("page_number"), int)
            and not isinstance(item.get("page_number"), bool)
        })
        fields[field_name] = {
            "value": candidate["value"],
            "evidence_pages": page_numbers,
        }
    return fields


def build_chatgpt_handoff_prompt(
    bundle: dict[str, Any],
    documents: Mapping[str, dict[str, Any]],
) -> str:
    """Build a copyable prompt from reviewed event values only.

    Source files, raw OCR text, filenames, identifiers, hashes, and unreviewed
    extracted candidates are intentionally excluded. No network call is made.
    """
    validate_expense_report_bundle(bundle, documents)
    verify_review_ledger(documents[bundle["note_document_id"]])

    sources = []
    note_id = bundle["note_document_id"]
    ordered_ids = [note_id, *[
        attachment["document_id"] for attachment in bundle["attachments"]
    ]]
    for index, document_id in enumerate(ordered_ids):
        record = documents[document_id]
        verify_review_ledger(record)
        role = "expense_note" if index == 0 else f"supporting_document_{index}"
        allowed_fields = (
            frozenset({
                "traveler_name", "trip_destination", "trip_purpose",
                "trip_start_date", "trip_end_date", "date_candidates",
                "total_amount", "currency",
            })
            if index == 0 else frozenset({
                "merchant_name", "supplier_name", "date_candidates", "issue_date",
                "check_in_date", "check_out_date", "total_amount", "currency",
                "taxable_base", "vat_amount", "vat_rate", "payment_amount", "tip_amount",
            })
        )
        fields = _human_confirmed_fields(record, allowed_fields)
        if fields:
            sources.append({
                "role": role,
                "verified_fields": fields,
            })
    if not sources:
        raise ChatGPTHandoffError(
            "No human-confirmed fields are available; review and confirm fields first."
        )

    data = json.dumps(sources, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "Aiutami a riscrivere in italiano una nota spese usando esclusivamente i "
        "valori strutturati confermati dal revisore nel JSON seguente. "
        "Non inventare, dedurre o correggere importi, date, esercente, IVA o valuta. "
        "Se i dati sono insufficienti o contraddittori, elenca i chiarimenti necessari "
        "e lascia il dato incerto. Non classificare una ricevuta POS come documento "
        "fiscale senza prova esplicita. Non approvare rimborsi, pagamenti o registrazioni. "
        "Restituisci: (1) una bozza della nota, (2) l'elenco dei valori usati con il "
        "ruolo documento e le pagine di evidenza, (3) i campi mancanti o i conflitti. "
        "Il testo restituito sarà una bozza da verificare contro gli originali.\n\n"
        "DATI CONFERMATI:\n"
        + data
    )
