# Operating rules for Codex and contributors

1. This repository is a new project. Do not copy code, configuration, dependencies, model artifacts, or historical outputs from the previous OCR project. Reuse only explicitly authorized requirements and lessons, and record their provenance.
2. Never automatically upload real company documents, raw OCR, or personal data to public CI, cloud OCR services, external services, or this repository. CI uses only synthetic fixtures; OCR, extraction, validation, and review run locally. The user selected a manual ChatGPT drafting exception documented in `ARCHITECTURE.md`: show a copyable prompt containing only minimum human-verified fields and necessary context; do not send files/raw OCR or call an API. Any external paste is a deliberate user action and must be permitted by the organization. Treat returned text as an untrusted draft requiring local human review.
3. Do not install dependencies, download models, change TLS settings, or provision infrastructure without explicit authorization. Keep TLS verification enabled.
4. Keep OCR observation, semantic interpretation, document validation, and administrative verification separate. A POS slip is not automatically a fiscal document. Never auto-approve reimbursements, payments, or accounting entries.
5. Every extracted field must retain source-document hash and page/region evidence. Preserve alternatives and uncertainty; never invent a value. Do not label uncertain values as confirmed.
6. Treat PDFs, images, and ZIP contents as untrusted. Define limits, validate paths and resource expansion, and avoid executing embedded content.
7. Maintain versioned schemas, decisions, benchmark splits, risk entries, and `CURRENT_STATE.md`. State only verified test/workflow results and cite the command or artifact.
8. For each task, state objective and acceptance criteria, make the smallest change, run the relevant authorized automated checks, review regressions, and update project status/documentation.
9. Keep benchmark development, regression, and independent frozen samples disjoint. Never tune against the frozen sample or infer labels from model output.
10. Do not commit secrets, real samples, derived sensitive text, or unreviewed dependency/model licenses.
