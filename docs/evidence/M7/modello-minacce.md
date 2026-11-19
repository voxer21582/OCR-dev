# M7 — Modello delle minacce iniziale

Stato originale: **in corso**, revisione e firma del proprietario non ancora completate. **Aggiornamento 2026-11-19:** il proprietario ha firmato il 2026-11-18 la revisione di sicurezza che esamina questo modello ([revisione](revisione-sicurezza.md)); la riga «Log e diagnostica» è ora coperta dalla [checklist REQ-124](log-review.md#checklist-delle-uscite-2026-11-19). Il resto del documento conserva il testo iniziale. Ambito: applicazione M6 e relativi processi locali; documenti usati nelle prove esclusivamente sintetici.

| Bene o confine | Minaccia | Controlli e limiti da verificare |
|---|---|---|
| Documenti, archivio e risultati | Lettura o modifica da siti o processi non autorizzati | Server su loopback, controlli Host, Origin e token per le modifiche; questi controlli non isolano necessariamente un processo ostile dello stesso utente. |
| Importazione e anteprime | File costruiti per consumare risorse o compromettere il processo | Limiti di ingestione e decoder/worker isolati; provare limiti e annullamento sui percorsi effettivamente usati. |
| Comunicazioni | Trasmissione involontaria all'esterno da Python, librerie native, processi figli o browser | Il vecchio hook Python non osserva tutto il codice nativo né tutti i protocolli. Servono osservazioni complementari e limiti espliciti; zero eventi osservati non è prova assoluta di assenza di traffico. |
| Runtime e aggiornamenti | File alterati, manifest sostituito, installer non autentico | L'inventario rileva differenze rispetto al manifest corrente; non autentica modifiche congiunte ai file e al manifest. Firma del codice rinviata per DEC-034. |
| Log e diagnostica | Testo del documento, identificativi o percorsi registrati o condivisi | REQ-124 richiede log privi di contenuti sensibili. DEC-035 dispone la protezione delle nuove voci e la conservazione provvisoria dei registri precedenti; la revisione complessiva resta aperta. |
| Disponibilità | Carichi grandi, blocchi, riavvio o ripetizione del lavoro | Misurare tempi, memoria, avanzamento e recupero sul prodotto installato con il benchmark riproducibile. |

## Riscontri iniziali

- Revisione indipendente statica: presenti controlli su loopback, Host, Origin e token, oltre a limiti su importazione e decoder; non è stata dimostrata assenza di traffico nativo né una protezione contro un processo ostile dello stesso utente.
- Prova isolata del registro di avvio: passando esplicitamente un messaggio d'eccezione e un identificativo **sintetici**, entrambi sono comparsi nel file di log. La prova dimostra cosa può essere scritto dalla funzione, non che un documento reale sia stato registrato. Il requisito REQ-124 non è superato.
- I dettagli del registro di avvio furono approvati dal proprietario in M6 ([revisione M6](../M6/review.md)); per M7 il proprietario ha scelto di proteggere le nuove voci e conservare per ora i vecchi registri (DEC-035). I file precedenti possono quindi ancora contenere dati sensibili. Nessun dato reale è stato usato nella prova.

Restano da verificare il prodotto installato, la copertura delle osservazioni di rete e il rapporto finale indipendente; nessun requisito M7 è dichiarato completato da questo documento.
