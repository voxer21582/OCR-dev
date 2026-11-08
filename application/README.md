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

## Verification limits

The repository-root required check currently validates only taxonomy registry and binding contracts. Application test files are included for review but are not automatically executed by that required check. Native PDF isolation, Windows packaging, real-document performance, runtime dependency licensing, and product acceptance remain separate gates.
