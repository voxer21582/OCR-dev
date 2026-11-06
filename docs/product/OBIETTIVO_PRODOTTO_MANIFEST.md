# Manifest di pubblicazione — obiettivo prodotto OCR2

**Preparato:** 2026-11-06

**Base:** `main` a `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Branch candidato:** `codex/product-goal-v1`

**Ambito:** sintesi pubblica e versionata dell'obiettivo e dei criteri di accettazione OCR2. È una bozza coordinativa; non accetta il prodotto, non chiude gate e non autorizza verifiche.

## File di contenuto incluso

| File | SHA-256 | Owner | Provenienza | Revisione e motivazione |
| --- | --- | --- | --- | --- |
| `docs/product/OBIETTIVO_PRODOTTO.md` | `B138C3FBB4E771AB54CD69341B78605C726A8098A4682EBAE88318A6A3C63C7C` | Coordinatore tecnico OCR2 | Sintesi originale da obiettivo esplicito dell'utente, confini pubblici, issue e overlay requisiti già revisionato; nessun codice, dato reale, OCR, modello, dossier o log locale copiato | Review indipendente finale richiesta. Incluso perché la repo pubblica non ha ancora un riferimento versionato ai criteri finali del prodotto. |

## Esclusioni

- Codice, test, runtime, modelli, dipendenze e artefatti dal checkout originale o da altri progetti OCR.
- Dossier ECC, output grezzi, prove Windows locali, benchmark, sample ID, valori quantitativi di pilot, documenti, OCR, dati personali, credenziali e decisioni riservate.
- Modifiche a workflow, protezioni, issue, automazioni o gate R7/R8.

## Verifica e limiti

- Modifica documentale; nessun test di prodotto è applicabile o eseguito.
- Prima della pubblicazione sono richiesti `git diff --cached --check`, controllo manuale del contenuto pubblico, pattern scan limitato e review indipendente sul diff completo.
- Lo scan di pattern non è DLP. La matrice è una ricostruzione coordinativa, non prova di implementazione o runtime readiness.
- Il manifest è metadato di controllo e non si auto-include nella tabella dei file di contenuto; il suo hash finale e il verdetto di review saranno riportati nella PR.
