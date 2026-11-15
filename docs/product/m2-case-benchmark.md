# M2 case benchmark and browser walkthrough (2026-11-15)

Evidence level: `LOCAL-RUN`. Synthetic documents only, one Windows 11 PC, CPU, no independent review. It does not measure accuracy on real expense statements.

## Inputs

| Item | Value |
|---|---|
| Statement | Synthetic PDF, 4 pages, 98 expense rows plus a pagination header on each page. SHA-256 `3b944c43e4cabe43fbde62230e8ae0067d2c20c5e2875423b324418d1073039c`. |
| Receipts | 100 synthetic files (60 PNG, 25 JPEG, 15 PDF), one receipt per file: number, `Data: dd/mm/2026`, `Totale: EUR n,nn`. SHA-256 of the concatenated per-file SHA-256 digests, in file-name order: `2aa6cabb8662661e8c9913242dfb16b00dc78fac7671841d4a85fe9317d9623b`. |
| Known answers | Receipts 1–95 have a statement row with the same amount; rows for receipts 10, 20, 30 carry a different amount (amount conflict); 3 rows (777,77, 888,88, 999,99) have no receipt; receipts 96–100 have no row. All dates are in November 2026; 43 rows have a day of 12 or less (ambiguous day/month). |
| Code | PR #144 (main `03cdab9` plus D3, #135 headers, known-answer fixtures and the review-input fix). Run 1 used commit `0ae051d`; run 2 used `48fa9ab` for OCR and `7c3e0a3` for the reconciliation figures (possible signals, see below). |
| Runtime | Hash-locked Windows runtime (`requirements/ocr2-runtime-cp313-win-amd64.lock`), RapidOCR 3.10.0, `--ocr-engine rapidocr-v6`. Archive in a temporary `LOCALAPPDATA`, not the user profile. |

The fixtures were generated for this repository in an earlier session and are kept outside it; their generator is not in the repository, so the hashes above identify the run but do not make it reproducible from the repository alone.

## Procedure

Loopback HTTP only (`127.0.0.1`), the same routes as the UI: create the case with the statement, add the 100 receipts in 5 chunks of 20, start local OCR, poll the job, open the reconciliation page, download the case JSON export, and compare it with the known answers by source hash. A socket hook logged connection and DNS attempts of the server and its workers.

## Results

The reconciliation is recomputed from the stored records on every read, so the run 2 figures were taken by restarting the server on `7c3e0a3` and exporting the same case again, without repeating OCR.

| Measure | Run 1 (`0ae051d`) | Run 2 (`7c3e0a3`) |
|---|---|---|
| Upload (statement + 5 chunks) | 3.1 s; 100 / 100 accepted | 2.7 s; 100 / 100 accepted |
| OCR and analysis job (101 documents, 104 pages) | 256.4 s, about 2.5 s per page | 201.7 s, about 1.9 s per page |
| Statement lines | 98 of 98, **no page header proposed as a line** (#135) | same |
| Correct receipt ranked first | **92 of 92**; reason `possible_amount_and_currency_match` | **92 of 92**; reasons `possible_amount_and_currency_match`, `possible_date_match`; no `ambiguous_candidates` |
| Amount-conflict rows (receipts 10, 20, 30) | `missing_support`; receipts listed as unused | **`possible_amount_conflict`** with the right receipt as the only suggestion |
| Rows with no receipt (777,77, 888,88, 999,99) | `missing_support` | `missing_support` for 2; the 888,88 row shares 21/11 with receipt 20 and also shows it as a `possible_amount_conflict` (see limits) |
| Unused receipts | 96–100 plus 10, 20, 30 | **96–100**, as expected |
| Ambiguous dates | 43 rows `uncertain`; in all 43 the first reading carries `date-dmy-hint` and is the correct November date; 55 unambiguous dates `observed` | same |
| Duplicate claims / duplicate sources | 0 / 0, as expected | same |
| Non-loopback connection or DNS attempts | 0 | 0 |

A first run-2 export on `48fa9ab` showed a regression, fixed in `7c3e0a3`: unused receipts of the same day were offered as possible conflicts to lines that already had their receipt, tied with it, and in 12 of 98 lines were ranked first. A possible conflict now needs a line that no receipt fits by amount; a unit test reproduces the case.

## Browser walkthrough (built-in browser of the Claude desktop app, no test driver installed)

On the benchmark case: case list → case → reconciliation page (98 lines on 2 pages) → evidence page image → review actions.

- The date hint is visible: `Data: Da verificare (suggerito giorno/mese): 2026-11-02 · 2026-02-11`.
- Keyboard: the candidate checkbox, evidence link, note field and action buttons are reached with Tab in that order; a confirmation was submitted with Enter.
- Saved and shown: `confirmed`, `missing support`, `ambiguous` (two decisions in a row without reloading), `excluded with reason` (note typed with the keyboard). The JSON export lists the four events, with the note only on the exclusion.
- **Defect found and fixed in this branch:** excluding a line without a note answered 409 "le prove o il fascicolo sono cambiati", the stale-revision message. It now answers 400 and names the missing note; confirming without a selected receipt does the same.
- **Accessibility gap found and fixed:** the review note input had no accessible name; it now has an `aria-label`. A full accessibility check with a screen reader (REV-5) was not done.

## Limits and open findings

- **Amount conflicts from OCR receipts are possible signals only.** Receipt dates and totals from OCR stay `uncertain` (common-field proposals never promote a date to an issue date or an amount to a total), so the observed-field rule `amount_conflict` still does not fire on them. Following the owner's decision of 2026-11-15, reconciliation now reports `possible_amount_conflict` when a line and a receipt share a possible date (any reading on either side), currency and merchant are compatible, no receipt fits the line by amount and the receipt fits no line by amount. It is a hint for the reviewer, never a confirmation.
- A receipt left over on a day with several unsupported lines is offered to each of them: in run 2 receipt 20 is a possible conflict for its own row and for the 888,88 row of the same day. The person decides.
- Every match is `possible_…` for the same reason: the person must confirm each one.
- One run, one PC, synthetic layout with a simple font; no real documents, no accuracy target, no interruption or resume test in this run.
