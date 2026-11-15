# Richieste di nuove dipendenze (in attesa di approvazione)

Nulla di questo elenco è installato o scaricato. Ogni voce serve solo dalla milestone indicata; il lavoro che ne dipende si ferma finché il proprietario non approva. Alla approvazione la voce passa in [`dependencies-approved.md`](dependencies-approved.md) con versione e SHA-256 esatti.

## R-001 — Distribuzione embeddable di CPython 3.13 per Windows x64

| Campo | Valore |
|---|---|
| Nome | `python-3.13.x-embed-amd64.zip` (python.org) |
| Versione | L'ultima 3.13.x disponibile al momento di M6, fissata con SHA-256 (oggi la CI usa 3.13.18) |
| Licenza | PSF License 2.0 (più le licenze dei componenti inclusi, es. OpenSSL Apache-2.0, libffi MIT) |
| Dimensione | circa 10–12 MB compressa |
| Motivo | L'installer porta con sé il proprio Python (DEC-010): l'app non dipende dal Python del PC e aggiornamento e ritorno indietro restano sotto controllo. |
| Alternative | (a) Python già installato sul PC: nessuna richiesta, ma l'app si rompe se l'utente lo cambia o lo rimuove; (b) PyInstaller: un componente in più (GPL con eccezione), eseguibili spesso segnalati dagli antivirus. |
| Serve da | M6 |

## R-002 — NSIS 3.x (costruzione dell'installer)

| Campo | Valore |
|---|---|
| Nome | NSIS (Nullsoft Scriptable Install System) |
| Versione | L'ultima 3.x stabile al momento di M6, fissata con SHA-256 dell'archivio portabile (`nsis-3.x.zip`), usata **senza installarla** nel sistema |
| Licenza | zlib/libpng (parti bzip2 e CPL; il programma installato non eredita obblighi) |
| Dimensione | circa 2–3 MB compresso |
| Motivo | Installer per utente, offline, senza privilegi di amministratore, come indicato nel piano Windows 11. |
| Alternative | (a) Inno Setup: simile, licenza propria gratuita; (b) WiX/MSI: più rigido per installazioni solo per utente; (c) MSIX: richiede firma e un modello di installazione di sistema. |
| Serve da | M6 (sul PC di sviluppo per costruire; l'installer prodotto gira sull'altro PC del proprietario) |

## Possibili richieste future (non ancora chieste)

- Un secondo motore OCR **vero** (es. un motore alternativo per confronto): solo se il proprietario lo vuole; il requisito multi-motore si dimostra con un motore di prova (DEC-003).
- Uno strumento per generare l'SBOM: preferenza per uno script nel repository che legge i lock (nessuna dipendenza nuova).
