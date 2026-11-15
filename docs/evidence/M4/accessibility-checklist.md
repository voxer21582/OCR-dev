# M4 — checklist di accessibilità della revisione sintetica

Data: 2026-11-15. Chrome su Windows, pagina di revisione locale, fixture generata da `application/tools/m4_synthetic_review_server.py`, senza documenti reali o OCR reale. Questa è una verifica del percorso di revisione rappresentativo, non una certificazione generale WCAG o di tutte le schermate dell’app.

| Controllo | Esito e prova |
|---|---|
| Navigazione da tastiera | Tab ha raggiunto collegamenti, selettore pagina, coordinate, trascrizione e pulsanti; una correzione è stata registrata con Invio e, nella stessa sessione, «Concludi revisione» è stato raggiunto con Tab e attivato con Invio. |
| Etichette e lettura vocale | Albero accessibilità: etichette di pagina, coordinate, valore e pulsanti presenti; il proprietario, con Assistente vocale attivo, ha riferito che collegamenti, nomi dei campi, coordinate e messaggio della regione erano comprensibili. L’assistente non ha ascoltato direttamente l’audio. |
| Ordine e focus | Nel percorso: collegamenti, selettore pagina, x0, y0, x1, y1, valore, registrazione, campo successivo, registrazione, conclusione. Per i controlli raggiunti Chrome ha riportato `outline: rgb(16, 16, 16) auto 0.8px` sul focus. |
| Contrasto | Stili calcolati nella prova: testo nero su bianco 21:1; link blu `rgb(0,0,238)` su bianco 9.40:1; testo nero su pulsante `rgb(240,240,240)` 18.43:1; contorno selezione `rgb(20,110,180)` su bianco 5.36:1. Il bianco è lo sfondo effettivo nella schermata catturata; si riferisce a questo tema/browser. |
| Mouse e tastiera | Selezione della regione mediante puntatore e inserimento mediante coordinate da tastiera provati su dati sintetici; il poligono è rimasto collegato alla pagina. |
| Schermate | [Regione corretta](browser-screen.jpg), [alternative dopo correzione](browser-alternatives.jpg), [conclusione](browser-completed.jpg). Le immagini sono state ispezionate da un revisore indipendente. |

Limiti: non sono state verificate tutte le combinazioni di zoom, tema o ausili; il riscontro vocale copre il percorso sopra, non ogni possibile stato. Il test non valuta l’accuratezza semantica del testo trascritto.

## Controlli aggiunti successivamente — riscontro vocale

Il 2026-11-15, sulla versione contenente il recupero dei conflitti, è stata ripetuta la prova su ricevuta e dati sintetici. Sono stati percorsi i collegamenti, selezionata e registrata una famiglia personalizzata, scelti stato fiscale ed evidenza, aperto il campo data personalizzato e inserite le quattro coordinate. Un valore non valido ha mostrato titolo, campo e formato richiesto; dopo la correzione del valore, una seconda scheda con modulo obsoleto ha mostrato il conflitto e il collegamento di recupero, raggiunto con Tab.

Alla domanda se famiglia, stato fiscale, coordinate, errore di formato e conflitto con collegamento fossero letti in modo comprensibile, il proprietario ha risposto: «Sì, tutto comprensibile». L'assistente ha osservato la struttura di accessibilità e il focus, non direttamente l'audio. La prova copre i controlli elencati e non tutti gli stati, temi, zoom o ausili.
