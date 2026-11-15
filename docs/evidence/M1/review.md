# M1 — Revisione indipendente (2026-11-15)

**Revisore:** agente di revisione senza il contesto del lavoro (modello Opus), sul diff completo `3d5ac61..f8d19ee` (9 commit). Ha ricevuto il piano, il design, GOAL.md e le decisioni del costruttore.

**Verifiche fatte dal revisore:**
- ha eseguito 31 test (punteggio, guardia, workflow, fixture, lock);
- ha generato le fixture due volte in processi separati e ha ottenuto la stessa impronta `6bcdb274…ed99`.

**Esito:** nessun problema critico; pronto «con correzioni».

## Problemi importanti, tutti corretti nel commit `7dfd36f`

| # | Problema | Correzione | Test (prima rosso, poi verde) |
|---|---|---|---|
| 1 | Il punteggio contava un abbinamento «possibile» come confermato e accettava un primo suggerimento con motivi di conflitto | Abbinamenti solo possibili riportati a parte (risultato: 92 su 92 sono possibili); i motivi di conflitto escludono l'abbinamento | `test_possible_matches_are_counted_apart_and_conflicting_firsts_are_not_matches` |
| 2 | Un conflitto risultava segnalato anche se veniva da un altro giustificativo | Il conflitto deve stare sul suggerimento del giustificativo atteso | `test_conflict_counts_only_on_the_expected_receipts_own_suggestion` |
| 3 | La guardia delle evidenze non riconosceva i percorsi del profilo utente in stile Git Bash e POSIX | Pattern estesi | `test_rejects_posix_style_user_paths` |
| 4 | Il README indicava Python 3.13.18 per il job Windows (è 3.13.17) | Corretto | — (documento) |

## Problemi minori

**Corretti**, perché per chi legge sono affermazioni false:
- frasi del README rimaste vecchie («solo alcuni moduli in CI», opzioni del launcher);
- commit non indicato nell'evidenza del benchmark;
- conteggi locali da riconciliare.

**Rinviati**:
- `test_ci_workflow` cerca i nomi dei moduli in tutto il blocco del job, non solo negli argomenti, e non controlla i moduli di tassonomia;
- lo script del benchmark, su errori imprevisti, stampa una traceback e non cancella la cartella temporanea (che contiene solo dati sintetici);
- il salto su Linux del test sulla scadenza del worker potrebbe nascondere un difetto solo Linux; il prodotto è solo per Windows;
- il punteggio non controlla che un giustificativo abbinato non compaia anche tra i non usati; l'app li rende disgiunti per costruzione.

**Il revisore ha lasciato al proprietario:**
- la presenza di colorama nel lock CI di Windows (gruppo 1 approvato);
- se rendere obbligatorio il job Windows;
- le classificazioni della rassegna delle PR.

**Dopo le correzioni:** 680 passati, 1 saltato in locale, sul commit `7dfd36f`.
