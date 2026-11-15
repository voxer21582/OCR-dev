# Richieste di nuove dipendenze (in attesa di approvazione)

Nulla di questo elenco è installato o scaricato. Ogni voce serve solo dalla milestone indicata; il lavoro che ne dipende si ferma finché il proprietario non approva. Alla approvazione la voce passa in [`dependencies-approved.md`](dependencies-approved.md) con versione e SHA-256 esatti.

R-001 (CPython 3.13 embeddable x64) e R-002 (NSIS 3.x portabile) sono state approvate il 2026-11-15: vedi [`dependencies-approved.md`](dependencies-approved.md). Al momento non ci sono richieste in attesa.

## Possibili richieste future (non ancora chieste)

- Un secondo motore OCR **vero** (es. un motore alternativo per confronto): solo se il proprietario lo vuole; il requisito multi-motore si dimostra con un motore di prova (DEC-003).
- Uno strumento per generare l'SBOM: preferenza per uno script nel repository che legge i lock (nessuna dipendenza nuova).
