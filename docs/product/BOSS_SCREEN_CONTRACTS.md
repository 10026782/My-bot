# BOSS Admin App — Screen Contracts

**Status:** Draft implementation-ready spec artifact.
**Date:** 31/08/2026.
**Companions:** `docs/product/BOSS_ADMIN_APP_IMPLEMENTATION_SPEC.md` (narrative spec, entity drilldowns, cross-screen nav, search, AI assistant integration, build order), `docs/product/BOSS_PERMISSION_AND_ACTION_MATRIX.md` (role reality, tool registry, API gap classification — read that document's §2 before trusting any role claim below).
**Also read:** `docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md` (WIP UX/design gate, PR #600) before building any screen's UI — it defines the shared component vocabulary (`AppShell`, `PageHeader`, `Card`, `StatusBadge`, `EmptyState`/`LoadingState`/`ErrorState`, `ActionBar`, `ConfirmationPreview`, `Receipt`, etc.) and the canonical action flow (`Initiate → Preview/Validation → Execute/Approve → Result → Receipt`) every screen below should be built against. This document supplies the *content* of each screen (fields, buttons, API calls, states, forms); that document supplies the *shared visual/interaction language* those contents should render through — don't invent a one-off header/card/state pattern per screen when that gate already names the component to reuse.
**How to read this document:** every action row follows the fixed chain **button → API/tool → authorization → approval? → canonical writer → result → UI state**. Where a described action does not exist in code today, it is explicitly labeled "(recommended addition — see Gap Matrix)" rather than presented as built. Field names are given verbatim as they appear in Airtable/code (Hebrew where that's the live field name), not translated, so an implementer can grep them directly.

---

## Command Center

### Purpose
The owner's single "what needs my attention right now" cockpit. Reconciles pending approvals, task load, system health, project/marketing/venture state, and longer-horizon development status into one attention feed — distinguishing operational items needing action now (`attention`) from a roadmap-shaped view of what's being built (`development_status`).

### User roles
- **View:** owner only. `GET /api/owner/command-center` hard-403s any non-owner identity. No Manager or Partner variant exists in code — a scoped view for those roles is a **POLICY DECISION REQUIRED** gap (see Permission Matrix §4), not a coding task.
- **Execute:** N/A — this screen has zero write actions.

### Data sources
- `GET /api/owner/command-center` (`tma_api.py:2735`) → `core/command_center.py::compose_command_center_status()`, composing:
  - `core/owner_attention.py::build_owner_attention_projection()` — independent `SourceReader`s for approvals, tasks, system_health, projects, marketing, ventures, each individually status-tagged.
  - `core/owner_development.py::generate_owner_development_status()` — reads a roadmap/registry text source.
- Cross-links to `GET /api/health` (System Health drill-in) and, via the existing home screen, `GET /api/owner/my-work`.

### KPIs
| KPI | Formula / source |
|---|---|
| `overall_state` | Rollup of `OK / ATTENTION / PARTIAL / UNKNOWN` across all sub-sections |
| System-health percent | `working_count / (working_count + partial_count + broken_count)` — exists in the sibling `/api/owner/control-center` payload, **not currently pulled into this screen** (see below) |
| Attention item count by severity | Count of `attention.items` grouped by `INFO / WARNING / CRITICAL` |
| Pending decisions count | `len(pending_decisions)` |

### Main views

**Attention section** — cards from `attention.items`, each `{signal_key, category, severity, state, title, summary, reason, destination, owner_action_required, freshness}`. No filter control; client shows first 3, expandable to full list.

**Pending Decisions section** — same card shape, rendered only when non-empty.

**Development Status section** — bucketed lists: `current_focus / next_actions / needs_verification / blocked / owner_decisions / recently_closed`, each item carrying `horizon, work_state, current_stage, evidence_state, next_step, needs_verification, blocked, owner_decision_required, freshness, last_reconciled`. "Open all / Close all" bulk toggle.

**System status strip** — compact badge (`state`, `freshness`) + one button to the health screen.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| Attention card "פתיחה" (open) | none — client-side navigation to `destination` (approvals/system_health/marketing/ventures) | owner | n/a | n/a | routes to target screen | navigates |
| "פתיחת בריאות המערכת" | none — navigates to Settings/System Health, which then calls `GET /api/health` | owner | n/a | n/a | — | navigates |
| Open all / Close all | client-only state toggle | owner | n/a | n/a | — | expands/collapses |

**Recommended addition (BACKEND EXISTS BUT UNWIRED):** a Doctor diagnostics tile calling `boss_doctor.run_doctor()` — already pure, side-effect-free, and used by the Telegram `/boss_doctor` command; needs only a new `GET /api/owner/doctor` route.

### States
- **Loading:** spinner, no partial render.
- **Success:** all sections render per their own `freshness` value.
- **Partial:** any section whose `freshness ≠ CURRENT` renders an inline "Unavailable" message in that section only — the rest of the screen still renders. `business_status` and `recent_activity` in the raw API response are **structurally always this placeholder today** (`reason="unsupported_canonical_source"`) — no caller populates them; do not build a UI that assumes they ever carry data without also wiring a real source.
- **Failure:** whole-fetch error banner with retry.
- **Unauthorized:** distinct "owner-only" message, not a blank screen or a generic error.
- **Stale:** section-level `STALE` badge, still rendered, visually flagged (not hidden).
- **Empty:** `attention.items` empty → an explicit "nothing needs attention" state, distinct from loading/error.

### Forms
None — this is a read + navigate screen by design.

---

## Ventures

### Purpose
Pre-deal, pre-lead strategic opportunity evaluation. Tracks a business idea/opportunity from `Research` through `Due Diligence` → `Smoke Test` → `GO`/`NO-GO`/`Converted`, before it becomes a Lead or a Deal. **This is not a view onto the six business domains** — it is a distinct Airtable-tracked entity (`Ventures` table) that happens to carry a `Domain` tag as one attribute.

### User roles
- **View and every write action:** owner only, hard-403 for every route (`GET/POST/PATCH /api/ventures*`). No Partner or Manager path exists at all.

### Data sources
`Airtable Ventures table` (`VentureFields`) via `GET /api/ventures[?stage=]`, `GET /api/ventures/<id>`, `POST /api/ventures`, `PATCH /api/ventures/<id>`.

### KPIs
| KPI | Formula |
|---|---|
| Count in current stage filter | `count(ventures where stage matches filter)` |
| Total potential | `Σ estimated_potential` across the filtered set |
| "Has next step" count | `count(ventures where next_action is non-empty)` |

### Main views

**List (stage-grouped)** — sections per `VentureStage`: `Research, Supplier/Source Contact, Due Diligence, Legal/Tax Review, Smoke Test, GO, NO-GO, Converted`, plus an "uncategorized" bucket for any unrecognized stage value.

**Filter:** stage chips including "all stages" — server round-trip on selection (`?stage=`). **No domain filter exists server-side** — API MISSING, would need a new query param.

**Card columns:** name, stage badge, `next_action` (if set), `domain` (raw text, no color/tone), conviction badge (`LOW/MEDIUM/HIGH`), `estimated_potential` (₪, K/M-abbreviated), `target_decision_date`, open button.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| "פתיחת הזדמנות" (open) | `GET /api/ventures/<id>` | owner | n/a (read) | — | venture detail | loading→success/error |
| "+" New Venture | `POST /api/ventures` | owner | yes — but Owner auto-claims+executes synchronously in the same request (`_queue_or_owner_execute`) | `core/action_gateway.py::propose_action` → Airtable `Ventures` create | new record | success toast → navigate to detail, or inline error |
| Save (stage/conviction/next_action/notes) | `PATCH /api/ventures/<id>` | owner | same auto-execute pattern | ActionGateway → Airtable `Ventures` update | updated fields | save confirmation |

### States
Loading / Success / Empty ("no ventures at this stage") / Error / Unauthorized (non-owner → hide screen, distinct 403 message) — no "stale" concept (direct live Airtable reads, no staleness projection here).

### Forms

**Create Venture**
| Field | Label | Canonical field | Type | Required | Validation | Default | Options | Permission |
|---|---|---|---|---|---|---|---|---|
| Name | שם ההזדמנות | `VentureFields.NAME` ("Venture Name") | text | **yes** | non-empty | — | — | owner |
| Domain | תחום | `VentureFields.DOMAIN` ("Domain") | select | no | must be one of `VentureDomain` — **only 5 values exist: Real Estate, Import, SaaS, Recruitment, General; no Media, no Finance** — see Gap Matrix | empty | Real Estate / Import / SaaS / Recruitment / General | owner |

Stage defaults to `Research` server-side if omitted; not shown on the create form.

**Edit Venture** (only these 4 fields have a UI path today — the backend PATCH accepts more, see Gap Matrix)
| Field | Label | Canonical field | Type | Required | Validation | Default | Options | Permission |
|---|---|---|---|---|---|---|---|---|
| Stage | שלב | `STAGE` | select (lifecycle rail) | implicit (always has a value) | one of 8 `VentureStage` values | current value | 8 stages | owner |
| Conviction | רמת ביטחון | `CONVICTION` | button-select | no | `LOW/MEDIUM/HIGH` | current value | 3 | owner |
| Next Action | צעד הבא | `NEXT_ACTION` | textarea | no | free text | current value | — | owner |
| Notes | הערות | `NOTES` | textarea | no | free text | current value | — | owner |

Backend-editable but **no UI form field today** (gap): `name`, `domain`, `estimated_potential`, `target_decision_date`, `decision_log`, `linked_contacts`, `owner`.

---

## Pipeline

### Purpose
Lead lifecycle management — from inbound capture through qualification, follow-up, task creation, and either conversion or terminal closure. The operational sales/ops working surface.

### User roles
- **View:** owner, manager, **partner (own domain only**, via `can_access_domain`).
- **Write** (status/patch/outcome/task/followup): **owner, manager only** — partner is read-only even inside their own domain.

### Data sources
Airtable `Leads` table (`LeadFields`) via `GET /api/leads[?domain=][?view=]`, `GET/PATCH /api/leads/<id>`, `PATCH .../status`, `POST .../outcome`, `POST .../task`; `Interaction Log` (timeline); optionally `Lead Events` (BUG-104 reasoning projection, off by default, byte-compatible when off).

### KPIs
| KPI | Formula |
|---|---|
| Count in view | `count(leads matching active/monitoring/all filter)` |
| Temperature distribution (recommended, not currently aggregated server-side) | Bucket leads by `score_display.py`'s 5-tier scale: 🧊 COLD 0–20, 🌤️ WARM 21–40, 🔥 HOT 41–60, 🔥🔥 VERY HOT 61–80, 🚀 BOILING 81–100 |

### Main views

**List** — `LeadCard` row: `name`, status badge (`hot`=red, `active`=green, `new`=blue, `waiting_call`=yellow, else gray), `score` (color-coded ≥70 red / ≥40 yellow / else gray).

**Filters:** backend supports `?view=active|monitoring|all` and `?domain=`/`?project_slug=` — **none are wired to a UI control today** (the list always calls the `active` view). Recommended additions: view switcher, domain filter (for Owner/Manager cross-domain use), score/temperature filter, status filter, name/phone search.

**Detail** — 5-stage workflow bar, client-derived (not a server field) from status/outcome/next_step: `new → followup → qualified → task → closed`. Fields shown: `name, phone, domain, status, score(+color), source, summary, next_step (mapped label), created_at, timeline, tier (read-only badge), outcome, next_followup, owner`.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| "פולואפ" (+ date picker) | `POST /api/leads/<id>/outcome {outcome:"needs_followup"}` [+ optional `PATCH next_followup`] | owner, manager | yes — Owner auto-executes, Manager queues (202) | `_queue_or_owner_execute` → `Leads.Business Outcome` + status auto-derived `waiting_response` | updated lead | optimistic (owner) / pending banner (manager) |
| "סמן כמתאים" | `PATCH /api/leads/<id> {status:"high_confidence"}` | owner, manager | same pattern | `Leads.status` | updated | optimistic/pending |
| "פגישה נקבעה" | `POST .../outcome {outcome:"meeting_scheduled"}` | owner, manager | same pattern | status auto-derived `active` | updated | optimistic/pending |
| "צור משימה" (inline form) | `POST /api/leads/<id>/task` | owner, manager | yes, Owner auto-executes | `Tasks` create (`NAME/STATUS=ממתין/DUE_DATE/DESCRIPTION/DOMAIN/OWNER/LEAD_LINK`) | new task | confirmation |
| Terminal outcome buttons (`converted/not_relevant/lost/duplicate/archived`) | `POST .../outcome {outcome}` | owner, manager | same pattern | status auto-derived per `_OUTCOME_STATUS_MAP` | lead closed | sale actions hidden after |
| "פתח מחדש" (reopen) | `POST .../outcome {outcome:"open"}` + `PATCH {status:"active"}` | **owner only** | same pattern | status reset | reactivated | — |
| Score override | `PATCH /api/leads/<id> {score}` | **owner only** | same pattern | `Leads.Score` | updated | — |
| Bottom-bar free note | `POST /api/followup {lead_id, note}` | owner, manager | yes — **always queues, even for Owner** (inconsistent with every other lead-write button above) | raw `Tasks` row (title/desc/due=tomorrow/status=ממתין) — **no domain/owner/lead-link copy**, unlike the `/task` endpoint | new bare task | pending toast even for owner |
| "AI" toggle → ask | `POST /api/ai/ask {context:"lead_card", context_id, question}` | authenticated (no extra role gate found) | n/a — single-turn LLM Q&A, not the tool-use loop, no write | — | text answer | inline answer bubble |

**Dead/inconsistent surfaces worth flagging before extending this screen:**
- `PATCH /api/leads/<id>/status` is a fully wired backend route with **zero frontend callers** — resurrect it deliberately (e.g. for a quick-status dropdown) rather than leaving two divergent status-write paths (`/status` always queues; `PATCH /api/leads/<id>` auto-executes for Owner) both live.
- `/convert` (Lead → Contact) is Telegram-command-only (`LEAD_AUTO_CONVERT` flag, default off) and **currently broken for most real leads** — it passes a `notes` string to `crm_add_contact`, but `Contacts` has no `Notes` field, so the write is rejected with a generic, unhelpful error. This is separate from PR1153's fixed reasoning adapter; fix the field mismatch before building a Pipeline "Convert to Contact" button.

### States
Loading / Success / Empty ("no leads in view") / Error (502 `data_unavailable` on Airtable failure) / Unauthorized (distinct message for a partner attempting a write vs. a role with no pipeline access at all) — no "stale" concept.

### Forms

**Create Task (inline, from Lead detail)**
| Field | Label | Canonical field | Type | Required | Validation | Default | Permission |
|---|---|---|---|---|---|---|---|
| Title | כותרת | `TaskFields.NAME` | text | **yes** | non-empty | — | owner, manager |
| Due date | תאריך יעד | `DUE_DATE` | date | no | valid date | tomorrow | owner, manager |
| Notes | הערות | `DESCRIPTION` | textarea | no | free text | — | owner, manager |

**Follow-up note (bottom bar)**
| Field | Label | Canonical field | Type | Required | Default | Permission |
|---|---|---|---|---|---|---|
| Note | (placeholder freetext) | `Tasks.תיאור` via `/api/followup` | text | no | `"מעקב"` server-side if blank | owner, manager |

**Outcome selection** — button-select, not a text form: canonical `LeadFields.OUTCOME` via `LeadOutcome` enum (8 canonical keys); terminal vs. non-terminal split enforced client-side; permission owner/manager (reopen is owner-only).

**Score override (owner only)**
| Field | Label | Canonical field | Type | Required | Validation | Default | Permission |
|---|---|---|---|---|---|---|---|
| Score | ציון | `LeadFields.SCORE` | number | no | 0–100 | current score | **owner only** |

**Not built anywhere — flag before promising it:** Deal creation/edit has no TMA form at all today; the backend writer is now statically wired as `crm_create_deal` by PR1153, but has no production canary.

---

## Operations

### Purpose
The owner/manager's day-to-day execution surface: tasks owed, the activity/audit trail, and (recommended addition) system operational health — "what do I need to do, and is the machine running."

### User roles
- **My Work:** owner only.
- **Activity:** owner, manager.
- **Doctor/scheduler tile (recommended addition):** no code exists to gate; recommend owner-only to match every other diagnostics surface in this app.

### Data sources
`Tasks` table (My Work); `Business Memory` + a `[TMA receipt]`-filtered slice of `Interaction Log` (Activity); `boss_doctor.run_doctor()` (recommended, currently Telegram-command-only); `event_bus.PendingActionsStore` (recommended, currently no read API at all).

### KPIs
| KPI | Formula |
|---|---|
| Immediate task count | tasks overdue or due today, non-Done, owned by (or unassigned and defaulting to) the caller |
| Upcoming task count | tasks due in the future or with no due date |
| Activity entries in period | `len(entries)` for the current fetch (default `limit=50`, capped 100) |

### Main views

**My Work** — two summary tiles (immediate=red, upcoming=blue counts); two `TaskCard` lists. Card fields: overdue badge (if overdue), domain badge (if present), title (bold), description (2-line clamp), due date with icon. **No filters, no sort, and — today — no action buttons on any card at all** (no complete/edit/reassign).

**Activity** — `ActivityRow`: channel icon (whatsapp💬/telegram✈️/email📧/voice🎙️/tma📱, default 💼), title (or summary truncated to 60 chars), summary subtitle (only if both present, 80-char), domain pill, relative timestamp, sentiment color/text (positive=green/negative=red/neutral=gray, else default gray). Click → detail bottom sheet (full timestamp, full summary, sentiment as "business impact," domain tag pills). `?domain=` is server-supported (code comment: "reserved for future") but not wired to any UI control.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| (none today — 100% read + expand-detail) | — | — | — | — | — | — |

**Recommended additions, all real gaps (see Permission Matrix, no code exists for any of these):**
- Task complete/reassign/edit buttons on My Work — needs a new `PATCH`-task-status endpoint; none exists (only the unrelated gamification `Roadmap_Tasks` "done" PATCH exists today, a different table).
- Manager-visible task list — `my-work` is hard owner-gated with no Manager equivalent, despite Manager being able to *create* tasks via the Pipeline screen.
- Scheduler/background-job status tile — wire `boss_doctor.run_doctor()`.
- Pending-actions-across-subsystems view — `event_bus.PendingActionsStore` has zero TMA read surface; do not confuse with `GET /api/approvals`, which is a different, non-authoritative store.
- Unified calendar/email/WhatsApp interaction timeline — `interaction_engine.py` writes real data but `INTERACTION_INTELLIGENCE` defaults off (documented as "(Future)," not rollout-ready) and has no dedicated read endpoint even when on.

### States
Loading / Success / Empty ("no tasks" / "no activity") / Error / Unauthorized (My Work: owner-only 403; Activity: owner+manager 403 — keep the existing pattern of distinguishing 401 vs 403 with a specific message rather than a generic failure) — no "stale" concept on these direct-read endpoints.

### Forms
None exist today. If task-create is exposed directly on Operations (not only via Lead detail), reuse Pipeline's Create Task field shape verbatim (`TaskFields.NAME/DUE_DATE/DESCRIPTION`) rather than inventing a second shape.

---

## Finance

### Purpose
Current-month business P&L snapshot, plus — folded in from the pre-existing "Personal Mode" screen rather than re-invented — a personal/real-estate asset balance sheet. The owner's money view.

### User roles
- **Finance Pulse:** owner only.
- **Assets:** **read** — owner, or partner if `"personal" ∈ identity.allowed_domains`; **write (PATCH)** — owner only (stricter than the read gate).

### Data sources
`Payments` table + `Expenses` table (Finance Pulse); `Assets` table (balance sheet).

### KPIs (all current-month window unless noted — exact formulas from the live aggregation code)
| KPI | Formula |
|---|---|
| `income.amount` | `Σ Payments.amount` where `status="received"` **and** `date ≥ month_start`. Received payments dated before this month are silently excluded from every aggregate, not just income. |
| `pending.amount` | `Σ amount` where `status ∉ {received, overdue, cancelled}` and (`date` empty or `date ≥ today`) |
| `overdue.amount` | `Σ amount` where `status="overdue"` (any date) **plus** non-received/cancelled rows with `date < today` |
| `expenses.amount` | `Σ Expenses.amount` where `date ≥ month_start` |
| `net` | `income.amount − expenses.amount` — a pure this-month P&L, **not** a running balance |
| Assets: `total_value` / `total_debt` / `total_equity` / `my_equity` / `monthly_income` | Sums of `Current Value` / `Mortgage Balance` / (`Current Value − Mortgage Balance`, an Airtable formula field) / (`Equity × Ownership%`) / gross `Monthly Income` (no expense/tax/partner deductions) |

### Main views

**Finance Pulse** — 2×2 KPI grid: income (green) / pending (yellow) / overdue (red if >0, else gray) / expenses (gray), each with amount + record count. Full-width net card, sign-colored. Recent-payments list (top 5 by date desc): `ref`, `date`, `amount` — **no status badge, not clickable, no detail/edit link.**

**Filters supported server-side but not wired to any UI control:** `?view=active|overdue|all`, `?domain=` — recommended addition, since the backend work is already done.

**Assets (folded-in Personal Mode)** — portfolio header: 3-tile row (total value / total debt / total equity) + 2-tile row (my equity / monthly income). Asset cards: type icon, name, current value, status badge, ownership% (if <100%), equity, my equity (if <100%), monthly income (if >0). Detail: balance-sheet 2×2, gross-income card with an explicit "gross only" disclaimer, fixed bottom edit bar.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| Asset edit save (status chip / value / mortgage / income inputs) | `PATCH /api/assets/<id>` | **owner only** | yes — Owner auto-executes | `_queue_or_owner_execute` → Assets table PATCH | updated record; formula fields (`Equity`/`My Equity`) re-fetched | toast + refetch |
| Everything else on Finance | — | — | — | — | — | **read-only today** — no create-payment, no mark-paid, no create-deal button anywhere, even though `crm_mark_payment_paid` is a real wired agent tool (see Gap Matrix) |

### States
Loading / Success / Empty (no assets / no recent payments) / Error (502 `data_unavailable`) / Unauthorized (distinct: "owner only" for Finance Pulse vs. "personal domain required" for Assets) — no "stale" concept.

### Forms

**Asset edit**
| Field | Label | Canonical field | Type | Required | Validation | Default | Permission |
|---|---|---|---|---|---|---|---|
| Current Value | שווי נוכחי | `"Current Value"` | number | no (blank = skip) | numeric | current value | owner |
| Mortgage Balance | יתרת משכנתא | `"Mortgage Balance"` | number | no | numeric | current value | owner |
| Monthly Income | הכנסה גולמית | `"Monthly Income"` | number | no | numeric | current value | owner |
| Status | — | `"Status"` | single-select (chip) | no | one of מושכר/פנוי/בבנייה | current value | owner |

`Ownership %` is backend-editable but **has no UI input anywhere in the current Asset Detail form** — gap.

**Not built anywhere:** Payment / Deal / Expense creation forms — the TMA surfaces are new build. `commercial_crm.py` Deal/Payment writers are statically wired by PR1153 but lack a production canary; `Expenses` has no writer at all.

---

## Approvals

### Purpose
The owner's single queue for every pending high-risk/irreversible action across the whole system (Airtable writes, Gmail sends, Calendar events, Lead/Task/Venture/Asset writes, payment-paid marks) — approve or reject before anything executes.

### User roles
Owner only, full stop. No Manager or Partner visibility into the queue at all, even for actions **they themselves** requested (a real, decision-worthy gap — see Permission Matrix §4).

### Data sources
Airtable `Approvals` table — an explicitly **non-authoritative display projection** of the canonical `ActionContract` (`core/action_gateway.py`). It is never itself sufficient to authorize an execution; the API re-derives everything from the real contract on every action.

### KPIs
| KPI | Formula |
|---|---|
| Pending count | `count(Approvals where סטטוס='ממתין')` |
| Bulk-eligible count | `count(pending where risk_level='נמוך' and actionable=true)` — drives the bulk-approve button's shown number |

### Main views

Flat list, no tabs/filters, always the pending set only. Card columns: `action` (bold), risk badge (`גבוה`=red / `בינוני`=yellow / `נמוך`=green), `requested_by`, `requested_at` (relative time), `context_type` icon. Header: pending count, bulk button ("אשר הכל (N)") shown only when bulk-eligible count > 0.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| "✅ אשר" (approve) | `POST /api/approvals/<id> {action:"approve"}` | owner | self (this **is** the approval action) — re-checks `FEATURE_ACTION_CONTRACT_PERSISTENCE` + `FEATURE_ATOMIC_CLAIMS` live (else **HTTP 503**, no fallback) + 24h TTL (auto-rejects if expired) | `core/action_gateway.py::_execute_contract()` → `dispatch_tool()` on the originally-proposed tool | `{contract_status: completed\|executed}` | optimistic removal + toast |
| "❌ דחה" (reject) | `POST /api/approvals/<id> {action:"reject", note}` | owner | no flag/TTL re-check on the reject path | contract marked rejected | — | optimistic removal + toast |
| "🟢 אשר הכל" (bulk) | `POST /api/approvals/bulk` | owner | same per-item flag/TTL checks; low-risk-and-actionable rows only | same as single approve, looped | `{approved, failed, skipped}` | toast summary + full reload |
| Non-actionable row | — (no button rendered) | — | — | — | static message: `legacy_read_only` → "רשומה ישנה — לקריאה בלבד"; else → "לא ניתנת לביצוע כרגע" | never offer a button that can only fail — keep this pattern |

### States
Loading / Success / Empty ("no pending approvals") / Error / Unauthorized (owner-only 403) / Stale — a row whose underlying contract changed since load surfaces as non-actionable with the message above rather than a stale-looking enabled button; this is a deliberate existing safety pattern, preserve it in any redesign.

### Forms
**Reject note** (optional, inline on the reject action) — `note` (canonical `ApprovalsFields.REJECTION_NOTE`, text, not required, empty default, owner). No approval-*creation* form exists on this screen by design — approvals are always produced by other screens' write actions.

---

## Knowledge

### Purpose
**No single existing backend screen maps to this concept.** This section is a spec recommendation built on the cheapest real path, not a description of something already shipped: a browsable institutional-memory feed — manually logged business context plus system-captured interaction history — "what have we learned or decided, and when."

### User roles
No existing Knowledge-specific gate to cite. Recommend matching the closest real analog (`GET /api/activity`, owner+manager) pending an explicit owner decision — do not invent broader access than that without one.

### Data sources (realistic, cheapest-first — see Gap Matrix)
- `GET /api/activity` (Business Memory + a `[TMA receipt]`-filtered Interaction Log slice) — **extend this**, don't rebuild it.
- `GET /api/marketing/demands` — pre-existing, fold in as a sub-view.
- Decision Hub (`Decisions` / `Decision Events` / `Decision Stakeholders` / `Decision Inbox` tables, `cmd_decision.py`) — real, detailed schema; `FEATURE_DECISION_HUB` defaults off, zero TMA wiring. Genuinely new build, not a wiring task.

### KPIs
| KPI | Formula |
|---|---|
| Entries in period | `len(entries)` from the extended activity feed |
| (Future) Open Decisions / Inbox pending | Only meaningful once Decision Hub is wired — do not fabricate this number today |

### Main views

**Primary feed (recommended, built on `/api/activity`'s existing shape)** — same row shape as Operations' Activity feed: channel icon, title, summary, domain pill(s), relative timestamp, sentiment/impact. Same detail-sheet expand pattern. **Filters to add** (backend comment already flags `?domain=` as "reserved for future"): domain, date range, source (`business_memory` vs. `receipt`, later `decision`).

**Marketing sub-view (pre-existing, fold in as-is)** — cards: title, consistency-state warning badge (if `inconsistent`), stage/status subtitle, next_action, detail text. Read-only, no actions.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| (none today) | — | — | — | — | — | pure read feed, same as Activity |

**A "log a business update" create form is a plausible future addition, not a small one:** today `/update` is Telegram-command-only (flag off), and its domain-value validation (`resolve_business_memory_domain()`, resolving against Airtable's *live* singleSelect choices rather than a static list) lives inside the Telegram command handler, not a shared service function — extending `tma_write` to this table means either extracting that validation first or re-implementing it, not a one-line reuse.

### States
Loading / Success / Empty ("no entries") / Error / Unauthorized (owner+manager, per recommendation) — no "stale" concept on a direct read.

### Forms
None exist today. If "log a business update" is added, mirror the existing Telegram `/update` wizard's 3 required fields exactly — don't invent a different shape:

| Field | Label | Required | Options |
|---|---|---|---|
| Domain | תחום | yes | Resolved live against Airtable's actual choices server-side — do not hardcode a list client-side |
| Entry type | סוג | yes | פגישה / שיחה / החלטה / סיכון / הצעת מחיר / רעיון / אחר |
| Content | תוכן | yes | free text |

---

## Settings

### Purpose
System safety controls (emergency stop) today; longer-term, the operational-configuration surface (feature flags, identity/role assignment, channel routing). **Almost entirely just the emergency-stop panel today** — everything else listed is a recommended addition with an honest gap classification.

### User roles
Owner only — across every existing feature **and** every recommended addition. No code anywhere grants Manager/Partner any Settings access, and given the blast radius of what lives here (emergency stop, feature flags, identity/role assignment), that is the sane default to preserve rather than merely an artifact of what happens to be built.

### Data sources
`EmergencyStopManager` (durable, Airtable-backed) via `GET /api/health` + `POST /api/health/emergency[/clear]`. Recommended, unwired: `feature_flags.py`'s ~40-flag registry; `identity.py`'s static `_REGISTRY`; `config.py`'s `CHANNEL_DOMAINS`.

### KPIs
| KPI | Formula |
|---|---|
| Overall status | `ok / degraded / emergency` |
| Per-service status | Airtable / Telegram / Anthropic, each a live probe |
| Active emergency-flag count | `len(active_emergency)` |

### Main views

**Emergency Stop (the one fully-built part)** — status banner; per-service rows (🟢/🔴/🟡 + label); Active Emergency Flags block (shown only if any active) with a two-step-confirm clear button per flag; Emergency Stop block with 5 two-step-confirm stop buttons.

| Button | API/tool | Auth | Approval? | Canonical writer | Result | UI state |
|---|---|---|---|---|---|---|
| Stop (any of 5: all/whatsapp/email/automation/ai) | `POST /api/health/emergency {action}` | owner | **not** ActionGateway-mediated — a direct, unconditional durable write; the two-step client confirm is the only friction | `feature_flags.set_emergency_stop()` → `EmergencyStopManager` (Airtable-backed, `source="tma_owner_stop"`) | `{ok, action, flag, operation_id}` | immediate status update + owner Telegram notification |
| Clear | `POST /api/health/emergency/clear {action, expected_operation_id}` | owner | optimistic-concurrency CAS: `expected_operation_id` must match current, else **HTTP 409** | same manager, `source="tma_owner_clear"` | `{ok, action, flag, operation_id, still_blocked_by_env}` | on 409: distinct "someone/something else already changed this" message + auto-reload, never silent retry; if `still_blocked_by_env=true`, **do not show success** — an env var still forces the block |

**Recommended additions (all currently gaps, see Permission Matrix):**
- General flag-registry table (name / current value / default / description) — read-only first. **A naive on/off toggle UI is actively dangerous**: many of the ~40 flags gate multi-stage rollouts with a specific dependency order documented in `feature_flags.py`'s own docstring (e.g. `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` must precede `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE`; `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` must precede `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`). Any write UI must enforce that ordering server-side, not just document it.
- Identity/user-management table (name / channel / role / tenant / domains) — a policy-and-infrastructure decision before any UI work, not a coding task (see Permission Matrix).
- Channel/domain routing config (`CHANNEL_DOMAINS`) — same; currently code-deploy-only.
- Doctor diagnostics tile — cheapest of the four additions; `boss_doctor.run_doctor()` is already safe to expose, just needs a route.

### States
Loading / Success / Error / Unauthorized (owner-only 403) — no "stale" concept; every load is a fresh live probe, nothing is cached.

### Forms
None today — every existing Settings action is a single-click two-step confirm, not a multi-field form. Any future flag-toggle or identity-edit form is new build with its own validation requirements, not a wiring task.
