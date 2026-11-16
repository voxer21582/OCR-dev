# Domande per il proprietario

Si aggiunge una domanda solo quando cambia scopo, costo, licenza o un vincolo (GOAL §3). Ogni domanda ha 2–3 opzioni e una raccomandazione; quando è aperta, `STATUS.md` riporta `STATO: DOMANDA APERTA`.

## Aperte

Nessuna. (Le domande della Fase 0 sono state risolte il 2026-11-15: vedi DEC-001…DEC-009 in `decisions.md`.)

## Risolte e già previste

Q-001 e Q-003 sono risolte il 2026-11-15 (DEC-030 e DEC-031: scelta (a) per entrambe). Q-004 è risolta il 2026-11-16 (DEC-034: nessun certificato, REQ-105 rinviato come limite dichiarato). Le altre restano previste per più avanti.

| ID | Quando | Domanda | Opzioni | Raccomandazione |
|---|---|---|---|---|
| Q-001 (risolta, DEC-030) | M6 | Il file FFmpeg (LGPL) dentro OpenCV va nell'installer? | (a) Escluderlo dopo aver verificato che l'OCR funziona senza; (b) includerlo rispettando gli obblighi LGPL | (a) |
| Q-002 | M8, prima della prova | Soglie minime per la prova sul campo (es. importo totale corretto, data corretta, giustificativo giusto al primo posto). | Proposta numerica da preparare in M8 sulla base dei risultati sintetici di M3 | — |
| Q-003 (risolta, DEC-031) | Prima di M6 | Serve un backup portabile (su un altro PC o un altro utente Windows)? Oggi il backup si ripristina solo con lo stesso utente (DEC-029). | (a) No, va bene così; (b) backup protetto da una password scelta dall'utente: richiede un nuovo componente di cifratura da approvare | (a) per ora; (b) se si vuole cambiare PC senza migrare il profilo Windows |
| Q-004 (risolta, DEC-034) | M6 | Quale certificato di firma del codice usa il proprietario per installer e binari (REQ-105)? | (a) Certificato commerciale o di un'organizzazione, con marca temporale; (b) nessun certificato: rilascio non firmato con SmartScreen all'installazione, REQ-105 rinviato; un certificato autofirmato richiederebbe di modificare l'archivio certificati del PC di destinazione (vietato da V4) | (a) se disponibile; il proprietario ha scelto (b) il 2026-11-16 |
