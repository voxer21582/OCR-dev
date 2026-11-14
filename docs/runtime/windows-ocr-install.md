# Windows OCR runtime: install and start (candidate procedure)

This is the procedure verified for the **candidate** runtime on CPython 3.13 x64, Windows 11. It is not an installer, a redistribution approval or an accepted runtime; see the [acceptance plan](windows11-acceptance-plan.md).

## Create the environment

Use a virtual environment outside the repository and install only from the hash-locked file. The command refuses any package whose hash differs and downloads nothing else:

```powershell
python -m venv C:\ocr2\venv
C:\ocr2\venv\Scripts\python.exe -m pip install --no-input --only-binary=:all: --require-hashes -r requirements\ocr2-runtime-cp313-win-amd64.lock
```

The lock is [`requirements/ocr2-runtime-cp313-win-amd64.lock`](../../requirements/ocr2-runtime-cp313-win-amd64.lock): the 21 evaluation packages plus `pypdfium2` 5.15.2, which PDF rendering needs. The two PP-OCRv6 small models used by the factory ship inside the `rapidocr` wheel; nothing is downloaded at install or run time, and the factory refuses models whose SHA-256 differs from its pins.

## Start with local OCR

From `application/`:

```powershell
$env:PYTHONPATH = "src"
C:\ocr2\venv\Scripts\python.exe -m alfa_document_intelligence --ocr-engine rapidocr-v6
```

When `--ocr-engine rapidocr-v6` is given, the launcher checks the runtime **before** it opens a port: the exact RapidOCR version, the two model hashes, and the presence of ONNX Runtime, NumPy and Pillow. If any of these fail, it prints every problem, exits with code 2 and starts nothing. A missing `pypdfium2` is only a warning: images still work, PDFs cannot be read. Without the option, OCR stays disabled and no check runs.

## Limits of this procedure

- Verified with synthetic files only, on one development PC.
- It does not select, sign or package an installer, and it does not cover updates or rollback.
- Licences and notices of the bundled models and native libraries still need review before any redistribution.
