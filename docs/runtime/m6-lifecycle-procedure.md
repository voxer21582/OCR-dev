# Collaudo M6 sull'altro PC

Gli installer 0.6.0 e 0.6.1 sono build di rilascio **non firmate** (DEC-034): il proprietario non dispone di un certificato e REQ-105 è rinviato come limite dichiarato. Si compilano con `OCR2_UNSIGNED_RELEASE` ([installer/README.md](../../installer/README.md)): rispetto a una build firmata cambiano solo le verifiche Authenticode, saltate; collegamenti Start, domanda sui dati e cartella di installazione sono quelli del rilascio. Il testo in basso nelle finestre dell'installer e del disinstallatore riporta «non firmato». Servono, nella stessa cartella: i due installer, `SHA256SUMS.txt` e `user-footprint.ps1`.

Usare un account Windows normale e solo documenti sintetici del progetto. Conservare le copie di prova e gli inventari sul PC: possono contenere nomi personali. Prima di condividere qualsiasi confronto, rileggere il risultato e condividere soltanto le righe che riguardano OCR2.

## Regole

- OCR2 si installa sempre in `%LOCALAPPDATA%\Programs\OCR2`: l'installer non chiede la cartella. Con i percorsi lunghi di Windows disattivati, il percorso di `%LOCALAPPDATA%` deve restare entro circa 95 caratteri, perché il file più lungo del contenuto di prova ha 125 caratteri dentro la cartella della versione. Il limite è calcolato, non provato: annotare la lunghezza di `%LOCALAPPDATA%` (`$env:LOCALAPPDATA.Length` in PowerShell).
- Durante la prova non installare né aggiornare altri programmi.
- Il ritorno alla versione precedente si fa **solo** dalla voce «Torna alla versione precedente» del menu Start, mai reinstallando la 0.6.0.
- Gli script del progetto si lanciano con `powershell -NoProfile -ExecutionPolicy Bypass …`: l'opzione vale solo per quel comando e non cambia le impostazioni di Windows.
- Il disinstallatore ritorna subito e continua per qualche secondo: aspettare 15 secondi prima di controllare cartelle e menu Start.
- Su questo PC si usano **solo dati di prova**: la rimozione dei dati al punto 9 è definitiva.

## Limiti già noti

Non sono errori: annotarli se si presentano.

- Gli installer non sono firmati: all'avvio Windows SmartScreen mostra «Windows ha protetto il PC». È atteso (DEC-034), vedi il punto 2.
- All'avvio OCR2 verifica tutti i propri file: l'apertura della finestra può richiedere alcuni secondi.
- Una finestra chiusa con la X entro 2 secondi da un clic, o mentre una pagina di elaborazione si aggiorna da sola ogni 2 secondi, conta come navigazione: OCR2 può restare acceso fino a 180 secondi. Intanto installer e disinstallatore rifiutano con «Chiudi OCR2 e gli altri installer prima di continuare.»: aspettare 3 minuti e riprovare.
- Dopo la chiusura, l'avvio rapido di Edge può lasciare un processo `msedge.exe` con `--no-startup-window` sul profilo normale di Edge. È un'impostazione di Edge che OCR2 non cambia.
- Con `/S` (installazione silenziosa) i messaggi non compaiono; contano il codice di uscita e lo stato delle cartelle. Codici dell'installer: `0` riuscito, anche quando la versione è già installata e integra (non viene sostituita); `1` OCR2 o un altro installer aperto, oppure percorso non sicuro; `2` estrazione, verifica, collegamenti o attivazione non riusciti.
- Dopo la disinstallazione possono restare il file `%LOCALAPPDATA%\OCR2.instance.lock` (DEC-033) e una cartella `%LOCALAPPDATA%\Programs` vuota, se prima non esisteva.

## Passi

Lo stato delle versioni si legge con `Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"`.

1. **Prima dell'installazione.** Chiudere i programmi non necessari ed eseguire in PowerShell `powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\user-footprint.ps1" -Out "<cartella>\prima.txt"`. Se compare «l'inventario è incompleto», annotarlo. Il confronto rileva nomi aggiunti o rimossi: non rileva modifiche al contenuto di file esistenti né ai valori delle chiavi di registro, quindi non basta da solo a dimostrare che impostazioni già presenti siano invariate. Conservare il file privatamente.
   1. **Impronte degli installer.** Nella cartella degli installer eseguire `Get-FileHash -Algorithm SHA256 '<cartella>\OCR2-*-setup.exe'` e confrontare ogni valore con `SHA256SUMS.txt`: devono coincidere. Se uno differisce, fermarsi. Firma: `(Get-AuthenticodeSignature '<cartella>\OCR2-0.6.0-setup.exe').Status` dà `NotSigned`; le verifiche di firma della procedura sono saltate e si annota «non firmato». □
2. **Installare 0.6.0.** Eseguire l'installer per l'utente corrente. Compare SmartScreen («Windows ha protetto il PC»): premere «Ulteriori informazioni» e poi «Esegui comunque»; annotare «SmartScreen: non firmato». Se SmartScreen ricompare a ogni avvio e si vuole evitare che blocchi il comando del punto 5, dopo il controllo delle impronte si può togliere il solo contrassegno di download dai due file con `Unblock-File '<cartella>\OCR2-0.6.0-setup.exe', '<cartella>\OCR2-0.6.1-setup.exe'`: non cambia impostazioni di Windows; annotarlo. Verificare che non servano privilegi amministrativi; che nel menu Start la cartella OCR2 contenga «OCR2», «Torna alla versione precedente» e «Disinstalla OCR2»; che `active.json` sia `{"active": "0.6.0", "previous": null}`; che non esistano file `opencv_videoio_ffmpeg*.dll`: `(Get-ChildItem "$env:LOCALAPPDATA\Programs\OCR2" -Recurse -Filter 'opencv_videoio_ffmpeg*').Count` deve dare `0`. □
3. **Aprire l'app.** Dal menu Start avviare «OCR2»: si apre una finestra di Edge senza barra degli indirizzi. «Esci» e «Informazioni» sono in fondo al contenuto della pagina: scorrere in basso se serve. In «Informazioni» verificare Versione `0.6.0`, Python, Motore OCR diverso da «disattivato» e Verifica del runtime `verificato`, poi tornare con «Torna all’acquisizione temporanea». Caricare con «Carica e continua» soltanto un'immagine sintetica, salvarla con «Salva in archivio» e aprirla da «Apri archivio locale». □
   1. **Documento originale (R14).** Nella stessa sessione, nella pagina «Documento in archivio» premere «Apri documento originale»: compare la pagina «Documento originale». Aspettare 30 secondi e tornare indietro con Alt+freccia sinistra: l'archivio deve rispondere. Riaprire il documento originale e restarci **200 secondi**, più della scadenza di 180 secondi: la pagina tiene viva l'app, che deve rispondere al clic successivo. Se compare «Documento non disponibile», annotarlo. □
   2. **Sospensione.** Con la finestra aperta mettere il PC in sospensione (Start → Arresta → Sospendi) per 5 minuti, riattivarlo e premere un collegamento, per esempio «Informazioni»: l'app deve rispondere. □
4. **Uscire, chiudere e riaprire.** Premere «Esci»: compare «OCR2 si è chiuso. Puoi chiudere questa finestra.». La finestra non si chiude da sola: chiuderla con la X. Entro circa 15 secondi `%LOCALAPPDATA%\OCR2\instance.json` non deve esistere e in Gestione attività non deve esserci `pythonw.exe` di OCR2. Riaprire e controllare che il documento sia ancora in archivio. □
   1. **Processo di Edge (R18).** Almeno 15 secondi dopo la chiusura, in Gestione attività → Dettagli, colonna «Riga di comando»: nessun `msedge.exe` deve contenere `OCR2\edge-profile`. Un `msedge.exe` con `--no-startup-window` è l'avvio rapido di Edge (limite noto): annotarlo. □
   2. **Chiusura con la X e porta libera.** Riaprire OCR2, leggere la porta con `Get-Content "$env:LOCALAPPDATA\OCR2\instance.json"` e verificare che sia in ascolto con `Get-NetTCPConnection -LocalPort <porta> -State Listen -ErrorAction SilentlyContinue` (una riga). Chiudere la finestra con la X, **non** con «Esci», e ripetere il comando ogni 15 secondi. Porta libera significa che il comando non stampa nulla; con `netstat -ano | findstr :<porta>` significa nessuna riga `LISTENING` (le righe `TIME_WAIT` sono normali). Di solito la porta si libera dopo circa 10 secondi; soglia unica della prova: **190 secondi** (scadenza del battito di 180 secondi più margine). Annotare i secondi e verificare che `instance.json` non esista più. □
5. **Interrompere il primo aggiornamento.** Prima di installare 0.6.1, chiudere OCR2 e interrompere l'installer 0.6.1 dopo avere osservato un file estratto, seguendo il comando sotto. Verificare che `active.json` indichi ancora `0.6.0` e che la versione 0.6.0 e il documento siano ancora disponibili. Se il comando non osserva l'estrazione mentre il processo è attivo, non segnare la prova come riuscita. □
   1. **OCR2 aperto durante l'aggiornamento.** Avviare OCR2 e lasciarlo aperto, poi eseguire l'installer 0.6.1: deve comparire «Chiudi OCR2 e gli altri installer prima di continuare.» e `active.json` non deve cambiare. Facoltativo, sempre con OCR2 aperto: `(Start-Process -FilePath '<installer-0.6.1>' -ArgumentList '/S' -Wait -PassThru).ExitCode` deve dare `1`. Chiudere poi OCR2 con «Esci». □
6. **Riprendere l'aggiornamento.** Con OCR2 chiuso eseguire nuovamente l'installer 0.6.1 (se compare SmartScreen: «Ulteriori informazioni» → «Esegui comunque»): `active.json` deve essere `{"active": "0.6.1", "previous": "0.6.0"}`. Aprire Informazioni, verificare la nuova versione e la presenza del documento, poi «Esci». □
7. **Ripristinare.** Dal menu Start selezionare «Torna alla versione precedente». Se riesce non compare alcun messaggio; in caso di errore compare «Impossibile ripristinare la versione precedente.». `active.json` deve essere `{"active": "0.6.0", "previous": "0.6.1"}`; verificare 0.6.0 in Informazioni e la presenza dei dati, poi «Esci». □
8. **Disinstallare mantenendo i dati.** Prima, con OCR2 aperto, avviare «Disinstalla OCR2»: deve comparire «Chiudi OCR2 e gli altri installer prima di continuare.» e nulla deve cambiare. Chiudere OCR2 con «Esci», avviare di nuovo «Disinstalla OCR2» e alla domanda «Vuoi eliminare anche i dati locali OCR2?» rispondere **No**. Dopo 15 secondi `%LOCALAPPDATA%\Programs\OCR2` e la cartella OCR2 del menu Start non devono esistere, mentre `%LOCALAPPDATA%\OCR2` deve esistere. Se compare «La cartella OCR2 non è vuota e non è stata rimossa.», annotare cosa contiene. Reinstallare 0.6.1 e verificare che il documento sia ancora presente. □
9. **Disinstallare eliminando i dati.** **Solo dati di prova su questo PC.** Con OCR2 chiuso avviare «Disinstalla OCR2» e alla domanda «Vuoi eliminare anche i dati locali OCR2?» rispondere **Sì**. Verificare che la cartella `%LOCALAPPDATA%\OCR2` sia assente, poi reinstallare e verificare nell’app che il documento di prova non sia presente. Chiudere l’app con «Esci» e disinstallare di nuovo rispondendo **Sì**, prima del confronto finale. In Gestione attività non deve restare alcun processo di OCR2. □
10. **Dopo la prova.** Eseguire `powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\user-footprint.ps1" -Out "<cartella>\dopo.txt"`, poi il confronto e il filtro della sezione «Confronto da condividere». Righe OCR2 attese: soltanto `+ LOCALAPPDATA|FILE|OCR2.instance.lock`. Riportare ogni altra riga OCR2. □


### Interruzione controllata del primo aggiornamento

Da usare solo sul PC di collaudo, dopo i punti 1–4 e prima di installare 0.6.1. Sostituire il percorso tra virgolette con il percorso effettivo dell'installer 0.6.1 verificato. SmartScreen blocca l'avvio finché non si risponde e il comando attende al massimo 30 secondi: se all'avvio di 0.6.1 compare SmartScreen, usare prima `Unblock-File` come al punto 2, oppure ripetere la prova dopo aver risposto; lasciare invariato il resto. Il comando interrompe soltanto il processo che ha appena avviato e soltanto dopo aver visto un file dentro una sottocartella di staging. Tra l’osservazione e l’arresto la copia potrebbe comunque terminare: questa prova non stabilisce il momento esatto dell’interruzione. Se esistono già residui, si ferma senza cancellarli: occorre esaminarli prima di ripetere la prova.

```powershell
$installerProva = 'C:\percorso\OCR2-0.6.1-setup.exe'
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

### Confronto da condividere

Il confronto completo resta sul PC di collaudo; nel repository entrano solo le righe che riguardano OCR2.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '<cartella>\user-footprint.ps1' -Compare @('<cartella>\prima.txt','<cartella>\dopo.txt') | Set-Content '<cartella>\confronto-completo.txt' -Encoding UTF8"
Select-String -Path '<cartella>\confronto-completo.txt' -Pattern 'OCR2' | ForEach-Object { $_.Line } | Set-Content '<cartella>\confronto-ocr2.txt' -Encoding UTF8
(Select-String -Path '<cartella>\confronto-completo.txt' -Pattern 'OCR2' -NotMatch).Count
```

Ogni riga è `+` (solo dopo) o `-` (solo prima), seguita da radice, tipo e percorso relativo, senza nome utente né contenuti. L'ultimo comando conta le differenze estranee a OCR2 (Windows, Edge e altri programmi cambiano file da soli): riportare solo il numero. Una riga `+ LOCALAPPDATA|DIR|Programs` non contiene «OCR2»: se la cartella non esisteva prima, è la cartella vuota dei limiti noti; annotarla a parte. Rileggere `confronto-ocr2.txt` prima di consegnarlo; `prima.txt`, `dopo.txt` e `confronto-completo.txt` restano sul PC di collaudo.

### Se qualcosa non va

- **L'installer dice «Chiudi OCR2 e gli altri installer prima di continuare.»** Chiudere OCR2 con «Esci»; se la finestra era stata chiusa con la X, aspettare 3 minuti e riprovare.
- **OCR2 non si apre o mostra «OCR2 — avvio non riuscito», «OCR2 — installazione non valida» o «OCR2 — archivio non compatibile».** Il messaggio resta generico e termina con «Dettagli in %LOCALAPPDATA%\OCR2\logs\launcher.log». Chiudere il messaggio e leggere il registro con `Get-Content "$env:LOCALAPPDATA\OCR2\logs\launcher.log" -Tail 60` (oltre circa 256 KB le voci più vecchie passano in `launcher.log.1`). Ogni voce inizia con `=== <data e ora> · <tipo> ===` (`integrità`, `archivio più recente`, `uscita anomala`, `eccezione` o `import`) e riporta il messaggio o il tipo dell'errore con il traceback. Il registro contiene percorsi con il nome utente: riportare solo la voce rilevante, dopo averla riletta e aver tolto i nomi personali. Si scrive solo quando l'avvio non riesce: dopo un avvio o una chiusura normali non compare. In alternativa, senza scrivere file: `& "$env:LOCALAPPDATA\Programs\OCR2\versions\<versione>\python\python.exe" -B -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6`, con la versione indicata in `active.json`; il motivo compare nella finestra di PowerShell. Rimedi che l'installer accetta: installare di nuovo OCR2 con il suo installer, oppure «Torna alla versione precedente».
- **«Impossibile avviare la versione attiva di OCR2.»** Stessi rimedi: installare di nuovo OCR2 con il suo installer, oppure «Torna alla versione precedente».
- **«Nessuna versione integra disponibile. Reinstalla OCR2, poi riprova la disinstallazione.»** Installare di nuovo OCR2 e ripetere la disinstallazione.
- **Per fermare la prova a metà.** Chiudere OCR2 con «Esci», disinstallare come al punto 9 ed eseguire il punto 10.

Per ogni casella annotare data, esito e messaggio di errore, senza includere dati personali. Non modificare impostazioni o registro di Windows per eseguire la prova.
