# M8 — Preparazione della prova e del collaudo

Obiettivo: preparare la valutazione locale su 30–50 documenti reali e il collaudo Windows, senza raccogliere documenti o risultati individuali nel repository. Prima dell'esecuzione il proprietario deve approvare protocollo, soglie e foglio delle risposte (REQ-140). La preparazione non è approvazione né prova reale.

Scelte: due file JSON locali esterni al repository, uno con risposte verificate e uno con i primi valori proposti dall'app, collegati tramite codici casuali locali; lo script restituisce soltanto array numerici aggregati in ordine fisso. I valori, gli identificativi e i percorsi non sono stampati, neppure negli errori. Non si esportano file reali verso repository o servizi esterni. La riconciliazione usa codici di riga e documento definiti nel foglio locale, senza lo scorer sintetico che cerca etichette testuali. I risultati non vengono corretti o sostituiti dopo la lettura delle soglie.

Criteri: test sintetici verificano confronto, denominatori, campioni mancanti, duplicati, valori sensibili e output numerico. Proporre soglie, protocollo e checklist; non eseguire la prova reale prima dell'approvazione del proprietario. Una sola ripetizione su campione nuovo dopo eventuale correzione (DEC-006).

Verifica preliminare su dati esclusivamente sintetici: `python -B -m pytest tests/test_field_trial_score.py tests/test_field_benchmark.py tests/test_case_benchmark_score.py -q -p no:cacheprovider` da `application/`, **32 test passati**. Nessuna prova su dati reali. La trascrizione dei risultati nel foglio locale non è autenticata dallo script e deve essere verificata separatamente.

I fogli CSV locali possono essere controllati senza creare copie usando [istruzioni-foglio-locale.md](istruzioni-foglio-locale.md); la selezione e le risposte devono ancora essere approvate.

La revisione automatica indipendente dell’adattatore CSV ha verificato che non scrive copie del foglio e ha segnalato che non controlla esistenza, località o identità fisica dei documenti; questi controlli rimangono manuali. Verifica sintetica aggiornata dei test M8, benchmark e workflow: **38 passati**.

È stata aggiunta una [preparazione sintetica del legame tra fogli e byte](integrita-campione-preparazione.md); non sostituisce il congelamento operativo, la protezione privata né l’approvazione del campione. Test mirati aggiornati: **55 passati**.
