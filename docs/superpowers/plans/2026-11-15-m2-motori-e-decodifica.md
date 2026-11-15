# M2 — Motori e decodifica: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere un motore OCR deve richiedere solo file nuovi; le anteprime non decodificano più nel processo web; i PDF con testo usano il testo incorporato; le pagine ruotate vengono lette; GIF a fotogramma singolo e BMP sono ammessi.

**Architecture:** un pacchetto `alfa_document_intelligence.engines` dove ogni modulo dichiara un `MANIFEST`; un registro li scopre senza importare i motori; il launcher e il worker usano il registro. Il testo incorporato nei PDF e la rotazione stanno nel percorso di decodifica ed elaborazione, indipendenti dal motore.

**Tech Stack:** Python 3.13, Pillow 13.0.0, pypdfium2 5.15.2 (approvati), unittest/pytest.

**Spec:** [`docs/superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](../specs/2026-11-15-ocr2-product-completion-design.md) §7; requisiti REQ-014, 020, 021, 022, 023, 025, 027, 028, 030 in [`docs/requirements.md`](../../requirements.md); [`docs/product/format-evaluation-gif-bmp.md`](../../product/format-evaluation-gif-bmp.md).

## Global Constraints

- Nessuna dipendenza nuova: solo `docs/dependencies-approved.md`.
- Solo dati sintetici generati nei test; nessun file binario di fixture nuovo nel repository se si può generare.
- Errori con codici stabili, mai testo dei documenti o percorsi.
- OCR spento di default; nessun download; i motori si importano solo nel worker.
- Non toccare R7/R8 (archivio ed export) salvo le righe di `local_intake_app.py` delle anteprime (Task 4): la PR lo dichiara e attende l'ok del proprietario (DEC-001).
- Ogni modulo di test nuovo va in entrambi i job CI (`test_ci_workflow` lo impone).
- Commit con autore `Claude Code <noreply@anthropic.com>` e riga `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Manifest malformato o duplicato** (id ripetuto, versione vuota, factory non importabile): il registro deve rifiutarlo con codice stabile, non scegliere a caso.
2. **Motore che dichiara un'identità diversa dal manifest** (nome o versione dell'adattatore ≠ manifest): il worker deve fallire con `engine_identity_mismatch` prima di produrre risultati.
3. **PDF con testo incorporato vuoto o parziale** (solo spazi, testo invisibile, pagina mista immagine+testo): non deve sostituire l'OCR quando il testo è insufficiente.
4. **Anteprima di un file malformato o che fa scadere il tempo:** risposta d'errore controllata, server ancora vivo.
5. **GIF animata o con schermo logico enorme:** rifiuto con codice stabile prima di decodificare tutti i fotogrammi.

---

### Task 1: Registro dei motori a manifest

**Files:**
- Create: `application/src/alfa_document_intelligence/ocr_engine_registry.py`, `application/src/alfa_document_intelligence/engines/__init__.py`, `application/src/alfa_document_intelligence/engines/rapidocr_v6.py`
- Test: `application/tests/test_ocr_engine_registry.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class EngineManifest: engine_id: str; name: str; version: str; languages: tuple[str, ...]; license: str; artifacts: tuple[tuple[str, str], ...]; factory_ref: str; runtime_check_ref: str | None; selectable: bool = True` (`selectable=False` = solo test, non offerto dal launcher)
  - `class EngineRegistryError(ValueError)` con `code` in {`manifest_invalid`, `engine_id_duplicate`, `engine_unknown`}
  - `discover_engines(package: str = "alfa_document_intelligence.engines") -> dict[str, EngineManifest]`: importa solo i moduli manifest del pacchetto (che non importano il motore) e valida ogni `MANIFEST`.
  - `get_engine(engine_id: str, *, package: str = ...) -> EngineManifest`
  - `engines/rapidocr_v6.py`: `MANIFEST = EngineManifest(engine_id="rapidocr-v6", name=<adapter.name>, version="3.10.0", languages=("it", "en"), license="Apache-2.0", artifacts=MODEL_ARTIFACTS, factory_ref="alfa_document_intelligence.rapidocr_runtime_factory:create_rapidocr_v6_multilingual_adapter", runtime_check_ref="alfa_document_intelligence.rapidocr_runtime_factory:check_rapidocr_runtime")`

- [ ] Test che falliscono: `test_discovers_rapidocr_manifest_without_importing_rapidocr` (dopo `discover_engines()`, `"rapidocr"` non è in `sys.modules`), `test_rejects_duplicate_ids`, `test_rejects_invalid_manifest` (id con caratteri non `[a-z0-9-]`, versione vuota, factory_ref non `modulo:nome`, hash non di 64 esadecimali), `test_unknown_engine_has_stable_code`. I casi negativi usano un pacchetto temporaneo creato in `tmp_path` e aggiunto a `sys.path`.
- [ ] Eseguire → FAIL; implementare; eseguire → PASS; commit.

### Task 2: Launcher e worker guidati dal registro

**Files:**
- Modify: `application/src/alfa_document_intelligence/__main__.py`, `application/src/alfa_document_intelligence/ocr_processing.py`
- Test: `application/tests/test_ocr_launcher_contract.py`, `application/tests/test_ocr_processing.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `--ocr-engine` accetta `disabled` più gli id del registro; il controllo all'avvio usa `runtime_check_ref` del manifest; `OCRProcessingManager(adapter_factory_ref, limits, *, expected_identity: tuple[str, str] | None = None)`; nel worker, dopo `factory()`, se `(adapter.name, adapter.version) != expected_identity` lo stato è `failed` con `error_code="engine_identity_mismatch"` (nuovo codice stabile).

- [ ] Test che falliscono: `test_engine_choices_come_from_registry` (con registro finto patchato, `--ocr-engine synthetic-x` accettato e `_FakeManager` riceve il factory_ref del manifest), `test_unknown_engine_is_rejected_by_argparse`, `test_identity_mismatch_fails_closed` (factory sintetica che dichiara versione diversa → `engine_identity_mismatch`, nessun risultato).
- [ ] FAIL → implementare → PASS (suite completa) → commit.

### Task 3: Motore di prova aggiunto solo con file nuovi (REQ-023)

**Files (solo nuovi):**
- Create: `application/src/alfa_document_intelligence/engines/synthetic_fixed.py`, `application/tests/test_synthetic_fixed_engine.py`

**Interfaces:**
- Produces: `MANIFEST` con `engine_id="synthetic-fixed"`, `license="Apache-2.0"` (codice del repository), `artifacts=()`; `SyntheticFixedAdapter` (name `synthetic-fixed`, version `1`) che restituisce un token fisso `SYNTHETIC` sull'intera pagina con confidenza 1.0. Il manifest ha `selectable=False`: il launcher non lo offre all'utente, i test lo usano tramite il registro.

- [ ] Test che falliscono: `test_registry_lists_synthetic_engine` (presente in `discover_engines()`, assente dalle scelte di `--ocr-engine`), `test_document_processed_end_to_end_with_synthetic_engine` (un PNG generato con Pillow passa per `OCRProcessingManager` con la factory del manifest e il record ha `engine_name == "synthetic-fixed"` e provenienza completa).
- [ ] FAIL → implementare → PASS → commit. **Evidenza:** `git diff --name-status` del commit mostra solo `A` (aggiunte) più l'aggiunta del modulo di test ai due job CI. Ruling atteso: la riga del workflow è configurazione di CI, non codice del sistema.

### Task 4: Anteprime decodificate in un worker isolato (REQ-030, R7/R8)

**Files:**
- Modify: `application/src/alfa_document_intelligence/local_intake_app.py` (`_source_page_png`)
- Test: `application/tests/test_local_intake_app.py`

**Interfaces:**
- Consumes: `iter_decoded_pages_isolated` (esistente, `isolated_decoder.py`).
- Produces: `_source_page_png` usa `iter_decoded_pages_isolated(..., timeout_seconds=30)`; errori → `DocumentDecodeError` già gestito dalle rotte (risposta 4xx/5xx senza contenuto).

- [ ] Test che falliscono: `test_preview_decodes_in_isolated_worker` (patch di `iter_decoded_pages_isolated` registra la chiamata; `iter_decoded_pages` diretto non viene chiamato), `test_malformed_pdf_preview_fails_closed` (PDF troncato sintetico → status d'errore, app risponde ancora a `GET /`).
- [ ] FAIL → implementare → PASS → commit (messaggio con «R7/R8: preview route only»).

### Task 5: Testo incorporato dei PDF come produttore distinto (REQ-027)

**Files:**
- Create: `application/src/alfa_document_intelligence/pdf_text_layer.py`
- Modify: `application/src/alfa_document_intelligence/document_processing.py` (scelta per pagina), schema/contratti solo se il nome del produttore è vincolato
- Test: `application/tests/test_pdf_text_layer.py`

**Interfaces:**
- Produces: `PDF_TEXT_PRODUCER = ("pdf-text-layer", <versione pypdfium2>)`; `extract_text_tokens(source_bytes: bytes, page_number: int, *, min_chars: int = 20) -> list[OCRToken] | None` (None quando il testo utile è sotto soglia o il PDF non ha testo); token con riquadri normalizzati 0–1 dalla pagina pypdfium2, `confidence=None`. In `process_document_record`, per una pagina PDF con token dal testo incorporato si costruisce l'`OCRPageResult` con `engine_name="pdf-text-layer"` e non si chiama il motore.
- Il testo incorporato viene estratto nel worker (stesso processo isolato del decoder), mai nel processo web.

- [ ] Test che falliscono: PDF sintetico con testo creato con pypdfium2 (`PdfDocument.new`, pagina con testo in un font standard) → token con il testo e riquadri dentro la pagina; PDF solo immagine (Pillow) → `None` e si usa il motore; pagina con soli spazi → `None`; il record risultante nomina `pdf-text-layer` come produttore.
- [ ] FAIL → implementare → PASS (suite) → commit.

### Task 6: Rotazioni di 90°/180°/270° (REQ-028, SHOULD)

**Files:**
- Modify: `application/src/alfa_document_intelligence/document_processing.py`
- Test: `application/tests/test_document_processing.py` (nuova classe `OrientationTests`)

**Interfaces:**
- Produces: `choose_orientation(adapter, page: RasterPage, languages) -> tuple[int, OCRPageResult]`: riconosce a 0°; se i token sono meno di 3 o la confidenza media è sotto 0,5 prova 90/180/270 e tiene il risultato con più caratteri riconosciuti × confidenza media; la rotazione scelta è registrata nella provenienza della pagina (`orientation_degrees`) e i poligoni sono riportati nelle coordinate della pagina originale.

- [ ] Test che falliscono con un adattatore sintetico che «legge» solo se l'immagine ha un pixel marcatore nell'angolo in alto a sinistra: pagina ruotata di 90° → rotazione 270 scelta e poligoni riportati alla pagina originale; pagina diritta → una sola chiamata all'adattatore.
- [ ] FAIL → implementare → PASS → commit. Se lo schema del record non ammette `orientation_degrees`, aggiungere il campo opzionale con versione di schema invariata solo se lo schema lo permette; altrimenti Ruling e rinvio a M3.

### Task 7: GIF a fotogramma singolo e BMP (REQ-014, SHOULD)

**Files:** quelli elencati nella valutazione (`ingestion.py`, `image_safety.py`, `document_decoder.py`, `isolated_decoder.py`, `local_intake_app.py`, `document_processing.py`, `expense_reports.py`, `review_ui.py`, schema dei media type)
- Test: `application/tests/test_gif_bmp_formats.py`

- [ ] Test che falliscono (fixture generate con Pillow): GIF e BMP con testo accettati con pagina 1 e impronta corretta; estensione sbagliata rilevata dalla firma; GIF animata (2 fotogrammi) rifiutata con codice stabile; schermo logico oltre il limite di pixel rifiutato prima della decodifica; GIF e BMP troncati rifiutati; trasparenza appiattita su bianco.
- [ ] FAIL → implementare → PASS (suite) → commit.

### Task 8: Evidenze, revisione, chiusura

- [ ] Benchmark del fascicolo (M1) rieseguito col motore scelto dal registro: punteggi invariati → `docs/evidence/M2/<data>-case-benchmark.md`.
- [ ] `docs/evidence/M2/engine-diff.md`: elenco dei file del commit del Task 3 (solo aggiunte).
- [ ] CI verde su Ubuntu e Windows → `docs/evidence/M2/<data>-ci.md`.
- [ ] Revisione indipendente → `docs/evidence/M2/review.md`; correzioni con test.
- [ ] `docs/evidence/M2/acceptance.md`, `docs/requirements.md` (stati), `docs/STATUS.md`; PR (R7/R8 per il Task 4) e merge solo con il sì del proprietario.
