# A5 pilot decision register template

**Status:** blank template; no pilot decision or authorization is recorded here.

**Related work:** [issue #10](https://github.com/voxer21582/OCR-dev/issues/10).
**Scope:** prepare and record owner decisions before any pilot. Completing this template does not itself authorize data access, OCR, or a pilot.

## Fixed boundaries

- The intended product target is local use on Windows 11.
- A5 protocol and data authority must be accepted before a pilot; A4 runtime and security prerequisites must also be accepted before any pilot execution.
- Public GitHub, Actions, Codex, and external services must not receive company documents, personal data, OCR text, sample identifiers, labels, or confidential values.
- No paid service, model acquisition, installation, or Windows configuration change is authorized by this template.
- The Project issue remains open until the required decisions are recorded and independently checked. A completed form is not a claim of product acceptance.

## Owner decision register

For each row, record the approved decision, its authorized source and date in the project’s approved decision record. Keep identifying or confidential detail in the authorized private location. In this public copy, use only a non-sensitive status and a safe reference.

| Decision | Required owner decision | Status | Safe reference to approved decision |
| --- | --- | --- | --- |
| Sample eligibility and selection | Define the population, inclusion/exclusion rules, sampling method, and approval of the actual sample by the data authority | UNDECIDED | — |
| Data authority and access | Identify the authorizing role, permitted operators, local host/account boundary, and access revocation method | UNDECIDED | — |
| Independent labels | Define label schema, annotator independence/qualification, disagreement handling, adjudication, and label access boundary | UNDECIDED | — |
| Retention and deletion | Approve retention duration, deletion trigger, scope (including derived data/backups), and how deletion is verified | UNDECIDED | — |
| Budget and resources | Set a monetary ceiling, approved local resources, and explicit exclusions; paid services remain off unless separately authorized | UNDECIDED | — |
| Success and stop thresholds | Approve correctness/error thresholds, critical-error definitions, end-to-end time measure, denominators, and stop rules before measurement | UNDECIDED | — |
| Formal authorization | Record who has authority to approve the pilot and the approval date after all prerequisites are satisfied | UNDECIDED | — |

## Preconditions before pilot execution

The pilot remains **NOT AUTHORIZED** until all of the following are true:

1. Every owner decision above is approved by the appropriate authority and recorded in the approved decision source.
2. The actual sample is confirmed eligible and authorized; no sample document or derived text is placed in GitHub, Actions, Codex, or another external service.
3. A4 runtime, licensing, security, and Windows 11 acceptance prerequisites are complete for the exact candidate tuple.
4. The pilot procedure binds the approved sample, independent labels, measures, thresholds, access controls, retention/deletion, and stop conditions.
5. An independent review confirms that the protocol and evidence plan match the decisions and do not expose private data.

If any authority, evidence, threshold, or cleanup condition is missing or uncertain, do not start the pilot. Record the gap in the issue and keep the pilot unauthorized.

## Evidence permitted in the public issue

Link only to the approved public protocol and non-sensitive status/evidence references. Do not post sample file names, contents, OCR, labels, per-document outcomes, employee/customer details, private storage paths, access credentials, or other values that could identify a person or business record. Publish aggregate results only after the data authority approves the disclosure and the aggregation is reviewed for disclosure risk.
