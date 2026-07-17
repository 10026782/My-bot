# F52 — Unified Approval Runtime Migration and Implementation

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

7b. Incremental message-standard implementation plan:
   `rollout/UNIFIED_MESSAGE_IMPLEMENTATION_PLAN.md`

8. Decision history:
   `decisions/DECISION_LOG.md`

## Authority rules

Historical audits are evidence, not implementation instructions.

The current-state and risk reports describe verified repository behavior.

The SPEC defines what must be built only after planning-gate approval.

Rollout documents define deployment, cutover and rollback only after they are
reviewed and approved.

## Current status

Planning Gate / Migration Readiness
