# Eliminazione: cosa garantisce e cosa no (REQ-085, REQ-122)

Questa pagina descrive in modo onesto che cosa succede quando elimini un documento
dall'archivio locale di OCR2, e che cosa resta fuori dal controllo del programma.

## Cosa garantisce OCR2

- **Tutto è cifrato prima di arrivare sul disco.** Il record, il file originale e i
  metadati della libreria (nome visualizzato, etichette, cronologia delle modifiche)
  sono cifrati con la protezione dati di Windows (DPAPI) del tuo utente. Senza il tuo
  accesso a Windows non sono leggibili.
- **L'eliminazione toglie tutto il documento in una sola operazione.** In un'unica
  transazione vengono rimossi il record, il file originale, i metadati della libreria
  e i riferimenti interni. Se l'operazione si interrompe, il documento resta intero:
  non rimane mai a metà.
- **Lo spazio liberato viene sovrascritto.** L'archivio usa `secure_delete` di SQLite:
  le pagine del file che contenevano il documento vengono riempite di zeri. Un test
  automatico (`test_deletion_traces`) controlla che, dopo l'eliminazione, nel file
  dell'archivio non resti nessun frammento dei dati cifrati del documento.
- **La sessione in memoria non lascia tracce.** I documenti caricati e non salvati
  restano solo in memoria; «Cancella sessione» o l'inattività prolungata li rilasciano
  (test `test_clear_releases_volatile_session_and_returns_to_upload_form` e
  `test_in_memory_session_expires_after_idle_timeout`).

## Cosa OCR2 non può garantire

- **Backup già scaricati.** Un backup (ZIP) contiene l'archivio così com'era quando
  l'hai scaricato. Eliminare un documento dopo non lo toglie dai backup esistenti:
  se serve, elimina anche quei file.
- **La copia lasciata dal ripristino.** Quando ripristini un backup, l'archivio
  precedente viene conservato accanto a quello nuovo con il nome
  `document-archive.sqlite3.before-restore-<data e ora>`, per poter tornare indietro
  (ogni ripristino crea una copia nuova, senza sovrascrivere le precedenti). Resta cifrato,
  ma contiene i documenti di prima: eliminalo a mano quando non ti serve più.
- **File esportati.** I file JSON o CSV esportati sono in chiaro e stanno dove li hai
  salvati: OCR2 non li controlla.
- **Copie fatte da Windows o da altri programmi.** Cronologia file, punti di
  ripristino, copie shadow del volume, sincronizzazione cloud (per esempio OneDrive)
  o antivirus possono aver copiato il file dell'archivio. Quelle copie sono cifrate,
  ma OCR2 non può cancellarle.
- **Dischi SSD.** Su un SSD il controller del disco può spostare i dati in celle
  diverse da quelle sovrascritte: i vecchi blocchi cifrati possono restare fisicamente
  sul disco finché il disco non li riutilizza. Per una cancellazione fisica serve la
  cifratura dell'intero disco (BitLocker) o una cancellazione sicura del disco.
- **Memoria di sistema.** File di paging e ibernazione di Windows possono contenere
  frammenti della memoria usata durante una sessione.

## In breve

Dentro l'archivio di OCR2 un documento eliminato non è più recuperabile, nemmeno
leggendo il file a basso livello. Fuori dall'archivio (backup, esportazioni, copie
di Windows, SSD) valgono le regole del sistema: per la massima protezione usa
BitLocker ed elimina i backup e le esportazioni che non ti servono.
