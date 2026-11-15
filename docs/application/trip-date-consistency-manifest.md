# Trip-date consistency — scoped manifest

Date: 2026-11-09. Base public main `7486989d556503fa07c66ccce52bc13a5be4effd`. This is new OCR2 work with synthetic tests; no material from the previous OCR project was copied.

For expense reports with both trip-date candidates, the rule compares only observed canonical ISO dates: start no later than end passes, reversed order fails, and uncertain/absent/noncanonical candidates are indeterminate. Missing candidates cause no finding. Source-bound evidence and alternatives are retained; extraction is not mutated and a finding is not an administrative decision. OCR proposals remain uncertain until separately reviewed; the validation of extracted data does not automatically consume later review events.

From `application/`, with `PYTHONPATH=src;tests` and the existing Windows Python environment, `python -B -m unittest test_trip_date_consistency test_document_validation test_tax_exact_arithmetic.TaxExactArithmeticTests test_semantic_proposals` passed 60 synthetic tests. An initial run of the new selector failed because the rule was absent. The synthetic integration test exercises OCR-token proposals through analysis, not an OCR engine. Static independent review examined the rule; no real documents, native decoder, browser, R7/R8 work or product acceptance is claimed.
