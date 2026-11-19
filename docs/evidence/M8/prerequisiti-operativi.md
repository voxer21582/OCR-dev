# M8 — Prerequisiti operativi e collaudo (preparazione)

Il protocollo e le soglie sono approvati; questa scheda organizza le verifiche restanti e non sostituisce l'approvazione del foglio delle risposte (REQ-140). Nessun OCR reale è autorizzato prima di quella approvazione.

| Punto | Preparazione e verifica |
|---|---|
| Campione | 30–50 documenti distinti; verificare manualmente nota, giustificativi, lingue, leggibilità, duplicati e almeno 10 abbinamenti univoci. Conservare localmente la selezione e il riferimento approvato. |
| Integrità | Prima della firma del foglio, fissare localmente un'impronta dei file selezionati; confrontarla di nuovo prima dell'OCR. Non pubblicare impronte o codici individuali. Se un file cambia, fermarsi e aggiornare il foglio prima di richiedere una nuova approvazione. |
| Ambiente | PC Windows 11 del proprietario, versione e runtime identificati; elaborazione esclusivamente locale. Preparare un'installazione e un profilo dati isolati: non aprire o modificare gli archivi e le installazioni OCR2 reali. I dati della prova restano fuori dal repository. |
| Accesso e conservazione | Originali lasciati al loro posto; file del foglio, risultati e qualsiasi archivio di prova in una cartella privata locale verificata dal proprietario, senza sincronizzazione cloud. Definire con il proprietario la durata e l'eventuale cancellazione delle sole copie della prova; nessuna cancellazione degli originali. |
| Misure pilot | Oltre alle soglie approvate, registrare soltanto aggregati di tempo end-to-end, tempo di revisione, errori e denominatori. Concordare prima della prova il confronto con il flusso abituale: se la baseline non è disponibile, dichiararla non misurata, senza inventare un risparmio. |
| Costo e limiti | Usare gli strumenti e il runtime già disponibili; nessun acquisto o download previsto. Tempo umano e costi aggiuntivi vanno annotati solo se effettivamente misurati o comunicati. |
| Ripetizione | Se le soglie non sono raggiunte, al massimo una ripetizione su campione nuovo dopo correzione; cambiare le soglie richiede firma del proprietario (DEC-006). |
| Collaudo | La checklist Windows si firma solo dopo le verifiche osservate; segnalare strumenti di sviluppo inclusi e limiti M6/M7. |

Non indicare percorsi, impronte, nomi o valori individuali nel repository, nel ticket o nella chat. La verifica CSV è sintattica e non sostituisce il controllo dei documenti o l'approvazione del foglio.

Verifica preparatoria del 2026-11-19: il sistema riferisce **Windows 11 Home, versione 10.0.26300, 64 bit**. È una lettura dell’ambiente, non un collaudo firmato né l’identificazione del runtime della prova; il primo tentativo nella sandbox è stato negato e la lettura successiva autorizzata è riuscita.

Conservazione: il proprietario ha scelto di conservare foglio, risultati e archivio isolato della prova reale fino a un suo successivo via libera. Questa decisione non autorizza l'OCR prima dell'approvazione del foglio compilato e non sostituisce la verifica che la cartella sia privata e non sincronizzata.

Verifica del collegamento operativo: `tools/run_case_benchmark.py` mostra come inviare file in memoria agli endpoint locali di un fascicolo, ma è predisposto **solo per fixture sintetiche**: crea log di processo e rete e scrive un export JSON nel proprio spazio di lavoro. Non va riutilizzato direttamente con il campione reale. Prima della prova va approntato e verificato un percorso che riceva i byte restituiti da `read_current`, mantenga un legame attendibile con la fotografia approvata e protegga risultati ed errori; il solo schema HTTP del benchmark non dimostra queste proprietà. Anche la trascrizione dei risultati nel formato dello scorer necessita di verifica indipendente.

Preparazione del 2026-11-19: payload 0.6.1 assemblato offline dalla cache approvata, NSIS verificato contro `installer/pins.json`, installer `OCR2_TEST` SHA-256 `8403ece54833a63f058ea813fcea8341adc8afb448bf273ffcf1d2907dfbaf10`. Installazione silenziosa in directory e `LOCALAPPDATA` sintetici isolati: uscita 0; `install_state verify 0.6.1` sull'installazione, uscita 0. Un tentativo precedente in percorso più lungo aveva restituito 2; la causa non è stata accertata. Questa è una preparazione sintetica, non una prova di OCR, un collaudo visivo o l'accettazione del proprietario. L'installer è di prova e non firmato.
