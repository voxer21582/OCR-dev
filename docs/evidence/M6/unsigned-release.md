# Rilascio non firmato per il collaudo sull'altro PC

Data: 2026-11-16. Decisione: DEC-034 (nessun certificato, REQ-105 rinviato). Codice degli installer consegnati: commit `fa952c3`, dopo le correzioni della revisione (la prima consegna, da `0ea5abc`, è stata ritirata: vedi sotto).

## Opzione `OCR2_UNSIGNED_RELEASE`

`ocr2.nsi` accetta `/DOCR2_UNSIGNED_RELEASE`. Salta solo il controllo delle firme del runtime, gli agganci di firma e la verifica della firma dopo gli agganci. La parte non Authenticode di `verify-runtime-signatures.ps1` resta coperta: il manifest confronta ogni file di `app` e `python` e rifiuta i collegamenti, e `verify_payload.py`, eseguito da ogni build di rilascio, rifiuta elementi della radice del payload diversi da `app`, `python`, manifest, distinta e avvisi, oppure collegati. Il nome del file prodotto deve contenere «non-firmato» o «unsigned».

I test statici di `test_nsis_script.py` valutano i blocchi `!ifdef`/`!ifndef` e il controllo del nome per ogni configurazione: prima della modifica 3 falliti ([output](unsigned-release-red.txt)), dopo 21 passati ([output](unsigned-release-green.txt)); oggi 24 con il BOM e il nome. Il confronto riga per riga tra rilascio firmato e non firmato, dopo i controlli di compilazione, differisce solo per `BrandingText "OCR2 ${OCR2_VERSION} — non firmato"`.

Prove con NSIS 3.13 portabile (impronta come in `pins.json`):

| Configurazione | Esito |
|---|---|
| `OCR2_UNSIGNED_RELEASE` + `OCR2_CERT_THUMBPRINT` | errore, «cannot be combined with OCR2_CERT_THUMBPRINT» |
| `OCR2_UNSIGNED_RELEASE` + `OCR2_SIGN_COMMAND` | errore, «cannot be combined with OCR2_SIGN_COMMAND» |
| `OCR2_UNSIGNED_RELEASE` + `OCR2_TEST` | errore, «cannot be combined with OCR2_TEST» |
| `OCR2_UNSIGNED_RELEASE` con `OCR2_OUTPUT=OCR2-0.6.0-setup.exe` | errore, «requires an OCR2_OUTPUT name containing non-firmato or unsigned» |
| rilascio senza opzione né impronta | errore, «Release builds require the expected signing certificate thumbprint» |
| `OCR2_UNSIGNED_RELEASE`, `OCR2_VERSION=0.6.1` con payload 0.6.0 | errore, «Payload version does not match installer version» |
| `OCR2_UNSIGNED_RELEASE`, 0.6.0 e 0.6.1 | riuscito: `Processing script file: "ocr2.nsi" (UTF8)`, «Payload integrity and version verified», «Release inventory and notices match regenerated output» |

## Codifica del testo

La prima consegna era compilata da un `ocr2.nsi` senza BOM: `makensis` lo leggeva con la tabella codici ANSI (`(ACP)` nel registro di compilazione) e gli installer mostravano «â€”» al posto di «—» e lettere sbagliate in tutti i messaggi con «è», «« »» o «’», incluso quello di R38. Ora `ocr2.nsi` e `sign.ps1` hanno il BOM UTF-8 e un test lo richiede per ogni `.nsi`/`.ps1` dell'installer con caratteri non ASCII. Le stringhe dell'installer sono compresse e non si leggono dall'eseguibile: un programma di prova compilato con lo stesso `makensis`, stesso `Unicode true` e la stessa riga `BrandingText`, scrive le stesse stringhe in un file. Con il BOM: `(UTF8)`, «OCR2 0.6.0 — non firmato|non è stata cambiata|«Torna alla versione precedente»». Senza BOM: `(ACP)`, «OCR2 0.6.0 â€” non firmato|non Ã¨ stata cambiata|Â«Torna alla versione precedenteÂ»», cioè il difetto della prima consegna.

## Installer

Payload ricostruiti dal codice di `fa952c3` (contengono quindi anche la cattura dei messaggi limitata all'avvio) con `build_payload.py`, dall'archivio Python locale 3.13.18 (SHA-256 `a2aa39db…3041`, come nel pin) e dalle 22 wheel del lock, senza rete. Compilazione dalla cartella `installer` con `makensis /DOCR2_UNSIGNED_RELEASE`.

| File | Byte | SHA-256 | Firma |
|---|---|---|---|
| `OCR2-0.6.0-setup-non-firmato.exe` | 111.663.724 | `06e343a5efaf9bcda255fe1060c10f978fde4d9fc311d273ddd50719058199e7` | `NotSigned` |
| `OCR2-0.6.1-setup-non-firmato.exe` | 111.663.724 | `4de96fb033bf0b84f0c3fbb5285824c3bafaa7b303106435ba6e83297237c87c` | `NotSigned` |

Gli eseguibili non entrano nel repository; sono consegnati al proprietario con `SHA256SUMS.txt`, `LEGGIMI.txt`, `user-footprint.ps1` e una copia della [procedura](../../runtime/m6-lifecycle-procedure.md). I file della prima consegna (`OCR2-0.6.x-setup.exe`, testo con caratteri sbagliati) sono stati eliminati.

## Prova sul PC di sviluppo

**Gli installer di rilascio non sono stati eseguiti su questo PC.** NSIS ricava `$LOCALAPPDATA` e `$SMPROGRAMS` dalle cartelle note di Windows, non dalle variabili d'ambiente: un installer di prova minimo, avviato con `LOCALAPPDATA` e `APPDATA` puntati a una cartella temporanea, ha riportato comunque le cartelle reali del profilo. Il rilascio inoltre imposta sempre `$INSTDIR` a `$LOCALAPPDATA\Programs\OCR2` e ignora `/D=`. Eseguirlo avrebbe quindi scritto nella cartella reale del programma, nella cartella dati reale e nel menu Start; isolarlo richiederebbe di cambiare impostazioni di Windows.

Sostituto, ripetuto sui payload ricostruiti: installer `OCR2_TEST` compilati dagli **stessi** payload 0.6.0 e 0.6.1, eseguiti con `/S /D=<cartella temporanea>` e `LOCALAPPDATA` temporaneo per l'app:

| Passo | Esito |
|---|---|
| Installazione 0.6.0 | codice 0, `active.json` `{"active": "0.6.0", "previous": null}` |
| `Uninstall.exe /LAUNCH` (modalità prova) | versione attiva risolta: `0.6.0` |
| Avvio con `pythonw.exe --app-window` della versione installata | finestra Edge con profilo temporaneo; Informazioni: Versione 0.6.0, Python 3.13.18, Motore OCR RapidOCR 3.10.0, Verifica del runtime `verificato` |
| «Esci» (POST `/app/exit`) | 200, «OCR2 si è chiuso»; processo terminato, `instance.json` rimosso; nessun `launcher.log` |
| Aggiornamento a 0.6.1 | codice 0, `{"active": "0.6.1", "previous": "0.6.0"}` |
| Disinstallazione `/S /TEST-REMOVE-DATA` | codice 0; restano solo `test-launch-version.txt` (file della modalità prova) e il blocco `test-user-data.instance.lock` (DEC-033) |

La finestra Edge resta aperta dopo «Esci» (comportamento documentato); i suoi processi con profilo temporaneo sono stati chiusi a mano. Prima e dopo: la cartella reale del programma invariata (numero, dimensione e data dei file, impronta di `active.json`), cartella dati reale e blocco reale assenti, menu Start senza cartella OCR2.

Non provati qui, e quindi demandati al collaudo sull'altro PC: collegamenti del menu Start, domanda sui dati alla disinstallazione, cartella di installazione reale, avviso SmartScreen e testo «non firmato» nella finestra dell'installer.
