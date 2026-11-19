# M8 — Protocollo di prova sul campo (proposta, da approvare)

**Stato: BOZZA, non autorizza l'esecuzione.** REQ-140 richiede l'approvazione del proprietario di protocollo, soglie e foglio delle risposte prima della prova. I risultati M3 sono sintetici e non stimano l'accuratezza su documenti reali.

## Campione e riservatezza

Selezionare prima della prova 30–50 documenti reali pertinenti, comprendenti nota/e spese e giustificativi; definire prima la composizione e includere italiano e inglese. Proposta: almeno 5 documenti valutabili per ciascuna lingua e almeno 10 righe con giustificativo corretto univoco. Se non disponibili, la copertura interessata è **non valutabile**, non superata. Segnalare formati, rotazioni e qualità delle scansioni in termini aggregati. Evitare di scegliere i documenti dopo aver visto il risultato OCR.

Il costruttore opera localmente sul PC del proprietario. Documenti, esportazioni, valori individuali, corrispondenze tra codici e identità e foglio compilato restano fuori dal repository e dai servizi esterni, in una cartella privata scelta dal proprietario. Nel repository solo aggregati numerici e la firma, senza testo, nomi, identificativi o percorsi. Non incollare file reali in chat.

## Prima di eseguire

1. Congelare versione dell'app, selezione e criteri; compilare **indipendentemente e prima dell'OCR** il foglio delle risposte, con codici casuali e senza dati personali nei codici. Il proprietario approva il protocollo, le soglie e il foglio compilato localmente. Non inviare il foglio a GitHub.
2. Per ogni documento annotare lingua e valori di riferimento effettivamente presenti e leggibili: importo totale, data, valuta, numero documento, partita IVA e esercente. I campi assenti o illeggibili sono registrati separatamente nel foglio locale e non inventati; escluderli dal denominatore e riportarne il conteggio aggregato. Applicare le stesse regole a tutti i documenti prima di vedere l'OCR.
3. Per ogni riga della nota con corrispondenza univoca annotare il codice della riga e il codice del giustificativo corretto; le righe senza riscontro o ambigue sono inventariate a parte e non contate come corrispondenze univoche. Non modificare i valori del foglio dopo la prova.
4. Registrare in forma aggregata numero di documenti e denominatori per lingua/campo; annotare localmente eventuali esclusioni e il motivo, senza pubblicare valori individuali.

## Esecuzione e punteggio

Elaborare il campione nell'app locale senza modificare manualmente i suggerimenti prima della misurazione. Trascrivere in un secondo file locale i primi valori proposti e, per ogni riga valutabile, il codice del primo giustificativo suggerito. Un risultato mancante o diverso è errato; non scegliere un'alternativa successiva perché corrisponde alla risposta. Un candidato osservato usa il suo valore; uno incerto usa la prima alternativa; assente, illeggibile o rifiutato conta come mancato. Valori di importo, data e valuta devono usare lo stesso formato canonico fissato nel foglio prima della prova; non normalizzare valori dopo avere osservato il risultato.

Lo script `application/tools/field_trial_score.py` confronta soltanto i due fogli locali preparati. Non legge l'archivio né l'export direttamente: la trascrizione manuale dei risultati richiede controllo indipendente locale; questa limitazione deve essere accettata o eliminata prima dell'uso. Lo script non verifica autenticità della trascrizione, eleggibilità dei campi, composizione o minimi del campione. Su input invalido esce con errore numerico, senza stampare contenuti. I numeri vanno confrontati manualmente con le soglie approvate; un denominatore zero è **non valutabile**.

### Soglie proposte Q-002 — da approvare prima della prova

| Metrica | Soglia proposta |
|---|---:|
| Totale, data e valuta: primo valore esatto | ciascuno ≥ 95% |
| Numero documento e partita IVA: primo valore esatto | ciascuno ≥ 90% |
| Esercente: primo valore esatto | ≥ 80% |
| Giustificativo corretto al primo posto, tra righe univoche | ≥ 90% |
| Copertura italiana e inglese | risultato separato per lingua; almeno 5 documenti valutabili per lingua |

Le percentuali usano come denominatore tutti i casi valutabili predefiniti, compresi quelli con risultato mancante. Le soglie dei campi riprendono quelle M3; la soglia di riconciliazione e i minimi di copertura sono proposte, non risultati verificati su documenti reali. Per ogni campo richiesto un denominatore nullo rende il relativo criterio non valutabile; non promuovere la prova complessiva se una metrica obbligatoria non è valutabile o è sotto soglia.

Se una soglia non è raggiunta, registrare il risultato, correggere e fare **al massimo una ripetizione su un campione nuovo**; ridurre una soglia richiede firma del proprietario (DEC-006). Dopo la ripetizione decide il proprietario. Registrare solo i numeri riepilogativi e il giudizio, con i limiti del campione.

## Formato locale dei due fogli JSON

Entrambi hanno `documents`; ciascuna voce ha un `id` locale univoco. Il riferimento aggiunge `language` (`it`/`en`) e `expected` con i campi valutabili; i risultati aggiungono `fields` con candidati `status`, `value` o prima `alternatives`. Il riferimento può avere `matches` come elenco di `{id, target}`: `id` è il codice riga, `target` il codice documento presente nel riferimento. I risultati possono riportare le stesse righe con il primo `target` proposto. Righe senza risultato restano nel denominatore; righe inattese e ID duplicati sono rifiutati.

Da `application/`: `python -B -m tools.field_trial_score PERCORSO_RIFERIMENTO PERCORSO_RISULTATI`. Il programma stampa un array di 42 interi: posizione 0 documenti, 1 risultati documentali mancanti; poi coppie `corretti, valutabili` per i sei campi nell'ordine totale, data, valuta, numero, partita IVA, esercente, prima su tutto il campione, poi italiano, poi inglese (posizioni 2–37); posizioni 38–39: documenti distinti con almeno un campo valutabile in italiano e inglese; ultime due posizioni 40–41: corrispondenze corrette e valutabili. L'array non contiene percentuali; calcolarle dividendo corretti per valutabili solo quando il denominatore è positivo. I nomi e i percorsi non sono stampati.
