# M7 — Esportazione diagnostica

La pagina Informazioni offre, su richiesta dell'utente, il download `ocr2-diagnostica.json`. Il file contiene soltanto un identificativo fisso del formato, le versioni applicativa e Python se conformi al formato numerico ammesso, lo stato di configurazione OCR e l'esito del confronto con il manifest locale. Valori non riconosciuti sono `unknown`.

Il generatore non consulta l'archivio o i registri e non esporta percorsi, identificativi di sessione, nomi, documenti, contenuti, hash di documenti o messaggi d'errore. I test usano marcatori sintetici in campi non attendibili e verificano che non compaiano nell'output, oltre al download, al tipo, alle intestazioni e ai metodi ammessi. La risposta non viene conservata in cache.

Il riesame automatico indipendente non ha individuato una fuga concreta nel percorso esaminato. Lo stato OCR descrive la configurazione e non dimostra che il riconoscimento funzioni; lo stato runtime riguarda il confronto con il manifest presente e non ne autentica la provenienza. Il download non è una raccolta di log né una diagnosi degli errori nativi.

Sulla versione di prova installata 0.6.1, un controllo HTTP locale ha verificato il collegamento dalla pagina Informazioni, la risposta 200 e i soli cinque campi previsti. Nel server avviato senza `app_info`, OCR e runtime risultano correttamente `unknown` anziché essere dedotti. La prova non sostituisce un controllo visivo della finestra.

Una prova visiva successiva ha avviato un server sintetico con l'interprete Python 3.13.18 e i moduli della build `OCR2_TEST` installata, senza passare dal launcher di rilascio e senza configurare `app_info`. Nel browser integrato la pagina Informazioni mostrava il collegamento «Scarica diagnostica», la descrizione dei dati e i limiti degli stati OCR e runtime; il comando Esci ha arrestato il server. Il browser e il server di prova non verificano la finestra Edge di rilascio, né il download è stato ripetuto in questa osservazione visiva.
