# Rilascio non firmato per il collaudo sull'altro PC

Data: 2026-11-16. Decisione: DEC-034 (nessun certificato, REQ-105 rinviato). Codice: commit `0ea5abc`.

## Opzione `OCR2_UNSIGNED_RELEASE`

`ocr2.nsi` accetta `/DOCR2_UNSIGNED_RELEASE`. Salta solo il controllo delle firme del runtime, gli agganci di firma e la verifica della firma dopo gli agganci; gli altri controlli di rilascio restano. I test statici di `test_nsis_script.py` valutano i blocchi `!ifdef`/`!ifndef` per ogni configurazione: prima della modifica 3 falliti ([output](unsigned-release-red.txt)), dopo 21 passati ([output](unsigned-release-green.txt)). Suite Windows completa: 1.113 test passati, 3 saltati, 398 sottocasi. Il confronto riga per riga tra rilascio firmato e non firmato, dopo i controlli di compilazione, differisce solo per `BrandingText "OCR2 ${OCR2_VERSION} — non firmato"`.

Prove con NSIS 3.13 portabile (impronta come in `pins.json`):

| Configurazione | Esito |
|---|---|
| `OCR2_UNSIGNED_RELEASE` + `OCR2_CERT_THUMBPRINT` | errore, «cannot be combined with OCR2_CERT_THUMBPRINT» |
| `OCR2_UNSIGNED_RELEASE` + `OCR2_SIGN_COMMAND` | errore, «cannot be combined with OCR2_SIGN_COMMAND» |
| `OCR2_UNSIGNED_RELEASE` + `OCR2_TEST` | errore, «cannot be combined with OCR2_TEST» |
| rilascio senza opzione né impronta | errore, «Release builds require the expected signing certificate thumbprint» |
| `OCR2_UNSIGNED_RELEASE`, `OCR2_VERSION=0.6.1` con payload 0.6.0 | errore, «Payload version does not match installer version» |
| `OCR2_UNSIGNED_RELEASE`, 0.6.0 e 0.6.1 | riuscito: «Payload integrity and version verified», «Release inventory and notices match regenerated output» |

## Installer

Payload costruiti con `build_payload.py` dall'archivio Python locale 3.13.18 (SHA-256 `a2aa39db…3041`, come nel pin) e dalle 22 wheel del lock, senza rete. Compilazione dalla cartella `installer` con `makensis /DOCR2_UNSIGNED_RELEASE`.

| File | Byte | SHA-256 | Firma |
|---|---|---|---|
| `OCR2-0.6.0-setup.exe` | 111.663.359 | `387126b4f5c752304bf3bd456082441003367fac91ba806307471cede5c4d90a` | `NotSigned` |
| `OCR2-0.6.1-setup.exe` | 111.663.327 | `75888a7d1fafcf659e27f518b08c9b25919862da3196a00b73beb72fa89a1477` | `NotSigned` |

Gli eseguibili non entrano nel repository; sono consegnati al proprietario con `SHA256SUMS.txt`, `LEGGIMI.txt`, `user-footprint.ps1` e una copia della [procedura](../../runtime/m6-lifecycle-procedure.md).

## Prova sul PC di sviluppo

**Gli installer di rilascio non sono stati eseguiti su questo PC.** NSIS ricava `$LOCALAPPDATA` e `$SMPROGRAMS` dalle cartelle note di Windows, non dalle variabili d'ambiente: un installer di prova minimo, avviato con `LOCALAPPDATA` e `APPDATA` puntati a una cartella temporanea, ha riportato comunque le cartelle reali del profilo. Il rilascio inoltre imposta sempre `$INSTDIR` a `$LOCALAPPDATA\Programs\OCR2` e ignora `/D=`. Eseguirlo avrebbe quindi scritto nella cartella reale del programma, nella cartella dati reale e nel menu Start; isolarlo richiederebbe di cambiare impostazioni di Windows.

Sostituto: installer `OCR2_TEST` compilati dagli **stessi** payload 0.6.0 e 0.6.1, eseguiti con `/S /D=<cartella temporanea>` e `LOCALAPPDATA` temporaneo per l'app:

| Passo | Esito |
|---|---|
| Installazione 0.6.0 | codice 0, `active.json` `{"active": "0.6.0", "previous": null}` |
| `Uninstall.exe /LAUNCH` (modalità prova) | versione attiva risolta: `0.6.0` |
| Avvio con `pythonw.exe --app-window` della versione installata | finestra Edge con profilo temporaneo; Informazioni: Versione 0.6.0, Python 3.13.18, Motore OCR RapidOCR 3.10.0, Verifica del runtime `verificato` |
| «Esci» (POST `/app/exit`) | 200, «OCR2 si è chiuso»; processo terminato, `instance.json` rimosso |
| Aggiornamento a 0.6.1 | codice 0, `{"active": "0.6.1", "previous": "0.6.0"}` |
| Disinstallazione `/S /TEST-REMOVE-DATA` | codice 0; restano solo `test-launch-version.txt` (file della modalità prova) e il blocco `test-user-data.instance.lock` (DEC-033) |

La finestra Edge resta aperta dopo «Esci» (comportamento documentato); i suoi processi con profilo temporaneo sono stati chiusi a mano. Prima e dopo: la cartella reale del programma invariata (numero, dimensione e data dei file, impronta di `active.json`), cartella dati reale e blocco reale assenti, menu Start senza differenze.

Non provati qui, e quindi demandati al collaudo sull'altro PC: collegamenti del menu Start, domanda sui dati alla disinstallazione, cartella di installazione reale, avviso SmartScreen e testo «non firmato».
