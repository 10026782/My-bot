# Pull Request — CI-aware checklist

> Fill only the sections relevant to this PR. CI is authoritative; this checklist exposes the expected gates before review.

## Summary

- What changed:
- Why / scope:
- Related issue or PR:
- Change type: `runtime` / `test` / `docs-governance` / `CI-audit` / `schema` / `deployment`

## Required for every PR

- [ ] `git fetch origin main` completed; base SHA checked: `________________`
- [ ] `bash pre_session_gate.sh "<task>"` completed; branch warnings reviewed.
- [ ] Scope is limited to this PR; no unrelated branch was merged or overwritten.
- [ ] No secrets or production data are included.
- [ ] `git diff --check` passed.

## Select only applicable gates

### Material implementation, architecture, status, schema, flag, or deployment change

- [ ] I inspected the affected canonical status documents, including `ROADMAP.md` and the applicable governance/initiative plan.
- [ ] I updated only materially affected status documents, or recorded why none need updating: `________________`
- [ ] Program status, phase status, dependencies, and blockers reflect current evidence.
- [ ] `python3 tools/status_sync_validator.py --base origin/main --head HEAD --main-ref origin/main` passed.

### Core Reasoning, routing, approvals, tools, F52/UX, RP5, authority, or production-state task

- [ ] Context Librarian suggest-profile was run; manual choice recorded: `Selected profile: __________`
- [ ] The selected bundle and cited canonical sources were read; context expansions were recorded when needed.
- [ ] New authority/runtime sources have owner review and registration; no silent registration.

### Python/runtime/backend change

- [ ] `pip install -r requirements.txt` (or CI-equivalent environment) passed.
- [ ] `python3 -m compileall -q .` passed.
- [ ] `python3 smoke_tests.py` passed.
- [ ] `python3 -c "import app; import tma_api; import tools.dispatcher"` passed.
- [ ] Relevant focused tests passed with `python3 -m pytest <files> -m "not airtable and not live and not integration" -x --tb=short -q`.

### Governance, status, registry, Context Librarian, or CI guard change

- [ ] `python3 tools/dev_registry_validator.py` passed when registry files changed.
- [ ] Relevant focused guard/audit tests were run directly; no silent `python test_*.py` no-op was relied on.
- [ ] Context Librarian changes also ran `validate`, `budget-preflight --all-profiles`, and relevant focused tests.
- [ ] New audit findings are remediated or have explicit authority review.

### Frontend, schema, or deployment change

- [ ] Relevant frontend/schema/migration/deployment checks were run.
- [ ] No live or deployment verification is claimed from local tests alone.

Not-applicable gates / reason:

## Evidence and current status

- Evidence before this PR: `CODE_DONE` / `STATIC_VERIFIED` / `MERGED` / `WIRED` / `DEPLOYED` / `RUNTIME_VERIFIED`
- Evidence after this PR: `CODE_DONE` / `STATIC_VERIFIED` / `MERGED` / `WIRED` / `DEPLOYED` / `RUNTIME_VERIFIED`
- Exact SHA and test/artifact evidence:
- Remaining merge, deployment, or runtime work:

> Local tests do not prove merge, deployment, or runtime behavior. `DEPLOYED` requires exact SHA, environment, timestamp, method, and observed result. `RUNTIME_VERIFIED` requires live behavior evidence.

## Review handoff

- Risks / owner decisions:
- Status documents inspected:
- Status documents updated:
- Documents intentionally unchanged:
- Known failures or skipped checks and owner:

```text
## Status Documents Inspected
## Status Documents Updated
## Documents Intentionally Unchanged
## Evidence Level Before
## Evidence Level After This PR
## Merge Verification Required
## Deployment Verification Required
## Runtime Verification Required
## Remaining Work
```
