# M4 — Progetto della revisione

## Obiettivo e criteri

Completare REQ-070, REQ-072, REQ-073 e REQ-075: mostrare origine, area, alternative e motivi; registrare utente Windows e momento UTC degli eventi e riportarli negli export; consentire selezione delle aree con mouse e tastiera; verificare etichette, focus, contrasto e Assistente vocale. Gli esempi e le prove automatiche usano esclusivamente dati sintetici.

## Approccio

Si estendono i componenti esistenti: `review_ledger.py` conserva la storia verificabile, `local_intake_app.py` gestisce i percorsi di revisione e `document_export.py` produce gli export. Le registrazioni già esistenti non vengono alterate né attribuite retroattivamente a un utente inventato. Le variazioni a export e archivio sono soggette a DEC-001: la PR le dichiara e il proprietario le approva prima del merge. Le PR del gruppo C sono riferimenti da riesaminare, non modifiche da applicare automaticamente.

Alternativa: introdurre un nuovo registro parallelo. Richiederebbe riconciliazione e migrazione di due storie: si preferisce estendere il registro corrente. L'identità Windows viene ricavata sul server, non accettata dal browser; errori di identificazione non devono produrre identità inventate. I timestamp nuovi sono UTC. I dati storici rimangono leggibili con le loro attribuzioni originali.

## Sequenza e verifica

1. Inventariare i percorsi di revisione, gli eventi e gli export, e confrontare le PR M4 con la base attuale.
2. Aggiungere test sintetici fallenti per autore, UTC, cronologia e compatibilità; attuare la soluzione minima e verificare JSON/CSV, senza modificare gli hash degli eventi storici.
3. Verificare e completare il percorso di revisione e selezione delle aree con mouse e tastiera, con test DOM e regressioni.
4. Registrare il percorso nel browser con screenshot sintetici; compilare la checklist con Assistente vocale Windows, etichette, focus e contrasto. Riportare qualsiasi verifica non eseguibile come aperta.
5. Aggiornare i selettori CI, registrare evidenze, richiedere revisione indipendente e ripetere le verifiche pertinenti. La milestone si chiude solo con tutti i criteri dimostrati.

Non si installano dipendenze, non si usano documenti reali, non si modificano configurazioni Windows e non si ripetono operazioni bloccate senza una nuova osservazione discriminante. Le modifiche sono su un ramo dedicato; nessun merge senza il consenso del proprietario.
