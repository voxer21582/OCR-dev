# Windows 11 runtime acceptance plan

**Status:** planning only; A4 is open. No OCR runtime or model is selected or accepted by this document.

This plan defines the evidence needed before OCR2 can claim a supported local OCR runtime on Windows 11. The public repository currently contains taxonomy contracts and their synthetic CI only; it does not contain the full application, an OCR runtime bundle, or model artifacts. Passing the taxonomy workflow does not satisfy any runtime criterion below.

## Acceptance boundary

- Product target: local use on Windows 11. Windows Server results are not substitutes.
- Data boundary: public repository and CI use synthetic fixtures only. Real documents, OCR output, personal data, and derived sensitive values stay out of GitHub and external services.
- Activation: OCR remains off until every applicable prerequisite has evidence bound to the exact runtime tuple and the required technical and security approvals are recorded.
- Change control: this plan authorizes no downloads, installs, Windows configuration changes, native tests, model acquisition, deployment, or activation. Each operation follows its own approved plan and authority.

## Freeze the exact runtime tuple

Before acceptance testing, record one immutable candidate tuple. A missing or changing component returns the work to candidate selection; results from different tuples must not be combined.

| Component | Required identity and evidence | Current status |
| --- | --- | --- |
| Windows host | Windows 11 edition, version/build, architecture, test account role and effective permissions; capture without changing settings | Not captured for an acceptance run |
| OCR2 application | source commit and hashes of the application, worker, bootstrap, and preview-decoder code under review | Not bound to a runtime candidate in this repository |
| Python/runtime | exact interpreter build, architecture, supported Windows baseline, package lock, wheel hashes, and native DLL/PYD inventory | No accepted tuple |
| OCR engine | exact distribution/version and source provenance; runtime configuration that prevents implicit network/model acquisition | No accepted engine |
| Models | task and language roles, official source/revision, exact file hashes, metadata, and redistribution terms | No accepted model set |
| Preview decoder | exact implementation/version, native components, source provenance, and license/notice inventory | Not bound to a runtime candidate |
| Package and notices | complete dependency/model/native-component inventory, license texts, attribution, and redistribution decision tied to the tuple hashes | Open |

Historical inventories or candidate recipes may guide investigation but do not become the selected tuple without current artifacts and review. Do not combine old evidence, unverified hashes, or results from another OCR project.

## Required evidence gates

All evidence must identify the frozen tuple, test host and account, command or procedure, timestamp, result, raw privacy-safe artifact, and reviewer. Use synthetic fixtures for repository-based checks. Keep real-data pilot evidence outside this repository.

| Gate | Required evidence | Acceptance condition |
| --- | --- | --- |
| Provenance and licensing | Source/revision and hashes for every wheel, model and native component; complete license and notice mapping; documented redistribution conclusion | No unresolved component or notice obligation; independent legal/licensing review recorded |
| Installation and identity | Clean install, expected file/registry scope, least-privilege account behavior, and clear behavior for missing permissions | Reproducible install without elevating the application; no undocumented Windows changes |
| Input and resource limits | Synthetic PDF/image/ZIP boundary cases, malformed inputs, expansion limits, timeouts, and bounded memory/disk behavior | Invalid or oversized inputs fail closed within documented bounds; embedded content is never executed |
| Worker isolation and access | Host-positive/worker-negative access controls, token/capability review, protected model snapshot and race checks, and safe error/stop handling | Only declared resources are accessible; races and failures preserve integrity and leave no unsafe active worker |
| Offline behavior and egress | Positive local load/inference plus a bounded negative network test, with observed network evidence | Required local function works; worker cannot make undeclared network connections; host behavior is separately documented |
| OCR and preview behavior | Synthetic fixtures by supported document family; source page/region evidence, alternatives, uncertainty and failure cases | Outputs retain source hash and page/region; uncertain values remain unconfirmed; preview decoding meets its own limits |
| Lifecycle | Upgrade, interrupted upgrade, restore/rollback, clean uninstall, and post-stop cleanup against the same tuple | Each lifecycle path is repeatable and leaves the documented state; recovery is verified before cleanup |
| Operational limits | Cold/warm startup, latency, peak memory, disk footprint, failures and restarts across declared synthetic runs | Measurements include denominators, hardware/runtime identity and failure accounting; limits are agreed before execution |
| Sign-off and application link | Independent technical and security reviews; exact evidence hashes; explicit approval of the application link and activation gate | Named authorized approvers accept the same tuple and evidence set; activation remains off until then |

## Execution order and stops

1. Select a candidate tuple and verify that every artifact is already available from an authorized source. Do not acquire or install anything under this plan.
2. Complete provenance and licensing review and freeze the tuple. If artifacts or redistribution rights cannot be established, stop before runtime execution.
3. Prepare separately reviewed, bounded plans for synthetic host checks and native Windows 11 checks. Native checks must use the approved Windows 11 account and must not change Windows settings.
4. Run only the checks named in those plans. Preserve raw synthetic-safe results. Diagnose any refusal, failure, timeout or uncertain cleanup before considering a retry; stricter task-specific stop/no-retry rules take precedence.
5. Obtain independent technical and security review against the exact final tuple and evidence. Keep OCR disabled if any required criterion is open, failed, stale or unreviewed.

## Current gaps and next actions

- **Candidate selection — open:** no exact runtime and model tuple has been accepted. The owner must select or authorize a bounded candidate evaluation before acquisition or native testing.
- **Artifact and license closure — open:** exact current runtime/model artifacts and a complete component-level license/notice review are required.
- **Native Windows 11 evidence — not run:** installation, identity, isolation, egress, lifecycle, and resource checks need a separately reviewed plan and applicable authorization. This plan does not authorize them.
- **Application and approval linkage — open:** the public repository does not contain the full OCR2 app. The exact app commit and authorized technical/security approvers must be linked to the evidence before any gate can close.

Until these gaps are closed, the valid claim is limited to the repository's synthetic taxonomy checks. This plan is a checklist for future evidence, not evidence of runtime readiness, OCR accuracy, real-document safety, pilot usefulness, or release readiness.
