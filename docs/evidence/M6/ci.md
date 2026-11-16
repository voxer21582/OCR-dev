# Controlli automatici M6

La PR in bozza #152, commit `0b208ce54f62fdf3b419ba50344ee791fabe045f`, ha completato con esito positivo il workflow [OCR2 synthetic taxonomy](https://github.com/voxer21582/OCR-dev/actions/runs/43824045702): job «Taxonomy registry and binding» (Ubuntu) e «Windows application contracts» entrambi riusciti. L'esito riguarda quel commit; le modifiche successive richiedono nuovi controlli.

Sul successivo commit `4ff4286ca4e6f74f9726bdce5b8a8b93229f432f`, un’esecuzione Ubuntu separata è fallita perché il test tentava di riutilizzare immediatamente una porta ancora in TIME_WAIT; il controllo CodeQL ha segnalato un’espressione regolare usata solo da un test HTML che non riconosceva tag maiuscoli. Il test della porta ora verifica l’assenza di un listener e il test HTML usa un parser; 29 test mirati locali passati. Nuova CI necessaria.
