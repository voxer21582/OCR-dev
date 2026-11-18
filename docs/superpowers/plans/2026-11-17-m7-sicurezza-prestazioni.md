# M7 — Sicurezza e prestazioni

Obiettivo: verificare il prodotto M6 installato con dati sintetici, documentando separatamente limiti e criteri non dimostrati. Il punto di partenza è `main` dopo la PR #152; M6 è stata accettata con i limiti riportati in `docs/evidence/M6/acceptance.md` e DEC-034.

1. Redigere il modello delle minacce e sottoporre codice ed evidenze a revisione indipendente (REQ-125, DEC-008). Registrare i rilievi e correggere quelli autorizzati, con test preventivi.
2. Verificare i log con marcatori esclusivamente sintetici (REQ-124), conciliando i requisiti M7 con la precedente scelta del proprietario sui dettagli di avvio. Non acquisire né pubblicare log reali.
3. Ricostruire il prodotto usando soltanto gli archivi approvati e le impronte previste; provare un fascicolo sintetico completo con osservazione locale delle connessioni e dichiarare ciò che ogni metodo non osserva (REQ-121).
4. Misurare elaborazione, ripresa, memoria e latenza sul benchmark rigenerabile e sul prodotto installato; registrare ambiente, metodo, campione e confronto con le soglie, senza trattare stime aggregate come mediane o percentili (REQ-127–130).
5. Valutare il pacchetto diagnostico senza contenuti (REQ-108), applicare TDD e verificare che non raccolga dati personali se realizzato.
6. Rieseguire i controlli pertinenti, aggiornare evidenze e stato, richiedere la firma del proprietario prevista da DEC-008 e confrontare ogni requisito con le evidenze. Non dichiarare completata M7 finché mancano prove, revisione o firma richieste.

## REQ-108: scelta per l'esportazione diagnostica

Esportazione esplicitamente avviata dall'utente dalla pagina Informazioni, come JSON scaricabile. Solo versione applicativa e Python validate come versioni numeriche brevi e stati OCR/runtime ricondotti a valori chiusi. Non leggere né includere registri, percorsi, nomi, documenti, hash di documenti, contenuti, identificativi di sessione o dati dell'archivio; non effettuare connessioni. Valori non riconosciuti diventano `unknown`. Testare download, metodo HTTP, intestazioni e assenza di marcatori sintetici. Il file non sostituisce una diagnosi completa degli errori nativi.
