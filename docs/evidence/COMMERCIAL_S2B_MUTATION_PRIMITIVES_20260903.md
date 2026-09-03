# Commercial V2 S2B — Narrow Mutation Primitives Evidence

**Date:** 03/09/2026 (Asia/Jerusalem)
**Branch:** `codex/commercial-v2-s2b-mutation-primitives`
**Base:** `origin/main` `23ab957e75961c7b50f929e263eddd3f0d6632c8`
**Evidence:** `CODE_DONE + STATIC_VERIFIED`
**Not claimed:** merged, deployed, wired to the completion engine, live-write
canary, runtime verified, reader/writer cutover

## Implemented scope

- `commercial_crm.find_or_create_organization`: universal Organization identity
  by exact normalized name. Trim and whitespace collapse are deterministic;
  comparison is case-insensitive; submitted display spelling is preserved on
  create. Zero matches creates, one reuses, and multiple matches fail closed.
- `commercial_crm.create_charge`: Deal-required canonical Charge create with
  optional same-Deal Billing Term, native Currency Code, explicit dates and
  document state, and no writable formula/rollup/reverse-link inputs.
- `commercial_crm.create_charge_payment`: actual `received` movement only;
  Charge is mandatory and exactly determines the accepted Deal, Direction,
  Currency, and optional Payment Term relationship.
- Internal-only tool metadata, required-field validation, Airtable evidence
  validators, dedicated dispatcher cases, protected generic-create redirects,
  and fail-closed generic updates for Organizations and Charges.
- Context Librarian node `decision.commercial_v2_mutation_primitives` and exact
  symbol ownership in the Writer Authority Registry.

## Preserved boundaries

- No Airtable schema or record write was performed during S2B.
- The legacy `commercial_crm.create_payment` implementation is unchanged and
  the existing legacy Payment is not read, updated, linked, migrated, or
  reinterpreted.
- No Agent tool schema exposes the three primitives.
- No completion-engine caller, route, reader, channel, Mini App, scheduler,
  Contact writer, auto-Charge generator, allocation primitive, or production
  execution authority was introduced.
- ActionGateway remains the approval and idempotency owner; dispatcher execution
  proof is action-, identity-, tenant-, and exact-payload-bound.

## Static verification

- `python3 -m pytest -q tests/test_commercial_v2_mutation_primitives.py`:
  **28 passed**.
- Existing commercial/schema/completion/Contact regression group:
  **63 passed, 17 subtests passed**.
- Existing protected generic CRM bypass suite: **1 passed**.
- `python3 test_action_gateway.py`: **46 checks passed**. This repository test
  intentionally calls `sys.exit()` at module scope, so its supported direct
  invocation was used rather than pytest collection.
- Edited Python modules compile successfully and `git diff --check` is clean.
- CI-aligned Context Librarian, status-sync, and reconciliation pytest group:
  **264 passed**; smoke checks passed.
- Context Librarian catalog validation passed with **44 nodes, 27 edges, and 8
  profiles**. Reconciliation has an empty decision queue and no ownership
  conflict; its `AUTO_MAINTENANCE_REQUIRED` result contains only mechanical
  provenance refreshes from the merged S2A baseline.
- Writer Authority / development registry validation passed with **45 rows**.

## Context verification ledger

- Selected profile: `cross_layer_architecture` after displaying all suggestion
  scores; the approval/tool-execution tie was not auto-resolved.
- Bundle budget: estimated 14,080 / 14,300 tokens, overflow 0, 49/49 documents.
- Direct source expansion beyond the bundle covered `commercial_crm.py`, owner
  resolution, runtime schema/read adapters, Airtable gateway, anti-hallucination
  evidence, commercial tests, and the field completion matrix. This recurring
  expansion was necessary to verify writer, read-before-write, evidence, and
  field-parity boundaries rather than infer them from navigation metadata.

## Status Documents Inspected

`ROADMAP.md`, `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`,
`docs/governance/HORIZON.md`, the commercial writer design, the S2A schema
status, `CHANGE_CONTROL_LOG.md`, and the maintenance audit ledger.

## Status Documents Updated

The active roadmap/master-plan/horizon projections, commercial writer design,
commercial schema status, change-control log, maintenance ledger, Context
Librarian registry, and Writer Authority Registry.

## Documents Intentionally Unchanged

Historical S2A evidence is unchanged. Schema constants and the completion field
matrix already match the merged S2A live schema and are not rewritten by a
mutation-only slice.

## Evidence Level Before

S2A `MERGED + LIVE_SCHEMA_VERIFIED`; S2B not implemented.

## Evidence Level After This PR

S2B `CODE_DONE + STATIC_VERIFIED` on the PR branch.

## Merge Verification Required

Yes. After merge, fetch `origin/main`, prove commit ancestry, and grep the three
exact writer symbols and decision-node registration on current main.

## Deployment Verification Required

Yes, before any deployment claim. This PR does not request a production wiring
or route change.

## Runtime Verification Required

Yes, under a separately approved live-canary plan. None was run in S2B.

## Remaining Work

Merge verification; separately gated deployment/live canary; and separate owner
decisions for completion-engine wiring, reader/writer cutover, updates,
allocation/economics primitives, and any additional callers.
