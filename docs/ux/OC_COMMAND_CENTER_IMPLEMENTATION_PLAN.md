# OC-0 — Command Center audit and implementation plan

Status: **planning only**
Audit baseline: local `origin/main` at `c97d675b87cde8f2745929ed35fb16be43b8aa3d`
Scope: repository evidence only; no production UI, backend, API, schema, routing, navigation, Airtable, runtime, or business-logic changes.

## Plan Status (ops/project-md-completion audit, 16/08/2026)

This block was added by the recurring MD-completion routine (`ops/project-md-completion`), grounded in current `origin/main` evidence. It does not change this document's original content or scope.

**Status:** COMPLETE, as a planning artifact. This document's own scope — a docs-only audit and implementation-sequence proposal — is finished and merged.

**Completed:**
- Repository evidence audit (§1–§10) and OC-1..OC-4 implementation sequence proposal (§11).
- Merged to `main` via PR #652 (`codex/oc-0-command-center-audit`), merge commit `815a5cd`.

**Verified:**
- `git log origin/main` confirms `815a5cd` and `ff0427d` ("OC-0: document Command Center audit and implementation plan") are ancestors of the current `main` tip (`f8ab112`).
- GitHub Actions on merge commit `815a5cd`: `completed` / `success`.
- Not applicable: this document changes no runtime code, so there is no production/staging behavior to verify.

**Next Action:** None against this document directly. The initiative continued past this document's own proposed OC-1 into a different next step — see `docs/ux/OC_CANONICAL_DATA_SOURCE_AND_ATTENTION_PLAN.md` (OC-A) for the current phase of the same initiative and its Plan Status block for the latest state.

**Depends On:** Nothing outstanding.

**Blocked By:** Nothing.

**Owner Decision Required:** None outstanding for this document by itself. Note: this document's own stop condition ("Owner review is the stop condition. OC-1 must not begin until the owner accepts...") was not followed literally — the initiative's next step in practice was OC-A (a second audit/architecture document), not OC-1 implementation, and OC-B collector code was merged shortly after that. See the Owner Decision Required section of OC-A's Plan Status block for the evidence and the specific open question.

**Evidence:**
- PR #652 — `https://github.com/10026782/My-bot/pull/652` (GitHub PR API currently reports this PR as `state: closed`, `merged: false`, which conflicts with `815a5cd` being a `Merge pull request #652` commit present in `origin/main` ancestry; treated here as a GitHub tracking/API discrepancy, not as evidence the change is absent from `main` — see OC-A's Plan Status for the consolidated note covering PRs #652/#654/#657).

> **Evidence labels**
>
> - **EXISTING** — observed in the checked-in implementation.
> - **PROPOSED** — recommended future behavior; not present today.
> - **BLOCKED / UNSUPPORTED** — the current contract does not honestly support the concept.

## Executive decision

Command Center should become the owner-facing **read / understand / decide** surface, not a second work queue. Its first release should summarize canonical attention signals, real pending decisions, compact system/business status, and bounded drill-down links. Execution, creation, continuation of unfinished work, broad approvals, emergency controls, and domain workflows should remain in their canonical workspaces.

The current `OwnerControlCenter` is the best starting data aggregation point, but it is not yet the canonical screen: it contains a capability-map snapshot, permissions vocabulary, business-language configuration, Ventures counts, approval history, blockers, and hard-coded next actions in one owner-only view. `Projects Hub` supplies live project/lead counts and exceptions; `BossDigest` supplies a partially live health/approval summary but currently has empty action and change lists. These surfaces overlap and must be separated before OC-1.

## 1. Audit method and baseline

### Repository evidence inspected

| Area | Evidence | Observed behavior |
|---|---|---|
| Top-level TMA composition | `tma-frontend/src/App.tsx` (`App`) | Boolean view state opens Projects Hub, Approvals, Activity, Finance, Personal, System Health, Digest, Check-in, Game, Owner Control Center, Ventures, and Marketing as separate full-screen branches. |
| Frontend contracts | `tma-frontend/src/api.ts`, `tma-frontend/src/types.ts` | API functions and TypeScript response shapes are explicit for Projects, project dashboard, approvals, activity, health, owner control center, finance, marketing, Ventures, assets, leads, and game/check-in. |
| Current OC screen | `tma-frontend/src/components/OwnerControlCenter.tsx` (`OwnerControlCenter`) | Owner-only read screen with system health, critical systems, strategic pipeline, approvals, permissions, business language, blockers, next actions, warnings, and a Ventures navigation button. Copy is mostly English and the local `Section` primitive is not the shared `Surface`/`PageHeader` system. |
| Projects Hub | `tma-frontend/src/App.tsx`, `tma-frontend/src/components/GlobalKpis.tsx`, `ProjectCard.tsx`; `tma_api.py:get_projects`, `_get_project_cards`, `_get_global_kpis` | Owner-only live read of visible ProjectsHub records, active leads, hot-lead count, and overdue tasks. It is a project/lead overview, not a canonical owner attention queue. |
| Digest | `tma-frontend/src/components/BossDigest.tsx` (`deriveDigest`, `BossDigest`) | Health and pending approvals are live; blockers are derived from health flags; required actions and daily changes are explicitly TODO and currently empty. UI can toggle local action completion without a persisted task contract. |
| Decisions/approvals | `tma-frontend/src/components/Approvals.tsx`, `tma_api.py:get_approvals`, `bulk_approve`, approval POST route; `test_approval_concurrency.py`, `test_pr0c0_tma_approval_truthfulness.py` | Pending approvals are canonical Airtable-backed records with risk and action-contract safeguards. Approval execution is a real write path and has targeted concurrency/truthfulness coverage. |
| Activity/business memory | `tma-frontend/src/components/ActivityFeed.tsx`, `tma_api.py` activity route and `SCREEN_CONFIGS["activity_feed"]` | Activity is a separate read/detail surface over Interaction Log/business memory. It is contextual history, not yet a reliable cross-domain “what changed” digest. |
| System/emergency status | `tma-frontend/src/components/SystemHealth.tsx`, `tma_api.py:system_health`, emergency POST/clear routes; `feature_flags.py`; `test_feature_flags_cutover.py` | Owner-only live service checks plus durable emergency flags. Stop/clear are destructive or safety-sensitive controls and belong in System Health, not as ordinary OC cards. |
| Domain workspaces | `Ventures.tsx`, `MarketingStatus.tsx`, `LeadPipeline.tsx`, `FinancePulse.tsx`, `PersonalMode.tsx` and corresponding API routes | Domain-specific detail and execution surfaces already exist. OC should summarize them only where a stable read contract exists and should navigate to these workspaces for execution. |
| Shared visual system | `tma-frontend/src/components/ui/PageHeader.tsx`, `Surface.tsx`, `StatusBadge.tsx`, `ScreenState.tsx`, `tma-frontend/src/index.css` | Shared BOSS tokens, light/dark surfaces, action/selectable/information bubble classes, focus-visible states, reduced-motion handling, and mobile breakpoints exist. OC currently uses an older local Tailwind-style surface/header pattern. |
| Architecture guidance | `docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md`, `reports/tma-audit/BOSS_SCREEN_CONSISTENCY_ARCHITECTURE_GATE_HE.md`, `docs/ux/BOSS_UX_REFERENCE_SYNTHESIS.md` | OC is described as attention/decision-oriented; Actions/My Work is described as the place for create/execute/continue. Navigation count and final placement remain open decisions. |
| Planning signals | `BOSS_Refactor_Plan.md`, `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`, `reports/capability_map.json` | OCC + Hub + Digest are proposed for eventual consolidation; Command Center is still recorded as a future product UI loop, not a finished canonical screen. |

### Baseline caveat

The local worktree metadata could not fetch because its shared `.git/worktrees` metadata is read-only in this environment. The available local `origin/main` ref was inspected at `c97d675`. PR #650 was not present in that local ref during the audit, although the checkout contains the Ventures visual-system work used as the reference. This does not change the audit findings; it is recorded so “fresh origin/main after #650” is not represented as independently verified when it was not.

## 2. Current-state inventory and data flow

### 2.1 Projects Hub and dashboard

**EXISTING.** `App` loads `fetchProjects()` on mount and renders `GlobalKpis`, exception text, and `ProjectCard` items. `tma_api.py:get_projects` is owner-only. `_get_global_kpis` reads overdue Tasks; `_get_project_cards` reads ProjectsHub, hides `saas`, filters non-owners by `owner_ids`, then performs one bulk Leads read for visible domains. It derives:

- `overdue_tasks` from an Airtable date/status formula;
- `hot_leads_count` from active visible-domain Leads with score >= 70;
- per-project active lead count and a `hot leads` exception;
- project status color from the presence of hot leads or any leads.

These are useful attention inputs, but “status color” is a UI derivation, not a backend-owned business status. The endpoint does not expose canonical project health, a decision deadline, a cross-domain owner task, or a canonical next action.

`get_project_dashboard` resolves a project slug to ProjectsHub, filters Leads and Deals by domain, and reads global open Tasks because the Tasks table has no domain field. That global-task behavior must not be presented as project-specific work.

### 2.2 Owner Control Center

**EXISTING.** `fetchOwnerControlCenter()` calls `GET /api/owner/control-center`. `owner_control_center()` requires owner identity and combines:

1. `reports/capability_map.json` through `_load_capability_map()`;
2. `_owner_system_health()` and `_owner_critical_systems()` from that snapshot;
3. `_owner_approvals_snapshot()` from live Approvals reads;
4. `_owner_recent_receipts()` from Interaction Log records whose title contains `[TMA receipt]`;
5. `_owner_strategic_pipeline()` from a live Ventures table read;
6. `_owner_blockers_and_actions()` from capability-map blockers plus three hard-coded actions;
7. static `_PERMISSIONS_MATRIX` and `_BUSINESS_LANGUAGE` constants.

The endpoint is therefore a mixed contract: some live canonical records, one dated generated snapshot, and static governance/configuration content. It is suitable as evidence for an OC plan, but its entire response must not be treated as a single live business-state source.

### 2.3 Digest

**EXISTING, PARTLY SUPPORTED.** `BossDigest` fetches health and approvals in parallel. `deriveDigest()` converts health flags into blockers and a percentage, but contains explicit TODOs for “today’s required actions” and “what changed”; both arrays are empty. The rendered approval rows can approve/reject through the real approval API. The rendered required-actions rows only toggle local React state. Therefore Digest is not evidence for a canonical cross-domain action queue or activity delta.

### 2.4 Approvals and pending decisions

**EXISTING and canonical for the approval domain.** `GET /api/approvals` reads pending Approvals records. `POST /api/approvals/<id>` routes through the approval execution path; bulk approval is limited to low-risk, contract-backed, non-legacy rows. The response includes risk, context, contract linkage, lifecycle projection, and an `actionable` classification. Tests cover normal approve/reject, execution failure, concurrency, and legacy/non-actionable truthfulness.

OC may summarize pending count and selected decision rows. It must not copy the full approval executor into OC. The canonical approval workspace remains responsible for execution, confirmation, error/receipt handling, and the complete queue.

### 2.5 Exceptions and warnings

**EXISTING, but heterogeneous.** Projects Hub exceptions are derived strings for overdue tasks and hot leads. OCC warnings are read failures from capability-map, approval, and receipt reads. Capability-map blockers are status-derived from a generated JSON snapshot. System Health has live degraded/emergency states. These must not be merged into one undifferentiated red-alert list.

Recommended distinction:

- canonical operational exception: live source, explicit severity/state, and owner-relevant consequence;
- data-quality/read warning: freshness or source failure, shown as a warning about the screen itself;
- capability gap: planning/governance information, demoted below live business attention;
- emergency state: compact safety indicator linking to System Health.

### 2.6 Cross-domain status

**PARTIALLY SUPPORTED only.** The repository has separate live or semi-live domain sources:

- Real estate / personal assets: `GET /api/assets`, `PersonalMode`, formula-derived equity and income;
- Import / recruitment / CRM: ProjectsHub and Leads domain values, project dashboard, lead pipeline;
- SaaS/BOSS: ProjectsHub records, with `saas` currently hidden by `_get_project_cards`;
- Marketing: `/api/marketing/demands`, computed by `marketing_orchestrator.compute_next_action` over demands/creatives;
- Ventures: `/api/ventures` and `_owner_strategic_pipeline`.

There is no single cross-domain health/attention/next-action contract. OC can show compact source-labeled domain summaries, but cannot honestly claim a unified business status or rank all domains without a new aggregation contract.

### 2.7 Activity and business memory

**EXISTING contextual source; NOT YET a canonical OC digest.** `ActivityFeed` reads Interaction Log entries and opens a detail sheet. Receipts are queried separately by a title marker in OCC. Capability-map calls Activity Feed “PARTIAL” and notes receipt display/persistence gaps. The repository therefore supports “recent recorded activity” with source/freshness labeling, not a complete business-memory narrative or a reliable “what changed today” summary.

### 2.8 Emergency/system status

**EXISTING canonical safety status.** `/api/health` performs live Airtable and Telegram checks, checks Anthropic key presence without a paid call, and reads durable emergency flags through the feature-flag manager. Active emergency makes status `emergency`; service failures make it `degraded`. Stop is durable; clear requires the current operation ID and has conflict handling. OC should show only a compact status indicator and a link to System Health.

## 3. Data and contract matrix

| Candidate OC element | Source / evidence | Canonical? and freshness | Scope | Actionability | Decision |
|---|---|---|---|---|---|
| Owner attention summary | No single current endpoint. Inputs exist in Projects Hub exceptions, pending Approvals, live Health, and domain-specific data. | **BLOCKED as a unified ranking.** Individual inputs are live/derived, but the ranking contract does not exist. | Cross-domain, owner-only. | Read now; navigate to source. | **NOT SUPPORTED YET** as a ranked list. OC-1 may compose bounded sections without inventing rank. |
| Overdue tasks count | `tma_api.py:_get_global_kpis`, Tasks formula. | Canonical count from a live read, but global because Tasks lack domain field. | Cross-domain, owner-only. | Navigate to future Actions/My Work or task context. | **KEEP IN OC** as a compact exception/KPI with “global” scope label. |
| Hot leads count | `_get_project_cards`, active visible-domain Leads with score >= 70. | Live read and deterministic derivation; score quality is capability-map **PARTIAL**. | Cross-domain aggregate of visible project domains. | Navigate to CRM/project context. | **KEEP IN OC, DEMOTE** until scoring freshness/quality is established. |
| Project/domain cards | ProjectsHub + bulk Leads; `ProjectCard`. | Live project records plus derived lead count/status color. | Domain/project, owner/role filtered. | Navigate to project dashboard. | **KEEP IN OC** as read-only compact domain status; no fake health claims. |
| Pending approval count | `/api/approvals` or OCC snapshot. | Canonical live Approvals records. | Owner-only; risk/context-sensitive. | Decide only for a bounded supported approval; otherwise navigate. | **KEEP IN OC** as decision summary; **EXECUTE ELSEWHERE** by default. |
| Selected pending decision row | `OwnerControlCenter` pending payload / `Approvals.tsx`. | Canonical when `actionable` and contract-backed; stale/read failures possible. | Owner-only and action-contract scoped. | Decide or navigate to approval detail. | **KEEP IN OC** only for bounded low-risk/clearly supported decisions; full queue stays in Approvals. |
| Approval receipts | Interaction Log marker `[TMA receipt]`. | Readable but partial; capability map says persistence/display gaps. | Owner-only, audit/context. | Read/navigate; never imply complete history. | **DEMOTE** to recent evidence, with freshness and completeness caveat. |
| Capability/system health percentage | `reports/capability_map.json`, generated `2026-06-08`; `_owner_system_health`. | Snapshot-based and dated, not live runtime health. | Cross-system owner governance. | Read/planning only. | **DEMOTE**; not the primary “business is healthy” KPI. |
| Critical systems statuses | Capability map, `_owner_critical_systems`. | Snapshot-based; status may be `UNKNOWN`. | Cross-system owner governance. | Read; navigate to health/evidence. | **KEEP IN OC** only as “capability readiness” secondary section, labeled snapshot. |
| Live service health | `/api/health`, `SystemHealth`. | Live checks plus durable emergency state; checked date, not timestamp. | Cross-system, owner-only. | Navigate to System Health; emergency execution elsewhere. | **KEEP IN OC** as compact indicator. |
| Blockers | `_owner_blockers_and_actions` from capability map, with defaults. | Derived from snapshot; default blockers are hard-coded fallback. | Cross-system governance. | Read/planning; not a task queue. | **DEMOTE** or show as “known capability gaps”; never label all as current business blockers. |
| “Next actions” | `_owner_blockers_and_actions` returns three hard-coded strings; Digest actions are empty/TODO; domain next_action fields are domain-specific. | **Not canonical cross-domain.** | Supposedly cross-domain but unsupported. | No honest execution target. | **NOT SUPPORTED YET** in cross-domain form. Keep domain next actions contextual. |
| Ventures pipeline counts | `_owner_strategic_pipeline`, live Ventures table; OCC link opens Ventures. | Canonical counts by stage, capped at 200 records; domain-specific strategic data. | Cross-domain strategic owner view. | Navigate to Ventures for decisions/editing. | **KEEP IN OC** as compact status; **NAVIGATE** for execution. |
| Marketing demand status | `/api/marketing/demands`, marketing orchestrator and live demand/creative reads. | Derived from current records; pending creative count and consistency are useful but domain-specific. | Marketing, domain-permission filtered. | Navigate to Marketing for action. | **CONTEXTUAL**; summarize only if OC needs a domain snapshot. |
| Activity / recent memory | `/api/activity`, Interaction Log. | Live read of recorded entries; partial memory/receipt coverage. | Cross-domain or domain-filtered, owner-permission scoped. | Read and navigate to detail. | **CONTEXTUAL / DEMOTE** in initial OC. |
| Finance KPIs | `/api/finance/pulse`, `FinancePulse`; Payments/Expenses. | Domain-specific live read; formulas and production spot-check caveats exist. | Finance/personal owner scope. | Navigate to Finance. | **CONTEXTUAL**; one compact finance indicator at most. |
| Personal assets/equity | `/api/assets`, `PersonalMode`. | Canonical asset records plus Airtable formulas; personal scope. | Owner/personal only. | Navigate to Personal Mode. | **CONTEXTUAL**, not a general business KPI. |
| Emergency state | `/api/health` + `SystemHealth`. | Canonical safety state, live/durable. | Owner-only. | Execution belongs to System Health with explicit controls. | **KEEP IN OC** as indicator; **EXECUTE ELSEWHERE**. |
| Permissions/business language tables | Static `_PERMISSIONS_MATRIX`, `_BUSINESS_LANGUAGE`. | Configuration/reference, not changing business state. | Governance/owner. | Read only. | **MOVE OUT OF OC** to settings/governance/contextual reference. |

## 4. Candidate-area ownership decisions

| Area | Decision | Rationale and boundary |
|---|---|---|
| A. Priority / Attention | **KEEP IN OC, but bounded** | Show canonical live exceptions and pending decisions, not a fabricated cross-domain rank. A future attention aggregator requires an explicit contract with source, severity, owner, freshness, and destination. |
| B. Pending Decisions | **KEEP IN OC as summary; execute in Approvals** | Pending approval is a real canonical state. OC may expose one or a few clearly actionable decisions; the complete queue, risk detail, approve/reject, receipts, and failure recovery stay in Approvals. |
| C. Exceptions | **KEEP IN OC when canonical; DEMOTE warnings/gaps** | Overdue tasks, hot leads, live emergency/degraded state are distinct signals. Capability gaps and read failures must not look like current customer/business exceptions. |
| D. Cross-domain status | **KEEP as compact source-labeled summaries; NOT SUPPORTED as unified health** | Projects, Ventures, Marketing, Finance, Leads, and Health have separate contracts. OC may link to each and show supported counts; it must not manufacture a common status vocabulary/ranking. |
| E. Next Actions | **CONTEXTUAL; NOT SUPPORTED cross-domain** | Ventures and Marketing have domain next actions; OCC’s three actions are hard-coded capability roadmap items. Actions/My Work should own executable work once a canonical task/action queue exists. |
| F. Approvals | **KEEP summary + NAVIGATE; EXECUTE ELSEWHERE by default** | Approval execution is risk-gated and already has a dedicated screen and tests. Inline decide is acceptable only for a bounded, explicitly supported low-risk contract after the interaction contract is designed. |
| G. KPIs | **KEEP only reliable, scoped KPIs** | Overdue tasks and live record counts are usable with scope labels. Snapshot health percentage, score-derived hot leads, and finance formulas need caveats or contextual placement. |
| H. Activity / Business Memory | **CONTEXTUAL / DEMOTE** | Activity Feed is a detail/history workspace and current Digest change data is empty. Add to OC only as “recent recorded activity,” not as complete business memory. |
| I. Emergency / System status | **KEEP compact indicator; full controls contextual** | System Health owns live checks, durable flags, conflict-safe clear, and destructive stop actions. OC should never make the entire dashboard an emergency control panel. |

## 5. Recommended information hierarchy

The candidate hierarchy is validated with one change: “business status” must follow attention/decisions, and capability/system status must remain compact and clearly separate from business outcomes.

1. **מה דורש תשומת לב עכשיו** — live canonical exceptions only: overdue tasks (global), hot leads (scoped/derived), live emergency/degraded state, and data-read warnings separated by tone.
2. **החלטות ממתינות** — count plus a bounded preview of real pending approvals/decisions, with risk and destination; no giant approval queue.
3. **מצב העסק** — compact, source-labeled domain summaries: Projects/Leads, Ventures, Marketing, Finance only where current contracts support a meaningful read.
4. **מצב מערכות ויכולת** — compact live health indicator followed, if needed, by dated capability snapshot; not mixed with business KPIs.
5. **לפי תחום** — drill-down cards linking to canonical Ventures, Leads/CRM, Marketing, Finance, Personal, or Project workspaces.
6. **פעילות אחרונה שנרשמה** — optional small contextual list with freshness/completeness wording; do not promise a full daily delta.

The first viewport at 390×844 should contain the header, attention, and beginning of pending decisions. Domain summaries and activity should be below the fold or collapsible. There should be no eight-icon header like the current `App` hub.

## 6. Interaction boundary

| OC element | Interaction class | Allowed behavior | Explicitly excluded |
|---|---|---|---|
| Attention item | Read + Navigate | Explain source, severity, freshness, and open canonical detail/workspace. | Marking done, editing records, or silently creating work. |
| Pending decision preview | Read + Decide or Navigate | Show action/context/risk; allow only an explicitly bounded canonical decision or open Approvals. | Bulk approval, arbitrary action execution, or a second approval mechanism. |
| Domain status card | Read + Navigate | Open Ventures/CRM/Marketing/Finance/Project detail. | Editing a domain record from a summary card. |
| Live system indicator | Read + Navigate | Show ok/degraded/emergency and link to System Health. | Stop/clear controls in OC. |
| Capability gap | Read | Explain snapshot date/source and link to governance evidence. | Presenting roadmap items as owner tasks or current outages. |
| Recent activity | Read + Navigate | Open Activity Feed/detail sheet. | Calling it complete memory or using it as an execution queue. |

### Boundary with Actions / My Work

`Command Center` answers: “What should I understand and decide about now?”
`Actions / My Work` answers: “What can/should I create, execute, approve, or continue now?”

An item belongs in Actions/My Work when it has an executable lifecycle: owner, action type, due/priority semantics, canonical state transition, completion/receipt behavior, and a destination or contract. OC may show a summary/count or a decision preview, but it should hand execution to that surface or to a domain workspace. Until such a queue contract exists, OC must not invent one from strings such as `_owner_blockers_and_actions()`.

## 7. Reuse of the BOSS screen system

### Required reuse

**PROPOSED, based on existing primitives.** OC-1 should use:

- `PageHeader` for Hebrew title, explanatory subtitle, back/navigation action, and one bounded refresh/secondary action;
- `Surface` for section hierarchy rather than `OwnerControlCenter`’s local `Section` wrapper;
- `StatusBadge` for text + tone, never color alone;
- `ScreenState` for loading, empty, and error states;
- existing CSS variables in `index.css` for spacing, radius, border, elevation, light/dark surfaces, focus rings, and reduced motion;
- existing `boss-bubble--action`, `boss-bubble--selectable`, and `boss-bubble--information` semantics;
- Hebrew-first copy and RTL layout; preserve long labels and avoid internal IDs;
- the mobile breakpoints and safe-area/focus/motion rules already documented in the unified screen contract and exercised in Ventures.

### Bubble semantics

`Depth != Clickability` remains an explicit invariant:

- informational attention/summary surfaces use `boss-bubble--information` or non-interactive `Surface` and have no pointer affordance;
- navigation cards use `boss-bubble--selectable` only when the whole card opens a canonical destination and expose an accessible label;
- decision controls use `boss-bubble--action` only on the actual button/control, with risk/confirmation semantics;
- status indicators are badges/inline status, not buttons;
- a shadow, gradient, border, or raised surface never alone implies action.

### New primitives

No new primitive is required for OC-1. Existing primitives are sufficient for the first composition. A future `DecisionQueueRow` or `ExceptionSurface` may be justified only if the same semantics recur across OC, Approvals, and Actions/My Work; it should be an extraction after one implementation, not a parallel bespoke system. A cross-domain attention aggregator is a **data contract**, not a visual primitive, and must be designed separately.

## 8. Hebrew terminology recommendation

Use Hebrew-first product labels in the user-facing screen:

| English concept | Recommended Hebrew | Note |
|---|---|---|
| Command Center | **מרכז שליטה** | Short, understandable, and distinct from a work queue. “מרכז הבקרה” is a reasonable alternative but sounds more system/technical. |
| Needs Attention | **דורש תשומת לב עכשיו** | Use only for canonical current signals. |
| Pending Decisions | **החלטות ממתינות** | Prefer this over “אישורים” when the item is a genuine owner decision; show “אישורים” for the approval workspace. |
| Exceptions | **חריגים וחסמים** | Separate live exceptions from capability gaps in sublabels. |
| Business Status | **מצב העסק** | Use with source/domain labels. |
| System Status | **מצב המערכת** | Do not merge with business status. |
| Recent Activity | **פעילות אחרונה שנרשמה** | “שנרשמה” prevents implying complete business memory. |
| Navigate to workspace | **פתיחה במרחב העבודה** | Prefer destination-specific labels where possible. |

Do not expose `record_id`, `contract_id`, `ProjectsHub`, `capability_map`, internal table names, or technical flags in the user UI.

## 9. Proposed mobile composition (390 × 844)

**PROPOSED.** One vertical RTL flow, not a squeezed desktop grid:

1. compact `PageHeader`: “מרכז שליטה”, one-line purpose, refresh/status action;
2. first `Surface` for “דורש תשומת לב עכשיו,” with at most three priority rows and an explicit empty state;
3. second `Surface` for “החלטות ממתינות,” count + one/two preview rows + “פתיחת כל ההחלטות” navigation;
4. compact “מצב העסק” summary strip with horizontally scrollable or stacked domain rows, never four tiny KPI tiles;
5. compact system-status row and optional capability snapshot metadata;
6. collapsible/low-priority “לפי תחום” links;
7. recent recorded activity last, collapsed by default if it would create excessive vertical nesting.

Rules:

- no horizontal page overflow;
- no desktop grid forced into 390px;
- no full-width clickable surface when only one action is clickable;
- minimum comfortable touch target and visible focus state;
- long Hebrew labels wrap; they are not ellipsized when meaning is lost;
- one information architecture across desktop and mobile; desktop may widen domain rows or place two read-only sections side by side after the mobile hierarchy is proven.

## 10. Unsupported capabilities and gaps

1. **No canonical cross-domain attention/priority contract.** Current inputs are separate and differently fresh.
2. **No canonical cross-domain next-action queue.** OCC actions are hard-coded capability roadmap strings; Digest actions are TODO/empty.
3. **No complete “what changed today” contract.** Activity exists, but Digest’s daily delta is not wired and receipt persistence/display is partial.
4. **Capability-map health is a dated snapshot.** It cannot be the sole live system-health signal.
5. **Project/task scope mismatch.** Project dashboard explicitly returns global open Tasks because Tasks have no domain field.
6. **Hot-lead quality is not fully canonical.** The count is deterministic, but the capability map marks scoring as partial and follow-up automation as not active.
7. **SaaS visibility is intentionally filtered.** `_get_project_cards()` skips `domain == "saas"`; OC must not claim a complete cross-domain SaaS view from Projects Hub.
8. **Approval receipt completeness is not established.** OCC reads a title marker from Interaction Log; this is useful evidence, not a complete audit ledger presentation.
9. **Navigation architecture is not canonical.** `App.tsx` uses many independent booleans and icon shortcuts; OC-0 should not rewrite routing/navigation, but OC-1 needs an owner-approved destination contract.
10. **Owner-only scope is current.** The endpoint and current screen reject non-owners; a role-sensitive OC requires a separate contract and is out of scope for OC-1.

## 11. Implementation sequence

### OC-1 — shell and truthful read model

1. Owner approves the information hierarchy and Hebrew wording.
2. Define a read-only OC view model with source, freshness, scope, severity, destination, and canonicality fields.
3. Compose the screen with `PageHeader`, `Surface`, `StatusBadge`, `ScreenState`, and explicit bubble semantics.
4. Include only live health/emergency indicator, overdue task count, scoped hot-lead count, and pending approval summary; label derived/snapshot values.
5. Add focused contract tests for missing/empty/stale sources and owner authorization.

### OC-2 — priority and decision surfaces

1. Add bounded attention rows from existing canonical sources.
2. Add pending decision preview with a single explicit boundary: navigate to Approvals, or implement a reviewed low-risk decide action using the existing approval contract.
3. Do not add bulk approval or a second mutation path.
4. Verify empty, degraded, partial-read, and stale-source states.

### OC-3 — domain/status composition

1. Add compact source-labeled summaries for Ventures, Projects/CRM, Marketing, and optionally Finance after owner confirms value/freshness.
2. Link every summary to its canonical workspace.
3. Do not introduce a unified cross-domain health score or cross-domain next-action ranking without a separately approved backend/read-model contract.

### OC-4 — activity and polish

1. Add “פעילות אחרונה שנרשמה” only if the completeness/freshness contract is explicit.
2. Reuse Activity Feed detail rather than duplicating business-memory logic.
3. Complete 390×844 and desktop responsive QA, keyboard/focus/reduced-motion checks, and Hebrew copy review.
4. Reassess whether a repeated `DecisionQueueRow`/`ExceptionSurface` warrants extraction.

### Separate future work, not OC-1

- Actions / My Work canonical queue and lifecycle;
- cross-domain attention/priority aggregation contract;
- complete receipt/audit projection;
- role-sensitive OC variants;
- navigation/AppShell consolidation;
- any new API/schema/Airtable fields required by the above.

## 12. Explicit non-goals

- Do not implement OC UI in OC-0.
- Do not modify production frontend, backend, API, schema, Airtable, runtime, routing, navigation, feature flags, or business logic.
- Do not create a second task/action/approval system.
- Do not convert capability-map roadmap items into business tasks.
- Do not invent cross-domain “next action,” health, priority, or activity semantics.
- Do not perform approvals, emergency stop/clear, record edits, project creation, or domain workflow execution inside the audit deliverable.
- Do not expose internal IDs or technical source names in proposed user-facing copy.

## 13. Validation plan for this OC-0 change

The implementation change for OC-0 is this planning document only. Before commit/PR:

- `git status --short` must show only `docs/ux/OC_COMMAND_CENTER_IMPLEMENTATION_PLAN.md` as an intended change;
- `git diff --check` must pass;
- `git diff --name-only` must contain no production implementation files;
- no frontend build is required because no implementation file changes.

Owner review is the stop condition. OC-1 must not begin until the owner accepts the ownership boundary, unsupported-gap list, and hierarchy above.
