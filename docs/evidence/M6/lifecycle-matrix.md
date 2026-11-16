# M6 — Matrice della prova sul PC pulito (REQ-102, REQ-104)

Modello da compilare dal proprietario dopo aver eseguito [`docs/runtime/m6-lifecycle-procedure.md`](../../runtime/m6-lifecycle-procedure.md) sul secondo PC. Una riga per passo; «Esito» = `OK`, `NO` o `limite dichiarato`; «Note» = ciò che si è visto (valori richiesti dal passo, foto, messaggi). Non inserire dati personali né il confronto completo delle impronte: solo il file filtrato (sezione finale della procedura).

**Stato: DA ESEGUIRE dal proprietario** (nessuna riga compilata).

| Campo | Valore |
|---|---|
| Data e ora | |
| Windows (versione) | |
| Utente (solo «normale» o «amministratore») | |
| Edge (versione) | |
| File provati | `OCR2-0.6.0-setup.exe`, `OCR2-0.6.1-setup.exe` |
| Firma | firmato / non firmato (SmartScreen sì/no) — Q-004 aperta |

| # | Passo | Verifica principale | Esito | Note |
|---|---|---|---|---|
| 1 | Impronta prima | `prima.txt` scritto; N voci | | |
| 2 | Firma | `verify-signature.ps1` sul setup: `Valid`, oppure «non firmato» + SmartScreen | | |
| 3 | Installazione 0.6.0 | nessuna richiesta di amministratore; menu Start con 3 voci; `versions\0.6.0`, `active.txt` = `0.6.0`; nessun `opencv_videoio_ffmpeg*`; se firmato: `verify-signature.ps1` su `OCR2.exe` e `uninstall.exe` | | |
| 4 | Avvio e «Informazioni» | finestra senza barra indirizzi; Versione 0.6.0, Python, Motore OCR, «verificato (N file, S s)» — N e S | | |
| 5 | Fascicolo sintetico e Archivio | documento in archivio; R14: «Apri documento originale», 30 s, Indietro: app viva | | |
| 6 | «Esci» | pagina «OCR2 si è chiuso»; finestra chiusa a mano con la X; `instance.json` assente entro ~15 s; nessun `pythonw.exe` | | |
| 7 | Edge dopo «Esci» (R18) | dopo aver chiuso la finestra: processo `msedge.exe --no-startup-window` presente sì/no (limite di Edge, non di OCR2); nessun processo con `OCR2\edge-profile` | | |
| 8 | Chiusura finestra e porta libera | porta letta da `instance.json`; secondi alla porta libera (soglia unica ≤ 190 s; nessuna riga `LISTENING`, `TIME_WAIT` normale) | | |
| 9 | Aggiornamento interrotto (0.6.0 attiva) | `active.txt` ancora `0.6.0`; l'app parte e mostra 0.6.0; documento presente | | |
| 10 | OCR2 aperto durante l'aggiornamento (R8) | messaggio «Chiudi OCR2 con Esci e riprova.»; 0.6.0 resta attiva | | |
| 11 | Aggiornamento a 0.6.1 | `active.txt` = `0.6.1` / `0.6.0`; due versioni; «Informazioni» 0.6.1; documento presente | | |
| 12 | Versione già attiva (R7, R29) | «Questa versione di OCR2 è già installata.»; in silenzioso codice 2, nessun messaggio | | |
| 13 | Ritorno alla 0.6.0 (solo «Torna alla versione precedente») | «Versione attiva: 0.6.0»; `active.txt` = `0.6.0` / `0.6.1`; documento presente | | |
| 14a | Disinstallazione con OCR2 aperto (R8) | rifiutata con «Chiudi OCR2 con Esci e riprova.»; programma e dati presenti | | |
| 14b | Disinstallazione senza dati | `Programs\OCR2` e cartella menu Start eliminate; `%LOCALAPPDATA%\OCR2` presente | | |
| 15 | Reinstallazione 0.6.1 | documento ritrovato; «Informazioni» 0.6.1 | | |
| 16 | Disinstallazione con dati | `Programs\OCR2`, `%LOCALAPPDATA%\OCR2`, menu Start eliminati; nessun processo OCR2 | | |
| 17 | Impronta dopo e confronto | righe OCR2 rimaste: nessuna / elenco; differenze non OCR2: numero; di cui `HKCU`: numero | | |

## Output di `verify-signature.ps1` (solo se firmato)

```
(setup)
(OCR2.exe installato)
(uninstall.exe installato)
```

## Confronto delle impronte, solo righe OCR2

```
(contenuto di confronto-ocr2.txt, riletto prima di incollarlo; vuoto = nessuna traccia di OCR2)
```

## Osservazioni del proprietario

(Cosa non era chiaro, cosa non ha funzionato, messaggi esatti.)
