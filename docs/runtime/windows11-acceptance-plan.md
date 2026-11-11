# Windows 11 runtime acceptance plan

**Status:** planning only; A4 is open. An evaluation route and installer direction have owner approval, but no exact runtime tuple or distribution is accepted.

This plan defines the evidence needed before OCR2 can claim a supported local OCR runtime on Windows 11. The public repository now contains taxonomy contracts and a selectively migrated application under `application/`; it still does not contain an accepted OCR runtime bundle or model artifacts, and it does not yet contain the complete product. Passing synthetic application or taxonomy checks does not satisfy any runtime criterion below.

## Acceptance boundary

- Product target: local use on Windows 11. Windows Server results are not substitutes.
- Data boundary: public repository and CI use synthetic fixtures only. Real documents, OCR output, personal data, and derived sensitive values stay out of GitHub and external services.
- Activation: OCR remains off until every applicable prerequisite has evidence bound to the exact runtime tuple and the required technical and security approvals are recorded.
- Change control: this plan authorizes no downloads, installs, Windows configuration changes, native tests, model acquisition, deployment, or activation. Each operation follows its own approved plan and authority.

## Owner-approved evaluation direction

The owner approved the following direction for evaluation, recorded in [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6718473055). These decisions define the evaluation target; they do not establish that a runtime, model, installer, format, or the application has passed acceptance.

- Candidate OCR route: RapidOCR 3.10.0 with PP-OCRv6 small multilingual (`multi`) and ONNX Runtime CPU. Do not substitute another engine or model in the acceptance tuple without an owner decision.
- Initial language and document scope: Italian and English; PDF, PNG, and JPEG. The broader product goal also includes WebP and multipage TIFF; their end-to-end support remains to be demonstrated and must not be inferred from inventory or fake-decoder tests.
- Installer direction: per-user, offline, no elevation, using NSIS 3.x and embedded CPython 3.13 x64. Exact versions, payload, notices, and install/update/rollback behavior remain subject to review.
- Quality method: first measure page completeness, source/page/region provenance, uncertainty behavior, CER/WER by language and format, and exact-match for critical fields on an approved labeled sample. Set numerical thresholds only after reviewing the baseline and agreeing on acceptable risk.
- Test host: the owner's current Windows 11 PC. Its identifying details must stay out of this public repository; a privacy-safe host/account record must be bound to a particular acceptance run before that run is accepted.

The open draft [PR #100](https://github.com/voxer21582/OCR-dev/pull/100) assesses PaddleOCR 3.7.0 with PP-OCRv6 medium as a separate feasibility candidate. It is not the owner-approved evaluation route above and does not change the selected direction.

## Freeze the exact runtime tuple

Before acceptance testing, record one immutable candidate tuple. A missing or changing component returns the work to candidate selection; results from different tuples must not be combined.

| Component | Required identity and evidence | Current status |
| --- | --- | --- |
| Windows host | Windows edition/build, architecture, test account role and effective permissions; capture without changing settings, excluding device identifiers | Owner-designated PC; no acceptance-run host/account record |
| OCR2 application | source commit and hashes of the application, worker, bootstrap, and preview-decoder code under review | Selectively migrated application exists; not bound to an accepted runtime candidate |
| Python/runtime | exact interpreter build, architecture, supported Windows baseline, package lock, wheel hashes, and native DLL/PYD inventory | Embedded CPython 3.13 x64 is an approved direction; exact build and artifact inventory are open |
| OCR engine | exact distribution/version and source provenance; runtime configuration that prevents implicit network/model acquisition | RapidOCR 3.10.0 is the approved evaluation candidate; exact artifact, provenance, and offline behavior are not accepted |
| Models | task and language roles, official source/revision, exact file hashes, metadata, and redistribution terms | PP-OCRv6 small multilingual is the evaluation candidate; exact artifacts, hashes, and redistribution review remain open |
| Preview decoder | exact implementation/version, native components, source provenance, and license/notice inventory | Not bound to a runtime candidate |
| Package and notices | complete dependency/model/native-component inventory, license texts, attribution, and redistribution decision tied to the tuple hashes | Open; the NSIS per-user offline installer is a direction, not an accepted package |

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

- **Candidate selection — evaluation route approved; exact tuple open:** RapidOCR 3.10.0 with PP-OCRv6 small multilingual and ONNX Runtime CPU is the approved evaluation direction. Exact package/model artifacts, source revisions, hashes, and offline configuration must be verified before freezing a tuple. PR #100 is a separate PaddleOCR feasibility assessment and does not authorize switching candidates.
- **Artifact and license closure — open:** exact current runtime/model artifacts and a complete component-level license/notice review are required.
- **Native Windows 11 evidence — not run:** installation, identity, isolation, egress, lifecycle, and resource checks need a separately reviewed plan and applicable authorization. This plan does not authorize them.
- **Application and approval linkage — open:** the public repository does not contain the full OCR2 app. The exact app commit and authorized technical/security approvers must be linked to the evidence before any gate can close.

Until these gaps are closed, claims are limited to the synthetic taxonomy checks and explicitly selected application contract tests. These checks do not establish runtime readiness, OCR accuracy, real-document safety, pilot usefulness, or release readiness. This plan is a checklist for future evidence, not evidence that any of those gates has passed.
