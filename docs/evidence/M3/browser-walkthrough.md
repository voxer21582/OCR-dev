# M3 — Percorso nel browser dell'editor del catalogo (2026-11-15)

**Requisiti:** REQ-045, REQ-041. **Livello:** `LOCAL-RUN`, browser integrato dell'app desktop Claude, nessun test driver installato. App avviata dal launcher con `LOCALAPPDATA` temporaneo (mai l'archivio dell'utente); nell'ultimo giro OCR spento.

## Passi e risultati (commit `13295d6`)

1. Pagina iniziale → link «Catalogo dei tipi di documento» → `/catalog`. La pagina mostra:
   - «Nessun tipo personalizzato»;
   - il modulo «Aggiungi un tipo» con tre campi etichettati;
   - i comandi per importare ed esportare.
2. Compilato il modulo:
   - nome «Ricevuta taxi»;
   - parole chiave «RICEVUTA TAXI, TAXI RECEIPT»;
   - campo «Partenza: Partenza, Da [testo]».

   Inviato con il pulsante. Risultato: «Tipo «Ricevuta taxi» aggiunto.»; il tipo è elencato con le parole chiave e il campo; viene mostrata l'impronta del catalogo; il file `family-catalog.json` è creato.
3. Inviato di nuovo lo stesso nome. Risultato: HTTP 400 con «Esiste già un tipo con questo nome: scegline un altro.»; catalogo invariato (stessa impronta).
4. `GET /catalog/export`: risposta 200, `Content-Disposition: attachment; filename="ocr2-catalogo-tipi.json"`, con il tipo `custom_ricevuta_taxi`.

## Due difetti trovati durante il percorso e corretti

1. **Server bloccato da una connessione inattiva** (commit `4390ed4`, test `test_server_idle_connection`).
   - Il server gestisce una connessione alla volta e aspettava senza limite una connessione di riserva aperta dal browser.
   - Da quel momento ogni richiesta successiva restava appesa: è stato riprodotto con un socket vuoto.
   - Ora ogni connessione ha un tempo massimo di inattività di 2 s.
   - Il difetto riguardava tutta l'app, non solo il catalogo.
2. **Modulo del catalogo bloccato quando inviato dalla pagina** (commit `13295d6`, test `OpaqueOriginFormTests`).
   - Le pagine hanno una CSP «sandbox», quindi il browser invia i moduli con `Origin: null`.
   - Il controllo CSRF legge il corpo prima della rotta, e la rotta lo rileggeva dal flusso vuoto.
   - Ora la rotta usa il lettore comune, che riusa i valori già letti.
   - I test con dati in memoria non lo vedevano, perché lì una seconda lettura restituisce subito vuoto.

## Limiti

- Il caricamento di un documento dal selettore di file non è automatizzabile nel browser integrato. Le prove che un tipo definito solo nel catalogo viene proposto e che gli stati dei campi compaiono nella pagina sono test automatici: `CatalogRuleTests` e `test_field_status_presentation`.
- Nessuna verifica con screen reader (REV-5, M4).
- I clic con il mouse nel pannello nascosto a volte non sono stati possibili. In quei casi i campi sono stati compilati con `form_input` e il secondo invio è stato fatto con `requestSubmit()`.
