# Collaudo M6 sull'altro PC — bozza

**Non eseguire ancora:** servono installer definitivi, firma verificata e revisione. Questa procedura sarà completata e consegnata quando saranno pronti.

Usare un account Windows normale e solo documenti sintetici del progetto. Conservare le copie di prova e gli inventari sul PC: possono contenere nomi personali. Prima di condividere qualsiasi confronto, rileggere il risultato e condividere soltanto le righe che riguardano OCR2.

1. **Prima dell'installazione.** Eseguire `user-footprint.ps1 -Out <file-prima>` in PowerShell. Se viene segnalato che l'inventario è incompleto, annotarlo. Conservare il file privatamente.
2. **Installare 0.6.0.** Eseguire l'installer firmato per l'utente corrente. Verificare che nel menu Start compaia OCR2 e che non servano privilegi amministrativi. □
3. **Aprire l'app.** Dal menu Start avviare OCR2, aprire Informazioni e verificare versione 0.6.0 e runtime verificato. Creare un fascicolo usando esclusivamente fixture sintetiche. □
4. **Uscire e riaprire.** Usare Esci, poi riaprire e controllare che il fascicolo sia ancora presente. Chiudere la finestra e verificare che il processo termini. □
5. **Aggiornare.** Installare 0.6.1, aprire Informazioni e verificare la nuova versione e la presenza del fascicolo. □
6. **Interrompere un aggiornamento.** Usare il pacchetto di prova e le istruzioni definitive che saranno fornite; interrompere durante l'estrazione e verificare che la versione precedente continui ad aprirsi. □
7. **Ripristinare.** Dal menu Start selezionare «Torna alla versione precedente»; verificare 0.6.0 in Informazioni e la presenza dei dati. □
8. **Disinstallare mantenendo i dati.** Scegliere di non eliminarli. Reinstallare e verificare che il fascicolo sia ancora presente. □
9. **Disinstallare eliminando i dati.** Confermare esplicitamente la rimozione dei dati di prova; verificare che il fascicolo non sia più presente. □
10. **Dopo la prova.** Eseguire `user-footprint.ps1 -Out <file-dopo>` e poi `user-footprint.ps1 -Compare @('<file-prima>','<file-dopo>')`. Rileggere l'output privatamente e riportare solo le righe pertinenti a OCR2. □

Per ogni casella annotare data, esito e messaggio di errore, senza includere dati personali. Non modificare impostazioni o registro di Windows per eseguire la prova.
