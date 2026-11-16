# Collaudo M6 sull'altro PC — bozza

**Non eseguire ancora:** servono installer definitivi, firma verificata e revisione. Questa procedura sarà completata e consegnata quando saranno pronti.

Usare un account Windows normale e solo documenti sintetici del progetto. Conservare le copie di prova e gli inventari sul PC: possono contenere nomi personali. Prima di condividere qualsiasi confronto, rileggere il risultato e condividere soltanto le righe che riguardano OCR2.

1. **Prima dell'installazione.** Eseguire `user-footprint.ps1 -Out <file-prima>` in PowerShell. Se viene segnalato che l'inventario è incompleto, annotarlo. Il confronto rileva nomi aggiunti o rimossi: non rileva modifiche al contenuto di file esistenti né ai valori delle chiavi di registro, quindi non basta da solo a dimostrare che impostazioni già presenti siano invariate. Conservare il file privatamente.
2. **Installare 0.6.0.** Eseguire l'installer firmato per l'utente corrente. Verificare che nel menu Start compaia OCR2 e che non servano privilegi amministrativi. □
3. **Aprire l'app.** Dal menu Start avviare OCR2, aprire Informazioni e verificare versione 0.6.0 e runtime verificato. Creare un fascicolo usando esclusivamente fixture sintetiche. □
4. **Uscire e riaprire.** Usare Esci, poi riaprire e controllare che il fascicolo sia ancora presente. Chiudere la finestra e verificare che il processo termini. □
5. **Interrompere il primo aggiornamento.** Prima di installare 0.6.1, chiudere OCR2 e interrompere l'installer 0.6.1 dopo avere osservato un file estratto, seguendo il comando sotto. Verificare che la versione 0.6.0 e il fascicolo siano ancora disponibili. Se il comando non osserva l'estrazione mentre il processo è attivo, non segnare la prova come riuscita. □
6. **Riprendere l'aggiornamento.** Chiudere OCR2, eseguire nuovamente l'installer firmato 0.6.1, aprire Informazioni e verificare la nuova versione e la presenza del fascicolo. □
7. **Ripristinare.** Dal menu Start selezionare «Torna alla versione precedente»; verificare 0.6.0 in Informazioni e la presenza dei dati. □
8. **Disinstallare mantenendo i dati.** Scegliere di non eliminarli. Reinstallare e verificare che il fascicolo sia ancora presente. □
9. **Disinstallare eliminando i dati.** Confermare esplicitamente la rimozione dei dati di prova; verificare che la cartella `%LOCALAPPDATA%\OCR2` sia assente, poi reinstallare e verificare nell’app che il fascicolo di prova non sia presente. Chiudere l’app e disinstallare di nuovo con rimozione dei dati di prova prima del confronto finale. □
10. **Dopo la prova.** Eseguire `user-footprint.ps1 -Out <file-dopo>` e poi `user-footprint.ps1 -Compare @('<file-prima>','<file-dopo>')`. Rileggere l'output privatamente e riportare solo le righe pertinenti a OCR2. □


### Interruzione controllata del primo aggiornamento

Da usare solo sul PC di collaudo, dopo i punti 1–4 e prima di installare 0.6.1. Sostituire il percorso tra virgolette con il percorso effettivo dell'installer 0.6.1 verificato; lasciare invariato il resto. Il comando interrompe soltanto il processo che ha appena avviato e soltanto dopo aver visto un file dentro una sottocartella di staging. Tra l’osservazione e l’arresto la copia potrebbe comunque terminare: questa prova non stabilisce il momento esatto dell’interruzione. Se esistono già residui, si ferma senza cancellarli: occorre esaminarli prima di ripetere la prova.

```powershell
$installerProva = 'C:\percorso\installer-0.6.1-firmato.exe'
$baseProva = Join-Path $env:LOCALAPPDATA 'Programs\OCR2'
$stagingProva = Join-Path $baseProva 'staging'
if (Test-Path -LiteralPath (Join-Path $baseProva 'versions\0.6.1')) {
    throw 'La versione 0.6.1 è già presente: questa prova richiede il primo aggiornamento.'
}
if (@(Get-ChildItem -LiteralPath $stagingProva -Force -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Staging contiene già elementi: esaminarli prima della prova.'
}
$processoProva = Start-Process -FilePath $installerProva -ArgumentList '/S' -WindowStyle Hidden -PassThru
$scadenzaProva = [DateTime]::UtcNow.AddSeconds(30)
$interrottoProva = $false
while ([DateTime]::UtcNow -lt $scadenzaProva) {
    $processoProva.Refresh()
    if ($processoProva.HasExited) { break }
    $fileEstrattiProva = @(Get-ChildItem -LiteralPath $stagingProva -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -File -Recurse -Force -ErrorAction SilentlyContinue })
    if ($fileEstrattiProva.Count -gt 0) {
        $processoProva.Kill()
        $processoProva.WaitForExit()
        $interrottoProva = $true
        break
    }
    Start-Sleep -Milliseconds 50
}
if (-not $interrottoProva) {
    throw 'Estrazione non osservata: prova non conclusa; controllare lo stato prima di procedere.'
}
Write-Output "File estratto osservato e processo interrotto: verificare la versione precedente."
```

Il comando non modifica il registro o le impostazioni Windows; avvia l'installer di prova e interrompe quel processo. Se non è stata osservata l'estrazione, il processo potrebbe essere ancora attivo: verificarne lo stato prima di qualsiasi nuovo tentativo. La verifica del funzionamento di 0.6.0 dopo l'interruzione va eseguita separatamente.

Per ogni casella annotare data, esito e messaggio di errore, senza includere dati personali. Non modificare impostazioni o registro di Windows per eseguire la prova.
