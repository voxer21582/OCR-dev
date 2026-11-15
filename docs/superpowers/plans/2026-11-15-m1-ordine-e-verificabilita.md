# M1 — Ordine e verificabilità: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rendere provabile secondo GOAL.md tutto ciò che esiste già: PR riordinate, evidenze nel repository, benchmark rigenerabile da script, tutti i test in CI.

**Architecture:** nessuna funzione nuova per l'utente. Si aggiungono un generatore deterministico di fixture (Pillow), una funzione di punteggio pura testata in CI, uno script locale che esegue il benchmark sul server reale, e si estende il workflow esistente con i moduli mancanti e un job Windows.

**Tech Stack:** Python 3.13, unittest/pytest, Pillow 13.0.0 e pypdfium2 5.15.2 (già approvati), GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](../specs/2026-11-15-ocr2-product-completion-design.md); requisiti in [`docs/requirements.md`](../../requirements.md); milestone in [`docs/plan.md`](../../plan.md).

## Global Constraints

- Solo dipendenze di `docs/dependencies-approved.md`; nessuna installazione nel sistema; venv esistente per pytest.
- Solo dati sintetici, generati da script nel repository (GOAL V2).
- Nessuna modifica a Windows o a risorse Google (V4); stop/no-retry (V6): un errore esterno si registra e ci si ferma.
- Lavorare solo nel worktree `C:\Users\voxer\ocr2-phase2a\plan` (o un worktree nuovo per ogni PR) e su branch propri; mai `reset --hard`, `clean`, `push --force` (V7).
- Ogni PR che tocca `local_document_store.py`, `document_export.py`, rotte di archivio/fascicoli/export in `local_intake_app.py` o i loro test dichiara «R7/R8» e attende l'approvazione esplicita del proprietario (DEC-001).
- Nessuna PR si chiude o si unisce senza il sì del proprietario (DEC-019).
- File di testo con fine riga CRLF nel working copy restano tali (il repository normalizza a LF).
- Commit con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; autore impostato con `-c user.name="Claude Code" -c user.email="noreply@anthropic.com"`.

## Review Focus

1. **Fixture non deterministiche:** due generazioni sullo stesso PC devono dare byte identici; PDF e JPEG di Pillow possono includere date o metadati variabili → fissare `creationDate`/`modDate` e non scrivere EXIF.
2. **Moduli che passano su Windows e falliscono su Linux** (percorsi, DPAPI, fine riga, fuso orario): ogni salto su Linux deve avere un motivo esplicito ed eseguire il modulo nel job Windows.
3. **Il punteggio confonde «possibile» con «confermato»:** una riga con `possible_amount_conflict` non conta come abbinata; un giustificativo in `unused` non conta come usato.
4. **Il runner del benchmark tocca l'archivio reale dell'utente:** deve sempre impostare un `LOCALAPPDATA` temporaneo per il processo server e rifiutarsi di partire se il percorso risultante è sotto il profilo reale.
5. **Evidenze con dati sensibili:** i file in `docs/evidence/` non devono contenere percorsi del profilo utente; il test di guardia esistente (`test_public_data_guard`) si estende alla cartella `docs/evidence/`.

---

### Task 1: Rassegna delle PR aperte

**Files:**
- Create: `docs/evidence/M1/pr-triage.md`

**Interfaces:**
- Consumes: `gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,updatedAt,mergeable,files`
- Produces: tabella con una raccomandazione per PR (`unire`, `chiudere: superata da …`, `ripartire da main`, `lasciare aperta: motivo`) e una colonna «Decisione del proprietario» vuota.

- [ ] **Step 1:** raccogliere i dati di tutte le PR aperte (oggi 30) con il comando sopra; per ciascuna, verificare se le sue modifiche sono già su `main` (`git log origin/main --oneline --grep` sul titolo o `git cherry origin/main <branch>`).
- [ ] **Step 2:** scrivere la tabella; #144 e #141 in cima. #141 è superata da `docs/requirements.md` (raccomandazione: chiudere).
- [ ] **Step 3:** commit (`docs: M1 PR triage`) e chiedere al proprietario le decisioni in un unico messaggio. **Fermarsi** fino alla risposta; eseguire solo le azioni approvate e registrarle nella tabella.

### Task 2: Evidenze della base di partenza

**Files:**
- Create: `docs/evidence/baseline/README.md`, `docs/evidence/baseline/2026-11-15-m2-case-benchmark.md` (copia del contenuto di `docs/product/m2-case-benchmark.md` da #144, se unita; altrimenti un riassunto con link alla PR)
- Modify: `application/tests/test_public_data_guard.py` (aggiungere `docs/evidence/` alle cartelle controllate)

**Interfaces:**
- Produces: indice con, per ogni evidenza esistente, requisito REQ-xxx, fonte (PR/issue con link), data, host, esito, limiti.

- [ ] **Step 1: test che fallisce** — in `test_public_data_guard.py`, `test_evidence_folder_is_scanned`: crea in una cartella temporanea `docs/evidence/x.md` contenente `C:\Users\someone\` e verifica che la guardia lo segnali.
- [ ] **Step 2:** `cd application; $env:PYTHONPATH='src;tests'; python -B -m unittest -v test_public_data_guard` → FAIL.
- [ ] **Step 3:** estendere la guardia alla cartella `docs/evidence/` (stesse regole delle altre cartelle di documentazione).
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5:** scrivere l'indice dalle fonti elencate in `docs/product/requirements.md` §12 (PR #133, #138–#144, issue #106, #134, #135, #9). Solo riassunti e link; nessun log privato.
- [ ] **Step 6:** commit (`docs: baseline evidence register`).

### Task 3: Generatore delle fixture del benchmark del fascicolo

**Files:**
- Create: `application/tools/case_benchmark_fixtures.py`, `application/tests/test_case_benchmark_fixtures.py`

**Interfaces:**
- Produces:
  - `generate_case_benchmark(output_dir: Path) -> dict` scrive `statement.pdf`, `receipts/receipt-NNN.{png,jpg,pdf}` (NNN = 001…100) e `manifest.json`, e restituisce il manifest.
  - Manifest: `{"version": "ocr2-case-benchmark-v1", "files": {nome: sha256}, "statement_rows": [{"row": int, "date": "2026-11-DD", "amount": "n,nn", "currency": "EUR", "receipt": int | null}], "receipts": [{"receipt": int, "file": str, "date": "2026-11-DD", "amount": "n,nn", "expected": "match" | "amount_conflict" | "unused"}]}`.
  - CLI: `python -m tools.case_benchmark_fixtures OUTPUT_DIR` (da `application/`).

Valori fissati dallo spec del benchmark (`docs/product/m2-case-benchmark.md`):
- 100 giustificativi: 60 PNG, 25 JPEG, 15 PDF; uno per file; testo `Ricevuta NNN`, `Data: dd/mm/2026`, `Totale: EUR n,nn`.
- Nota spese PDF di 4 pagine, 98 righe, intestazione `Pagina N di 4` su ogni pagina.
- Giustificativi 1–95 hanno una riga con lo stesso importo, tranne 10, 20, 30 la cui riga ha un importo diverso (`amount_conflict`); 3 righe senza giustificativo con importi `777,77`, `888,88`, `999,99`; giustificativi 96–100 senza riga (`unused`).
- Tutte le date a novembre 2026; esattamente 43 righe con giorno ≤ 12.
- Determinismo: importi e date da una funzione pura dell'indice (nessun `random` senza seme fisso); `ImageFont.load_default()`; PDF salvati con `creationDate` e `modDate` fissati a `datetime(2026, 11, 1, tzinfo=timezone.utc)`; JPEG con `quality=90`, senza EXIF.

- [ ] **Step 1: test che falliscono** (pytest):
  - `test_counts`: 100 file in `receipts/` con 60 `.png`, 25 `.jpg`, 15 `.pdf`; `statement.pdf` ha 4 pagine (pypdfium2).
  - `test_known_answers`: 98 righe; `receipt` nullo esattamente per `777,77`, `888,88`, `999,99`; `expected == "amount_conflict"` esattamente per 10, 20, 30; `"unused"` esattamente per 96–100; 43 righe con giorno ≤ 12.
  - `test_deterministic`: due generazioni in due cartelle temporanee → stesso dizionario `files`.
  - `test_manifest_hashes_match_files`: lo SHA-256 di ogni file scritto è quello del manifest.
- [ ] **Step 2:** `cd application; python -B -m pytest -q tests/test_case_benchmark_fixtures.py` → FAIL (modulo assente).
- [ ] **Step 3:** implementare `generate_case_benchmark` in `application/tools/case_benchmark_fixtures.py`.
- [ ] **Step 4:** stesso comando → PASS; poi `python -B -m unittest -v test_public_data_guard` → PASS.
- [ ] **Step 5:** commit (`test: deterministic case benchmark fixture generator`).

### Task 4: Punteggio del benchmark (funzione pura, in CI)

**Files:**
- Create: `application/tools/case_benchmark_score.py`, `application/tests/test_case_benchmark_score.py`

**Interfaces:**
- Consumes: manifest del Task 3; export JSON del fascicolo prodotto da `GET /cases/{case_id}/export`.
- Produces: `score_case_export(export: dict, manifest: dict) -> dict` con le chiavi `statement_lines_found`, `header_lines_proposed`, `correct_receipt_ranked_first` (`[n, 92]`), `amount_conflicts_flagged` (`[n, 3]`), `missing_support_rows` (`[n, 3]`), `unused_receipts` (lista ordinata), `ambiguous_dates_with_correct_hint` (`[n, 43]`), `ambiguous_candidates`. Solo numeri e numeri di giustificativo, mai testo.

- [ ] **Step 1: test che falliscono:** costruire un export sintetico minimo a mano (2 righe abbinate, 1 `possible_amount_conflict`, 1 `missing_support`, 1 giustificativo non usato) e verificare: `test_possible_conflict_is_not_a_match` (la riga in conflitto non conta in `correct_receipt_ranked_first`), `test_unused_receipts_listed`, `test_output_contains_no_text` (nessun valore stringa nell'output tranne le chiavi).
- [ ] **Step 2:** `python -B -m pytest -q tests/test_case_benchmark_score.py` → FAIL.
- [ ] **Step 3:** implementare, leggendo la struttura reale dell'export da `_build_case_reconciliation` in `local_intake_app.py` e dalla fixture di `test_expense_reconciliation_ui.py`.
- [ ] **Step 4:** → PASS. Commit (`test: case benchmark scoring`).

### Task 5: Esecuzione locale del benchmark

**Files:**
- Create: `application/tools/run_case_benchmark.py`
- Create (output): `docs/evidence/M1/<data>-case-benchmark.md`

**Interfaces:**
- Consumes: Task 3, Task 4; `python -m alfa_document_intelligence --ocr-engine rapidocr-v6 --port 0`.
- Produces: CLI `python -m tools.run_case_benchmark --fixtures DIR --out REPORT.json`.

Comportamento: crea una cartella temporanea, la imposta come `LOCALAPPDATA` del solo processo server figlio (e verifica che non sia sotto `%USERPROFILE%\AppData\Local`), avvia il server, legge la porta dalla riga «Apri http://…», crea il fascicolo con la nota, carica i 100 giustificativi in 5 blocchi da 20, avvia l'OCR, interroga lo stato del lavoro, scarica l'export, calcola il punteggio, misura tempi di caricamento e di OCR, ferma il server e cancella la cartella temporanea.

- [ ] **Step 1:** implementare il runner (nessun test automatico: richiede il runtime OCR; la logica testabile sta nel Task 4).
- [ ] **Step 2:** generare le fixture in una cartella temporanea ed eseguire il runner sul PC di sviluppo. Atteso: `correct_receipt_ranked_first == [92, 92]`, `amount_conflicts_flagged == [3, 3]`, `unused_receipts == [96, 97, 98, 99, 100]`, `header_lines_proposed == 0` (con #144 su `main`; altrimenti registrare i valori ottenuti e il motivo).
- [ ] **Step 3:** scrivere `docs/evidence/M1/<data>-case-benchmark.md` (commit, host, tempi, punteggi, impronta del manifest, limiti). Commit (`docs: M1 case benchmark evidence`).

### Task 6: Tutti i test in CI (Ubuntu) e job Windows

**Files:**
- Modify: `.github/workflows/ocr2-synthetic-taxonomy.yml`
- Create: `requirements/ci-taxonomy-cp313-win-amd64.lock`, `requirements/ci-pytest-cp313-win-amd64.lock`, `requirements/ci-decoder-cp313-win-amd64.lock` (stesse versioni dei lock Ubuntu; SHA-256 delle wheel `win_amd64` o `py3-none-any` dai metadati PyPI, DEC-011)
- Modify: `README.md` (sezione CI)
- Modify, solo se serve: i moduli di test che falliscono su Linux (marcatori `skipif` con motivo)

I 19 moduli oggi fuori da CI: `test_evidence_linked_review_ui`, `test_expense_case_intake_routes`, `test_expense_case_processing`, `test_expense_case_store`, `test_expense_reconciliation_ui`, `test_fingerprints`, `test_local_document_archive_ui`, `test_local_document_store`, `test_local_intake_app`, `test_local_launcher`, `test_loopback_csrf`, `test_manual_chatgpt_handoff_ui`, `test_manual_region_review`, `test_multipage_tiff_processing_contract`, `test_ocr_job_ui`, `test_ocr_launcher_contract`, `test_ocr_processing`, `test_security_gate`, `test_synthetic_ocr_metrics`. Più i nuovi `test_case_benchmark_fixtures` e `test_case_benchmark_score`.

- [ ] **Step 1:** in locale, `cd application; python -B -m pytest -q -rs tests` → registrare `passed/skipped` (oggi 660 passed, 1 skipped su #144).
- [ ] **Step 2:** aggiungere i 21 moduli al passo pytest del job Ubuntu esistente (il nome del job **Taxonomy registry and binding** non cambia: è il controllo obbligatorio di `main`).
- [ ] **Step 3:** aggiungere il job `windows-contracts` su `windows-2025` con le stesse azioni fissate per SHA, i tre lock Windows con `--require-hashes` e `python -B -m pytest -q -rs tests` da `application/`.
- [ ] **Step 4:** push del branch; leggere i risultati dei due job. Per ogni fallimento: se dipende da Windows (DPAPI, percorsi), `skipif(sys.platform != "win32", reason="…")` e conferma che passa nel job Windows; se è un difetto, superpowers:systematic-debugging. Un fallimento esterno (rete del runner, servizio GitHub) si registra e **non** si ripete in varianti (V6); una ripetizione singola del job è ammessa solo per un timeout già osservato come instabile, dichiarandolo.
- [ ] **Step 5:** atteso: entrambi i job verdi; ogni `SKIPPED` ha un motivo; salvare l'estratto in `docs/evidence/M1/<data>-ci.md` con i link alle esecuzioni.
- [ ] **Step 6:** chiedere al proprietario se rendere obbligatorio anche `windows-contracts` (impostazione di GitHub: la fa il proprietario). Commit e PR (`ci: run every application test module; add Windows job`), segnata R7/R8 perché esegue i test dell'archivio.

### Task 7: Chiusura di M1

**Files:**
- Create: `docs/evidence/M1/review.md`, `docs/evidence/M1/acceptance.md`
- Modify: `docs/STATUS.md`, `docs/requirements.md` (colonna stato)

- [ ] **Step 1:** revisione indipendente del branch (superpowers:requesting-code-review); correggere i problemi rilevanti; salvare il rapporto in `review.md`.
- [ ] **Step 2:** rieseguire tutti i test in locale e in CI.
- [ ] **Step 3:** `acceptance.md`: per ogni REQ di M1 (`docs/plan.md`), il criterio e il link all'evidenza.
- [ ] **Step 4:** `STATUS.md` in cima: `STATO: MILESTONE COMPLETATA — M1` con l'elenco dei criteri e i link. Commit e PR; merge solo con il sì del proprietario.
