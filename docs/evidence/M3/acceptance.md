# M3 — Accettazione: criteri ed evidenze

Commit di riferimento: `420c3b7` (branch `claude/m3-classificazione`).

Livelli di prova:
- **`SYN-CI`**: test sintetici in CI su Ubuntu e Windows ([`2026-11-15-ci.md`](2026-11-15-ci.md));
- **`LOCAL-RUN`**: prova sul PC di sviluppo con dati sintetici.

| Requisito | Criterio | Esito | Evidenza |
|---|---|---|---|
| REQ-041 | Catalogo da configurazione, istantanea legata a ogni record, collegato a interfaccia e archivio | `SYN-CI` + `LOCAL-RUN` | Il launcher carica il catalogo dell'utente (`test_ocr_launcher_contract`, job Windows); il catalogo arriva all'elaborazione dei documenti singoli e dei fascicoli (`CatalogReachesCaseProcessingTests`); [`browser-walkthrough.md`](browser-walkthrough.md) |
| REQ-042 | Un tipo definito solo dal catalogo viene proposto | `SYN-CI` | `CatalogRuleTests` |
| REQ-045 | Editor: crea, importa, esporta, versiona | `SYN-CI` + `LOCAL-RUN` | `test_catalog_editor` (creazione, export, import, storico delle versioni, rifiuto di duplicati, ridefinizioni e file non validi, messaggi comprensibili, origine sbagliata, modulo inviato dalla pagina in sandbox); [`browser-walkthrough.md`](browser-walkthrough.md) |
| REQ-051 | Campi comuni con evidenza | `SYN-CI` + `LOCAL-RUN` | Test esistenti più `test_attached_currency_amounts`; accuratezza 100% su totale, data, valuta, numero e partita IVA ([`2026-11-15-field-accuracy.md`](2026-11-15-field-accuracy.md)) |
| REQ-052 | Nome dell'esercente con evidenza; alternative se ambiguo | `SYN-CI` + `LOCAL-RUN` | `test_merchant_name` (6 test); accuratezza 90% (soglia 80%) |
| REQ-055 | Normalizzazione per lingua che conserva il letterale | `SYN-CI` | Test esistenti e date ambigue di M2; data 100% sul primo suggerimento |
| REQ-057 | Obiettivi di accuratezza sintetici con soglie fissate prima | `LOCAL-RUN` | [`accuracy-thresholds.md`](accuracy-thresholds.md) (commit `f45e036`, prima della misura); [`2026-11-15-field-accuracy.md`](2026-11-15-field-accuracy.md): tutte le soglie superate nell'esecuzione 4 |
| REQ-060 | I quattro stati di GOAL con il motivo, in interfaccia ed export | `SYN-CI` | `test_field_status`, `test_field_status_presentation`, `ReviewedFieldStatusTests`; CSV `ocr2-document-csv-v2` |
| REQ-026 (sintetico) | Italiano e inglese riconosciuti | `LOCAL-RUN` | Accuratezza per lingua: inglese 100% su tutti i campi; italiano 100% salvo l'esercente all'80% |
| REQ-053 | Righe di fattura e tabelle con totali ed evidenza | `SYN-CI` + `LOCAL-RUN` | `test_invoice_line_items` (estrazione, confini, migliaia, quantità, più pagine, limite, contratto, pagina di revisione), `test_line_item_benchmark`; misura su 12 fatture: 54/54 in tutti i campi, verifica della somma 12/12 ([`2026-11-15-line-items.md`](2026-11-15-line-items.md)) |
| REQ-064 | Regole di verifica con versione; i record revisionati non cambiano | `SYN-CI` | `test_validation_rules` (versione dal registro, nuova regola solo sui record non revisionati, `validation_ruleset` nello schema e nel contratto, pagina «Verifiche») |
| REQ-028 (da M2) | L'angolo di rotazione registrato nel record | `SYN-CI` | `test_page_orientation::test_rotation_angle_is_recorded_on_the_page` |

**Decisioni:** il limite della riconciliazione resta una decisione di chi rivede (DEC-023). REQ-053 e REQ-064 sono inclusi su richiesta del proprietario (DEC-021 e DEC-022 annullate).

**Difetti dell'app trovati e corretti durante M3:**
- importi attaccati al codice di valuta (`39dea21`);
- server bloccato da una connessione inattiva del browser (`4390ed4`);
- modulo del catalogo inviato dalla pagina in sandbox (`13295d6`).

**Revisione indipendente:** [`review.md`](review.md) (prima parte) e [`2026-11-15-line-items.md`](2026-11-15-line-items.md) (estensione). Tutti i problemi importanti sono corretti con test.

**Merge:** la PR modifica l'export CSV (R8) e il server locale. Serve l'approvazione del proprietario (DEC-001).
