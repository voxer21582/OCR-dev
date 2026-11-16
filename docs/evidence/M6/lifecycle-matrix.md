# Matrice di collaudo M6

| Prova | PC di sviluppo | Altro PC |
|---|---|---|
| Installazione 0.6.0 | Riuscita su ac4ba8a, modalità test | Da eseguire |
| Avvio, informazioni e uscita | Riusciti con finestra Edge reale su copia installata ac4ba8a; pacchetto firmato non verificato | Da eseguire |
| Documento originale: 30 s e Indietro, poi 200 s (R14) | Non eseguita; visualizzazione di un PDF sintetico in Edge verificata a parte ([revisione](review.md)) | Da eseguire |
| Sospensione del PC per 5 minuti, poi clic | Non eseguita; solo test sintetici dell'orologio | Da eseguire |
| Processo di Edge dopo la chiusura (R18) | Avvio rapido di Edge osservato dopo la chiusura, avvio da sorgenti ([app-window.md](app-window.md), 4c) | Da eseguire |
| Chiusura con la X e porta libera entro 190 s | Arresto in 10,2–11,5 s con segnale di chiusura e in 175 s per scadenza, avvio da sorgenti ([app-window.md](app-window.md), 4) | Da eseguire |
| Aggiornamento 0.6.1 | Riuscito su ac4ba8a, modalità test | Da eseguire |
| Aggiornamento interrotto | Ripresa riuscita dopo file estratto osservato su ac4ba8a; momento esatto dell’arresto non dimostrato | Da eseguire |
| Aggiornamento con OCR2 aperto | Non eseguita sul pacchetto; stesso blocco della disinstallazione | Da eseguire |
| Disinstallazione con OCR2 aperto | Rifiutata con app simulata e completata dopo il rilascio, modalità test | Da eseguire |
| Ripristino versione precedente (solo dal menu Start) | Riuscito su ac4ba8a con `/ROLLBACK`, modalità test senza collegamenti | Da eseguire |
| Disinstallazione senza dati | Riuscita su ac4ba8a con dati sintetici conservati, modalità test | Da eseguire |
| Disinstallazione con dati | Riuscita su ac4ba8a con soli dati sintetici, modalità test | Da eseguire |
| Confronto impronta utente, solo righe OCR2 | Parziale: profilo Edge predefinito e associazioni HTTP/HTTPS, prima della chiusura della finestra; script e filtro provati su cartelle sintetiche (`test_user_footprint.py`) | Da eseguire |

La modalità test non crea collegamenti nel menu Start e non elimina dati utente. I risultati parziali sono descritti in [installer-dev-pc.md](installer-dev-pc.md); i passi sono nella [procedura](../../runtime/m6-lifecycle-procedure.md).
