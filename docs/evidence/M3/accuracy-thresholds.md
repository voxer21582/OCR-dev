# M3 — Soglie di accuratezza sintetica (fissate prima della misura)

**Requisiti:** REQ-057, REQ-026 (parte sintetica), REQ-051, REQ-052, REQ-055. Registrate il 2026-11-15 **prima** di eseguire `tools/run_field_benchmark.py`; la misura le confronta con i risultati e non le modifica.

**Insieme di prova:** `ocr2-field-benchmark-v1`, generato da `tools/field_benchmark_fixtures.py`.
- 60 giustificativi sintetici: 30 in italiano e 30 in inglese; 30 PNG e 30 PDF raster.
- Testo pulito con il carattere incluso in Pillow, una riga per campo.
- **Controllo preliminare:** con una lettura perfetta del testo (token costruiti dalle righe del manifest), le regole di estrazione trovano il valore giusto nel 100% dei casi per ogni campo. Le differenze nella misura vera dipendono quindi dall'OCR.

**Metrica:** quota di documenti in cui il primo valore che chi rivede vede per il campo è uguale al valore atteso. Il primo valore è quello osservato, oppure la prima alternativa di un candidato incerto.

| Campo | Soglia |
|---|---|
| `total_amount` | ≥ 95% |
| `issue_date` (primo suggerimento) | ≥ 95% |
| `currency` | ≥ 95% |
| `document_number` | ≥ 90% |
| `vat_registration_number` | ≥ 90% |
| `merchant_name` | ≥ 80% |

**Limiti:**
- sono testi sintetici puliti, quindi queste soglie non dicono nulla su scansioni, foto o documenti veri;
- le soglie per i documenti veri si fissano in M8 (Q-002);
- un campo sotto soglia non porta ad abbassare la soglia: si registra il risultato e si decide con il proprietario.
