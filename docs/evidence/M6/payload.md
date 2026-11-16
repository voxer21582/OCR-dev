# Contenuto installer: prova locale

Python 3.13.18 è stato compilato localmente dalle fonti ufficiali; l'archivio embeddable locale è fissato in `installer/pins.json`, non è un binario ufficiale firmato. Le 22 wheel del lock sono state scaricate con verifica delle impronte e installate offline; pip non ha generato bytecode.

Il contenuto di prova 0.6.0 contiene 2.345 file, 264.694.258 byte, nessuna DLL `opencv_videoio_ffmpeg*.dll`. La verifica del manifest è riuscita in 3,2 secondi; import di RapidOCR, OpenCV e ONNX Runtime riusciti. Un'immagine sintetica ha prodotto `TOTALE 123.45 EUR`. Il launcher `-B -m alfa_document_intelligence --ocr-engine rapidocr-v6` è stato avviato con dati in una cartella temporanea del worktree e ha restituito HTTP 200 sulla porta locale. Queste prove non sostituiscono l'installer, il collaudo su PC pulito o una revisione indipendente.

Limite di sicurezza: il manifest non è ancorato a una radice di fiducia indipendente dall'installazione; la verifica non dimostra resistenza a un attaccante capace di modificare insieme codice e manifest.
