# M8 — Diagnosi del percorso volatile (`/upload` → `/assign-note` → `/ocr/jobs/…`)

Data: 2026-11-19. Evidenza sanitizzata: non contiene contenuti, testo OCR, valori, nomi, percorsi o impronte di documenti reali né risultati individuali.

## Problema

Due tentativi esplorativi sull'installazione isolata 0.6.1 avevano mostrato «Elaborazione non riuscita» per il primo file del campione provvisorio, mentre `process_document_record` diretto dava `ocr.status=completed` e `OCRProcessingManager` con i limiti dell'app `phase=succeeded`. Il file reale è un **JPEG RGB, una pagina, < 1 MB**.

## Confronto del codice e cause candidate

- La pagina volatile (`_ocr_job_page`, `local_intake_app.py`) mostra «Elaborazione non riuscita» solo con `phase=failed` del manager; un rifiuto in pubblicazione (`publish_completed_result`) mostra invece «Risultato rifiutato». La pagina **non mostrava il codice** del worker.
- Lo stesso testo iniziale compariva anche nella pagina 400 di `/assign-note` per qualunque `ValueError` (selezione della nota non valida in `create_expense_report_intake_session`, oppure `OCRProcessingManager.start` rifiutato), cioè anche quando nessuna elaborazione era partita.
- Candidate verificate: limiti di decodifica (`DecodeLimits`) e dimensione; cornici IPC (`max_input_frame_bytes`, `max_result_frame_bytes`); limite di memoria del job Windows; validazione dei record e pubblicazione; ruolo della nota sintetica e ordine dei file; nome originale del file; `TEMP` privato; avvio a freddo; catalogo dei tipi (assente nei profili esplorativi).

## Prove

Tutte sulla runtime 0.6.1 dell'installazione isolata o sulla copia ricostruita, con profili `LOCALAPPDATA` nuovi e isolati.

| Prova | Esito |
|---|---|
| Fixture sintetiche (nota PNG bianca 800×400 + JPEG 900×1200), in-process e via HTTP reale | `succeeded`, 2/2 `completed`, pagine di revisione 200 |
| Varianti sintetiche: JPEG progressivo, ICC + EXIF, nome lungo non ASCII | `succeeded`, 4/4 `completed` |
| File reale, in-process, nome originale | `succeeded`, 2/2 `completed`, revisione 200 |
| File reale via HTTP: server nuovo a freddo, file reale come nota, file reale caricato per primo, `TEMP` privato | ogni volta `succeeded`, 2/2 `completed`, revisione 200 (20–42 s) |

**Il guasto non si è riprodotto.** Nei profili esplorativi non c'è traccia del codice (nessun dato persistito; i registri contengono solo l'intestazione d'avvio). La causa originale resta **non accertata**: i due tentativi potrebbero essere finiti nella pagina 400 di `/assign-note` (stesso testo iniziale, nessun job avviato) oppure in un `phase=failed` del worker dovuto a condizioni dell'ambiente di allora; non è possibile distinguerlo a posteriori.

## Correzione (TDD)

- `ocr_processing.PUBLIC_JOB_ERROR_CODES`: insieme fisso dei codici d'errore dei job.
- `_ocr_job_page`: con `phase=failed` mostra `Codice: <codice>`; un codice fuori dall'insieme diventa `unknown_error` e non viene mai riportato.
- `/assign-note`: la pagina 400 distingue `assign_note_invalid` (selezione rifiutata) da `ocr_start_rejected` (avvio OCR rifiutato) e non dice più «Elaborazione non riuscita» quando non è partita alcuna elaborazione; nessun dettaglio dell'eccezione.

Test nuovi in `tests/test_ocr_job_ui.py` (5, più 4 sottocasi) e asserzione aggiornata in `tests/test_local_intake_app.py`. RED: 7 fallimenti; GREEN: moduli correlati 112 passati e 99 sottocasi. Suite completa: **1393 passati, 4 saltati, 411 sottocasi** con `--basetemp` fuori dal repository. Con `--basetemp` sotto `.m8-work` 4 test di `test_field_trial_score.py` falliscono perché gli strumenti rifiutano, per progetto, cartelle dentro un repository Git; lo stesso modulo passa 65/65 fuori dal repository. Nessuna modifica a R7/R8.

## Verifica sull'app ricostruita

Payload 0.6.1 ricostruito con `installer/build_payload.py` dagli ingredienti di `build-cache` in una nuova cartella isolata, controllato con `verify_payload.py` («Payload integrity and version verified»); non è stato compilato né eseguito l'installer NSIS. Con profilo isolato nuovo: fixture sintetica e file reale via HTTP arrivano a «Elaborazione completata», 2/2 `completed`, pagine di revisione 200; la selezione non valida mostra `assign_note_invalid`. I valori dei campi non sono stati letti né mostrati: il controllo spetta al proprietario, in locale.

## Limiti

- Causa originale non riprodotta; la correzione rende diagnosticabile un futuro fallimento, non dimostra di rimuoverne la causa.
- La copia di verifica è un payload avviato in modalità console, non un'installazione NSIS; la modalità finestra (`--app-window`) non è stata provata.
- Prova esplorativa: non è una misura d'accuratezza (REQ-140/142 restano aperti).
