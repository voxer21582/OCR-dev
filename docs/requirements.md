# OCR2 — Requisiti (REQ-xxx)

Fonte: [`GOAL.md`](../GOAL.md) §1–2, il design approvato il 2026-11-15 ([`superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](superpowers/specs/2026-11-15-ocr2-product-completion-design.md)) e la baseline precedente [`product/requirements.md`](product/requirements.md) (colonna «Vecchio ID»). Nessun requisito è ancora *accettato*.

**Priorità:** MUST (serve per il prodotto completo), SHOULD (atteso, rinviabile con decisione registrata), COULD.

**Stato oggi** (dalla baseline, al commit `03cdab9` di `main`): `SYN-CI` test sintetici in CI · `SYN-LOCAL` test sintetici solo in locale · `LOCAL-RUN` provato sul PC di sviluppo con dati sintetici · `IN-PR` in una PR aperta · `OPEN` assente o senza evidenza. Nessuno di questi stati è accettazione.

**Accettato** = criterio soddisfatto + evidenza in `docs/evidence/` + revisione indipendente (GOAL V8, §4).

## P — Processo e verificabilità

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-001 | I file di processo di GOAL esistono e `docs/STATUS.md` è aggiornato a ogni giro. | MUST | I nove file/cartelle di GOAL §4 Fase 0 esistono; ogni commit di milestone aggiorna `STATUS.md`. | — | 0 | fatto (#145) |
| REQ-002 | Ogni affermazione di completamento rimanda a un'evidenza in `docs/evidence/`. | MUST | Ogni criterio marcato soddisfatto in `STATUS.md` ha un link a un file esistente in `docs/evidence/`. | — | M1 | fatto per M1 (`evidence/M1/acceptance.md`) |
| REQ-003 | Tutte le fixture, compresi i benchmark, sono generate da script nel repository. | MUST | Lo script genera le fixture del benchmark del fascicolo due volte con impronta SHA-256 identica; nessun test legge file fuori dal repository o dalla cartella temporanea. | — | M1 | fatto (M1) |
| REQ-004 | Tutti i moduli di test girano in CI, senza salti non spiegati. | MUST | Il workflow elenca ogni `application/tests/test_*.py` e i test di tassonomia; ogni salto ha un motivo dichiarato; il job Windows esegue i test DPAPI e del launcher. | — | M1 | fatto (M1: Ubuntu + Windows) |
| REQ-005 | Revisione indipendente prima di chiudere ogni milestone. | MUST | Rapporto del revisore in `docs/evidence/Mx/review.md` e correzioni registrate. | — | tutte | — |

## IMP — Importazione

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-010 | Importa PDF, PNG, JPEG, WebP, TIFF multipagina e ZIP di questi. | MUST | Fixture per ogni formato: numero di pagine e SHA-256 corretti; estensione sbagliata riconosciuta dalla firma; tipo non supportato rifiutato con codice stabile. | IMP-1 | M1 | `SYN-CI`, `LOCAL-RUN` |
| REQ-011 | Limiti espliciti e configurabili (dimensione, membri, espansione, rapporto di compressione, pixel, pagine); archivi annidati e percorsi pericolosi rifiutati. | MUST | Test al limite e oltre ogni limite; nessun file scritto su disco durante l'inventario. | IMP-2 | M1 | `SYN-CI` |
| REQ-012 | Un fascicolo: una nota spese più almeno 100 giustificativi, caricamento a blocchi ripetibile e riprendibile. | MUST | 5×20 blocchi accettati; ripetizione idempotente; 101° allegato rifiutato; caricamento interrotto riprende. | IMP-3 | M5 | `SYN-LOCAL`, `LOCAL-RUN` |
| REQ-013 | Duplicati esatti segnalati, mai rimossi in silenzio. | MUST | Test con due copie: entrambe le identità elencate. | IMP-4 | M1 | `SYN-CI` |
| REQ-014 | Altri formati ammessi solo dopo valutazione documentata; GIF a fotogramma singolo e BMP. | SHOULD | Per formato: decisione, limiti, test su input malformati, provenienza. | IMP-5, D4 | M2 | `SYN-CI` (M2) |
| REQ-015 | PDF cifrati o protetti rifiutati con messaggio chiaro. | MUST | Codice stabile, nessun crash, test in CI. | IMP-6 | M1 | `SYN-CI` (M1) |

## OCR — Riconoscimento con provenienza e più motori

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-020 | Ogni testo riconosciuto è legato a SHA-256 del documento, pagina, area (poligono normalizzato), motore, versione del motore e modello, confidenza. | MUST | Test di contratto; le evidenze di un record risalgono ai byte originali. | OCR-1 | M2 | `SYN-CI`, `LOCAL-RUN` |
| REQ-021 | Interfaccia di motore OCR intercambiabile. | MUST | Pipeline e revisione non importano alcun modulo specifico di un motore (test di importazione). | OCR-2 | M2 | `SYN-CI` (M2) |
| REQ-022 | Registro dei motori a manifest (nome, versione, lingue, licenza, impronte degli artefatti, factory), selezionabile per installazione e per lavoro, verificato nel worker. | MUST | Impronta o versione errata → errore con codice stabile, nessun OCR; il launcher sceglie il motore dal registro. | OCR-3 | M2 | `SYN-CI`, `LOCAL-RUN` (M2) |
| REQ-023 | Aggiungere un motore non richiede modifiche al resto del sistema. | MUST | Il motore di prova si aggiunge con soli file nuovi (manifest + adattatore + test): il diff della sua PR non tocca altri file. | OCR-3 | M2 | fatto (M2, `evidence/M2/engine-diff.md`) |
| REQ-024 | Worker OCR isolato con limiti di memoria e tempo, annullamento, comunicazione limitata, pubblicazione unica del risultato. | MUST | Test su limiti, annullamento, timeout e corse in CI. | OCR-4 | M1 | `SYN-CI` (M1; Job Object sul job Windows), `LOCAL-RUN` |
| REQ-025 | Pagine parziali o fallite hanno codici non sensibili e non producono proposte. | MUST | Test di contratto. | OCR-5 | M2 | `SYN-CI` |
| REQ-026 | Italiano e inglese riconosciuti. | MUST | Fixture sintetiche miste con soglie registrate (M3); campione reale in M8. | OCR-6 | M3/M8 | `LOCAL-RUN` sintetico (M3: it/en); soglie reali in M8 |
| REQ-027 | Uso del testo incorporato nei PDF, come produttore distinto. | SHOULD | Un PDF con testo produce token senza OCR raster; la provenienza nomina il produttore. | OCR-7 | M2 | `SYN-CI` (M2) |
| REQ-028 | Orientamento: EXIF, rotazioni di 90°/180°/270°. | SHOULD | Fixture ruotate riconosciute. | OCR-8 | M2 | `SYN-CI` (M2, angolo registrato in M3) |
| REQ-029 | OCR spento salvo attivazione esplicita; il runtime incompleto è segnalato all'avvio. | MUST | Avvio con pacchetto o modello mancante → messaggio specifico, nulla avviato. | OCR-9 | M1 | `SYN-CI` (M1), `LOCAL-RUN` |
| REQ-030 | Anche le anteprime delle pagine si decodificano in un worker isolato. | MUST | Un PDF malformato in anteprima non ferma il server (test). | SEC-3 | M2 | `SYN-CI` (M2) |

## CLS — Classificazione configurabile

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-040 | Tipi di documento predefiniti (fattura, scontrino fiscale, ricevuta parcheggio, documento d'albergo, nota spese, scontrino POS, altro, sconosciuto). | MUST | Test di contratto. | CLS-1 | — | `SYN-CI` |
| REQ-041 | Catalogo dei tipi definito da configurazione (tipi, campi tipizzati, obbligatori, alias), con istantanea legata da impronta a ogni record; collegato a interfaccia e archivio. | MUST | Catalogo non valido rifiutato; record riaperto conserva la sua istantanea; giro completo nell'interfaccia. | CLS-2 | M3 | `SYN-CI`, `LOCAL-RUN` (M3) |
| REQ-042 | Le regole di classificazione (parole chiave, alias, pesi) stanno nel catalogo, non nel codice. | MUST | Un tipo nuovo definito solo da catalogo viene proposto su una fixture sintetica. | — | M3 | `SYN-CI` (M3) |
| REQ-043 | La classificazione è una proposta con evidenza e alternative; la sceglie una persona; la scelta è nella storia. | MUST | Nessuna conferma automatica (test). | CLS-3 | — | `SYN-CI` |
| REQ-044 | Contratto di tassonomia versionato. | MUST | Test del registro e del binding. | CLS-4 | — | `SYN-CI` |
| REQ-045 | Editor del catalogo nell'interfaccia: crea, importa, esporta, versiona. | MUST | Creare un tipo, applicarlo a un record, riaprire. | CLS-5 | M3 | `SYN-CI`, `LOCAL-RUN` (M3) |

## EXT — Estrazione dei campi

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-050 | Modello del candidato: valore, stato, alternative, confidenza, evidenza, regola e versione di normalizzazione. | MUST | Schema e test; nessun campo confermato senza evidenza. | EXT-1 | — | `SYN-CI` |
| REQ-051 | Campi comuni con evidenza: date per ruolo, importi, valuta, totali, IVA e identificativi fiscali, numero documento, riferimenti di pagamento, intestatario, mance. | MUST | Fixture per campo con casi positivi e negativi. | EXT-2 | M3 | `SYN-CI`, `LOCAL-RUN` (M3) |
| REQ-052 | Nome dell'esercente con evidenza. | MUST | Fixture sintetiche; alternative quando ambiguo. | — | M3 | `SYN-CI`, `LOCAL-RUN` (M3) |
| REQ-053 | Righe di fattura e tabelle con totali ed evidenza. | SHOULD | Fatture sintetiche producono righe legate alle aree. | EXT-3 | M3 | `SYN-CI`, `LOCAL-RUN` (M3) |
| REQ-054 | Righe della nota spese (data, descrizione, importo, valuta) con evidenza; valori incerti restano alternative. | MUST | Fixture a risposta nota. | EXT-4 | — | `SYN-CI`, `LOCAL-RUN` |
| REQ-055 | Normalizzazione per lingua (virgola decimale, separatori, ordine giorno/mese) che conserva il letterale e ogni lettura ambigua. | MUST | Fixture a tabella per it-IT ed en. | EXT-5, D3 | M3 | `SYN-CI` |
| REQ-056 | Valori mancanti, illeggibili e superamento dei limiti espliciti con codici stabili. | MUST | Test di overflow. | EXT-6 | — | `SYN-CI` |
| REQ-057 | Obiettivi di accuratezza per famiglia di campi, misurati su fixture sintetiche. | MUST | Soglie registrate prima della misura; report in `docs/evidence/M3/`. | EXT-7 | M3 | `LOCAL-RUN` sintetico (M3), soglie superate |

## VAL — Validazione, incertezza, valori mancanti

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-060 | Ogni campo mostra uno dei quattro stati di GOAL (valido, incerto, mancante, non valido) con la motivazione, nell'interfaccia e nell'export. «Non applicabile» resta distinto e motivato. | MUST | Tabella di corrispondenza documentata (DEC-013); test per ogni stato interno; colonna stato e motivo nel CSV. | — | M3 | `SYN-CI` (M3) |
| REQ-061 | Esiti di validazione deterministici (superato, fallito, indeterminato) con ID di regola stabili; aritmetica decimale esatta. | MUST | Test delle regole. | VAL-1 | — | `SYN-CI` |
| REQ-062 | Riconciliazione tra righe della nota e giustificativi: conflitti d'importo, valuta, data; possibili duplicati; supporto mancante; solo suggerimenti. | MUST | Fixture a risposta nota in CI; benchmark del fascicolo rigenerabile (REQ-003). | VAL-2 | M1 | `SYN-CI`, `LOCAL-RUN` (M1); limite aperto: giustificativo avanzato proposto a righe dello stesso giorno (M3) |
| REQ-063 | Nessuna approvazione automatica. | MUST | Nessun percorso scrive uno stato confermato senza un evento umano (test). | VAL-3 | — | `SYN-CI` |
| REQ-064 | Regole di validazione versionate; i record già revisionati conservano i vecchi esiti. | SHOULD | Regola aggiunta; vecchi record invariati. | VAL-4 | M3 | `SYN-CI` (M3) |

## REV — Revisione e correzione

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-070 | La revisione mostra pagina originale, area, alternative, incertezza e motivi. | MUST | Percorso nel browser registrato. | REV-1 | M4 | `LOCAL-RUN` |
| REQ-071 | Correzioni solo in aggiunta: valore originale conservato; risultati derivati superati marcati. | MUST | Test di correzione, conflitto e invalidazione. | REV-2 | — | `SYN-CI` |
| REQ-072 | Ogni evento di revisione registra chi (nome utente Windows) e quando (UTC), ed è nell'export. | MUST | Test: evento con utente e orario; export JSON e CSV li contengono. | — | M4 | `OPEN` |
| REQ-073 | Selezione manuale dell'area per campi assenti, con mouse e tastiera. | MUST | Test DOM e percorso nel browser. | REV-3 | M4 | `SYN-CI` |
| REQ-074 | Revisione della riconciliazione: conferma, rifiuto, ambiguo, supporto mancante, possibile duplicato, esclusione motivata, legata alla revisione corrente. | MUST | Revisioni obsolete rifiutate; storia solo in aggiunta. | REV-4 | M1 | `SYN-CI` (M1), `LOCAL-RUN` |
| REQ-075 | Accessibilità: uso completo da tastiera, etichette, ordine del focus, contrasto. | MUST | Checklist compilata con l'Assistente vocale di Windows. | REV-5 | M4 | `OPEN` |
| REQ-076 | Tempo di revisione registrato ed esportabile, mai usato per decidere. | SHOULD | Export CSV. | REV-6 | M1 | `SYN-CI` (M1) |

## LIB / EXP — Archivio ed esportazione (R7/R8, responsabile: proprietario)

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-080 | Archivio locale cifrato per utente Windows; salva, apri, elimina espliciti. | MUST | Dopo riavvio, record e byte originali identici. | LIB-1 | M5 | `SYN-LOCAL`, `LOCAL-RUN` |
| REQ-081 | Ricerca per testo, tipo, data, stato, etichetta; risultati limitati e paginati. | MUST | Test di ricerca a risposta nota. | LIB-2 | M5 | `SYN-CI`, `LOCAL-RUN` (M5, PR in bozza) |
| REQ-082 | I fascicoli si salvano e riprendono (nota, allegati, blocchi, eventi). | MUST | Interruzione durante caricamento e OCR, poi ripresa. | LIB-3 | M5 | `SYN-CI` (M5, PR in bozza) |
| REQ-083 | Rinomina di documenti e fascicoli. | MUST | Il nome cambia, l'identità e la storia no; evento registrato. | — | M5 | `SYN-CI`, `LOCAL-RUN` (M5, PR in bozza) |
| REQ-084 | Organizzazione con etichette (aggiungi, togli, filtra). | MUST | Test e percorso nel browser. | — | M5 | `SYN-CI`, `LOCAL-RUN` (M5, PR in bozza) |
| REQ-085 | Eliminazione di record e sorgenti, con limiti della cancellazione sicura documentati. | MUST | Dopo l'eliminazione, record e sorgenti non sono più leggibili dall'app. | LIB-4 | M5 | `SYN-CI`; limiti in `product/deletion-limits.md` (M5, PR in bozza) |
| REQ-086 | Backup e ripristino dell'archivio. | MUST | Backup, cancellazione, ripristino → contenuto identico (impronte). | LIB-5 | M5 | `SYN-CI`, `LOCAL-RUN` (M5, PR in bozza) |
| REQ-087 | Integrità, migrazione dello schema tra versioni, scritture interrotte. | MUST | Fixture sintetiche per ogni versione dello schema; test con interruzione simulata. | LIB-5 | M5 | `SYN-CI` (M5, PR in bozza) |
| REQ-088 | Export di un record in JSON completo e in CSV, su azione esplicita, dall'interfaccia. | MUST | Output deterministico; celle CSV protette da formule. | EXP-1 | M5 | `SYN-CI`, `LOCAL-RUN` (M5, PR in bozza) |
| REQ-089 | Export di una riconciliazione con suggerimenti, decisioni ed evidenze separati; reimportabile per verifica. | MUST | Andata e ritorno senza perdite. | EXP-2 | M5 | `SYN-CI`; non rileva falsificazioni volute (M5, PR in bozza) |
| REQ-090 | Esportatori dietro un'interfaccia comune; un formato nuovo non cambia il resto. | MUST | Esportatore di prova aggiunto con soli file nuovi. | — | M5 | `SYN-CI` (M5, PR in bozza) |
| REQ-091 | Altri formati (foglio di calcolo, PDF con evidenze) dopo valutazione. | COULD | Decisione registrata. | EXP-3 | — | `OPEN` |

## APP / INS — Applicazione, installazione, aggiornamento

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-100 | L'app si apre in una finestra di Edge in modalità app, senza modificare impostazioni di Edge o Windows. | MUST | Procedura con screenshot; nessuna chiave di registro o impostazione cambiata (confronto prima/dopo delle cartelle dell'utente). | — | M6 | `OPEN` |
| REQ-101 | Comando «Esci» e spegnimento automatico del server quando nessuna finestra è collegata. | MUST | Test: dopo «Esci» o dopo il timeout senza finestra la porta è libera e il processo è terminato. | — | M6 | `OPEN` |
| REQ-102 | Installer per utente, offline, senza privilegi di amministratore (NSIS + Python embeddable). | MUST | Installazione su PC pulito (DEC-007); elenco documentato dei file e delle voci per utente create. | INS-1 | M6 | `OPEN` |
| REQ-103 | Il runtime installato è verificato (impronte delle wheel e dei modelli, notice); nessun download. | MUST | Verifica delle impronte all'installazione e all'avvio. | INS-2 | M6 | `OPEN` |
| REQ-104 | Aggiornamento, recupero da aggiornamento interrotto, ritorno alla versione precedente, disinstallazione; i dati restano se l'utente non li toglie. | MUST | Matrice del ciclo di vita eseguita sull'altro PC. | INS-3 | M6 | `OPEN` |
| REQ-105 | Installer e binari firmati dal proprietario. | MUST | La firma si verifica; l'evidenza registra chi ha firmato e quando. | INS-4, D1 | M6 → milestone successiva | rinviato: limite dichiarato (DEC-034); M6 si chiude con installer non firmati e avviso SmartScreen |
| REQ-106 | Un collegamento nel menu Start per l'utente; versione e identità del runtime visibili nell'app. | MUST | Checklist. | INS-5 | M6 | `OPEN` |
| REQ-107 | SBOM e notice di licenza nell'installer; decisione su FFmpeg (Q-001). | MUST | SBOM generato dai lock; notice presenti; FFmpeg trattato come deciso. | SEC-5 | M6 | parziale |
| REQ-108 | Pacchetto diagnostico senza contenuti, esportabile su richiesta. | SHOULD | Revisione del pacchetto. | OPS-1 | M7 | `OPEN` |
| REQ-109 | I lavori seguono stop/no-retry; annullamento affidabile. | MUST | Test di annullamento e fallimento. | OPS-2 | M1 | `SYN-CI` (M1) |
| REQ-110 | Interfaccia in italiano; inglese più avanti. | SHOULD | Catalogo dei testi. | OPS-3 | — | italiano fatto |

## SEC / PRF — Sicurezza e prestazioni

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-120 | Solo loopback; controlli di host, origine e token su ogni modifica. | MUST | Host, origine o token errati rifiutati. | SEC-1 | M1 | `SYN-CI` (M1) |
| REQ-121 | Nessun traffico di rete in uscita durante l'uso. | MUST | Fascicolo completo con registrazione delle connessioni del processo senza modificare Windows (es. hook Python più elenco delle connessioni del processo dal sistema); limiti dichiarati. | SEC-2 | M7 | parziale |
| REQ-122 | Archivio cifrato per utente; sessioni che scadono e si cancellano. | MUST | Test e verifica manuale. | SEC-4 | M5 | `SYN-CI` (M5, PR in bozza) |
| REQ-123 | Anteprime e risposte con CSP, nosniff, no-store. | MUST | Test sulle intestazioni in CI. | SEC-6 | M1 | `SYN-CI` (M1) |
| REQ-124 | Errori e log con codici stabili, mai testo dei documenti, percorsi o identificativi. | MUST | Checklist di revisione dei log. | SEC-7 | M7 | `OPEN` |
| REQ-125 | Modello delle minacce e revisione di sicurezza indipendente (automatica) firmata dal proprietario. | MUST | Documento firmato in `docs/evidence/M7/` (DEC-008). | SEC-8 | M7 | `OPEN` |
| REQ-126 | Repository e CI contengono solo dati sintetici. | MUST | Test di guardia. | SEC-9 | — | `SYN-CI` |
| REQ-127 | Al massimo 3 s per pagina sul PC di riferimento. | MUST | Mediana sul benchmark rigenerabile. | PRF-1 | M7 | `LOCAL-RUN` 1,9–2,9 s |
| REQ-128 | Un fascicolo da 1 + 100 documenti in al massimo 10 minuti, riprendibile, con avanzamento visibile. | MUST | Benchmark e prova di interruzione. | PRF-2 | M7 | `LOCAL-RUN` |
| REQ-129 | Al massimo 2 GiB per worker; interazione p95 sotto 200 ms. | MUST | Tracce di memoria e latenza. | PRF-3 | M7 | memoria `LOCAL-RUN` |
| REQ-130 | Avvio fino alla finestra usabile in al massimo 5 s; PDF da 100 pagine gestito nei limiti. | SHOULD | Misure. | PRF-4 | M7 | `OPEN` |

## FLD — Prova sul campo

| ID | Requisito | Pri | Criterio di accettazione | Vecchio ID | M | Stato |
|---|---|---|---|---|---|---|
| REQ-140 | Protocollo, soglie e foglio delle risposte giuste approvati dal proprietario prima della prova. | MUST | Documento firmato in `docs/evidence/M8/`, senza contenuti dei documenti. | — | M8 | `OPEN` |
| REQ-141 | Lo script di punteggio confronta i risultati con il foglio e stampa solo numeri. | MUST | Test su un campione sintetico: l'output non contiene testo dei documenti. | — | M8 | `OPEN` |
| REQ-142 | Prova eseguita su 30–50 documenti veri; numeri riassuntivi contro soglie (DEC-005, DEC-006). | MUST | Report numerico in `docs/evidence/M8/`; documenti e risultati fuori dal repository. | — | M8 | `OPEN` |
| REQ-143 | Collaudo finale Windows 11 firmato dal proprietario. | MUST | Checklist del piano Windows firmata. | — | M8 | `OPEN` |
