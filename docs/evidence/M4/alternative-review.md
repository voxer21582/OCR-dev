# Revisione indipendente — selezione alternative

La rotta seleziona solo un’alternativa originale `observed` con evidenze e respinge moduli con testa obsoleta. I nuovi eventi con motivo `human_selected_alternative` vengono confrontati dal ledger con la proposta originale, comprese prove e metadati; regressione verifica anche prove alterate con hash ricalcolato. Test indipendenti: 37 passati, 5 sottocasi. Suite Windows: 831 test e 358 sottocasi passati ([output](alternative-final-suite.txt)).

Compatibilità: gli eventi storici con altri motivi conservano il contratto precedente. Un evento rietichettato come storico e ricalcolato non è distinguibile crittograficamente da un evento legacy: non si attribuisce a tutta la cronologia una garanzia antimanomissione. La revisione copre il nuovo percorso, non l’intera M4.
