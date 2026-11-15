"""Pages and helpers for editing the document-type catalog in the app (REQ-045).

A person who does not program adds a type with a short form: a name, the
words that identify it on the page, and one line per field
(``Etichetta: alias1, alias2 [data|importo|testo|codice] [obbligatorio]``).
The catalog itself stays the strict JSON validated by
``document_family_catalog``; every change keeps the previous file in
``catalog-history`` next to it, so earlier versions are never lost.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping

from .document_family_catalog import (
    DocumentFamilyCatalog,
    DocumentFamilyCatalogError,
    DocumentFamilyCatalogStore,
    load_custom_family_catalog,
)

CATALOG_FORM_MAX_BYTES = 16 * 1024
_TYPE_WORDS = {"testo": "text", "data": "date", "importo": "amount", "codice": "identifier"}
_TYPE_LABELS = {"text": "testo", "date": "data", "amount": "importo", "identifier": "codice"}


class CatalogFormError(ValueError):
    """The form cannot become a valid type; the message is shown to the person."""


def _slug(text: str, limit: int) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", folded).strip("_")
    if not slug or not slug[0].isalpha():
        slug = "t_" + slug
    return slug[:limit].rstrip("_")


def _split(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def family_from_form(*, label: str, title_cues: str, fields: str) -> dict[str, Any]:
    """Turn the add-type form into one catalog family (catalog format 2)."""
    label = label.strip()
    if not label:
        raise CatalogFormError("Scrivi il nome del tipo di documento.")
    cues = _split(title_cues)
    if not cues:
        raise CatalogFormError("Scrivi almeno una parola chiave che compare sul documento.")
    family_fields: list[dict[str, Any]] = []
    line_of_id: dict[str, int] = {}
    seen_aliases: set[str] = set()
    for number, raw in enumerate(fields.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        flags = re.findall(r"\[([^\]]+)\]", line)
        line = re.sub(r"\[[^\]]*\]", "", line).strip()
        if ":" not in line:
            raise CatalogFormError(f"Campo alla riga {number}: usa il formato «Etichetta: alias1, alias2».")
        field_label, aliases_text = (part.strip() for part in line.split(":", 1))
        aliases = _split(aliases_text)
        if not field_label or not aliases:
            raise CatalogFormError(f"Campo alla riga {number}: servono un'etichetta e almeno un alias.")
        field_id = _slug(field_label, 20)
        if field_id in line_of_id:
            raise CatalogFormError(
                f"I campi alle righe {line_of_id[field_id]} e {number} hanno etichette troppo simili: cambia una delle due."
            )
        line_of_id[field_id] = number
        for alias in aliases:
            if alias.casefold() in seen_aliases:
                raise CatalogFormError(f"L'alias «{alias}» compare in più campi: ogni alias va usato una sola volta.")
            seen_aliases.add(alias.casefold())
        field: dict[str, Any] = {"id": field_id, "label": field_label, "aliases": aliases}
        for flag in (item.strip().lower() for item in flags):
            if flag in _TYPE_WORDS:
                if _TYPE_WORDS[flag] != "text":
                    field["type"] = _TYPE_WORDS[flag]
            elif flag == "obbligatorio":
                field["required"] = True
            else:
                raise CatalogFormError(f"Campo alla riga {number}: «{flag}» non è un'opzione nota (usa data, importo, testo, codice, obbligatorio).")
        family_fields.append(field)
    return {"id": "custom_" + _slug(label, 24), "label": label, "title_cues": cues, "fields": family_fields}


def catalog_with_family(catalog: DocumentFamilyCatalog, family: Mapping[str, Any]) -> str:
    """JSON of ``catalog`` plus ``family``, in the catalog's own format.

    A type with the same id is refused. The format is kept: changing it would
    change the stored snapshot of every existing type.
    """
    if any(existing.id == family["id"] for existing in catalog.families):
        raise CatalogFormError("Esiste già un tipo con questo nome: scegline un altro.")
    if catalog.version == "1" and any("type" in field or "required" in field for field in family["fields"]):
        raise CatalogFormError(
            "Questo catalogo è nel formato 1, che non ammette tipi di campo né «obbligatorio»: "
            "togli le opzioni tra parentesi quadre oppure importa un catalogo nel formato 2."
        )
    payload = {"catalog_version": catalog.version, "families": [item.as_dict() for item in catalog.families] + [dict(family)]}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def explain_catalog_error(error: DocumentFamilyCatalogError) -> str:
    """An Italian sentence that says what to fix (the validator's text is technical)."""
    text = str(error).lower()
    if "limit" in text or "exceeds" in text or "too large" in text:
        return ("Il catalogo è troppo grande: al massimo 64 KB, 25 tipi, 20 campi per tipo, "
                "12 alias e 12 parole chiave.")
    if "json" in text or "utf-8" in text:
        return "Il file non è un catalogo valido (JSON non leggibile)."
    if "title cue" in text:
        return "Una parola chiave è ripetuta o è già usata da un altro tipo."
    if "alias" in text:
        return "Un alias è ripetuto all'interno di un tipo."
    if "duplicate family" in text:
        return "Due tipi hanno lo stesso nome."
    if "id is invalid or duplicated" in text or "colliding" in text:
        return "Due campi hanno etichette troppo simili."
    return "Il catalogo non è valido e non è stato salvato."


def save_with_history(
    store: DocumentFamilyCatalogStore, raw: str | bytes, current: DocumentFamilyCatalog | None = None,
) -> DocumentFamilyCatalog:
    """Validate and save ``raw``; after a successful save the replaced file goes to ``catalog-history``.

    A type that already exists with a different definition (or catalog format)
    is refused: processed documents keep the old definition, and a changed one
    under the same name would make their history ambiguous.
    """
    catalog = load_custom_family_catalog(raw)  # validate before touching any file
    if current is not None:
        existing = {family.id: family for family in current.families}
        for family in catalog.families:
            old = existing.get(family.id)
            if old is not None and (old.as_dict() != family.as_dict() or current.version != catalog.version):
                raise CatalogFormError(
                    f"Il tipo «{old.label}» esiste già con una definizione diversa. I documenti già elaborati "
                    "usano quella precedente: per cambiarlo, crea un tipo con un nome nuovo."
                )
    path = Path(store.path)
    previous = path.read_bytes() if path.is_file() and not path.is_symlink() else None
    store.save(raw)
    if previous is not None:
        history = path.parent / "catalog-history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (history / f"{stamp}-{hashlib.sha256(previous).hexdigest()[:12]}.json").write_bytes(previous)
    return catalog


def render_catalog_page(catalog: DocumentFamilyCatalog | None, *, message: str = "", error: str = "") -> str:
    """The catalog page: types, the add-type form, import and export."""
    rows = []
    for family in catalog.families if catalog is not None else ():
        fields = "".join(
            f"<li>{escape(field['label'])}: {escape(', '.join(field['aliases']))}"
            f" <small>({escape(_TYPE_LABELS.get(field['type'], field['type']))}"
            f"{', obbligatorio' if field['required'] else ''})</small></li>"
            for field in family.fields
        )
        rows.append(
            f"<li><strong>{escape(family.label)}</strong> — parole chiave: "
            f"{escape(', '.join(family.title_cues))}<ul>{fields}</ul></li>"
        )
    listing = f"<ul>{''.join(rows)}</ul>" if rows else "<p>Nessun tipo personalizzato. I tipi predefiniti (fattura, scontrino, …) sono sempre disponibili.</p>"
    notice = (f'<p role="status">{escape(message)}</p>' if message else "") + (
        f'<p role="alert">{escape(error)}</p>' if error else ""
    )
    version = f"<p><small>Impronta del catalogo: {escape(catalog.sha256[:12])}</small></p>" if catalog is not None else ""
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Catalogo dei tipi</title><main><p><a href=\"/\">Torna all'inizio</a></p>"
        "<h1>Catalogo dei tipi di documento</h1>" + notice + listing + version
        + "<h2>Aggiungi un tipo</h2>"
        '<form method="post" action="/catalog/families">'
        '<p><label>Nome del tipo <input name="label" required maxlength="80"></label></p>'
        '<p><label>Parole chiave sul documento, separate da virgola <input name="title_cues" required maxlength="400"></label></p>'
        '<p><label>Campi, uno per riga (es. «Targa: Targa, Veicolo [codice] [obbligatorio]»)'
        '<textarea name="fields" rows="6" cols="60" maxlength="4000"></textarea></label></p>'
        '<button type="submit">Aggiungi tipo</button></form>'
        "<h2>Importa o esporta</h2>"
        '<p><a href="/catalog/export">Esporta il catalogo (JSON)</a></p>'
        '<form method="post" action="/catalog/import" enctype="multipart/form-data">'
        '<label>File del catalogo <input type="file" name="files" accept=".json" required></label> '
        '<button type="submit">Importa e sostituisci</button></form>'
        "<p><small>Ogni modifica conserva la versione precedente del catalogo. I documenti già salvati "
        "mantengono la definizione del tipo con cui sono stati elaborati.</small></p></main></html>"
    )
