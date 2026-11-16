# installer/

Costruzione dell'installer di OCR2 (M6). Solo sul PC di sviluppo Windows; nessun file binario va nel repository.

## Contenuto dell'installer (Task 6)

```
python installer/build_payload.py --version 0.6.0
```

Con il Python 3.13 di sviluppo (lo stesso dei test). Il comando:

1. legge `pins.json` e scarica **una sola volta** in `installer/.cache/` l'embeddable di CPython (R-001) e lo zip portabile di NSIS (R-002, usato dal Task 8); un file che non corrisponde a SHA-256 e dimensione fissati ferma la costruzione (V6), senza nuovi tentativi né altre fonti; un file già in cache che non corrisponde non viene sostituito;
2. scarica le wheel con `pip download --only-binary=:all: --require-hashes --platform win_amd64 --python-version 3.13 -r requirements/ocr2-runtime-cp313-win-amd64.lock -d installer/.cache/wheels` (pip rifiuta impronte diverse);
3. costruisce `installer/out/<versione>/`:
   - `python/`: embeddable estratto; `python313._pth` = `python313.zip`, `.`, `..\app`, `Lib\site-packages`, `import site`;
   - `python/Lib/site-packages/`: wheel del lock installate con `pip install --target --no-deps --no-index --require-hashes --no-compile`, poi compilate in bytecode a controllo di hash (PEP 552) con nomi di file relativi, così nessun `.pyc` contiene la cartella di costruzione;
   - nessun `opencv_videoio_ffmpeg*.dll` (DEC-030) e nessun lanciatore di script (`bin/`, `Scripts/`);
   - `app/alfa_document_intelligence/`: i sorgenti dell'applicazione, senza `tests`, `__pycache__`, `*.pyc`;
   - `runtime-manifest.json`: dimensione e SHA-256 di ogni file, verificato all'avvio (Task 5).

La versione (`--version`) deve essere `MAGGIORE.MINORE.PATCH` ed è scritta come `__version__` nel `__init__.py` copiato in `app/` (R23), prima del manifest.

Uscita: 0 riuscito, 2 errore di costruzione, 3 **BLOCCATO** (impronta diversa).

`installer/.cache/` e `installer/out/` sono ignorate da git.

## Impronte

`pins.json` registra file, URL, dimensione, SHA-256 e fonte dell'impronta; le stesse voci sono in `docs/dependencies-approved.md` (gruppo 4). Per cambiare versione: aggiornare entrambi dopo l'approvazione del proprietario.

## Installer (Task 8)

```
python installer/build_payload.py --version 0.6.1
python installer/build_installer.py --version 0.6.1
python installer/build_installer.py --version 0.6.1 --test --test-data-root <cartella temporanea>
```

`build_installer.py` controlla `installer/out/<versione>/` con il suo `runtime-manifest.json`, verifica lo zip di NSIS con `pins.json` (SHA-256 e dimensione; diverso: **BLOCCATO**, uscita 3) e lo estrae ogni volta da capo in `installer/.cache/nsis-3.13/`, poi esegue `makensis`:

1. `launcher.nsi` → `installer/out/launcher/OCR2.exe` (R6): legge `active.txt` e avvia `versions\<v>\python\pythonw.exe -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6`; `OCR2.exe /rollback` esegue `install_state rollback` e mostra l'esito;
2. `ocr2.nsi` → `installer/out/OCR2-<versione>-setup.exe` (con `--test`: `OCR2-<versione>-setup-test.exe`, `-DOCR2_TEST`).

Cartella del programma (per utente, nessun registro, nessun diritto di amministratore): `%LOCALAPPDATA%\Programs\OCR2\` con `versions\<v>\`, `active.txt` (riga 1 versione attiva, riga 2 precedente), `OCR2.exe`, `uninstall.exe`. I dati restano in `%LOCALAPPDATA%\OCR2\`.

- **Installazione/aggiornamento:** se la versione è già quella attiva: «Questa versione di OCR2 è già installata.», con i rimedi se OCR2 non funziona («Torna alla versione precedente», oppure disinstallare mantenendo i dati e installare di nuovo: non c'è riparazione sul posto, R38), e nessuna modifica (R7); altrimenti `versions\<v>\` rimasta da un'installazione interrotta viene cancellata, il contenuto estratto, e `install_state activate <v>` verifica i file e solo allora riscrive `active.txt` (in modo atomico) e tiene due versioni. Se la verifica fallisce: messaggio, `versions\<v>\` cancellata, resta attiva la versione precedente. Con OCR2 aperto l'attivazione è rifiutata: «Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova.» (R8).
- **Menu Start** (non nella build di prova): cartella «OCR2» con «OCR2» (`OCR2.exe`), «Torna alla versione precedente» (`OCR2.exe /rollback`), «Disinstalla OCR2» (`uninstall.exe`).
- **Disinstallazione:** chiede «Eliminare anche i dati di OCR2 (archivio e catalogo)?» (predefinito: no; in modo silenzioso `/S` i dati restano, salvo `/REMOVEDATA`). `install_state uninstall` rifiuta con OCR2 aperto (R8) e, solo se richiesto, elimina `<LOCALAPPDATA>\OCR2` letto dalla variabile d'ambiente (mai un collegamento, mai altro). Poi NSIS elimina `versions\`, `active.txt`, `OCR2.exe`, `uninstall.exe` e la cartella se vuota.
- **Build di prova** (`--test`): nessun collegamento nel menu Start; installa solo sotto `--test-data-root` (mai in `%LOCALAPPDATA%\Programs\OCR2`), e la disinstallazione passa `--test-data-root`, così i dati si eliminano solo se sono lì dentro. Prova: `LOCALAPPDATA` del processo = cartella temporanea, `OCR2-<v>-setup-test.exe /S /D=<temporanea>\Programs\OCR2`.
