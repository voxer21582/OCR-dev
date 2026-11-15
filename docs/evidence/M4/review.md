# M4 — audit indipendente dei criteri

Audit del 2026-11-15: il revisore indipendente ha confrontato piano, requisiti, audit delle PR, codice e prove disponibili e ha eseguito 52 test di registro, export, presentazione, controllo dati e CI, tutti passati. La suite completa più recente sul codice `3ff4e28` riporta 835 test e 365 sottocasi (`conflict-recovery-suite.txt`). Dopo il riscontro vocale del proprietario il revisore ha confermato che le lacune specifiche individuate sono coperte nei limiti del percorso e dell'ambiente descritti.

| Criterio | Evidenza e stato |
|---|---|
| REQ-070 — pagina, area, alternative, incertezza e motivi | Percorso e schermate sintetiche in `browser-walkthrough.md`; prova successiva di famiglia e campo personalizzato descritta sotto. Da riesaminare sul risultato finale. |
| REQ-072 — autore Windows, UTC, export JSON e CSV | `test_review_identity.py`, `test_document_export.py` e suite completa; il revisore ha ripetuto i test di registro ed export. |
| REQ-073 — regione manuale con mouse e tastiera | `browser-walkthrough.md` e `missing-fields-review.md`: percorsi sintetici con puntatore e tastiera. Prove WSGI e regione in `missing-fields-green.txt`. |
| REQ-075 — accessibilità e Assistente vocale | Checklist in `accessibility-checklist.md`: percorso iniziale e nuova prova sui controlli aggiunti; il proprietario riferisce lettura comprensibile di famiglia, stato fiscale, coordinate, errore e conflitto. Riscontro audio indiretto e per il percorso descritto. |

## Prova aggiuntiva sulla versione attuale

Con browser locale e PNG sintetico, nella ricevuta è stata selezionata da tastiera la famiglia personalizzata «Ricevuta taxi»; la pagina ha mostrato famiglia e prova. Un campo personalizzato è stato aperto, compilato con coordinate e data errata: la risposta ha mostrato il formato richiesto e mantenuto valore e coordinate. Una data valida è stata quindi registrata con la regione. La classificazione fiscale e la relativa evidenza sono state selezionate da tastiera; la cronologia ha mostrato gli eventi. Queste osservazioni non attestano l'output audio dell'Assistente vocale e non coprono tutti i possibili stati o dispositivi.

L'audit ha inoltre segnalato che nella storia Git locale è presente un percorso di profilo in un vecchio commit: la pulizia del file corrente non elimina quel dato dalla storia. Nessuna pubblicazione del ramo è implicita in questo audit.

La chiusura richiede ancora evidenze CI Ubuntu e Windows sul risultato finale e approvazione esplicita del proprietario sulla PR che tocca R8, come previsto dal piano e da DEC-001.
