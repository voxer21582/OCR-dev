# M7 — Revisione di sicurezza

## Riesame successivo delle modifiche

Un riesame automatico indipendente ha esaminato staticamente il diff fra la base `0a76d415bf28c0e69b52a7539a88fe73ebe20ee7` e il commit `b8baa044be444558f752e7dc93d39009b3978b8f`, concentrandosi su launcher, isolamento delle uscite, server WSGI, navigazione, diagnostica, archivio R7/DPAPI e conteggio JSON. Non ha individuato ulteriori vulnerabilità concrete nei percorsi esaminati. Non ha eseguito personalmente i test o verificato la CI, né svolto un audit umano esterno, un penetration test o una nuova verifica completa di dipendenze e licenze.

Restano i limiti documentati su handle o file nativi non coperti, bootstrap precedente agli import applicativi, navigazione e browser non tutti provati, rete osservata parzialmente e ripristino concorrente tra istanze. Le cache sperimentali non sono nel prodotto. La verifica della latenza resta aperta.

**Approvazione R7 e firma aggiornate:** il 2026-11-18 il proprietario ha dichiarato: «Approvo le modifiche R7 e firmo la revisione di sicurezza aggiornata. Procedi autonomamente con la verifica della latenza e completa la M7.» L'approvazione riguarda il perimetro R7 della PR #153 a `bd77d6231b3e3ce2b8e14ddaa16260aeb50a5e9b`; il codice riesaminato è quello del commit `b8baa044be444558f752e7dc93d39009b3978b8f`, mentre le modifiche successive fino a `bd77d62` riguardano documentazione ed evidenze. La firma non chiude la verifica della latenza.

Un successivo controllo automatico indipendente dei file di evidenza aggiunti fino a `17f3da41fe2d3f699a7d29e79a2227ce89e9ce52` non ha rilevato testo, identificativi o hash di documenti nei nuovi JSON, né incoerenze nei calcoli statistici verificati, compresa la stima prudenziale per i due campioni mancanti. Non ha verificato i log grezzi locali, l'identità degli installer o la raccolta delle misure.

**Modifica R7 successiva alla firma (2026-11-19), non coperta.** La cache per processo delle verifiche della lista dei fascicoli (`_VerifiedReferenceCache` in `local_document_store.py`) cambia il modo in cui la lista verifica i riferimenti: un esito già autenticato con DPAPI viene riutilizzato per byte identici senza nuova decifratura. È una modifica R7 sostanziale dell'autenticazione: la firma e l'approvazione del 2026-11-18 non la coprono. Una revisione automatica indipendente (intervallo `2427a31..3e59a02`) l'ha giudicata «con correzioni», senza rilievi critici; le correzioni sono nel commit `30d42ab`. Resta una scelta che il proprietario deve accettare esplicitamente: la cache ribalta il criterio con cui era stato respinto il prototipo HMAC/snapshot, perché un riscontro in cache salta DPAPI, e una perdita parziale di master key può restare nascosta nella lista per al massimo 480–600 s. Richiede approvazione esplicita del proprietario ai sensi di DEC-001 prima del merge; disegno, limiti e misure in [letture concorrenti](letture-concorrenti.md#cache-per-processo-delle-verifiche-indicizzata-sui-byte-autenticati-proposta-r7-in-attesa-di-approvazione).

**Approvazione del proprietario della cache dei riferimenti (2026-11-19).** Le tre domande sono state poste al proprietario così:

1. Approvazione della nuova modifica R7 (la cache delle verifiche dei riferimenti della lista dei fascicoli in `local_document_store.py`).
2. Accettazione esplicita del ribaltamento del criterio di rifiuto del prototipo HMAC/snapshot: una perdita parziale di master key DPAPI può restare nascosta nella lista per al massimo 480–600 s; la perdita totale resta rilevata subito.
3. Accettazione del metodo di clic tramite Chrome DevTools Protocol come evidenza per REQ-129.

Il proprietario ha risposto nella conversazione del progetto: «si a tutto». La risposta è stata riferita a Claude dal coordinatore della sessione; Claude non l'ha osservata direttamente.

Perimetro: la cache come implementata fino al commit `25bb11e`, cioè `_VerifiedReferenceCache` e il suo uso in `list_cases` e `_validate_case_references_parallel`, con le correzioni `30d42ab` e `25bb11e`. Comprende la scadenza 480–600 s e il mascheramento limitato descritto al punto 2. Non comprende modifiche successive al codice R7, né scadenze o capacità diverse. Una revisione automatica indipendente successiva (intervallo `3e59a02..290b775`) ha giudicato risolti tutti gli 8 rilievi della prima revisione e non ha trovato altri problemi critici o importanti. I rilievi minori residui sono stati corretti in `25bb11e`. REQ-129 non è ancora chiuso: mancano le serie Edge di conferma sulla build corretta, rinviate perché la sessione Windows è bloccata.

## Revisione e firma precedenti

Il proprietario ha firmato la revisione automatica indipendente descritta in questa sezione; tale firma precede il riesame e le modifiche successive. La revisione è statica e automatica: non sostituisce una verifica umana esterna.

Il revisore indipendente ha esaminato il modello delle minacce, il diff M7, la protezione dei registri, la diagnostica, l'archivio R7, il riuso delle funzioni DPAPI, la configurazione OCR e gli strumenti di osservazione. I rilievi su registri, errori del catalogo, letture concorrenti e limiti delle prove sono stati corretti o documentati nei rispettivi file di evidenza. Nel riesame del diff residuo non ha individuato ulteriori difetti concreti; non ha eseguito personalmente i test né osservato direttamente ogni prova installata.

Dopo la firma sotto riportata, una nuova prova ha rilevato un avviso Pillow con il percorso del runtime. La correzione e il riesame indipendente successivo sono descritti in [log-review.md](log-review.md#avviso-pillow-su-tiff-corrotto); la firma precede temporalmente questa modifica.

Anche la proposta successiva di lettura parallela R7 è stata aggiunta dopo la firma e l'approvazione R7 precedenti riportate sotto. Il riesame automatico indipendente non ha rilevato nuove regressioni concrete nel diff proposto, ma segnala duplicazione dei controlli e limiti su memoria e attesa dei worker. Il proprietario ha successivamente approvato il perimetro R7 attuale come riportato sopra; le verifiche prestazionali restano aperte. [Dettagli e misure](letture-concorrenti.md#verifica-della-modifica-proposta).

Le prove sono locali e usano esclusivamente dati sintetici. La suite applicativa ha riportato 1167 test superati, 2 saltati e 403 sottotest superati. La rete è stata osservata con hook Python e campioni TCP su una copia strumentata: non sono stati osservati eventi non loopback nei metodi coperti, ma chiamate native, processi transitori e connessioni brevi possono sfuggire. Le prove sui log non coprono ogni possibile uscita di librerie native o altri processi. I registri precedenti `launcher.log` e `launcher.log.1` restano conservati per scelta del proprietario e possono contenere dati sensibili.

La lista dei fascicoli sulla versione installata ha raggiunto p95 HTTP di 161,72 e 150,74 ms nelle due prove sintetiche; queste misure non includono il rendering e riguardano un solo PC. Il ripristino concorrente fra istanze o processi che usano lo stesso archivio rimane un limite preesistente. In due avvii strumentati il primo heartbeat della pagina è arrivato dopo 3,315 e 2,992 secondi; il segnale non dimostra che la finestra fosse visivamente pronta e utilizzabile, misura che rimane incompleta.

La PR tocca **R7 (archivio e ripristino)**. Il proprietario ha approvato esplicitamente queste modifiche per la PR #153 ai sensi di DEC-001, separatamente dalla firma della revisione ai sensi di DEC-008. Ha inoltre accettato il limite della prova visiva di avvio.

**Firma/approvazione del proprietario:** dichiarazione esplicita nella conversazione del progetto: «Approvo le modifiche R7, firmo la revisione di sicurezza e accetto il limite della prova visiva di avvio. Procedi con la chiusura della M7.»
**Data:** 2026-11-18.
