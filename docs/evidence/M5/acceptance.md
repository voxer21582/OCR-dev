# M5 — Accettazione: criteri ed evidenze

Commit di riferimento: `75ce91d` (branch `claude/m5-libreria`). La suite locale ha dato 881 test passati, 1 saltato e 398 sottocasi ([output](suite-75ce91d.md)).

Livelli di prova:
- **`SYN-CI`**: test sintetici in CI su Ubuntu e Windows;
- **`LOCAL-RUN`**: prova sul PC di sviluppo con dati sintetici e la vera DPAPI ([`browser-walkthrough.md`](browser-walkthrough.md)).

| Requisito | Criterio | Esito | Evidenza |
|---|---|---|---|
| REQ-081 | Ricerca per testo, tipo, data, stato ed etichetta; risultati limitati e a pagine | `SYN-CI` + `LOCAL-RUN` | `FilteredSearchTests` (filtri combinati, pagine, date, filtri non validi); `test_library_ui` (pagine da 25, filtri che restano tra le pagine, pagina oltre la fine); percorso nel browser |
| REQ-082 | I fascicoli si salvano e riprendono | `SYN-CI` | `ResumeAfterReopenTests`: dopo un errore e la riapertura dell'archivio, l'elaborazione riprende dal cursore e rielabora solo il gruppo non finito; restano validi i test di ripresa di M2 |
| REQ-083 | Rinomina di documenti e fascicoli: il nome cambia, identità e storia no, l'evento è registrato | `SYN-CI` + `LOCAL-RUN` (documenti) | `RenameAndTagTests` e `CaseLabelTests`: il record e il fascicolo restano identici; l'evento registra l'utente Windows e l'ora UTC; il nome è cifrato. Rinomina dalla pagina Archivio e dalla pagina Fascicoli (`test_library_ui`) |
| REQ-084 | Etichette: aggiungi, togli, filtra | `SYN-CI` + `LOCAL-RUN` | `RenameAndTagTests` (deduplicate, limiti), `FilteredSearchTests`, `test_library_ui`; percorso nel browser |
| REQ-085 | Eliminazione di record e sorgenti, con limiti documentati | `SYN-CI` | `test_deletion_traces`: dopo l'eliminazione, nel file non resta alcun frammento dei dati cifrati di record, sorgente e metadati; il test fallisce se `secure_delete` è spento. Eliminando un fascicolo vengono tolti anche i metadati dei suoi documenti. Limiti in [`deletion-limits.md`](../../product/deletion-limits.md) |
| REQ-086 | Backup, cancellazione, ripristino: contenuto identico (impronte) | `SYN-CI` + `LOCAL-RUN` | `test_archive_backup` (impronte identiche; rifiuto di copie troncate, di altri utenti e di cartelle già usate; nessuna copia precedente sovrascritta; ritorno all'archivio precedente se lo scambio fallisce); ZIP dalla pagina (`test_library_ui`); prova con la vera DPAPI |
| REQ-087 | Migrazione dello schema, integrità, scritture interrotte | `SYN-CI` | `SchemaV4MigrationTests` (da v3 a v4 senza modifiche; una migrazione interrotta lascia la v3 usabile). `InterruptedWriteTests`: guasto simulato a ogni scrittura e al commit di `save`, `append_case_chunk` e `commit_case_processing_chunk`, 11 casi; dopo ogni guasto l'archivio si riapre identico e l'operazione ripetuta riesce |
| REQ-088 | Export JSON e CSV di un record, su azione esplicita, dall'interfaccia | `SYN-CI` + `LOCAL-RUN` | I link della pagina Archivio vengono dal registro (`test_library_ui`); i byte prodotti sono gli stessi di prima (`test_export_by_suffix_matches_the_existing_serializers`) e i test di export di M4 restano invariati |
| REQ-089 | Export della riconciliazione con suggerimenti, decisioni ed evidenze separati; reimportabile | `SYN-CI` | `test_case_export_reader`: il file si rilegge senza perdite; vengono rifiutati otto tipi di modifica (importo, stato senza decisione, nota, decisione tolta, suggerimento verso un altro allegato, impronta dell'allegato, versione, campo in più). **Limite:** le impronte non sono a chiave, quindi una falsificazione voluta con impronte ricalcolate non viene rilevata ([`review.md`](review.md), punto 3) |
| REQ-090 | Esportatori dietro un'interfaccia comune; un formato nuovo con soli file nuovi | `SYN-CI` | `test_exporter_registry`, `test_synthetic_exporter`; il formato di prova è stato aggiunto con due soli file nuovi ([`exporter-new-files.txt`](exporter-new-files.txt)) |
| REQ-122 | Archivio cifrato per utente; sessioni che scadono e si cancellano | `SYN-CI` | Nome, etichette e backup cifrati (`test_metadata_is_encrypted_on_disk`, `test_backup_files_are_encrypted_and_described`); scadenza e cancellazione della sessione già coperte da `test_in_memory_session_expires_after_idle_timeout` e `test_clear_releases_volatile_session_and_returns_to_upload_form` |

**Decisioni:** DEC-029 (backup legato all'utente Windows). Domanda Q-003 (backup portabile) da porre prima di M6.

**Limiti dichiarati:**
- Il ripristino dalla pagina accetta file fino a 100 MB.
- Il rifiuto del backup di un altro utente è provato solo con il protettore sintetico.
- Nel browser, filtri combinati e passaggio di pagina sono stati eseguiti via JavaScript sulla pagina, perché la finestra era nascosta.
- Nessuno screenshot.
- Le prestazioni della ricerca non sono state misurate (da fare in M7).

**Revisione indipendente:** [`review.md`](review.md). I quattro problemi importanti sono corretti, oppure, per il punto 3, il contratto è stato reso esatto.

**Merge:** la PR modifica archivio e ripristino (R7) ed export (R8). Il 2026-11-15 il proprietario ha approvato in chat le modifiche R7/R8 e il merge («1. approvo») e ha accettato il limite di REQ-089 sulle falsificazioni volute («2. accetto»), come previsto da DEC-001.
