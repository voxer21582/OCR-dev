# Contributor instructions

## Repository scope

This public repository currently contains only the synthetic-testable taxonomy registry and binding slice of OCR2. It is not the full application. Treat the README, linked GitHub Project, issue acceptance criteria, and approved project decisions as the source of current scope. Do not infer that a local component is approved for transfer or publication.

## Data and provenance

- Use synthetic fixtures in this repository and public CI. Never commit company documents, real OCR text, personal data, credentials, secrets, or derived sensitive values.
- Keep real-document OCR, interpretation, validation, review, and drafting local to an authorized environment.
- Do not copy code, configuration, dependencies, models, or historical outputs from the previous OCR project. Record provenance for any explicitly authorized reused requirement or lesson.
- Keep OCR observation, semantic interpretation, validation, review, and administrative confirmation separate. Every extracted field must retain the source-document hash and page/region evidence. Preserve alternatives and uncertainty; never invent a value or label an uncertain value as confirmed.
- OCR2 supports human review; never automatically approve reimbursements, payments, or accounting entries. A POS slip or payment proof is not automatically a fiscal document.

## Work and review

- Before changing files, read the relevant issue, its acceptance criteria, current project priorities, and any approved design or active gate. Make the smallest change that satisfies the authorized scope.
- Use a dedicated branch and pull request. Do not merge pull requests, bypass branch protection, or change repository permissions, required checks, or governance without explicit owner approval.
- Assign one owner to each edited file. Use agents only for bounded independent work; keep implementation and final-diff review separate where practical. The coordinator remains responsible for the result.
- Report what was implemented, which checks ran, their exact scope, and what remains unverified. Do not claim full OCR2 readiness from a narrow contract check.
- Update documentation only when evidence changes or a durable rule needs clarification. Avoid duplicating requirements and session reports.

## Verification and CI

- The current `Taxonomy registry and binding` workflow runs the two synthetic taxonomy test modules described in the README. Its 22 tests cover that slice only; they do not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.
- Run only checks authorized for the issue and available evidence. Do not install dependencies, download models, or alter TLS settings without explicit authorization; keep TLS verification enabled.
- Workflow changes belong in a separate pull request. Review triggers, permissions, untrusted code exposure, and cost before proposing them. Preserve read-only permissions and full-SHA action pins unless an approved change says otherwise.

## Project restrictions

- Preserve R7/R8 stop/no-retry restrictions. Do not test or modify blocked R7/R8 scopes; issue #8 remains out of scope until its overlap is clarified. Ownership confirmation or a green CI check does not authorize resumption.
- Issue #1 remains dependent on A4 and A5. Do not select an OCR runtime/model, authorize real-data use, or start a pilot without the required owner decisions.
- Use the linked GitHub Project for current tracking. Mark work accepted only when its criteria and evidence are reviewed; an open pull request, passing CI, or administrative closure alone is not product acceptance.
