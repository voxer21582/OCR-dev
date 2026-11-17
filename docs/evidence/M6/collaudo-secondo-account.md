# Collaudo M6 con un secondo account Windows (2026-11-17)

Il proprietario ha eseguito la [procedura del secondo account](../../runtime/m6-procedura-secondo-account.md) in un account Windows standard creato per la prova sul PC di sviluppo, perché non era disponibile un altro PC. Sono stati usati solo documenti inventati. Ore di inizio e fine non annotate. Il foglio esiti non è copiato nel repository: contiene il nome della macchina e dell'account.

## Build provata

Installer non firmati costruiti dal commit `5e347e2` ([anomalia /assign-note](assign-note-anomaly.md)); le impronte annotate nel foglio corrispondono a quelle sotto (4 corrispondenze, B1).

| File | SHA-256 |
|---|---|
| `OCR2-0.6.0-setup-non-firmato-5e347e2.exe` | `accc5a021b65b2ca0d0c63b6dafe4c808eab653db6071c12a86493fc2a1dbc34` |
| `OCR2-0.6.1-setup-non-firmato-5e347e2.exe` | `2c768e00165fe1af80c6476ab555ca152838e6856705b847c4bc9ea80034c70f` |

## Sintesi dell'esito

- **Preparazione (A1–A4).** Account creato, installer copiati, cartella esiti creata, accesso eseguito.
- **B1–B2.** Impronte corrette; firma dell'installer `NotSigned`; `%LOCALAPPDATA%` lungo 32 caratteri; fotografia iniziale senza avvisi di inventario incompleto.
- **B3.** Installazione della 0.6.0 riuscita (`active` 0.6.0, `previous` null; nessun file `opencv_videoio_ffmpeg`). Testo in fondo all'installer e comportamento di SmartScreen: confermato dal proprietario; il testo esatto letto non è stato annotato.
- **B4.** Avvio, elaborazione di un documento (1 su 1), nessun «Risorsa non trovata», salvataggio e apertura dell'archivio riusciti. «Informazioni»: verifica dichiarata OK; i valori letti non sono annotati.
- **B5–B7.** Documento originale dopo 30 e 200 secondi, sospensione di 5 minuti, chiusura con «Esci»: tutto riuscito, nessun processo residuo, `instance.json` assente, documento conservato.
- **B8–B9.** Nessun Edge con `OCR2\edge-profile`; resta un Edge con `--no-startup-window` (limite noto). Porta libera dopo circa 15 secondi.
- **B10–B13.** Aggiornamento con OCR2 aperto rifiutato e versione rimasta 0.6.0; aggiornamento interrotto osservato e ripreso con versione e archivio conservati; aggiornamento alla 0.6.1 riuscito con nuovo documento archiviato; ripristino alla 0.6.0 riuscito con entrambi i documenti. La voce «Torna alla versione precedente» non è stata individuata subito nel menu Start; causa non accertata (ipotesi: la ricerca di Windows può impiegare alcuni minuti a mostrare i nuovi collegamenti). Il proprietario ha confermato che va bene. Non è un difetto.
- **B14–B15.** Disinstallazione con dati conservati e reinstallazione con recupero dei documenti; disinstallazione con eliminazione dei dati e archivio vuoto dopo la reinstallazione; nessun `pythonw.exe` residuo.
- **B16.** Confronto delle impronte, vedi sotto.
- Nessun errore bloccante segnalato. I dettagli non annotati non si considerano verificati.

## Impronta sul profilo

Il confronto filtrato contiene una sola riga OCR2:

```
+ LOCALAPPDATA|FILE|OCR2.instance.lock
```

È il residuo già dichiarato (DEC-033). Le altre 1533 differenze non riguardano OCR2: sono normali per un profilo Windows nuovo al primo uso. Il confronto rileva solo nomi aggiunti o rimossi, non contenuti o valori di registro.

## Limiti dichiarati

- Stessi Windows ed Edge del PC di sviluppo: non è una macchina separata né un PC pulito (DEC-007). Un problema legato a un'altra installazione di Windows non emergerebbe.
- La reputazione di SmartScreen è condivisa con il PC di sviluppo, quindi l'avviso potrebbe differire su un altro PC.
- L'assenza di una richiesta di amministratore è dedotta dall'account standard su cui l'installazione è riuscita; il proprietario non l'ha registrata in modo esplicito.
- Installer non firmati (DEC-034): REQ-105 resta rinviato.
- Non esercitati: completezza di SBOM e avvisi (REQ-107), verifica specifica di impronte e manifest (REQ-103), disinstallazione con OCR2 aperto.
- Nessuno screenshot conservato; gli esiti sono dichiarazioni del proprietario.

Esito per requisito in [acceptance.md](acceptance.md); righe di prova in [lifecycle-matrix.md](lifecycle-matrix.md).
