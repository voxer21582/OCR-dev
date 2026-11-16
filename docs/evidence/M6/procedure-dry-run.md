# M6 — Prova della procedura sul PC di sviluppo (Task 10)

Data: 2026-11-16. Procedura provata: [`docs/runtime/m6-lifecycle-procedure.md`](../../runtime/m6-lifecycle-procedure.md). Solo i passi possibili senza collegamenti nel menu Start, con il build di prova (`-DOCR2_TEST`); la matrice del PC pulito (`lifecycle-matrix.md`) resta **da eseguire dal proprietario**.

## Condizioni

- `<run>` = scratchpad in forma 8.3 + `\dr`; `LOCALAPPDATA` del processo = `<run>\local`, `TEMP=TMP=<run>\tmp`; installazione con `/S /D=<run>\Programs\OCR2`; `OCR2-0.6.0-setup-test.exe` e `OCR2-0.6.1-setup-test.exe` (`build_installer.py --test --test-data-root <run>`). Prima della prova: `%LOCALAPPDATA%\Programs\OCR2` reale e cartella OCR2 del menu Start reale **assenti**; dopo: **assenti**. Percorso reale dell'utente mai letto né toccato dall'impronta.
- `user-footprint.ps1` eseguito con `-LocalAppData <run>` (contiene `local`, `tmp` e `Programs`), `-StartMenu <run>\start`, `-RegistryRoot HKCU:\Software\OCR2DryRunNonexistent` (chiave inesistente: nessun nome di chiave del profilo reale letto). Gli output delle impronte stanno nello scratchpad, **non** nel repository.
- Processi avviati: `OCR2.exe` (versione attiva), Edge con il profilo di prova; fermati con «Esci» e, per i resti, con terminazione dei soli processi sotto `<run>`. Nessun processo rimasto.
- Passi non eseguibili qui (richiedono clic nella finestra o il menu Start): menu Start e collegamenti, fascicolo/Archivio e R14 (già descritto in `app-window.md`), SmartScreen, disinstallazione dal menu con risposta Sì/No (provata con `/S` e `/S /REMOVEDATA`). Un file `synthetic-note.txt` fa le veci dei dati.

## Esiti (numeri = passi della procedura)

| # | Passo | Esito |
|---|---|---|
| 1 | Impronta prima | `prima.txt`: 3 voci, 0,4 s (sulla cartella di prova) |
| 3 | Installazione 0.6.0 `/S` | codice 0, 25 s; `active.txt` `0.6.0`/vuoto; `versions` = `0.6.0`; contenuto `OCR2.exe`, `active.txt`, `uninstall.exe`, `versions`; `opencv_videoio_ffmpeg*`: **0** |
| 3b | Impronta con OCR2 installato | 4220 voci in 15 s; confronto con «prima»: 4217 differenze, **4213 con «OCR2»** nel percorso e 4 senza (`Programs` e tre cartelle `local\Microsoft\Windows\Caches` create da Windows durante l'installazione) |
| 4 | Avvio con `OCR2.exe` e «Informazioni» | pronto in 8,4 s; Versione 0.6.0; «verificato (3745 file, **7,3 s**)» la prima volta; negli avvii successivi 4,9–6,8 s (macchina occupata dalla prova; costo di ≈4 s dichiarato, R24) |
| 8 | Porta e chiusura della finestra | porta letta da `instance.json`: 51195; `Get-NetTCPConnection -LocalPort 51195 -State Listen` → `127.0.0.1:51195`, stesso processo di `netstat -ano` (`LISTENING`); `CloseMainWindow` sulla finestra Edge del profilo di prova: porta libera e `instance.json` assente dopo **13,4 s**; a porta libera `Get-NetTCPConnection` non stampa nulla e `netstat` mostra solo connessioni `TIME_WAIT` senza stato `LISTENING` |
| 6 | «Esci» (POST) | risposta 200; porta libera in 1,1–1,5 s (7 volte); nessun `pythonw.exe` rimasto |
| 7 | Edge dopo «Esci» (R18) | con «Esci» i processi `msedge.exe` del profilo di prova (8–9 subito dopo) scompaiono con qualche secondo di ritardo: la prova li ha terminati subito (nessuno rimasto). R18 osservato: al termine della prova restava un `msedge.exe --no-startup-window /prefetch:5` (con i suoi 4 processi figli), nato durante la prova dal primo Edge del profilo di prova (avvio rapido sul profilo normale di Edge, qui nel `LOCALAPPDATA` di prova): ha tenuto aperti file di `<run>\local` fino alla pulizia, quando l'ho terminato (solo quell'albero). Limite dichiarato di Edge, non di OCR2 |
| 9 | Aggiornamento interrotto (0.6.0 attiva) | installer 0.6.1 terminato dopo 609 file estratti (`taskkill /F`, uscita 1); `active.txt` prima e dopo `0.6.0`; resta `versions\0.6.1` parziale; `OCR2.exe` → Versione 0.6.0 |
| 10 | Aggiornamento con OCR2 aperto (R8) | `/S` (silenzioso: messaggio non visibile): codice **2**; `active.txt` `0.6.0`; `versions` = `0.6.0` (il parziale 0.6.1 cancellato) |
| 11 | Aggiornamento a 0.6.1 | codice 0, 53,5 s; `active.txt` `0.6.1`/`0.6.0`; dati identici (SHA-256); Versione 0.6.1 |
| 12 | Versione già attiva (R7/R29) | `/S`: codice **2**, `active.txt` invariato, nessun messaggio mostrato (silenzioso) |
| 13 | Ritorno (`OCR2.exe /rollback`) | finestra «OCR2»: «Versione attiva: 0.6.0», codice 0, 6,7 s; `active.txt` `0.6.0`/`0.6.1`; Versione 0.6.0 all'avvio; nessuna reinstallazione |
| 14a | Disinstallazione con OCR2 aperto (R8) | `uninstall.exe /S _?=<base>`: **rimane in attesa** (0,6 s, ritorna con codice 2), rifiutata; programma, `active.txt` e dati presenti |
| 14b | Disinstallazione senza dati | `uninstall.exe /S` ritorna subito; in 5,9 s `<base>` eliminata; dati presenti e identici (`document-archive.sqlite3`, `edge-profile`, `instance.lock`, `synthetic-note.txt`) |
| 15 | Reinstallazione 0.6.1 | codice 0, 54,5 s; `active.txt` `0.6.1`/vuoto; dati identici; Versione 0.6.1 |
| 16 | Disinstallazione `/S /REMOVEDATA` | 3,0 s; programma e `<run>\local\OCR2` eliminati |
| 17 | Impronta dopo e confronto | `dopo.txt` 689 voci, 2,4 s. `-Compare prima dopo`: 686 differenze, **0 con «OCR2»**, 1 riga `D Programs` (vedi sotto), 685 altre, **0** chiavi `HKCU`. Le 685 altre sono create da Edge (cartelle `Microsoft\Edge\User Data` nel `LOCALAPPDATA` di prova) e dai file temporanei in `tmp`: sono proprio il «rumore» che il filtro della procedura scarta |

Filtro della procedura (`Select-String … -Pattern 'OCR2|\tD\tPrograms$'`) provato sui file veri: restituisce 1 riga (`+ LOCALAPPDATA	D	Programs`); conteggio delle altre 685, `HKCU` 0.

## Cosa la prova ha trovato

1. **La cartella `%LOCALAPPDATA%\Programs` resta vuota dopo la disinstallazione** se prima non esisteva: l'installer la crea (`Programs\OCR2`), la disinstallazione toglie `OCR2` ma non `Programs`. Un filtro solo su «OCR2» la nasconderebbe: la procedura la gestisce esplicitamente (passo 17). Non è modificata nell'installer in questo task.
2. Il confronto prima/installato (4217 differenze) mostra che quasi tutto il footprint dell'installazione è `Programs\OCR2\…`; nulla in `HKCU` (0 chiavi cambiate: V4 confermato sulla cartella di prova).
3. Il codice di uscita 2 e il silenzio dei messaggi (R29) sono confermati in `/S`: il codice 2 compare sia per «già installata» sia per il rifiuto R8; il messaggio non si vede in `/S`.
4. `uninstall.exe /S _?=<cartella>` è utile per aspettare il risultato quando la disinstallazione **viene rifiutata**; nel caso di successo, il programma non cancella la cartella stessa (comportamento NSIS di `_?=`) e la prova non lo ha usato.

## Pulizia

`<run>` (compresi i due installer di prova, che contengono il percorso dello scratchpad), `installer/out/OCR2-*-setup-test.exe` e le impronte nello scratchpad cancellati; nessun processo rimasto. Nessun output di impronta di profili reali nel repository.
