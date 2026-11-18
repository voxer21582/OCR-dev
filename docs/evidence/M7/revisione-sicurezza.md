# M7 — Revisione di sicurezza

## Riesame successivo delle modifiche

Un riesame automatico indipendente ha esaminato staticamente il diff fra la base `0a76d415bf28c0e69b52a7539a88fe73ebe20ee7` e il commit `b8baa044be444558f752e7dc93d39009b3978b8f`, concentrandosi su launcher, isolamento delle uscite, server WSGI, navigazione, diagnostica, archivio R7/DPAPI e conteggio JSON. Non ha individuato ulteriori vulnerabilità concrete nei percorsi esaminati. Non ha eseguito personalmente i test o verificato la CI, né svolto un audit umano esterno, un penetration test o una nuova verifica completa di dipendenze e licenze.

Restano i limiti documentati su handle o file nativi non coperti, bootstrap precedente agli import applicativi, navigazione e browser non tutti provati, rete osservata parzialmente e ripristino concorrente tra istanze. Le cache sperimentali non sono nel prodotto. La firma e l'approvazione R7 riportate sotto precedono una parte del diff riesaminato; non costituiscono approvazione delle modifiche successive. La verifica della latenza resta aperta.

## Revisione e firma precedenti

Il proprietario ha firmato la revisione automatica indipendente descritta in questa sezione; tale firma precede il riesame e le modifiche successive. La revisione è statica e automatica: non sostituisce una verifica umana esterna.

Il revisore indipendente ha esaminato il modello delle minacce, il diff M7, la protezione dei registri, la diagnostica, l'archivio R7, il riuso delle funzioni DPAPI, la configurazione OCR e gli strumenti di osservazione. I rilievi su registri, errori del catalogo, letture concorrenti e limiti delle prove sono stati corretti o documentati nei rispettivi file di evidenza. Nel riesame del diff residuo non ha individuato ulteriori difetti concreti; non ha eseguito personalmente i test né osservato direttamente ogni prova installata.

Dopo la firma sotto riportata, una nuova prova ha rilevato un avviso Pillow con il percorso del runtime. La correzione e il riesame indipendente successivo sono descritti in [log-review.md](log-review.md#avviso-pillow-su-tiff-corrotto); la firma precede temporalmente questa modifica.

Anche la proposta successiva di lettura parallela R7 è stata aggiunta dopo la firma e l'approvazione R7 riportate sotto. Il riesame automatico indipendente non ha rilevato nuove regressioni concrete nel diff proposto, ma segnala duplicazione dei controlli e limiti su memoria e attesa dei worker. La nuova modifica richiede valutazione e approvazione esplicita del proprietario prima del merge; le verifiche prestazionali restano aperte. [Dettagli e misure](letture-concorrenti.md#verifica-della-modifica-proposta).

Le prove sono locali e usano esclusivamente dati sintetici. La suite applicativa ha riportato 1167 test superati, 2 saltati e 403 sottotest superati. La rete è stata osservata con hook Python e campioni TCP su una copia strumentata: non sono stati osservati eventi non loopback nei metodi coperti, ma chiamate native, processi transitori e connessioni brevi possono sfuggire. Le prove sui log non coprono ogni possibile uscita di librerie native o altri processi. I registri precedenti `launcher.log` e `launcher.log.1` restano conservati per scelta del proprietario e possono contenere dati sensibili.

La lista dei fascicoli sulla versione installata ha raggiunto p95 HTTP di 161,72 e 150,74 ms nelle due prove sintetiche; queste misure non includono il rendering e riguardano un solo PC. Il ripristino concorrente fra istanze o processi che usano lo stesso archivio rimane un limite preesistente. In due avvii strumentati il primo heartbeat della pagina è arrivato dopo 3,315 e 2,992 secondi; il segnale non dimostra che la finestra fosse visivamente pronta e utilizzabile, misura che rimane incompleta.

La PR tocca **R7 (archivio e ripristino)**. Il proprietario ha approvato esplicitamente queste modifiche per la PR #153 ai sensi di DEC-001, separatamente dalla firma della revisione ai sensi di DEC-008. Ha inoltre accettato il limite della prova visiva di avvio.

**Firma/approvazione del proprietario:** dichiarazione esplicita nella conversazione del progetto: «Approvo le modifiche R7, firmo la revisione di sicurezza e accetto il limite della prova visiva di avvio. Procedi con la chiusura della M7.»
**Data:** 2026-11-18.
