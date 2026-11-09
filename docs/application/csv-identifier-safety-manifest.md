# CSV identifier safety — scoped evidence

Date: 2026-11-09. Base public main `7486989d556503fa07c66ccce52bc13a5be4effd`. This is new OCR2 work; no code or data from the prior OCR project was copied.

CSV export now rejects document identifiers and field names that violate the existing schema identifier patterns, before writing rows. This prevents formula-like identifiers from being emitted directly as spreadsheet cells; it does not modify the record or alter values. A terminal newline is rejected strictly. It may refuse an earlier malformed record that the weaker runtime invariant checker previously accepted. JSON export is unchanged; other candidate and filename contents remain JSON-encoded in CSV.

`$env:PYTHONPATH='src;tests'; python -B -m unittest test_csv_identifier_safety test_document_export` from `application/` passed 11 synthetic tests locally in the existing Windows environment. Initial tests reproduced 19 failing subcases. Independent security review found no blocking issue; its suggestions led to maximum-length tests. No archive access, real data, browser or R7/R8 test was performed. Spreadsheet applications may still reinterpret otherwise valid CSV text; JSON is the complete representation and import settings matter. This is not product acceptance.

