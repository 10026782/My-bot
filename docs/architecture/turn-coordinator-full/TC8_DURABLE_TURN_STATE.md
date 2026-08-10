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

## Closure evidence — 2026-08-10

TC8 implementation and staging runtime verification were completed on the
dedicated staging deployment at commit
`2750f8ca9b4f052e5c64adbb20459e97ed56b64f`.

Verified against the non-production PostgreSQL database
`my_bot_atomic_claims_staging`:

- PostgreSQL connection and `psycopg2` 2.9.12: PASS.
- Migration `002_durable_turn_state.sql`: PASS.
- Migration idempotency: PASS.
- Table, primary key, state/claimed/version constraints, and contract index:
  PASS.
- Persistence/reconstruction: PASS.
- CAS race and two independent repository instances: PASS.
- Tenant isolation: PASS.
- Replay/stale rejection: PASS.
- Terminal/release behavior: PASS.
- ActionContract lifecycle authority invariant: PASS.
- Staging callback/text lifecycle smoke verification: PASS.

The full regression matrix was not used as TC8 closure evidence. It was run
against shared staging Airtable state and encountered pre-existing external
ActionContracts, including `BUG-122 proposal_boundary_blocked`. The matrix is
therefore contaminated by external state and cannot distinguish a test-harness
failure from a TC8 runtime defect. TC8 does not weaken BUG-122, change PA-01,
or add isolation architecture to compensate.

### TC10 handoff

TC10 owns the missing deterministic regression harness: an isolated Airtable
test base or complete mock boundary, unique test identities, controlled
external ActionContract state, cleanup by test-owned namespace, and a repeatable
full regression run. TC10 must rerun the callback-hardening, PR-0C, BUG-158,
and complete regression matrix there. Until that handoff is complete, the
classification is:

`TC8 — IMPLEMENTATION AND STAGING VERIFIED / FINAL REGRESSION GATE DEFERRED TO TC10 HARNESS`

### TC10 handoff closure — 2026-08-10

TC10 built the isolated regression harness this section asked for:
`scripts/run_isolated_regression.py` (matrix definitions extracted to
`scripts/regression_matrix.py`), `scripts/staging_identity.py` for unique
per-run test identities and scoped cleanup, and a root-cause fix to
`scripts/verify_tc8_staging.py` itself — it no longer runs the full
regression matrix against real staging at all (that was the actual
contamination vector: subprocess env inherited the ambient shell's real
credentials). See
`docs/architecture/turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md`
for the full audit, isolation strategy, and evidence.

Callback hardening (39/39), PR-0C callbacks (8/8), and BUG-158 recovery
(11/11) all pass isolated, reproduced twice with stable results, as does
the full 21-file `FULL_REGRESSION` set (21/21, stable across 2 runs) — both
in local verification and, now, in a confirmed real CI run (PR #590 commit
`2b6ecb3`, `backend-ci` run 31362450916, `FINAL: PASS`; see harness doc
§6.2 for the linked evidence). This followed this session finding and
fixing an over-broad credential override in its own runner that had
regressed 2 of those files — the harness doc §6.1 records the full account,
including the real-CI-confirmed root cause and the real-CI-confirmed fix.
The isolated regression gate is satisfied with CI evidence, not merely
local evidence — matching the evidence-classification discipline the
harness doc itself requires.

Revised classification:

`TC8 — IMPLEMENTATION AND STAGING VERIFIED / ISOLATED REGRESSION GATE SATISFIED AND CI-CONFIRMED (TC10) / REAL-STAGING TC9 CANARY STILL PENDING`
