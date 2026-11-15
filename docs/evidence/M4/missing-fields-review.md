# M4 — campi mancanti e revisione indipendente

Il 2026-11-15 sono stati verificati campi standard non proposti e campi definiti negli snapshot del documento, senza modificare l'estrazione originaria. Un'anteprima prodotta nella sessione per documento, hash e pagina è richiesta prima di registrare una regione. Il controllo prova la produzione dell'immagine dal server, non la sua effettiva lettura da parte della persona; l'elenco è volatile e limitato a 128 pagine.

Il revisore indipendente ha rilevato la perdita del valore digitato in una correzione custom senza regione con tipo errato; il caso è stato riprodotto, corretto e riesaminato senza ulteriori difetti concreti. Il revisore ha eseguito 96 test e 30 sottocasi su revisione, tastiera, ledger, CSRF, catalogo e contratti. Le prove mirate e la suite completa sono rispettivamente in `missing-fields-green.txt` e `missing-fields-suite.txt`.

Prova browser locale con `application/tools/m4_synthetic_review_server.py`: aperto «Numero documento», inserite coordinate normalizzate e valore sintetico, registrata la correzione; pagina e cronologia mostrano il valore e la regione umana. La prova usa un PNG sintetico e non dimostra l'intero percorso custom nel browser; il percorso custom, inclusi formato non valido, ripristino e successivo invio, è coperto dai test WSGI. Nessun documento reale utilizzato.
