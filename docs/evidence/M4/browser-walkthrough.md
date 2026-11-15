# M4 — percorso sintetico nel browser

Data: 2026-11-15. Ambiente: Chrome, applicazione locale loopback, `application/tools/m4_synthetic_review_server.py`; documento PNG e dati OCR simulati generati dallo script, decoder reale Pillow del lock approvato, nessun archivio o OCR reale.

1. La pagina `Revisione doc-001` mostrava il documento originale, un campo valuta mancante e il campo esercente incerto con due alternative e relative coordinate.
2. Partendo dal corpo pagina, quattro pressioni Tab hanno portato il focus a «X iniziale»; con tastiera sono state inserite le coordinate 0.6, 0.3, 0.9, 0.5 e il valore sintetico EUR. La regione veniva annunciata nella struttura di accessibilità come selezionata.
3. Tab e Invio su «Registra correzione umana» hanno aperto la pagina aggiornata: valuta EUR, stato valido con motivo «corretto in revisione», pagina 1, regione e coordinate corrispondenti; l’esercente restava incerto con due alternative.

Limiti: la prova non ha verificato la selezione con mouse nel browser né l’intero percorso di accessibilità; non sono state salvate schermate in questo giro. I test DOM separati coprono il gesto del puntatore. Il processo di prova era isolato e non usava l’archivio.

## Assistente vocale — BLOCCATO

Avvio richiesto con l’identificatore restituito dall’inventario Windows. Lo strumento ha risposto che l’app avviata non esponeva una finestra controllabile. Non è stato possibile verificare output vocale né completare la checklist. Non è stato effettuato alcun secondo tentativo, secondo GOAL V6. Per sbloccare: una nuova osservazione discriminante o un ambiente/finestra controllabile che renda verificabile l’Assistente vocale senza modificare impostazioni Windows. La sola struttura di accessibilità osservata nel browser non dimostra l’output vocale.

## Assistente vocale — ripresa con riscontro del proprietario

Il proprietario ha avviato Assistente vocale e Windows lo ha mostrato in esecuzione. Con una nuova sessione sintetica nel browser sono stati percorsi con Tab i collegamenti al fascicolo e all’originale, il selettore di pagina e i quattro campi delle coordinate; sono stati inseriti EUR e i valori 0.6, 0.3, 0.9, 0.5, quindi il pulsante di correzione è stato attivato con Invio. La struttura di accessibilità mostrava etichette, messaggio della regione selezionata e, dopo l’invio, valore corretto e coordinate.

Il proprietario, dopo aver ascoltato la prova, ha riferito «Sì, tutto comprensibile» alla domanda se fossero stati letti collegamenti, nomi dei campi, coordinate e messaggio di selezione. L’assistente non dispone di osservazione diretta dell’audio: il riscontro è del proprietario. Questa prova parziale non conclude da sola la checklist di accessibilità completa né sostituisce la prova mouse o gli screenshot.

## Selezione con mouse — sessione sintetica separata

Con una nuova esecuzione del server sintetico è stata aperta la revisione del campo valuta mancante. Il trascinamento del puntatore sulla pagina ha popolato i quattro campi delle coordinate e il messaggio «Regione selezionata nella pagina 1». Dopo l’inserimento di EUR e il pulsante di registrazione, la pagina ha mostrato EUR, stato corretto in revisione e il poligono normalizzato corrispondente al trascinamento (0.182922, 0.370104; 0.229172, 0.420104). La prova verifica il collegamento tra gesto e coordinate salvate, non l’accuratezza semantica del valore trascritto. Non sono stati salvati screenshot.

## Evidenze visive e nuova verifica

Le schermate sono ora salvate: [campo corretto e regione](browser-screen.jpg), [alternative originali dopo correzione](browser-alternatives.jpg), [revisione conclusa](browser-completed.jpg). Le immagini mostrano stati della UI con dati generati e non registrano il movimento del mouse. La prima immagine proviene dalla sessione precedente a d45e11c; le altre due dalla versione contenente i fix. Un revisore indipendente le ha ispezionate, verificandone contenuto sintetico, hash e assenza di marker EXIF/XMP.

Sulla versione con i fix, il browser ha mostrato entrambe le alternative dopo la correzione dell’esercente; un campo valuta inizialmente mancante è stato corretto due volte mantenendo la stessa regione, e la revisione è stata conclusa. In una sessione separata il trascinamento del mouse ha popolato le coordinate e registrato la regione; nella sessione già usata con Assistente vocale il pulsante finale è stato raggiunto con sette Tab e attivato con Invio.
