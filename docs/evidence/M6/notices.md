# M6 Task 7: SBOM e notice di licenza - esito della generazione sul contenuto reale

Data: 2026-11-16. Comando: `python installer/build_payload.py --version 0.6.0` (wheel e embeddable dalla cache fissata, nessun nuovo download).

## Esito: FERMO, decide il proprietario

`build_notices` si e' fermata (codice di uscita 3): due pacchetti del lock non hanno alcun file di testo di licenza
nella loro cartella `*.dist-info` (ne' `License-File`, ne' `licenses/`, ne' file LICENSE/COPYING/NOTICE nella radice):

| Pacchetto | Licenza dichiarata nei metadati | Nota |
| --- | --- | --- |
| flatbuffers 25.12.19 | `License: Apache 2.0` | La wheel non contiene alcun file di licenza (nemmeno nel pacchetto). |
| onnxruntime 1.31.1 | `License: MIT License` | Fuori da `dist-info` la wheel contiene `onnxruntime/LICENSE` e `onnxruntime/ThirdPartyNotices.txt`. |

Nessun testo e' stato inventato. Gli altri 20 pacchetti, `python/LICENSE.txt` e `MODEL_LICENSES.md` di RapidOCR
(in `rapidocr-3.10.0.dist-info/licenses/`) sono presenti.

Opzioni per il proprietario (non applicate):
1. onnxruntime: accettare come testo di licenza i file `onnxruntime/LICENSE` e `onnxruntime/ThirdPartyNotices.txt` del pacchetto installato (estensione della regola di ricerca).
2. flatbuffers: fornire il testo Apache-2.0 ufficiale del progetto (nessuna fonte nella wheel), oppure scegliere un altro modo di documentarlo.

Fino alla decisione il contenuto `out/0.6.0/` e' incompleto (senza `sbom.cdx.json`, `THIRD_PARTY_NOTICES.txt`, manifest): non usarlo.

## Da registrare dopo la decisione
Numero di componenti dell'SBOM (previsti 27: 22 pacchetti + CPython + 2 modelli + OCR2 + NSIS escluso), pacchetti con licenza `NOASSERTION`
(nessuno nei metadati letti: tutti dichiarano una licenza), dimensione di `THIRD_PARTY_NOTICES.txt`, assenza di componenti FFmpeg
(verificata dal test `test_sbom_has_no_ffmpeg_component`; la DLL `opencv_videoio_ffmpeg500_64.dll` di cv2 viene rimossa dal build, DEC-030).
