# M2 — Benchmark del fascicolo con il motore scelto dal registro (2026-11-15)

**Requisiti:** REQ-022 (il launcher sceglie `rapidocr-v6` dal registro) e REQ-062 (nessuna regressione). **Livello:** `LOCAL-RUN`. Dati sintetici, un PC, CPU.

**Procedura:** la stessa di M1 ([`../M1/2026-11-15-case-benchmark.md`](../M1/2026-11-15-case-benchmark.md)), con le stesse fixture (impronta `6bcdb274…ed99`). Il server parte con `--ocr-engine rapidocr-v6`, che ora arriva dal manifest `engines/rapidocr_v6.py`.

| Esecuzione | Commit | Esito | OCR |
|---|---|---|---|
| 1 | `13afb1e` | **fallita**: «OCR job did not complete»; codice d'errore non catturato e registro cancellato per errore | — |
| 2 | `13afb1e`, script con codice d'errore | riuscita | 144,7 s (1,39 s/pagina) |
| 3 | `13afb1e` | riuscita | 138,7 s (1,33 s/pagina) |
| 4 | `1b98d93` (codice finale) | riuscita | 140,7 s (1,35 s/pagina) |

Punteggi delle esecuzioni 2–4, identici fra loro e a M1:
- righe trovate: 98 su 98; intestazioni scambiate per righe: 0;
- giustificativo giusto al primo posto: 92 su 92, tutti abbinamenti *possibili*;
- conflitti d'importo segnalati: 3 su 3;
- date ambigue con il suggerimento corretto: 40 su 40;
- giustificativi non usati: 96, 98, 99 (limite noto per M3);
- tentativi di connessione o DNS non di loopback: 0 / 0.

**Problema aperto: fallimento intermittente.**
- Una esecuzione su quattro è fallita e la causa non è nota: il codice d'errore non era catturato e il registro è stato cancellato prima dell'analisi (errore mio).
- È lo stesso sintomo del «lavoro bloccato non riprodotto» annotato nell'issue #106 prima di M2.
- Il revisore indipendente esclude come causa le modifiche deterministiche di M2. Come causa plausibile indica le letture ruotate aggiuntive, senza poterla confermare; la correzione della revisione non ruota più le pagine bianche.
- Ora lo script riporta fase e codice d'errore. Un nuovo fallimento ne darà la causa: da seguire in M7 (affidabilità e prestazioni).
