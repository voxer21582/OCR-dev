# OCR2 — design per il completamento del prodotto

Data: 2026-11-15. Stato: **bozza per l'approvazione del proprietario**. Fonte dell'obiettivo: `GOAL.md` (non negoziabile). Questo documento descrive *come* portare il prototipo attuale al prodotto; il piano a milestone dettagliato (`docs/plan.md`) viene scritto solo dopo l'approvazione di questo design.

## 1. Intento

Il proprietario vuole un'applicazione Windows completa di Document Intelligence (GOAL §1, capacità 1–9), usata per prima cosa per le note spese: una nota spese finale confrontata con i giustificativi. Il proprietario non programma: ogni scelta va spiegata in parole semplici e ogni "fatto" va dimostrato con evidenze salvate nel repository (GOAL V8).

Oggi il repository contiene un **prototipo avanzato** (circa 15.000 righe di codice e 660 test, tutti su dati sintetici, un solo PC, nessun collaudo formale). Il lavoro consiste nel consolidarlo e completarlo, non nel riscriverlo.

## 2. Obiettivi, non-obiettivi, anti-obiettivi

**Obiettivi**
- Le 9 capacità di GOAL §1, ciascuna con requisiti numerati (REQ-xxx), criteri di accettazione verificabili ed evidenze in `docs/evidence/`.
- I file di processo richiesti da GOAL: `docs/requirements.md`, `docs/architecture.md`, `docs/plan.md`, `docs/dependencies-approved.md`, `docs/dependencies-request.md`, `docs/decisions.md`, `docs/questions.md`, `docs/STATUS.md`, `docs/evidence/`.
- Un installer per utente, offline, senza privilegi di amministratore, con aggiornamento, ripristino della versione precedente e disinstallazione che conserva i dati dell'utente.
- Una prova finale su un piccolo campione di documenti veri, con soglie fissate prima.

**Non-obiettivi**
- Più utenti, accesso da rete, server condivisi.
- OCR nel cloud, download di modelli a runtime, telemetria.
- Distribuzione a terzi (D2: solo i PC del proprietario; prima di distribuire serve una revisione legale).
- Approvazione automatica di rimborsi, pagamenti o registrazioni contabili.
- Documenti Office (l'utente li esporta in PDF).

**Anti-obiettivi** (il lavoro è fallito anche se "funziona")
- Un valore incerto mostrato come confermato, o un campo senza evidenza della sua origine.
- Un documento reale, testo OCR reale o dati personali nel repository o in CI.
- Una connessione di rete in uscita durante l'uso.
- Una milestone o il prodotto dichiarati completi senza evidenze in `docs/evidence/`.
- Lavoro concorrente sovrascritto o storia condivisa riscritta.

## 3. Vincoli

Tutti i vincoli V1–V9 di `GOAL.md`, più quelli ereditati in `docs/product/requirements.md` §2. In particolare:
- **V2**: anche le fixture dei benchmark devono essere generate da script nel repository. Oggi il benchmark da 100 documenti usa fixture esterne senza generatore: va corretto.
- **V3**: si usano solo i componenti in `docs/dependencies-approved.md` (vedi §5.2). Ogni componente nuovo va in `docs/dependencies-request.md` e il lavoro che ne dipende si ferma fino all'approvazione.
- **V4**: nessuna modifica a impostazioni, registro, servizi o file di sistema di Windows. L'installer scrive solo nella cartella dell'utente e crea collegamenti per l'utente.
- **V6**: niente tentativi ripetuti per aggirare un errore esterno: si registra e ci si ferma.

## 4. Approcci considerati

| Approccio | Pro | Contro | Esito |
|---|---|---|---|
| **1. Consolidare l'esistente** | Riusa codice testato e correzioni già fatte; più rapido; meno rischio | Eredita un file molto grande (`local_intake_app.py`, 2.575 righe) e 30 PR aperte da riordinare | **Scelto dal proprietario** |
| 2. Riscrivere da zero seguendo GOAL alla lettera | Struttura nuova e uniforme | Butta lavoro testato, reintroduce difetti già corretti, molto più lungo | Scartato |
| 3. Consolidare e spezzare subito il file grande | Codice più ordinato | Costo iniziale senza beneficio visibile | Scartato come passo iniziale: il file si spezza solo dove una milestone ci lavora |

## 5. Decisioni del proprietario (2026-11-15)

### 5.1 R7/R8
Il proprietario è il responsabile di R7 (archivio e ripristino) e R8 (esportazione). Il lavoro può modificare queste parti; **ogni PR che le tocca richiede l'approvazione esplicita del proprietario** prima del merge e lo dice nella descrizione. Le regole stop/no-retry restano valide.

### 5.2 Componenti approvati
Approvati così come sono, con le versioni e le impronte già bloccate:
1. **Runtime OCR Windows**: i 22 pacchetti di `requirements/ocr2-runtime-cp313-win-amd64.lock` (tra cui RapidOCR 3.10.0, onnxruntime, OpenCV headless, numpy, Pillow, pypdfium2) e i due modelli PP-OCRv6 con le impronte registrate (issue #9).
2. **Strumenti CI**: i lock `ci-taxonomy`, `ci-pytest` e `ci-decoder` (jsonschema, pytest, Pillow, pypdfium2 e le loro dipendenze).
3. **Già presenti sul PC**: Python 3.13 e Node.js (solo per il test della tastiera).

Il file FFmpeg incluso in OpenCV (LGPL) **non va nell'installer** finché il proprietario non decide (proposta: escluderlo dopo aver verificato che l'OCR funziona senza).

### 5.3 Prova su documenti veri
L'ultima milestone è una prova sul campo: il proprietario sceglie 30–50 documenti veri e li elabora sul proprio PC. Documenti e risultati restano sul suo PC; nel repository entrano solo numeri riassuntivi senza contenuto. Le soglie si fissano e si registrano prima della prova. Il prodotto è completo solo dopo questa milestone.

**Chi la esegue (decisione del 2026-11-15): il costruttore (Claude), sul PC del proprietario.** Il proprietario mette i documenti in una cartella fuori dal repository e compila un foglio con le risposte giuste (per esempio data, totale, valuta di ogni documento). Il costruttore avvia l'app e uno script di punteggio che confronta i risultati con quel foglio e stampa solo numeri. Regole:
- per impostazione il costruttore legge solo i numeri dello script, non testi, immagini o log dei documenti;
- per capire un errore il costruttore può guardare un singolo documento solo con il permesso del proprietario, caso per caso; il contenuto visto passa dal servizio di Claude (fuori dal PC) e non viene mai scritto nel repository;
- cartella dei documenti, foglio delle risposte e archivio della prova restano fuori dal repository e si cancellano a fine prova se il proprietario lo chiede.

### 5.5 PC pulito, revisione di sicurezza, dati esistenti
- **PC pulito per M6**: un altro PC del proprietario, usato per installazione, aggiornamento, ritorno indietro e disinstallazione. Le prove su quel PC le esegue il proprietario con una procedura scritta, oppure il costruttore se il proprietario lo rende disponibile.
- **Revisione di sicurezza (M7)**: un revisore automatico indipendente (agente o skill di revisione, senza contesto del lavoro) più la firma finale del proprietario. Il limite è dichiarato nell'evidenza: non è una revisione di un esperto umano.
- **Dati già presenti nell'archivio del PC**: nessuno da conservare. La migrazione tra versioni si collauda solo con dati sintetici; l'archivio del prototipo si può cancellare.

### 5.4 Finestra
L'app si apre in una finestra di Microsoft Edge in modalità app (senza barra degli indirizzi, con la propria icona nella barra delle applicazioni). Nessun componente nuovo. Servono un comando "Esci" nell'interfaccia e lo spegnimento automatico del server quando nessuna finestra è più collegata.

## 6. Scelte del costruttore (reversibili, da registrare in `docs/decisions.md`)

| Scelta | Alternative | Come tornare indietro |
|---|---|---|
| Requisiti rinumerati REQ-xxx in `docs/requirements.md`, con colonna del vecchio ID (IMP-1, OCR-3, …). `docs/product/requirements.md` diventa un rimando. | Tenere i vecchi ID | Ripristinare il vecchio file |
| Stati dei campi: i sei stati interni restano; si aggiunge la corrispondenza con i quattro di GOAL (valido = osservato e confermato o con validazione superata; incerto = incerto; mancante = assente o illeggibile; non valido = rifiutato o validazione fallita; "non applicabile" resta distinto e motivato). | Ridurre a quattro stati interni | Cambiare solo la tabella di corrispondenza |
| Multi-motore dimostrato con un registro a manifest e un secondo motore di prova che gira nei test. Un secondo motore vero è una richiesta separata. | Integrare subito un secondo motore vero | Aggiungere un manifest |
| Organizzazione dell'archivio con etichette (parole chiave) e rinomina. | Cartelle | Aggiungere le cartelle sopra le etichette |
| Il "chi" nella storia delle correzioni è il nome dell'utente Windows; un solo utente. | Account interni | Aggiungere account dietro un nuovo requisito |
| Aggiornamento: un nuovo installer sopra il vecchio, offline, con ritorno alla versione precedente; i dati utente restano. | Aggiornamento automatico da internet (vietato da A5) | — |
| Interfaccia in italiano; inglese più avanti (SHOULD). | Bilingue subito | Aggiungere il catalogo inglese |
| La numerazione delle milestone in `docs/plan.md` sostituisce quella di `docs/product/requirements.md` §11 e dell'issue #137; il lavoro già fatto (vecchie M1 e M2) è registrato come base di partenza con le sue evidenze. | Tenere M0–M6 | Rinumerare |
| Le 30 PR aperte si passano in rassegna una per una; nessuna si chiude o si unisce senza il sì del proprietario. | Lasciarle aperte | — |
| Se la prova non raggiunge le soglie: si registra l'esito, si correggono le cause e si ripete **una volta** su un campione nuovo (per non adattarsi agli stessi documenti). Abbassare le soglie richiede la firma del proprietario. Dopo il secondo tentativo decide il proprietario. | Ripetere senza limite; abbassare le soglie | Cambiare il numero di tentativi |
| L'installer porta con sé il proprio Python 3.13 (distribuzione embeddable) e il proprio runtime, così l'app non dipende dal Python del PC. Python embeddable e NSIS vanno richiesti in `docs/dependencies-request.md` già nella Fase 0, per non fermare M6. | Usare il Python già installato | Cambiare il pacchetto del runtime |
| CI: si aggiunge un job su runner Windows di GitHub (gratuito per repository pubblici) per archivio cifrato (DPAPI), avvio e finestra; su Ubuntu restano i test con le parti Windows simulate. Le prove di installer e finestra reale restano locali e registrate in `docs/evidence/`. | Solo Ubuntu con simulazioni | Togliere il job |
| `GOAL.md`, oggi non versionato nella copia principale, entra nel repository con il primo commit della Fase 0. | Lasciarlo fuori | Rimuoverlo con un commit |

## 7. Architettura (sintesi; dettaglio in `docs/architecture.md`)

Si mantiene la struttura esistente:

```
Finestra Edge (modalità app) ──HTTP locale 127.0.0.1──▶ server locale (WSGI)
                                                         ├─ ingestione e limiti
                                                         ├─ worker OCR isolato ◀── registro dei motori (manifest)
                                                         ├─ proposte semantiche ◀── catalogo dei tipi (configurazione)
                                                         ├─ validazione e riconciliazione
                                                         ├─ revisione (storia append-only)
                                                         ├─ archivio cifrato per utente (R7)
                                                         └─ esportatori JSON/CSV (R8) ◀── registro degli esportatori
```

Punti di estensione da rendere espliciti:
1. **Motori OCR**: manifest (nome, versione, lingue, licenza, impronte degli artefatti, riferimento alla factory), verificato dentro il worker; un motore nuovo = manifest + adattatore, nessuna modifica altrove.
2. **Classificatori e catalogo**: tipi, campi e regole definiti da file di configurazione e da un editor nell'interfaccia; ogni record conserva l'istantanea del catalogo usato.
3. **Esportatori**: interfaccia comune; JSON e CSV obbligatori; altri formati dopo valutazione.
4. **Decodificatori di formato**: un formato nuovo segue la regola IMP-5 (decoder con licenza e impronta, limiti, test su input malformati).

Correzioni architetturali note:
- Le anteprime delle pagine si generano oggi nel processo web: vanno spostate in un worker isolato (SEC-3).
- `local_intake_app.py` si spezza per aree (fascicoli, archivio, revisione) solo quando una milestone ci lavora.

## 8. Ordine di lavoro proposto (le milestone esatte vanno in `docs/plan.md`)

| Fase | Contenuto | Evidenza di chiusura |
|---|---|---|
| **Fase 0** | I file di processo di GOAL; requisiti REQ-xxx con criteri; dipendenze approvate e richieste; `STATUS.md` = IN ATTESA DI APPROVAZIONE. | Approvazione del proprietario |
| M1 Ordine | Rassegna delle 30 PR (#144 e #141 per prime); evidenze esistenti spostate in `docs/evidence/` (solo dati sintetici); generatore delle fixture del benchmark nel repository; tutti i moduli di test in CI (ora che R7/R8 hanno un responsabile). | CI verde con l'elenco completo; benchmark rigenerabile |
| M2 Motori | Registro dei motori con manifest; motore di prova; avvio guidato dal registro; testo incorporato dei PDF come produttore distinto; anteprime isolate; rotazione. | Aggiungere il motore di prova senza toccare altri file (diff) |
| M3 Classificazione ed estrazione | Catalogo collegato a interfaccia e archivio; editor del catalogo; corrispondenza degli stati; nome dell'esercente; righe di fattura (SHOULD). | Fixture a risposta nota; giro completo del catalogo |
| M4 Revisione | "Chi" nella storia; percorso completo da tastiera; checklist di accessibilità. | Percorso registrato; checklist compilata |
| M5 Libreria (R7/R8) | Rinomina, etichette, filtri di ricerca, CSV dall'interfaccia, backup e ripristino, migrazione tra versioni, ripresa dopo interruzione (issue #8). | Prove di interruzione e migrazione con dati sintetici |
| M6 Applicazione e installer | Finestra Edge in modalità app, "Esci", spegnimento automatico; installer per utente; aggiornamento, ritorno indietro, disinstallazione; elenco dei componenti (SBOM) e notice; firma del proprietario. | Matrice installazione/aggiornamento/disinstallazione su un PC pulito |
| M7 Sicurezza e prestazioni | Modello delle minacce; revisione di sicurezza indipendente; prova di assenza di traffico di rete; misure di prestazione (PRF-1…4). | Revisione firmata; misure registrate |
| M8 Prova sul campo | Protocollo e soglie approvati; prova eseguita dal costruttore sul PC del proprietario su 30–50 documenti veri; collaudo Windows. | Numeri riassuntivi contro soglie; firma del proprietario |

Ogni milestone: test prima del codice, revisione indipendente prima della chiusura, `STATUS.md` aggiornato, evidenze in `docs/evidence/<milestone>/`.

## 9. Lasciato al costruttore

- La forma esatta dei manifest, del registro degli esportatori e del formato di backup.
- Il dettaglio dei requisiti REQ-xxx e la loro suddivisione nelle milestone, purché ogni capacità di GOAL §1 sia coperta.
- Quali PR vecchie proporre di chiudere, unire o ripartire (la decisione resta al proprietario).
- Lo strumento per costruire l'installer: **non è tra i componenti approvati** (il piano Windows indica NSIS 3.x e una distribuzione embeddable di CPython 3.13). Va richiesto in `docs/dependencies-request.md` nella Fase 0 (vedi §6).
- Come ottenere una prova forte di assenza di traffico di rete senza modificare Windows (V4): da proporre al proprietario in M7.
