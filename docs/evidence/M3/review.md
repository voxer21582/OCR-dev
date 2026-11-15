# M3 — Revisione indipendente (2026-11-15)

**Revisore:** agente di revisione senza il contesto del lavoro (modello Opus), sul diff `1e44053..e67b175` (16 commit).

**Materiale fornito:** piano, design, GOAL.md, requisiti, decisioni DEC-021…026 e le decisioni del costruttore.

**Verifiche fatte dal revisore:** ha eseguito 76 test e alcune prove mirate con script propri.

**Esito:** nessun problema critico; «servono correzioni prima del merge».

## Problemi importanti, tutti corretti nel commit `ed976ae`

| # | Problema | Correzione | Test (prima rosso, poi verde) |
|---|---|---|---|
| 1 | Il tempo massimo di 2 s per le connessioni inattive tagliava anche un caricamento che si ferma a metà (file ancora in sincronizzazione) | Il tempo breve vale solo finché la richiesta non inizia; dopo, fino a 300 s | `SlowUploadTests` |
| 2 | Testo senza etichetta proposto come esercente su note spese, su fatture con il cliente in alto e su contratti | Niente esercente dalle righe in alto sulle note spese, quando un'etichetta nomina fornitore o cliente, e sui destinatari («Spett.le», «Gentile»…) | 3 test in `test_merchant_name` |
| 3 | L'editor accettava un tipo con lo stesso nome e una definizione diversa; aggiungere un tipo cambiava il formato del catalogo | Ridefinizione rifiutata; il formato del catalogo resta quello di partenza | `CatalogSafetyTests`. Il test della ridefinizione passava già prima della correzione: il «rosso» non è stato osservato e la causa non è stata indagata. Ora il rifiuto è garantito da `save_with_history(current)`. |
| 4 | Messaggi d'errore del catalogo generici | Messaggi che dicono cosa correggere: alias ripetuto, etichette troppo simili alle righe N e M, catalogo troppo grande | `CatalogSafetyTests.test_errors_say_what_to_fix` |
| 5 | Un valore già corretto in revisione poteva comparire «Non valido» per una verifica fatta sul valore estratto | Stato «Valido — corretto in revisione; le verifiche automatiche valgono per il valore estratto»; le due pagine di revisione ora coincidono | `ReviewedFieldStatusTests` |

## Problemi minori

**Corretti:**
- la copia di storico si scrive solo dopo un salvataggio riuscito;
- un lavoro sul fascicolo usa il catalogo presente al suo avvio;
- la separazione del codice di valuta avviene solo dopo nulla o dopo un'etichetta d'importo (`Rif:EUR2024,00` non diventa più un importo);
- il controllo con «lettura perfetta» è ora un test in CI;
- la frase sui 6 esercenti mancati è ristretta a ciò che è stato osservato;
- `__main__` è in fondo ai file di test.

**Rinviati:**
- `catalog_state` è letto fuori dal lock. Non ha effetti finché il server gestisce una connessione alla volta.
- Un catalogo non valido all'avvio non mostra un avviso nella pagina Catalogo; l'avviso compare solo nella console di avvio.
- L'evidenza di un importo con la valuta attaccata mostra lo spazio aggiunto (`Totale:EUR 4,50`).

## Trovato dopo la revisione

La misura dell'accuratezza rieseguita dopo le correzioni ha dato esercente 0%. La causa era lo script di misura, che trattava i giustificativi come note spese; è corretto in `8342d13`. Con lo script corretto tutte le soglie sono superate. I dettagli sono in [`2026-11-15-field-accuracy.md`](2026-11-15-field-accuracy.md).

**Dopo le correzioni:** in locale 763 passati, 1 saltato.
