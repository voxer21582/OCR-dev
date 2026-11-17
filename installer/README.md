# Preparazione dell'installer M6

**Stato: lavoro in corso.** Le prove locali non costituiscono una release. Verifica completa delle licenze, revisione conclusiva e collaudo sull'altro PC sono ancora necessari. M6 si chiude senza firma (DEC-034): REQ-105 è rinviato.

Gli input approvati e le rispettive impronte sono in [`pins.json`](pins.json), nel [lock del runtime](../requirements/ocr2-runtime-cp313-win-amd64.lock) e nelle evidenze M6. L'archivio Python è stato compilato localmente dalle fonti ufficiali 3.13.18: non è un archivio Windows firmato da python.org. Il suo hash identifica quella specifica build, non garantisce che una ricompilazione produca gli stessi byte. La cache `installer/.cache/` non viene inclusa nel repository.

Con gli input già disponibili e verificati, dalla radice del progetto si può assemblare una versione di prova così:

```powershell
$env:PYTHONPATH = 'application/src'
@'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('builder', 'installer/build_payload.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
builder.build_payload(
    embeddable_zip=Path('installer/.cache/python-3.13.18-local-embed-amd64.zip'),
    wheel_dir=Path('installer/.cache/wheels'),
    app_src=Path('application/src'),
    out_dir=Path('installer/.cache/payload'),
    version='0.6.0',
)
'@ | python -B -
```

Il contenuto di destinazione deve essere nuovo. Il generatore installa le wheel dal lock senza rete, esclude la DLL FFmpeg, crea distinta e avvisi e aggiorna il manifest. Le versioni delle cartelle, dei modelli e dei metadati vanno poi verificate; non cancellare una cartella esistente per forzare il completamento.

NSIS viene usato dall'archivio portabile verificato, senza installarlo nel sistema. `ocr2.nsi` richiede `OCR2_VERSION`, `OCR2_PAYLOAD` e `OCR2_OUTPUT`; `OCR2_TEST` crea una variante per sole prove locali e non crea collegamenti Start. Le build di rilascio richiedono inoltre `OCR2_CERT_THUMBPRINT` e `OCR2_SIGN_COMMAND`: la procedura e i limiti sono in [signing.md](../docs/runtime/signing.md). Non distribuire una build di prova.

Senza certificato (DEC-034) si compila un rilascio **non firmato** con l'opzione esplicita `OCR2_UNSIGNED_RELEASE`. Salta solo le verifiche Authenticode; tutti gli altri controlli di rilascio e il comportamento del rilascio (collegamenti Start, domanda sui dati, cartella di installazione) restano invariati. Non si combina con `OCR2_CERT_THUMBPRINT`, `OCR2_SIGN_COMMAND` o `OCR2_TEST`, e il nome in `OCR2_OUTPUT` deve contenere «non-firmato» (o «unsigned»): altrimenti la compilazione si ferma. I controlli `!system` usano percorsi relativi: `makensis` va eseguito dalla cartella `installer`, con `python` nel `PATH`. `pwsh.exe` (PowerShell 7) serve solo per le build firmate: controllo delle firme del runtime e verifica della firma dopo gli agganci.

```powershell
Set-Location installer
& .cache\nsis\nsis-3.13\makensis.exe /DOCR2_UNSIGNED_RELEASE /DOCR2_VERSION=0.6.0 `
  /DOCR2_PAYLOAD=<cartella-payload>\0.6.0 /DOCR2_OUTPUT=<cartella-uscita>\OCR2-0.6.0-setup-non-firmato.exe ocr2.nsi
```

Il testo in basso nelle finestre dell'installer e del disinstallatore riporta «OCR2 <versione> — non firmato».
