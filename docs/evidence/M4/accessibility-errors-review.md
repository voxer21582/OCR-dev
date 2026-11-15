# M4 — revisione dei messaggi accessibili

La prova browser del 2026-11-15 ha mostrato che l'errore di formato di un campo personalizzato non indicava lingua o titolo della pagina e che il campo corretto veniva mostrato con un identificatore tecnico. La risposta ora dichiara l'italiano, ha un titolo descrittivo e identifica il campo; il campo revisionato mostra la descrizione dello snapshot. È stato rimosso il modulo generico duplicato per la famiglia, che resta selezionabile tramite il controllo dedicato.

Revisione indipendente senza difetti concreti nel perimetro: 48 test e 8 sottocasi. I test mirati successivi riportano 52 test e 10 sottocasi (`accessibility-errors-green.txt`); suite sintetica completa 835 test e 360 sottocasi (`accessibility-errors-suite.txt`). Queste prove non sostituiscono il riscontro con Assistente vocale sulla versione corrente.

Prova browser sulla versione corretta: aprendo un campo data personalizzato e inserendo un formato errato, l'albero di accessibilità ha mostrato come titolo e intestazione «Formato non valido — Ricevuta taxi — Data corsa», il formato richiesto, il valore inserito e le quattro coordinate conservate. Il riscontro audio resta in attesa del proprietario.
