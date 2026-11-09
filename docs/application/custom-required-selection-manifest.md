# Required fields for selected custom families

The previous custom-field validation only considered observed OCR title
alternatives, as documented in the catalog-pipeline manifest. This candidate
extends the rule to a custom `document_family` on the record and to an
observed primary `document_family_candidates.value`, even when no alternatives
are present. Existing observed alternatives remain active as before. Only
definitions present in the record's validated snapshots are considered.

A required field that is absent or uncertain still produces a neutral
`warning`/`indeterminate` finding. This is a conservative validation signal,
not proof that a family or document is correct. Multiple OCR alternatives may
still cause warnings for multiple plausible families. A top-level family value
does not itself provide evidence of classification.

This rule operates on the supplied record. It does not add a custom-family
selection UI, change the review ledger, or re-run validation on a review
overlay; those integrations remain separate. It does not modify fiscal or
administrative approval. Tests use only synthetic records and a local catalog;
no OCR, decoder, archive, R7/R8 or real data is involved.

The product branch is based on the proposed expense-report date validation in
PR #73, so it must be reconciled if that prerequisite changes or is integrated.
Its CI coverage must be proposed separately; no merge is implied.
