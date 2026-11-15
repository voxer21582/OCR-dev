# M4 — recupero dopo conflitto di revisione

Il 2026-11-15 è stato rilevato che la risposta a un modulo obsoleto suggeriva di ricaricare la pagina risultante dal POST, con possibile nuovo invio del modulo superato. I cinque percorsi interessati restituiscono ora una pagina italiana con titolo, messaggio che precisa che la modifica non è stata salvata e collegamento alla revisione aggiornata.

Un revisore indipendente ha verificato codifica del collegamento, assenza di mutazioni e identificabilità della pagina, senza rilevare difetti concreti; 37 test e 9 sottocasi passati. I test mirati locali sono in `conflict-recovery-green.txt`, la suite completa in `conflict-recovery-suite.txt`. La lettura vocale della nuova pagina non è ancora stata verificata.

Prova browser sulla versione `3ff4e28`, con documento sintetico e due schede: dopo il salvataggio nella prima, l'invio della seconda ha prodotto il messaggio di conflitto con titolo «Revisione aggiornata» e avviso che la modifica non era stata salvata. Tab ha raggiunto il collegamento di recupero e Invio ha aperto la revisione con il valore salvato dalla prima scheda. In una successiva prova del 2026-11-15 il proprietario ha riferito comprensibile la lettura del conflitto e del collegamento con Assistente vocale; percorso e limiti in `accessibility-checklist.md`.
