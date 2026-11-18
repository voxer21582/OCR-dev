# M7 — Valutazione della cache di validazione autenticata

Stato: **sperimentale, non approvata per il prodotto**. Obiettivo: valutare se ridurre il costo della lista senza saltare l'autenticazione DPAPI o trattenere documenti decifrati. Le prove attuali su copia strumentata non dimostrano sicurezza né stabilità della p95.

1. Definire le garanzie rispetto al percorso corrente: ogni lettura autentica binding e record; la chiave usa i medesimi plaintext autenticati con framing non ambiguo e contesto completo; cardinalità, riferimenti e totali sono sempre ricontrollati. In caso di dubbio, usare il percorso originale.
2. Separare, con test preventivi di equivalenza, autenticazione DPAPI e validazione del plaintext affinché un miss validi esattamente i byte usati per il confronto. Non introdurre una seconda decifratura sul miss.
3. Progettare cache limitata a esiti numerici e booleani e identificatori HMAC con chiave casuale in RAM; nessun testo, percorso, documento o identificatore in chiaro. Documentare che gli HMAC sono pseudonimi e che Python non garantisce azzeramento della memoria.
4. Definire pubblicazione solo dopo verifica completa, scadenza/invalidation e gestione di letture in volo durante cancellazione, restore e rollback, incluse istanze/processi diversi. Non presupporre che un lock in memoria coordini processi distinti.
5. Coprire fallimenti DPAPI dopo riscaldamento per entrambi i payload, byte variabili, manomissioni, modifiche di manifest, indici e limiti, errori aggregati, cap LRU, gate, concorrenza WAL/DELETE, cancellazione, restore, rollback e protector personalizzati. Includere DPAPI Windows reale e revisione indipendente.
6. Solo dopo sicurezza e test, ricostruire offline e confrontare prodotto installato e copia strumentata in prove sintetiche indipendenti, registrando campioni, memoria e limiti. Scartare la soluzione se non raggiunge un miglioramento stabile o se la sua equivalenza non è dimostrata.

La proposta non sostituisce l'approvazione esplicita R7 del proprietario, né la verifica della p95 e della revisione di sicurezza richiesta per chiudere M7.
