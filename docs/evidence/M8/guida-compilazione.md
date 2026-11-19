# M8 — Compilazione assistita del campione

La preparazione è manuale: apri i documenti sul PC e trascrivi soltanto ciò che leggi. Non usare l'OCR o i suoi suggerimenti per preparare le risposte. I documenti e i fogli rimangono nella cartella privata locale; non inviarli in chat o nel repository. Il campione proposto è provvisorio: se non contiene documenti adatti, va modificato prima dell'approvazione.

## Comincia con un documento

1. Apri `campione-e-risposte.csv` dalla cartella privata. Se il programma chiede come importarlo, scegli **UTF-8**, separatore **punto e virgola** e formato **testo** per tutte le colonne. Non modificare `codice` e `percorso_locale`.
2. Apri sul computer il documento indicato nella prima riga. Scrivi `nota` nella colonna `ruolo` se è una nota spese, altrimenti `giustificativo` se è il relativo documento di spesa; se non rientra in queste categorie, segnalo per sostituzione. Indica `it` o `en` nella colonna `lingua` secondo il documento.
3. Trascrivi i valori presenti e leggibili: `total_amount` (ad esempio `12.34`), `issue_date` (ad esempio `2026-01-31`), `currency` (ad esempio `EUR`), `document_number`, `vat_registration_number`, `merchant_name`. Gli esempi sono inventati. Se un dato manca o è illeggibile, lascia vuota la cella e annota il motivo in `esclusioni_motivo`. Non dedurre valori mancanti.
4. Salva in CSV UTF-8 con lo stesso separatore; controlla che codici, date e importi restino testo. Ripeti per gli altri documenti solo dopo avere verificato che il primo sia salvato correttamente.

## Corrispondenze e controllo finale

Apri `corrispondenze.csv` con le stesse impostazioni. Per ogni riga della nota spese che ha un solo giustificativo corretto, scrivi un codice di riga casuale privo di dati personali in `codice_riga` e copia in `codice_documento_corretto` il `codice` del relativo giustificativo. In un registro separato da conservare nella stessa cartella privata annota anche il codice della nota, la pagina e la posizione della riga associati a ciascun codice di riga: altrimenti dopo l'OCR non sarà possibile sapere quale suggerimento confrontare. Prepara e fai approvare anche questo registro prima dell'OCR. Non inserire righe ambigue come se fossero univoche. Occorrono almeno dieci corrispondenze univoche, 30–50 documenti distinti e almeno cinque documenti valutabili per ciascuna lingua; ogni campo misurato deve avere almeno un caso valutabile.

La verifica formale descritta in [istruzioni-foglio-locale.md](istruzioni-foglio-locale.md) aiuta a trovare errori di formato ma non certifica la correttezza delle risposte. Dopo la compilazione il proprietario esamina e approva esplicitamente il foglio prima di ogni OCR reale. Conservare fogli, risultati e archivio di prova fino a suo successivo via libera.
