# M3 — Classificazione ed estrazione: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il catalogo dei tipi di documento è configurabile dall'utente (file ed editor) e usato dall'app; ogni campo mostra uno dei quattro stati di GOAL con il motivo, anche nell'export; il nome dell'esercente è proposto con evidenza; l'accuratezza è misurata su dati sintetici contro soglie fissate prima.

**Architecture:** il catalogo esistente (`document_family_catalog.py`, con `title_cues` come regole di classificazione) viene caricato dal launcher da un file per utente e modificato da nuove rotte dell'interfaccia. Un modulo `field_status.py` riconduce i sei stati interni ai quattro di GOAL. Il nome dell'esercente si aggiunge a `semantic_proposals.py`. La misura dell'accuratezza riusa l'impianto del benchmark di M1.

**Tech Stack:** Python 3.13, Pillow e pypdfium2 (approvati), RapidOCR per la sola misura locale.

**Spec:** [`docs/superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](../specs/2026-11-15-ocr2-product-completion-design.md); requisiti REQ-026 (sintetico), 041, 042, 045, 051, 052, 053, 055, 057, 060, 064 in [`docs/requirements.md`](../../requirements.md).

## Global Constraints

- Nessuna dipendenza nuova; solo dati sintetici generati da script.
- Nessuna conferma automatica: ogni proposta resta `uncertain` finché una persona decide.
- R7/R8: l'export CSV (Task 2) è R8; il file del catalogo non è l'archivio R7, ma la PR lo dichiara comunque. Merge solo con il sì del proprietario.
- Testi dell'interfaccia in italiano, comprensibili da chi non programma.
- Ogni modulo di test nuovo va in entrambi i job CI.
- Gli script di modifica vanno scritti in file (non incollati nel terminale: le barre rovesciate si perdono).

## Decisioni di ambito (registrate in `docs/decisions.md`)

- **REQ-053 (righe di fattura e tabelle, SHOULD)** rinviato a una milestone successiva: GOAL §1.5 chiede campi strutturati con evidenza, non tabelle; il costo è alto. Reversibile.
- **REQ-064 (regole di validazione versionate, SHOULD)** rinviato con lo stesso criterio.
- **Limite della riconciliazione da M1** (giustificativo avanzato proposto a righe dello stesso giorno): non esiste un criterio che distingua i due candidati senza inventare informazioni; resta una decisione di chi rivede, documentata nell'interfaccia. Nessun cambio di codice.
- **Tipi predefiniti** (fattura, scontrino…): le loro parole chiave restano nel codice come tassonomia di base (contratto CLS-4); le regole configurabili dall'utente sono quelle del catalogo (REQ-042).

## Review Focus

1. **Catalogo modificato dall'editor con un id di tipo già usato da record salvati:** i record esistenti devono restare leggibili con la loro istantanea; un tipo con lo stesso id e definizione diversa viene rifiutato.
2. **Catalogo non valido incollato o importato** (JSON rotto, troppo grande, alias duplicati): rifiuto con messaggio comprensibile, file sul disco invariato.
3. **Campo con stato interno raro** (`not_applicable`, `rejected`, `unreadable`): lo stato di GOAL e il motivo devono essere sempre presenti, mai vuoti.
4. **Nome dell'esercente su un documento senza intestazione** (prima riga = data o importo): nessuna proposta inventata.
5. **CSV con valori che iniziano con `=`, `+`, `-`, `@`** nelle nuove colonne: protezione dalle formule come per le colonne esistenti.

---

### Task 1: Stati dei campi secondo GOAL (REQ-060)

**Files:** Create `application/src/alfa_document_intelligence/field_status.py`; Test `application/tests/test_field_status.py`

**Interfaces — Produces:**
- `GOAL_STATUSES = ("valido", "incerto", "mancante", "non_valido", "non_applicabile")`
- `goal_status(candidate: dict, *, failed_rule_ids: frozenset[str] = frozenset()) -> tuple[str, str]`: stato e motivo in italiano.
  - `observed` senza regola fallita → `valido`, «letto dal documento»;
  - `observed` con una regola fallita sul campo → `non_valido`, «la verifica <rule_id> non è superata»;
  - `uncertain` → `incerto`, con il motivo: «più letture possibili: N» se ci sono alternative, altrimenti «lettura incerta»;
  - `absent` → `mancante`, «non trovato nel documento»;
  - `unreadable` → `mancante`, «presente ma illeggibile»;
  - `rejected` → `non_valido`, «scartato in revisione»;
  - `not_applicable` → `non_applicabile`, «non previsto per questo tipo di documento»;
  - stato sconosciuto → `incerto`, «stato non riconosciuto».
- `failed_rules_by_field(record: dict) -> dict[str, frozenset[str]]` dai `validation_findings` con esito `fail`.

- [ ] Test che falliscono: una tabella con tutti e sei gli stati più quello sconosciuto, il caso `observed` con una regola fallita, e il motivo mai vuoto. → FAIL → implementare → PASS → commit.

### Task 2: Stato e motivo nell'interfaccia e nel CSV (REQ-060, R8)

**Files:** Modify `review_ui.py` (tabella dei campi), `local_intake_app.py` (`_render_editable_record`), `document_export.py` (CSV); Test `test_field_status_presentation.py`

**Interfaces — Produces:**
- CSV versione `ocr2-document-csv-v2`, con le colonne `goal_status` e `goal_status_reason` dopo `field_name`;
- celle protette dalle formule con la funzione esistente;
- nella pagina, colonna «Stato» con l'etichetta italiana e il motivo.

- [ ] Test che falliscono:
  - il CSV di un record sintetico con un campo per stato ha le due colonne e i valori attesi;
  - un motivo che inizia con `=` viene neutralizzato;
  - l'HTML della revisione mostra «Incerto — più letture possibili: 2».
- [ ] Ciclo FAIL → PASS → commit, con «R7/R8: CSV export columns» nel messaggio.

### Task 3: Il catalogo caricato dall'app (REQ-041)

**Files:** Modify `__main__.py`; Test `test_ocr_launcher_contract.py`

**Interfaces — Produces:** il launcher crea `DocumentFamilyCatalogStore(%LOCALAPPDATA%\OCR2\family-catalog.json)`, carica il catalogo (vuoto se manca il file) e lo passa a `serve_expense_report_local(custom_family_catalog=...)` e ai gestori OCR. Se il catalogo non è valido, l'app parte senza catalogo e mostra l'avviso «catalogo dei tipi non valido: ignorato».

- [ ] Test che falliscono:
  - con un file valido nel `LOCALAPPDATA` temporaneo, il server riceve il catalogo;
  - con un file non valido, riceve `None` e viene stampato l'avviso.
- [ ] Ciclo FAIL → PASS → commit.

### Task 4: Editor del catalogo nell'interfaccia (REQ-045, REQ-042)

**Files:** Create `application/src/alfa_document_intelligence/catalog_editor.py` (pagine HTML e conversione dal modulo al JSON); Modify `local_intake_app.py` (rotte); Test `test_catalog_editor.py`

**Interfaces — Produces:**
- `GET /catalog`: elenco dei tipi (nome, parole chiave, campi), con un modulo «Aggiungi tipo» e i link «Esporta» e «Importa»;
- `POST /catalog/families`: aggiunge un tipo dal modulo, con questi campi:
  - `label`;
  - `title_cues`, parole chiave separate da virgola;
  - `fields`, una riga per campo nel formato `Etichetta: alias1, alias2 [data|importo|testo] [obbligatorio]`.

  Il tipo riceve l'id `custom_<slug>` e la versione del catalogo cresce di 1. Il salvataggio passa da `DocumentFamilyCatalogStore.save`.
- `GET /catalog/export`: scarica il JSON;
- `POST /catalog/import`: sostituisce il catalogo con un JSON caricato, dopo la validazione;
- tutte le modifiche passano dai controlli di origine e token già usati dalle altre rotte;
- gli errori sono mostrati in italiano e il file sul disco resta invariato;
- dopo una modifica, il catalogo nuovo vale per le elaborazioni successive; i record già salvati conservano la loro istantanea.

- [ ] Test che falliscono:
  - creare un tipo dal modulo e ritrovarlo nella pagina e nell'export;
  - un tipo nuovo, definito solo dal catalogo, viene proposto su una pagina OCR sintetica che contiene la sua parola chiave (REQ-042);
  - un JSON non valido all'import viene rifiutato e il file resta invariato;
  - un'origine sbagliata riceve 403;
  - un tipo con lo stesso id e definizione diversa viene rifiutato.
- [ ] Ciclo FAIL → PASS → commit.

### Task 5: Nome dell'esercente (REQ-052)

**Files:** Modify `semantic_proposals.py`; Test `test_merchant_name.py`

**Interfaces — Produces:** quando non c'è un'etichetta esplicita, `merchant_name` diventa un candidato `uncertain`, con regola `merchant-top-line` versione 1, così costruito:
- si prendono fino a 3 righe tra il 25% più alto della prima pagina;
- si scartano le righe con data, importo, valuta o parole di intestazione note (`fattura`, `ricevuta`, `scontrino`, `totale`, `data`, `pagina`);
- la prima riga rimasta è il valore, le altre sono alternative;
- l'evidenza sono i token della riga.

Se un'etichetta esplicita esiste, resta la proposta preferita.

- [ ] Test che falliscono:
  - una ricevuta sintetica «Bar Centrale / Data: … / Totale: …» propone «Bar Centrale», `uncertain`, con evidenza;
  - un documento che inizia con data e importo non ha alcuna proposta;
  - un'etichetta «Esercente: X» ha la precedenza.
- [ ] Ciclo FAIL → PASS → commit.

### Task 6: Angolo di rotazione nel record (rinviato da M2)

**Files:** Modify `schemas/document.schema.json` (`page.rotation_degrees`, enum 0/90/180/270, facoltativo), `document_processing.py`, `ocr_adapter.py` se serve; Test `test_page_orientation.py`

- [ ] Test che falliscono:
  - una pagina letta ruotata ha `pages[0]["rotation_degrees"] == 90` nel record;
  - una pagina diritta non ha il campo;
  - lo schema accetta solo i quattro valori.
- [ ] Ciclo FAIL → PASS → commit.

### Task 7: Accuratezza sintetica contro soglie (REQ-057, REQ-026 sintetico, REQ-051, REQ-055)

**Files:** Create `application/tools/field_benchmark_fixtures.py`, `application/tools/field_benchmark_score.py`, `application/tools/run_field_benchmark.py`; Test `test_field_benchmark.py` (generatore deterministico e punteggio, in CI); Create `docs/evidence/M3/accuracy-thresholds.md` **prima** della misura.

**Interfaces — Produces:**
- **fixture:** 60 giustificativi sintetici in PNG e PDF raster, metà in italiano e metà in inglese. Ognuno ha nome dell'esercente, data (anche ambigua), totale con virgola o punto, valuta, partita IVA o identificativo fiscale e numero di documento. Il manifest contiene i valori attesi;
- **punteggio per campo:** quota di documenti in cui il primo valore proposto (valore osservato, oppure prima alternativa di un candidato incerto) è uguale a quello atteso;
- **soglie proposte:** totale ≥ 95%, data ≥ 95% (sul primo valore suggerito), valuta ≥ 95%, numero di documento ≥ 90%, partita IVA ≥ 90%, esercente ≥ 80%.

  Le soglie sono scritte e committate prima della prima esecuzione.

- [ ] Test che falliscono: generatore deterministico (stessa impronta in due esecuzioni) e punteggio su record sintetici scritti a mano. → FAIL → implementare → PASS → commit.
- [ ] Committare le soglie; poi eseguire `run_field_benchmark` sul PC di sviluppo con RapidOCR e registrare i risultati in `docs/evidence/M3/<data>-field-accuracy.md`. Un campo sotto soglia non si «aggiusta» cambiando la soglia: si registra e si decide con il proprietario.

### Task 8: Evidenze, revisione, chiusura

- [ ] CI verde su entrambi i job → `docs/evidence/M3/<data>-ci.md`.
- [ ] Percorso nel browser integrato dell'editor del catalogo:
  - creare un tipo;
  - elaborare un documento sintetico;
  - vedere il tipo proposto e lo stato dei campi.

  Passi e risultati vanno in `docs/evidence/M3/browser-walkthrough.md`.
- [ ] Revisione indipendente → `review.md`; correzioni con test.
- [ ] Aggiornare `acceptance.md`, `requirements.md`, `decisions.md` (rinvii di REQ-053 e REQ-064) e `STATUS.md`; aprire la PR. Merge solo con il sì del proprietario (R8).
