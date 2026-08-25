# No New Architectural Debt — Phase 1 Posture

**Truth reset:** final guard verification against `origin/main` (2026-08-25).

## Current enforcement posture

| Guard | CI mode | Status | Reason |
| --- | --- | --- | --- |
| A1 Provider Boundary | `BLOCKING` | Blocking | AST fingerprints are useful, but adapter allowlists still need symbol-level hardening. |
| A2 Direct Model / Agent Calls | `BLOCKING` | Blocking | AST target fingerprints are useful, but the approved adapter is currently whole-file scoped. |
| A3 Dispatcher / Tool Bypass | `BLOCKING` | Blocking | Stable path/module/imported-symbol/ordinal identity is line-shift tolerant; duplicate new imports remain visible. |
| A4 Writer / Authority Registration | `BLOCKING` | Blocking | Added-line detection is reconciled against the origin/main stable path/symbol snapshot, so harmless moves do not create new debt. |
| A5 Public Renderer / MessageContract | `BLOCKING` | Blocking | Renderer and MessageContract entry detection is AST-only; comments and strings are excluded. |

The overall posture is:

> **`ESTABLISHED`**

All five architecture guards are now blocking. Each guard has both sides of the
verification contract: harmless changes pass, while synthetic real violations
fail. No runtime or business logic is changed by the guard system.

## Phase 1 verification contract

- A1–A5 execute their normal commands and print findings.
- A1–A5 fail on synthetic real violations.
- A1–A5 pass harmless line shifts, unrelated insertions, approved paths, and legacy cases covered by their identity models.
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

Final noise verification completed; continue monitoring guard findings for confirmed false positives under the governance rules below.
