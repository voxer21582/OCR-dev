# Publication manifest — repository contributor instructions

**Prepared:** 2026-11-06
**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`
**Branch:** `codex/repo-agent-guidance-v1`

| Included file | SHA-256 | Owner | Provenance | Review status and rationale |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | `B44301F45123C1FD692A9808E520436A03EFA33D166BEF8D9D4745713359554C` | OCR2 technical coordinator | Concise synthesis of the user's standing instructions and current public repository scope in `README.md`; includes the permanent rule to assess automated quality and useful free GitHub capabilities for each authorized feature. | Independent final review READY; durable contributor rules for this public taxonomy-slice repository. |
| `.github/ISSUE_TEMPLATE.md` | `6030C25B18DB273EC0A9E4971F607B47FD4B9B13D365312CDC0B98018FCB4EF0` | OCR2 technical coordinator | Lightweight template based on the user's requested acceptance, scope, evidence, and owner-decision fields. | Independent final review READY; no labels, automation, or new permissions. |
| `.github/PULL_REQUEST_TEMPLATE.md` | `3023846743E16DBC12219DAF25B5167F31C236512E28895578A168F4DA27ECA3` | OCR2 technical coordinator | Lightweight template based on the user's requested objective, issue, changes, tests, evidence, risks, and acceptance. | Independent final review READY; avoids closing keywords before acceptance. |

## Excluded

- Product code, tests, dependencies, runtime/model artifacts, local evidence, internal dossiers, real documents, OCR output, personal data, secrets, and previous-project files.
- Changes to workflows, branch protection, Project settings, issue state, gates, or blocked R7/R8 implementation.

## Verification

- Documentation-only change; no product tests are applicable or run.
- `git diff --check` passed; public-content and hash checks passed; independent final-diff review READY on 2026-11-06.
- `AGENTS.md` summarizes durable operating rules; issue-specific acceptance criteria and approved designs remain authoritative for their scope.
- Templates are plain Markdown and do not add labels, automation, dependencies, permissions, or required checks.
