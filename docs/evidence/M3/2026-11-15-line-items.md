# M3 — Righe di fattura e regole con versione (2026-11-15)

**Requisiti:** REQ-053 (righe di fattura e tabelle) e REQ-064 (regole di verifica con versione). Il proprietario li ha inclusi in M3 il 2026-11-15, annullando i rinvii DEC-021 e DEC-022.

## Righe di fattura: misura con l'OCR vero (`LOCAL-RUN`)

**Strumento:** `tools/line_item_benchmark.py`.
- Genera 12 fatture sintetiche PNG, con 3–6 righe ciascuna (54 righe in tutto), colonne Descrizione / Qtà / Prezzo / Importo e il totale in una cella separata.
- Le legge con RapidOCR 3.10.0, scelto dal registro, attraverso l'elaborazione dell'app: ogni fattura è un allegato di una nota fittizia.

| Misura | Esecuzione 1 (`261ef3c`) | Esecuzione 2 (`b0cf31c`) | Esecuzione 3 (`420c3b7`, codice finale) |
|---|---|---|---|
| Fatture con il numero giusto di righe | 12/12 | 12/12 | 12/12 |
| Importi corretti | 54/54 | 54/54 | 54/54 |
| Prezzi unitari corretti | 54/54 | 54/54 | 54/54 |
| Descrizioni corrette | **0/54** | 48/54 | **54/54** |
| Quantità corrette | **0/54** | 48/54 | **54/54** |
| Verifica «somma delle righe = totale» presente e concorde | **0/12** | 12/12 | **12/12** |

**Cause trovate e corrette.** Sono difetti reali della lettura, non dei documenti di prova:
1. **Esecuzione 1, intestazione «Qtà»:** l'OCR la legge come `Qt`, senza accento. La colonna quantità non veniva riconosciuta e il numero finiva nella descrizione. Corretto in `b0cf31c`.
2. **Esecuzione 1, «Totale» in colonna:** il totale e il suo importo stanno in due celle separate della stessa riga, quindi il totale non veniva letto e la verifica della somma non partiva. Ora una cella che contiene solo l'etichetta del totale prende l'importo nella cella a destra (`b0cf31c`). Dopo la revisione prende l'importo più a destra e salta le celle che hanno parole proprie (`420c3b7`).
3. **Esecuzione 2:** in una fattura l'OCR ha letto «Qtà» come `Qt` seguito da un carattere cinese, perché il modello è multilingue. Il riconoscimento dell'intestazione ora accetta queste letture (`420c3b7`, con test sui casi osservati).

## Revisione indipendente dell'estensione

**Revisore:** agente Opus senza contesto, sui commit `574afc2..9fd9e67`. **Esito:** nessun problema critico; 5 importanti, tutti corretti con test in `420c3b7`.

| # | Problema | Test (prima rosso, poi verde) |
|---|---|---|
| 1 | Migliaia separate da uno spazio (`1 234,00`) spezzate | `test_thousands_separated_by_a_space` |
| 2 | Totale in colonna: preso il primo importo (l'imponibile in un riepilogo IVA) o una cella di un'altra etichetta | `test_rightmost_amount_of_a_total_row_and_no_labelled_cells` |
| 3 | Confini della tabella: «Importo totale» diventava una riga, una voce «Tax …» chiudeva la tabella, una frase apriva una tabella, la tabella non continuava sulla pagina dopo | `test_total_rows_end_the_table_but_items_named_tax_do_not`, `test_a_sentence_does_not_open_a_table`, `test_a_table_continues_on_the_next_page` |
| 4 | Quantità presa dalla descrizione (`Toner HP 305`) | `test_quantity_is_the_number_just_before_the_prices` |
| 5 | Oltre 1000 righe si perdevano tutti i campi del documento | `test_too_many_items_keep_the_common_fields` |

**Problemi minori corretti:**
- le righe salvate non possono essere «osservate» e devono avere area e token;
- le dimensioni del registro coincidono con quelle dei risultati, e lo schema ammette `amount_arithmetic_consistency` (lacuna preesistente);
- id e versioni delle regole sono controllati in modo esatto;
- una revisione inizia con il primo evento;
- la sezione «Verifiche» elenca solo le regole applicate;
- aggiunto il test «nota spese senza righe».

**Rinviati:** sconti con il segno meno in fondo (`10,00-`), che vengono ignorati e lasciano la verifica della somma da rivedere. `revalidate()` è pronta e testata, ma nessun percorso dell'app riverifica oggi un record già salvato; lo userà M5 (libreria e migrazioni).

## Nessun peggioramento sulle misure di M3

Sul codice finale (`420c3b7`):
- **accuratezza dei campi:** invariata, cioè totale, data, valuta, numero e partita IVA 100% ed esercente 90%;
- **benchmark del fascicolo:** punteggi identici a M1 e M2 (98/98 righe, 92/92, 3/3, 40/40, 0 connessioni esterne), 1,2 s per pagina.
