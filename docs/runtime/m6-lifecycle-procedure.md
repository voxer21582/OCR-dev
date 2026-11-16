# OCR2: prova di installazione sul PC pulito (M6)

Per il proprietario. Si esegue su un secondo PC Windows senza OCR2, con il tuo utente normale (non serve essere amministratore e non bisogna avviare nulla «come amministratore»). Dura circa un'ora. In ogni passo trovi: **cosa fare**, **cosa si deve vedere** e una casella per l'**esito** (scrivi `OK`, `NO` o un'osservazione). Alla fine si compila la tabella `docs/evidence/M6/lifecycle-matrix.md` (una riga per passo).

Se un passo non va come descritto: **fermati**, annota cosa vedi (anche con una foto dello schermo) e passa al passo indicato in «Se qualcosa non va». Non reinstallare né cancellare cartelle a mano per «aggiustare».

## Prima di cominciare

Servono, in una cartella a tua scelta (per esempio `C:\Users\<tu>\Desktop\prova-ocr2`):

| File | Da dove |
|---|---|
| `OCR2-0.6.0-setup.exe` e `OCR2-0.6.1-setup.exe` | costruiti sul PC di sviluppo, copiati con una chiavetta |
| `user-footprint.ps1` | cartella `installer\` del repository |
| `verify-signature.ps1` | cartella `installer\` del repository (serve solo se hai firmato i file) |
| un'immagine di prova (`.png` o `.jpg`) | la crei tu al passo 5, con **dati inventati**: mai documenti veri |

Regole:

- Installa **nella cartella predefinita** (`%LOCALAPPDATA%\Programs\OCR2`). Non scegliere una cartella diversa e profonda: i percorsi dei file installati devono restare corti (il tratto fino a `versions\<versione>\` deve stare in 109 caratteri; la cartella predefinita va bene).
- Durante la prova non installare né aggiornare altri programmi.
- In questa procedura **non si reinstalla mai la versione precedente** (0.6.0) dopo la 0.6.1: il ritorno indietro si fa solo con «Torna alla versione precedente».
- Per «aprire PowerShell»: tasto Windows, scrivi `powershell`, Invio. (Windows PowerShell va bene.)
- Nei comandi, `<cartella>` è la cartella con i file; scrivi il percorso completo tra virgolette se contiene spazi.

Limiti già noti (non sono errori, annotali se li vedi):

- All'avvio OCR2 controlla tutti i suoi file: costa circa 4 secondi (a volte fino a 10). Lo trovi in «Informazioni» come `S s`.
- I file non firmati fanno comparire l'avviso di Windows SmartScreen (vedi passo 2).
- OCR2 può restare acceso fino a 30 minuti (il tempo di inattività della sessione) prima di fermarsi da solo, in questi casi: dopo aver letto un documento originale; se la finestra è chiusa con la X entro 2 secondi da un clic o dal controllo dell'installer; se la finestra è chiusa con la X durante un'elaborazione (quelle pagine si aggiornano da sole ogni 2 secondi). Intanto installare o disinstallare viene rifiutato con «Chiudi la finestra di OCR2…»: aspetta fino a 30 minuti oppure riavvia il PC.
- Dopo «Esci» Edge può lasciare un suo processo in secondo piano (avvio rapido di Edge): è un comportamento di Edge, OCR2 non cambia le sue impostazioni (passo 7).
- Il programma di disinstallazione si avvia e «ritorna subito»: la disinstallazione continua per qualche secondo dopo il suo avvio. Aspetta 15 secondi prima di controllare. Per **aspettare** davvero la fine (utile per vedere un rifiuto), da PowerShell: `& "$env:LOCALAPPDATA\Programs\OCR2\uninstall.exe" _?="$env:LOCALAPPDATA\Programs\OCR2"` (con `_?=` la cartella di installazione non viene cancellata a fine corsa: è normale).
- Costruendo l'installer, `makensis` segnala l'avviso 9000 sul nome «setup» (Windows applica regole di compatibilità ai file con questo nome): è atteso. Con `/S` (silenzioso) i messaggi (per esempio «già installata» o «Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova.») non si vedono: contano il codice di uscita (2) e lo stato delle cartelle.

---

## Passo 1. Impronta prima

**Cosa fare.** Chiudi i programmi che non servono. Apri PowerShell e lancia (può richiedere da 1 a diversi minuti: legge l'elenco di tutte le cartelle del tuo profilo e i nomi delle chiavi `HKCU\Software`, **mai** i valori né il contenuto dei file; non scrive nulla tranne il file indicato):

```
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\user-footprint.ps1" -Out "<cartella>\prima.txt"
```

**Cosa si deve vedere.** «Impronta scritta in …\prima.txt: N voci». Il file `prima.txt` esiste. Eventuali cartelle che Windows non lascia leggere compaiono come righe `DENIED` (normale).

Esito: ☐ OK ☐ NO — N voci: ________ Note: ____________________

## Passo 2. Firma dei file (solo se hai firmato)

**Se hai firmato** (certificato di Q-004; domanda ancora aperta): verifica il file di installazione prima di usarlo:

```
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\verify-signature.ps1" -Path "<cartella>\OCR2-0.6.0-setup.exe"
```

Si deve vedere `Status: Valid`, il tuo soggetto/impronta e l'ora della marca temporale. Incolla l'output nella matrice. Gli altri due file (`OCR2.exe` e `uninstall.exe` installati) si verificano al passo 3.

**Se non hai firmato:** scrivi nell'esito «non firmato». All'avvio del file di installazione Windows mostra «Windows ha protetto il PC» (SmartScreen): è atteso. Premi «Ulteriori informazioni», leggi il nome del file e premi «Esegui comunque». Annota che l'avviso è comparso.

Esito: ☐ firmato (Valid) ☐ non firmato, SmartScreen comparso ☐ altro: ____________________

## Passo 3. Installazione della 0.6.0

**Cosa fare.** Doppio clic su `OCR2-0.6.0-setup.exe`. Non serve cliccare altro: si apre una finestra con l'avanzamento («Estrazione di: …»); aspetta che finisca (circa 1 minuto). Se compare «OCR2 0.6.0 non è stato installato», fermati e vai a «Se qualcosa non va».

**Cosa si deve vedere.**

1. Nessuna richiesta di amministratore (nessun riquadro «Controllo account utente»).
2. Nel menu Start, cartella **OCR2** con tre voci: «OCR2», «Torna alla versione precedente», «Disinstalla OCR2».
3. In Esplora file, `%LOCALAPPDATA%\Programs\OCR2` (incolla l'indirizzo nella barra) contiene `versions\0.6.0`, `active.txt`, `OCR2.exe`, `uninstall.exe`.
4. `active.txt` (aprilo con il Blocco note) ha la riga 1 `0.6.0` e la riga 2 vuota.
5. Nessun file `opencv_videoio_ffmpeg*.dll`: in PowerShell
   `(Get-ChildItem "$env:LOCALAPPDATA\Programs\OCR2" -Recurse -Filter 'opencv_videoio_ffmpeg*').Count` → `0`.

Se hai firmato, verifica anche i due file installati (incolla gli output nella matrice):

```
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\verify-signature.ps1" -Path "$env:LOCALAPPDATA\Programs\OCR2\OCR2.exe"
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\verify-signature.ps1" -Path "$env:LOCALAPPDATA\Programs\OCR2\uninstall.exe"
```

Esito: ☐ OK ☐ NO — Durata installazione: ______ s. Note: ____________________

## Passo 4. Avvio dal menu Start e «Informazioni»

**Cosa fare.** Menu Start → OCR2 → «OCR2». Aspetta fino a 15 secondi.

**Cosa si deve vedere.** Si apre una finestra Edge **senza barra degli indirizzi** (finestra «app»). In fondo al contenuto della pagina (scorri in basso se serve) ci sono il pulsante «Esci» e il collegamento «Informazioni». Premi **Informazioni**; la pagina mostra:

| Riga | Valore atteso |
|---|---|
| Versione | `0.6.0` |
| Python | `3.13.x` |
| Motore OCR | `rapidocr-v6` (o simile, diverso da «disattivato») |
| Verifica del runtime | `verificato (N file, S s)` |

Annota **N** e **S** (S è il costo di avvio, circa 4 s; è un limite dichiarato, non un errore). Poi premi «Torna all'acquisizione temporanea».

Esito: ☐ OK ☐ NO — Versione: ______ Python: ______ N: ______ S: ______ s

## Passo 5. Un fascicolo sintetico e l'Archivio

**Cosa fare.**

1. Crea l'immagine di prova: apri **Paint**, scrivi con lo strumento testo righe inventate, per esempio «Scontrino di prova - Negozio Esempio - Totale 12,50 EUR - 15/11/2026», e salvala come `prova-ocr2.png` nella cartella di prova. Dati inventati, nessun dato personale.
2. In OCR2 (pagina «Carica nota spese e giustificativi»): «Documenti» → scegli `prova-ocr2.png` → «Carica e continua».
3. Se compare «Quale file è la nota spese?», scegli il file e premi «Conferma nota spese».
4. Nella pagina «Documenti collegati» premi **Salva in archivio** accanto al file.
5. Premi «Apri archivio locale».

**Cosa si deve vedere.** «Archivio documenti locale» con il documento `prova-ocr2.png` nell'elenco. Il documento si apre («Documento in archivio»). Se qualche passaggio ha un nome leggermente diverso, annotalo.

**R14: «Apri documento originale» non deve fermare l'app.**

1. Nella pagina del documento in archivio premi **Apri documento originale** (si apre l'immagine).
2. Aspetta **30 secondi** senza fare altro.
3. Premi **Indietro** (Alt + freccia a sinistra).

Si deve vedere la pagina dell'archivio che si ricarica e continua a rispondere (per esempio premi «Informazioni» e poi di nuovo Archivio). L'app **non deve essersi chiusa**. (Sull'immagine si può restare fino a 30 minuti, il tempo di inattività della sessione; oltre, l'app può fermarsi.)

Esito fascicolo/archivio: ☐ OK ☐ NO   Esito R14: ☐ app viva ☐ app chiusa — Note: ____________________

## Passo 5b. Sospensione del PC con OCR2 aperto (R40)

**Cosa fare.** Con la finestra di OCR2 aperta (pagina dell'archivio), metti il PC in sospensione: menu Start → Arresta → **Sospendi**. Aspetta **5 minuti**, poi riattiva il PC (tasto di accensione o un tasto della tastiera) e sblocca la sessione. Nella finestra di OCR2 premi un collegamento (per esempio «Informazioni», poi «Torna all'acquisizione temporanea»).

**Cosa si deve vedere.** Le pagine si aprono: l'app **risponde** e non si è chiusa durante la sospensione. Se il PC non ha «Sospendi» (o va in ibernazione), annota cosa hai usato.

Esito: ☐ app viva ☐ app chiusa — Durata della sospensione: ______ min. Note: ____________________

## Passo 6. «Esci»

**Cosa fare.** Nella finestra premi **Esci**.

**Cosa si deve vedere.** Compare «OCR2 si è chiuso. Puoi chiudere questa finestra.». La finestra **non si chiude da sola**: chiudila tu con la **X**. Il controllo riguarda il programma, non la finestra: entro circa 15 secondi dall'«Esci» in `%LOCALAPPDATA%\OCR2` il file `instance.json` non c'è più. In Gestione attività (Ctrl + Maiusc + Esc → scheda «Dettagli») non c'è più `pythonw.exe` con OCR2.

Esito: ☐ OK ☐ NO — Secondi dall'«Esci» a `instance.json` assente: ______

## Passo 7. Processo di Edge dopo «Esci»

**Cosa fare.** Prima chiudi la finestra con la X (passo 6). Poi in Gestione attività, scheda «Dettagli», cerca `msedge.exe` e guarda la colonna «Riga di comando» (clic destro sulle intestazioni → «Seleziona colonne» → «Riga di comando»).

**Cosa si deve vedere / annotare.** Può esserci un `msedge.exe` con `--no-startup-window` (avvio rapido di Edge sul profilo normale di Edge). **Non è un errore di OCR2** (è un limite dichiarato di Edge: «Avvio rapido» è un'impostazione tua e OCR2 non la cambia). Nessun `msedge.exe` deve avere `OCR2\edge-profile` nella riga di comando (guarda dopo 15 secondi: Edge chiude i suoi processi con qualche secondo di ritardo).

Esito: ☐ nessun processo Edge residuo ☐ presente un processo Edge «--no-startup-window» (limite di Edge) ☐ presente un processo con `OCR2\edge-profile` (NO)

## Passo 8. Chiusura della finestra e porta libera

**Cosa fare.**

1. Avvia di nuovo OCR2 dal menu Start e aspetta la finestra.
2. In PowerShell leggi la porta: `Get-Content "$env:LOCALAPPDATA\OCR2\instance.json"` (mostra `"port": <numero>`). Annota il numero.
3. Controlla che sia in ascolto (deve stampare una riga con indirizzo `127.0.0.1` e quella porta):
   `Get-NetTCPConnection -LocalPort <porta> -State Listen -ErrorAction SilentlyContinue`
   (in alternativa: `netstat -ano | findstr :<porta>`; cerca la riga con `LISTENING`; l'ultimo numero è il PID del processo).
4. Chiudi la finestra con la **X** in alto a destra (non «Esci»).
5. Aspetta. Il programma si ferma di solito dopo circa 10 secondi; se Windows non ha consegnato il segnale di chiusura, entro la scadenza del battito (180 secondi). Soglia unica di questa prova: **≤ 190 secondi**. Ogni 15 secondi ripeti il comando del punto 3.

**Cosa si deve vedere.** Alla fine il comando del punto 3 non stampa **nulla** (porta libera; con `-ErrorAction SilentlyContinue` non compare nessun errore rosso). Con `netstat` porta libera significa **nessuna riga con `LISTENING`**: righe `TIME_WAIT` possono restare anche per qualche minuto, sono normali. Inoltre `instance.json` non esiste più. Annota dopo quanti secondi (superato se ≤ 190 s).

Esito: ☐ OK ☐ NO — Secondi alla porta libera: ______

## Passo 9. Aggiornamento interrotto (con la 0.6.0 attiva)

**Cosa fare.** Con OCR2 chiuso: doppio clic su `OCR2-0.6.1-setup.exe`. Mentre scorre «Estrazione di: …» (la parte lunga dura circa un minuto), apri Gestione attività → «Dettagli», seleziona `OCR2-0.6.1-setup.exe` e premi **Termina attività** (conferma). Poi:

1. Apri `%LOCALAPPDATA%\Programs\OCR2\active.txt`: deve avere ancora la riga 1 `0.6.0`.
2. Avvia OCR2 dal menu Start → «Informazioni»: **Versione 0.6.0** e il documento di prova ancora in archivio. Poi «Esci».

Può restare una cartella `versions\0.6.1` incompleta: è normale, sarà cancellata dal passo successivo.

Esito: ☐ OK (0.6.0 resta attiva e funziona) ☐ NO — Note: ____________________

## Passo 10. OCR2 aperto durante un aggiornamento

**Cosa fare.** Avvia OCR2 (resta aperto). Doppio clic su `OCR2-0.6.1-setup.exe` e aspetta la fine.

**Cosa si deve vedere.** Un messaggio che finisce con «**Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova.**» («OCR2 0.6.1 non è stato installato. Resta attiva la versione precedente»). `active.txt` ha ancora `0.6.0`. Poi premi **Esci** in OCR2. Se hai chiuso la finestra con la X durante un'elaborazione o subito dopo un clic, OCR2 può restare acceso fino a 30 minuti: aspetta, oppure riavvia il PC, e ripeti il passo.

Esito: ☐ OK (messaggio visto, 0.6.0 attiva) ☐ NO — Testo del messaggio: ____________________

## Passo 11. Aggiornamento a 0.6.1 (i dati restano)

**Cosa fare.** Con OCR2 chiuso (verifica che non ci sia più `instance.json`): doppio clic su `OCR2-0.6.1-setup.exe` e aspetta la fine (circa 1 minuto).

**Cosa si deve vedere.**

1. `active.txt`: riga 1 `0.6.1`, riga 2 `0.6.0`.
2. `versions` contiene `0.6.0` e `0.6.1` (due versioni).
3. Avvia OCR2 dal menu Start → «Informazioni»: **Versione 0.6.1**.
4. «Apri archivio locale»: il documento `prova-ocr2.png` c'è ancora. Poi «Esci».

Esito: ☐ OK ☐ NO — Note: ____________________

## Passo 12. Reinstallare la versione già attiva

**Cosa fare.** Senza aprire OCR2: doppio clic su `OCR2-0.6.1-setup.exe`.

**Cosa si deve vedere.** Un messaggio che comincia con «Questa versione di OCR2 è già installata.» e indica cosa fare se OCR2 non funziona («Torna alla versione precedente» dal menu Start, oppure disinstallare mantenendo i dati e installare di nuovo). Nessuna modifica (`active.txt` uguale a prima).

Controllo facoltativo del codice di uscita (in modo silenzioso i messaggi **non** si vedono, è atteso): in PowerShell

```
Start-Process -FilePath "<cartella>\OCR2-0.6.1-setup.exe" -ArgumentList '/S' -Wait -PassThru | Select-Object ExitCode
```

Deve stampare `ExitCode 2`.

Esito: ☐ OK (messaggio visto) ☐ codice 2 ☐ NO

## Passo 13. Ritorno alla 0.6.0

**Non si reinstalla nulla.** Menu Start → OCR2 → «**Torna alla versione precedente**».

**Cosa si deve vedere.** Una finestra «OCR2» con «Versione attiva: 0.6.0». `active.txt`: riga 1 `0.6.0`, riga 2 `0.6.1`. Avvia OCR2 → «Informazioni»: **Versione 0.6.0**; l'archivio mostra ancora il documento. Poi «Esci».

Esito: ☐ OK ☐ NO — Note: ____________________

## Passo 14. Disinstallazione con OCR2 aperto, poi senza dati

**14a.** Avvia OCR2 (resta aperto). Menu Start → OCR2 → «Disinstalla OCR2». Se chiede di eliminare anche i dati, rispondi **No**. Atteso: la disinstallazione si rifiuta con «**Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova.**»; il programma e i dati restano. Poi premi **Esci** in OCR2. (Se la finestra era stata chiusa con la X durante un'elaborazione, il rifiuto può durare fino a 30 minuti: aspetta, oppure riavvia il PC.)

**14b.** Con OCR2 chiuso: «Disinstalla OCR2» → conferma. Alla domanda «Eliminare anche i dati di OCR2 (archivio e catalogo)?» premi **No**. Aspetta 15 secondi dopo che la finestra scompare.

**Cosa si deve vedere dopo 14b.**

1. `%LOCALAPPDATA%\Programs\OCR2` **non esiste più**.
2. La cartella OCR2 del menu Start è sparita.
3. `%LOCALAPPDATA%\OCR2` **esiste ancora** con `document-archive.sqlite3`, `edge-profile` e altri file.

Esito 14a: ☐ OK ☐ NO   Esito 14b: ☐ OK ☐ NO — Note: ____________________

## Passo 15. Reinstallazione: i dati si ritrovano

**Cosa fare.** Doppio clic su `OCR2-0.6.1-setup.exe` (installazione da zero: non è una reinstallazione della versione precedente). Avvia OCR2 → «Apri archivio locale».

**Cosa si deve vedere.** Il documento `prova-ocr2.png` è ancora nell'elenco. «Informazioni»: Versione 0.6.1. Poi «Esci».

Esito: ☐ OK ☐ NO — Note: ____________________

## Passo 16. Disinstallazione con dati

**Cosa fare.** Ricorda: **solo dati di prova su questo PC** (il documento inventato del passo 5). OCR2 chiuso. Menu Start → «Disinstalla OCR2». Alla domanda «Eliminare anche i dati di OCR2 (archivio e catalogo)?» premi **Sì**. Aspetta 15 secondi.

**Cosa si deve vedere.** Non esistono più `%LOCALAPPDATA%\Programs\OCR2`, `%LOCALAPPDATA%\OCR2` e la cartella OCR2 del menu Start. In Gestione attività non c'è alcun processo con OCR2 (`pythonw.exe` da `Programs\OCR2`, `msedge.exe` con `OCR2\edge-profile`).

Esito: ☐ OK ☐ NO — Note: ____________________

## Passo 17. Impronta dopo e confronto

**Cosa fare.**

```
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\user-footprint.ps1" -Out "<cartella>\dopo.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "<cartella>\user-footprint.ps1" -Compare "<cartella>\prima.txt" "<cartella>\dopo.txt" > "<cartella>\confronto-completo.txt"
```

**Cosa si deve vedere.** `confronto-completo.txt` elenca solo le differenze: `+` presente solo dopo, `-` solo prima, `~` file con dimensione diversa. Windows, Edge e gli altri programmi cambiano file anche da soli (cache, registri): troverai tante righe che **non** riguardano OCR2. Atteso per OCR2: **nessuna riga con «OCR2»** (tutto è stato rimosso al passo 16). Unica eccezione ammessa: una riga `D\tPrograms` (cartella `Programs` vuota): compare solo se `%LOCALAPPDATA%\Programs` non esisteva prima; l'installer la crea e la disinstallazione la lascia. Annotala come «Programs vuota». Se restano altre righe OCR2 (per esempio una cartella vuota), riportale nella matrice.

**Non condividere né committare `confronto-completo.txt`: può contenere nomi di altri programmi.** Passa alla sezione seguente.

Esito: ☐ nessuna riga OCR2 ☐ righe OCR2 rimaste (vedi file filtrato) — Note: ____________________

---

## Come condividere il confronto (solo le righe di OCR2)

Il file completo si rilegge **prima** di condividerlo; nel repository entrano solo le righe che riguardano OCR2.

1. Estrai le sole righe con «OCR2» (non distingue maiuscole) più l'eventuale riga della cartella `Programs` (vedi passo 17):

```
Select-String -Path "<cartella>\confronto-completo.txt" -Pattern 'OCR2|\tD\tPrograms$' | ForEach-Object { $_.Line } | Set-Content "<cartella>\confronto-ocr2.txt" -Encoding UTF8
```

2. Conta e guarda le righe **non** OCR2, senza copiarle:

```
(Select-String -Path "<cartella>\confronto-completo.txt" -Pattern 'OCR2|\tD\tPrograms$' -NotMatch | Where-Object { $_.Line -match '^[+~-] ' }).Count
(Select-String -Path "<cartella>\confronto-completo.txt" -Pattern 'OCR2|\tD\tPrograms$' -NotMatch | Where-Object { $_.Line -match '^[+~-] HKCU' }).Count
```

   Il primo numero è quante differenze ci sono fuori da OCR2 (rumore normale di Windows e di Edge), il secondo quante di queste sono chiavi di registro `HKCU`. Scrivili nella matrice: servono solo come numeri. Se il secondo numero non è zero, guarda a schermo quali chiavi sono (`Select-String … -Pattern 'HKCU'`): OCR2 non scrive nel registro, quindi non devono avere «OCR2» nel nome; se ne vedi una con «OCR2», è un problema da segnalare.
3. Apri `confronto-ocr2.txt` con il Blocco note e **rileggilo**: ogni riga è un percorso relativo (nessun nome utente, nessun contenuto). Se ci sono righe che non vuoi condividere, cancellale a mano. Un file vuoto significa «nessuna traccia di OCR2 rimasta».
4. Solo questo file (`confronto-ocr2.txt`) e la matrice compilata vanno consegnati per il repository (`docs/evidence/M6/`). `prima.txt`, `dopo.txt` e `confronto-completo.txt` restano sul PC pulito e si cancellano alla fine.

## Se qualcosa non va

- **L'installazione dice «non è stato installato».** Copia il messaggio. Verifica `active.txt`: deve avere ancora la versione precedente (o non esistere se era la prima installazione). Non provare altre cartelle.
- **Il percorso è troppo lungo / «File mancante».** Hai usato una cartella diversa dalla predefinita: disinstalla (se installato) e riparti con la cartella predefinita.
- **L'app non si apre entro 30 secondi.** Annota cosa si vede (finestra bianca, pagina «OCR2 non si avvia» nel browser predefinito). Se OCR2 non riesce ad avviarsi mostra quella pagina, con il motivo in una riga; i dettagli sono nel file `%LOCALAPPDATA%\OCR2\logs\launcher.log` (aprilo con il Blocco note e copia nella matrice l'ultima voce). Guarda se in Gestione attività c'è `pythonw.exe` (se sì, `Get-Content "$env:LOCALAPPDATA\OCR2\instance.json"` dà la porta). Poi disinstalla seguendo il passo 14.
- **Disinstallazione che sembra non fare nulla.** Il programma di disinstallazione ritorna subito: aspetta 15 secondi e ricontrolla. Se OCR2 è aperto compare «Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova.» Se OCR2 sembra chiuso ma il messaggio resta (finestra chiusa con la X durante un'elaborazione, entro 2 secondi da un clic o dopo aver letto un documento originale), aspetta fino a 30 minuti oppure riavvia il PC.
- **Per fermare la prova a metà.** Esci con «Esci», poi vai al passo 16 e al passo 17 (impronta dopo).
