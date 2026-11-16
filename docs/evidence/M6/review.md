# M6 — Revisione indipendente

Le revisioni sono state fatte da agenti automatici separati, in sola lettura sul diff, senza contesto del lavoro. Il limite di questa revisione è dichiarato secondo DEC-008: non sostituisce le prove del proprietario sul PC pulito. Il registro completo (ruling, riesami, minori) è nel libro mastro del lavoro (`.superpowers/sdd/2026-11-15-m6-applicazione-installabile/progress.md`); qui è riassunto.

## 1. Revisioni per compito e correzioni

Ogni compito ha avuto una revisione sul suo diff e, se servito, da 1 a 2 giri di correzione. Tutti i compiti si sono chiusi con revisione pulita.

| Compito | Esito della revisione | Correzioni |
|---|---|---|
| 1 Documenti di avvio | 1 importante: titolo di STATUS vecchio e domanda Q-003 non aggiornata | 1 giro, corretto |
| 2 Presenza delle finestre e durata | 1 importante: una finestra morta rimasta in elenco saltava i 10 s di tolleranza | 1 giro, corretto |
| 3 Rotte `/app/*` | 1 importante: token CSRF esposto nella risposta 403 per Host errato (DNS rebinding); inoltre navigazione verso pagine senza script (R12, R14) | 1 giro, 3 punti corretti (R15) |
| 4 Istanza unica e finestra Edge | 2 importanti: l'avviatore in attesa non riprovava; mancava R16 | 1 giro, 5 punti corretti (R17); R18 accettato |
| 5 Verifica del runtime | 2 importanti: junction non rifiutate; glob FFmpeg sensibile alle maiuscole; R19 | 2 giri, corretti (R21) |
| 6 Contenuto dell'installer | nessun importante; R22, R23, R24 | 1 giro per R23 |
| 7 SBOM e notice | arresto sulla licenza mancante di due pacchetti (R25, R26) | 1 giro, corretto |
| 8 Installer NSIS | 1 importante: un errore nella pulizia dopo il cambio di stato faceva cancellare dall'installer la versione appena attivata | 1 giro, corretto |
| 9 Firma | 1 importante: un errore di firma prima dell'esecuzione dello script lasciava un `uninstall.exe` non firmato in una build «riuscita» | 1 giro, corretto (hook con `= 0`) |
| 10 Procedura per il proprietario | non conformità R29 (mancavano `_?=` e avviso 9000); passi 6/7 e 8 errati | 1 giro, 3 punti corretti (R35) |

## 2. Revisione finale dell'intero ramo

Esito: **con correzioni** (revisore Opus, `03cdab9..eca78c3`; solo `3a59153..eca78c3` è M6; la PR va fatta contro `origin/main`). **Nessun problema critico, 5 importanti:**

1. manifest mancante in una copia installata: la verifica veniva saltata (R37);
2. consiglio di riparazione che non funziona: «Reinstalla» è rifiutato dall'installer (R38);
3. errori di avvio silenziosi sotto `pythonw` (R39);
4. la sospensione del PC fermava il server (R40);
5. la vista di un documento originale oltre 180 s fermava l'app (R41).

## 3. Giro di correzioni

10 punti, commit `eca78c3..167c895` (5 importanti e 5 minori, R42), 1077 test passati, 3 saltati (prima 1046). Dettaglio in `final-fix-report.md`:

| # | Punto | Commit |
|---|---|---|
| 1 | Copia installata senza manifest: rifiuto, esce con 2 (R37) | `c26b07f` |
| 2 | Consigli di riparazione che funzionano (R38) | `d1e27b8` |
| 3 | Errori di avvio visibili: pagina e `launcher.log` (R39) | `30a5a62` |
| 4, 5 | Sospensione (R40); finestre ripristinate con scadenza di 30 minuti (R41) | `b69d612` |
| 6 | La sonda `/app/info` non è attività; testo del rifiuto R8 | `605beb3` |
| 7 | `uninstall.exe` si ferma se la cartella non è di OCR2 | `c3f41e8` |
| 8 | Nessun controllo dell'app nei download | `614c591` |
| 9 | L'installer controlla che OCR2 sia chiuso prima di toccare le cartelle (comando `check-closed`) | `94775a9` |
| 10 | Procedura: «Esci» e «Informazioni» in fondo alla pagina | `167c895` |

## 4. Riesame mirato (`eca78c3..167c895`)

I punti 1–10 sono tutti **risolti**. Un **nuovo importante**: le pagine di elaborazione si aggiornano da sole ogni 2 s, quindi chiudere con la X durante l'elaborazione conta come «navigazione» e lascia il programma acceso fino a 30 minuti; il consiglio «attendi qualche secondo» è sbagliato in quel caso. Deciso in R46: nessun secondo giro di correzioni (rientra nel limite di R41, nessun compito dipende da esso); il limite e il consiglio sono dichiarati in [`acceptance.md`](acceptance.md) e nella procedura. Resta da decidere con il proprietario il seguito (scadenza di 30 minuti solo per le ripristinazioni non HTML).

## 5. Minori rimasti, in ordine di intervento

La classificazione è mia, dal libro mastro: il libro mastro dice solo che questi restano rinviati.

### Prima dell'unione (solo documentazione, già fatto)

- app-window.md 4c rimanda a R18 come limite dichiarato (compito 4).
- Archivio più recente: `runtime-error.html` nella cartella dei dati, dichiarato (compito 8).
- R45: avviso «Reinstalla OCR2 con l'installer» di `launcher.nsi`, dichiarato con il consiglio giusto.
- Compito 9: la dicitura sul contenuto 0.6.2 della relazione va letta così: il contenuto verifica.
- Compito 10: ripetere «solo dati di prova» prima del passo 16 e formulazioni della procedura (Gestione attività, finestra del prompt): da rivedere con la compilazione della matrice.

### Dopo l'unione (codice e hardening, nessun impatto sull'accettazione)

- Compito 2: eccezione di `stop_server` silenziosa; `poll_seconds <= 0` non validato; test «stop una volta sola» debole; test della scadenza a 180 s nel ramo di tolleranza.
- Compito 3: `activity()` ripristina identificatori mai battuti (commento); una POST cross-site rifiutata conta come attività.
- Compito 4: `running_instance` con timeout per socket ma senza scadenza totale.
- Compito 5: misurare la verifica sul contenuto reale (fatto in `payload.md`); chiave di manifest molto lunga ripetuta per intero su stderr e nella pagina di errore.
- Compito 6: `pip` non isolato; nessun controllo che l'interprete sia CPython 3.13 win-amd64; una build fallita lascia `out/<versione>` parziale e l'errore di rete condivide il codice 3 con l'impronta errata.
- Compito 7: ricerca della licenza nel `RECORD` limitata a site-packages e senza test su `../`; un pacchetto con solo AUTHORS/NOTICE supera il controllo; test di determinismo sullo stesso contenuto; altri dettagli (`License: UNKNOWN`, extra nel lock).
- Compito 8: cancellazione della versione precedente (obiettivo di ritorno) prima del controllo R8 in alcuni casi; `_refuse_while_running` con LOCALAPPDATA non impostata; `chmod` che segue i collegamenti; prefisso `OCR2_TEST /D=` che accetta `..`; `activate` con `active.txt` corrotto; fallimento di `RMDir /r` non segnalato; percorso «attivo ma problema» che salta i collegamenti.
- Compito 9: espansione `%VAR%` di cmd nell'URL della marca temporale; apice nei percorsi; marcatore di riserva; nessun test del marcatore vecchio; messaggio del marcatore non mostrato se `makensis` si interrompe.
- Compito 10: `user-footprint.ps1` (segue una junction se `GetAttributes` fallisce; percorsi lunghi segnati come negati; commento di ordinamento; `-Out` relativo); chiave di prova sotto `HKCU\Software` reale.
- Revisione finale: reinstallare la versione precedente cancella l'obiettivo di ritorno prima dell'estrazione; un'attivazione fallita lascia la riga 2 di `active.txt` pendente; `ReadActive` dell'avviatore accetta qualsiasi cifra o punto; `resume_after_suspend` riporta le finestre ripristinate a 1800 s; `check-closed` usa il Python della versione attiva (una versione attiva corrotta impedisce di installarne una nuova); avvisi di catalogo e di runtime OCR non mostrati sotto `pythonw`.

## 6. Ruling R1–R46 e costo se sbagliati

| Id | Decisione | Costo se sbagliata |
|---|---|---|
| R1 | `AppLifetime` ha un thread di guardia; `request_exit()` imposta solo un flag e il thread ferma il server dopo la risposta | blocco su «Esci»; lo avrebbe visto il test con server vero |
| R2 | `AppInfo` ha `instance_id`; `/app/info` emette la meta `ocr2-instance` e `running_instance` la confronta | piccolo ritocco dell'interfaccia |
| R3 | `/app/info` sempre servita; senza `app_info` mostra versione, Python, OCR «disattivato», runtime «non verificato» | nessuno rilevante |
| R4 | cartella del programma = `versions\<v>\`; senza manifest, avvio da sorgenti (poi superata da R37) | vedi R37 |
| R5 | la verifica ignora i file in `__pycache__`; avvio con `-B` | un `.pyc` piantato non viene rilevato; limite documentato |
| R6 | `active.txt` al posto di `active.json`; `OCR2.exe` (NSIS) legge `active.txt`; `OCR2.exe /rollback` | un altro script NSIS da firmare |
| R7 | l'installer cancella una `versions\<v>` non attiva prima di estrarre; la versione già attiva è rifiutata | riparazione sul posto non disponibile |
| R8 | aggiornamento, disinstallazione e potatura rifiutati mentre OCR2 risponde | il rifiuto può durare fino a 30 minuti (R41, R46) |
| R9 | script e procedura ora; Q-004 al proprietario | l'evidenza della firma resta in attesa |
| R10 | la matrice sull'altro PC è del proprietario | evidenza dei punti sul PC pulito in attesa |
| R11 | impronta SHA-256 dell'embeddable da python.org; NSIS calcolata al download | fonte e limite registrati |
| R12 | una richiesta vicino a una chiusura ripristina la finestra chiusa (R7 non toccato) | una finestra chiusa insieme a una richiesta resta fino a 180 s (poi 30 minuti, R41) |
| R13 | beacon di chiusura come `URLSearchParams`; `/app/exit` e `/app/closing` richiedono CSRF | nessuno (più severo) |
| R14 | simmetrico a R12: una chiusura entro 2 s da un'attività è navigazione | una chiusura vera coincidente resta fino a 180 s (poi 30 minuti) |
| R15 | inclusi i minori 1 e 3 del compito 3 | nessuno |
| R16 | aggiunto `--disable-background-mode` agli argomenti di Edge | un flag in più |
| R17 | inclusi i minori 3, 5, 6 del compito 4 | nessuno |
| R18 | il processo `--no-startup-window` dopo la chiusura è l'avvio rapido di Edge: accettato e dichiarato | il proprietario può volere un'altra impostazione di Edge in seguito |
| R19 | l'avviatore controlla prima `running_instance`; verifica solo se serve il processo | nessuno rilevante |
| R20 | pagina di errore nel browser predefinito (URI file); immagine sintetica PIL accettata | nessuno rilevante |
| R21 | inclusi minori 3 e 4 del compito 5 | nessuno |
| R22 | CPython 3.13.17 embeddable (la 3.13.18 è solo sorgente) | nessuno |
| R23 | la versione di build è scritta nel pacchetto copiato; `__version__` è 0.6.0 | piccolo |
| R24 | verifica di circa 4 s per avvio accettata; M7 decide | tempo di avvio più lungo |
| R25 | notice: accettati i file di licenza installati nella cartella del pacchetto e elencati nel `RECORD` | nessuno (usa i testi originali) |
| R26 | testo Apache-2.0 per flatbuffers da un'altra wheel, con intestazione (provvisorio, conferma del proprietario) | togliere o sostituire un file |
| R27 | tetto di profondità del percorso (circa 109 caratteri) | installazione che fallisce in una cartella `/D` molto profonda |
| R28 | `abspath` al posto di `resolve()` più `_resolved()` senza `\\?\` | regressione di R4 o delle junction |
| R29 | uscita 2 se già attiva; messaggi nascosti in silenzioso; `uninstall.exe` asincrono; avviso `makensis` 9000 | limiti dichiarati |
| R30 | `activate` rifiuta mentre gira; il disinstallatore cancella i propri file e `RMDir` della base vuota | nessuno (più sicuro di `RMDir /r`) |
| R31 | firma opzionale con argomenti di build (impronta e URL), mai nel repository | il proprietario deve rilanciare la build con gli hook |
| R32 | resta vuota la cartella `%LOCALAPPDATA%\Programs` dopo la disinstallazione | una cartella vuota |
| R33 | ordine dei passi della procedura (aggiornamento interrotto prima di quello vero) | nessuno |
| R34 | PNG con testo inventato disegnato dal proprietario con Paint | nessuno |
| R35 | soglia unica di 190 s per la porta libera | il proprietario aspetta 10 s in più |
| R36 | prima revisione finale e correzioni, poi i documenti | nessuno |
| R37 | «installata» si decide dalla struttura delle cartelle; manifest mancante = uscita 2 con pagina di errore (supera R4) | avvii da strutture insolite rifiutati |
| R38 | testi di errore e di R7 con i rimedi che funzionano; nessuna riparazione sul posto in M6 | la riparazione sul posto passa a M7 |
| R39 | in modalità app, ogni errore di avvio mostra una pagina generica e scrive `launcher.log` | un file di log nella cartella dei dati |
| R40 | la guardia riconosce una sospensione e sposta avanti le battute di un periodo di scadenza | il server resta fino a 180 s dopo una sospensione con la finestra chiusa |
| R41 | finestre ripristinate per navigazione con scadenza di 30 minuti | una costante da ripristinare; il proprietario è informato |
| R42 | minori corretti nel giro: `/app/info`, `uninstall.exe`, download, ordine di R7, testo di «Esci» | nessuno |
| R43 | `/app/info` conta per la navigazione ma non per l'attività (scostamento dal punto 6) | raro: chiusura entro 2 s da un controllo dell'installer resta fino a 30 minuti |
| R44 | l'elemento 9 richiede `check-closed` nella versione attiva; mai distribuita una build precedente | le installazioni di prova vecchie vanno prima disinstallate |
| R45 | avviso di `launcher.nsi` («Reinstalla…») lasciato e dichiarato | in un'installazione rotta il consiglio è inesatto |
| R46 | nessun secondo giro: chiudere durante un'elaborazione conta come navigazione; limite e consiglio dichiarati; seguito al proprietario | chi chiude durante un'elaborazione aspetta fino a 30 minuti per aggiornare o disinstallare |
