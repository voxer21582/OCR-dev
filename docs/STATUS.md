STATO: IN ATTESA DI APPROVAZIONE — M3 (lavoro finito; serve l'ok del proprietario al merge, R8)

# Stato del lavoro

Aggiornato: 2026-11-15.

## M3 — Classificazione ed estrazione

Tutti i compiti del piano M3 sono fatti e la revisione indipendente è chiusa: criteri ed evidenze in [`evidence/M3/acceptance.md`](evidence/M3/acceptance.md). M3 sarà completata dopo il merge della PR (export CSV, R8).

Risultati principali:
- catalogo dei tipi caricato dall'app e modificabile da una pagina «Catalogo», con storico delle versioni;
- i quattro stati di GOAL con il motivo in revisione e nel CSV;
- proposta del nome dell'esercente;
- angolo di rotazione nel record;
- righe di fattura e tabelle, con la verifica «somma delle righe = totale»;
- regole di verifica con versione: i documenti già in revisione non cambiano.

Accuratezza sintetica (60 giustificativi): totale, data, valuta, numero e partita IVA 100%; esercente 90%; tutte le soglie fissate prima sono superate. Tre difetti dell'app trovati e corretti (valuta attaccata, server bloccato da connessioni inattive, modulo da pagina in sandbox).

Righe di fattura su 12 fatture sintetiche: 54/54 corrette, verifica della somma 12/12.

CI: Ubuntu 783 passati e 9 saltati con motivo; Windows 792 passati.

REQ-053 e REQ-064 inclusi in M3 su richiesta del proprietario.

## M2 — Motori e decodifica

Tutti i compiti del piano M2 sono fatti e la revisione indipendente è chiusa: criteri ed evidenze in [`evidence/M2/acceptance.md`](evidence/M2/acceptance.md). M2 è completata: PR #147 unita il 2026-11-15.

Risultati principali (dati sintetici):
- registro dei motori a manifest; un motore di prova aggiunto con soli file nuovi;
- anteprime in un worker isolato;
- testo incorporato dei PDF usato come produttore distinto;
- rotazioni di 90°, 180° e 270°;
- GIF a fotogramma singolo e BMP.

CI: Ubuntu 716 passati e 7 saltati con motivo; Windows 723 passati. Benchmark con il motore scelto dal registro: punteggi identici a M1. **Aperto:** 1 esecuzione su 4 fallita senza causa nota (seguito in M7).

## M1 — Ordine e verificabilità

M1 è completata: tutti i compiti del piano sono fatti, la revisione indipendente è chiusa e il proprietario ha approvato le decisioni aperte il 2026-11-15.

Criteri di accettazione ed evidenze:
- REQ-001…004: [`evidence/M1/acceptance.md`](evidence/M1/acceptance.md);
- rassegna delle PR: [`evidence/M1/pr-triage.md`](evidence/M1/pr-triage.md);
- tutti i test in CI: [`evidence/M1/2026-11-15-ci.md`](evidence/M1/2026-11-15-ci.md);
- benchmark rigenerabile: [`evidence/M1/2026-11-15-case-benchmark.md`](evidence/M1/2026-11-15-case-benchmark.md);
- revisione: [`evidence/M1/review.md`](evidence/M1/review.md);
- base di partenza: [`evidence/baseline/README.md`](evidence/baseline/README.md).

Il proprietario ha reso obbligatorio anche il controllo «Windows application contracts» nella protezione di `main` (verificato il 2026-11-15: i controlli richiesti sono «Taxonomy registry and binding» e «Windows application contracts»).

Limite registrato per M3: un giustificativo avanzato viene proposto come possibile conflitto alle righe dello stesso giorno.



Risultati principali (dati sintetici): tutti i 55 moduli di test in CI su Ubuntu (672 passati, 6 saltati con motivo) e Windows (678 passati); benchmark del fascicolo rigenerabile da script: 98/98 righe, 92/92 giustificativi giusti al primo posto (tutti come abbinamenti *possibili*), 3/3 conflitti, 40/40 date ambigue con suggerimento corretto, 0 connessioni esterne, 1,1–1,3 s per pagina.

## Fase 0 — Requisiti e piano

Approvata e unita in `main` (#145, 2026-11-15):
- [`requirements.md`](requirements.md): requisiti REQ-001…REQ-143 con criteri di accettazione;
- [`architecture.md`](architecture.md): architettura e punti di estensione;
- [`plan.md`](plan.md): milestone M1–M8 con requisiti, deliverable ed evidenze;
- [`superpowers/plans/2026-11-15-m1-ordine-e-verificabilita.md`](superpowers/plans/2026-11-15-m1-ordine-e-verificabilita.md): piano passo-passo di M1;
- [`dependencies-approved.md`](dependencies-approved.md) (approvate il 2026-11-15) e [`dependencies-request.md`](dependencies-request.md) (R-001 Python embeddable, R-002 NSIS: servono da M6);
- [`decisions.md`](decisions.md) (DEC-001…DEC-020), [`questions.md`](questions.md) (nessuna domanda aperta);
- [`evidence/README.md`](evidence/README.md).

Design approvato dal proprietario il 2026-11-15: [`superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](superpowers/specs/2026-11-15-ocr2-product-completion-design.md).

## Milestone

| Milestone | Stato |
|---|---|
| M1 Ordine e verificabilità | **completata** (2026-11-15) |
| M2 Motori e decodifica | **completata** (2026-11-15, #147) |
| M3 Classificazione ed estrazione | lavoro finito, in attesa dell'ok al merge |
| M4 Revisione | non iniziata |
| M5 Libreria | non iniziata |
| M6 Applicazione installabile | non iniziata |
| M7 Sicurezza e prestazioni | non iniziata |
| M8 Prova sul campo e collaudo | non iniziata |

Il prodotto **non** è completo. Il codice esistente è un prototipo (vedi `requirements.md`, colonna «Stato oggi»).

## Note su V1

Il vecchio progetto OCR non è stato letto per la Fase 0.
