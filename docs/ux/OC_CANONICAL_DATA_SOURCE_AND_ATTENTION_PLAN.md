# OC-A — Canonical data sources and owner attention architecture

Status: **audit + architecture + source-design only**

Audit branch base: `origin/main` at `1c3d7fd2d2f604a555a84102bb4b89fd7c0d3bd8`

This document does not implement Command Center UI, an API, a projection file, a runtime store, a schema, a feature flag, or a new status system.

## Plan Status (ops/project-md-completion audit, 16/08/2026)

This block was added by the recurring MD-completion routine (`ops/project-md-completion`), grounded in current `origin/main` evidence. It tracks the whole OC-0 → OC-F Command Center / Owner Attention program defined in §15, since §15 is the only place in the repository that enumerates every phase together; it does not change this document's original content or scope.

**Status:** IN PROGRESS. OC-0 and OC-A (planning/architecture) are complete and merged. OC-B (business signal collectors) is code-complete and merged but not wired into any runtime API or UI. OC-C, OC-D, OC-E, and OC-F have not started.

**Completed:**
- OC-0 (audit + sequence proposal) — merged, PR #652, commit `815a5cd`.
- OC-A (this document: source audit, architecture, `OwnerAttentionItem` contract) — merged, PR #654, commit `344b6c2`.
- OC-B scope (§15) — `core/owner_attention.py` (`build_owner_attention_projection`, 6 source collectors: approvals/tasks/system_health/projects/marketing/ventures, per-source `UNKNOWN`-on-failure isolation, deterministic ordering, no invented cross-domain priority score) and `test_owner_attention.py` — merged, PR #657, commits `eb53660`..`9e28be0`.

**Verified:**
- `git log origin/main` confirms all commits above are ancestors of the current `main` tip (`f8ab112`).
- GitHub Actions on merge commits `815a5cd`, `344b6c2`, and `f8ab112` (the last includes the OC-B merge, PR #657): all `completed` / `success`.
- `test_owner_attention.py`: 20/20 passed when run locally this session (`python3 -m pytest test_owner_attention.py -q`, 16/08/2026). This is local/session-level test evidence only — not a staging or production verification.
- Confirmed by grep this session (`grep -rn "owner_attention" --include="*.py" .`): no file outside `core/owner_attention.py`/`test_owner_attention.py` imports this module, and no `command-center`/`command_center` route exists in `tma_api.py`. OC-B is genuinely unwired, consistent with its own scope boundary ("do not implement UI/API/projection storage").
- **Not verified:** any staging or production behavior — there is no runtime wiring yet for this to apply to.

**Next Action:** OC-C — development intelligence generator (§15: define the registered Active Work Registry/Horizon subset, reconcile main/roadmap/verification evidence/owner gates, generate a provenance-carrying development projection). No `reports/owner_development_status.json` or equivalent generator artifact exists yet (checked this session).

**Depends On:** OC-B (satisfied — see Completed). OC-D (API evolution) additionally depends on both OC-B and OC-C per §15's sequence.

**Blocked By:** No repository evidence of a current blocker to starting OC-C.

**Owner Decision Required:**
1. **Sequencing deviation from this document's own stop condition.** §17 states: "OC-A changes exactly one planning document... owner reviews this document before OC-B or any UI/API work begins." In practice, OC-B's first commit (`eb53660`, message: "OC-B: add owner attention projector (force override authorized)") landed roughly 14 minutes after the OC-A merge, authored directly by `eli chazan <elichazan24@gmail.com>` (this repository's owner account per the session configuration). The commit message's own "force override authorized" wording reads as owner-authorized fast-tracking rather than an unauthorized process breach, but that override is not reflected anywhere in OC-0's or this document's text, so both still describe a stop condition that was in fact bypassed. This routine cannot decide whether that reading is correct or amend the stop-condition text on the owner's behalf — flagging for owner confirmation and, if confirmed, a short owner-approved amendment.
2. **PR metadata vs. actual merge state.** GitHub's PR API reports PR #652, #654, and #657 as `state: closed`, `merged: false`, while `git log origin/main` shows each PR's commits as direct ancestors of the current `main` tip via an explicit `Merge pull request #NNN` commit for each. Per `AGENTS.md`'s post-merge verification protocol, `main` ancestry is treated as authoritative here, not the PR API field — so this is not read as evidence the changes are absent from `main`. The discrepancy itself (e.g., consistent with merges pushed directly rather than via GitHub's "Merge pull request" button) is unexplained and worth an owner/maintainer look so PR tooling and dashboards reflect reality.

**Evidence:**
- PR #652 / commit `815a5cd` (OC-0), PR #654 / commit `344b6c2` (OC-A), PR #657 / commit `f8ab112` (OC-B) — `https://github.com/10026782/My-bot/pull/652`, `.../654`, `.../657`.
- `core/owner_attention.py`, `test_owner_attention.py` (added in PR #657).
- Local test run this session: `python3 -m pytest test_owner_attention.py -q` → `20 passed`.
- `grep -rn "owner_attention" --include="*.py" .` this session → no callers outside the module/test.
- GitHub Actions: workflow runs on `815a5cd`, `344b6c2`, `f8ab112` all `status=completed`, `conclusion=success`.

### Update (18/08/2026, Command Center Data Hygiene Audit)

The "Status"/"Completed"/"Next Action" text above (dated 16/08/2026) is now **stale**: it was written at commit `dd37884` (2026-08-16 04:11 UTC), several hours before OC-B was wired into a runtime API and UI later the same day. This addendum corrects the record without rewriting the block above (per this repo's append-only planning-doc convention).

- **OC-D (unified read API) and OC-E (owner-facing UI) have both landed**, not "not started": commit `41392a3` ("Implement unified read-only Command Center API", 2026-08-16 16:27 +0300, ancestor of current `main` tip `d60b377`) adds `GET /api/owner/command-center` (`tma_api.py::owner_command_center`, ~L2583-2597), which composes `core.owner_attention.build_owner_attention_projection`, `core.owner_development.generate_owner_development_status`, and `core.command_center.compose_command_center_status` — i.e. exactly the OC-B/OC-C/OC-D read models this document proposed in §11/§15.
- The frontend `OwnerControlCenter.tsx` component (the screen this document's §1.1 describes) now calls `fetchCommandCenter()` → `GET /api/owner/command-center` (`tma-frontend/src/api.ts:197-204`, `tma-frontend/src/components/OwnerControlCenter.tsx:2`), not the old mixed `/api/owner/control-center` endpoint. `fetchOwnerControlCenter()`/`owner_control_center()` still exist in the codebase but have no remaining caller in `App.tsx`.
- **Business status and recent activity remain genuinely unsupported**, consistent with this document's own recommendation: `owner_command_center()` never passes `business_status=`/`recent_activity=` to `compose_command_center_status()`, so both sections always render as the hardcoded `UnsupportedSection()` (state `UNKNOWN`) — this is by design, not a regression.
- **New finding, not previously documented here:** `core/owner_attention.py::_default_sources().health()` calls `tma_api.system_health(identity)` directly (a positional arg) on a function still wrapped by `@require_tma_auth`, which itself injects `identity=` as a keyword arg — this raises `TypeError: system_health() got multiple values for argument 'identity'` on every real invocation (reproduced standalone this session). `_run_reader()`'s exception handling converts this into a permanent `system_health` source status of `UNKNOWN`, which is why the Command Center's "מצב המערכת" section is UNKNOWN/unavailable in practice even though `/api/health` itself (the dedicated System Health screen's own read path) works correctly. Neither `test_owner_attention.py` nor `test_command_center.py` exercises `_default_sources()`, so this is untested. Not fixed here — this document records evidence only; see the Command Center Data Hygiene Audit report for the full write-up and suggested fix (call the underlying undecorated health-check logic, or add an internal non-decorated helper, instead of calling the Flask-wrapped route function directly).

## Evidence labels

- **EXISTING** — directly observed in current `main` code, tests, or a clearly identified current authority document.
- **PROPOSED** — architecture or behavior recommended for later review; not current product fact.
- **BLOCKED / UNSUPPORTED** — current contracts do not support a truthful owner-facing claim.

## Executive recommendation

Command Center should be a generated projection of canonical business and development sources. It should answer:

1. What requires attention now?
2. What owner decisions are waiting?
3. What is operating normally, unknown, or stale?
4. What meaningful development work is active, blocked, unverified, or awaiting an owner gate?
5. What changed materially, when a reliable source exists?

It must not become a manually maintained roadmap, a second approval queue, a generic task manager, a capability-map viewer, or a universal execution screen.

The recommended architecture is a **read-only projection layer** with two independently sourced sections:

```text
Canonical business sources
  -> business signal collectors
  -> deterministic Owner Attention projection

Canonical repository/planning sources
  -> development status parser
  -> deterministic Owner Development projection

Both projections
  -> one future owner-facing Command Center read API
```

The projection is allowed to aggregate and explain canonical state. It must never own the underlying business lifecycle, approval lifecycle, task lifecycle, roadmap status, or production verification state.

## 1. Current Command Center and overlapping surfaces

### 1.1 OwnerControlCenter

**EXISTING.** `tma-frontend/src/components/OwnerControlCenter.tsx::OwnerControlCenter` calls `fetchOwnerControlCenter()`. The screen currently renders:

- System Health percentage;
- Critical Systems;
- Strategic Pipeline;
- Approvals;
- Permissions;
- Business Language;
- Blockers;
- Next Actions;
- Warnings.

The screen uses a local Tailwind-style `Section`, English headings, and direct inline layout. It does not use the shared `PageHeader`, `Surface`, `StatusBadge`, or `ScreenState` primitives found under `tma-frontend/src/components/ui/`.

`tma_api.py::owner_control_center()` combines seven different kinds of data:

1. `reports/capability_map.json` through `_load_capability_map()`;
2. snapshot health through `_owner_system_health()`;
3. snapshot critical systems through `_owner_critical_systems()`;
4. live pending/recent Approvals through `_owner_approvals_snapshot()`;
5. Interaction Log receipt markers through `_owner_recent_receipts()`;
6. live Ventures counts through `_owner_strategic_pipeline()`;
7. static `_PERMISSIONS_MATRIX`, `_BUSINESS_LANGUAGE`, and hard-coded actions from `_owner_blockers_and_actions()`.

**Classification:** `KEEP BUT REWORK` as a starting aggregation boundary, not as the final source contract. Its current response is a mixed read model with inconsistent freshness and semantic ownership.

### 1.2 Projects Hub

**EXISTING.** `tma-frontend/src/App.tsx::App` loads `fetchProjects()`, then renders `GlobalKpis`, exception strings, and `ProjectCard` cards. `tma_api.py::get_projects()` is owner-only.

`_get_global_kpis()` reads overdue Tasks. `_get_project_cards()` reads `ProjectsHub`, filters visibility, deliberately skips `saas`, performs one bulk Leads read, and derives active lead counts, hot-lead counts, and a status color. The endpoint exposes useful live inputs but not a canonical cross-domain priority, project health, deadline, or next-action contract.

`get_project_dashboard()` reads Leads and Deals by resolved project domain but explicitly reads global open Tasks because the Tasks table has no domain field. Global Tasks must not be rendered as project-specific work.

**Classification:** `KEEP BUT REWORK` as compact domain context and source of supported counts; `REMOVE` its role as the owner attention system.

### 1.3 BossDigest

**EXISTING, PARTIALLY SUPPORTED.** `tma-frontend/src/components/BossDigest.tsx::loadDigestData()` derives blockers from live health flags and fetches live approvals. It contains explicit TODOs for required Tasks and daily activity delta; both arrays are currently empty. The required-action rows only toggle local React state and do not persist a canonical task completion.

**Classification:** `MOVE ELSEWHERE` conceptually into the future OC projection only after source contracts exist. Keep the current screen until a reviewed replacement exists; do not use it as evidence of a live cross-domain action or change feed.

### 1.4 Approvals

**EXISTING and canonical for approval lifecycle.** `tma_api.py::get_approvals()`, the approval POST route, `bulk_approve()`, `core/action_gateway.py`, and `core/action_contract_repository.py` form the approval execution area. `tma-frontend/src/components/Approvals.tsx` is the execution/detail surface.

The Context Librarian authority explicitly says ActionContracts are canonical for approval lifecycle, while multiple legacy/reachable mechanisms still coexist. Therefore OC may summarize pending decisions but must not create a fifth approval mechanism.

Tests including `test_approval_concurrency.py`, `test_pr0c0_tma_approval_truthfulness.py`, and the ActionGateway suites are relevant evidence for the execution boundary.

**Classification:** `KEEP` as a canonical source and destination; `KEEP BUT REWORK` in OC as a summary only.

### 1.5 Activity Feed / Business Memory

**EXISTING but partial.** `tma-frontend/src/components/ActivityFeed.tsx` calls `/api/activity` and opens a detail sheet. `tma_api.py` reads Interaction Log entries through the activity route. Approval receipts are separately searched by `[TMA receipt]` title markers in `_owner_recent_receipts()`.

The capability map marks Activity Feed and Receipts partial, and notes that receipt persistence/display is incomplete. This supports “recent recorded activity,” not a complete business-memory or daily-delta claim.

**Classification:** `KEEP` as contextual history; `KEEP BUT REWORK` in OC only as a small, explicitly incomplete recent-activity projection.

### 1.6 System Health

**EXISTING and canonical for current service/safety status.** `tma_api.py::system_health()` performs live Airtable and Telegram checks, checks Anthropic key presence without a paid call, and reads durable emergency flags through `feature_flags`. `SystemHealth.tsx` owns stop/clear controls; clear uses operation-id conflict handling.

**Classification:** `KEEP` as a compact OC indicator and `KEEP` as the full contextual safety screen. Emergency actions must not be duplicated in OC.

### 1.7 Ventures, Marketing, CRM, Finance, Tasks

**EXISTING.** These are domain workspaces with separate source contracts:

- Ventures: `tma_api.py::get_ventures`, `update_venture`, `_owner_strategic_pipeline()`, and `Ventures.tsx`;
- Marketing: `/api/marketing/demands`, `_marketing_status_payload()`, `marketing_orchestrator.compute_next_action()`, and `MarketingStatus.tsx`;
- CRM: `/api/leads`, project dashboard, `LeadPipeline.tsx`, and `LeadDetail.tsx`;
- Finance: `/api/finance/pulse` and `FinancePulse.tsx`;
- Tasks/deadlines: Tasks reads in `tma_api.py`, lead task creation, scheduler/follow-up paths, and game/check-in task paths.

**Classification:** `KEEP` as canonical contextual destinations. OC should summarize only fields whose scope, freshness, and state semantics are explicit.

## 2. Current OC section decisions

| Current section | Decision | Reason |
|---|---|---|
| System Health percentage | **REMOVE FROM PRIMARY OC; KEEP as dated capability context** | Comes from generated `reports/capability_map.json`, generated 2026-06-08. It is not live runtime health and a percentage invites false precision. |
| Critical Systems | **KEEP BUT REWORK** | Useful as a secondary capability/readiness summary only when labeled snapshot/unknown. Live service health belongs to `/api/health`. |
| Strategic Pipeline | **KEEP BUT REWORK** | Live Ventures stage counts are useful; keep compact and link to Ventures. Do not call it a cross-domain business health score. |
| Approvals | **KEEP BUT REWORK** | Pending approvals are canonical. Show count/preview; full queue and execution stay in Approvals. |
| Permissions | **MOVE ELSEWHERE** | `_PERMISSIONS_MATRIX` is static governance configuration, not owner attention. |
| Business Language | **MOVE ELSEWHERE** | `_BUSINESS_LANGUAGE` is internal vocabulary/configuration and does not answer an owner’s current-state question. |
| Blockers | **KEEP BUT REWORK** | Separate live business blockers from capability gaps and source/read failures. `_DEFAULT_BLOCKERS` are not current incidents. |
| Hard-coded Next Actions | **REMOVE FROM OWNER OC** | `_owner_blockers_and_actions()` returns roadmap-like strings (“Activate Lead Scoring”, etc.) without owner, due date, canonical task, or executable destination. |
| Warnings | **KEEP BUT REWORK** | Show source/read freshness warnings separately from business exceptions; never turn them into green/healthy state. |
| Project cards / global KPIs | **KEEP BUT REWORK** | Use supported counts with scope labels; do not imply unified priority or project-specific Tasks. |

## 3. Recommended owner information hierarchy

The proposed hierarchy is:

1. **דורש תשומת לב עכשיו** — live, canonical, owner-relevant signals only.
2. **החלטות ממתינות** — canonical pending decisions, with a bounded preview and destination.
3. **מצב העסק** — compact status by supported domain, with source/scope semantics.
4. **מצב המערכת** — compact live runtime/safety status; snapshot capability data is secondary.
5. **מצב הפיתוח** — current focus, decided next steps, verification gaps, real blockers, owner gates, and recent meaningful closures.
6. **פעילות אחרונה משמעותית** — only recorded activity with an explicit completeness/freshness caveat.

This order follows the owner’s immediate decision need, then moves from business status to system context to development context. Development is important but should not displace live business attention above the fold.

### Mobile composition

**PROPOSED.** At 390×844, the first viewport should contain the header, the attention section, and the start of pending decisions. Use one RTL vertical flow. Do not use a desktop KPI grid squeezed into mobile, and do not make every informational card clickable. Domain and development sections can be collapsed or placed below the fold; desktop may widen the same hierarchy but must not use a different information architecture.

## 4. Business attention source matrix

| Signal | Canonical source and evidence | Freshness/state semantics | Safe derivation | Owner destination | Classification |
|---|---|---|---|---|---|
| Overdue Tasks | `tma_api.py::_get_global_kpis()`; Tasks table formula; `/api/projects` | Live request read, but global scope because Tasks have no domain field | Safe as global overdue count; do not attach to a project | Future Actions/My Work or task context | **KEEP** in attention with `domain=global` |
| Due soon Tasks | No current owner-facing contract found; current KPI only computes overdue | Unsupported threshold and scope | Not safe to invent | Actions/My Work after contract | **BLOCKED / UNSUPPORTED** |
| Blocked Tasks | No single canonical blocked-task field/endpoint identified in current TMA surface | Unknown | Not safe to infer from free text or status labels | Tasks/contextual workspace | **BLOCKED / UNSUPPORTED** |
| Owner-assigned Tasks | Tasks schema/read path exists, but current `/api/projects` does not expose owner assignment as an OC signal | Scope and owner semantics require direct contract review | Not safe to aggregate from unrelated task paths | Actions/My Work | **BLOCKED / UNSUPPORTED** |
| Hot Leads | `_get_project_cards()` bulk Leads read, score >= 70, active visible domains | Live read; score quality is partial per `reports/capability_map.json` and roadmap evidence | Safe as “scored hot leads,” not as guaranteed priority | CRM/project workspace | **KEEP BUT REWORK** |
| Ultra-hot Leads | Lead tier vocabulary exists in `_BUSINESS_LANGUAGE`, but no verified OC aggregation contract for ultra-hot | Tier/scoring activation and production status not established | Not safe to present as canonical count | CRM | **BLOCKED / UNSUPPORTED** |
| Leads without follow-up | Lead fields and task creation exist, but no canonical cross-domain missing-follow-up query in current OC API | Follow-up automation is partial/flag-gated | Not safe to infer absence from a missing free-text field | Lead detail/Actions | **BLOCKED / UNSUPPORTED** |
| Stale Leads | No accepted freshness threshold or canonical last-contact rule in current OC contract | Unknown | Not safe to invent a time window | CRM | **BLOCKED / UNSUPPORTED** |
| Pending approvals | `tma_api.py::get_approvals()` and `_owner_approvals_snapshot()` read Approvals records | Live read; pending status is canonical; owner-only | Safe count and bounded preview | Approvals | **KEEP** |
| Actionable approvals | `_fmt_approval()` exposes contract linkage, legacy status, projected lifecycle, and `actionable` | Live read; actionability depends on canonical ActionContract and identity | Safe if passed through existing classification | Approvals | **KEEP BUT REWORK** |
| High-risk approvals | Approval `risk_level` field and ActionGateway policy | Live record; execution must remain risk-gated | Safe to label, not auto-rank or execute | Approvals | **KEEP** as decision metadata |
| Stale approvals | TMA approval TTL exists in `tma_api.py`, but OC does not currently expose a reviewed stale state | TTL exists; owner-facing wording/destination requires contract | Derive only after adopting the existing TTL policy explicitly | Approvals | **PROPOSED; requires contract confirmation** |
| Failed approval execution | Approval paths and tests expose failure outcomes, but no current OC failure projection is defined | Evidence is lifecycle/result-specific | Safe only from canonical execution result/receipt, not from UI disappearance | Approvals / audit detail | **PROPOSED; requires projection** |
| Marketing waiting for review | `/api/marketing/demands`, `_marketing_status_payload()`, pending creative count | Current demand/creative read; orchestrator-derived status | Safe to show pending creative count and consistency state | Marketing | **KEEP BUT REWORK** |
| Marketing blocked | Marketing orchestrator returns status/next step, but a cross-domain OC severity mapping is not defined | Domain-specific derived state | Safe as domain status with source label; not universal priority | Marketing | **KEEP BUT REWORK** |
| Marketing next action | `marketing_orchestrator.compute_next_action()` returns `next_step.action` and detail | Current domain-derived recommendation; not an executable cross-domain task | Safe only in Marketing context | Marketing | **CONTEXTUAL** |
| Active Ventures | `_owner_strategic_pipeline()` reads Ventures and counts stages | Live read, max 200 records; active excludes NO-GO/Converted | Safe as count/status context | Ventures | **KEEP BUT REWORK** |
| Venture decision due/overdue | Venture has `target_decision_date`, but no current OC due rule or stale policy | Field exists; rule and timezone/freshness are unspecified | Not safe until decision-date policy is approved | Ventures | **PROPOSED; requires contract** |
| Venture missing next action | Venture has `next_action`, but no owner-attention rule for empty values | Live field, semantics are text-based | Safe to report missing data, not necessarily an urgent blocker | Ventures | **KEEP BUT REWORK** |
| Finance exceptions | `/api/finance/pulse` and Payments/Expenses contracts exist; Finance is domain-specific | Live read with formula/production spot-check caveats | Safe as Finance context only | Finance | **CONTEXTUAL** |
| Project/domain status | ProjectsHub + bulk Leads; project status color is derived | Live records plus derived count; `saas` intentionally hidden | Safe for visible-domain counts; not unified health | Project/CRM workspace | **KEEP BUT REWORK** |
| Live system health | `/api/health::system_health()` and `SystemHealth.tsx` | Live service checks and durable emergency flags; checked date currently date-level | Safe as OK/ATTENTION/UNKNOWN based on complete check result | System Health | **KEEP** |
| Capability snapshot health | `_owner_system_health()` from `reports/capability_map.json` | Generated snapshot, dated 2026-06-08 | Safe only as dated readiness context | Governance/development | **DEMOTE** |
| Recent activity | `/api/activity`, Interaction Log, ActivityFeed | Recorded entries; completeness not established | Safe as “recent recorded activity,” not complete change log | Activity Feed | **CONTEXTUAL** |

## 5. Truthful status vocabulary

### Proposed states

- `OK` — source check succeeded, rule evaluated, and no current exception was found.
- `ATTENTION` — source check succeeded and a known business/operational condition requires owner attention.
- `BLOCKED` — a canonical source explicitly says work cannot proceed, or a known dependency is preventing the next state. This is separate from a generic warning.
- `UNKNOWN` — the system cannot truthfully determine the state, including read failure, missing required data, or unsupported semantics.
- `STALE` — the source exists and is valid but is older than its accepted freshness threshold.

`BLOCKED` is useful only when the source owns that meaning. A capability-map `next_blocker` is not automatically a current business blocker. `UNKNOWN` and `STALE` must never render as `OK`.

### Severity versus state

State answers whether the signal is known/current. Severity answers the consequence once known. Keep them separate:

- state: `OK | ATTENTION | BLOCKED | UNKNOWN | STALE`;
- severity: `info | low | medium | high | critical`;
- category: `task | lead | approval | marketing | venture | finance | project | system | development`.

No cross-domain priority score is recommended initially. Group by state/category and use deterministic tie-breakers only within a category.

## 6. Proposed OwnerAttentionItem contract

**PROPOSED.** This is a read projection contract, not a business table and not an execution contract.

### Required fields

```text
OwnerAttentionItem
  signal_key              stable semantic identity, not a record ID
  domain                  business domain or global
  category                task|lead|approval|marketing|venture|finance|project|system|development
  severity                info|low|medium|high|critical
  state                   OK|ATTENTION|BLOCKED|UNKNOWN|STALE
  title                   Hebrew-first owner-facing title
  summary                 short owner consequence
  reason                  deterministic explanation of the rule
  source_kind             api|airtable_read|runtime_check|repository|github|generated_snapshot
  source_name             human-readable canonical source name
  source_ref              safe repository/API reference; never expose internal record IDs to UI
  detected_at             ISO timestamp/date when the condition was observed
  last_checked_at         ISO timestamp/date of source check
  freshness               current|stale|unavailable|snapshot
  owner_action_required   boolean
  destination              canonical workspace/route identifier
  canonicality            canonical|derived|snapshot|unsupported
```

### Optional fields

```text
  entity_label             safe business label, never an internal ID
  due_at                   only when source owns a due date and timezone rule
  risk_level               only for approval/security signals
  evidence_summary         short provenance explanation for internal read model
  related_signal_keys      deterministic dedup/grouping links
  source_version            commit, API version, or snapshot generation marker
  stale_after_seconds      internal policy metadata
```

### Identity, lifecycle, and ordering

- `signal_key` must be deterministic and semantic, for example `tasks.overdue.global` or `approvals.pending`; it must not be an Airtable record ID.
- Multiple rows for one underlying record may be grouped only when the grouping rule is deterministic and preserves the destination.
- A signal exists for the duration of a successful source evaluation that meets its rule; it disappears only when the rule no longer matches or the source becomes unavailable/stale.
- A read failure produces `UNKNOWN` or `STALE`, never an empty green state.
- Initial ordering: `BLOCKED`/`ATTENTION` before `UNKNOWN`/`STALE`, then severity, then category-specific deterministic ordering. No global business score is proposed.
- The projection is read-only. It cannot mark a task, approve an action, change a lead, or update a roadmap.

## 7. Development intelligence audit

### 7.1 Source inventory

| Source | Current role/evidence | Authority classification |
|---|---|---|
| `ROADMAP.md` | Declared by governance as first active planning source; contains priorities, Horizon/F/N/C work, gates, and next actions. | **EXISTING primary planned-work authority**, but current freshness must be checked against main and recent merges. |
| `BOSS_CURRENT_STATE.md` | Governance says it is the second active planning/current-state source, but `AI_CONTEXT.md` explicitly calls it stale historical material for current operational claims. | **EXISTING secondary historical/context source; stale for current runtime claims unless directly reverified.** |
| `AI_CONTEXT.md` | Current briefing explicitly identifies stale documents, recent merges, verification gaps, and next priorities. | **EXISTING current briefing/triage authority**, not a replacement for source code or production evidence. |
| `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` | Defines Horizon language, active work registry, precedence rules, and maps programs. It says it is a super-layer and does not replace ROADMAP. | **EXISTING planning super-layer and sequencing authority.** |
| `BUG_AUDIT_LOG.md` | Append-only defect history and verification lifecycle; current governance lists it as active. | **EXISTING defect/evidence ledger**, not a complete active-work queue. |
| `CHANGE_CONTROL_LOG.md` | Append-only merged-change record and change evidence. | **EXISTING merge/change history**, not proof of deployment or production verification. |
| `reports/capability_map.json/.md` | Generated capability/readiness snapshot, generated 2026-06-08. | **EXISTING generated snapshot; not current runtime health.** |
| `BOSS_Marketing_Execution_Map.md` | Revenue execution layer, dated 20/06/2026, explicitly not a general master plan. | **EXISTING domain execution context; stale unless reconciled with main/current evidence.** |
| Current `main` code | Direct evidence of what is merged into the branch; required to resolve documentation drift. | **EXISTING implementation authority.** |
| PR/CI/merge evidence | Demonstrates merge/CI state and may support verification provenance, but a merged PR is not deployment proof. | **EXISTING change/verification evidence, lower than direct current production evidence.** |
| Production verification artifacts | Dated Render/staging/live evidence where available. | **EXISTING highest authority for “active in production,” scoped by date/deploy/environment.** |
| Archived docs | Historical context and prior decisions. | **EXISTING historical evidence only; never override later verified evidence or current main.** |

### 7.2 Final precedence policy

**PROPOSED, derived from `AGENTS.md`, `AI_CONTEXT.md`, Context Librarian decisions, and governance docs:**

1. Direct current production evidence for a production-state claim, scoped to environment, deploy, date, and behavior.
2. Current `main` implementation and tests for merged-code reality.
3. Current active planning authority: `ROADMAP.md` for planned work, `BOSS_UNIFIED_MASTER_PLAN.md` for Horizon/registry mapping, and `AI_CONTEXT.md` for reconciled briefing/known freshness warnings.
4. `BUG_AUDIT_LOG.md` for defect lifecycle and evidence ledger; `CHANGE_CONTROL_LOG.md` for merged change history.
5. Current PR/CI evidence for merge/check state where it is the direct evidence available.
6. Generated capability/readiness snapshots, only with generation date and source version.
7. Older audits and archived documents.

Conflict rule: newer, directly verified evidence wins. “Merged” means code is in main; it does not mean deployed or production-verified. A planning status cannot override code reality, and code presence cannot claim production activity without deployment evidence.

### 7.3 Development categories for the owner

The projection should expose only these categories:

- **עובדים עכשיו** — active registry items with explicit current phase and evidence that work is actually in progress.
- **השלב הבא** — already-decided next action from the authoritative planning source; never infer from a generic TODO.
- **דורש אימות** — merged/implemented items with explicit missing staging/production verification.
- **חסום** — real canonical blocker or owner gate, not every capability-map `next_blocker`.
- **דרושה החלטת בעלים** — only explicit owner decisions in current planning/governance sources.
- **נסגר לאחרונה** — a small bounded set of recent meaningful completions, reconciled against main and evidence.
- **Horizon** — only Horizons with current active items; no giant roadmap table.

## 8. Proposed OwnerDevelopmentStatus contract

**PROPOSED.** Generated, deterministic, provenance-carrying, and never manually edited.

```text
OwnerDevelopmentStatus
  current_focus[]
  next_actions[]
  needs_verification[]
  blocked[]
  owner_decisions[]
  recently_closed[]
  horizon_summary[]
  updated_at
  source_versions
```

Each item should include:

```text
  initiative_key          stable registry/roadmap key, not a PR number alone
  title                   owner-readable Hebrew/short business title
  horizon                 H0..H7 or null when not mapped
  state                   active|next|needs_verification|blocked|owner_decision|closed
  summary                 owner consequence
  next_step               only copied from an explicit decided source
  blocker                 only when source-owned and current
  decision_question       only for explicit owner gate
  evidence_state          merged|tested|staging_verified|production_verified|unknown
  source_refs[]           provenance paths/commit/PR references
  source_versions[]       source commit/date/generation markers
  freshness               current|stale|unknown
```

The projection must not parse every bug or PR into owner UI. It should ingest only registered active work and a bounded recent-closure window. `source_versions` must let reviewers reproduce why an item appeared.

## 9. Freshness policy

**PROPOSED policy; thresholds require owner approval before implementation.** Freshness is internal metadata even when the UI shows only current/stale/unavailable.

| Source class | Suggested threshold | Failure state |
|---|---:|---|
| Runtime/system health | 5 minutes | `UNKNOWN` if no successful check; `ATTENTION` for degraded/emergency |
| Approvals/tasks/leads/project reads | 5–15 minutes or request-local | `UNKNOWN` on read failure; source-specific `STALE` only with an accepted timestamp |
| Marketing/ventures/finance domain reads | request-local with source response date | `UNKNOWN` when contract/read fails; do not silently omit |
| Activity/business memory | 15 minutes for latest read; completeness remains separate | `STALE` or “recorded activity only” when source coverage is incomplete |
| Development planning sources | latest fetched `main` commit plus document update date | `STALE` when source predates a material merge or reconciliation event |
| Capability snapshots | explicit generation date; recommended max 24 hours for operational display | `STALE`, never live `OK` |
| GitHub merge/CI evidence | current fetched ref/PR state | `STALE` when ref has advanced; `UNKNOWN` if unavailable |
| Production verification | scoped to deploy revision and verification date | `UNKNOWN` for current production state when no matching evidence exists |

No data is not OK. A source exception must be retained as an availability/freshness state so the owner can distinguish “nothing requires attention” from “we could not check.”

## 10. Projection and storage strategy

### Option A — compute live on request

**Recommended for initial business signals.**

Pros: current data, no duplicate durable store, source failures visible immediately, no synchronization worker required.

Cons: multiple Airtable/API reads, variable latency, repeated derivation, and risk of inconsistent point-in-time reads across domains. It must use bounded parallel reads and source-level freshness metadata.

Use for: system health, approvals, overdue Tasks, visible Projects/Leads counts, Marketing demand status, Ventures counts, and other already-existing read contracts.

### Option B — generated repository artifact

**Recommended for development intelligence only, after a separately approved generator.** Candidate: `reports/owner_development_status.json`.

It must be generated in CI or a controlled command, include source versions and generation date, never be hand-edited, and never be read as runtime business state. It can summarize ROADMAP/registry/merge/verification evidence while preserving links back to sources.

Do not create this JSON in OC-A.

### Option C — materialized runtime projection/store

**Not recommended for OC-A or the first implementation.** A runtime `Owner Attention` table/store would introduce retention, replay, event ordering, reconciliation, and operational ownership. It becomes appropriate only if live computation cannot meet latency/reliability requirements and after a projection contract, backfill, idempotency, freshness, and repair design are approved.

### Recommendation

Use a single future read API that computes business signals from canonical sources and consumes a generated development artifact or a deterministic parser output. Do not create an Airtable “Owner Attention” table, manual roadmap table, or parallel status registry.

## 11. Proposed read API shape

**PROPOSED only; do not implement in OC-A.** Prefer evolving `/api/owner/control-center` rather than creating parallel aggregation endpoints, provided the existing endpoint can be versioned or migrated without breaking current consumers.

Candidate future shape:

```text
GET /api/owner/command-center

{
  "attention": {
    "items": [],
    "state": "current|partial|unknown|stale",
    "freshness": {}
  },
  "pending_decisions": {
    "items": [],
    "count": 0,
    "destination": "approvals"
  },
  "business_status": {
    "domains": [],
    "freshness": {}
  },
  "system_status": {
    "status": "OK|ATTENTION|UNKNOWN|STALE",
    "services": [],
    "emergency": {}
  },
  "development_status": {
    "current_focus": [],
    "next_actions": [],
    "needs_verification": [],
    "blocked": [],
    "owner_decisions": [],
    "recently_closed": [],
    "horizon_summary": []
  },
  "recent_activity": {
    "items": [],
    "completeness": "recorded_only|partial|unknown"
  },
  "freshness": {},
  "generated_at": "...",
  "source_versions": []
}
```

The API must be owner-authorized, read-only, bounded, and free of internal record IDs, contract IDs, raw feature-flag names, and technical tool names. Decisions should link to Approvals or a canonical domain workspace; the API must not execute them.

## 12. Avoiding duplication and migration boundary

### Reuse

- Reuse live collectors already inside `tma_api.py` where their semantics are explicit: `_get_global_kpis`, `_get_project_cards`, `_owner_approvals_snapshot`, `_owner_strategic_pipeline`, `system_health`, and Marketing status helpers.
- Reuse existing API/domain destinations and approval lifecycle rather than duplicating writes.
- Reuse the current Projects Hub and Approvals endpoint contracts during a transition.

### Do not duplicate

- Do not create another approval queue or pending-action store.
- Do not create another roadmap or active-work registry.
- Do not treat `capability_map.json` as a live system-health database.
- Do not create a new manually maintained “owner status” Airtable table.
- Do not copy domain next-action text into a cross-domain executable queue.

### Later retirement/evolution

`/api/owner/control-center` should be evolved or deprecated only after consumers are inventoried and a compatibility plan exists. `OwnerControlCenter` can become a transitional shell, but its Permissions, Business Language, hard-coded Next Actions, and raw capability snapshot sections should be removed from the owner-facing composition after the replacement read model is accepted.

## 13. What should not occupy Command Center

The owner should see the consequence, not internal implementation detail:

- permission matrices and internal enum vocabularies;
- raw capability maps and full registry inventories;
- every bug, PR, CI job, and audit receipt;
- Airtable record IDs, ActionContract IDs, tool names, table names, or feature-flag identifiers;
- full CI matrices and architecture internals;
- generated snapshot percentages without date/source context;
- hard-coded developer roadmap actions presented as owner tasks;
- empty/TODO sections presented as current state.

Example: do not show `FEATURE_X=false`; show a Hebrew business consequence only when a current source proves it, such as “שכבת המדיה עדיין לא מאומתת בפרודקשן.”

## 14. Unsupported gaps

1. No canonical cross-domain priority/attention contract exists.
2. No accepted due-soon, stale-lead, missing-follow-up, or blocked-task projection exists.
3. Lead scoring and follow-up automation are partial/flag-gated; hot-lead counts must be qualified.
4. No complete approval-failure/receipt projection is exposed to OC.
5. Marketing/venture next actions are domain text/derived outputs, not a cross-domain executable queue.
6. Venture decision-date overdue semantics are not defined for OC.
7. Finance has a domain contract but not an approved cross-domain attention rule.
8. Activity/Business Memory does not prove complete daily material change coverage.
9. Capability-map health is dated and cannot represent live runtime status.
10. Development sources contain documented staleness/drift; no deterministic generated owner-development projection exists.
11. There is no reviewed conflict resolver that joins current main, production evidence, planning docs, PR/CI state, and dated snapshots into one owner view.
12. Current navigation/App state uses separate booleans and many icon shortcuts; navigation consolidation is separate work.

## 15. Implementation sequence

### OC-A — contracts and source audit (this document)

- approve the state vocabulary, source precedence, freshness policy, and owner boundary;
- inventory source versions and explicit gaps;
- do not implement UI/API/projection storage.

### OC-B — business signal collectors and projector

- implement read-only collectors for live health, approvals, overdue Tasks, supported Projects/Leads counts, Marketing status, and Ventures counts;
- emit `UNKNOWN`/`STALE` on read failure or aged sources;
- add deterministic collector tests and no-data tests;
- preserve domain destinations and ActionContract authority.

### OC-C — development intelligence generator

- define the registered subset of Active Work Registry/Horizon entries;
- reconcile current main, roadmap, verification evidence, and owner gates;
- generate a provenance-carrying development projection, preferably repository-generated first;
- keep it out of runtime business state and never hand-edit it.

### OC-D — unified read API evolution

- decide whether `/api/owner/control-center` can evolve compatibly or needs a versioned replacement;
- expose bounded `attention`, `pending_decisions`, `business_status`, `system_status`, `development_status`, `recent_activity`, and freshness metadata;
- add owner authorization, redaction, source-error handling, and response contract tests.

### OC-E — owner-facing UI

- only after the read contract is accepted, implement the Hebrew-first mobile composition;
- reuse PageHeader, Surface, StatusBadge, ScreenState, bubble semantics, and Ventures-proven tokens;
- keep Decide/Navigate bounded and send execution to canonical workspaces.

### OC-F — production verification and polish

- verify deploy identity and source freshness in production;
- verify no data failure renders green;
- test 390×844, RTL, focus, reduced motion, loading/empty/error/stale states;
- compare the owner projection against canonical source samples and document discrepancies;
- only then remove/demote legacy OC sections or retire the old endpoint.

## 16. Explicit non-goals

- No Command Center UI implementation.
- No new API, runtime route, schema, Airtable table, projection JSON, feature flag, or store.
- No changes to frontend, backend, navigation, routing, business logic, or current roadmap statuses.
- No manual owner-status system or competing source of truth.
- No universal action/approval/task queue.
- No global priority score without an explicit owner-approved rule.
- No claim that merged code is deployed or production-active without scoped evidence.
- No exposure of internal IDs, tool names, feature flags, raw capability maps, or full developer audit detail.
- No use of archived or stale planning documents to override current main or later verified evidence.

## 17. Validation and owner stop condition

OC-A changes exactly one planning document. Before commit/PR:

- working tree contains only this document as an intended change;
- `git diff --check origin/main...HEAD` passes after commit;
- changed-file list contains no production implementation file;
- branch is based on current `origin/main`;
- owner reviews this document before OC-B or any UI/API work begins.
