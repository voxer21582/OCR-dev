# M1 — Rassegna delle PR aperte (2026-11-15)

Requisito: REQ-001 (ordine del repository), DEC-019. Base: `main` a `d077824`.

**Metodo** (solo lettura, nessuna PR modificata):
- `gh pr list --state open` restituisce **50 PR** aperte. Il piano ne indicava 30: era il limite dell'elenco usato nella Fase 0.
- Per ogni PR ho calcolato il diff rispetto alla sua base. Poi ho misurato:
  - quante righe aggiunte (oltre 25 caratteri) sono già presenti in `main`;
  - quante delle funzioni di test aggiunte esistono già in `main`;
  - se i file nuovi esistono già in `main`;
  - se il diff si applica a `main` senza conflitti.
- È un indizio, non una prova: una correzione riscritta in modo diverso su `main` risulta «assente».

**Regola:** nessuna PR si chiude o si unisce senza il sì del proprietario. Una PR del gruppo C si chiude solo quando la sua sostituta su `main` è unita, e la sostituta la cita.

## A — Unire adesso (2)

| PR | Titolo | Perché |
|---|---|---|
| #144 | M2: date ambigue, intestazioni #135, fixture a risposta nota, benchmark | Riguarda anche R7/R8 (solo presentazione e messaggi di `local_intake_app.py`). CI verde. Serve al benchmark di M1 (Task 5). |
| #126 | docs: export dall'archivio | Si applica a `main` senza conflitti. È corretta: i link JSON e CSV esistono nell'interfaccia (verificato in `local_intake_app.py`). |

## B — Chiudere: superate o solo selettori CI (14)

| PR | Motivo |
|---|---|
| #57, #70, #72, #74, #77, #78, #80, #82, #84, #86, #92 | Aggiungono solo un modulo di test al workflow per la PR madre. Le sostituisce il Task 6 di M1 (tutti i moduli in CI). |
| #141 | Stato dei requisiti: sostituita da `docs/requirements.md` (#145). |
| #117 | Aggiornamento di `CURRENT_STATE.md`: sostituito da `docs/STATUS.md` (#145). Conflitto con `main`. |
| #118 | README dell'applicazione: dice di non avviare la build Windows finché R7/R8 sono bloccati. Dopo DEC-001 è superata; il README si aggiorna nel Task 6. |

## C — Riportare su `main` nella milestone giusta (31)

Le modifiche **non** risultano in `main`: per esempio i file di test nuovi mancano, oppure 0 test su N sono presenti. Sono basate su rami vecchi e quasi tutte vanno in conflitto. Proposta: lasciarle aperte come riferimento e rifare ciascuna con una PR nuova su `main`, con i test scritti prima, nella milestone indicata.

| Milestone | PR | Contenuto |
|---|---|---|
| M1 (Task 6) | #105, #101 | Test dei lavori OCR in CI, con modifiche a `ocr_processing.py`; allowlist CI dell'export (#101: 22 test su 36 già in `main`) |
| M1 | #81 | Isolamento delle sessioni obsolete, protezione della sessione volatile (sicurezza, `test_stale_session_isolation`) |
| M2 | #56, #83, #45 | Protocollo OCR limitato (0 test su 11 in `main`); forma dell'output RapidOCR; workflow di prova Windows di RapidOCR (#45, bozza su un ramo superato: da rivalutare, probabilmente superata dal lock di #138) |
| M3 | #60, #73, #87, #85, #91, #93 | Accumulo limitato delle proposte; coerenza delle date di viaggio; campi obbligatori dei tipi personalizzati; copertura delle evidenze e dei gruppi nel benchmark; avviso di errore semantico |
| M3 | #115, #116, #127, #128, #131, #132 | Correzioni della catena delle note spese (validazione delle evidenze, enum, ordine dei token, schema delle righe, ordinamento della riconciliazione, segno degli importi incerti). Basate sul ramo #106 prima di #142; 0 test aggiunti presenti in `main` per nome, ma alcune correzioni potrebbero essere già in `main` in altra forma: da verificare caso per caso. |
| M4 | #69, #71, #75, #94, #95, #96, #97, #98, #103 | Campo mancante manuale e campi personalizzati; etichetta neutra di revisione; pila R6 della storia di revisione (migrazione del registro, conflitti di revisione, presentazione, storia fiscale); avviso prima del passaggio a ChatGPT |
| M5 (R7/R8) | #76, #79, #99, #108 | Sicurezza degli identificativi nel CSV; proiezione CSV revisionata; ripristino dell'archivio in background; eliminazione di un fascicolo |

## D — Documenti di ricerca da tenere (3)

| PR | Proposta |
|---|---|
| #100 | Fattibilità di PaddleOCR 3.7 (bozza). Unire come documento di ricerca, oppure chiudere: un secondo motore vero è fuori dal piano (DEC-003). Raccomandazione: **chiudere**, il documento resta leggibile nella PR. |
| #111 | Proposta di protocollo del pilot (issue #10). Si applica a `main` senza conflitti. Raccomandazione: **lasciare aperta fino a M8**, dove diventa la base del protocollo. |
| #119 | Ambito CI della pipeline di elaborazione. Si applica senza conflitti ma descrive la CI di oggi, che il Task 6 cambia. Raccomandazione: **chiudere** e aggiornare quel documento nel Task 6. |

## Decisioni del proprietario

| Gruppo | Proposta | Decisione |
|---|---|---|
| A | Unire #144 e #126 | **Approvato**, eseguito |
| B | Chiudere le 14 PR con un commento che indica cosa le sostituisce | **Approvato**, eseguito |
| C | Lasciare aperte; ognuna si chiude quando la sua sostituta su `main` è unita | **Approvato** |
| D | Chiudere #100 e #119; lasciare aperta #111 | **Approvato**, eseguito |

**Decisione del proprietario (2026-11-15): «approvo» i gruppi A–D.** Eseguito:
- unite #144 (`fe22a6c`) e #126 (`3d5ac61`), con i controlli verdi;
- chiuse con commento #57, #70, #72, #74, #77, #78, #80, #82, #84, #86, #92, #141, #117, #118, #100 e #119.

## Integrazione: 18 PR non viste nella prima rassegna

L'elenco usato per la prima rassegna si fermava a 50 voci (`--limit 50`): le PR aperte erano **68**. Le 18 più vecchie (5–8 novembre) sono analizzate qui con lo stesso metodo.

| Gruppo proposto | PR | Motivo |
|---|---|---|
| **B — chiudere: solo selettori CI** | #19, #24, #26, #30, #33, #36 | Aggiungono solo selettori CI alle PR madri; li sostituisce il Task 6. |
| **B — chiudere: superate dalla migrazione dell'applicazione** | #18, #23, #25, #29, #32, #35, #37 | Pila R1–R6 del 6 novembre: contratti nel pacchetto di radice (`ocr_contracts.py`, preflight delle sorgenti, candidati di campo, validazione strutturale, registro di revisione, mappa di accettazione). Dal 7 novembre gli stessi contratti esistono in `application/` (`contracts.py`, `ingestion.py`, `document_validation.py`, `review_ledger.py`) e i requisiti vivono in `docs/requirements.md`. Le issue #17, #22, #28, #31 e #34 restano aperte e verranno chiuse o aggiornate in M1 rispetto a REQ-xxx. |
| **B — chiudere: superate** | #14, #15, #40 | #14 obiettivo di prodotto (sostituito da `GOAL.md`); #15 guida per contributori e modelli di issue e PR (le regole ora stanno in `GOAL.md` e `application/AGENTS.md`); #40 prova di RapidOCR su Windows (superata dal lock e dal controllo del runtime di #138). Lo stesso vale per **#45**, che nella prima rassegna era nel gruppo C: si propone di chiuderla insieme a #40. |
| **C — riportare** | #16 | Correzione reale non presente in `main`: `bind_document_record` sostituisce senza avviso il legame di tassonomia di un record già legato. Da rifare in M3 con il suo test. |
| **D — tenere fino a M8** | #13 | Modello di registro delle decisioni del pilot (A5); serve con #111 per il protocollo della prova sul campo. |

| Gruppo | Proposta | Decisione |
|---|---|---|
| Integrazione B | Chiudere #14, #15, #18, #19, #23, #24, #25, #26, #29, #30, #32, #33, #35, #36, #37, #40 e #45 (17 PR) | **Approvato** (2026-11-15): chiuse con commento |
| Integrazione C/D | Lasciare aperte #16 (M3) e #13 (M8) | **Approvato** (2026-11-15) |

**Stato dopo la rassegna:** 34 PR aperte, cioè la PR di M1 (#146), le 30 PR del gruppo C da rifare nelle milestone indicate (#45 è passata al gruppo B), #16, #13 e #111.
