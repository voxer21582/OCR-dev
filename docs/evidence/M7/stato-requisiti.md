# M7 — Stato delle verifiche

Stato: **in corso**, non è un'accettazione della milestone. Le prove sono locali, su un PC Windows e documenti sintetici.

| Requisito | Evidenza disponibile | Lavoro residuo |
|---|---|---|
| REQ-108 | Download diagnostico volontario con campi tecnici limitati, test sintetici, revisione indipendente e controllo HTTP sulla versione installata. | Controllo visivo della finestra. [Dettagli](diagnostica.md). |
| REQ-121 | Fascicolo completo sulla copia strumentata aggiornata; hook Python e 82 campioni TCP, 7 PID coincidenti, zero eventi non loopback osservati. | Copertura nativa e prodotto originale non completamente osservabili; nessuna garanzia assoluta. [Metodo e limiti](benchmark-installato.md). |
| REQ-124 | Protezioni e test dei percorsi individuati; su copia installata strumentata, marcatori stdout/stderr raccolti da sette processi durante 104 pagine sintetiche. | Completare la revisione degli errori e delle uscite native non coperte; i registri storici sono conservati su scelta del proprietario. [Verifica](log-review.md). |
| REQ-125 | Modello delle minacce e revisione automatica indipendente dei cambiamenti, firmata dal proprietario il 2026-11-18. | Limiti della revisione documentati nella [revisione](revisione-sicurezza.md). [Modello](modello-minacce.md). |
| REQ-127 | Sull'ultima versione installata, 104 intervalli di avanzamento pagina osservati: mediana 1,255 s, massimo 16,522 s; polling ogni 0,2 s circa. | Validare metodo e rappresentatività; gli intervalli sono stime, non tempi interni esatti. |
| REQ-128 | 104 pagine in 158,8 s, avanzamento visibile; annullamento e ripresa su 31 documenti; dopo terminazione del server, recupero di 20 documenti già salvati e completamento di 36/36. | La terminazione del processo non simula perdita di alimentazione o riavvio del PC. |
| REQ-129 | 728,6 MiB massimo campionato nei processi figli; due prove installate hanno misurato p95 lista 161,72 e 150,74 ms, con 279 e 283 risposte 200. | La misura HTTP non include il rendering del browser e la memoria è campionata; un PC e un set sintetico. [Diagnosi](letture-concorrenti.md). |
| REQ-130 | PDF sintetico di 100 pagine elaborato in 116,6 s; due primi heartbeat della pagina a 3,315 e 2,992 s su copia strumentata. | Il proprietario ha accettato il limite della prova visiva il 2026-11-18. Il heartbeat non dimostra che la finestra fosse visivamente pronta o usabile; prova PDF rappresentativa di un solo file leggero. |

I numeri e i limiti delle misure sono in [benchmark-installato.md](benchmark-installato.md). Le misure non rappresentano prestazioni o accuratezza su documenti reali.
