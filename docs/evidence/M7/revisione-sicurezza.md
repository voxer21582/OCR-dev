# M7 — Revisione di sicurezza

Stato: **revisione automatica indipendente eseguita; firma del proprietario non ancora acquisita**. Questa pagina non attesta il completamento della milestone. La revisione è statica e automatica: non sostituisce una verifica umana esterna.

Il revisore indipendente ha esaminato il modello delle minacce, il diff M7, la protezione dei registri, la diagnostica, l'archivio R7, il riuso delle funzioni DPAPI, la configurazione OCR e gli strumenti di osservazione. I rilievi su registri, errori del catalogo, letture concorrenti e limiti delle prove sono stati corretti o documentati nei rispettivi file di evidenza. Nel riesame del diff residuo non ha individuato ulteriori difetti concreti; non ha eseguito personalmente i test né osservato direttamente ogni prova installata.

Le prove sono locali e usano esclusivamente dati sintetici. La suite applicativa ha riportato 1167 test superati, 2 saltati e 403 sottotest superati. La rete è stata osservata con hook Python e campioni TCP su una copia strumentata: non sono stati osservati eventi non loopback nei metodi coperti, ma chiamate native, processi transitori e connessioni brevi possono sfuggire. Le prove sui log non coprono ogni possibile uscita di librerie native o altri processi. I registri precedenti `launcher.log` e `launcher.log.1` restano conservati per scelta del proprietario e possono contenere dati sensibili.

La lista dei fascicoli sulla versione installata ha raggiunto p95 HTTP di 161,72 e 150,74 ms nelle due prove sintetiche; queste misure non includono il rendering e riguardano un solo PC. Il ripristino concorrente fra istanze o processi che usano lo stesso archivio rimane un limite preesistente. La misura fino alla finestra usabile non è stata completata.

La PR tocca **R7 (archivio e ripristino)**: DEC-001 richiede l'approvazione esplicita del proprietario prima del merge. La firma sulla revisione richiesta da DEC-008 è separata dall'approvazione R7 e non è implicita nel fatto che la PR sia in bozza.

**Firma/approvazione del proprietario:** non acquisita.
**Data:** non acquisita.
