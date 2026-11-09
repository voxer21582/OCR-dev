# Semantic extraction failure warning

Status: isolated candidate, 2026-11-09. The assigned `OCR-dev-semantic-warning` worktree was initially based on public `6facee4b814b4bffbe0f80a463d9077532313364` and reconciled with accepted main `a92ef319d5fd06ea0a209bbd3d0337e7d693bb81`; the reviewed UI and test bytes remain unchanged. The original historical sources remain intact. Independent technical review is READY. CI changes and publication are separate and require owner review and merge.

## Behavior

The review detail displays an Italian warning that automatic extraction was not completed and manual verification is required when `processing.semantic_extraction.status` is `failed`. For `semantic_proposal_field_limit`, `semantic_proposal_catalog_limit`, and `semantic_proposal_family_limit`, it adds a fixed explanation that a proposal review limit was reached. Missing or other error codes produce the generic warning; their contents are not reflected. The warning does not claim existing fields are absent, and existing field rendering and HTML escaping are retained.

## Verification and boundaries

Five synthetic `unittest` cases passed with the following command, run from `application/` with the already available interpreter:

```powershell
$env:PYTHONPATH='src;tests'
& 'C:/Users/voxer/.codex/worktrees/local-document-store/OCR2-Document-Intelligence-GitHub/.ocr2-rapidocr-demo-venv/Scripts/python.exe' -B -m unittest -v test_semantic_failure_warning.SemanticFailureWarningTests
```

The preceding RED run recorded seven failing subtests at the missing warning assertion; the GREEN run reported five tests passed. Local command output and hashes are retained in `.local-evidence/semantic-warning-20261109/` in the parent workspace. The existing test suite was not run. The tests extract text with the standard-library `HTMLParser`, ignoring script/style contents and attributes; this does not establish actual CSS visibility or accessibility, and no browser verification was performed. No Chrome or server, real data, native processing, new model, R7 or R8 was used for this slice.
