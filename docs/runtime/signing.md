# Firma del codice di OCR2 (REQ-105)

Procedura per il proprietario. La firma è facoltativa in costruzione: senza i parametri sotto, l'installer resta non firmato come oggi. Nessuna impronta, indirizzo di marca temporale o certificato è scritto nel repository.

## Cosa si firma

| File | Come |
|---|---|
| `OCR2-<versione>-setup.exe` (installer) | `!finalize` in `installer/ocr2.nsi` |
| `uninstall.exe` (generato dentro la costruzione dell'installer) | `!uninstfinalize` in `installer/ocr2.nsi` (NSIS 3.13) |
| `OCR2.exe` (avviatore) | `!finalize` in `installer/launcher.nsi` |

Gli `!finalize` chiamano `installer/sign.ps1` e sono presenti solo se la costruzione riceve impronta e indirizzo di marca temporale.

## Prerequisiti (sul PC di sviluppo del proprietario)

- Un certificato di firma del codice **nell'archivio dell'utente** (`Cert:\CurrentUser\My`), con chiave privata e uso «Firma del codice» (1.3.6.1.5.5.7.3.3). Gli script non importano, non creano e non installano certificati e non toccano gli archivi della macchina.
- L'indirizzo di un servizio di marca temporale (RFC 3161) scelto dal proprietario. Senza marca temporale la firma smette di essere valida alla scadenza del certificato.
- Il contenuto già costruito (`python installer/build_payload.py --version <X.Y.Z>`).

Impronta del certificato: `Get-ChildItem Cert:\CurrentUser\My | Select-Object Thumbprint, Subject, NotAfter`.

## Firmare

```
python installer/build_installer.py --version <X.Y.Z> --sign-thumbprint <IMPRONTA> --timestamp-url <INDIRIZZO>
```

Le due opzioni vanno indicate insieme. Se una firma non riesce, `sign.ps1` scrive `installer/out/sign-failed.txt` e la costruzione si ferma con errore (makensis da solo segnala solo un avviso). Al termine la costruzione esegue `verify-signature.ps1` su `OCR2.exe` e sull'installer e si ferma se lo stato non è `Valid`.

Per firmare a mano un file già costruito:

```
powershell -NoProfile -ExecutionPolicy Bypass -File installer\sign.ps1 -Installer <file.exe> -Thumbprint <IMPRONTA> -TimestampServer <INDIRIZZO>
```

`sign.ps1` usa `Set-AuthenticodeSignature -HashAlgorithm SHA256 -TimestampServer` ed esce con 0 solo se lo stato è `Valid`.

## Verificare

```
powershell -NoProfile -ExecutionPolicy Bypass -File installer\verify-signature.ps1 -Path <file.exe>
```

Stampa `Status`, soggetto e impronta del firmatario e l'ora della marca temporale (oppure «nessuna marca temporale»). Esce con 1 se lo stato non è `Valid`. È in sola lettura. Per `uninstall.exe`: dopo l'installazione, verificare `%LOCALAPPDATA%\Programs\OCR2\uninstall.exe` con lo stesso comando.

## Limiti dichiarati

- **I file `.py` non sono firmabili.** La loro integrità non viene da una firma ma dal `runtime-manifest.json` (impronte SHA-256 di ogni file), contenuto nell'installer firmato e controllato all'avvio e dopo l'installazione. Chi può scrivere nel profilo dell'utente può comunque alterare i file dell'utente (R5).
- I binari di Python e delle wheel (`.exe`, `.dll`, `.pyd`) **mantengono le firme dei loro autori, dove presenti**; OCR2 non li ri-firma.
- Un **certificato autofirmato** funziona solo se viene aggiunto all'archivio certificati del PC che verifica. Sul PC di destinazione questo è vietato da V4 (nessuna modifica a registro, impostazioni o archivi di sistema): su quel PC la firma risulterebbe `UnknownError`/non attendibile. Per questo la scelta del certificato è la domanda aperta Q-004.
- Il testo di `verify-signature.ps1` sull'ora della marca temporale non è stato provato su un file firmato (manca un certificato): vedi `docs/evidence/M6/signature.md`.
