# OCR2 — Obiettivo di prodotto per Claude Code

> Questo file è la fonte di verità dell'obiettivo. Rileggilo all'inizio di ogni giro.
> Lo stato del lavoro vive in `docs/STATUS.md`, non nella tua memoria della conversazione.

## 1. Obiettivo

Realizzare **OCR2**, applicazione Windows completa di Document Intelligence (prodotto, non prototipo).

Capacità richieste:

1. **Importazione**: PDF, PNG, JPEG, WebP, TIFF multipagina; altri formati solo dopo valutazione documentata.
2. **OCR per pagina con provenienza**: ogni testo riconosciuto è legato a documento, pagina, area (bounding box), motore, versione del motore, confidenza.
3. **Architettura multi-motore**: interfaccia di motore OCR intercambiabile; aggiungere un motore non richiede modifiche al resto del sistema.
4. **Classificazione configurabile** dei documenti (tipi e regole definibili dall'utente/configurazione, non nel codice).
5. **Estrazione strutturata di campi** con evidenze (dove nel documento) e alternative candidate.
6. **Validazione, incertezza, valori mancanti**: ogni campo ha stato esplicito (valido / incerto / mancante / non valido) e motivazione.
7. **Revisione e correzione manuale** con traccia delle modifiche (valore originale, valore corretto, chi/quando).
8. **Persistenza**: salvataggio, riapertura, ricerca, gestione (rinomina, elimina, organizza), esportazione (almeno JSON e CSV; altri formati da valutare).
9. **Requisiti non funzionali verificabili**: sicurezza, prestazioni, installazione, aggiornamento. "Verificabile" = esiste un test, uno script o una procedura riproducibile con esito registrato.

## 2. Vincoli (non negoziabili)

- **V1** Non copiare dati, codice o configurazioni dal vecchio progetto OCR. Puoi leggerlo solo se esplicitamente necessario per capire i requisiti, e annotarlo in `docs/STATUS.md`.
- **V2** In CI e nei test automatici usare **solo fixture sintetiche** generate da script nel repository. Nessun documento reale.
- **V3** **Non installare dipendenze, pacchetti, runtime o modelli** che non siano elencati in `docs/dependencies-approved.md`. Se ne serve uno nuovo: aggiungilo a `docs/dependencies-request.md` (nome, versione, licenza, dimensione, motivo, alternative) e fermati (vedi §5).
- **V4** Non modificare impostazioni, registro, servizi o file di sistema di Windows. Non modificare deployment o risorse Google.
- **V5** Rispettare le regole **R7** e **R8** come definite nella documentazione di progetto. Se non le trovi o sono ambigue: fermati e chiedi.
- **V6** **Diagnosi e tentativi reversibili**: se un'operazione fallisce per cause esterne, registra il problema, diagnosticalo e puoi riprovare in modo ragionato e reversibile. Non aggirare limitazioni di sicurezza o autorizzazioni, non modificare Windows (V4), e fermati quando è indispensabile un intervento esterno o una decisione del proprietario. Modifica autorizzata dal proprietario il 2026-11-16.
- **V7** Preservare i checkout concorrenti: lavora solo nella tua cartella/worktree e sul tuo branch. Mai `git reset --hard`, `git clean`, `push --force`, né modifiche a file fuori dal progetto.
- **V8** Non dichiarare nulla "completato" senza evidenze (output di test, log, screenshot, report) salvate in `docs/evidence/`.
- **V9** Prototipo ≠ prodotto. Una milestone completata non significa prodotto completato. Il prodotto è completo solo quando **tutte** le milestone in `docs/plan.md` sono verificate.

## 3. Decisioni

- Per aspetti non specificati scegli opzioni **reversibili** e annotale in `docs/decisions.md` (decisione, alternative, come tornare indietro).
- Chiedi una decisione all'utente **solo** quando cambia sostanzialmente lo scopo, il costo, la licenza o un vincolo. In quel caso scrivi la domanda in `docs/questions.md` con 2–3 opzioni e una raccomandazione, poi fermati.

## 4. Fasi

### Fase 0 — Requisiti e piano (nessun codice di prodotto)
Produci:
- `docs/requirements.md`: requisiti dettagliati e numerati (REQ-xxx) ricavati da questo file e dalla documentazione esistente, ciascuno con criterio di accettazione verificabile.
- `docs/architecture.md`: architettura proposta, con punti di estensione (motori, classificatori, esportatori).
- `docs/plan.md`: milestone ordinate (M1, M2, …), ciascuna con: requisiti coperti, deliverable, test/evidenze che la dichiarano finita.
- `docs/dependencies-request.md`: dipendenze e modelli proposti, in attesa di approvazione.
- `docs/decisions.md`, `docs/questions.md`.
Poi fermati: la Fase 0 richiede approvazione umana.

### Fasi M1…Mn — Esecuzione per milestone
Lavora **una milestone alla volta**, quella indicata nel comando di avvio. Per ogni giro:
1. Leggi `GOAL.md`, `docs/STATUS.md`, `docs/plan.md`.
2. Scegli il prossimo passo più piccolo e utile della milestone.
3. Scrivi prima il test, poi il codice (TDD).
4. Esegui i test; salva l'output rilevante in `docs/evidence/<milestone>/`.
5. Fai un commit piccolo con messaggio chiaro.
6. Aggiorna `docs/STATUS.md`.

Prima di dichiarare finita una milestone: fai eseguire una revisione indipendente del codice (agente revisore o skill di code review), correggi i problemi rilevanti, riesegui tutti i test.

## 5. Come fermarsi

Il ciclo termina solo scrivendo `<promise>STOP</promise>`, e **solo dopo** aver aggiornato `docs/STATUS.md` con uno di questi stati in cima:

- `STATO: MILESTONE COMPLETATA — Mx` + elenco dei criteri di accettazione con link alle evidenze.
- `STATO: IN ATTESA DI APPROVAZIONE` (fine Fase 0, o nuove dipendenze in `dependencies-request.md`).
- `STATO: DOMANDA APERTA` (vedi `docs/questions.md`).
- `STATO: BLOCCATO` + causa, cosa è stato tentato, cosa serve per sbloccare.

Non scrivere `<promise>STOP</promise>` in nessun altro caso.
