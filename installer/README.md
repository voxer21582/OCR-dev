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

Uscita: 0 riuscito, 2 errore di costruzione, 3 **BLOCCATO** (impronta diversa).

`installer/.cache/` e `installer/out/` sono ignorate da git.

## Impronte

`pins.json` registra file, URL, dimensione, SHA-256 e fonte dell'impronta; le stesse voci sono in `docs/dependencies-approved.md` (gruppo 4). Per cambiare versione: aggiornare entrambi dopo l'approvazione del proprietario.
