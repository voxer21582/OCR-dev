# Dipendenze approvate

Fonte: decisione del proprietario del 2026-11-15 («A»: approvati i gruppi 1, 2 e 3 così come sono). Si possono usare **solo** le versioni e le impronte indicate nei file di lock qui citati. Qualsiasi altra dipendenza, versione, runtime o modello va prima in [`dependencies-request.md`](dependencies-request.md) (GOAL V3).

## Gruppo 1 — Runtime OCR per Windows

| Elemento | Versione / impronta | Licenza dichiarata | Fonte |
|---|---|---|---|
| 22 pacchetti Python del runtime | Versioni e SHA-256 in [`requirements/ocr2-runtime-cp313-win-amd64.lock`](../requirements/ocr2-runtime-cp313-win-amd64.lock): certifi 2026.10.23, charset-normalizer 3.5.2, colorama 0.4.6, colorlog 6.12.0, flatbuffers 25.12.19, idna 3.20, numpy 2.5.4, omegaconf 2.4.0, onnxruntime 1.31.1, opencv-python-headless 5.0.0.93, packaging 26.3, pillow 13.0.0, protobuf 7.36.2, pyclipper 1.4.0, pypdfium2 5.15.2, pyyaml 6.0.3, rapidocr 3.10.0, requests 2.34.2, shapely 2.2.0, six 1.17.0, tqdm 4.70.1, urllib3 2.8.0 | Vedi `docs/product/requirements.md` §13 (punti di licenza) | PyPI, installazione solo con `--require-hashes` |
| Modelli PP-OCRv6 small multilingue (rilevamento e riconoscimento) | Dentro la wheel `rapidocr` 3.10.0; SHA-256 fissati nella factory (`rapidocr_runtime_factory.py`) | Apache-2.0 (dichiarata in `MODEL_LICENSES.md`) | Issue #9 |

**Limite:** il file FFmpeg incluso in `opencv-python-headless` (`cv2/opencv_videoio_ffmpeg500_64.dll`, LGPL-2.1) **non entra nell'installer** finché il proprietario non decide (vedi `questions.md`, Q-001, da porre in M6).

## Gruppo 2 — Strumenti dei controlli automatici (CI)

| Lock | Pacchetti |
|---|---|
| [`requirements/ci-taxonomy-cp313-ubuntu-24_04.lock`](../requirements/ci-taxonomy-cp313-ubuntu-24_04.lock) | attrs 26.1.0, jsonschema 4.26.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1 |
| [`requirements/ci-pytest-cp313-ubuntu-24_04.lock`](../requirements/ci-pytest-cp313-ubuntu-24_04.lock) | iniconfig 2.3.1, packaging 26.3, pluggy 1.7.0, pygments 2.21.0, pytest 9.2.0 |
| [`requirements/ci-decoder-cp313-ubuntu-24_04.lock`](../requirements/ci-decoder-cp313-ubuntu-24_04.lock) | pillow 13.0.0, pypdfium2 5.15.2 |

Le stesse versioni possono avere un lock per Windows (per il job CI su Windows, decisione DEC-011), con gli SHA-256 delle wheel `win_amd64` presi dai metadati PyPI. Cambia solo la piattaforma della wheel, non il pacchetto né la versione.

Le GitHub Actions usate dal workflow (`actions/checkout`, `actions/setup-python`) sono fissate per SHA del commit.

## Gruppo 3 — Già presenti sul PC di sviluppo

| Elemento | Uso consentito |
|---|---|
| CPython 3.13 (x64) già installato | Sviluppo e test locali. **Non** è il Python dell'installer (vedi richiesta R-001). |
| Node.js già installato | Solo per `test_region_review_keyboard` (VM integrata di Node, nessun pacchetto npm). |
| Microsoft Edge (parte di Windows 11) | Finestra dell'app in modalità app (DEC-004). Nessuna modifica alle impostazioni di Edge o di Windows. |
| Assistente vocale di Windows (Narrator) | Controllo di accessibilità REV-5 (REQ-075), senza modificare impostazioni di sistema. |
