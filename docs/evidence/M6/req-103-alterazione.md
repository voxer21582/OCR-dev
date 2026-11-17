# REQ-103 — avvio rifiutato con un file alterato (2026-11-17)

Prova eseguita da Claude sul PC di sviluppo, isolata dal profilo reale:

- installer di prova `OCR2-test-0.6.0.exe`, costruito dallo stesso contenuto degli installer consegnati (commit `5e347e2`);
- installazione silenziosa in una cartella corta temporanea sotto il profilo, con `LOCALAPPDATA` temporaneo;
- avvio con `python.exe -B -m alfa_document_intelligence --port 0` della versione installata.

| Caso | Esito |
|---|---|
| Installazione intatta | l'app parte: server ancora attivo dopo 15 secondi |
| Una riga aggiunta a `app/alfa_document_intelligence/review_ui.py` | uscita con codice 2: «Installazione non valida: File modificato: app/alfa_document_intelligence/review_ui.py. Installa di nuovo OCR2 con il suo installer, oppure dal menu Start usa «Torna alla versione precedente».» |

Poi disinstallazione con eliminazione dei dati di prova (codice 0) e cancellazione della cartella. `Programs\OCR2` reale invariata (2352 file), `%LOCALAPPDATA%\OCR2` reale assente.

Osservazione collaterale: un primo tentativo in una cartella molto profonda è fallito anche con l'installazione intatta («Manifest o installazione non validi»), perché un file della versione superava i 260 caratteri. È il limite di lunghezza già dichiarato nella procedura (`%LOCALAPPDATA%` entro circa 95 caratteri) e non riguarda l'installazione predefinita.

Limiti: la verifica rileva alterazioni accidentali o parziali; non protegge da chi altera insieme un file e il manifest, perché il manifest non è ancorato a una radice di fiducia indipendente (vedi [payload](payload.md)). La finestra di errore in modalità app non è stata osservata in questa prova; il suo log è coperto dai test automatici.
