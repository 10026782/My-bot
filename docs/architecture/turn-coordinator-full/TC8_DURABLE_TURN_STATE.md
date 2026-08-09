# TC8 durable turn state contract

This module provides coordination state only. `ActionContract` remains the
approval and execution lifecycle authority; `active_contract_id` is a reference
and never a copied lifecycle status.

## State and invariants

`durable_turn_state` has one row per `(tenant_id, canonical_user_id)`:

- `turn_id`: the turn represented by the row.
- `active_contract_id`: optional reference to the canonical ActionContract.
- `state`: `active`, `claimed`, `released`, or `terminal`.
- `owner_kind` and `operation_id`: required together while `claimed`; owner kind
  is `callback` or `text`.
- `version`: starts at 1 and increments exactly once for every accepted
  mutation.
- `updated_at` and bounded `terminal_reason`: recovery/audit metadata only.

Creation uses a unique identity key. Claims and owner finalization use a
conditional `UPDATE ... WHERE version = expected_version`; zero affected rows
are conflicts, never success. A claim is allowed only from `active`. Release
and terminal finalization are allowed only from `claimed` by the same
`operation_id`. Released and terminal rows cannot be claimed again.

Missing identity/version, malformed rows, stale versions, competing owners,
terminal replay, and unavailable storage fail closed.

## Race and recovery proof

Callback approval, callback rejection, and text confirmation each use a
distinct operation id and call `claim()` against the same identity row. The
database update serializes them: exactly one receives the returned row; every
other path receives `TurnStateConflictError` and cannot become effective
owner. A second callback is rejected after the first path finalizes or releases
the row. Reconstructing `TurnStateRepository` reads the same PostgreSQL row,
so restart and independent service instances retain the version and owner.

Ingress wiring is an integration seam owned by the Track C integrator. This
integration now exists in `app.py` at the callback approve/reject and text
confirm/cancel boundaries. It claims the exact ActionContract reference before
the existing authoritative lifecycle call, then finalizes/releases from the
read-back ActionContract status. It does not edit ActionGateway, EventBus, or
TMA lifecycle semantics. If PostgreSQL/schema access is unavailable, those
mutation paths fail closed instead of falling back to in-memory ownership.
