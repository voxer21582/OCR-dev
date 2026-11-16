STATO: M6 IN CORSO — Python compilato, verifiche e installer in corso — applicazione installabile; piano in [2026-11-15-m6-applicazione-installabile.md](superpowers/plans/2026-11-15-m6-applicazione-installabile.md)
Preparato contenuto 0.6.0 con Python locale e 22 wheel del lock; verifica manifest, OCR sintetico senza FFmpeg e avvio locale HTTP 200 riusciti. Non è ancora un installer completo: SBOM, licenze, lifecycle, firma, PC pulito, CI e revisione restano aperti. [Evidenza](evidence/M6/payload.md).
Build Python 3.13.18 x64 riuscita con accesso agli strumenti locali; import dei moduli principali riuscito. Prove estese del runtime e creazione dell'installer ancora da completare. [Evidenza](evidence/M6/python-build.md).
Il 2026-11-16 il proprietario ha autorizzato una modifica di V6: diagnosi e tentativi reversibili senza modificare Windows. Diagnosi C1902 ripresa.
La build x64 di Python 3.13.18 è terminata con codice 1 e errori C1902 sugli strumenti Visual Studio; causa esatta non accertata, nessun binario verificato. Per V6 nessun tentativo alternativo. [Evidenza](evidence/M6/python-build.md).
Il proprietario ha richiesto un nuovo download: il sorgente ufficiale Python 3.13.18 è stato acquisito e la sua impronta coincide con quella pubblicata; verificata la presenza della licenza PSF. Restano la verifica di provenienza, licenze e impronte delle dipendenze esterne e la compilazione. [Evidenza](evidence/M6/python-source-download.md).
Diagnostica successiva su richiesta del proprietario: la verifica DNS in sola lettura è stata negata; causa precisa non accertata. Nessuna impostazione Windows modificata e nessun nuovo download tentato.
Il proprietario ha approvato R-003 il 2026-11-16, con verifica preventiva di licenze e impronte. Il primo download da python.org di Python-3.13.18.tar.xz è fallito con «Host sconosciuto». Nessuna compilazione avviata. Serve ripristinare la risoluzione del nome e poi riprendere senza aggirare il vincolo V6. Dettagli in [evidenza](evidence/M6/python-source-download.md).
Revisione parziale M6: corretti avvio con manifest mancante, directory collegate, manifest privo di file essenziali e riapertura dell’archivio tra verifica ed estrazione. Test mirati: 23 passati, 2 saltati; prova estesa launcher interrotta dopo un fallimento e un’attesa prolungata, esito non verificato. La protezione non è ancorata a un elemento indipendente e non dimostra resistenza a manomissioni intenzionali.
Task 6 avviato: costruttore locale verifica l'impronta dell'archivio Python, rifiuta percorsi ZIP pericolosi, installa wheel dal lock senza rete, esclude test/cache e DLL FFmpeg e genera il manifest. Test sintetici con installazione wheel simulata, manifest e CI: 22 passati e 2 saltati ([output](evidence/M6/payload-input-green.txt)). Mancano pin ufficiali, assemblaggio reale, test supplementari e revisione; non è ancora un installer verificato.
Suite sintetica completa Windows del runtime corrente: 952 test e 401 sottocasi passati, 2 saltati ([output](evidence/M6/runtime-suite.txt)). Il caso symlink fisico non è eseguibile con i permessi correnti, ma il rifiuto è verificato con simulazione; la prova OCR opt-in è stata eseguita separatamente ([output](evidence/M6/ocr-without-ffmpeg.txt)). La verifica indipendente rimane necessaria.
Task 5: confronto locale reale con runtime RapidOCR approvato e immagine sintetica, stesso testo riconosciuto con e senza DLL FFmpeg in una copia temporanea di OpenCV ([output](evidence/M6/ocr-without-ffmpeg.txt)). La prova riguarda una sola immagine sintetica e non sostituisce il benchmark completo o il payload dell'installer. Restano revisione, suite completa e le attività successive.
Task 5 in corso: il launcher verifica il manifest prima del server e blocca l'avvio su errore; in modalità finestra mostra un messaggio locale del sistema. Verificati anche directory mancanti, errori di scansione e DLL vietata inclusa nel manifest. Test mirati: 23 passati, 1 saltato (creazione symlink non consentita; controllo simulato separato passato), [output](evidence/M6/runtime-launcher-green.txt). Mancano prova OCR senza FFmpeg, revisione e suite completa. Scelta reversibile: dialogo locale anziché pagina statica, per segnalare l'errore senza avviare server né scrivere file fuori dal progetto; ritorno a pagina locale possibile in fase installer.
Ripresa in worktree separato dal commit `1ea5c43`: avviato Task 5, inventario runtime con verifica file mancanti, aggiunti, alterati e FFmpeg vietato. Test sintetico iniziale passato; prova symlink saltata per permessi Windows. Mancano integrazione al launcher, prove di sicurezza complete, prova OCR senza FFmpeg, revisione e suite prima di considerare il task completato. Nessuna modifica al worktree di Claude.
M6 (applicazione installabile) avviata il 2026-11-15 con le decisioni del proprietario: R-001 e R-002 approvate, Q-001 e Q-003 risolte (DEC-030, DEC-031, DEC-032); il collaudo su PC pulito lo esegue il proprietario con una procedura scritta.

## M5 — completata (2026-11-15, #150)

Approvazione: R7/R8 approvati dal proprietario il 2026-11-15; limite di REQ-089 accettato.

Criteri di accettazione M5 ed evidenze: [acceptance.md](evidence/M5/acceptance.md).
- Libreria: ricerca con filtri e pagine (REQ-081); rinomina di documenti e fascicoli (REQ-083); etichette (REQ-084). [Percorso nel browser](evidence/M5/browser-walkthrough.md).
- Archivio: eliminazione senza tracce nel file, con i [limiti documentati](product/deletion-limits.md) (REQ-085); backup e ripristino verificati (REQ-086); migrazione allo schema 4 e scritture interrotte (REQ-087); ripresa dei fascicoli dopo la riapertura (REQ-082).
- Export: dalla pagina (REQ-088); export del fascicolo riletto (REQ-089, con il limite dichiarato); registro dei formati, con un formato nuovo aggiunto con [soli file nuovi](evidence/M5/exporter-new-files.txt) (REQ-090); archivio cifrato e sessioni (REQ-122).
- [Revisione indipendente](evidence/M5/review.md): i quattro problemi importanti sono stati corretti in `75ce91d`.
- Suite locale: 881 test passati ([output](evidence/M5/suite-75ce91d.md)).
- La CI e il link alla PR sono nella PR. Nuova decisione: DEC-029. Q-003 risolta in M6 (DEC-031).


# Stato del lavoro

M4 verificata sulla proposta della PR #149: REQ-070 ([percorso browser](evidence/M4/browser-walkthrough.md)), REQ-072 ([test export](evidence/M4/ci-security-suite.txt)), REQ-073 ([regione manuale](evidence/M4/missing-fields-review.md)) e REQ-075 ([checklist e riscontro vocale](evidence/M4/accessibility-checklist.md)). CI [Ubuntu](https://github.com/voxer21582/OCR-dev/actions/runs/43750928840/job/132924474854) e [Windows](https://github.com/voxer21582/OCR-dev/actions/runs/43750928840/job/132924474509) passata su `b6dc0f5`; revisione indipendente e approvazione esplicita R8 del proprietario in [audit](evidence/M4/review.md). La PR è stata unita in `main` dal proprietario il 2026-11-15. CodeQL mantiene due avvisi medi, valutati senza divulgazioni concrete nei percorsi attuali ([limiti](evidence/M4/ci-security-review.md)).

## Cronologia della chiusura

Le voci successive descrivono lo stato al momento di ciascuna verifica e possono contenere attese successivamente risolte.

Il 2026-11-15 il proprietario ha approvato esplicitamente in chat le modifiche all'export R8 della PR #149 e ha richiesto la chiusura M4. I job Ubuntu e Windows sono passati sul commit `b6dc0f5`; CodeQL segnala due avvisi medi residui, riesaminati senza individuare divulgazioni concrete nei percorsi attuali ([valutazione](evidence/M4/ci-security-review.md)). Audit conclusivo in corso; nessun merge effettuato.

La PR #149 ha superato i job Ubuntu e Windows; resta in attesa dell'approvazione esplicita del proprietario per le modifiche all'export R8, richiesta da DEC-001. CodeQL mantiene due avvisi medi esaminati senza individuare divulgazioni concrete nei percorsi attuali ([valutazione](evidence/M4/ci-security-review.md)). Per riprendere serve la decisione del proprietario sulla PR; nessun merge è stato eseguito.

PR #149: su `cd37ce4` i job Ubuntu e Windows sono passati. CodeQL segnala due avvisi medi residui; l'audit indipendente non ha individuato una divulgazione concreta negli otto flussi esaminati ([dettagli e limiti](evidence/M4/ci-security-review.md)). La PR tocca R8 e attende l'approvazione esplicita del proprietario; la CI finale è consultabile nei controlli della PR.

PR #149 aperta in bozza: i job Ubuntu e Windows su `e4e0389` sono passati; CodeQL ha riportato tre avvisi di possibile esposizione di eccezioni. Sono stati corretti percorsi in cui `OSError` o `ValueError` interni potevano finire nella risposta, con test sentinella e revisione indipendente ([evidenza](evidence/M4/ci-security-review.md)). Suite locale: 837 test e 365 sottocasi passati ([output](evidence/M4/ci-security-suite.txt)). La CI deve essere rieseguita sulla nuova revisione.

Il proprietario ha autorizzato la pubblicazione del ramo e l'apertura della PR in bozza. La chiusura richiede CI Ubuntu/Windows riuscita; la PR tocca R8 e richiederà inoltre approvazione esplicita prima del merge. Dettagli e controlli di privacy in [proposal-review.md](evidence/M4/proposal-review.md).

Proposta locale separata preparata dalla base `origin/main`: i file applicativi e le evidenze riproducono il risultato revisionato senza includere la cronologia precedente del ramo M4. La suite sintetica nel nuovo worktree passa con 835 test e 365 sottocasi ([output](evidence/M4/proposal-windows-suite.txt)); il controllo privacy non ha trovato il percorso del profilo nel contenuto preparato. Restano pubblicazione della proposta, CI Ubuntu/Windows e approvazione esplicita del proprietario sulla PR che tocca R8 ([dettagli](evidence/M4/proposal-review.md)).

Il proprietario ha ascoltato la prova aggiornata con Assistente vocale e riferisce comprensibili famiglia, stato fiscale, coordinate, errore e conflitto con collegamento; percorso e limiti nella [checklist](evidence/M4/accessibility-checklist.md).

Il riesame indipendente conferma le prove del percorso vocale nei limiti dichiarati. La chiusura resta subordinata ai gate del piano: CI Ubuntu e Windows sul risultato finale e approvazione esplicita del proprietario sulla PR che tocca R8. Prima di pubblicare serve evitare l'esposizione di un percorso personale presente nella storia locale del ramo ([audit](evidence/M4/review.md)).

# Prova browser del recupero conflitto sulla versione `3ff4e28`: due schede sintetiche, rifiuto del modulo obsoleto e ritorno alla revisione aggiornata con Tab e Invio ([evidenza](evidence/M4/conflict-recovery-review.md)). Il riscontro dell'Assistente vocale sui controlli recenti resta necessario.

# Conflitti di revisione: i cinque percorsi che rifiutano un modulo obsoleto mostrano una pagina con titolo, lingua e collegamento diretto alla revisione aggiornata; la modifica non salvata è esplicitata. Revisione indipendente senza difetti concreti ([evidenza](evidence/M4/conflict-recovery-review.md)); suite completa 835 test e 365 sottocasi passati ([output](evidence/M4/conflict-recovery-suite.txt)). Il riscontro con Assistente vocale rimane in attesa.

# Correzioni accessibilità sul percorso custom: pagina di errore con lingua, titolo e nome del campo; campo revisionato con etichetta leggibile; rimosso modulo generico duplicato della famiglia. Revisione indipendente e prove in [evidenza](evidence/M4/accessibility-errors-review.md); suite completa 835 test e 360 sottocasi passati ([output](evidence/M4/accessibility-errors-suite.txt)). Rimane il riscontro vocale sulla versione corrente.

# Audit finale M4 in corso: revisione indipendente completata e rapporto per requisito in [review.md](evidence/M4/review.md). Sulla versione attuale sono stati provati nel browser famiglia e campo personalizzato, errore di formato e classificazione fiscale; resta da completare il riscontro dell'Assistente vocale sui controlli recenti. Nessuna dichiarazione di completamento finché la verifica non è conclusa.

#94: selezione della famiglia personalizzata supportata da proposta OCR, con snapshot validato e incluso nell'hash dell'evento; revisione indipendente senza difetti nel perimetro ([evidenza](evidence/M4/custom-family-review.md)). Suite sintetica completa: 835 test e 360 sottocasi passati ([output](evidence/M4/custom-family-review-suite.txt)). Resta l'audit indipendente finale dei criteri M4.

## Cronologia M4

Le annotazioni successive registrano lo stato al momento di ciascun passaggio; indicazioni di blocchi, attività aperte o modifiche non committate possono essere state superate dalle voci più recenti sopra.

#69 e #71: aggiunti campi standard mancanti e campi personalizzati dichiarati negli snapshot; anteprima prodotta per la pagina richiesta, controlli di tipo e recupero del modulo in caso di errore. Revisione indipendente e prova browser sintetica documentate in [evidenza](evidence/M4/missing-fields-review.md). Suite completa: 833 test e 358 sottocasi passati ([output](evidence/M4/missing-fields-suite.txt)); test mirati aggiornati 61 e 19 sottocasi ([output](evidence/M4/missing-fields-green.txt)). Resta aperta la selezione della famiglia personalizzata #94 e l'audit finale della milestone.

#71 parziale: il registro valida i candidati personalizzati usando versione e snapshot del documento; test mirati 47 passati e 19 sottocasi, revisione indipendente senza difetti nel perimetro ([evidenza](evidence/M4/custom-review-validation-review.md)). Suite sintetica completa: 832 test e 358 sottocasi passati ([output](evidence/M4/custom-review-validation-suite.txt)). Restano le funzioni aperte nell'audit, tra cui aggiunta dei campi mancanti e selezione di famiglie personalizzate.

#96: selezione di alternative originali osservate con evento e prove; revisione indipendente e limite legacy in [evidenza](evidence/M4/alternative-review.md). Suite Windows completa: 831 test e 358 sottocasi passati ([output](evidence/M4/alternative-final-suite.txt)). Altre voci dell’audit M4 restano aperte.

#103 verificata: avviso e conferma per revisione bloccata, bozza vincolata al contesto e gestione di concorrenza; revisione indipendente nel perimetro senza ulteriori difetti ([evidenza](evidence/M4/blocked-handoff-review.md)). Suite Windows finale: 827 test e 354 sottocasi passati ([output](evidence/M4/blocked-final-suite.txt)). Le altre voci dell’audit M4 restano aperte.

#103 ancora in corso: corretti i casi di bozza obsoleta, hash non ASCII e GET concorrente; 18 test e 5 sottocasi passati ([evidenza](evidence/M4/blocked-handoff-race-green.txt)). Il revisore ha segnalato che il calcolo del fingerprint sotto lock può ritardare annullamento: rifattorizzare con snapshot e controlli brevi, testare e far riesaminare prima del commit. Modifiche non committate.

In corso #103: avviso e conferma per revisione bloccata con fingerprint del contesto; la bozza richiede fingerprint corrente. Test sintetici mirati: 16 passati e 5 sottocasi ([evidenza](evidence/M4/blocked-handoff-green.txt)). Revisione indipendente ha individuato una corsa tra `/chatgpt/return` e `/clear`: da riprodurre e correggere prima di commit e suite completa. Modifiche non committate.

Controllo #95 verificato: moduli obsoleti ricevono 409; corse tra revisione, anteprima, archivio e sessione affrontate con test sintetici. Revisione indipendente senza ulteriori difetti nel perimetro ([evidenza](evidence/M4/review-conflict-review.md)); suite Windows completa 823 test e 354 sottocasi passati ([output](evidence/M4/review-final-suite-v4.txt)). Le altre voci dell’audit M4 restano aperte.

Controllo concorrente #95: dopo le correzioni successive, suite Windows con loopback autorizzato 823 passati e 354 sottocasi sul codice prima dell’ultima correzione snapshot ([evidenza](evidence/M4/review-final-suite-v3.txt)); ultima correzione snapshot preview verificata con 36 test e 4 sottocasi ([evidenza](evidence/M4/review-preview-snapshot-green.txt)). Riesame indipendente e suite completa sull’ultimo codice ancora necessari; modifiche non committate.

Revisione #95 ancora in corso: corretta la riapertura di archivio che poteva scartare revisioni non salvate ([test](evidence/M4/review-archive-aba-green.txt)). Il revisore ha individuato due problemi ancora aperti: body POST di revisione lento può bloccare annullamento; anteprima completata dopo rimozione del documento nella stessa sessione può restituire dati non più disponibili. Correggere con test prima di commit e suite completa; modifiche non committate.

Revisione concorrente #95: il riesame ha individuato il blocco su upload/anteprima lenti e la pubblicazione dopo chiusura della sessione; aggiunti test e correzioni, rispettivamente 9 test ([anteprima](evidence/M4/review-preview-green.txt)) e 37 test ([processor](evidence/M4/review-processor-green.txt)) passati. Restano da correggere e verificare le corse nei percorsi archivio open/delete, quindi rieseguire la suite e la revisione indipendente. Modifiche non committate.

Il proprietario ha richiesto di riprendere: eseguiti i test loopback fuori dalla sandbox, 8 passati ([evidenza](evidence/M4/loopback-authorized.txt)); suite completa prima del fix della corsa: 812 test e 354 sottocasi passati ([evidenza](evidence/M4/review-conflict-suite-authorized.txt)). Revisione indipendente ha individuato una corsa GET/POST; aggiunti test e lock, 32 test mirati e 4 sottocasi passati ([evidenza](evidence/M4/review-race-green.txt)). Riesame e suite finale in corso.

Suite M4 bloccata da permessi loopback: esecuzione completa Windows con 808 passati, 354 sottocasi passati e 4 fallimenti, inclusi errori socket `WinError 10013` e un test applicativo che richiede aggiornamento al token ([evidenza](evidence/M4/review-conflict-suite.txt)). Nessun nuovo tentativo per aggirare il problema esterno (GOAL V6). Serve una nuova osservazione discriminante o un ambiente dove la connessione loopback sia autorizzata. Il passo #95 è non committato e non è pronto; test mirati 38 passati e 4 sottocasi ([evidenza](evidence/M4/review-conflict-green.txt)).

In corso #95: aggiunto token della testa del registro nei moduli e rifiuto 409 per una revisione obsoleta; il nuovo test mirato passa ([evidenza](evidence/M4/review-conflict-green.txt)). Verifica regressioni incompleta: cinque test precedenti inviano moduli privi del nuovo token e falliscono; aggiornarli e verificare anche la concorrenza atomica prima di considerare completo il passo. Modifiche di codice e test non committate.

Revisore indipendente nuovamente disponibile: revisione del commit `0d20b89` conclusa senza difetti nel perimetro, 33 test e 4 sottocasi passati ([evidenza](evidence/M4/family-provenance-review.md)). Restano le funzioni dell’audit PR e la verifica finale della milestone.

Revisione indipendente finale bloccata: il revisore assegnato ha segnalato il raggiungimento del limite di utilizzo ed è terminato prima di completare la verifica della cronologia corretta. Non è stato ritentato o sostituito per aggirare il limite (GOAL V6). Serve disponibilità ripristinata del revisore o altra nuova osservazione che consenta una revisione indipendente autorizzata. Restano anche le funzioni elencate nell’audit PR M4; milestone non completata.

Corretto il rilievo sulla provenienza: la famiglia iniziale mostra prove non disponibili, senza attribuire automaticamente quelle di una proposta corrispondente. Test mirati: 33 passati e 4 sottocasi ([evidenza](evidence/M4/family-provenance-green.txt)).

Revisione indipendente della cronologia: individuata e corretta la famiglia iniziale mostrata come `None`; aggiunta regressione su due cambi e prove, 33 test e 4 sottocasi passati ([evidenza](evidence/M4/family-history-green.txt)).

Implementata la presentazione della cronologia di correzioni e decisioni fiscali con autore, momento, valori e prove precedenti/nuove; 33 test e 4 sottocasi passati ([evidenza](evidence/M4/review-history-green.txt)); revisione indipendente in corso.

Audit indipendente dei ref locali delle nove PR assegnate a M4: #75 coperta; altre funzioni risultano mancanti o parziali. Dettagli in [audit PR](evidence/M4/pr-scope-audit.md). La milestone resta in corso.

Il proprietario ha reso disponibile il desktop. Cattura ripresa con una pagina locale sintetica: tre schermate salvate e ispezionate da revisore indipendente; lista di ammissione immagini vincolata a percorso e hash (DEC-028). Eseguita la conclusione con tastiera, ripetuto il gesto mouse sulla versione corretta e documentati focus e contrasto nella [checklist](evidence/M4/accessibility-checklist.md). In corso verifica completa e audit finale; non è ancora dichiarata la chiusura.

M4 bloccata sulla cattura: durante la selezione dello screenshot la finestra in primo piano è cambiata e l’osservazione successiva ha mostrato contenuti estranei alla prova. Nessuna immagine è stata salvata. Per GOAL V6 non si ripete il tentativo senza una nuova osservazione discriminante. Se la selezione di cattura è ancora visibile, il proprietario può annullarla con Esc e comunicare quando il desktop è disponibile per una prova isolata.

Dopo le due correzioni della revisione indipendente la suite Windows completa riporta 806 test e 354 sottocasi passati ([evidenza](evidence/M4/windows-suite-current.txt)); la revisione dei due fix non ha rilevato regressioni. Restano screenshot sintetici, checklist completa e audit finale.

Il proprietario ha chiuso Strumento di cattura; l’inventario ha confermato la chiusura. Corrette le due regressioni segnalate dalla revisione indipendente: alternative originali visibili anche dopo correzione e successive correzioni di un campo manuale con riuso della regione. Test mirati: 31 passati e 4 sottocasi ([evidenza](evidence/M4/review-regressions-green.txt)).

Revisione indipendente: corretta la seconda modifica di un campo inizialmente assente; la regione verificata viene riutilizzata.

Revisione indipendente aggiuntiva: le alternative OCR sono ora mostrate dopo una correzione manuale; regressione verificata.

M4 temporaneamente bloccata: durante la predisposizione degli screenshot, l’azione per chiudere la finestra «Strumento di cattura» ha restituito «coordinate input geometry is unavailable». Per GOAL V6 non è stata ripetuta né aggirata. Serve una nuova osservazione discriminante, ad esempio la chiusura manuale della finestra da parte del proprietario. Non è stato salvato alcuno screenshot in questo tentativo.

Suite Windows dopo l’export CSV della riconciliazione: 804 test e 354 sottocasi passati ([evidenza](evidence/M4/windows-suite-after-csv.txt)). La lettura vocale del percorso da tastiera è stata confermata dal proprietario e la selezione con mouse è stata provata ([evidenza](evidence/M4/browser-walkthrough.md)). Restano screenshot, checklist completa di contrasto/accessibilità, revisione indipendente finale e bonifica della cronologia Git locale prima della pubblicazione.

M4 ripresa: il proprietario ha aperto Assistente vocale e l’inventario conferma che è in esecuzione. È stato percorso un ciclo sintetico da tastiera nel browser con Assistente vocale attivo; il proprietario ha confermato la lettura comprensibile dei controlli e del messaggio della regione durante il percorso sintetico. Nessuna impostazione Windows modificata. Dettagli precedenti: [prova browser](evidence/M4/browser-walkthrough.md).

Suite Windows con dipendenze approvate e hash-locked installate nella cartella del progetto: 802 test e 354 sottocasi passati ([evidenza](evidence/M4/windows-suite-green.txt)). Una regressione iniziale nella descrizione delle regioni umane è stata corretta ([test mirati](evidence/M4/human-region-green.txt)); il percorso di correzione sintetica da tastiera è stato eseguito nel browser. La prova del mouse nel browser è stata eseguita e il proprietario ha confermato la lettura vocale del percorso da tastiera ([evidenza](evidence/M4/browser-walkthrough.md)). Mancano screenshot, checklist completa di contrasto/accessibilità, audit dei requisiti e revisione indipendente finale. Non pubblicare il ramo: una versione precedente di un’evidenza contiene un percorso locale nella cronologia Git.

Il primo tentativo di commit M4 era fallito per identità Git assente. Su richiesta del proprietario, è stata impostata solo per questo repository l’identità già usata nei commit recenti; il lavoro può riprendere.

M4: progetto approvato dal proprietario; piano in `docs/superpowers/plans/2026-11-15-m4-revisione.md`. Identità locale negli eventi di revisione documento e cronologia CSV implementate; 29 test sintetici passati ([evidenza](evidence/M4/review-export-green.txt)). Anche gli eventi di riconciliazione registrano ora utente locale e UTC, con conservazione dei vecchi eventi e ripetizione idempotente; 77 test sintetici e controllo privacy passati ([evidenza](evidence/M4/reconciliation-green.txt)). I contratti sintetici esistenti di selezione con mouse e tastiera e presentazione degli stati passano (8 test; [evidenza](evidence/M4/review-ui-contracts.txt)). La cronologia delle revisioni della riconciliazione è ora esportabile anche in CSV, con autore, UTC e prove; test sintetici mirati: 77 passati ([evidenza](evidence/M4/case-csv-green.txt)). Restano percorso completo documentato con screenshot, checklist di contrasto/accessibilità e revisione indipendente. Revisione indipendente iniziale: individuati e corretti valore etichettato come verificato, alternative e coordinate mancanti, errori di identità non gestiti e validazione/compatibilità CSV; nuovo formato v3 (DEC-027). Verifica mirata: 89 test, incluso l’export di archivio e il controllo privacy ([evidenza](evidence/M4/review-fixes-green.txt)). La revisione finale resta aperta. Il ramo contiene un percorso locale nella cronologia di un commit non pubblicato: bonificare prima di qualsiasi pubblicazione.

Aggiornato: 2026-11-15.

## Per chi riprende il lavoro (2026-11-15)

Il proprietario sposta il progetto su un altro assistente. Stato al merge di M3:

- **Prossima milestone:** M4 Revisione (REQ-070, 072, 073, 075), non iniziata. Il suo piano dettagliato va scritto in `docs/superpowers/plans/` prima di cominciare (`docs/plan.md`). Da rifare in M4 le PR del gruppo C elencate in `docs/evidence/M1/pr-triage.md` (#69, #71, #75, #94–#98, #103).
- **Regole del progetto:** `GOAL.md` (vincoli V1–V9); decisioni in `docs/decisions.md` (DEC-001…026); il proprietario è responsabile di R7/R8 e approva ogni PR che tocca archivio ed esportazione; nessuna dipendenza fuori da `docs/dependencies-approved.md`; solo dati sintetici.
- **Metodo usato:** test scritto prima (deve fallire, poi passare); evidenze in `docs/evidence/Mx/` con i commit citati verificati; revisione indipendente prima di chiudere una milestone; merge solo con il sì del proprietario.
- **CI:** due controlli obbligatori su `main` («Taxonomy registry and binding» su Ubuntu, «Windows application contracts» su Windows); ogni modulo di test nuovo va elencato in entrambi i job (`application/tests/test_ci_workflow.py` lo verifica).
- **Misure locali con l'OCR vero** (da `application/`, con il venv del runtime approvato): `tools/run_case_benchmark.py` (fascicolo), `tools/run_field_benchmark.py` (campi), `tools/line_item_benchmark.py --measure` (righe di fattura). Le fixture le generano gli script stessi.
- **Problemi aperti noti:** fallimento intermittente non spiegato di un lavoro OCR di fascicolo (1 esecuzione su 4 in M2, da seguire in M7: ora lo script ne riporta il codice); giustificativo avanzato proposto a righe dello stesso giorno (DEC-023); sconti con meno finale ignorati; `revalidate()` pronta ma usata solo da M5.
- **Su Windows con Git Bash:** gli script Python incollati nel terminale possono perdere le barre rovesciate; scrivere gli script in file. I file del repository sono LF nell'indice e CRLF nella copia di lavoro.

## M3 — Classificazione ed estrazione

Tutti i compiti del piano M3 sono fatti e la revisione indipendente è chiusa: criteri ed evidenze in [`evidence/M3/acceptance.md`](evidence/M3/acceptance.md). M3 è completata: il proprietario ha approvato il merge della PR #148 il 2026-11-15. Criteri ed evidenze: [`evidence/M3/acceptance.md`](evidence/M3/acceptance.md).

Risultati principali:
- catalogo dei tipi caricato dall'app e modificabile da una pagina «Catalogo», con storico delle versioni;
- i quattro stati di GOAL con il motivo in revisione e nel CSV;
- proposta del nome dell'esercente;
- angolo di rotazione nel record;
- righe di fattura e tabelle, con la verifica «somma delle righe = totale»;
- regole di verifica con versione: i documenti già in revisione non cambiano.

Accuratezza sintetica (60 giustificativi): totale, data, valuta, numero e partita IVA 100%; esercente 90%; tutte le soglie fissate prima sono superate. Tre difetti dell'app trovati e corretti (valuta attaccata, server bloccato da connessioni inattive, modulo da pagina in sandbox).

Righe di fattura su 12 fatture sintetiche: 54/54 corrette, verifica della somma 12/12.

CI: Ubuntu 783 passati e 9 saltati con motivo; Windows 792 passati.

REQ-053 e REQ-064 inclusi in M3 su richiesta del proprietario.

## M2 — Motori e decodifica

Tutti i compiti del piano M2 sono fatti e la revisione indipendente è chiusa: criteri ed evidenze in [`evidence/M2/acceptance.md`](evidence/M2/acceptance.md). M2 è completata: PR #147 unita il 2026-11-15.

Risultati principali (dati sintetici):
- registro dei motori a manifest; un motore di prova aggiunto con soli file nuovi;
- anteprime in un worker isolato;
- testo incorporato dei PDF usato come produttore distinto;
- rotazioni di 90°, 180° e 270°;
- GIF a fotogramma singolo e BMP.

CI: Ubuntu 716 passati e 7 saltati con motivo; Windows 723 passati. Benchmark con il motore scelto dal registro: punteggi identici a M1. **Aperto:** 1 esecuzione su 4 fallita senza causa nota (seguito in M7).

## M1 — Ordine e verificabilità

M1 è completata: tutti i compiti del piano sono fatti, la revisione indipendente è chiusa e il proprietario ha approvato le decisioni aperte il 2026-11-15.

Criteri di accettazione ed evidenze:
- REQ-001…004: [`evidence/M1/acceptance.md`](evidence/M1/acceptance.md);
- rassegna delle PR: [`evidence/M1/pr-triage.md`](evidence/M1/pr-triage.md);
- tutti i test in CI: [`evidence/M1/2026-11-15-ci.md`](evidence/M1/2026-11-15-ci.md);
- benchmark rigenerabile: [`evidence/M1/2026-11-15-case-benchmark.md`](evidence/M1/2026-11-15-case-benchmark.md);
- revisione: [`evidence/M1/review.md`](evidence/M1/review.md);
- base di partenza: [`evidence/baseline/README.md`](evidence/baseline/README.md).

Il proprietario ha reso obbligatorio anche il controllo «Windows application contracts» nella protezione di `main` (verificato il 2026-11-15: i controlli richiesti sono «Taxonomy registry and binding» e «Windows application contracts»).

Limite registrato per M3: un giustificativo avanzato viene proposto come possibile conflitto alle righe dello stesso giorno.



Risultati principali (dati sintetici): tutti i 55 moduli di test in CI su Ubuntu (672 passati, 6 saltati con motivo) e Windows (678 passati); benchmark del fascicolo rigenerabile da script: 98/98 righe, 92/92 giustificativi giusti al primo posto (tutti come abbinamenti *possibili*), 3/3 conflitti, 40/40 date ambigue con suggerimento corretto, 0 connessioni esterne, 1,1–1,3 s per pagina.

## Fase 0 — Requisiti e piano

Approvata e unita in `main` (#145, 2026-11-15):
- [`requirements.md`](requirements.md): requisiti REQ-001…REQ-143 con criteri di accettazione;
- [`architecture.md`](architecture.md): architettura e punti di estensione;
- [`plan.md`](plan.md): milestone M1–M8 con requisiti, deliverable ed evidenze;
- [`superpowers/plans/2026-11-15-m1-ordine-e-verificabilita.md`](superpowers/plans/2026-11-15-m1-ordine-e-verificabilita.md): piano passo-passo di M1;
- [`dependencies-approved.md`](dependencies-approved.md) (approvate il 2026-11-15) e [`dependencies-request.md`](dependencies-request.md) (R-001 Python embeddable, R-002 NSIS: servono da M6);
- [`decisions.md`](decisions.md) (DEC-001…DEC-020), [`questions.md`](questions.md) (nessuna domanda aperta);
- [`evidence/README.md`](evidence/README.md).

Design approvato dal proprietario il 2026-11-15: [`superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](superpowers/specs/2026-11-15-ocr2-product-completion-design.md).

## Milestone

| Milestone | Stato |
|---|---|
| M1 Ordine e verificabilità | **completata** (2026-11-15) |
| M2 Motori e decodifica | **completata** (2026-11-15, #147) |
| M3 Classificazione ed estrazione | **completata** (2026-11-15, #148) |
| M4 Revisione | **completata** (2026-11-15, #149) |
| M5 Libreria | **completata** (2026-11-15, #150) |
| M6 Applicazione installabile | in corso |
| M7 Sicurezza e prestazioni | non iniziata |
| M8 Prova sul campo e collaudo | non iniziata |

Il prodotto **non** è completo. Il codice esistente è un prototipo (vedi `requirements.md`, colonna «Stato oggi»).

## Note su V1

Il vecchio progetto OCR non è stato letto per la Fase 0.
