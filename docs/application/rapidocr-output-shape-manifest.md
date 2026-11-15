# RapidOCR result-shape validation — scoped evidence

Date: 2026-11-09. Base public main `7486989d556503fa07c66ccce52bc13a5be4effd`. New OCR2 work; no source or artifacts from the previous OCR project were copied.

The adapter rejects a result object that lacks any of the three expected attributes rather than silently treating it as an empty page. Existing `None`, explicit three-attribute `None`, and empty-sequence cases remain unchanged. Processing reports a failed OCR stage for malformed output and does not mutate the input. No runtime or model is initialized by the test.

From `application/` using the existing Windows Python environment and `$env:PYTHONPATH='src;tests'`, `python -B -m unittest test_rapidocr_output_shape test_rapidocr_adapter test_document_processing.DocumentProcessingProgressTests test_document_processing.OverflowProcessingTests test_ocr_adapter` passed 25 synthetic tests. The initial targeted run showed six failing cases before the change. Independent static review found no blocker; it did not run tests. Simulated objects do not establish compatibility with a real RapidOCR output or model, recognition accuracy, browser behavior, or product acceptance. No archive, R7/R8, native decoder, model, real data or network was used.
