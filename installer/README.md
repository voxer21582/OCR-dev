# Preparazione dell'installer M6

**Stato: lavoro in corso.** Le prove locali non costituiscono una release. Firma reale, verifica completa delle licenze, revisione conclusiva e collaudo sull'altro PC sono ancora necessari.

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

NSIS viene usato dall'archivio portabile verificato, senza installarlo nel sistema. `ocr2.nsi` richiede `OCR2_VERSION`, `OCR2_PAYLOAD` e `OCR2_OUTPUT`; `OCR2_TEST` crea una variante per sole prove locali e non crea collegamenti Start. Le build di rilascio richiedono inoltre `OCR2_SIGN_COMMAND`: la procedura e i limiti sono in [signing.md](../docs/runtime/signing.md). Non distribuire una build di prova.
