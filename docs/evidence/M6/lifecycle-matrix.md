# Matrice di collaudo M6

| Prova | PC di sviluppo | Altro PC |
|---|---|---|
| Installazione 0.6.0 | Riuscita su ac4ba8a, modalità test | Sostituito dalla prova con secondo account (2026-11-17) (B3), vedi sotto |
| Avvio, informazioni e uscita | Riusciti con finestra Edge reale su copia installata ac4ba8a; pacchetto firmato non verificato | Sostituito dalla prova con secondo account (2026-11-17) (B4, B7), vedi sotto |
| Documento originale: 30 s e Indietro, poi 200 s (R14) | Non eseguita; visualizzazione di un PDF sintetico in Edge verificata a parte ([revisione](review.md)) | Sostituito dalla prova con secondo account (2026-11-17) (B5), vedi sotto |
| Sospensione del PC per 5 minuti, poi clic | Non eseguita; solo test sintetici dell'orologio | Sostituito dalla prova con secondo account (2026-11-17) (B6), vedi sotto |
| Processo di Edge dopo la chiusura (R18) | Avvio rapido di Edge osservato dopo la chiusura, avvio da sorgenti ([app-window.md](app-window.md), 4c) | Sostituito dalla prova con secondo account (2026-11-17) (B8), vedi sotto |
| Chiusura con la X e porta libera entro 190 s | Arresto in 10,2–11,5 s con segnale di chiusura e in 175 s per scadenza, avvio da sorgenti ([app-window.md](app-window.md), 4) | Sostituito dalla prova con secondo account (2026-11-17) (B9), vedi sotto |
| Aggiornamento 0.6.1 | Riuscito su ac4ba8a, modalità test | Sostituito dalla prova con secondo account (2026-11-17) (B12), vedi sotto |
| Aggiornamento interrotto | Ripresa riuscita dopo file estratto osservato su ac4ba8a; momento esatto dell’arresto non dimostrato | Sostituito dalla prova con secondo account (2026-11-17) (B11), vedi sotto |
| Aggiornamento con OCR2 aperto | Non eseguita sul pacchetto; stesso blocco della disinstallazione | Sostituito dalla prova con secondo account (2026-11-17) (B10), vedi sotto |
| Disinstallazione con OCR2 aperto | Rifiutata con app simulata e completata dopo il rilascio, modalità test | Da eseguire |
| Ripristino versione precedente (solo dal menu Start) | Riuscito su ac4ba8a con `/ROLLBACK`, modalità test senza collegamenti | Sostituito dalla prova con secondo account (2026-11-17) (B13), vedi sotto |
| Disinstallazione senza dati | Riuscita su ac4ba8a con dati sintetici conservati, modalità test | Sostituito dalla prova con secondo account (2026-11-17) (B14), vedi sotto |
| Disinstallazione con dati | Riuscita su ac4ba8a con soli dati sintetici, modalità test | Sostituito dalla prova con secondo account (2026-11-17) (B15), vedi sotto |
| Confronto impronta utente, solo righe OCR2 | Parziale: profilo Edge predefinito e associazioni HTTP/HTTPS, prima della chiusura della finestra; script e filtro provati su cartelle sintetiche (`test_user_footprint.py`) | Sostituito dalla prova con secondo account (2026-11-17) (B16), vedi sotto |

La modalità test non crea collegamenti nel menu Start e non elimina dati utente. I risultati parziali sono descritti in [installer-dev-pc.md](installer-dev-pc.md); i passi sono nella [procedura](../../runtime/m6-lifecycle-procedure.md).

## Prova con secondo account Windows (2026-11-17)

L'altro PC non era disponibile: il proprietario ha eseguito la [procedura](../../runtime/m6-procedura-secondo-account.md) in un account Windows standard nuovo sul PC di sviluppo, con gli installer `5e347e2`. Sintesi e limiti in [collaudo-secondo-account.md](collaudo-secondo-account.md). Le righe di «Altro PC» non sono considerate eseguite su un altro PC: dove indicato sono sostituite da questa prova; le altre restano aperte.

| Passo | Prova | Esito dichiarato dal proprietario |
|---|---|---|
| B1 | Impronte e firma | 4 impronte corrispondenti; installer `NotSigned` |
| B2 | Lunghezza `%LOCALAPPDATA%` e fotografia iniziale | 32 caratteri; fotografia riuscita, nessun avviso di inventario incompleto |
| B3 | Installazione 0.6.0 | Riuscita; `active` 0.6.0, `previous` null; nessun `opencv_videoio_ffmpeg`. Testo in fondo all'installer e comportamento di SmartScreen: confermati dal proprietario, testo letto non annotato. Assenza di elevazione dedotta dall'account standard, non osservata |
| B4 | Avvio, elaborazione, archivio, «Informazioni» | Documento elaborato (1 su 1), nessun «Risorsa non trovata», salvataggio e apertura dell'archivio riusciti; «Informazioni»: verifica dichiarata OK, valori non annotati |
| B5 | Documento originale dopo 30 e 200 s | Riuscito |
| B6 | Sospensione di 5 minuti | Riuscita |
| B7 | «Esci» e riapertura | Nessun processo residuo, `instance.json` assente, documento conservato |
| B8 | Processo di Edge | Nessun Edge con `OCR2\edge-profile`; `--no-startup-window` presente (limite noto) |
| B9 | Chiusura con la X | Porta libera in circa 15 s |
| B10 | Aggiornamento con OCR2 aperto | Bloccato; versione rimasta 0.6.0 |
| B11 | Aggiornamento interrotto | Interruzione osservata; 0.6.0 e archivio conservati |
| B12 | Aggiornamento 0.6.1 | Riuscito; `active` 0.6.1, `previous` 0.6.0; nuovo documento elaborato e archiviato |
| B13 | Ripristino della 0.6.0 | Riuscito; `active` 0.6.0, `previous` 0.6.1; entrambi i documenti conservati. Nota: voce inizialmente non individuata; ripristino riuscito; confermato dal proprietario (non è un difetto) |
| B14 | Disinstallazione con dati conservati | Riuscita; reinstallazione con documenti recuperati |
| B15 | Disinstallazione con eliminazione dati | Riuscita; archivio vuoto dopo reinstallazione; nessun `pythonw.exe` residuo |
| B16 | Fotografia finale e confronto | Unica riga OCR2: `+ LOCALAPPDATA\|FILE\|OCR2.instance.lock`; 1533 differenze non OCR2 (profilo nuovo) |

**Non coperto.** «Disinstallazione con OCR2 aperto» non è un passo della procedura del secondo account (B10 prova l'aggiornamento con OCR2 aperto): resta aperta. Restano aperte anche le prove su un altro PC, su un'altra installazione di Windows e con SmartScreen senza reputazione condivisa.
