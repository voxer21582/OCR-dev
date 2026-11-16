# M6 — Contenuto dell'installer: costruzione reale (Task 6)

Data: 2026-11-16. PC di sviluppo Windows 11 x64. Costruzione con il Python 3.13.15 di sviluppo (`<repo>`/../venv-pytest).
Prove con `LOCALAPPDATA` temporaneo (`<scratchpad>\lad-run`, `<scratchpad>\lad-final`), mai l'archivio dell'utente; solo immagine sintetica.

## Impronte fissate (V6, R11)

| File | Versione | Byte | SHA-256 | Fonte dell'impronta |
|---|---|---|---|---|
| `python-3.13.17-embed-amd64.zip` | CPython 3.13.17 | 11 441 267 | `9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38` | pagina di rilascio python.org `python-31317`; il file scaricato coincide |
| `nsis-3.13.zip` | NSIS 3.13 | 2 363 925 | `ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8` | calcolata al primo download (NSIS non pubblica SHA-256); coincide con l'SHA-256 dell'elenco file di SourceForge |

URL: `https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip`,
`https://downloads.sourceforge.net/project/nsis/NSIS%203/3.13/nsis-3.13.zip` (SourceForge sceglie il mirror; l'impronta lo copre).

Versione di Python: 3.13.18 (usata dal job CI Ubuntu) non ha embeddable: è una release solo sorgente, senza pacchetti Windows
(pagina di rilascio: «No installers … Python 3.13.17 was the last bugfix release of Python 3.13 with binary installers»).
L'embeddable più recente pubblicato è quindi 3.13.17, la stessa versione del job CI Windows.

Wheel: le 22 wheel di `requirements/ocr2-runtime-cp313-win-amd64.lock` (113 705 219 byte in `installer/.cache/wheels`),
scaricate con `pip download --require-hashes` e installate con `pip install --require-hashes --no-index`: nessuna impronta diversa.

NSIS è solo scaricato e verificato; si usa dal Task 8.

## Costruzione

```
> python installer/build_payload.py --version 0.6.0
...
Successfully installed certifi-2026.10.23 charset-normalizer-3.5.2 colorama-0.4.6 colorlog-6.12.0 flatbuffers-25.12.19 idna-3.20 numpy-2.5.4 omegaconf-2.4.0 onnxruntime-1.31.1 opencv-python-headless-5.0.0.93 packaging-26.3 pillow-13.0.0 protobuf-7.36.2 pyclipper-1.4.0 pypdfium2-5.15.2 pyyaml-6.0.3 rapidocr-3.10.0 requests-2.34.2 shapely-2.2.0 six-1.17.0 tqdm-4.70.1 urllib3-2.8.0
Rimosso (DEC-030): python/Lib/site-packages/cv2/opencv_videoio_ffmpeg500_64.dll
Contenuto costruito: <repo>\installer\out\0.6.0 (3742 file, 287447306 byte)
```

Durata circa 1,5 minuti (wheel già in cache).

| Misura | Valore |
|---|---|
| File nel manifest | 3 742 (più `runtime-manifest.json`) |
| Dimensione dei file elencati | 287 447 306 byte (≈ 274 MiB) |
| `python/` | 286 486 451 byte |
| `app/` | 960 858 byte |
| SHA-256 di `runtime-manifest.json` | `fe08d94249684345954f27193e131d765570f1a714799e5d93f00ebfdbdd8e9a` |
| `opencv_videoio_ffmpeg*.dll` nel contenuto | nessuno |
| `bin/`, `Scripts/` in site-packages | nessuno |
| File che contengono il nome della cartella utente | 0 (i `.pyc` hanno nomi di file relativi) |

`python313._pth`:

```
python313.zip
.
..\app
Lib\site-packages
import site
```

`sys.path` del Python installato: `python\python313.zip`, `python`, `app`, `python\Lib\site-packages` (sotto `<repo>\installer\out\0.6.0`).
`python.exe -VV`: `Python 3.13.17 (tags/v3.13.17:64e080d, Oct 21 2026, 14:08:53) [MSC v.1944 64 bit (AMD64)]`.

## Avvio con il Python installato

```
> set LOCALAPPDATA=<scratchpad>\lad-final
> installer\out\0.6.0\python\python.exe -B -u -m alfa_document_intelligence --ocr-engine rapidocr-v6 --port 0
Apri http://127.0.0.1:49671/ nel browser. Il server ascolta solo su loopback.
OCR locale RapidOCR 3.10.0 abilitato su richiesta; pacchetto, modelli e identità del motore saranno verificati nel worker isolato.
Archivio locale cifrato attivo: %LOCALAPPDATA%\OCR2\document-archive.sqlite3
```

Pronto in 4,7 s, poi terminato. L'avvio arriva al server solo se la verifica del runtime è riuscita (altrimenti esce con
codice 2 prima di aprire la porta) e se il controllo del runtime OCR di `rapidocr-v6` è riuscito (altrimenti errore
«OCR locale non utilizzabile»). Senza `--app-window` lo stato della verifica non viene stampato (R3: `/app/info`
mostra «non verificato (avvio da sorgenti)» perché `app_info` è assente in questa modalità); per questo è misurato
direttamente con la stessa funzione dell'avvio:

```
> python.exe -B -c "from alfa_document_intelligence.__main__ import _verify_runtime; print(_verify_runtime(False))"
verificato (3742 file, 4.6 s)
verificato (3742 file, 4.3 s)
verificato (3742 file, 4.3 s)
```

**Tempo di verifica all'avvio: 3,7–4,6 s** (dieci misure su tre costruzioni), misurato chiamando direttamente `_verify_runtime`
(la funzione che l'avvio esegue prima di aprire la porta), non dall'output dell'avvio. **Limite misurato**: circa 4 s
a ogni avvio per l'hash di ≈ 274 MiB; accettato per M6, i budget di tempo si fissano in M7.

Controllo del runtime OCR (`runtime_check_ref` del manifest del motore `rapidocr-v6`): `ok=True`, nessun problema, nessun avviso.

Controprova: una riga aggiunta a `app\alfa_document_intelligence\app_window.py` →

```
I file di OCR2 non sono integri:
- File alterato: app/alfa_document_intelligence/app_window.py
exit=2
```

File ripristinato, verifica di nuovo riuscita.

## Versione nel contenuto (R23)

`build_payload` scrive `__version__ = "<versione>"` nel `__init__.py` **copiato** in `app/` prima del manifest
(l'hash nel manifest è quello del file aggiornato); `--version` deve essere `MAGGIORE.MINORE.PATCH`
(`--version 0.6` → «versione non valida»). Il `__version__` del repository è ora `0.6.0`.
Dopo la ricostruzione: `import alfa_document_intelligence` dal Python installato dà `0.6.0`, e `/app/info`
del server avviato mostra «Versione 0.6.0 · Python 3.13.17».

## OCR sintetico senza FFmpeg

Sonda `application/tests/ffmpeg_probe.py` (immagine disegnata dalla sonda) eseguita con il Python installato:

```
{"cv2_folder": "<repo>\\installer\\out\\0.6.0\\python\\Lib\\site-packages\\cv2", "ffmpeg_dlls": [], "texts": ["FATTURA N. 2024/0153", "TOTALE EUR 1.234,50"]}
```

Testo riconosciuto uguale a quello atteso; nessun DLL FFmpeg nella cartella di `cv2`. Dopo l'OCR la verifica del
runtime è ancora riuscita (nessun file scritto nelle cartelle del programma).
