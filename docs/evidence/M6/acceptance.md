# Accettazione M6 — non completata

| Requisito | Evidenza disponibile | Stato |
|---|---|---|
| REQ-100 | Prove precedenti della finestra e test sintetici; da confermare sul pacchetto finale e sull'altro PC. | Aperto |
| REQ-101 | Test sintetici di presenza finestra e launcher; da confermare sul pacchetto finale. | Aperto |
| REQ-102 | Installazioni di prova locali in cartelle temporanee; nessuna prova sul PC pulito. | Aperto |
| REQ-103 | Impronte delle wheel e dei modelli, manifest e prova locale; il manifest non è ancorato a una radice di fiducia indipendente. | Aperto |
| REQ-104 | Prove parziali di installazione, aggiornamento, interruzione, ripristino e disinstallazione; collegamenti e matrice sull'altro PC da verificare. | Aperto |
| REQ-105 | Il proprietario non dispone di un certificato (Q-004): installer, disinstallatore e binari della build locale non sono firmati. Gli installer di rilascio si compilano con `OCR2_UNSIGNED_RELEASE`, che salta solo le verifiche Authenticode; all'installazione Windows SmartScreen avvisa («Ulteriori informazioni» → «Esegui comunque»). La procedura di [firma](../../runtime/signing.md) resta pronta. | Rinviato — limite dichiarato (DEC-034) |
| REQ-106 | Collegamenti e informazioni implementati, ma il percorso completo nel menu Start non è stato verificato sul PC pulito. | Aperto |
| REQ-107 | Distinta e avvisi generati, FFmpeg escluso e OCR sintetico riuscito; la completezza degli avvisi e delle licenze resta da verificare. | Aperto |

La [revisione](review.md), le [prove locali](installer-dev-pc.md) e la [matrice](lifecycle-matrix.md) riportano i limiti. Nessuna evidenza qui dichiara completata la milestone.

## Limiti dichiarati

Ripresi dal confronto con la PR #151 e verificati su questo ramo; nessuno chiude un requisito. Restano tutti aperti finché il collaudo sull'altro PC non li conferma.

| Limite | Stato |
|---|---|
| Dopo la chiusura, l'avvio rapido di Edge può lasciare un processo `msedge.exe` con `--no-startup-window` sul profilo normale di Edge; `--disable-background-mode` non lo impedisce e OCR2 non cambia le impostazioni di Edge ([app-window.md](app-window.md), 4c). | Aperto |
| Una finestra chiusa con la X entro 2 s da un'altra richiesta conta come navigazione e tiene acceso OCR2 fino a 180 s. Succede facilmente durante un'elaborazione, perché quelle pagine si aggiornano ogni 2 s. Intanto installer e disinstallatore rifiutano con «Chiudi OCR2 e gli altri installer prima di continuare.». | Aperto |
| La sospensione del PC è tollerata; una finestra chiusa durante la sospensione può tenere acceso OCR2 fino a 180 s dopo il risveglio. | Aperto |
| Con i percorsi lunghi di Windows disattivati, `%LOCALAPPDATA%` deve restare entro circa 95 caratteri: il file più lungo del contenuto di prova ha 125 caratteri dentro la cartella della versione. Limite calcolato, non provato. | Aperto |
| Codici di uscita dell'installer: `0` anche per una versione già installata e integra, `1` con OCR2 o un altro installer aperto o con percorso non sicuro, `2` per gli altri errori. Con `/S` i messaggi non compaiono. Il disinstallatore ritorna subito e continua da solo. | Aperto |
| Un installer della stessa versione di quella installata e integra non sostituisce i file (codice `0`): una nuova build con lo stesso numero, per esempio una correzione di 0.6.0, si applica solo dopo la disinstallazione (verificato in prova isolata il 2026-11-16). | Aperto |
| Il ripristino dal menu Start, se riesce, non mostra messaggi: la versione si controlla in «Informazioni». | Aperto |
| Dopo la disinstallazione possono restare `%LOCALAPPDATA%\OCR2.instance.lock` (DEC-033) e una cartella `%LOCALAPPDATA%\Programs` vuota, se prima non esisteva. | Aperto |
| La verifica di integrità copre `app`, `python`, distinta e avvisi della versione, non `Uninstall.exe` (che fa anche da avviatore), `active.json` né il manifest stesso; rileva la corruzione, non la manomissione. | Aperto |
| I messaggi di avvio non riuscito restano generici; in modalità finestra i dettagli (data e ora, tipo, messaggio o tipo dell'errore con traceback) vanno in `%LOCALAPPDATA%\OCR2\logs\launcher.log`, indicato nel messaggio (decisione del proprietario del 2026-11-16). Il registro può contenere percorsi con il nome utente, non contenuti: i messaggi della console vengono conservati solo durante l'avvio, quindi le righe delle richieste (ricerche, etichette, identificativi) non entrano mai nel registro; una voce troppo lunga conserva inizio e fine, compresa l'ultima riga dell'errore; resta entro circa 256 KB più una copia `launcher.log.1`; non si scrive se `LOCALAPPDATA` manca o non è assoluto, né se la cartella non è scrivibile. Errori dell'interprete prima degli import applicativi non mostrano nulla e non scrivono il registro sotto `pythonw` ([procedura](../../runtime/m6-lifecycle-procedure.md)). | Aperto |
| «Esci» e «Informazioni» stanno in fondo al contenuto di ogni pagina. | Aperto |
| Il confronto dell'impronta rileva solo nomi aggiunti o rimossi, non contenuti o valori di registro. | Aperto |
| Nel rilascio M6 non firmato (DEC-034) nessun binario porta la firma del proprietario e il controllo delle firme non viene eseguito. Con un certificato, solo i binari della build Python locale porterebbero la firma del proprietario. I binari di terze parti conservano la firma del fornitore oppure nessuna (40 senza firma e 10 con firma valida del fornitore nel payload di prova `0.6.2`): il controllo di rilascio accetta `Valid` o `NotSigned` e rifiuta gli altri stati; la loro integrità viene dal manifest, che non è una radice di fiducia indipendente ([firma](../../runtime/signing.md)). | Aperto |
