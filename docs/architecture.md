# OCR2 — Architettura

Descrive l'architettura del prodotto e i punti di estensione. Il dettaglio dei moduli esistenti è in `application/ARCHITECTURE.md`, `application/PROCESSING_PIPELINE.md` e `application/DATA_SCHEMA.md`.

## Schema

```
Finestra Edge (modalità app) ──HTTP 127.0.0.1──▶ server locale WSGI (local_intake_app.py)
                                                  ├─ ingestione e limiti (ingestion.py, image_safety.py)
                                                  ├─ worker isolati
                                                  │   ├─ OCR (ocr_processing.py) ◀── registro dei motori [M2]
                                                  │   └─ anteprime [M2]
                                                  ├─ proposte semantiche (semantic_proposals.py) ◀── catalogo (document_family_catalog.py)
                                                  ├─ validazione e riconciliazione (document_validation.py, expense_reconciliation.py)
                                                  ├─ revisione, storia solo in aggiunta (review_ledger.py)
                                                  ├─ archivio cifrato DPAPI per utente (local_document_store.py)  [R7]
                                                  └─ esportatori JSON/CSV (document_export.py) ◀── registro esportatori [M5] [R8]
```

## Principi (invariati)

- Osservazione OCR, interpretazione, validazione e decisione umana restano separate.
- Ogni valore porta impronta del documento, pagina e area; le alternative e l'incertezza non si perdono; nessun valore inventato.
- Nessuna approvazione automatica; nessuna rete in uscita; OCR spento salvo attivazione.
- Decodificatori nativi solo in worker isolati con limiti.

## Punti di estensione

| Punto | Contratto | Aggiungere un elemento significa | Milestone |
|---|---|---|---|
| Motore OCR | `OCREngineAdapter` (`ocr_adapter.py`) + manifest del motore (nome, versione, lingue, licenza, SHA-256 degli artefatti, riferimento alla factory) letto da un registro e verificato nel worker | un manifest e un modulo adattatore, nessun altro file | M2 |
| Produttore di testo PDF | lo stesso contratto del motore, con produttore distinto nella provenienza | — | M2 |
| Formato di input | decodificatore in `document_decoder.py` dietro la regola REQ-014 | decoder con licenza e impronta, limiti, test su input malformati | M2 |
| Tipi di documento e regole di classificazione | catalogo in file di configurazione, istantanea legata a ogni record | voci nel catalogo (file o editor), nessun codice | M3 |
| Regole di validazione | ID di regola stabile e versione; i record revisionati mantengono gli esiti | una regola nuova con test | M3 |
| Esportatore | interfaccia comune degli esportatori e registro | un modulo esportatore, nessun altro file | M5 |

## Decomposizione prevista

`local_intake_app.py` (2.575 righe) si divide per aree (fascicoli, archivio, revisione, OCR) solo quando una milestone lavora su quell'area, mantenendo le rotte invariate.

## Installazione (M6)

Installer NSIS per utente in `%LOCALAPPDATA%\Programs\OCR2\<versione>`, con Python embeddable e runtime verificato da impronte; dati in `%LOCALAPPDATA%\OCR2` separati dal programma; un collegamento nel menu Start dell'utente che avvia il launcher, che apre Edge con `--app=http://127.0.0.1:<porta>/`. Più versioni installate affiancate permettono il ritorno indietro.
