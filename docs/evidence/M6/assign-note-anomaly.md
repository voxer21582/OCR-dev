# Anomalia «/assign-note» nel collaudo sull'altro PC

Data: 2026-11-16. Build interessata: `OCR2-0.6.0-setup-non-firmato.exe` (commit `fa952c3`). Correzione: commit `5e347e2`. Nuova build: `OCR2-0.6.x-setup-non-firmato-5e347e2.exe`.

## Cosa ha osservato il proprietario

Sintesi del memo tecnico del proprietario (non incluso nel repository):

- impronte di installer, script e procedura coincidenti con `SHA256SUMS.txt`; Windows PowerShell 5.1, `%LOCALAPPDATA%` di 29 caratteri; `active.json` `{"active":"0.6.0","previous":null}`; nessun file `opencv_videoio_ffmpeg*`; Informazioni: Python 3.13.18, RapidOCR 3.10.0, runtime `verificato`;
- da «Acquisizione temporanea», caricato un file sintetico e scelto come nota spese, «Conferma nota spese» porta alla pagina locale `/assign-note` con «Risorsa non trovata»; ripetuto con un PDF e con un'immagine di prova;
- il flusso non arriva a «Salva in archivio»: salvataggio, riapertura dall'archivio e «Apri documento originale» non verificabili; prova funzionale M6 bloccata;
- richieste: causa documentata, correzione minima con test di regressione, nuova build riconoscibile con nuove impronte, senza sovrascrivere la release verificata; non eseguire ancora la disinstallazione con eliminazione dei dati.

## Causa

Con un motore OCR attivo, `POST /assign-note` risponde con la pagina «Elaborazione OCR», che si aggiorna da sola ogni 2 secondi. L'aggiornamento era un `<meta http-equiv="refresh" content="2">` senza indirizzo: il browser ricarica l'indirizzo corrente, cioè `/assign-note`, con `GET`. `/assign-note` accetta solo `POST`, quindi la risposta è «Risorsa non trovata». Lo stesso vale per la pagina di elaborazione di un fascicolo, avviata da `POST /cases/<id>/process`.

Il difetto non nasce in M6: lo stesso aggiornamento senza indirizzo è presente su `origin/main` (codice M4/M5) in entrambe le pagine. Si vede solo con un motore OCR attivo, perché senza OCR `/assign-note` porta direttamente alla revisione. Verosimilmente nessuna prova precedente aveva atteso l'aggiornamento automatico della pagina con un motore OCR attivo: i test usano richieste dirette e il collegamento «Aggiorna stato» punta già all'indirizzo giusto. Il formato del file non c'entra.

## Correzione

Commit `5e347e2`: l'aggiornamento punta all'indirizzo `GET` del lavoro, `/ocr/jobs/<id>` e `/cases/<id>/jobs/<id>`. Due test nuovi (prima falliti, poi passati). Verifica del coordinatore in Chromium reale contro l'avviatore con RapidOCR: assegnazione della nota, OCR, salvataggio, apertura dall'archivio e documento originale funzionano. Suite Windows a `5e347e2`: 1.127 test passati, 3 saltati, 398 sottocasi.

## Nuova build

Payload 0.6.0 e 0.6.1 ricostruiti dal codice di `5e347e2`, stessi input e stesso metodo della consegna precedente; `makensis /DOCR2_UNSIGNED_RELEASE` con `(UTF8)` e i controlli di rilascio superati. Cartella di consegna nuova `m6-installer-altro-pc-2`; la precedente non è stata modificata, salvo un file `SUPERATO-LEGGIMI.txt` che rimanda alla nuova.

| File | Byte | SHA-256 |
|---|---|---|
| `OCR2-0.6.0-setup-non-firmato-5e347e2.exe` | 111.663.909 | `accc5a021b65b2ca0d0c63b6dafe4c808eab653db6071c12a86493fc2a1dbc34` |
| `OCR2-0.6.1-setup-non-firmato-5e347e2.exe` | 111.663.887 | `2c768e00165fe1af80c6476ab555ca152838e6856705b847c4bc9ea80034c70f` |

## Stessa versione sopra una installata

L'installer, se trova la stessa versione già installata e integra, non la sostituisce e termina con codice `0` (comportamento di #152, già indicato nei codici di uscita). Prova isolata: 0.6.0 della build precedente installata, poi 0.6.0 di `5e347e2` sopra; codice `0`, ma `local_intake_app.py` installato resta quello vecchio (impronta invariata). Sul PC di collaudo la nuova 0.6.0 si applica quindi solo dopo aver disinstallato la 0.6.0 presente: dal menu Start, «Disinstalla OCR2», risposta **No** alla domanda sui dati (il proprietario ha chiesto di non eseguire ancora la rimozione dei dati). Il limite è ora nella procedura e nei limiti dichiarati di [accettazione](acceptance.md).

## Prova isolata sulla nuova build

Installer di prova `OCR2_TEST` dagli stessi payload, cartella temporanea: installazione 0.6.0 (codice 0), `/LAUNCH` → 0.6.0, Informazioni 0.6.0 / Python 3.13.18 / RapidOCR 3.10.0 / `verificato`, Esci 200, aggiornamento a 0.6.1 (`{"active": "0.6.1", "previous": "0.6.0"}`), disinstallazione con rimozione dati (codice 0). Il flusso completo via HTTP (caricamento → assegnazione della nota → OCR → archivio → originale) **non è ancora stato completato** sulla build installata: il primo tentativo non ha letto la porta del server (uscita bufferizzata), il secondo non è partito. Da ripetere.
