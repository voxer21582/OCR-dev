# Collaudo M6 con un secondo account Windows

Questa procedura sostituisce la prova sull'altro PC quando l'altro PC non è disponibile. Si usa un **nuovo account Windows su questo PC**. OCR2 si installa solo per l'utente che lo esegue: programma, dati, menu Start e impostazioni stanno nel profilo di quell'utente. Un account nuovo parte quindi pulito, e il tuo account con il tuo OCR2 non viene toccato.

**Cosa non copre rispetto a un altro PC.** Edge e Windows sono quelli di questo PC. Un problema che dipende da un'altra installazione di Windows non emergerebbe. L'avviso SmartScreen potrebbe non comparire, perché Windows ha già visto file simili su questa macchina.

Tempo previsto: circa un'ora e mezza.

## Regole

- Usare **solo documenti di prova inventati**, mai documenti veri.
- Durante la prova non installare né aggiornare altri programmi.
- Il ritorno alla versione precedente si fa **solo** dalla voce «Torna alla versione precedente» del menu Start. Non reinstallare la 0.6.0 per tornare indietro.
- Il disinstallatore restituisce il controllo subito ma lavora ancora per qualche secondo. Aspettare **15 secondi** prima di controllare cartelle e menu Start.
- I comandi vanno scritti in **Windows PowerShell**: dal menu Start cercare «Windows PowerShell» e aprirlo **senza** «Esegui come amministratore».
- Per ogni passo annotare nel foglio esiti in fondo: esito (OK / NO), eventuale messaggio esatto, ora.

## Limiti già noti (non sono errori, annotarli se compaiono)

- **Avviso di Windows.** Gli installer non sono firmati (DEC-034). Windows può mostrare «Windows ha protetto il PC».
- **Avvio lento.** All'avvio OCR2 controlla tutti i propri file: la finestra può metterci alcuni secondi.
- **App ancora accesa dopo la chiusura.** Se si chiude la finestra con la X entro 2 secondi da un clic, oppure mentre una pagina di elaborazione si aggiorna da sola, OCR2 può restare acceso fino a 3 minuti. Nel frattempo installer e disinstallatore rispondono «Chiudi OCR2 e gli altri installer prima di continuare.»: aspettare 3 minuti e riprovare.
- **Edge in background.** Dopo la chiusura può restare un `msedge.exe` con `--no-startup-window`: è l'avvio rapido di Edge, non di OCR2.
- **Residui dopo la disinstallazione.** Possono restare il file `%LOCALAPPDATA%\OCR2.instance.lock` e una cartella `%LOCALAPPDATA%\Programs` vuota.

---

## Parte A — Preparazione (dal tuo account)

**A1. Creare l'account di prova.** Impostazioni → Account → Altri utenti → «Aggiungi account» → «Non ho le informazioni di accesso di questa persona» → «Aggiungi un utente senza account Microsoft». Nome: `ocr2prova`, con una password a scelta. Lasciarlo **utente standard**, non amministratore. □

**A2. Copiare la cartella degli installer in un posto comune.** In Esplora file copiare l'intera cartella `C:\Users\voxer\ocr2-phase2a\m6-installer-altro-pc-2` dentro `C:\Users\Public\`. Il risultato è `C:\Users\Public\m6-installer-altro-pc-2`. □

**A3. Creare la cartella per gli esiti.** Creare `C:\Users\Public\ocr2-esiti`. Ci finiranno solo il foglio esiti e il confronto filtrato. □

**A4. Uscire dal tuo account.** Start → icona utente → «Esci». Poi entrare come `ocr2prova`. Al primo accesso Windows prepara il profilo: ci vuole qualche minuto. □

---

## Parte B — Prova (nell'account `ocr2prova`)

Aprire Windows PowerShell e incollare queste due righe una volta sola. Valgono finché la finestra resta aperta; se la si chiude, incollarle di nuovo.

```powershell
$k = 'C:\Users\Public\m6-installer-altro-pc-2'
$p = Join-Path $env:USERPROFILE 'Documents\ocr2-prova'; New-Item -ItemType Directory -Force $p | Out-Null
```

`$p` è una cartella privata dell'account di prova. Qui finiscono le fotografie del profilo, che possono contenere nomi di file.

**B1. Controllare i file ricevuti.**
```powershell
Get-ChildItem "$k\*" -File -Exclude SHA256SUMS.txt,LEGGIMI.txt,*.pdf,m6-procedura-secondo-account.md | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) }
Get-Content "$k\SHA256SUMS.txt"
```
Devono uscire 4 righe, e ognuna deve comparire identica in `SHA256SUMS.txt`. Se una differisce, **fermarsi**.

Poi:
```powershell
(Get-AuthenticodeSignature "$k\OCR2-0.6.0-setup-non-firmato-5e347e2.exe").Status
```
Deve dare `NotSigned`: annotare «non firmato». □

**B2. Fotografia del profilo prima dell'installazione.**
```powershell
$env:LOCALAPPDATA.Length
powershell -NoProfile -ExecutionPolicy Bypass -File "$k\user-footprint.ps1" -Out "$p\prima.txt"
```
Annotare il numero stampato dalla prima riga: deve essere al massimo 95. Se compare «l'inventario è incompleto», annotarlo. □

**B3. Installare la 0.6.0.** In Esplora file aprire `C:\Users\Public\m6-installer-altro-pc-2` e fare doppio clic su `OCR2-0.6.0-setup-non-firmato-5e347e2.exe`.
- Se compare «Windows ha protetto il PC»: «Ulteriori informazioni» → «Esegui comunque», e annotarlo. Se non compare, annotare «SmartScreen non comparso».
- **Non deve essere chiesta** la password di un amministratore. Se viene chiesta, fermarsi e annotarlo.
- In basso nella finestra dell'installer deve leggersi **«OCR2 0.6.0 — non firmato»**, con le lettere corrette e senza simboli strani. Annotare cosa si legge.

Al termine, controllare:
```powershell
Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"
(Get-ChildItem "$env:LOCALAPPDATA\Programs\OCR2" -Recurse -Filter 'opencv_videoio_ffmpeg*').Count
```
- La prima riga deve dare `{"active": "0.6.0", "previous": null}`.
- La seconda deve dare `0`.
- Nel menu Start, cartella **OCR2**, devono esserci «OCR2», «Torna alla versione precedente» e «Disinstalla OCR2». □

**B4. Aprire l'app e caricare un documento.** Dal menu Start avviare «OCR2»: si apre una finestra di Edge senza barra degli indirizzi.
1. **Informazioni.** «Esci» e «Informazioni» sono in fondo alla pagina; scorrere se serve. Aprire «Informazioni» e verificare:
   - Versione `0.6.0`;
   - Python `3.13.18`;
   - Motore OCR `RapidOCR 3.10.0`;
   - Verifica del runtime `verificato`.

   Poi «Torna all'acquisizione temporanea».
2. **Caricamento.** Scegliere un'immagine di prova inventata (per esempio una foto di un foglio con scritto «TOTALE EURO 12,50») e premere «Carica e continua».
3. Nella pagina «Quale file è la nota spese?» selezionare il file e premere **«Conferma nota spese»**. Deve comparire «Elaborazione OCR» e poi «Elaborazione completata». **Non deve comparire «Risorsa non trovata».**
4. Premere «Apri i documenti elaborati», poi **«Salva in archivio»**: deve comparire «Documento salvato nell'archivio locale.».
5. Aprire «Apri archivio locale»: il documento deve essere nell'elenco. Premere «Apri». □

**B5. Documento originale.** Nella pagina «Documento in archivio» premere «Apri documento originale».
1. Aspettare **30 secondi**, poi tornare indietro con **Alt + freccia sinistra**: l'archivio deve rispondere.
2. Riaprire il documento originale e restarci **200 secondi**. Poi premere un collegamento: l'app deve rispondere.
3. Se compare «Documento non disponibile», annotarlo. □

**B6. Sospensione.** Con la finestra aperta: Start → Arresta → **Sospendi**. Aspettare 5 minuti, riattivare il PC e rientrare come `ocr2prova`. Premere «Informazioni»: l'app deve rispondere. □

**B7. Esci.** Premere «Esci»: compare «OCR2 si è chiuso. Puoi chiudere questa finestra.». La finestra non si chiude da sola: chiuderla con la **X**. Dopo circa 15 secondi:
```powershell
Test-Path "$env:LOCALAPPDATA\OCR2\instance.json"
```
Deve dare `False`. In Gestione attività (Ctrl+Maiusc+Esc) non deve esserci `pythonw.exe`. Riaprire OCR2 dal menu Start: il documento deve essere ancora in archivio. □

**B8. Processo di Edge.** Chiudere OCR2 con «Esci» e la X, poi aspettare 15 secondi. In Gestione attività → Dettagli, tasto destro sull'intestazione → «Seleziona colonne» → spuntare «Riga di comando». Nessun `msedge.exe` deve contenere `OCR2\edge-profile`. Un `msedge.exe` con `--no-startup-window` è un limite noto di Edge: annotarlo. □

**B9. Chiusura con la X e porta libera.** Riaprire OCR2, poi:
```powershell
$porta = (Get-Content "$env:LOCALAPPDATA\OCR2\instance.json" | ConvertFrom-Json).port
Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
```
Deve stampare una riga.

Ora chiudere la finestra con la **X**, non con «Esci», e ripetere ogni 15 secondi la seconda riga del comando qui sopra. La porta è libera quando il comando **non stampa nulla**. Annotare dopo quanti secondi succede: deve essere entro **190 secondi**, di solito circa 10. □

**B10. Aggiornamento con OCR2 aperto.** Aprire OCR2 e lasciarlo aperto. Fare doppio clic su `OCR2-0.6.1-setup-non-firmato-5e347e2.exe`, rispondendo a SmartScreen come in B3. Deve comparire «Chiudi OCR2 e gli altri installer prima di continuare.», e poi:
```powershell
Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"
```
deve dare ancora `0.6.0`. Chiudere OCR2 con «Esci» e la X. □

**B11. Aggiornamento interrotto.** Con OCR2 chiuso, incollare in PowerShell il blocco «Interruzione controllata» in fondo a questa procedura. Deve stampare «File estratto osservato e processo interrotto». Se invece stampa «Estrazione non osservata», annotarlo e passare comunque a B12.

Poi:
```powershell
Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"
```
deve dare ancora `0.6.0`. Aprire OCR2: deve mostrare 0.6.0 in «Informazioni» e il documento in archivio. Chiudere con «Esci» e la X. □

**B12. Aggiornamento alla 0.6.1.** Con OCR2 chiuso, fare doppio clic sull'installer 0.6.1. In basso deve leggersi «OCR2 0.6.1 — non firmato». Poi:
```powershell
Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"
```
deve dare `{"active": "0.6.1", "previous": "0.6.0"}`. Aprire OCR2: «Informazioni» deve dire 0.6.1 e il documento deve essere in archivio. Ripetere anche una volta B4 punti 2–4 con un nuovo documento di prova. Chiudere con «Esci» e la X. □

**B13. Ritorno alla versione precedente.** Dal menu Start: «Torna alla versione precedente». Se riesce non compare alcun messaggio; se fallisce compare «Impossibile ripristinare la versione precedente.». Poi:
```powershell
Get-Content "$env:LOCALAPPDATA\Programs\OCR2\active.json"
```
deve dare `{"active": "0.6.0", "previous": "0.6.1"}`. Aprire OCR2: «Informazioni» deve dire 0.6.0 e i documenti devono esserci. Chiudere con «Esci» e la X. □

**B14. Disinstallare mantenendo i dati.**
1. Aprire OCR2 e lasciarlo aperto. Dal menu Start avviare «Disinstalla OCR2»: deve comparire «Chiudi OCR2 e gli altri installer prima di continuare.» e nulla deve cambiare.
2. Chiudere OCR2 con «Esci» e la X. Avviare di nuovo «Disinstalla OCR2». In basso deve leggersi «non firmato». Alla domanda «Vuoi eliminare anche i dati locali OCR2?» rispondere **No**.
3. Dopo 15 secondi:
   ```powershell
   Test-Path "$env:LOCALAPPDATA\Programs\OCR2"
   Test-Path "$env:LOCALAPPDATA\OCR2"
   ```
   La prima riga deve dare `False`, la seconda `True`. La cartella OCR2 del menu Start non deve esistere più. Se compare «La cartella OCR2 non è vuota e non è stata rimossa.», annotare cosa contiene.
4. Reinstallare la **0.6.1** e aprire OCR2: i documenti devono esserci ancora. Chiudere con «Esci» e la X. □

**B15. Disinstallare eliminando i dati.** Questo account contiene solo dati di prova.
1. Con OCR2 chiuso avviare «Disinstalla OCR2» e rispondere **Sì** alla domanda sui dati. Dopo 15 secondi:
   ```powershell
   Test-Path "$env:LOCALAPPDATA\OCR2"
   ```
   deve dare `False`.
2. Reinstallare la 0.6.1 e aprire OCR2: l'archivio deve essere **vuoto**.
3. Chiudere con «Esci» e la X, poi disinstallare di nuovo rispondendo **Sì**.
4. In Gestione attività non deve restare `pythonw.exe`. □

**B16. Fotografia dopo e confronto.**
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$k\user-footprint.ps1" -Out "$p\dopo.txt"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$k\user-footprint.ps1' -Compare @('$p\prima.txt','$p\dopo.txt') | Set-Content '$p\confronto-completo.txt' -Encoding UTF8"
Select-String -Path "$p\confronto-completo.txt" -Pattern 'OCR2' | ForEach-Object { $_.Line } | Set-Content 'C:\Users\Public\ocr2-esiti\confronto-ocr2.txt' -Encoding UTF8
(Select-String -Path "$p\confronto-completo.txt" -Pattern 'OCR2' -NotMatch).Count
```
- L'ultimo numero stampato conta le differenze che non riguardano OCR2, come Windows ed Edge che cambiano file da soli. Annotare solo il numero.
- Aprire `C:\Users\Public\ocr2-esiti\confronto-ocr2.txt`: l'unica riga attesa è `+ LOCALAPPDATA|FILE|OCR2.instance.lock`. Annotare ogni altra riga.
- Una riga `+ LOCALAPPDATA|DIR|Programs` (cartella vuota) è un limite noto: annotarla a parte. □

**B17. Salvare il foglio esiti** compilato in `C:\Users\Public\ocr2-esiti\esiti.txt` (va bene anche Blocco note). Uscire da `ocr2prova` e rientrare nel tuo account. □

---

## Parte C — Dopo (dal tuo account)

**C1.** Mandare a Claude il contenuto di `C:\Users\Public\ocr2-esiti\` (esiti e `confronto-ocr2.txt`), rileggendolo prima. □

**C2.** Quando Claude ha registrato gli esiti, si può eliminare l'account: Impostazioni → Account → Altri utenti → `ocr2prova` → «Rimuovi» → «Elimina account e dati». Così si cancellano anche il suo profilo e le fotografie del profilo. Si possono poi eliminare `C:\Users\Public\m6-installer-altro-pc-2` e `C:\Users\Public\ocr2-esiti`. □

---

## Interruzione controllata (per B11)

Incollare tutto il blocco in PowerShell, con OCR2 chiuso. Il blocco avvia l'installer 0.6.1 in modo silenzioso e lo interrompe appena vede il primo file estratto. Non modifica impostazioni o registro di Windows. Se SmartScreen blocca l'avvio, eseguire prima:
```powershell
Unblock-File "$k\OCR2-0.6.1-setup-non-firmato-5e347e2.exe"
```
e annotarlo.

```powershell
$installerProva = "$k\OCR2-0.6.1-setup-non-firmato-5e347e2.exe"
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

## Se qualcosa non va

- **«Chiudi OCR2 e gli altri installer prima di continuare.»** Chiudere OCR2 con «Esci». Se la finestra era stata chiusa con la X, aspettare 3 minuti e riprovare.
- **OCR2 non si apre, oppure compare un messaggio «OCR2 — …».** Leggere il registro:
  ```powershell
  Get-Content "$env:LOCALAPPDATA\OCR2\logs\launcher.log" -Tail 60
  ```
  Copiare nel foglio esiti solo l'ultima voce (inizia con `=== <data e ora> · <tipo> ===`), dopo averla riletta.
- **Per fermare la prova a metà.** Chiudere OCR2 con «Esci», eseguire B15 e B16.

## Foglio esiti

Copiare in `esiti.txt` e compilare (OK / NO, più note e messaggi esatti):

```
Data e ora inizio:
Lunghezza LOCALAPPDATA (B2):
A1 account creato:
B1 impronte / NotSigned:
B2 fotografia prima / inventario incompleto?:
B3 installazione 0.6.0 / SmartScreen / nessuna richiesta di amministratore / testo «OCR2 0.6.0 — non firmato» letto come:
B4 Informazioni (versione, Python, motore, verificato):
B4 Conferma nota spese → Elaborazione completata (niente «Risorsa non trovata»):
B4 Salva in archivio / Apri archivio:
B5 originale 30 s + Indietro / 200 s:
B6 sospensione 5 min:
B7 Esci + X / instance.json assente / documento ancora presente:
B8 msedge con OCR2\edge-profile? / --no-startup-window?:
B9 porta libera dopo secondi:
B10 aggiornamento con OCR2 aperto rifiutato:
B11 interruzione osservata / resta 0.6.0:
B12 aggiornamento 0.6.1 / nuovo documento:
B13 Torna alla versione precedente:
B14 disinstallazione con dati conservati / reinstallazione:
B15 disinstallazione con dati eliminati / archivio vuoto:
B16 differenze non-OCR2 (numero) / righe OCR2:
Note:
```
