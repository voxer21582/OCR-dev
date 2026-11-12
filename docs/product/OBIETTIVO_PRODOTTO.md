# OCR2 — Obiettivo di prodotto e criteri finali

**Versione:** 1.0-draft

**Data di ricostruzione:** 2026-11-06
**Stato:** obiettivo di alto livello ricostruito dalle decisioni esistenti; la matrice è una sintesi di accettazione, non una dichiarazione di prodotto completato né un'autorizzazione a superare i gate.

## Obiettivo

Realizzare e accettare un'applicazione locale, completa e mantenibile di document intelligence per Windows 11, che aiuti una persona a gestire documenti di spesa: importare e organizzare le fonti, osservare il testo OCR con provenienza, proporre classificazioni e valori strutturati, applicare controlli separati e rendere ogni risultato rivedibile e correggibile da una persona. L'applicazione deve conservare le fonti e la storia in una libreria locale fino alla cancellazione esplicita, supportare ricerca e riapertura, ed esportare risultati con stato e prove comprensibili.

OCR2 supporta la revisione umana: non approva rimborsi, pagamenti, documenti fiscali o registrazioni contabili. Un POS o una prova di pagamento non diventa automaticamente un documento fiscale. Il prodotto non si considera completo finché non soddisfa i criteri finali pertinenti e il proprietario non ne accetta formalmente il risultato.

## Decisioni e confini già approvati

- **Piattaforma:** Windows 11 locale; Windows Server non è un target di prodotto e non sostituisce l'accettazione nativa.
- **Confine dati:** documenti reali, OCR, annotazioni e valori sensibili restano nell'ambiente locale autorizzato. Repository e CI pubblici usano solo fixture sintetiche; niente cloud OCR, archiviazione remota o sincronizzazione automatica.
- **Provenienza:** ogni campo estratto deve conservare hash della fonte e pagina/regione. OCR, interpretazione semantica, validazione, revisione e conferma amministrativa restano distinti.
- **Incertezza:** preservare alternative, stati incerti e valori mancanti; non inventare evidenza e non auto-confermare per migliorare metriche.
- **Revisione:** la persona mantiene la decisione finale; modifiche e correzioni devono essere distinguibili dalle osservazioni originali.
- **Persistenza:** libreria locale fino a cancellazione esplicita. La cancellazione applicativa non promette cancellazione forense da snapshot, backup, supporti o cache del sistema.
- **Formati e motori:** un formato o motore è supportato solo dopo verifica di compatibilità, sicurezza, licenze e comportamento effettivo; l'esistenza di un'interfaccia non dimostra operatività.

## Criteri finali di accettazione

Ogni area richiede prove legate alla versione esatta del software e dell'ambiente. Il livello host/sintetico, il runtime nativo Windows 11, il pilot locale e il rilascio sono fasi distinte.

| Area | Risultato richiesto | Evidenza di accettazione | Dipendenze e restrizioni | Stato corrente |
| --- | --- | --- | --- | --- |
| R1 — Importazione e inventario | PDF, immagini dichiarate, TIFF multipagina e archivi ammessi sono identificati dal contenuto; fonti, pagine e membri restano distinti; input malformati, cifrati, non supportati o fuori limite falliscono in modo controllato. | Matrice positiva/negativa su Windows 11 per il set esatto di formati e decoder, con limiti e risultati legati agli hash. | Non pubblicizzare nuovi formati prima di verifica di compatibilità, licenza e sicurezza. | Parziale; accettazione Windows 11 completa aperta. |
| R2 — OCR e provenienza | Ogni osservazione è legata a hash fonte, pagina/regione, stato, versione esatta di motore, modello e runtime; fallimenti e pagine mancanti sono espliciti. | Prove end-to-end sul runtime esatto, incluse pagine multiple, errori, stop, isolamento e assenza di rete non autorizzata. | OCR e launcher restano disattivati finché A4 non è accettato. | Contratti presenti; operatività OCR non accettata. |
| R3 — Classificazione e tassonomia | Le classi e i campi supportati sono versionati; ambiguità e campi non implementati restano incerti o manuali; le configurazioni storiche sono preservate e le migrazioni sono esplicite. | Casi positivi, ambigui, sconosciuti, corrotti e di migrazione; prove riferite alla configurazione e ai record esatti. | Nessuna regola POS/fiscale o approvazione amministrativa automatica. | Parziale; il repository pubblico verifica solo contratti della tassonomia con fixture sintetiche. |
| R4 — Estrazione strutturata | I candidati conservano testo letterale, normalizzazione, alternative, stato, hash e pagina/regione; assente, illeggibile, respinto e incerto restano distinti. | Copertura per famiglia/campo e verifica delle emissioni rispetto a etichette indipendenti, senza auto-conferma. | Correttezza generale su documenti reali non è dimostrata dalla sola CI sintetica. | Contratti esistenti; copertura e correttezza ampie non provate. |
| R5 — Validazione e interpretazione | Osservazioni OCR, semantica, coerenza del documento, interpretazione fiscale/politica e verifica amministrativa sono passaggi separati. | Test e revisioni per omissioni, conflitti, record non validi e proiezioni della revisione corrente. | Nessuna approvazione contabile o pagamento automatico. | Parziale; accettazione completa dello stato revisionato aperta. |
| R6 — Revisione umana | La fonte con pagina/regione, alternative, incertezza e ragioni è visibile; le modifiche conservano la storia e invalidano risultati obsoleti. | Walkthrough locale browser/tastiera e casi di correzione, conflitto, riapertura e aggiornamento. | Dati reali restano locali; le prove pubbliche restano sintetiche. | Parziale; walkthrough browser e accettazione completa non eseguiti. |
| R7 — Libreria e gestione | Casi e fonti si riaprono dopo riavvio; ricerca, filtri, associazioni, duplicati, interruzioni e recupero sono espliciti; cancellazione è verificabile. | Prove sintetiche di percorso e interruzioni, poi accettazione di sicurezza/runtime prima di dati reali. | Le issue #5/#6 restano soggette a stop/no-retry; la #8 resta ferma finché non è chiarita la sovrapposizione. | Alcune tranche host/sintetiche sono documentate; accettazione ampia bloccata. |
| R8 — Esportazione | JSON versionato conserva prove e storia; CSV è sicuro per fogli di calcolo; i risultati parziali o obsoleti sono etichettati. | Round-trip, input malformati, integrità, compatibilità, formula-injection e prove sul runtime accettato. | Esportazione esplicita e locale; nessun significato di approvazione fiscale. | Tranche host/sintetiche documentate; accettazione completa bloccata. |
| R9 — Errori, limiti e prestazioni | Errori spiegabili senza esporre dati; limiti su file, archivi e risorse; misure distinte per importazione, OCR, ricerca, revisione, esportazione e recupero. | Misure riproducibili sul runtime Windows 11 esatto, con denominatori, hardware, fallimenti e soglie quantitative approvate prima del test. | Gli obiettivi di latenza, throughput e risorse sono decisioni del proprietario quando non già approvati. | Parziale; runtime e soglie misurabili restano aperti. |
| R10 — Sicurezza e ciclo di vita | Provenienza/licenze complete, isolamento, accessi locali, egress limitato, installazione, aggiornamento, ripristino e disinstallazione verificabili. | Inventario legato agli hash, prove native Windows 11, pulizia e recupero, review indipendenti e sign-off tecnici/sicurezza. | Nessuna installazione, cambio Windows, download modelli, attivazione o rilascio senza relativa autorità. | Aperto; gate A4 e release non accettati. |

## Gate e dipendenze di accettazione

### A4 — runtime locale Windows 11

Prima di dichiarare il runtime utilizzabile occorre congelare un tuple esatto di sistema/app/interprete/architettura/dipendenze/decoder/motore/modelli, verificare provenienza e licenze di ogni componente, e raccogliere prove autorizzate su installazione, identità/accessi, isolamento, caricamento, egress, limiti, errori, arresto/pulizia, aggiornamento, ripristino e disinstallazione. Servono review e sign-off indipendenti legati agli stessi hash. Nessun tuple runtime/modelli è attualmente accettato; OCR resta disattivato.

### A5 — protocollo e autorità dei dati

Prima del pilot devono essere approvati eleggibilità e selezione del campione effettivo, autorità sui dati, operatori/accessi, etichette indipendenti e adjudication, retention/cancellazione, budget, definizione degli errori critici, soglie complete e regole di stop. Il [template A5 nella PR #13](https://github.com/voxer21582/OCR-dev/pull/13) è una scheda vuota: non approva alcuna voce e non autorizza dati o pilot. La issue #10 è aperta.

### A6 — utilità misurata

Il pilot può iniziare soltanto dopo A4 e A5 e dopo l'autorizzazione specifica. Va svolto localmente con campione approvato e annotazioni indipendenti, confrontando il tempo umano end-to-end con la baseline e riportando errori, fallimenti/riavvii, risorse/costi e denominatori. Le soglie devono essere state approvate prima della misura; il risultato deve guidare una decisione formale di continuare, restringere o cambiare strategia. Il pilot non è iniziato.

## Stato effettivo e collegamento con GitHub

Osservazione del 2026-11-06: il repository pubblico `voxer21582/OCR-dev` contiene una porzione sintetica per validazione tassonomia e il relativo workflow; non contiene l'applicazione completa o un runtime OCR operativo. La CI richiesta dalla protezione di `main` è `Taxonomy registry and binding`; il suo successo non dimostra l'accettazione di R1–R10 o dei gate.

- [Project OCR2](https://github.com/users/voxer21582/projects/1) è la dashboard gestionale, non una misura percentuale di completamento del prodotto.
- Le [issue #5](https://github.com/voxer21582/OCR-dev/issues/5), [#6](https://github.com/voxer21582/OCR-dev/issues/6) e [#7](https://github.com/voxer21582/OCR-dev/issues/7) restano bloccate; non riprendere test o modifiche soggetti ai vincoli R7/R8. La [#8](https://github.com/voxer21582/OCR-dev/issues/8) resta bloccata finché l'ambito non è separato in modo verificabile.
- La [#1](https://github.com/voxer21582/OCR-dev/issues/1) dipende da A4/A5 e non autorizza pilot o accesso ai dati.
- Le [PR #12](https://github.com/voxer21582/OCR-dev/pull/12) e [#13](https://github.com/voxer21582/OCR-dev/pull/13) sono documentali, non unite e non equivalgono a review GitHub formale o accettazione del prodotto.
- Lo stato delle feature locali, i run dossier e i dati di benchmark non vengono copiati in questo documento pubblico. Ogni eventuale trasferimento di artefatti dal checkout locale richiede ownership/provenienza, manifest e review indipendente.

## Decisioni ancora da approvare

Questa bozza non sceglie valori per conto del proprietario. Prima dell'accettazione finale restano da decidere o approvare, nei rispettivi gate:

1. La selezione e il tuple esatto del runtime OCR/modelli e la relativa conclusione di licenza/redistribuzione (A4).
2. Le soglie quantitative complete di correttezza, prestazioni e risorse da usare per accettazione e misurazione (R4/R9/A5/A6).
3. Campione effettivo, autorità/accessi, etichette/adjudication, retention/cancellazione, budget e autorizzazione formale del pilot (A5).
4. La scelta di packaging/distribuzione locale quando installazione e aggiornamento sono pronti per essere accettati (R10); nessun formato distributivo è scelto qui.
5. L'eventuale stato GitHub distinto “In attesa del proprietario”: il campo Status attuale non lo offre; non è stato aggiunto senza approvazione di governance.

La missione non è completa finché ogni criterio applicabile non ha prova adeguata, le verifiche necessarie sono autorizzate e il proprietario accetta formalmente il risultato. Non usare la chiusura delle issue, una PR unita, il successo CI o un punteggio come sostituto.
