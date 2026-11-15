# M2 — Un motore OCR aggiunto con soli file nuovi (REQ-023)

**Commit:** `975278a` ("test: synthetic engine added with new files only"), branch `claude/m2-motori`.

`git show --name-status 975278a`:

```
M	.github/workflows/ocr2-synthetic-taxonomy.yml
A	application/src/alfa_document_intelligence/engines/synthetic_fixed.py
A	application/tests/test_synthetic_fixed_engine.py
```

- **Codice del sistema:** due file nuovi.
  - `engines/synthetic_fixed.py` contiene il manifest e l'adattatore. Il manifest ha `selectable=False`, quindi il motore non compare tra le scelte del launcher.
  - `test_synthetic_fixed_engine.py` è il suo test.
- **L'unico file modificato** è il workflow CI, che elenca il nuovo modulo di test. È configurazione dei controlli automatici, non codice del sistema, ed è obbligatoria per la guardia `test_ci_workflow` (REQ-004).
- **Il test lo dimostra:**
  - il registro scopre il motore senza modifiche ad altri file;
  - il motore elabora un PNG sintetico attraverso la pipeline reale;
  - il record nomina `synthetic-fixed` 1 come produttore;
  - prima di aggiungere il modulo il test falliva (2 test falliti).

**Limite:** il motore di prova non ha modelli né pacchetti propri. La verifica delle impronte degli artefatti resta a carico della factory di ciascun motore: per RapidOCR, `rapidocr_runtime_factory`, con le stesse impronte dichiarate nel manifest.
