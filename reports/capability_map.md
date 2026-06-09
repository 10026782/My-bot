# BOSS Capability Map

Generated: 2026-06-08

Scope: system_registry.yaml, registry_calibration_report.md, Discovery Audit, ROADMAP.md, BOSS_CURRENT_STATE.md.

Rules observed: reports only; no code changes; no auth changes; no Airtable writes; no feature implementation.

## Summary

- System Health: 61%
- Total Capabilities: 23
- Working Count: 7
- Partial Count: 12
- Stub Count: 4
- Broken Count: 0
- Unused Count: 0

Health formula: WORKING=100, PARTIAL=50, STUB=20, BROKEN=0, UNUSED=10.

## Critical Systems

| System | Status | Owner | Evidence | Next Blocker |
|---|---|---|---|---|
| Leads | PARTIAL | growth | tma_api.py:838; airtable_schema.py:189; ROADMAP.md W0/W1 | Live scoring and lead_memory wire-up are next. |
| Tasks | WORKING | operations | tma_api.py:929; tools/airtable_tools.py:17 | TMA follow-up task writes are approval-gated, but broader task UX is not mapped here. |
| Payments | WORKING | finance | tma_api.py:503; tma_api.py:1060; airtable_schema.py:121 | Needs live production Airtable spot check for finance formulas. |
| ProjectsHub | PARTIAL | tma | tma_api.py:571; tma_api.py:688; airtable_schema.py:348 | Project hub reads/writes exist, navigation and partner UX remain limited. |
| Approvals | WORKING | security | tma_api.py:1151; tma_api.py:1200; airtable_schema.py:385 | Receipt persistence/display is still missing. |

## CRM

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Leads | PARTIAL | growth | Leads, tma_api, lead_capture, schema_intelligence | tma_api.py:808; tma_api.py:838; airtable_schema.py:189; BOSS_CURRENT_STATE.md Lead Flow | N02 live scoring, N03 memory wire-up, N04 followup activation. |
| Contacts | PARTIAL | crm | Contacts, airtable_tools, schema_intelligence | airtable_schema.py:135; tools/airtable_tools.py:21; schema_intelligence.py:34 | No owner-facing TMA contacts screen confirmed in current discovery. |
| Deals | PARTIAL | crm | Deals, tma_api, airtable_tools | tma_api.py:757; airtable_schema.py:147; tools/airtable_tools.py:25 | Deals are read for dashboards, but not a complete owner workflow. |
| Followups | PARTIAL | operations | Leads, Tasks, Approvals, tma_api | tma_api.py:929; tma_api.py:953; ROADMAP.md N04 | TMA follow-up creates approval request, but automated followup activation is still next. |

## TMA

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Auth | WORKING | security | Telegram initData, identity, TMA_ALLOWED_ORIGINS | tma_api.py:625; BOSS_CURRENT_STATE.md C39 | Keep Render/Vercel env drift monitored. |
| Projects Hub | PARTIAL | tma | ProjectsHub, Leads, Payments, Tasks | tma_api.py:661; tma_api.py:686; reports/registry_calibration_report.md | Navigation/project detail UX remains limited. |
| Finance Pulse | STUB | finance | Payments, Expenses | BOSS_CURRENT_STATE.md Module State Matrix; tma_api.py:1060; tma_api.py:1111 | Current state marks it stub/limited despite partial data reads. |
| Activity Feed | PARTIAL | intelligence | Business Memory, Interaction Log | tma_api.py:1264; BOSS_CURRENT_STATE.md Activity Feed | Receipts are returned by approval response but not persisted/shown. |
| Assets | PARTIAL | personal | Assets, tma_api, Airtable metadata | tma_api.py:1323; tma_api.py:1365; reports/registry_calibration_report.md Stale Tables | Runtime uses Assets, schema comment says Assets (Personal). |

## Approvals

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Approval Queue | WORKING | security | Approvals, event_bus, tma_api | tma_api.py:1151; tma_api.py:1200; ROADMAP.md C40 | Bulk approval path should stay low-risk only. |
| Receipts | PARTIAL | security | Approvals, Interaction Log, Activity Feed | tma_api.py:324; tma_api.py:1258; BOSS_CURRENT_STATE.md Golden Path | Receipt persistence and Activity Feed display not implemented. |

## Game

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Worlds | WORKING | game | Worlds, tma_api, scheduler | tma_api.py:1508; scheduler.py:422 | Needs live Airtable data quality check. |
| Quests | WORKING | game | Quests, Coins_Log, tma_api | tma_api.py:1529; tma_api.py:1590; app.py:116 | Quest write paths are direct owner-only writes, not approval-gated. |
| Coins | WORKING | game | Coins_Log, Quests, Daily_Tasks | tma_api.py:1552; tma_api.py:1599; tma_api.py:1714 | Running total is app-side and depends on existing log consistency. |
| Daily Tasks | WORKING | game | Daily_Tasks, Coins_Log | tma_api.py:1631; tma_api.py:1697 | Owner-only direct completion writes. |

## Communications

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Telegram | PARTIAL | owner | app.py, Telegram Bot API, router, tools | app.py routes; ROADMAP.md C19; BOSS_CURRENT_STATE.md Telegram agent | Tool/approval chain is improved but overall agent path remains partial. |
| WhatsApp | PARTIAL | growth | Twilio, app.py, lead_capture, Leads | ROADMAP.md C32/W0; BOSS_CURRENT_STATE.md WhatsApp webhook | Outbound remains honest stub; Meta Cloud API blocks production outbound. |
| Voice | STUB | operations | Twilio voice endpoints | BOSS_CURRENT_STATE.md Open Risks; ROADMAP.md F07 | Voice/IVR is future/white-glove and lacks full validation path. |
| Email | STUB | communications | Google OAuth, email_inbound | ROADMAP.md C28/F06; BOSS_CURRENT_STATE.md Email tools | Honest stub until Google tools/channel are fully live. |

## Operations

| Capability | Status | Owner | Dependencies | Evidence Files | Next Blocker |
|---|---|---|---|---|---|
| Scheduler | PARTIAL | operations | scheduler.py, feature flags, Airtable, Telegram | scheduler.py:679; BOSS_CURRENT_STATE.md Workers / scheduler | Some jobs active, some gated or dependent on env/imported engines. |
| Learning | STUB | intelligence | core/learning_engine.py, core/lead_events.py | ROADMAP.md F02; BOSS_CURRENT_STATE.md Learning system | No real production learning loop yet. |
| Memory | PARTIAL | intelligence | memory_store, lead_memory, context | ROADMAP.md C08/F10; BOSS_CURRENT_STATE.md Memory system | RAM-only and lead_memory not wired into lead capture yet. |
| Governance | WORKING | owner | system_registry.yaml, system_registry_audit.py, reports | system_registry.yaml; reports/registry_calibration_report.md | Needs Airtable metadata confirmation for stale Assets naming. |

## Owner Takeaway

- The owner can rely most on: Auth, Approvals, core TMA write gate, Payments data reads, Game tables, Governance registry.
- The system is improving but not fully partner-ready because Leads/Followups/Memory/Receipts are still partial.
- The most important visible blocker is receipt persistence/display after approval execution.
