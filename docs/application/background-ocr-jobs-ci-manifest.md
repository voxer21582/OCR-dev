# Background OCR jobs — CI selector manifest

Date: 2026-11-11. Feature base: `main` after [PR #104](https://github.com/voxer21582/OCR-dev/pull/104), merge commit `4271447da4505571ca9087264e18c4a15592b1c8`. CI change is isolated on `codex/ocr-processing-ci` and is not merged.

## Scope

Add only these already-reviewed standard-library unittest modules to the existing explicit application test command:

- `test_ocr_processing`
- `test_ocr_job_ui`
- `test_ocr_launcher_contract`

The suite uses generated/synthetic data and fake OCR engines. It does not load RapidOCR or model files, discover tests automatically, or include R7/R8 or other blocked components.

## Workflow properties retained

- Existing workflow and required check name: `OCR2 synthetic taxonomy` / `Taxonomy registry and binding`.
- Existing push, pull-request, and manual triggers; Ubuntu standard runner; pinned GitHub Actions; `contents: read`; existing hash-locked dependency closure.
- No new dependency, workflow, secret, paid service, security-setting change, or branch-protection change.

## Verification status

The selector edit is explicit and `git diff --check` is required before publication. GitHub Actions has not yet run on this branch; no test count or green status is claimed here until the run is observed. The candidate's 132-test local Windows unittest result is recorded separately in [the feature manifest](background-ocr-jobs-manifest.md); local Windows evidence does not substitute for this CI run.

## Limits

Passing these three modules in Actions will verify only the synthetic worker protocol, lifecycle, UI integration, and launcher wiring covered by those tests. It will not prove native OCR inference, product OCR quality, Windows 11 runtime acceptance, installation, licensing, or full application acceptance.
