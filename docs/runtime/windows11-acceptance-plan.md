# Windows 11 runtime acceptance plan

**Status:** acceptance remains open. The owner selected RapidOCR as the R9 evaluation direction; the A4 PaddleOCR/medium research track remains separate. The current RapidOCR candidate has one narrow local synthetic smoke result, but no runtime or model bundle is accepted for general product use or redistribution.

This plan defines the evidence needed before OCR2 can claim a supported local OCR runtime on Windows 11. The public repository contains a selective application snapshot and synthetic CI, not the complete application or a bundled runtime/model release. Passing the taxonomy workflow does not satisfy any runtime criterion below. A summary of the one-off local smoke is recorded in [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6818743640); its private detailed log is not part of this repository.

## Acceptance boundary

- Product target: local use on Windows 11. Windows Server results are not substitutes.
- Data boundary: public repository and CI use synthetic fixtures only. Real documents, OCR output, personal data, and derived sensitive values stay out of GitHub and external services.
- Activation: the launcher default remains disabled. The one-off synthetic smoke was separately authorized and does not enable general use or production acceptance. Keep OCR disabled by default until every applicable prerequisite has evidence bound to the exact runtime tuple and required technical and security approvals are recorded.
- Change control: this plan authorizes no downloads, installs, Windows configuration changes, native tests, model acquisition, deployment, or activation. Each operation follows its own approved plan and authority.

## Freeze the exact runtime tuple

Before acceptance testing, record one immutable candidate tuple. A missing or changing component returns the work to candidate selection; results from different tuples must not be combined.

| Component | Required identity and evidence | Current status |
| --- | --- | --- |
| Windows host | Windows 11 edition, version/build, architecture, test account role and effective permissions; capture without changing settings | One local synthetic smoke ran on the reference Windows 11 PC; no full host/account acceptance record |
| OCR2 application | source commit and hashes of the application, worker, bootstrap, and preview-decoder code under review | Selective worker/factory code is present; no full application release tuple is frozen |
| Python/runtime | exact interpreter build, architecture, supported Windows baseline, package lock, wheel hashes, and native DLL/PYD inventory | Local smoke tuple: CPython 3.13.15 AMD64 and ONNX Runtime 1.31.1; no product lock or redistribution approval |
| OCR engine | exact distribution/version and source provenance; runtime configuration that prevents implicit network/model acquisition | RapidOCR 3.10.0 is the evaluation candidate; no general-use or distribution acceptance |
| Models | task and language roles, official source/revision, exact file hashes, metadata, and redistribution terms | PP-OCRv6 small multilingual detector/recognizer used in the one-off smoke; rights and bundle review remain open |
| Preview decoder | exact implementation/version, native components, source provenance, and license/notice inventory | Not bound to a runtime candidate |
| Package and notices | complete dependency/model/native-component inventory, license texts, attribution, and redistribution decision tied to the tuple hashes | Local candidate wheel/notice inventories exist; complete installer closure and redistribution review remain open |

Historical inventories or candidate recipes may guide investigation but do not become the selected tuple without current artifacts and review. Do not combine old evidence, unverified hashes, or results from another OCR project.

## Current candidate evidence (2026-11-12)

One separately authorized synthetic local smoke completed with RapidOCR 3.10.0, ONNX Runtime 1.31.1, and PP-OCRv6 small multilingual detection/recognition. It processed one generated PNG page, produced the single expected candidate, published the result once, matched the generated-source hash, and closed the worker and supervisor with worker exit code 0 (5.849 seconds). The exact attempt summary and limitations are recorded in [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6818743640); the detailed local transcript remains private.

This verifies only basic inference and worker lifecycle for that candidate on the reference PC. It does not measure OCR quality, test real notes, establish CER/WER or field-accuracy thresholds, exercise PDF/JPEG end to end, or verify installation, egress, upgrades, rollback, or redistribution. The result is not a formal Windows 11 acceptance run and cannot be combined with other runtime tuples.

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

1. Reconfirm the owner-approved evaluation direction and bind the exact candidate tuple and source hashes. The existing local smoke tuple is a candidate, not a product freeze. Do not acquire or install anything under this plan.
2. Complete provenance and licensing review and freeze the product tuple. If artifacts or redistribution rights cannot be established, stop before distribution or further runtime execution.
3. Prepare separately reviewed, bounded plans for synthetic host checks and native Windows 11 checks. Native checks must use the approved Windows 11 account and must not change Windows settings.
4. Run only the checks named in those plans. Preserve raw synthetic-safe results. Diagnose any refusal, failure, timeout or uncertain cleanup before considering a retry; stricter task-specific stop/no-retry rules take precedence.
5. Obtain independent technical and security review against the exact final tuple and evidence. Keep OCR disabled if any required criterion is open, failed, stale or unreviewed.

## Current gaps and next actions

- **Candidate evaluation — partial:** RapidOCR and its model/runtime tuple have a narrow local synthetic smoke result. Product tuple freeze, quality evaluation, and general runtime acceptance remain open.
- **Artifact and license closure — open:** local wheel, model, native-binary, and notice inventories exist, but the complete installer dependency closure, final SBOM validation, license/attribution review, and redistribution decision are outstanding.
- **Windows 11 acceptance — partial:** the one-off smoke does not cover installation, least-privilege identity, isolation, egress, lifecycle, or operational limits. These require separately reviewed plans and applicable authorization; this plan does not authorize those checks.
- **Formal real-data pilot/baseline — not started:** before a run is used as pilot or product-acceptance evidence, issue #10 must record its sample, access, independent labels, retention/deletion, budget, and quality thresholds. Any separately authorized local handling of the owner's documents remains local and outside CI or external services; it is not a formal pilot result by itself.
- **Application and approval linkage — open:** the public repository does not contain the full OCR2 app. The exact app commit and authorized technical/security approvers must be linked to the evidence before any gate can close.

Until these gaps are closed, the valid claim is limited to the synthetic repository checks plus the single, narrow local synthetic smoke described above. This plan is a checklist and status summary, not evidence of runtime readiness, OCR accuracy on expense notes, pilot usefulness, or release readiness.
