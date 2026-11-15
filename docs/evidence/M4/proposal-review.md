# M4 — proposta per revisione

La proposta realizza la revisione dei documenti con provenienza, correzioni e alternative, storia degli eventi con autore e data UTC, esportazione della cronologia, selezione manuale della regione e controlli di accessibilità. Le prove sintetiche, il percorso browser e il riscontro del proprietario con Assistente vocale sono raccolti nella cartella `docs/evidence/M4/`; la revisione indipendente è in `review.md`.

Il lavoro tocca R8: modifica la proiezione CSV della cronologia e gli export della riconciliazione. Secondo DEC-001 la PR deve dichiararlo e ottenere approvazione esplicita del proprietario prima del merge. La milestone richiede inoltre CI riuscita su Ubuntu e Windows, non ancora eseguita sulla proposta.

Per evitare di pubblicare un percorso personale presente nella storia del ramo precedente, il contenuto è stato ricostruito in un nuovo worktree a partire da `origin/main`, senza modificare quel ramo. Prima delle aggiunte documentali di questa proposta, l'albero preparato coincideva con il risultato revisionato; ricerca del percorso del profilo nel contenuto preparato e `test_public_data_guard` non hanno rilevato esposizioni. La verifica non equivale a una garanzia generale di assenza di dati sensibili. La suite sintetica eseguita sul worktree preparato è `proposal-windows-suite.txt` (835 test e 365 sottocasi).
