# F52 — Unified Approval Runtime Migration and Implementation

**Last Updated:** 2026-08-20

## Purpose

F52 is the formal program for migrating all approval-required execution to one
durable, canonical and atomically claimed runtime.

The work was discovered during Lead Capture investigation, but the scope is
system-wide and includes Telegram, TMA, WhatsApp, internal tools, media,
background jobs, contracts, claims, identity, projections and legacy migration.

## Historical identifier

The research phase was previously named Phase 4C.

Phase 4C remains as a historical research identifier only.

## Document hierarchy

1. Historical baseline audits:
   `audits/original/`

2. Latest verified runtime audit:
   `audits/phase-4c/CURRENT_STATE_MAP.md`

3. Current risk authority:
   `audits/phase-4c/GAP_AND_RISK_REPORT.md`

3b. Turn-ownership extension (consumed by `../turn-coordinator/` Phase 0 — adds
    reply-ownership, pending-queue-source, message-kind and agent-dependency
    dimensions on top of the AP-01..AP-50 inventory; does not replace it):
   `audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`

3c. Unified user-message output baseline:
   `audits/phase-4c/AGENT_MESSAGE_OUTPUT_MAP.md`

4. Migration analysis:
   `research/MIGRATION_OPTIONS.md`

5. Open and closed decisions:
   `research/OPEN_QUESTIONS.md`

6. Canonical implementation specification:
   `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`

6b. User-message semantic and UX standard:
   `spec/UNIFIED_MESSAGE_UX_STANDARD.md`

7. Rollout authority:
   `rollout/`

7a. **Latest Gateway cutover/readiness authority (2026-08-20):**
   `rollout/GATEWAY_CUTOVER_READINESS_20260820.md`

7b. Incremental message-standard implementation plan:
   `rollout/UNIFIED_MESSAGE_IMPLEMENTATION_PLAN.md`

8. Decision history:
   `decisions/DECISION_LOG.md`

8a. **Gateway runtime-path authority decision (2026-08-20):**
   `decisions/D-020_GATEWAY_RUNTIME_PATH_AUTHORITY_20260820.md`

## Authority rules

Historical audits are evidence, not implementation instructions.

The current-state and risk reports describe verified repository behavior.

The SPEC defines what must be built only after planning-gate approval.

Rollout documents define deployment, cutover and rollback only after they are
reviewed and approved.

### Runtime-path interpretation guard

Do **not** report `MULTIPLE LIVE PATHS` merely because multiple approval stores,
branches, projections or fallback implementations are present in source code.

A duplicate live-execution finding requires proof that two execution-authority
paths are both reachable for the same action in the same deployed flag/runtime
configuration and can independently reach a real provider mutation.

Use `rollout/GATEWAY_CUTOVER_READINESS_20260820.md` for the verified
classification of Gateway, EventBus/PendingActionsStore, `_pending_approvals`,
`pending_lead_preview`, TMA Approvals projection, persistence and atomic claims.

The durable audit-interpretation decision is recorded in
`decisions/D-020_GATEWAY_RUNTIME_PATH_AUTHORITY_20260820.md`.

## Current status

**Gateway Cutover Readiness:** `READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`
(as verified on staging core path on 2026-08-20; Production was not changed).

Important provenance boundary: the final staging canary ran on `4e44bca...`,
while the production/main code examined was `09fc8a7e...`. The branches are
diverged; the core Gateway/atomic modules were unchanged in the comparison,
but production activation still requires the normal candidate-alignment/diff
gate described in the readiness report.
