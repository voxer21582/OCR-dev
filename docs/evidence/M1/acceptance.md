# M1 — Accettazione: criteri ed evidenze

Commit di riferimento: `7dfd36f` (branch `claude/m1-ordine`).

Livelli di prova:
- **`SYN-CI`**: test sintetici che girano in CI su entrambi i job (Ubuntu e Windows). Vedi [`2026-11-15-ci.md`](2026-11-15-ci.md).
- **`LOCAL-RUN`**: prova sul PC di sviluppo con dati sintetici.

## Requisiti propri di M1

| Requisito | Criterio | Esito | Evidenza |
|---|---|---|---|
| REQ-001 | File di processo di GOAL presenti e `STATUS.md` aggiornato | Soddisfatto | PR #145; `docs/STATUS.md` |
| REQ-002 | Ogni affermazione di completamento rimanda a `docs/evidence/` | Soddisfatto per M1 | questo file; [`baseline/README.md`](../baseline/README.md) |
| REQ-003 | Fixture del benchmark generate da script, impronta identica in due generazioni | Soddisfatto | `test_case_benchmark_fixtures::test_deterministic` (CI); [`2026-11-15-case-benchmark.md`](2026-11-15-case-benchmark.md) (stessa impronta con due venv) |
| REQ-004 | Ogni modulo di test in CI; salti motivati; job Windows | Soddisfatto | [`2026-11-15-ci.md`](2026-11-15-ci.md); guardia `test_ci_workflow` |
| REQ-010 | Formati, numero di pagine, firma, rifiuto con codice stabile | `SYN-CI` | `test_ingestion`, `test_document_decoder_contract`, `test_document_decoder`, `test_tiff_offset_fixture`, `test_multipage_tiff_processing_contract` |
| REQ-011 | Limiti di intake al limite e oltre | `SYN-CI` | `test_ingestion`, `test_materialized_upload_batch`, `test_expense_reports` |
| REQ-013 | Duplicati esatti segnalati | `SYN-CI` | `test_ingestion`, `test_expense_reports`, `test_expense_reconciliation` |
| REQ-015 | PDF cifrati rifiutati con codice stabile | `SYN-CI` (prima solo in locale) | `test_document_decoder`, `test_document_decoder_contract` |
| REQ-024 | Worker isolato: limiti, annullamento, timeout | `SYN-CI` (test Job Object sul job Windows) | `test_ocr_processing`, `test_isolated_decoder`, `test_expense_case_processing` |
| REQ-029 | OCR spento di default; runtime incompleto segnalato all'avvio | `SYN-CI` | `test_ocr_launcher_contract`, `test_rapidocr_runtime_factory`, `test_local_launcher` |
| REQ-062 | Riconciliazione: fixture a risposta nota e benchmark rigenerabile | `SYN-CI` + `LOCAL-RUN` | `test_expense_reconciliation`; [`2026-11-15-case-benchmark.md`](2026-11-15-case-benchmark.md). **Limite aperto per M3:** un giustificativo avanzato viene proposto a righe dello stesso giorno. |
| REQ-074 | Revisione della riconciliazione legata alla revisione corrente | `SYN-CI` (prima solo in locale) | `test_expense_reconciliation_ui`, `test_expense_case_intake_routes` |
| REQ-076 | Tempo di revisione esportabile in CSV | `SYN-CI` | `test_local_intake_app`, `test_ocr_job_ui` |
| REQ-109 | Stop/no-retry e annullamento affidabile | `SYN-CI` | `test_ocr_processing`, `test_expense_case_processing`, `test_ocr_job_ui` |
| REQ-120 | Loopback, host, origine e token | `SYN-CI` (prima in parte solo in locale) | `test_loopback_csrf`, `test_local_intake_app`, `test_expense_case_intake_routes` |
| REQ-123 | CSP, nosniff, no-store | `SYN-CI` (prima solo in locale) | `test_local_intake_app`, `test_review_ui`, `test_manual_region_review` |

## Requisiti già coperti, di cui M1 registra l'evidenza

REQ-040, 043, 044, 050, 054, 056, 061, 063, 071 e 126 sono `SYN-CI` tramite i moduli di contratto, tutti nella stessa esecuzione CI:
- `test_document_family_catalog`, `test_semantic_proposals`, `test_document_contract`, `test_contract_baseline`;
- `test_expense_line_extraction`, `test_document_validation`, `test_tax_exact_arithmetic`;
- `test_review_ledger`, `test_public_data_guard`;
- `test_taxonomy_registry` e `test_taxonomy_binding`.

## Revisione indipendente

[`review.md`](review.md).

## Decisioni del proprietario (2026-11-15): «approvo tutte e tre»

1. **Rassegna delle PR:** approvata anche per le 18 PR aggiunte; le 17 PR superate sono chiuse ([`pr-triage.md`](pr-triage.md)).
2. **Controllo obbligatorio Windows:** approvato. Lo attiva il proprietario nelle impostazioni del repository (regola di protezione di `main`), perché è un'impostazione di sicurezza del repository.
3. **Merge della PR #146:** approvato (R7/R8, DEC-001).
