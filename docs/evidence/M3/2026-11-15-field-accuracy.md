# M3 — Accuratezza sintetica dei campi (2026-11-15)

**Requisiti:** REQ-057, REQ-026 (sintetico), REQ-051, REQ-052, REQ-055. **Livello:** `LOCAL-RUN`. Le soglie sono state fissate prima in [`accuracy-thresholds.md`](accuracy-thresholds.md) (commit `f45e036`) e non sono cambiate.

**Insieme di prova:** `ocr2-field-benchmark-v1` (60 giustificativi: 30 in italiano e 30 in inglese; 30 PNG e 30 PDF raster).

**Esecuzione:** PC di sviluppo Windows 11, CPython 3.13.15, RapidOCR 3.10.0 con PP-OCRv6 scelto dal registro, comando `python -m tools.run_field_benchmark`. Nessun errore OCR in nessuna delle due esecuzioni.

| Campo | Soglia | Esecuzione 1 (`f45e036`) | Esecuzione 2 (`39dea21`, dopo la correzione) |
|---|---|---|---|
| `total_amount` | ≥ 95% | **86,7%** (52/60) — sotto soglia | **100%** (60/60) |
| `issue_date` | ≥ 95% | 100% | 100% |
| `currency` | ≥ 95% | 100% | 100% |
| `document_number` | ≥ 90% | 100% | 100% |
| `vat_registration_number` | ≥ 90% | 100% | 100% |
| `merchant_name` | ≥ 80% | **76,7%** (46/60) — sotto soglia | **90%** (54/60) |
| Tempo | — | 101,6 s | 96,7 s |

**Esecuzioni 3 e 4 (dopo la revisione indipendente).**
- **Esecuzione 3** (`ed976ae`): esercente **0%**, tutti gli altri campi 100%. La causa era nello script di misura, non nell'app. Lo script caricava ogni giustificativo come se fosse la nota spese (famiglia `expense_report`), e la revisione aveva appena escluso le note spese dalla regola dell'esercente. Le esecuzioni 1 e 2 avevano quindi misurato i giustificativi come note.
- **Esecuzione 4**, con lo script corretto (`8342d13`: una nota fittizia prende il ruolo di nota spese, il giustificativo è un allegato come nell'app): totale, data, valuta, numero documento e partita IVA 100%; **esercente 90%** (inglese 100%, italiano 80%); nessun errore OCR; 95,2 s. **Tutte le soglie sono superate.** È il risultato di riferimento per M3.

**Causa dei risultati sotto soglia nell'esecuzione 1: un difetto dell'app, non dei documenti di prova.**
- L'OCR perde gli spazi e legge, per esempio, `Total:EUR186.03`.
- La regola degli importi non accettava un numero attaccato a un codice di valuta, quindi il totale non veniva proposto. Di conseguenza mancava anche l'esercente, la cui regola richiede un importo sulla pagina.
- È lo stesso tipo di difetto corretto per le righe della nota spese in #135.
- **Correzione:** commit `39dea21`, test `test_attached_currency_amounts` (prima rosso, poi verde). Le soglie non sono state toccate.

**Errori rimasti (esecuzione 2):**
- 6 nomi di esercente italiani mancati. Nei casi controllati l'OCR ha letto il nome senza spazio (per esempio `FarmaciaCentrale`); non tutti i 6 casi sono stati ispezionati.
- Con una lettura perfetta del testo le regole danno 100% su ogni campo: lo verifica il test `test_rules_find_every_field_when_the_text_is_read_perfectly` in CI.

**Limiti:**
- testo sintetico pulito, un carattere, un PC;
- non prevede il comportamento su scansioni, foto o documenti veri: le soglie reali si fissano in M8.
