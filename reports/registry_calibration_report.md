# Registry Calibration Report

Generated: 2026-06-08

Scope: system_registry.yaml, system_registry_audit.py, discovery audit, airtable_schema.py, schema_intelligence.py, tma_api.py.

## Executive Summary

- Registry phase: CORE_03_GOVERNANCE_PHASE_2_1.
- Registry coverage after calibration: 29 / 29 known Airtable tables = 100%.
- No Airtable writes were performed.
- No business logic or auth code was changed.
- Registry now includes owner, status, criticality, dependencies, and last_audit for every registered table.
- Data flows added: Lead Flow, TMA Flow, Game Flow.

## Evidence Sources

- airtable_schema.py:10 defines the canonical Tables class.
- airtable_schema.py:189 defines current Leads fields, including score, tier, tenant_id, domain.
- airtable_schema.py:348 defines ProjectsHubFields.
- airtable_schema.py:367 documents AssetsFields as Assets (Personal), while runtime uses Assets.
- airtable_schema.py:385 defines ApprovalsFields.
- schema_intelligence.py:13 defines the write-validation SCHEMA subset.
- tma_api.py:571 reads ProjectsHub for Mini App project cards.
- tma_api.py:688 queues POST /api/projects through approval.
- tma_api.py:838 reads Leads for the Lead Pipeline.
- tma_api.py:898 queues lead status updates through approval.
- tma_api.py:929 queues follow-up task creation through approval.
- tma_api.py:1151 reads Approvals.
- tma_api.py:1200 executes or rejects approvals.
- tma_api.py:1323 reads Assets.
- tma_api.py:1365 patches Assets directly.
- tma_api.py:1508 reads active Worlds.
- tma_api.py:1529 reads Quests.
- tma_api.py:1552 reads Coins_Log.
- tma_api.py:1590 patches Quests.
- tma_api.py:1599 writes Coins_Log.
- tma_api.py:1631 reads Daily_Tasks.
- tma_api.py:1697 patches Daily_Tasks.
- tma_api.py:1714 writes Coins_Log.
- scheduler.py:422,437,462,523,542,549,553,602,615,618 use Worlds, Quests, Coins_Log.
- tools/airtable_tools.py:16 defines tool-level table fields.
- tools/airtable_tools.py:67 defines Roadmap_Tasks fields.

## Registry Coverage

Known tables counted:

- 26 tables from airtable_schema.py Tables.
- 3 TMA runtime/manual tables: ProjectsHub, Approvals, Assets.

Coverage after update:

- Registered: 29
- Missing from registry: 0
- Coverage: 100%

## Table Classification

| Table | Classification | Reason |
|---|---|---|
| Projects | VERIFIED | Defined in schema and tool/schema intelligence layers. |
| Units | UNUSED | Defined in schema/tool fields, no active runtime route found in scanned path. |
| Unit Sales & Debt Distribution | UNUSED | Defined in schema only. |
| Loans | UNUSED | Defined in schema/tool fields, no active runtime route found in scanned path. |
| Company A - Debt Management | UNUSED | Defined in schema only. |
| Weekly Cash Flow Reports | UNUSED | Defined in schema only. |
| הוצאות (Expenses) | VERIFIED | Used by tma_api finance pulse and tool/schema validation. |
| תשלומים (Payments) | VERIFIED | Used by tma_api KPIs/finance pulse and tool/schema validation. |
| אנשי קשר (Contacts) | VERIFIED | Used by tool/schema validation and CRM aliases. |
| עסקאות (Deals) | VERIFIED | Used by tma_api project dashboard and tool/schema validation. |
| Leads | VERIFIED | Used by TMA lead pipeline/card, project KPIs, lead capture/memory fields. |
| משימות ודד ליינים | VERIFIED | Used by tool/schema validation. |
| משימות (Tasks) | VERIFIED | Used by TMA follow-up approval write and tool/schema validation. |
| Profile | UNUSED | Defined in schema only. |
| למידות ותובנות | VERIFIED | Defined in schema_intelligence and learning schema. |
| Business Memory | VERIFIED | Used by tma_api activity and core lead event store. |
| Interaction Log | VERIFIED | Used by tma_api audit and lead timeline. |
| Imports | UNUSED | Defined in schema only. |
| Tenants | UNUSED | Defined in schema only; tenant is resolved by identity code, not table path in scanned files. |
| ProjectsHub | VERIFIED | Runtime TMA projects hub table. |
| Approvals | VERIFIED | Runtime TMA approval queue table. |
| Assets | STALE | Runtime uses Assets, schema comment says Assets (Personal). Needs Airtable metadata proof. |
| Worlds | VERIFIED | Runtime game dashboard and scheduler. |
| Quests | VERIFIED | Runtime game dashboard, Telegram game commands, scheduler. |
| Coins_Log | VERIFIED | Runtime game coin writes and reads. |
| Daily_Tasks | VERIFIED | Runtime TMA daily tasks. |
| Roadmap_Tasks | VERIFIED | Schema/tool fields and game/roadmap dependency. |
| Weekly_Goals | VERIFIED | Schema/tool fields. |
| Boss_Battles | VERIFIED | Schema/tool fields. |

## Missing Tables

- None after calibration.

Previously missing from Phase 1 registry:

- Units
- Unit Sales & Debt Distribution
- Loans
- Company A - Debt Management
- Weekly Cash Flow Reports
- הוצאות (Expenses)
- משימות ודד ליינים
- Profile
- למידות ותובנות
- Business Memory
- Interaction Log
- ProjectsHub
- Approvals
- Assets
- Worlds
- Quests
- Coins_Log
- Daily_Tasks
- Roadmap_Tasks
- Weekly_Goals
- Boss_Battles

## Stale Tables

- Assets: airtable_schema.py documents table name as Assets (Personal), but tma_api.py uses "Assets" for read, get, and patch. Registry follows runtime and marks this STALE until Airtable metadata confirms the production table name.

## Critical Systems

- Backend: CRITICAL, depends on Airtable, Telegram, frontend origin/env.
- Airtable: CRITICAL, source of business data and write target.
- Telegram: CRITICAL, production message entry point.
- Leads: CRITICAL, main growth pipeline table.
- Tasks: CRITICAL, follow-up write target.
- Payments: CRITICAL, finance pulse and KPI table.
- ProjectsHub: CRITICAL, Mini App project registry.
- Approvals: CRITICAL, approval gate for TMA writes.

## Data Flows

### Lead Flow

WhatsApp -> Lead Capture -> Leads -> Approval -> Followup

Status: PARTIAL

Reason: Leads and follow-up task paths exist, but runtime proof of full WhatsApp lead capture through approval to follow-up was not executed in this calibration.

### TMA Flow

Mini App -> Auth -> Airtable -> Approval -> Write -> Receipt

Status: VERIFIED

Reason: TMA auth and real Airtable read paths exist; project creation, lead status update, and follow-up creation queue approval and execute writes from the approval endpoint.

### Game Flow

Roadmap_Tasks -> Quests -> Coins_Log -> Dashboard

Status: PARTIAL

Reason: Quests, Coins_Log, Worlds, and Daily_Tasks runtime paths exist. Roadmap_Tasks is registered and schema-backed, but current runtime dashboard primarily reads Quests/Daily_Tasks/Worlds/Coins_Log.

## Registry Corrections Applied

- Replaced stale Leads field "score ציון" with runtime/schema field "score".
- Added Leads fields: tier, summary, source, channel, created_at, memory_key, tenant_id, domain.
- Added TMA runtime tables: ProjectsHub, Approvals, Assets.
- Added game tables: Worlds, Quests, Coins_Log, Daily_Tasks, Roadmap_Tasks, Weekly_Goals, Boss_Battles.
- Added memory/log tables: Business Memory, Interaction Log.
- Added finance/deal/task schema tables missing from Phase 1.
- Added owner/status/criticality/dependencies/last_audit metadata to every registry table.

## Open Calibration Risks

- Assets table name needs runtime Airtable metadata confirmation.
- Registry statuses are governance statuses, while system_registry_audit.py still reports operational statuses OK/EMPTY/MISSING/BROKEN.
- Some tables are schema-backed but not active in current runtime routes; these are marked UNUSED rather than deleted.
# ARCHIVED - historical registry report

This file is no longer an active source of truth as of 2026-06-14. Use `ROADMAP.md` for active priorities and `BOSS_CURRENT_STATE.md` for implementation reality, decisions, and known risks.
