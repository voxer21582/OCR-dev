# M6 — Firma del codice (REQ-105)

**Stato: FIRMA IN ATTESA del certificato del proprietario (Q-004, aperta).** Nessun file è stato firmato; questa pagina è il modulo da completare dopo la firma. Procedura: [`docs/runtime/signing.md`](../../runtime/signing.md).

## Da completare dal proprietario

| Campo | Valore |
|---|---|
| Chi ha firmato | |
| Quando (data e ora) | |
| Versione firmata | |
| Impronta del certificato | |
| Servizio di marca temporale | |

Comandi:

```
python installer/build_installer.py --version <X.Y.Z> --sign-thumbprint <IMPRONTA> --timestamp-url <INDIRIZZO>
powershell -NoProfile -ExecutionPolicy Bypass -File installer\verify-signature.ps1 -Path installer\out\OCR2-<X.Y.Z>-setup.exe
powershell -NoProfile -ExecutionPolicy Bypass -File installer\verify-signature.ps1 -Path installer\out\launcher\OCR2.exe
powershell -NoProfile -ExecutionPolicy Bypass -File installer\verify-signature.ps1 -Path "%LOCALAPPDATA%\Programs\OCR2\uninstall.exe"   (dopo l'installazione)
```

Output di `verify-signature.ps1` (incollare qui, uno per file):

```
(vuoto)
```

## Prova già eseguita senza certificato (2026-11-16)

`verify-signature.ps1` su `OCR2.exe` (avviatore) appena costruito da NSIS 3.13, senza firma, sul PC di sviluppo:

```
File:        <cartella di prova>\launcher\OCR2.exe
Status:      NotSigned
Soggetto:    nessun firmatario
Impronta:    nessun firmatario
Marca temporale: nessuna marca temporale
codice di uscita: 1
```

Il test `test_verify_signature_reports_not_signed_and_exits_1` ripete la prova su un eseguibile sintetico. Con un certificato fittizio (impronta di zeri) l'`!finalize` di makensis chiama `sign.ps1`, che segnala «Certificato non trovato in Cert:\CurrentUser\My», scrive il file di errore e la costruzione di `build_installer.py` si ferma. Non provato: la firma reale, la marca temporale e la lettura dell'ora della marca (serve il certificato).
