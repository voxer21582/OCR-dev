# Richieste di nuove dipendenze (in attesa di approvazione)

Nulla di questo elenco è installato o scaricato. Ogni voce serve solo dalla milestone indicata; il lavoro che ne dipende si ferma finché il proprietario non approva. Alla approvazione la voce passa in [`dependencies-approved.md`](dependencies-approved.md) con versione e SHA-256 esatti.

R-001 (CPython 3.13 embeddable x64) e R-002 (NSIS 3.x portabile) sono state approvate il 2026-11-15: vedi [`dependencies-approved.md`](dependencies-approved.md). Al momento non ci sono richieste in attesa.

## Possibili richieste future (non ancora chieste)

- Un secondo motore OCR **vero** (es. un motore alternativo per confronto): solo se il proprietario lo vuole; il requisito multi-motore si dimostra con un motore di prova (DEC-003).
- Uno strumento per generare l'SBOM: preferenza per uno script nel repository che legge i lock (nessuna dipendenza nuova).


## R-003 — Valutazione compilazione CPython 3.13.18 per M6 (approvata il 2026-11-16)

La release 3.13.18 corregge problemi di sicurezza ed è distribuita solo come sorgente; l'ultimo pacchetto Windows ufficiale della serie è 3.13.17. Fonte: https://www.python.org/downloads/release/python-31318/. R-001 approva esclusivamente l'archivio embeddable ufficiale e non copre una build locale.

| Componente proposto | Versione | Licenza / dimensione | Motivo e alternativa |
|---|---|---|---|
| Sorgente CPython | 3.13.18, tar.xz ufficiale, SHA-256 `abb0102e6d4ae027509bcb82327d9dd85515b44a3ba8ad538cfc5e9847029f68` | PSF; 22,2 MB | Compilare una versione con correzioni di sicurezza; alternativa: embeddable ufficiale 3.13.17 già approvato |
| Strumenti MSVC e Windows SDK | Build Tools 2022 e SDK già rilevati localmente; versione esatta da inventariare | Licenza Microsoft; nessun download previsto per gli strumenti già presenti | Compilazione Windows x64 senza modificare Windows |
| Librerie esterne CPython | bzip2 1.0.8, mpdecimal 4.0.0, sqlite 3.50.4.0, xz 5.2.5, zlib 1.3.1; libffi 3.4.4, OpenSSL 3.5.9 e Tcl/Tk 8.6.15.0 secondo configurazione | Licenze, dimensioni e impronte dei singoli archivi da verificare prima dell'uso | Componenti previsti dalla build ufficiale; il sottoinsieme effettivo dipende dai moduli necessari |

Fonte della lista: https://raw.githubusercontent.com/python/cpython/v3.13.18/PCbuild/get_externals.bat. La fattibilità è plausibile, non dimostrata: servono inventario dei componenti, verifica delle licenze e impronte, costruzione del layout embeddable, test del runtime e OCR, SBOM e revisione. I binari locali non sarebbero firmati da python.org. Non sono stati scaricati o installati nuovi componenti per questa valutazione.
