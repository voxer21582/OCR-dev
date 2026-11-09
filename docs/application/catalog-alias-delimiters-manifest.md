# Custom catalog aliases ending in delimiters

This fix was identified by a synthetic reproduction in the current OCR2
workspace against public main `7486989d556503fa07c66ccce52bc13a5be4effd`.
It builds on the catalog behavior already present there; no requirement or
implementation is taken from the previous OCR project.

Catalogs can already contain aliases such as `Data:` or `Data =`, but the
legacy field matcher compares only the prefix before the delimiter. This
candidate adds a fallback for a single matching trailing `:` or `=`, including
the normalized single-space form. The existing matching path takes precedence,
including previously supported aliases containing the other delimiter.

If the new fallback makes one OCR token match more than one distinct field,
all field proposals from that token are suppressed rather than attributing it
arbitrarily. This is conservative and can suppress an otherwise usable legacy
proposal. Ambiguities involving only legacy matches are intentionally not
resolved here. Values starting with another delimiter are not accepted by the
fallback. This behavior does not establish the correct document family or
confirm any value.

The catalog loader, stored definitions, canonical serialization, version and
snapshot hashes are unchanged. The matcher precomputes field alias sets and
parses each token once; worst-case work remains proportional to tokens times
catalog fields, within the existing input limits. The catalog's proposal limit
is not a wall-clock guarantee.

Tests use synthetic records and fake OCR observations. No actual OCR, native
decoder, archive, R7/R8, model or real document is exercised. UI usability,
full classification accuracy and application acceptance remain unverified.
