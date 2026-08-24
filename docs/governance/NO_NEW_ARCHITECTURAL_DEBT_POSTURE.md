# No New Architectural Debt — Phase 1 Posture

**Truth reset:** `origin/main` at `7e3dcf9` (2026-08-25).

## Current enforcement posture

| Guard | CI mode | Status | Reason |
| --- | --- | --- | --- |
| A1 Provider Boundary | `BLOCKING` | Blocking | AST fingerprints are useful, but adapter allowlists still need symbol-level hardening. |
| A2 Direct Model / Agent Calls | `BLOCKING` | Blocking | AST target fingerprints are useful, but the approved adapter is currently whole-file scoped. |
| A3 Dispatcher / Tool Bypass | `WARN_ONLY` | Partial | Pending stable-identity hardening; line movement has produced confirmed false positives. Findings remain visible. |
| A4 Writer / Authority Registration | `BLOCKING` | Blocking | Delta/registry enforcement is active; broader move/refactor and writer-shape coverage remains future hardening. |
| A5 Public Renderer / MessageContract | `WARN_ONLY` | Partial | Pending AST-only hardening; regex/comment/self-scan noise has been observed. Findings remain visible. |

The overall posture is:

> **`PARTIAL — NOT ESTABLISHED`**

This phase intentionally reduces CI noise without removing A3/A5 detection or
creating new baselines for their findings. `continue-on-error: true` is limited
to the two named WARN_ONLY steps so their reports and exit status remain visible
in CI while they do not fail the job.

## Phase 1 verification contract

- A3 and A5 still execute their normal commands and print findings.
- A3/A5 findings do not fail the CI job during this stabilization phase.
- A1, A2, and A4 remain blocking and continue to fail on synthetic violations.
- No runtime or business logic is changed.
- No false positive is baselined merely to make the report green.

## Governance recommendations

> **Guard that has produced a confirmed false positive cannot remain blocking
> until the failure mode is covered by regression tests.**

> **Enforcement must not be noisier than the architectural risk it prevents.**

> **A blocking architecture guard must prove both sides:** real violation fails;
> harmless change passes.

These are governance recommendations for the next SPEC/HORIZON update. This
Phase 1 slice does not modify those source documents.

## Next hardening order

`A2 → A1 → A4 → A3 stable identity → A5 AST rewrite → final noise verification`
