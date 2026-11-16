# M6 — Accettazione: criteri ed evidenze

Commit di riferimento: `167c895` (branch `claude/m6-installabile`). La suite locale ha dato **1077 test passati, 3 saltati** e 398 sottocasi. Il lavoro sul codice e le revisioni sono finiti ([`review.md`](review.md)); **M6 non è accettata**: le prove sul PC pulito, la firma e alcune conferme spettano al proprietario (sezione «In attesa del proprietario»).

Livelli di prova:
- **`SYN-CI`**: test sintetici in CI su Ubuntu e Windows;
- **`LOCAL-RUN`**: prova sul PC di sviluppo, con dati sintetici e build di prova dell'installer (`-DOCR2_TEST`, nessun collegamento nel menu Start);
- **`OWNER-PC`**: prova che solo il proprietario può eseguire (PC pulito, firma). **In attesa**: non è stata eseguita e non è dichiarata superata.

| Requisito | Criterio | Esito | Evidenza |
|---|---|---|---|
| REQ-100 | L'app si apre in una finestra di Edge in modalità app, senza modificare impostazioni di Edge o Windows | `SYN-CI` + `LOCAL-RUN`; confronto prima/dopo sul PC pulito: `OWNER-PC` — in attesa | `test_app_window`, `test_app_instance`; prova reale con Edge, istanza unica e chiusura ([`app-window.md`](app-window.md)); impronta prima/dopo dell'utente nella [procedura](../../runtime/m6-lifecycle-procedure.md), passi 1 e 17 ([`lifecycle-matrix.md`](lifecycle-matrix.md)) |
| REQ-101 | «Esci» e spegnimento automatico del server quando nessuna finestra è collegata; porta libera e processo terminato | `SYN-CI` + `LOCAL-RUN`; porta libera sull'immagine: `OWNER-PC` — in attesa | `test_app_lifetime` (presenza, finestre, sospensione), `test_app_window_routes` (`/app/exit`, `/app/closing`, CSRF, Origin); server fermato 10,2 s dopo la chiusura e dopo «Esci» ([`app-window.md`](app-window.md)); procedura, passi 5b, 7 e 8 |
| REQ-102 | Installer per utente, offline, senza amministratore (NSIS + Python embeddable); elenco di file e voci create | `SYN-CI` (script statici) + `LOCAL-RUN` (build di prova); installazione su PC pulito (DEC-007): `OWNER-PC` — in attesa | `test_nsis_script`, `test_build_payload`; installazione, aggiornamento e disinstallazione con il build di prova ([`installer-dev-pc.md`](installer-dev-pc.md), [`procedure-dry-run.md`](procedure-dry-run.md)); contenuto ([`payload.md`](payload.md)); elenco dei file e delle voci per utente: `user-footprint.ps1` nella procedura |
| REQ-103 | Runtime verificato (impronte di wheel e modelli, notice); nessun download | `SYN-CI` + `LOCAL-RUN`; verifica sul PC pulito: `OWNER-PC` — in attesa | `test_runtime_manifest` (manifest, file in più, junction, installazione senza manifest rifiutata, R37); verifica all'avvio sul contenuto reale, circa 4–7 s ([`payload.md`](payload.md)); OCR senza il DLL FFmpeg ([`ocr-without-ffmpeg.txt`](ocr-without-ffmpeg.txt)) |
| REQ-104 | Aggiornamento, recupero da aggiornamento interrotto, ritorno alla versione precedente, disinstallazione; i dati restano se l'utente non li toglie | `SYN-CI` + `LOCAL-RUN`; matrice sull'altro PC: `OWNER-PC` — in attesa | `test_install_state` (stato, rollback, interruzioni, rifiuto con OCR2 aperto), `test_nsis_script`; ciclo completo sul PC di sviluppo ([`installer-dev-pc.md`](installer-dev-pc.md), [`procedure-dry-run.md`](procedure-dry-run.md)); matrice vuota da compilare: [`lifecycle-matrix.md`](lifecycle-matrix.md) |
| REQ-105 | Installer e binari firmati dal proprietario; la firma si verifica; l'evidenza registra chi e quando | `OWNER-PC` — **in attesa di Q-004** (nessun file firmato) | Script e procedura pronti, con arresto della build se la firma fallisce: [`signing.md`](../../runtime/signing.md), `test_nsis_script`, `test_build_payload`; modulo da completare dopo la firma: [`signature.md`](signature.md) |
| REQ-106 | Un collegamento nel menu Start per l'utente; versione e identità del runtime visibili nell'app | `SYN-CI` (pagina «Informazioni») + `LOCAL-RUN`; collegamento nel menu Start: `OWNER-PC` — in attesa | `test_app_window_routes` (`/app/info`: versione, Python, motore OCR, esito della verifica); prova reale ([`app-window.md`](app-window.md)); il build di prova non crea collegamenti: controllo nella procedura ([`lifecycle-matrix.md`](lifecycle-matrix.md)) |
| REQ-107 | SBOM e notice di licenza nell'installer; decisione su FFmpeg (Q-001) | `SYN-CI` + `LOCAL-RUN`; conferma della licenza flatbuffers (R26): `OWNER-PC` — in attesa | `test_sbom_and_notices`; SBOM e notice generati dai lock sul contenuto reale ([`notices.md`](notices.md)); FFmpeg escluso come deciso (DEC-030) e OCR provato senza il DLL ([`ocr-without-ffmpeg.txt`](ocr-without-ffmpeg.txt)) |

**Decisioni:** DEC-030 (FFmpeg), DEC-031 (backup portabile), DEC-032; R-001 e R-002 approvate dal proprietario. Python embeddable fissato a CPython 3.13.17 (R22: la 3.13.18 non ha l'embeddable).

## Limiti dichiarati

- **R18:** dopo la chiusura, l'avvio rapido di Edge lascia un processo in background (`--no-startup-window`) sul profilo predefinito. Non è un'impostazione che OCR2 cambia ([`app-window.md`](app-window.md), 4c).
- **R20:** la pagina di errore dell'avvio si apre nel browser predefinito.
- **R24:** il controllo di integrità all'avvio costa circa 4–7 s (a volte fino a 10); la misura delle prestazioni spetta a M7.
- **R26:** il testo della licenza di flatbuffers è provvisorio (la wheel non ne contiene uno) e va confermato dal proprietario.
- **R27:** il percorso di installazione, fino a `versions\<v>\`, può essere lungo al massimo 109 caratteri.
- **R29:**
  - installare la versione già attiva termina con codice 2;
  - in modalità silenziosa (`/S`) i messaggi non si vedono;
  - `uninstall.exe` ritorna subito; con `_?=` aspetta la fine;
  - `makensis` segnala l'avviso 9000.
- **R32:** dopo la disinstallazione può restare una cartella `%LOCALAPPDATA%\Programs` vuota (è la cartella condivisa dei programmi per utente).
- **R41, R43, R46:** OCR2 può restare acceso fino a 30 minuti:
  - dopo la lettura di un documento originale;
  - se la finestra è chiusa con la X entro 2 s da un clic o dal controllo dell'installer;
  - se la finestra è chiusa durante un'elaborazione, perché quelle pagine si aggiornano da sole.

  Intanto installare o disinstallare viene rifiutato con «Chiudi la finestra di OCR2…». Consiglio: aspettare fino a 30 minuti, oppure riavviare il PC.
- **R40:** la sospensione del PC è tollerata; una finestra chiusa durante la sospensione può restare fino a un periodo di scadenza.
- **Archivio più recente:** con un archivio più recente dell'app, l'avvio scrive `runtime-error.html` nella cartella dei dati.
- **Ambito dell'integrità:** il controllo copre la corruzione del contenuto, **non** la manomissione. `OCR2.exe`, `uninstall.exe`, `active.txt` e il manifest stesso non sono coperti; l'integrità viene dalla firma del proprietario.
- **R45:** l'avviatore dice ancora «Reinstalla OCR2 con l'installer» quando mancano `active.txt` o `pythonw.exe`. Il rimedio giusto è disinstallare mantenendo i dati e reinstallare.
- **Arresto prima dell'avvio:** un arresto prima che `main()` del launcher giri non mostra nulla sotto `pythonw`.
- **Posizione di «Esci»:** «Esci» e «Informazioni» stanno in fondo alla pagina (le pagine R7/R8 non cambiano impaginazione).
- **Percorsi lunghi:** i percorsi lunghi di Windows sono disattivati: per questo esiste il limite di R27.

## In attesa del proprietario

1. **Q-004:** quale certificato; poi firma e `verify-signature` (REQ-105), da registrare in [`signature.md`](signature.md).
2. **Matrice sul PC pulito:** eseguire [`m6-lifecycle-procedure.md`](../../runtime/m6-lifecycle-procedure.md) e compilare [`lifecycle-matrix.md`](lifecycle-matrix.md), compresi i passi R14 e della sospensione (5b).
3. **R26:** confermare il testo della licenza di flatbuffers (`installer/licenses/flatbuffers-25.12.19.txt`).
4. **OK esplicito sulle modifiche accanto all'archivio (R7) e all'export (R8).** `local_document_store.py` non è modificato. Cambiano:
   - `__main__._open_archive` legge la versione dello schema dell'archivio (importa `_SCHEMA_VERSION` e `StoreSchemaError` dell'archivio e legge l'intestazione SQLite) e scrive `runtime-error.html`;
   - in modalità app, `_page` aggiunge il modulo «Esci», il token di sessione e lo script della finestra anche alle pagine dell'archivio e dell'export (mai ai download).
5. **Seguito di R46:** decidere se limitare la scadenza di 30 minuti alle sole ripristinazioni non HTML (così chiudere durante un'elaborazione torna a 180 s).
6. **Issue #9:** si chiude solo con il sì del proprietario.

**Revisione indipendente:** [`review.md`](review.md): nessun problema critico; 5 importanti, corretti in `eca78c3..167c895`; la nuova revisione ha trovato un ulteriore importante (R46), accettato come limite.
