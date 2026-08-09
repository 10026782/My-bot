# CORE Completion Master Plan

**Status:** planning only
**Date:** 2026-08-09
**Source of truth:** Runtime Capability Matrix and §3.5 Runtime Capability Status

## Classification

| Class | Remaining items |
|---|---|
| `BLOCKER` | TC7-B claim authorization; RP5 evidence-finalizer path; PA-01 coverage for `UPDATE_TASK`/`COMPLETE_TASK`; Staging ActionGateway canonicalization failure |
| `REQUIRED` | Production ActionGateway execution proof; atomic claims/persistence verification; TC8 durable state; TC9 MessageContract full surface; TC10 operational verification harness; CORE-vs-POST-CORE decisions |
| `HARDENING` | ~~RuntimeSchemaProvider source logging~~ (external `Track D`, closed in code 09/08/2026, runtime marker re-verification pending — see audit addendum); ~~IngressEnvelope ID/source logging~~ (external `Track D`, closed in code 09/08/2026, runtime marker re-verification pending — see audit addendum); full usage-telemetry consumption (external `Track D`, explicitly classified NOT IMPLEMENTED, 09/08/2026 — remains open, no consumer built); `INTERACTION_INTELLIGENCE` accessor drift (external `Track D`, re-verified 09/08/2026 — equivalence not provable, remains open, documented as accepted drift); broader EvidenceFinalizer sample coverage |
| `POST-CORE` | Profile, Project Timeline, Tenant Provisioner, Knowledge Router, Tenant Config/providers, OTP, Financial Gate, Creative Generator, Knowledge Engine, Emergency Window, learning-cycle activation, F14-B2 |

## Parallel tracks

### A — Action lifecycle / PA-01 / canonicalization

- **Scope:** Complete canonical proposal → approval → execution → terminal evidence for Create/Update/Complete; close `sheets_append → Tasks`; verify atomic claims/persistence; close PA-01 coverage gaps.
- **Owner:** ActionGateway / PA-01 owner.
- **Dependencies:** ActionContract authority, TC6 ownership interface, A32 evidence contract.
- **Allowed files/layers:** `core/action_gateway.py`, `core/action_contract_repository.py`, `tools/airtable_gateway.py`, PA-01 enforcement in `app.py`, focused tests and action-gateway docs.
- **Forbidden overlap:** No TC7-B claim-authorizer wiring, TurnEnvelope redesign, or observability instrumentation.
- **Verification gate:** All contract-required intents have deterministic policy coverage; Staging canonicalization passes; Staging and Production have lifecycle evidence; no phantom approval result; atomic claim/persistence behavior is verified.
- **Effort estimate:** 5–8 engineering days.
- **Merge order:** First implementation track; its evidence contract precedes Track B integration.

### B — Turn Coordinator / ownership / TC7-RP5

- **Scope:** Build TC7-B between per-action and per-turn evidence; complete RP5 claim authorization; preserve TC6 gateway ownership and PA-01 precedence.
- **Owner:** Turn Coordinator / RP5 owner.
- **Dependencies:** Track A lifecycle outcomes; A32; F52 Message Contract Foundation; RP5 shadow sample coverage.
- **Allowed files/layers:** `core/turn_envelope.py`, `core/turn_evidence.py`, RP5 boundary, ownership-related `app.py`, focused tests and Turn Coordinator/RP5 docs.
- **Forbidden overlap:** No ActionGateway state-machine changes, Airtable canonicalization, new reply owner, or competing formatter.
- **Verification gate:** Real shadow samples cover required evidence states; TC7-B consumes evidence; RP5 cannot overwrite PA-01 terminal outcomes; ownership tests and production canary evidence pass.
- **Effort estimate:** 6–10 engineering days after dependencies.
- **Merge order:** Design may run in parallel with Track A; implementation merges after Track A’s evidence contract is stable.

### C — Runtime observability / telemetry / drift

> **Naming-collision note (added 09/08/2026, not a scope change):** this
> document's internal letter **"C"** was assigned when this plan was
> drafted and predates the external `Track A`–`Track E` naming currently
> used in branch names and task assignments, where **`Track C` = TC8/TC9/
> TC10** and **`Track D` = Runtime Observability/Reliability** (this
> section's actual subject). The two lettering schemes have drifted apart
> and this document has not been renumbered to reconcile them. The
> "Progress" entry below is **external `Track D`** work — filed under this
> internal "C" heading only because its *content* matches this section's
> own Scope description, not because it is the externally-tracked
> `Track C` (TC8/TC9/TC10). Do not read it as TC8/TC9/TC10 progress.

- **Scope:** Add provider source/result observability, envelope ID/source-reference observability, decide or complete usage-telemetry consumption, and resolve/document centralized feature-flag drift.
- **Owner:** Reliability / observability owner.
- **Dependencies:** Stable provider, ingress, and evidence interfaces.
- **Allowed files/layers:** `core/runtime_schema_provider.py`, `tools/airtable_gateway.py`, ingress adapters, bounded `app.py` logging, `core/usage_telemetry.py`, `scheduler.py`, focused tests/docs.
- **Forbidden overlap:** No routing, approval, canonicalization, flag, or deployment behavior changes.
- **Verification gate:** Logs distinguish `live`/`cached`/`snapshot`/`seed`; envelope fields are observable without sensitive data; telemetry has a verified consumer or explicit deferral; drift is resolved or accepted.
- **Effort estimate:** 3–5 engineering days.
- **Merge order:** Parallel; merge after Tracks A/B stabilize interfaces.
- **Progress (09/08/2026, external `Track D` — Runtime Observability/
  Reliability; see naming-collision note above — NOT the externally-tracked
  `Track C`/TC8-TC10):** RuntimeSchemaProvider `live`/`cached`/`snapshot`/
  `seed` logging and IngressEnvelope ID/source logging are implemented and
  tested, code-level only — no fresh runtime/Render evidence yet (see
  `docs/audit/RUNTIME_CAPABILITY_AUDIT_20260809.md`'s Track D addendum for
  the precise "CODE OBSERVABILITY IMPLEMENTED + TESTED — NEW MARKER NOT YET
  OBSERVED IN RUNTIME" status); usage-telemetry has an explicit
  producer-ACTIVE/consumer-NOT-IMPLEMENTED classification, with no consumer
  built (deliberately out of scope); `INTERACTION_INTELLIGENCE` accessor
  drift was re-verified as not safely resolvable (semantic mismatch on
  `"1"`/`"yes"`/`"on"`/`"enabled"`) and left unchanged, accepted drift.
  EvidenceFinalizer sample coverage is untouched.

### D — Secondary audit and CORE-vs-POST-CORE decisions

- **Scope:** Decide which code-present systems belong inside CORE; move the rest to POST-CORE with owners and evidence criteria.
- **Owner:** Architecture / product owner.
- **Dependencies:** Current Runtime Matrix and §3.5 only.
- **Allowed files/layers:** Audit documents, §3.5, ROADMAP references, subsystem authority docs.
- **Forbidden overlap:** No wiring, activation, refactor, implementation, or flag changes.
- **Verification gate:** Every `CODE-ONLY`/`UNKNOWN` subsystem has a CORE requirement, POST-CORE classification, or explicit owner decision; none is labeled disconnected from silence.
- **Effort estimate:** 1–2 engineering days.
- **Merge order:** First documentation decision; required before final CORE sign-off.

### E — Final integration / regression gate

- **Scope:** Cross-track regression, evidence reconciliation, Production/Staging matrix refresh, rollback/readiness review.
- **Owner:** Release / reliability owner.
- **Dependencies:** Tracks A–D merged.
- **Allowed files/layers:** Tests, audit evidence, §3.5 status, release/runbook documents.
- **Forbidden overlap:** No new feature work or opportunistic bug fixes.
- **Verification gate:** Focused suite passes; environments remain separate; every BLOCKER/REQUIRED item has proof; no contradictory current-state claim remains.
- **Effort estimate:** 2–3 engineering days.
- **Merge order:** Final merge gate only.

## Schedule and critical path

Tracks C and D can run in parallel with Tracks A and B. Estimated calendar
time to `CORE COMPLETE`: **10–15 working days**, assuming no new Production
blocker and timely evidence access.

Critical path:

`Action lifecycle + PA-01 + canonicalization`
→ `TC7-B / RP5 claim authorization`
→ `TC8 durable state`
→ `TC9 MessageContract full surface`
→ `TC10 verification harness`
→ final integration gate.

## Definition of `CORE COMPLETE`

CORE is complete only when:

1. Create, Update, and Complete ActionContract lifecycles are verified,
   including canonicalization and atomic execution ownership.
2. PA-01 covers all contract-required intents without phantom approval claims.
3. TC7-B connects action evidence to turn evidence and RP5 authorization is
   operational.
4. TC6 single-speaker ownership remains enforced on verified approval paths.
5. Required durable state, MessageContract, and operational verification gates
   are closed.
6. Production and Staging evidence are separately verified.
7. Runtime observability is sufficient to diagnose provider source, envelope
   identity, evidence state, and telemetry consumption.
8. Every remaining system is explicitly CORE or POST-CORE.
9. Final regression, rollback, and status-source checks pass.

This document authorizes no implementation, finding fix, environment change,
deployment, or PR by itself.
