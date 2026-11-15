# M5 — percorso nella libreria (browser e HTTP locale)

Data: 2026-11-15. Codice: commit `4043ee4` (pagina della libreria) del branch `claude/m5-libreria`.

Ambiente:
- browser integrato dell'app desktop, server locale loopback avviato con `application/tools/m5_synthetic_library_server.py`;
- archivio **nuovo** in una cartella temporanea, protetto con la vera DPAPI dell'utente Windows;
- 30 record sintetici generati dallo script.

L'archivio reale in `%LOCALAPPDATA%\OCR2` non è stato usato.

## Nel browser

1. `/archive` mostrava «Documenti 1–25 di 30 · pagina 1 di 2», i filtri (testo, tipo, revisione, etichetta, date) e, per ogni documento:
   - i moduli «Rinomina» e «Salva etichette»;
   - i link «Esporta CSV» ed «Esporta JSON» presi dal registro degli esportatori.
2. Rinomina: nel campo «Nome visualizzato» del primo documento è stato scritto «Hotel Aurora Milano» e inviato con Invio. La pagina ha risposto «Nome aggiornato.» e il documento appariva come «Hotel Aurora Milano (file: ricevuta-sintetica-001.pdf)».
3. Etichette: «Trasferta Milano, cene» inviate con Invio. La pagina ha risposto «Etichette aggiornate.».
4. Filtro per etichetta «trasferta milano» (digitato e inviato con Invio): «Documenti 1–1 di 1».
5. Tipo «Scontrino» e revisione «Completata» scelti dai menu.
   - Insieme all'etichetta: 0 risultati (corretto, il documento etichettato è una fattura).
   - Senza l'etichetta: 3 risultati (010, 020, 030).
6. «Pagina successiva» da `/archive` ha aperto «Documenti 26–30 di 30 · pagina 2 di 2», con il solo link «Pagina precedente».

Limite: nei passi 5 e 6 la finestra dell'app era nascosta e il browser non disegnava la pagina. Per questo l'invio del modulo, lo svuotamento del campo etichetta e il clic sul link sono stati eseguiti via JavaScript sulla pagina. Nessuno screenshot è stato salvato.

## Backup e ripristino (HTTP locale, stesso server)

Lo scaricamento di un file dal browser non è stato fatto. La prova è stata eseguita con uno script Python contro lo stesso server, con la vera DPAPI.

1. `GET /archive/backup` → 200, `ocr2-backup-20261115-201142.zip` con `archive.sqlite3` e `manifest.json` (formato `ocr2-archive-backup-v1`, 30 documenti).
2. Eliminato `doc-002` (POST dalla stessa origine) → la ricerca «ricevuta-sintetica-002» dava 0 risultati.
3. Ripristino di uno ZIP con la copia troncata → 400, «Backup rifiutato … L'archivio attuale non è stato toccato».
4. Ripristino dello ZIP originale → 200, «Backup ripristinato: 30 documenti e 0 fascicoli».
   - La ricerca ritrovava `doc-002`.
   - Il nome «Hotel Aurora Milano» e l'etichetta del passo 3 erano presenti.
   - Accanto all'archivio era comparso `document-archive.sqlite3.before-restore`. Era la versione allora in prova; dopo la revisione (`75ce91d`) ogni ripristino crea una copia nuova `…before-restore-<data e ora>`, verificata da `test_archive_backup`.

Il rifiuto del backup di un altro utente Windows è verificato solo con il protettore sintetico (`test_archive_backup`, `test_library_ui`). Una prova con un secondo account Windows non è stata fatta.
