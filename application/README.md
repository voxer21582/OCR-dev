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

The repository-root required check runs taxonomy contracts and an explicit allowlist of application contract selectors. As a historical baseline, [main CI run 42519804658](https://github.com/voxer21582/OCR-dev/actions/runs/42519804658) at commit `0a2fba0731e230f385e305826b66e4ce17df854d` passed 22 taxonomy tests and 183 application tests (205 total) on 2026-11-08. Since then, the `origin/main` snapshot `90ae4f9111af5ddad9272ffc20a96acb5311a2f5` has expanded the explicit allowlist to 27 application selectors; the [workflow](../.github/workflows/ocr2-synthetic-taxonomy.yml) is the source of truth for that list. A later PR #100 Actions run passed 22 taxonomy tests and 279 application tests on its candidate branch ([run 42669302926](https://github.com/voxer21582/OCR-dev/actions/runs/42669302926)); this is branch evidence, not a claim about a main-branch run.

PR [#101](https://github.com/voxer21582/OCR-dev/pull/101) adds nine explicit test selectors: review ledger, multipage TIFF processing, OCR metrics, security gate, document export, expense-report bundles, source-bound ZIP intake, in-memory upload materialization, and SQLite fingerprint registry. The earlier head's [Actions run 42977830932](https://github.com/voxer21582/OCR-dev/actions/runs/42977830932) passed 22 taxonomy tests and 315 application tests. Candidate commit `005b58be2430c5d70c2c2c3f09697e7dc6aa309b` passed 22 taxonomy tests and 326 application tests in [run 42983308875](https://github.com/voxer21582/OCR-dev/actions/runs/42983308875); the follow-up documentation commit `c4224b2b973e5fba69a5896b4dceb3500b2a3eb0` passed the same suites in [run 42983769697](https://github.com/voxer21582/OCR-dev/actions/runs/42983769697), with CodeQL reporting no new alerts in [run 130400225933](https://github.com/voxer21582/OCR-dev/runs/130400225933). On candidate head `a56ba76e1e4954becd8840d08dc094c6bcf2a0c9`, [Actions run 42987936681](https://github.com/voxer21582/OCR-dev/actions/runs/42987936681) passed 22 taxonomy tests and 335 explicitly allowlisted application tests, including the six materialized-upload and three fingerprint-registry cases; [CodeQL run 130413739392](https://github.com/voxer21582/OCR-dev/runs/130413739392) completed with no new alerts. PR #101 remains unmerged; these are candidate-branch results, not `main` evidence. The catalog and its CI extension were integrated through [PR #46](https://github.com/voxer21582/OCR-dev/pull/46) and [PR #47](https://github.com/voxer21582/OCR-dev/pull/47); their 41 catalog tests are included in the published baseline.

Other test files in this directory are not automatically selected. Native OCR/PDF behavior, Windows packaging, real-document performance, runtime dependency licensing, archive acceptance, and full product acceptance remain separate gates. The public launcher accepts only the port option and does not yet construct an OCR engine or start background OCR jobs; installing optional packages alone does not enable that flow.
