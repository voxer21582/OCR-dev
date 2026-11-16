# M6 — Installer per utente sul PC di sviluppo: installazione, aggiornamento, ritorno indietro, disinstallazione (REQ-102, REQ-104, REQ-106)

Data: 2026-11-16. PC di sviluppo Windows 11 x64, NSIS 3.13 portabile (`installer/.cache/nsis-3.13.zip`, SHA-256 verificata da `build_installer.py` prima di ogni estrazione).

## Condizioni e sicurezza

- Solo **build di prova** (`build_installer.py --test --test-data-root <run>`, cioè `-DOCR2_TEST`): nessun collegamento nel menu Start; l'installer rifiuta `%LOCALAPPDATA%\Programs\OCR2` e qualsiasi cartella fuori da `<run>`; la disinstallazione passa `--test-data-root <run>` a `install_state`.
- `<run>` = `<scratchpad>\lc`. Processo di prova con `LOCALAPPDATA=<run>\local`, `TEMP=TMP=<run>\tmp`. Installazione sempre con `/S /D=<run>\Programs\OCR2`.
- Prima della prova lo script ha stampato cartella dati (`<run>\local\OCR2`) e cartella del programma (`<run>\Programs\OCR2`) e controllato che fossero sotto lo scratchpad (altrimenti: interruzione).
- Solo dati sintetici: l'archivio vuoto creato dal primo avvio e un file `synthetic-note.txt` scritto dalla prova. Archivio reale dell'utente mai letto né toccato.
- Arresto dell'app: terminati solo i processi con eseguibile sotto `<run>\Programs\OCR2` e i processi Edge con `<run>\local` nella riga di comando.
- Percorso corto (8.3) dello scratchpad (`<scratchpad-8.3>`): con il percorso lungo dello scratchpad (≈105 caratteri) il file più profondo del contenuto (150 caratteri relativi, in `onnxruntime\tools\...\__pycache__`) supera MAX_PATH (260; `LongPathsEnabled` = 0 su questo PC) e la prima prova si è fermata con «File mancante» per tre file (installer uscito con codice 2, nessuna versione attivata, `versions\0.6.0` cancellata: il percorso di errore funziona). Con il nome corto dello stesso scratchpad il percorso più lungo è di 250 caratteri. Nell'installazione reale il prefisso `%LOCALAPPDATA%\Programs\OCR2\versions\<v>\` è di 58 caratteri con questo utente: 208 caratteri al massimo (vedi «Limiti»).

## Costruzione

| Passo | Durata | Dimensione |
|---|---|---|
| `build_payload.py --version 0.6.0` / `0.6.1` / `0.6.2` (wheel in cache) | 41 / 36 / 40 s | 3745 file, ≈ 288,7 MB ciascuno |
| `build_installer.py --version 0.6.0 --test …` | 165 s | `OCR2-0.6.0-setup-test.exe` 90 641 541 byte |
| `build_installer.py --version 0.6.1 --test …` | 174 s | `OCR2-0.6.1-setup-test.exe` 90 621 995 byte |
| `build_installer.py --version 0.6.2 --test …` | 166 s | `OCR2-0.6.2-setup-test.exe` 90 621 473 byte |

Compressione LZMA solida: ≈ 289 MB → ≈ 86,5 MiB. ``makensis` (V2) senza avvisi nella costruzione; con V3 compare l'avviso 9000 sul nome «setup» (vedi «Limiti»).

## Prova preliminare del percorso di errore

Installer costruito con un contenuto finto (`python.exe` non eseguibile), `/S /D=<scratchpad>\nsistest\inst\OCR2`: codice di uscita 2, `versions\0.0.1` cancellata, nessun `active.txt`. Stesso installer con `/D=` fuori dalla cartella di prova: codice 2, cartella non creata.

## Ciclo di vita (`<scratchpad>\harness\lifecycle.py`, registro `lifecycle-final.log`)

Durata complessiva ≈ 7 min 15 s. Installazione completa 61–68 s, disinstallazione 6–8 s.

| # | Passo | Esito |
|---|---|---|
| 0 | Posizioni reali prima | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\OCR2`: **assente**; `%LOCALAPPDATA%\Programs\OCR2` reale: **assente** |
| 1 | Installazione 0.6.0 (`/S`) | **superato**: codice 0, 61 s; `active.txt` = `0.6.0` / vuoto; `versions` = `0.6.0` |
| 1a | `OCR2.exe` | **superato**: pronto in 5,4 s; processo `<base>\versions\0.6.0\python\pythonw.exe` in ascolto; `/app/info` «Versione 0.6.0», runtime «verificato (3745 file, 4,6 s)»; Edge con profilo in `<run>\local\OCR2\edge-profile` |
| 1b | Dati sintetici | `document-archive.sqlite3` creato dal primo avvio, SHA-256 `5f7f1526…90f0cf`; `synthetic-note.txt` SHA-256 `afe72c0c…16fbeb` |
| 2 | Aggiornamento a 0.6.1 | **superato**: codice 0, 68 s; `active.txt` = `0.6.1` / `0.6.0`; impronte dei dati identiche |
| 2a | `OCR2.exe` | **superato**: `/app/info` «Versione 0.6.1»; dati identici dopo l'avvio |
| 3 | Installer 0.6.1 con 0.6.1 attiva (R7) | **superato**: «Questa versione di OCR2 è già installata.» (in silenzioso non mostrato), uscita in 0,2 s con codice 2, `active.txt` invariato |
| 4 | `OCR2.exe /rollback` | **superato**: finestra «OCR2» con il testo «Versione attiva: 0.6.0» (accenti e testo corretti nell'uscita catturata), codice 0, 6,1 s; `active.txt` = `0.6.0` / `0.6.1` |
| 4a | `OCR2.exe` | **superato**: `/app/info` «Versione 0.6.0» |
| 5 | Aggiornamento interrotto a 0.6.2 | installer terminato (`taskkill /F`) dopo 606 file estratti in `versions\0.6.2`; `active.txt` prima e dopo = `0.6.0` / `0.6.1` |
| 5a | `OCR2.exe` dopo l'interruzione | **superato**: parte la versione attiva, `/app/info` «Versione 0.6.0», runtime verificato |
| 6 | Nuova esecuzione dell'installer 0.6.2 | **superato** (R7): `versions\0.6.2` parziale cancellata e riestratta, codice 0, 67 s; `active.txt` = `0.6.2` / `0.6.0`; `versions` = `0.6.0`, `0.6.2` (0.6.1 eliminata: due versioni) |
| 6a | `OCR2.exe` | **superato**: `/app/info` «Versione 0.6.2» |
| 7 | `python.exe -B -m alfa_document_intelligence.install_state rollback` (Python della 0.6.2) | **superato**: «Versione attiva: 0.6.0», `active.txt` = `0.6.0` / `0.6.2` |
| 8 | Disinstallazione `/S /REMOVEDATA` con OCR2 aperto (R8) | **superato**: rifiutata («Chiudi OCR2 con Esci e riprova.», non visibile in silenzioso); programma, `active.txt` e dati presenti |
| 9 | Disinstallazione `/S` (senza `/REMOVEDATA`) | **superato**: 7,9 s; `<run>\Programs\OCR2` **eliminata**; dati presenti, impronte identiche; restano `document-archive.sqlite3`, `edge-profile`, `instance.json`, `instance.lock`, `synthetic-note.txt` |
| 10 | Reinstallazione 0.6.1 | **superato**: codice 0, 67 s; `active.txt` = `0.6.1` / vuoto; dati identici; `/app/info` «Versione 0.6.1» |
| 11 | Disinstallazione `/S /REMOVEDATA` | **superato**: 5,8 s; `<run>\Programs\OCR2` eliminata, `<run>\local\OCR2` **eliminata**, `<run>\local` (cioè il `LOCALAPPDATA` di prova) ancora presente |
| 12 | Posizioni reali dopo | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\OCR2`: **assente**; `%LOCALAPPDATA%\Programs\OCR2` reale: **assente** |
| 13 | Processi rimasti | nessun processo con eseguibile sotto `<run>` e nessun Edge con il profilo di prova |

Tempi di avvio con `OCR2.exe` (fino a `/app/info` raggiungibile): 5–13 s, di cui verifica del runtime 4,6–10 s (con la macchina occupata dalla prova).

Pulizia: `<run>` cancellata; installer di prova (`OCR2-*-setup-test.exe`, contengono il percorso dello scratchpad) cancellati da `installer/out/`; restano solo i contenuti `installer/out/<v>/` e `installer/out/launcher/OCR2.exe` (ignorati da git).

## Limiti dichiarati

- **Lunghezza dei percorsi**: con `LongPathsEnabled` = 0 il prefisso della cartella `versions\<v>\` non deve superare 109 caratteri. `%LOCALAPPDATA%\Programs\OCR2\versions\<v>\` resta sotto questo limite per nomi utente fino a ≈ 50 caratteri (i nomi degli account locali sono al massimo 20). Una cartella `/D=` molto profonda fa fallire la verifica: l'installer lo dice e lascia attiva la versione precedente.
- Il codice di uscita 2 di «versione già installata» è quello di NSIS per un'uscita dello script; nessuna modifica è fatta.
- In modo silenzioso i messaggi (R7, R8, errori) non sono mostrati; l'esito si vede da codice di uscita e cartelle. `uninstall.exe` si copia in `%TEMP%` e ritorna subito: il suo codice di uscita non dice se la disinstallazione è riuscita.
- Senza Python della versione attiva (programma danneggiato) la disinstallazione elimina il programma ma non può controllare che OCR2 sia chiuso; con `/REMOVEDATA` rifiuta.
- I nomi `OCR2-<v>-setup.exe` contengono «setup»: makensis avverte (9000) che Windows applica gli shim di compatibilità agli installer così chiamati; il manifest `RequestExecutionLevel user` evita l'elevazione.
