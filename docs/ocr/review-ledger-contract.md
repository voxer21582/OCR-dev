# In-memory review ledger contract

`start_review_ledger` and `append_review_event` provide an immutable, in-memory
history and retain the original R4 `FieldCandidate` snapshot for one subject.
Each event records a neutral
human action (`confirm`, `correct`, `reject`, or `defer`), an opaque caller-
supplied reviewer ID, a stable reason code, and a UTC timestamp supplied by the
caller. A correction stores its new literal value in a new event; earlier events
and the original `FieldCandidate` remain unchanged.

The ledger binds to a deterministic SHA-256 fingerprint of the candidate and
the exact taxonomy schema/version/hash. Appends require the expected current
revision. A candidate, source-evidence, or taxonomy change makes the ledger
stale; a mismatched expected revision is rejected. A derived result is current
only when its candidate digest, taxonomy digest, and review revision all match
the current state. The result remains caller-owned; this contract reports
freshness and does not mutate or delete results.

The expected revision is a stale-snapshot precondition, not an atomic lock: two
concurrent callers holding the same old ledger can both produce a new value.
Any caller that permits concurrent writes must serialize them or compare-and-
swap the returned ledger in its owning store.

`confirm` selects an existing alternative when one exists; with no alternatives
it records human confirmation of an absence/unreadability observation only.
`correct` records a non-empty manually entered value. `reject` and `defer` do
not accept a value. None of these actions approves a payment, reimbursement,
tax document, or accounting entry.

Events stay in memory. The contract does not read Windows identity, generate
timestamps, write to disk, access a database, display a UI, run OCR, or persist
history across restart. The caller supplies an opaque reviewer ID, reason code,
and UTC timestamp; this contract does not accept free-text review notes. A view
can be reconstructed within the same process from the event tuple. Durable
reopening belongs to R7 and remains unimplemented.

Public tests use synthetic values only. This ledger is an R6 foundation, not a
review interface, durable audit log, or full R6/product acceptance.
