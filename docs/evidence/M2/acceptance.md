# M2 — Accettazione: criteri ed evidenze

Commit di riferimento: `1b98d93` (branch `claude/m2-motori`). Livelli: `SYN-CI` = test sintetici in CI su Ubuntu e Windows ([`2026-11-15-ci.md`](2026-11-15-ci.md)); `LOCAL-RUN` = PC di sviluppo, dati sintetici.

| Requisito | Criterio | Esito | Evidenza |
|---|---|---|---|
| REQ-014 (SHOULD) | GIF a fotogramma singolo e BMP: firma, limiti, input malformati, provenienza | `SYN-CI` | `test_gif_bmp_formats` (14 test: inventario, estensione/firma, schermo logico e fotogramma oltre limite, troncati, GIF animata rifiutata al caricamento, trasparenza su bianco, OCR con provenienza) |
| REQ-020 | Provenienza completa per ogni testo | `SYN-CI` | contratti esistenti; il produttore per pagina distingue `pdf-text-layer` (`test_pdf_text_layer`) |
| REQ-021 | Pipeline e revisione indipendenti dal motore | `SYN-CI` | il motore di prova attraversa la pipeline reale (`test_synthetic_fixed_engine`) |
| REQ-022 | Registro a manifest, scelta del motore, verifica nel worker con codici stabili | `SYN-CI` + `LOCAL-RUN` | `test_ocr_engine_registry`, `test_ocr_launcher_contract`, `test_ocr_processing::test_engine_identity_mismatch_fails_closed` (job Windows); benchmark con `rapidocr-v6` dal registro ([`2026-11-15-case-benchmark.md`](2026-11-15-case-benchmark.md)) |
| REQ-023 | Un motore aggiunto con soli file nuovi | Soddisfatto | [`engine-diff.md`](engine-diff.md) |
| REQ-025 | Pagine fallite senza proposte | `SYN-CI` | contratti esistenti (invariati) |
| REQ-027 (SHOULD) | Testo incorporato dei PDF come produttore distinto | `SYN-CI` | `test_pdf_text_layer` (8 test, inclusi CropBox, rotazione, testo invisibile, scansione con piè di pagina) |
| REQ-028 (SHOULD) | Pagine ruotate di 90/180/270° | `SYN-CI` | `test_page_orientation` (6 test). L'angolo non è registrato nel record (rinviato a M3) |
| REQ-030 | Anteprime in un worker isolato | `SYN-CI` | `test_preview_isolation`, `test_manual_region_review` |

**Revisione indipendente:** [`review.md`](review.md). I 5 problemi importanti sono corretti con test.

**Aperto:**
- fallimento intermittente del lavoro OCR del fascicolo (1 esecuzione su 4, causa non nota), da seguire in M7;
- nessun limite di concorrenza per le anteprime;
- soglia di confidenza 0,5 per le rotazioni da tarare su dati reali (M8).

**Merge:** la PR tocca il helper delle anteprime usato dalle rotte di archivio e fascicolo (R7/R8). Serve l'approvazione del proprietario (DEC-001).
