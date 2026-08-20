# D-020 — Gateway Runtime Path Authority and Audit Interpretation

**Date:** 2026-08-20  
**Status:** Closed for runtime-path interpretation and readiness classification.  
**Does not itself authorize Production flag activation.**

## Decision

The F52 approval runtime must not be classified as having multiple live execution
paths solely because multiple stores, branches, projections, recovery paths,
shadow callers or rollback implementations exist in source code.

A `MULTIPLE LIVE PATHS` finding is valid only when evidence proves that two
execution-authority paths are simultaneously reachable for the same action in
the same deployed runtime configuration and can independently reach a provider
mutation.

## Current authority model

- `ActionContract` is the canonical approval lifecycle authority.
- PostgreSQL `action_execution_claims` is the canonical execution-ownership
  primitive when Atomic Claims is enabled.
- verified provider execution evidence is required for a successful execution
  claim.
- TMA Airtable `Approvals` is a projection/read model, not execution authority.
- EventBus/PendingActionsStore may remain transport/recovery state without
  becoming execution authority.

## Telegram callback cutover decision

With `FEATURE_ACTION_GATEWAY=true`:

- the callback resolves a canonical ActionContract and executes through the
  Gateway lifecycle;
- if no matching contract exists, the callback fails closed;
- the legacy direct `dispatch_tool()` callback branch is not selected.

The legacy direct callback executor is therefore classified as a
Gateway-off rollback/config path, not a simultaneous Gateway-on executor.

## Separate flows that remain documented

`_pending_approvals` and `pending_lead_preview` remain separate legacy/generic
interaction flows. No explicit retirement contract was found for either during
the readiness audit.

They must not be called duplicate canonical executors without a concrete
same-action runtime trace, and they must not be silently deleted as part of the
Gateway flag flip. Any retirement is a separate migration decision.

## Readiness decision

The staging core Gateway path verified on 2026-08-20 is classified:

`READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`

The core canary proved the invariant:

`one approved contract -> one winning claim -> one executor -> one provider write -> one final reply`

Remaining completion checks are tracked as non-blocking follow-ups:

- free-text confirmation routing;
- restart persistence;
- executor failure/retry.

## Provenance boundary

The final staging canary ran on `4e44bca...`; the production/main code examined
was `09fc8a7e...`. The branches are diverged. Core Gateway and Atomic Executor
modules were unchanged in the comparison, while `app.py` contains
staging-specific confirmation-precedence changes.

Therefore the staging canary proves the core Gateway/atomic chain but does not
remove the normal production-candidate alignment/diff gate.

## Authoritative evidence

See:

- `../rollout/GATEWAY_CUTOVER_READINESS_20260820.md`
- `../rollout/CUTOVER_PLAN.md`
- `../../../PHASE_4B_ROLLOUT_AND_CUTOVER.md`
- `../../../../core/action_gateway.py`
- `../../../../core/action_gateway_atomic_executor.py`
- `../../../../app.py`
- `../../../../tma_api.py`
