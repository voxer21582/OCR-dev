# OCR2 Document Intelligence application

This directory contains the local, evidence-grounded OCR2 application. Project planning, issues, taxonomy contracts, and repository-wide CI are maintained at the repository root and in the linked GitHub Project.

## Scope

The application has no OCR dependency enabled by default. OCR remains `not_started` unless a caller supplies a prepared local processor. Tests and fixtures use synthetic data only. The application does not approve reimbursements, payments, or accounting entries.

## Local preview

Use an already approved Python 3.11 environment from this directory:

```powershell
$env:PYTHONPATH = "src"
python -m alfa_document_intelligence --port 8000
```

Open `http://127.0.0.1:8000/`. This preview binds to loopback and is not a production deployment.

## Local expense-case candidate

The current isolated development candidate adds a case workflow for one final expense statement and up to 100 supporting documents. Add receipts in batches of no more than 20, process them locally, then review each suggested match against source-page evidence. Uncertain values remain possible matches for human review; exclusions retain their reason and history. A JSON comparison can be downloaded explicitly from the local app.

This is not yet an accepted live-document demo. The OCR runtime/model on the reference Windows PC, real-document accuracy, visual browser behavior, and performance at 100 documents have not been verified. OCR remains disabled by default; enabling it requires an explicit local `--ocr-engine rapidocr-v6` choice. Do not send expense files, OCR text, source hashes, or comparison exports to this repository, GitHub Actions, or ChatGPT. Use real expense records only within the local application after the runtime is confirmed; automated checks continue to use synthetic fixtures only.

## Verification limits

Continuous integration runs every module under `tests/` on Ubuntu (the required check) and on Windows; see the [repository README](../README.md#continuous-integration). A passing run covers only those synthetic contracts.

Native OCR/PDF behavior, Windows packaging, real-document performance, runtime dependency licensing, archive acceptance, and full product acceptance remain separate gates. The launcher accepts `--port` and `--ocr-engine {disabled,rapidocr-v6}` (default `disabled`); OCR runs only when explicitly enabled and the approved runtime passes the start-up check.
