# Controlli automatici M6

La CI della PR #152 sul commit `24f184b` è passata: [tassonomia e contratti Windows](https://github.com/voxer21582/OCR-dev/actions/runs/43856038048), [seconda esecuzione](https://github.com/voxer21582/OCR-dev/actions/runs/43856045470) e [CodeQL](https://github.com/voxer21582/OCR-dev/actions/runs/43856039615). La suite locale Windows del codice `b1fb10a` ha prodotto 1.056 test passati, 2 saltati e 401 sottocasi; l'output è conservato in [suite-inventory.txt](suite-inventory.txt). L'aggiornamento documentale successivo non cambia il codice verificato.

La successiva CI del commit `f4b7f3d` ha segnalato un collegamento a una lista pubblica, contenente un carattere interpretato come indirizzo email dal controllo sui dati pubblici. Il riferimento è stato sostituito con il port ufficiale MacPorts; il test locale del controllo documentale è passato. I nuovi controlli della PR sono necessari per confermare la correzione.

Suite Windows locale dopo la correzione e l'aggiunta del generatore sorgenti: 1.059 test passati, 2 saltati e 401 sottocasi; [output](suite-source-bundle.txt). Il nuovo test è aggiunto esplicitamente ai job Ubuntu e Windows della CI.

La PR in bozza #152, commit `0b208ce54f62fdf3b419ba50344ee791fabe045f`, ha completato con esito positivo il workflow [OCR2 synthetic taxonomy](https://github.com/voxer21582/OCR-dev/actions/runs/43824045702): job «Taxonomy registry and binding» (Ubuntu) e «Windows application contracts» entrambi riusciti. L'esito riguarda quel commit; le modifiche successive richiedono nuovi controlli.

Sul successivo commit `4ff4286ca4e6f74f9726bdce5b8a8b93229f432f`, un’esecuzione Ubuntu separata è fallita perché il test tentava di riutilizzare immediatamente una porta ancora in TIME_WAIT; il controllo CodeQL ha segnalato un’espressione regolare usata solo da un test HTML che non riconosceva tag maiuscoli. Il test della porta ora verifica l’assenza di un listener e il test HTML usa un parser; 29 test mirati locali passati. Nuova CI necessaria.
