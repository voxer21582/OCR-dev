# Protocollo proposto per la baseline locale e il pilot OCR

**Stato:** proposta per revisione del proprietario. Nessun campione è stato selezionato o aperto e nessun pilot è autorizzato da questo documento.

**Blocco R7/R8:** finché restano attivi stop/no-retry e i gate non sono formalmente rimossi, non eseguire prove su archivio persistente, riapertura, ripristino, esportazione, cancellazione, backup o lifecycle. Anche le verifiche sintetiche di input/limiti devono restare fuori da componenti o selector che importano o esercitano il local store. Questa proposta non rimuove i blocchi e non autorizza tali prove.

## Scopo

Misurare se l'applicazione OCR2 estrae correttamente i dati dai giustificativi e consente di riconciliare ogni risultato con la corrispondente riga della nota spese definitiva. Il risultato serve a decidere se procedere con un pilot controllato; non equivale all'accettazione del prodotto.

## Decisioni e vincoli già registrati

| Tema | Decisione verificata | Limite |
| --- | --- | --- |
| Documenti | Si usano documenti reali delle note spese dell'utente, non fixture sintetiche per la valutazione OCR locale. | Nessun documento reale, testo OCR o valore derivato va in GitHub, CI, chat o servizi esterni. La CI resta sintetica. |
| Fonte di confronto | Per ogni trasferta, mese e anno esiste una nota PDF definitiva; il nome contiene normalmente “DEFINITIVO”. | Il PDF va scelto e verificato dall'utente; l'OCR non può creare né correggere l'etichetta di riferimento. |
| Elaborazione | Solo locale sul PC Windows 11 dell'utente; lingua italiana e inglese; input PDF, PNG e JPEG. | RapidOCR è la direzione runtime della issue #9, ma il runtime non è accettato per la produzione. A4/PaddleOCR è separato. |
| Dimensione desiderata | L'utente ha proposto lotti di circa 100 giustificativi. | Non è ancora dimostrato che l'applicazione e i limiti correnti possano gestire 100 file in modo affidabile. |
| Conservazione | Conservare fino alla cancellazione esplicita dell'utente. | Prima del pilot va verificato che la cancellazione copra copie importate, database, anteprime, risultati, esportazioni e backup controllabili. |
| Costi e rete | Nessun nuovo costo; nessun servizio OCR remoto. | Nessun download o installazione aggiuntiva è autorizzato da questo protocollo. |

## Approcci considerati

1. **Confrontare ogni giustificativo con la nota definitiva corrispondente — raccomandato.** Usa la nota finale già adottata come riferimento esterno al motore OCR. Richiede che l'utente confermi l'associazione tra giustificativo e riga, ma non introduce un secondo formato di rendicontazione.
2. **Creare un foglio di verità separato.** Permette etichette più dettagliate, ma duplica valori e crea un ulteriore artefatto sensibile da mantenere e cancellare.
3. **Usare l'output OCR come riferimento.** Non è indipendente e falserebbe la misura; escluso.

La proposta usa l'approccio 1, già coerente con la descrizione dell'utente. Gli identificativi di campione e le etichette rimangono in un registro locale non versionato.

## Procedura proposta

### 1. Selezione e congelamento del campione

- L'utente seleziona una trasferta o un periodo e il relativo PDF definitivo. Non si sceglie automaticamente una cartella o un anno.
- Per il primo lotto, puntare a un massimo di 100 giustificativi solo se i limiti applicativi già verificati lo consentono; altrimenti fermarsi e concordare un lotto più piccolo. Il limite di 100 è un obiettivo da verificare, non una capacità dichiarata.
- Prima di accettare file, verificare la validazione dei percorsi selezionati e limiti effettivi su dimensione, pagine, tempo, memoria, spazio temporaneo e decodifica/espansione delle immagini. File malformati, ostili o fuori limite devono essere rifiutati senza eseguire contenuti incorporati. Eventuali controlli sintetici devono usare componenti indipendenti dai gate R7/R8 e da moduli che importano il local store; se non è possibile dimostrarne la separazione, fermarsi senza eseguirli. La proposta non autorizza nuove prove.
- Prima dell'elaborazione creare un identificativo casuale locale per ciascun documento e un manifesto locale con hash SHA-256, dimensione, formato e numero di pagine. Non registrare nomi file, percorsi, hash, valori o testo OCR nel repository o in GitHub.
- Congelare il campione e le etichette prima del confronto. Non usarli per correggere il sistema e poi dichiarare valido lo stesso risultato.
- Ogni campo osservato, alternativa e correzione manuale deve mantenere hash SHA-256 del documento sorgente e prova della pagina/area. Una correzione conserva separatamente l'osservazione OCR originale e la motivazione umana; se l'app non può farlo, il caso non è accettabile per la misura.

### 2. Etichette indipendenti

- L'utente legge la nota definitiva e verifica manualmente l'associazione fra ogni giustificativo e la riga di spesa corrispondente.
- I valori di riferimento derivano dalla nota definitiva, mai dall'output OCR. Registrare localmente la provenienza della riga e le ambiguità.
- Prima del pilot formale, il proprietario decide se richiedere una seconda verifica umana indipendente per tutte le etichette o almeno per gli importi e le associazioni ambigue. In caso di disaccordo, escludere il caso dal denominatore fino a risoluzione documentata.
- Se la nota definitiva non consente una corrispondenza univoca, marcare il caso “riferimento ambiguo”; non forzare una corrispondenza.

### 3. Esecuzione e revisione locale

- Eseguire l'elaborazione soltanto dopo approvazione esplicita del campione e del piano per il pilot. Verificare che il flusso non faccia richieste remote; se l'uso di rete è necessario o incerto, fermarsi per revisione senza modificare le impostazioni di Windows.
- Non attivare invii automatici, API remote, telemetria, caricamenti o sincronizzazione. Mostrare un avviso per risultati mancanti, incerti o non associabili.
- Un revisore umano confronta i campi estratti con la nota definitiva, corregge l'etichetta solo sulla base della fonte e registra la motivazione localmente.
- Separare gli errori di riconoscimento, classificazione, estrazione, associazione alla riga e riferimento ambiguo; riportare anche file/pagine non elaborabili e risultati lasciati incerti.

### 4. Misure

Riportare localmente numeratore, denominatore ed esclusioni per lotto e formato:

- quota di documenti e pagine elaborati senza errore;
- corrispondenza esatta dei singoli campi rispetto alle etichette indipendenti, per ciascun campo effettivamente supportato;
- percentuale dei campi e delle correzioni che mantengono hash sorgente e prova di pagina/area verificabili;
- correttezza dell'associazione giustificativo-riga della nota definitiva;
- valori mancanti, alternative, incertezze e correzioni manuali;
- errori per categoria e motivo di esclusione.

Non usare un'unica percentuale aggregata per nascondere errori sugli importi. Non calcolare CER/WER senza una trascrizione di riferimento indipendente. Queste metriche non sostituiscono l'accettazione di sicurezza, lifecycle o installazione.

### 5. Soglie e separazione baseline/accettazione

- Il primo lotto può produrre una **baseline esplorativa**, non una dichiarazione di accettazione.
- Dopo aver visto la baseline, il proprietario approva le soglie per campo, i limiti di incertezza e la procedura per i casi non elaborabili.
- Se i risultati vengono usati per cambiare configurazione o codice, quel lotto diventa calibrazione e non può fungere da prova finale. L'accettazione successiva richiede un campione congelato e separato, etichettato indipendentemente e non usato per tuning.
- Le soglie restano “non definite” fino a decisione esplicita; nessun risultato può chiudere la issue #10 prima di allora.

## Privacy, conservazione e cancellazione

- I documenti sorgente restano nella cartella scelta dall'utente. Ogni copia eventualmente importata e i derivati restano sul PC locale, nello spazio dell'applicazione; nessun contenuto va pubblicato.
- Conservazione fino a cancellazione esplicita. La verifica della riapertura, ripristino e cancellazione su archivio reale o sintetico è bloccata finché R7/R8 non siano formalmente sbloccati e accettati. Non eseguire test di lifecycle, archivio, backup o cancellazione in questa fase. Dopo lo sblocco, il piano dovrà identificare copie importate, record, anteprime, OCR, esportazioni, temporanei e backup controllati dall'app. Non promettere l'eliminazione da backup o copie esterne non controllate dall'app.
- La cancellazione deve essere esplicita, confermata e documentabile; una cancellazione incompleta o un errore di cleanup sospende il pilot e impedisce di iniziare un lotto successivo.
- Questo documento non autorizza ad aprire o elaborare documenti, cambiare configurazioni Windows, installare pacchetti/modelli o inviare dati a terzi.

## Decisioni ancora necessarie per la #10

| Decisione | Raccomandazione | Perché serve |
| --- | --- | --- |
| Campione iniziale (trasferta, mese/anno) e relativo PDF definitivo | Sceglierlo esplicitamente dopo che l'app è pronta e i limiti sono verificati. | Determina il lotto reale e consente di verificare che ciascuna ricevuta abbia un riferimento. |
| Revisione indipendente delle etichette | Seconda verifica umana indipendente per importi e casi ambigui; estenderla a tutti i campi se disponibile. | Riduce il rischio che una trascrizione o associazione errata venga scambiata per errore OCR. |
| Soglie di accettazione per campo | Definirle dopo la baseline, poi verificarle su un campione separato e congelato. | Evita soglie arbitrarie e impedisce di validare sullo stesso lotto usato per tuning. |
| Sicurezza input e cap effettivo del lotto | Verificare validazione dei percorsi, file malformati/ostili e limiti di byte, pagine, espansione, tempo, memoria e spazio prima di confermare “100”. | L'obiettivo di 100 non dimostra capacità o sicurezza del flusso. |

## Stato e prossimi passi

1. Riesaminare questa proposta con il proprietario; nessun pilot è iniziato.
2. Chiudere i prerequisiti di runtime e identificare l'autorità necessaria per R7/R8; non eseguire prove di archivio, riapertura o cancellazione finché i blocchi sono attivi.
3. Valutare controlli sintetici per percorsi, file malformati/ostili e limiti di risorse solo se dimostrabilmente indipendenti da R7/R8, autorizzati e revisionati; altrimenti registrarli come bloccati, senza tentativi.
4. Solo allora chiedere l'autorizzazione circoscritta per baseline locale, specificando campione, procedure, metriche e cleanup.
5. Mantenere la issue #10 aperta finché decisioni, verifiche e autorizzazioni richieste non sono documentate.
