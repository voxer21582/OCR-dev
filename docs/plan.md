# OCR2 — Piano a milestone

Fonte: [`GOAL.md`](../GOAL.md), [`requirements.md`](requirements.md), design approvato il 2026-11-15 ([`superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](superpowers/specs/2026-11-15-ocr2-product-completion-design.md)).

**Il prodotto è completo solo quando M1–M8 sono tutte verificate** (GOAL V9). Una milestone è chiusa solo quando:
1. ogni criterio dei suoi requisiti MUST è soddisfatto con evidenza in `docs/evidence/Mx/`;
2. tutti i test passano in CI (Ubuntu e Windows);
3. un revisore indipendente ha controllato il lavoro e i problemi rilevanti sono corretti (`docs/evidence/Mx/review.md`);
4. `docs/STATUS.md` riporta `STATO: MILESTONE COMPLETATA — Mx`;
5. le PR che toccano R7/R8 hanno l'approvazione esplicita del proprietario (DEC-001).

Ogni milestone ha un proprio piano passo-passo in `docs/superpowers/plans/`, scritto all'inizio della milestone. Quello di M1 è già pronto: [`2026-11-15-m1-ordine-e-verificabilita.md`](superpowers/plans/2026-11-15-m1-ordine-e-verificabilita.md).

## Base di partenza (già fatta, non accettata)

Le vecchie M1 e M2 (PR #138–#143 su `main`; #144 in bozza) hanno prodotto il prototipo attuale: importazione dei cinque formati, worker OCR isolato con RapidOCR, proposte di campi con evidenza, fascicoli con 100 allegati, riconciliazione, revisione con storia, archivio cifrato. Le loro evidenze sono nei commenti delle PR e delle issue: M1 le riporta in `docs/evidence/baseline/`.

## M1 — Ordine e verificabilità

**Perché:** prima di aggiungere funzioni, tutto ciò che esiste deve essere provabile secondo le regole di GOAL.
**Requisiti:** REQ-001…004, REQ-010, 011, 013, 015, 024, 029, 062 (benchmark), 074, 076, 109, 120, 123.
**Deliverable:**
- rassegna delle PR aperte con una raccomandazione per ciascuna; decisione del proprietario; #144 unita o chiusa;
- `docs/evidence/baseline/` con le evidenze esistenti (solo dati sintetici);
- generatore nel repository delle fixture del benchmark del fascicolo (1 nota + 100 giustificativi) e script che esegue il benchmark e confronta con le risposte note;
- tutti i moduli di test in CI su Ubuntu; job Windows per archivio DPAPI e launcher.
**Evidenze:** `docs/evidence/M1/pr-triage.md`; esecuzione CI con l'elenco completo dei moduli e nessun salto non spiegato; due generazioni con impronta identica; report del benchmark (numeri) dal PC di sviluppo; revisione.

## M2 — Motori e decodifica

**Perché:** GOAL §1.3 (aggiungere un motore senza toccare il resto) e la sicurezza delle anteprime.
**Requisiti:** REQ-014, 020, 021, 022, 023, 025, 027, 028, 030.
**Deliverable:** registro dei motori a manifest verificato nel worker; launcher guidato dal registro; motore di prova aggiunto con soli file nuovi; testo incorporato dei PDF come produttore distinto; rotazioni; anteprime in un worker isolato; GIF a fotogramma singolo e BMP.
**Evidenze:** diff della PR del motore di prova (solo file nuovi); test di impronta errata; test anteprima con PDF malformato; fixture ruotate e PDF con testo; revisione.

## M3 — Classificazione ed estrazione

**Perché:** GOAL §1.4–1.6.
**Requisiti:** REQ-026 (sintetico), 041, 042, 045, 051, 052, 053, 055, 057, 060, 064.
**Deliverable:** catalogo collegato a interfaccia e archivio; regole di classificazione nel catalogo; editor del catalogo; nome dell'esercente; righe di fattura (SHOULD); i quattro stati di GOAL con motivazione in UI ed export; soglie di accuratezza sintetiche registrate e misurate.
**Evidenze:** giro completo del catalogo nel browser; fixture a risposta nota per campo; report di accuratezza sintetica contro soglie; revisione.

## M4 — Revisione

**Perché:** GOAL §1.7 e accessibilità.
**Requisiti:** REQ-070, 072, 073, 075.
**Deliverable:** «chi» e «quando» in ogni evento ed export; percorso completo da tastiera e mouse; checklist di accessibilità con l'Assistente vocale di Windows.
**Evidenze:** percorso registrato nel browser (passi e screenshot sintetici); checklist compilata; test sugli eventi; revisione.

## M5 — Libreria (R7/R8, approvazione del proprietario)

**Perché:** GOAL §1.8.
**Requisiti:** REQ-012, 080…090, 122.
**Deliverable:** rinomina; etichette; filtri di ricerca; export JSON e CSV dall'interfaccia; export della riconciliazione con andata e ritorno; registro degli esportatori; backup e ripristino; migrazione tra versioni dello schema; ripresa dopo interruzione (issue #8).
**Evidenze:** prove con dati sintetici di interruzione, migrazione e backup/ripristino (impronte identiche); esportatore di prova con soli file nuovi; approvazione del proprietario sulle PR; revisione.

## M6 — Applicazione installabile

**Perché:** GOAL §1.9 (installazione e aggiornamento) e «applicazione Windows».
**Requisiti:** REQ-100…107.
**Prerequisiti:** approvazione di R-001 (Python embeddable) e R-002 (NSIS); risposta a Q-001 (FFmpeg); disponibilità dell'altro PC.
**Deliverable:** finestra Edge in modalità app; «Esci» e spegnimento automatico; installer per utente con runtime verificato; aggiornamento, ritorno indietro, disinstallazione; SBOM e notice; passo di firma del proprietario documentato.
**Evidenze:** matrice del ciclo di vita eseguita sull'altro PC; elenco dei file e voci per utente creati; firma verificata; revisione.

## M7 — Sicurezza e prestazioni

**Requisiti:** REQ-108, 121, 124, 125, 127…130.
**Deliverable:** modello delle minacce; revisione di sicurezza indipendente automatica e firma del proprietario; prova di assenza di traffico in uscita durante un fascicolo completo; revisione dei log; misure di prestazione sul benchmark rigenerabile; pacchetto diagnostico (SHOULD).
**Evidenze:** documento firmato; registro delle connessioni con limiti dichiarati; tabella delle misure contro i budget; revisione.

## M8 — Prova sul campo e collaudo

**Requisiti:** REQ-026 (reale), 140…143.
**Deliverable:** protocollo, soglie (Q-002) e foglio delle risposte giuste approvati; script di punteggio che stampa solo numeri (testato su dati sintetici); prova su 30–50 documenti veri eseguita dal costruttore sul PC del proprietario; al massimo una ripetizione su un campione nuovo (DEC-006); collaudo Windows firmato.
**Evidenze:** solo numeri riassuntivi in `docs/evidence/M8/`; firma del proprietario.

## Ordine e dipendenze

M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8. M2, M3 e M4 toccano parti diverse e possono sovrapporsi se il proprietario lo chiede; M5 deve precedere M6 (l'installer deve conservare l'archivio); M7 misura il prodotto installato; M8 è sempre l'ultima.
