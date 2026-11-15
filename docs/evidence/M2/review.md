# M2 — Revisione indipendente (2026-11-15)

**Revisore:** agente di revisione senza il contesto del lavoro (modello Opus), sul diff `169ad6d..13afb1e` (8 commit). Aveva a disposizione il piano, il design, GOAL.md, i requisiti, la valutazione GIF/BMP e le decisioni del costruttore.

**Verifiche fatte dal revisore:**
- ha eseguito i 6 nuovi moduli di test (29 test, tutti passati);
- ha verificato con script propri le mappe inverse delle rotazioni (corrette) e la geometria del testo incorporato (errata con il CropBox).

**Esito:** nessun problema critico; «merge dopo aver corretto gli importanti 1–4; il 5 almeno con un limite di costo».

## Problemi importanti, tutti corretti nel commit `1b98d93`

| # | Problema | Correzione | Test (prima rosso, poi verde) |
|---|---|---|---|
| 1 | Riquadri del testo incorporato sbagliati con CropBox o `/Rotate` | Coordinate relative al CropBox; le pagine ruotate passano all'OCR | `test_boxes_are_relative_to_the_crop_box`, `test_rotated_pages_fall_back_to_ocr` |
| 2 | Bastavano 20 caratteri di testo incorporato per saltare l'OCR, anche con testo invisibile o su una scansione con piè di pagina | Si conta solo il testo visibile; se un'immagine copre metà pagina o più, la pagina passa all'OCR | `test_invisible_text_is_not_trusted`, `test_scanned_page_with_a_short_text_footer_is_ocred` |
| 3 | Il registro non verificava che il modulo della factory esistesse | `find_spec` sui moduli di factory e controllo → `manifest_invalid`; un registro rotto dà un messaggio all'avvio, non una traceback | `test_rejects_invalid_manifest` («missing factory module»), `test_broken_engine_manifest_stops_with_a_message_not_a_traceback` |
| 4 | Una GIF animata faceva fallire l'intero lavoro con `worker_failed` | Percorso dei blocchi GIF al caricamento: GIF animate e fotogrammi fuori limite rifiutati con motivo stabile | `test_animated_gif_is_rejected_at_upload_with_a_stable_reason`, `test_gif_frame_larger_than_the_limit_is_rejected_at_upload` |
| 5 | I tentativi di rotazione non avevano limite di costo | Le pagine bianche non vengono più ruotate; gli errori del motore durante una rotazione non sono più ignorati (minore 6) | `test_blank_page_is_not_retried`, `test_engine_failure_during_a_rotation_is_not_swallowed` |

## Problemi minori

**Corretti:**
- il PDF ora si apre una volta per documento, e gli errori di lettura del testo ripiegano sull'OCR (minore 7);
- un registro rotto all'avvio dà un messaggio invece di una traceback (minore 8).

**Rinviati:**
- le anteprime non hanno un limite di processi concorrenti; inoltre una pagina avanzata di un PDF lungo deve decodificare quelle precedenti entro 30 s (minore 9);
- il test di identità del motore gira solo su Windows;
- è testato un solo angolo di rotazione end-to-end (il revisore ha verificato numericamente le mappe dei tre angoli).

**Il revisore ha lasciato al proprietario:**
- registrare l'angolo di rotazione nel record (rinviato a M3: lo schema della pagina non lo ammette);
- il produttore a livello di documento per i PDF misti;
- una verifica generica delle impronte degli artefatti nel worker;
- la soglia di confidenza 0,5, che va tarata su dati reali.

## Benchmark intermittente

Il revisore esclude che le modifiche deterministiche (identità, registro, testo incorporato) causino fallimenti intermittenti. Come causa plausibile indica le letture ruotate aggiuntive (tempo e memoria), senza poterla confermare.

Dopo la correzione 5 le pagine bianche non vengono più ruotate, e lo script del benchmark ora riporta fase e codice d'errore in caso di fallimento. Vedi [`2026-11-15-case-benchmark.md`](2026-11-15-case-benchmark.md).
