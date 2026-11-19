# M8 — Foglio delle risposte: modello vuoto

Non inserire dati reali in questo file o nel repository. Preparare e conservare la copia compilata soltanto nella cartella privata locale. Questo modello non è un foglio compilato né un'approvazione.

```json
{"documents":[{"id":"codice-casuale-1","language":"it","expected":{"total_amount":"12.34","issue_date":"2026-01-01","currency":"EUR"}},{"id":"codice-casuale-2","language":"en","expected":{"merchant_name":"SYNTHETIC"}}],"matches":[{"id":"codice-riga-casuale-1","target":"codice-casuale-2"}]}
```

Il file dei risultati ha gli stessi codici documentali, con `fields` e candidati `{"status":"observed","value":"..."}` o `{"status":"uncertain","alternatives":[{"value":"..."}]}`; `matches` contiene il primo `target` suggerito per ciascuna riga. Non registrare tra le risposte valori sconosciuti o non applicabili; registrarne la motivazione nel foglio privato separato e il numero aggregato nel report. Identificativi sono sensibili anche se pseudonimi: non pubblicarli.
