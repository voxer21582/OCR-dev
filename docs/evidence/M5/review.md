# M5 — revisione indipendente

Il revisore era un agente automatico separato, con sola lettura del codice. Non ha eseguito i test. Ha esaminato il diff `origin/main...HEAD` di `claude/m5-libreria` fino a `4043ee4`. Il limite di questa revisione è dichiarato secondo DEC-008.

Correzioni: commit `75ce91d`, con test.

| # | Gravità | Problema | Esito |
|---|---|---|---|
| 1 | Importante | Un secondo ripristino sovrascriveva la copia `.before-restore` del primo | Corretto: ogni copia ha nome con data e ora (`test_a_second_restore_keeps_the_first_previous_copy`) |
| 2 | Importante | Un errore fra i due `os.replace`, o nei controlli dopo lo scambio, lasciava l'archivio mancante | Corretto: l'archivio precedente viene rimesso al suo posto (`test_a_failed_swap_puts_the_previous_archive_back`) |
| 3 | Importante | `read_case_export` non rileva una falsificazione voluta: le impronte non sono a chiave e alcuni campi non sono coperti | Contratto corretto: il lettore rileva modifiche incoerenti o accidentali, non falsificazioni. Il limite è scritto nel modulo e in `acceptance.md`. Una firma a chiave cambierebbe il formato dell'export (R8): resta una possibile estensione da decidere con il proprietario |
| 4 | Importante | Eliminando un fascicolo, restavano i metadati della libreria dei suoi documenti | Corretto (`test_deleting_a_case_removes_its_label_and_its_documents_metadata`) |
| 5 | Minore | Il ripristino accetta al massimo 100 MB | Limite scritto nella pagina e in `acceptance.md` |
| 6 | Minore | Limiti alti per gli elementi dello ZIP | Manifest al massimo 64 KB; database al massimo 512 MB e non oltre la dimensione dichiarata |
| 7 | Minore | Un journal di transazione rimasto accanto all'archivio | Il ripristino si rifiuta finché il journal esiste (`test_restore_refuses_while_a_transaction_journal_exists`) |
| 8 | Minore | Ripristino durante un'elaborazione di fascicolo | Corretto: risposta 409 (`test_restore_waits_for_a_running_case_job`) |
| 9 | Minore | Testo della pagina errato oltre l'ultima pagina | Corretto: viene mostrata l'ultima pagina |
| 10 | Minore | La ricerca decifra ogni record a ogni pagina | Accettato per ora, senza misure: da misurare e rivedere in M7 (prestazioni) |
| 11 | Minore | L'export del fascicolo rifiuta parametri estranei | Accettato: è più stretto, mentre byte e nomi dei file degli export validi sono invariati |

Il revisore ha trovato corretti:
- i controlli di origine e CSRF delle nuove richieste POST;
- l'escape dell'HTML e i nomi dei file scaricati;
- la gestione dello ZIP: niente path traversal;
- la verifica della copia prima dello scambio;
- l'atomicità della migrazione allo schema 4;
- i byte dell'export del fascicolo, identici a prima.
