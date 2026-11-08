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

The repository-root required check runs taxonomy contracts and an explicit allowlist of application contract modules. On 2026-11-08, [main CI run 42519804658](https://github.com/voxer21582/OCR-dev/actions/runs/42519804658) at commit `0a2fba0731e230f385e305826b66e4ce17df854d` passed 22 taxonomy tests and 183 application tests: **205 synthetic tests** in total. The [workflow](../.github/workflows/ocr2-synthetic-taxonomy.yml) gives the exact list of 13 application modules. The catalog and its CI extension were integrated through [PR #46](https://github.com/voxer21582/OCR-dev/pull/46) and [PR #47](https://github.com/voxer21582/OCR-dev/pull/47); their 41 catalog tests are now included in main.

Other test files in this directory are not automatically selected. Native OCR/PDF behavior, Windows packaging, real-document performance, runtime dependency licensing, archive acceptance, and full product acceptance remain separate gates. The public launcher accepts only the port option and does not yet construct an OCR engine or start background OCR jobs; installing optional packages alone does not enable that flow.
