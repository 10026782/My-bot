# F52 — Unified Approval Runtime Migration and Implementation

**Last Updated:** 2026-08-27

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

## F52 closure ledger

| Area | Status | Evidence / residual |
|---|---|---|
| F52 overall | PARTIALLY CLOSED | G1/G4/G5 remain open current gaps |
| F52-G1 | OPEN — CURRENT GAP | Dispatcher-wide execution proof remains out of scope |
| F52-G2 | CLOSED — STATIC VERIFIED | Commit `f17bfe9`; verified `origin/main` `d2ec703`; runtime NOT ESTABLISHED |
| F52-G3 | CLOSED — STATIC VERIFIED | S1–S7 close all current business-truth string consumers; only display/test assertions remain |
| F52-G4 | OPEN — CURRENT GAP | Scheduler/background normalization remains out of scope |
| F52-G5 | OPEN — CURRENT GAP | Durable generic evidence ledger remains out of scope |

### F52-G3-S1 — LeadMemory result migration

- Previous: OPEN; new: CLOSED — STATIC VERIFIED.
- Consumer: `lead_memory.py::LeadMemory._write` via `flush()` / `flush_all()`.
- Legacy parsers removed: success inferred from `"✅"` and record ID extracted from rendered `airtable_get()` text.
- Structured authority: `airtable_update()`'s `dict["ok"]` and `airtable_get_records()`'s record `id`.
- PR / commit: PR #1051, commit `2b58d16`; verified main `3039ba5`; runtime NOT REQUIRED FOR STATIC CLOSURE.
- Residual G3 consumers: `ad_attribution.py`, `inbound_handler.py`, `core/lead_buffer.py`, plus other audit-listed legacy paths.

### F52-G3-S2 — Structured attribution result migration

- Status: CLOSED — STATIC VERIFIED.
- Consumer: `ad_attribution.py::record_lead_source`.
- Legacy parser removed: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_get_records()` record `id`; write outcome remains `LeadCreateResult.ok`.
- PR / commit: PR #1052, commit `2945e44`; verified origin/main `9a1950c`.
- Remaining G3 consumers: `ad_attribution.py::mark_converted`, `inbound_handler.py`, `core/lead_buffer.py`, plus other audit-listed legacy paths.
- Runtime NOT REQUIRED FOR STATIC CLOSURE.

### F52-G3-S3 — Structured conversion result migration

- Status: CLOSED — STATIC VERIFIED.
- Consumer: `ad_attribution.py::mark_converted`.
- Legacy parser removed: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_get_records()` record `id`; conversion outcome remains `airtable_update()`'s `dict["ok"]`.
- PR / commit: PR #1053, branch commit `7b92d7a`; verified origin/main `edcdc57`.
- Residual G3 consumers: `inbound_handler.py`, `core/lead_buffer.py`, plus other audit-listed legacy paths.
- Runtime NOT REQUIRED FOR STATIC CLOSURE.

### F52-G3-S4 — Structured inbound duplicate lookup migration

- Status: CLOSED — STATIC VERIFIED.
- Consumer: `inbound_handler.py::_find_by_external_id`.
- Legacy parser removed: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_get_records()` record `id`; duplicate decision uses the returned identity.
- PR / commit: PR #1055, merge commit `bb782da`; verified origin/main `bb782da`.
- Residual G3 consumers: `inbound_handler.py::_find_by_sender`, `core/lead_buffer.py`, plus other audit-listed legacy paths.
- Runtime NOT REQUIRED FOR STATIC CLOSURE.

### F52-G3-S5 — Structured inbound sender lookup migration

- Status: CLOSED — STATIC VERIFIED.
- Consumer: `inbound_handler.py::_find_by_sender`.
- Legacy parser removed: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_get_records()` record `id`; sender-match decision uses the returned identity.
- PR / commit: PR #1056, merge commit `894abbe`; verified origin/main `c040319`.
- Residual G3 consumers: `core/lead_buffer.py`, plus other audit-listed legacy paths.
- Runtime NOT REQUIRED FOR STATIC CLOSURE.

### F52-G3-S6 — Structured LeadBuffer recovery lookup migration

- Status: CLOSED — STATIC VERIFIED.
- Consumer: `core/lead_buffer.py::recover_blocked_lead_payload`.
- Legacy parser removed: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_read_adapter.list_records()` record `id`; recovery patch target uses the returned identity.
- PR / commit: PR #1058, merge commit `d6e0718`; verified origin/main `d6e0718`.
- Residual business-truth G3 consumers: `lead_capture.py::capture_inbound_lead` remains category A; `core/lead_buffer.py` has no further occurrence.
- Runtime NOT REQUIRED FOR STATIC CLOSURE.

### F52-G3-S7 — Structured Lead Capture lookup migration

- Status: IMPLEMENTED / STATIC TESTED (pending merge verification).
- Consumer: `lead_capture.py::capture_inbound_lead`.
- Previous authority: record identity extracted from rendered `airtable_get()` text via regex.
- Structured authority: `airtable_read_adapter.list_records()` record `id`; FOUND and Lead Event decisions use that identity.
- PR / commit: PR #1060, implementation commit `ce39b5e`.
- Tests: focused S7 `5 passed`; Lead Capture/structured-result regressions `8 passed`; response-contract regression `19 passed`.
- G3 closure basis: no current business-state consumer derives success, record identity, or persistence truth from display strings.
- Residual business-truth parsers: NONE.
- Residual display/test assertions: `media_handler.py:852`, `startup_validator.py:353`.
- Runtime NOT REQUIRED FOR STATIC G3 CLOSURE.
