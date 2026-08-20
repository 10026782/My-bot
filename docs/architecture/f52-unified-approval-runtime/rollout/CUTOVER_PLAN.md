# F52 Gateway Cutover Plan

**Last Updated:** 2026-08-20  
**Status:** `READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`  
**Production activation:** Not performed by the readiness audit.

## Read first

The full verified runtime classification, code evidence, canary evidence,
retirement map and future-audit guard are recorded in:

`GATEWAY_CUTOVER_READINESS_20260820.md`

That document is the current Gateway cutover/readiness authority.

## Verified architecture conclusion

There is no proven `MULTIPLE LIVE PATHS` conflict for the same approval action
in the same deployed configuration.

Do not treat the simultaneous presence of ActionContracts,
PendingActionsStore/EventBus, `_pending_approvals`, `pending_lead_preview`, TMA
Approvals projection, shadow code and rollback branches as proof of competing
execution authorities.

A duplicate-execution defect requires runtime reachability evidence for the same
action and same configuration.

## Current production selection observed during readiness work

Production code examined: `09fc8a7e...`

- `FEATURE_ACTION_GATEWAY=false` by missing-env default.
- `FEATURE_ACTION_CONTRACT_PERSISTENCE=true`.
- `FEATURE_ATOMIC_CLAIMS=true`.
- `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true`.
- `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS=true`, with Gateway-dependent
  behavior not fully effective while Gateway is off.

Production was not changed.

## Staging readiness evidence

Final core canary code: `4e44bca...`

All five approval/cutover flags were ON. The canary proved:

- durable ActionContract persistence;
- PostgreSQL atomic claim;
- provider write;
- exactly one write for a successful approval;
- duplicate/concurrent approval does not double-execute;
- exactly one final reply;
- cleanup succeeded.

Core invariant:

`one approved contract -> one winning claim -> one executor -> one provider write -> one final reply`

## Activation effect that must not be misread

When `FEATURE_ACTION_GATEWAY=true`, `app.py::_handle_approval_callback_impl()`
uses the ActionContract/Gateway lifecycle. If no matching contract exists, it
fails closed and refuses legacy dispatch.

The direct callback `dispatch_tool()` branch exists only when
`FEATURE_ACTION_GATEWAY` is OFF. It is therefore a rollback/config path, not a
simultaneous Gateway-on executor.

## Retained / transitional paths

Retain during cutover unless separately migrated:

- EventBus / PendingActionsStore as transport/recovery.
- Atomic flag-off direct executor as rollback mode.
- TMA Airtable Approvals as projection/read model.
- `_pending_approvals` for generic `Handler.APPROVAL` routes — no explicit
  retirement contract found.
- `pending_lead_preview` for Tier-2 batch previews — no explicit retirement
  trigger found.

The last two are separate migration follow-ups and must not be silently removed
inside the Gateway flag activation.

## Candidate-alignment gate before Production activation

The staging canary SHA `4e44bca...` and current `main` SHA `09fc8a7e...` are
diverged. `core/action_gateway.py` and
`core/action_gateway_atomic_executor.py` were unchanged in the comparison, and
the callback implementation was not modified by the staging-only app diff, but
`app.py` does contain staging-specific confirmation-precedence changes.

Before Production activation, prove the actual production candidate preserves
the verified approval/callback behavior.

## Documented non-blocking completion tests

- free-text `כן` / `לא` routing;
- restart/redeploy ActionContract persistence;
- executor failure / retry without false success or duplicate provider write.

## Production activation checklist

1. Record exact candidate SHA.
2. Re-run approval-path diff/alignment against the verified staging behavior.
3. Confirm migrations/DB health and Atomic Claims READY.
4. Confirm Emergency Stop state.
5. Record current Production flag values for rollback.
6. Activate only the reviewed Gateway configuration.
7. Run a low-risk approval smoke canary.
8. Verify one contract / one claim / one executor / one provider write / one final reply.
9. Verify legacy callback `dispatch_tool()` was not selected.
10. Monitor lifecycle and claim errors; rollback on any authority or duplicate-write invariant breach.

## Abort criteria

Abort/rollback the cutover if any of the following occurs:

- provider write without an ActionContract-backed Gateway execution;
- more than one provider write for one approved contract;
- callback reaches the legacy direct-dispatch branch while Gateway is ON;
- claim storage unavailable and execution does not fail closed;
- false success is reported without verified provider execution evidence.
