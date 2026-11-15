# M6 — Prova manuale: istanza unica e finestra Edge in modalità app (REQ-100)

Data: 2026-11-15. PC di sviluppo Windows 11, Microsoft Edge installato in
`%ProgramFiles(x86)%\Microsoft\Edge\Application\`. Nessuna istanza di Edge
dell'utente era aperta durante la prova.

## Condizioni

- Avvio da sorgenti: Python di sviluppo con `PYTHONPATH=application/src`,
  comando `python -B -m alfa_document_intelligence --app-window` (OCR
  disattivato, porta scelta dal sistema).
- `LOCALAPPDATA` temporaneo: `<scratchpad>\m6-edge\LocalAppData`. Nessun uso
  dell'archivio reale; l'archivio cifrato è stato creato vuoto nella cartella
  temporanea. Solo dati sintetici (nessun documento caricato).
- Nessuna schermata. Gli esiti sono stati verificati dalla riga di comando dei
  processi (`Get-CimInstance Win32_Process`), dalle porte in ascolto
  (`Get-NetTCPConnection -State Listen`) e dal registro delle richieste del
  server.

## 1. Finestra senza barra degli indirizzi e risposta di /app/info

Passi: primo avvio con `--app-window`.

Esito: **superato**.
- `instance.json` pubblicato in `%LOCALAPPDATA%\OCR2\` con porta e id
  dell'istanza.
- Riga di comando di Edge (unico processo `msedge.exe` principale):
  `msedge.exe --app=http://127.0.0.1:<porta>/ --user-data-dir=%LOCALAPPDATA%\OCR2\edge-profile --no-first-run --no-default-browser-check`.
  `--app=` apre la finestra in modalità app (senza barra degli indirizzi);
  il profilo è quello dedicato dentro la cartella temporanea.
- Il registro del server mostra `GET /` e il primo `GET /app/heartbeat` della
  finestra.
- `GET /app/info` → 200: versione 0.1.0, Python 3.13, «Motore OCR:
  disattivato», «Verifica del runtime: non verificato (avvio da sorgenti)»,
  `<meta name="ocr2-instance">` presente.
- Porte in ascolto del processo Python: solo `127.0.0.1:<porta>`.

## 2. Secondo avvio

Passi: secondo `python -B -m alfa_document_intelligence --app-window` con lo
stesso `LOCALAPPDATA` mentre il primo è attivo.

Esito: **superato**.
- Il secondo processo è uscito con codice **0** in 0,7 s.
- Il server ha ricevuto `GET /app/info` (conferma dell'istanza), poi `GET /` e
  un heartbeat con un **nuovo** id di finestra: la seconda finestra si è aperta
  sulla stessa porta (il secondo `msedge.exe` passa l'apertura al processo Edge
  già attivo per lo stesso profilo ed esce).
- `Get-NetTCPConnection -State Listen`: una sola porta, del primo processo
  Python. Nessun secondo server.

## 3. «Esci» (POST /app/exit)

Passi: piccolo script Python (urllib, senza proxy) che legge il token CSRF da
`GET /` e invia `POST /app/exit` con `_ocr2_csrf` e intestazione
`Origin: http://127.0.0.1:<porta>`.

Esito: **superato**.
- Risposta 200; porta chiusa dopo **2,1 s**; processo Python terminato.
- `instance.json` rimosso (lock rilasciato).

## 4. Chiusura della finestra

4a. Chiusura normale: nuovo avvio, poi chiusura della finestra dell'app
(messaggio di chiusura alla sola finestra Edge del profilo temporaneo,
`CloseMainWindow`).

Esito: **superato tramite il segnale di chiusura**. Il server ha ricevuto
`POST /app/closing` ed è terminato dopo **11,5 s** (periodo di attesa di 10 s
+ controllo ogni secondo). `instance.json` rimosso.

4b. Chiusura forzata: nuovo avvio, poi arresto forzato dei soli processi
`msedge.exe` la cui riga di comando contiene la cartella temporanea (nessun
altro processo Edge). Una chiusura forzata non invia il segnale di chiusura.

Esito: **superato tramite la scadenza dell'heartbeat**. Il server è terminato
**175 s** dopo l'arresto di Edge, cioè circa 180 s dopo l'ultimo heartbeat
(limite massimo previsto: 190 s). `instance.json` rimosso.

Osservazione: dopo la chiusura normale (4a) Edge ha avviato da sé un processo
`msedge.exe --no-startup-window /prefetch:5` **senza** `--user-data-dir`, cioè
sul profilo predefinito ricavato da `%LOCALAPPDATA%` (qui la cartella
temporanea, dove ha creato `Microsoft\Edge\User Data`). Con il `LOCALAPPDATA`
reale questo processo in background userebbe il profilo Edge normale
dell'utente. Non cambia impostazioni, ma è un processo Edge che resta attivo
dopo la chiusura di OCR2: segnalato al responsabile della milestone.

## 5. R14: navigazione al documento originale (da verificare dal proprietario)

Non eseguibile senza clic nella finestra: **da verificare dal proprietario**.

Istruzioni:
1. Avviare OCR2 con `--app-window` (o dal collegamento, quando disponibile) con
   un archivio di prova contenente almeno un documento sintetico.
2. Aprire **Archivio**, scegliere il documento e premere
   «Apri documento originale» (pagina senza heartbeat).
3. Attendere **30 s** sulla pagina del documento.
4. Premere **Indietro** (Alt+Freccia sinistra).
5. Esito atteso: la pagina dell'archivio si ricarica e l'app risponde
   (il server non si è fermato). Ripetere premendo «Esci» alla fine: la
   finestra si chiude e il processo termina entro 15 s.

Limite noto (R12/R14): restando sulla pagina del documento originale per più
di 180 s il server può fermarsi.

## Pulizia

Al termine: nessun processo `python.exe` con `--app-window` né `msedge.exe`
legato alla cartella temporanea (compreso il processo in background
dell'osservazione al punto 4); cartella temporanea eliminata.
