# M6 Task 7: SBOM e notice di licenza - esito della generazione sul contenuto reale

Data: 2026-11-16. Comando: `python installer/build_payload.py --version 0.6.0` (wheel e embeddable dalla cache fissata, nessun nuovo download).

## Esito dopo R25 e R26: contenuto costruito, verifica superata

Prima esecuzione: `build_notices` si era fermata (exit 3) per due pacchetti senza testo di licenza in `*.dist-info`:
flatbuffers 25.12.19 (Apache 2.0, nessun file nella wheel) e onnxruntime 1.31.1 (MIT License). Nessun testo inventato.

- R25 (onnxruntime): sono accettati i file LICENSE/LICENCE/COPYING/NOTICE/ThirdPartyNotices* installati dalla wheel nella cartella
  di primo livello del pacchetto, solo se elencati nel `RECORD`. Per onnxruntime: `onnxruntime/LICENSE` e `onnxruntime/ThirdPartyNotices.txt`.
- R26 (flatbuffers, PROVVISORIO, in attesa di conferma del proprietario): `installer/licenses/flatbuffers-25.12.19.txt` = intestazione
  italiano/inglese + testo Apache-2.0 copiato byte per byte da `packaging-26.3.dist-info/licenses/LICENSE.APACHE` (testo completo dei termini,
  senza l'appendice; il LICENSE di rapidocr ha una riga di copyright davanti, quindi non e' stato usato). L'override vale solo per
  (flatbuffers, 25.12.19); l'SBOM lo registra con la proprieta' `ocr2:licence-text-source`.

Rigenerazione `build_payload.py --version 0.6.0` (cache, nessun download): OK, 3744 file, `verify_installation` ok (3744 controllati,
nessun problema); `sbom.cdx.json` e `THIRD_PARTY_NOTICES.txt` sono nel manifest.

Numeri: componenti SBOM 27 (22 pacchetti + CPython + 2 modelli + OCR2 + NSIS escluso); pacchetti con licenza `NOASSERTION`: nessuno;
`sbom.cdx.json` 13496 byte; `THIRD_PARTY_NOTICES.txt` 1186059 byte (pypdfium2, numpy e onnxruntime ThirdPartyNotices pesano di piu);
nessun componente FFmpeg (la DLL `opencv_videoio_ffmpeg500_64.dll` di cv2 viene rimossa dal build, DEC-030).
