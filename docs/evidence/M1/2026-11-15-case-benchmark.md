# M1 — Benchmark del fascicolo rigenerabile (2026-11-15)

**Requisiti:** REQ-003 (fixture generate da script), REQ-062 (riconciliazione), REQ-127/REQ-128 (misure preliminari; l'accettazione delle prestazioni è in M7), REQ-121 (indizio, non prova forte).

**Livello:** `LOCAL-RUN`. Dati sintetici, un PC, CPU, nessuna revisione indipendente.

## Come riprodurlo

Da `application/`, con il venv costruito dal lock del runtime approvato:

```powershell
python -B -m tools.case_benchmark_fixtures <cartella-fixture>
python -B -m tools.run_case_benchmark --fixtures <cartella-fixture> --work-dir <cartella-vuota> --out report.json
```

| Elemento | Valore |
|---|---|
| Commit | branch `claude/m1-ordine`, a partire da `89ec8d7` (generatore `0995b5d`, punteggio `b57060d`, script di esecuzione in questo commit) |
| Host | PC di sviluppo, Windows 11 (10.0.26300), CPython 3.13.15, RapidOCR 3.10.0 con PP-OCRv6 (`--ocr-engine rapidocr-v6`) |
| Fixture | `ocr2-case-benchmark-v1`: nota spese PDF di 4 pagine con 98 righe, più 100 giustificativi (60 PNG, 25 JPEG, 15 PDF). Impronta SHA-256 dell'elenco dei file: `6bcdb2746df7744a97c1709d22ff22a516ceef6ee403b3b54c662f694819ed99`. Identica in due generazioni con due venv diversi (Pillow 13.0.0). |
| Archivio | `LOCALAPPDATA` temporaneo dentro la cartella di lavoro, mai quello dell'utente |
| Rete | Hook Python nel server e nei worker OCR: conta i tentativi di connessione e di DNS non di loopback |

## Risultati

Due esecuzioni sullo stesso set di fixture. I punteggi sono uguali: la tabella mostra la seconda, ricalcolata con lo script di punteggio corretto (vedi sotto).

| Misura | Esito | Atteso |
|---|---|---|
| Allegati accettati (5 blocchi da 20) | 100 / 100 | 100 |
| Righe della nota trovate | **98 / 98** | 98 |
| Intestazioni di pagina proposte come righe | **0** | 0 |
| Giustificativo giusto al primo posto (righe con importo corrispondente) | **92 / 92** | 92 |
| Conflitti d'importo segnalati (giustificativi 10, 20, 30) | **3 / 3**, come `possible_amount_conflict` | 3 |
| Righe senza giustificativo con esito `missing_support` | 2 / 3 | 3 (vedi limiti) |
| Giustificativi elencati come non usati | 96, 98, 99 | 96–100 (vedi limiti) |
| Date ambigue con il suggerimento giorno/mese corretto | **40 / 40** | 40 |
| Righe con candidati alla pari (`ambiguous_candidates`) | 1 | 0 (vedi limiti) |
| Pagine elaborate | 104 | 104 |
| Tempo OCR e analisi | 112,6 s (1,08 s/pagina) e 138,8 s (1,33 s/pagina) | ≤ 3 s/pagina (REQ-127) |
| Caricamento | 1,5 s | — |
| Tentativi di connessione o DNS non di loopback | **0 / 0** | 0 |

## Due errori trovati e corretti durante la prova (nei miei strumenti, non nell'app)

1. **Script di esecuzione bloccato.** Alla prima esecuzione una richiesta di stato è scaduta dopo 120 s. Causa: il server scrive una riga di registro per ogni richiesta e lo script non leggeva più il suo output, quindi il canale si riempiva e il server si fermava. Ora l'output va su un file nella cartella di lavoro.
2. **Conteggio delle date ambigue.** Lo script di punteggio contava come ambigue anche le 3 righe datate 11/11/2026, che non lo sono perché giorno e mese coincidono; l'app le tratta correttamente come certe. Corretto, con il test `test_same_day_and_month_is_not_an_ambiguous_date`. Il denominatore giusto è 40, non 43: il valore 43 del benchmark di M2 contava allo stesso modo i giorni ≤ 12.

## Limiti e problemi aperti dell'app

- **Giustificativo avanzato proposto a righe dello stesso giorno** (limite già noto da M2, REQ-062):
  - il giustificativo 97 (7 novembre, nessuna riga) è proposto come possibile importo discordante alla riga da 999,99 dello stesso giorno, che quindi non risulta `missing_support`;
  - il giustificativo 100 (10 novembre, nessuna riga) è proposto alla riga 10, che ha già un conflitto d'importo con il proprio giustificativo; la riga mostra due candidati alla pari.

  Sono suggerimenti, non abbinamenti, ma per chi rivede sono rumore. Da valutare in M3 (riconciliazione): per esempio, non proporre un giustificativo avanzato a una riga che ha già un candidato migliore.
- Il registro di rete è un hook a livello Python: non vede il codice nativo né l'UDP. La prova forte di assenza di traffico è REQ-121 in M7.
- Un PC, documenti sintetici con un carattere pulito: le misure non prevedono il comportamento su scansioni o foto.
