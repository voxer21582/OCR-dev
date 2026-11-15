# M2 case benchmark and browser walkthrough (2026-11-15)

Evidence level: `LOCAL-RUN`. Synthetic documents only, one Windows 11 PC, CPU, no independent review. It does not measure accuracy on real expense statements.

## Inputs

| Item | Value |
|---|---|
| Statement | Synthetic PDF, 4 pages, 98 expense rows plus a pagination header on each page. SHA-256 `3b944c43e4cabe43fbde62230e8ae0067d2c20c5e2875423b324418d1073039c`. |
| Receipts | 100 synthetic files (60 PNG, 25 JPEG, 15 PDF), one receipt per file: number, `Data: dd/mm/2026`, `Totale: EUR n,nn`. SHA-256 of the concatenated per-file SHA-256 digests, in file-name order: `2aa6cabb8662661e8c9913242dfb16b00dc78fac7671841d4a85fe9317d9623b`. |
| Known answers | Receipts 1–95 have a statement row with the same amount; rows for receipts 10, 20, 30 carry a different amount (amount conflict); 3 rows (777,77, 888,88, 999,99) have no receipt; receipts 96–100 have no row. All dates are in November 2026; 43 rows have a day of 12 or less (ambiguous day/month). |
| Code | Branch `claude/m2-close` at the commit that adds this file (main `03cdab9` plus D3, #135 headers, known-answer fixtures and the review-input fix). |
| Runtime | Hash-locked Windows runtime (`requirements/ocr2-runtime-cp313-win-amd64.lock`), RapidOCR 3.10.0, `--ocr-engine rapidocr-v6`. Archive in a temporary `LOCALAPPDATA`, not the user profile. |

The fixtures were generated for this repository in an earlier session and are kept outside it; their generator is not in the repository, so the hashes above identify the run but do not make it reproducible from the repository alone.

## Procedure

Loopback HTTP only (`127.0.0.1`), the same routes as the UI: create the case with the statement, add the 100 receipts in 5 chunks of 20, start local OCR, poll the job, open the reconciliation page, download the case JSON export, and compare it with the known answers by source hash. A socket hook logged connection and DNS attempts of the server and its workers.

## Results

| Measure | Result |
|---|---|
| Upload (statement + 5 chunks) | 3.1 s; 100 / 100 attachments accepted |
| OCR and analysis job | 256.4 s for 101 documents, 104 pages: about 2.5 s per page; final state `OCR completato 101 / 101` |
| Statement lines | 98 of 98; **no page header proposed as a line** (#135) |
| Correct receipt ranked first | **92 of 92** rows whose amount has a receipt; reason `possible_amount_and_currency_match` in every case |
| Rows without a receipt amount | 6: the 3 rows with no receipt and the 3 amount-conflict rows, all `missing_support` |
| Unused receipts | 96–100 as expected, plus 10, 20, 30 (see limits) |
| Ambiguous dates | 43 rows `uncertain`; in all 43 the first reading carries `date-dmy-hint` and is the correct November date; 55 unambiguous dates `observed` |
| Duplicate claims / duplicate sources | 0 / 0, as expected |
| Non-loopback connection or DNS attempts | 0 |

## Browser walkthrough (built-in browser of the Claude desktop app, no test driver installed)

On the benchmark case: case list → case → reconciliation page (98 lines on 2 pages) → evidence page image → review actions.

- The date hint is visible: `Data: Da verificare (suggerito giorno/mese): 2026-11-02 · 2026-02-11`.
- Keyboard: the candidate checkbox, evidence link, note field and action buttons are reached with Tab in that order; a confirmation was submitted with Enter.
- Saved and shown: `confirmed`, `missing support`, `ambiguous` (two decisions in a row without reloading), `excluded with reason` (note typed with the keyboard). The JSON export lists the four events, with the note only on the exclusion.
- **Defect found and fixed in this branch:** excluding a line without a note answered 409 "le prove o il fascicolo sono cambiati", the stale-revision message. It now answers 400 and names the missing note; confirming without a selected receipt does the same.
- **Accessibility gap found and fixed:** the review note input had no accessible name; it now has an `aria-label`. A full accessibility check with a screen reader (REV-5) was not done.

## Limits and open findings

- **Amount conflicts are not surfaced from OCR receipts.** The reconciliation reports `amount_conflict` only when the receipt date is `observed`. Receipt dates and totals from OCR are deliberately left `uncertain` (common-field proposals never promote a date to an issue date or an amount to a total), so the three conflicting rows show `missing_support` and their receipts appear as unused. The known-answer fixture in CI shows the rule working with observed receipt fields. Whether reconciliation should use uncertain receipt dates as a possible signal is a product decision; it is not changed here.
- Every match is `possible_…` for the same reason: the person must confirm each one.
- One run, one PC, synthetic layout with a simple font; no real documents, no accuracy target, no interruption or resume test in this run.
