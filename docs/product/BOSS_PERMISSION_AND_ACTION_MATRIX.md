# BOSS Admin App — Permission & API Gap Matrix

**Status:** Draft implementation-ready spec artifact. **Reconciles, does not duplicate.**
**Date:** 31/08/2026.
**Companions:** `docs/product/BOSS_ADMIN_APP_IMPLEMENTATION_SPEC.md` (narrative spec, entity drilldowns, build order), `docs/product/BOSS_SCREEN_CONTRACTS.md` (per-screen field/action contracts).
**Also relevant:** `docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md` (WIP UX/design gate) leaves several architecture questions explicitly open in its §11 (e.g. "is Finance always primary or role-gated?", "are Contacts/Deals tabs, views, or separate entities?"). This document's role-reality findings (§2) and the entity drilldowns in the Implementation Spec answer several of those from actual code — cite this document when resolving that gate's open questions rather than re-deriving the role/entity facts from scratch.
**Method:** every row below is grounded in a direct read of current code on this branch (`tool_registry.py`, `tma_api.py`, `airtable_schema.py`, `feature_flags.py`, `identity.py`, `commercial_crm.py`, `event_bus.py`, plus the existing `tma-frontend/src` components) and cross-checked against `docs/architecture/CURRENT_SYSTEM_EXECUTION_MAP.md` (31/08/2026 ground-truth audit, cited as "Execution Map §N" below). Nothing here is invented product surface — where no code exists, it is marked as a gap, not described as if built.
**Non-goal:** this document does not change business intent. Golden-rule test and agent scope remain `docs/governance/BOSS_BUSINESS_INTENT.md` (unchanged, owner-authority-only).

---

## 1. Role hierarchy (ground truth)

`identity.py::Role._RANK`: **owner=6 > partner=5 > manager=4 > employee=3 > lead=2 > guest=1 > readonly=0**.

`Identity` is never `None` — `resolve_identity(channel, external_id)` looks up a static, process-local registry (`_REGISTRY`, built once at import from `IDENTITY_MAP` env JSON → `identity_map.json` file → an `ELIYAHU_CHAT_ID`-derived owner fallback). An unrecognized `channel:external_id` key falls back to `Role.LEAD` (WhatsApp) or `Role.READONLY` (everything else) — it never crashes and never returns an unauthenticated state. **There is no runtime API anywhere in the codebase that adds, edits, or removes an identity/role mapping** — this is a durable gap, see §4 Settings rows.

`Identity.can_access_domain(domain)`: owner → always `True`; partner → `domain in self.allowed_domains`; every other role → always `True`. **Domain scoping is only meaningfully enforced for the `partner` role** — this is the sole role for which the `allowed_domains` list does anything.

Tool-registry role buckets (`tool_registry.py:184-189`), used throughout this document:
- `_INTERNAL` = `{owner, partner, manager, employee}`
- `_MANAGEMENT` = `{owner, partner, manager}`
- `_SENIOR` = `{owner, partner}`
- `_OWNER_ONLY` = `{owner}`
- `_ALL_EXTERNAL` = `{owner, partner, manager, employee, lead}`

## 2. The TMA's actual role reality — read this before designing any screen

The task brief asks for "roles actually supported by code... do not invent unrestricted access." Reading every route gate across all eight screens produces one clear, and non-obvious, finding: **the TMA today is effectively an Owner console with a narrow Manager slice and an even narrower Partner slice. Employee, Lead, Guest, and Readonly have zero confirmed TMA route access anywhere in the codebase.** This is materially narrower than the 6-role hierarchy `identity.py` defines for the Telegram/WhatsApp agent surface — the TMA has never been built out past Owner+Manager+partial-Partner.

| Route family | Screen | Roles that actually pass the gate | Gate mechanism |
|---|---|---|---|
| `GET /api/owner/*` (health, control-center, command-center, my-work) | Command Center | **owner only** | `if not identity.is_owner: 403` |
| `GET/POST/PATCH /api/ventures*` | Ventures | **owner only** | `if not identity.is_owner: 403` |
| `GET /api/projects` (Hub list) | (Projects Hub — pre-existing home screen, not one of the 8) | **owner only** | hard 403 |
| `POST /api/projects` (create) | Ventures/Ops-adjacent | **owner only** | — |
| `GET /api/projects/<slug>/dashboard` | Pipeline (per-venture) | owner **or** partner with `can_access_domain(domain)` | dynamic domain check |
| `GET /api/leads`, `GET /api/leads/<id>` | Pipeline | owner, manager, **partner (own domain only)** | role set + domain check on partner |
| `PATCH /api/leads/<id>`, `PATCH /api/leads/<id>/status`, `POST /api/leads/<id>/outcome`, `POST /api/leads/<id>/task`, `POST /api/followup` | Pipeline | **owner, manager only** (partner excluded from all writes) | explicit role-in-set check |
| `GET /api/finance/pulse` | Finance | **owner only** | `if not identity.is_owner: 403` |
| `GET/PATCH /api/assets*` | Finance (Assets sub-view) | GET: owner or `"personal" in identity.allowed_domains`; PATCH: **owner only** | mixed — read looser than write |
| `GET /api/activity` | Operations | **owner, manager** | role-in-set check |
| `GET /api/owner/my-work` | Operations | **owner only** | — |
| `GET/POST /api/approvals*` | Approvals | **owner only** | — |
| `GET/POST/PATCH /api/health/emergency*`, `GET /api/health` | Settings | **owner only** | — |
| `GET/PATCH /api/game/*` | (existing gamification layer, not one of the 8) | **owner only** | — |
| `GET /api/marketing/demands` | (Knowledge-adjacent) | any authenticated identity — no role narrowing found | — |

**Implication for spec design:** any screen wireframe that assumes Manager or Partner gets a materially complete view of Command Center, Ventures, Finance, Approvals, Operations-my-work, or Settings is describing a **POLICY DECISION REQUIRED** gap, not a READY feature — see §4. Where this spec's screen contracts describe multi-role behavior, they are describing what would need to be *decided and built*, and say so explicitly rather than assuming it already exists.

## 3. Tool Registry — full permission table (22 registered tools)

This is the Agent/Telegram tool-use permission surface (`tool_registry.py::enforce()`), separate from the TMA's own per-route role checks above. `enforce()` is the "iron rule" gate: no tool without a permission check, always called before `tools/dispatcher.py::dispatch_tool()`.

| Tool | roles_allowed | tenant_scoped | requires_approval | high_risk | read_only | model_exposed |
|---|---|---|---|---|---|---|
| `search_drive` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `read_drive_file` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `calendar_get_events` | `_INTERNAL` | — | — | — | ✅ | ✅ |
| `calendar_create_event` | `_MANAGEMENT` | — | ✅ | — | — | ✅ |
| `gmail_draft` | `_MANAGEMENT` | — | ✅ | — | — | ✅ |
| `gmail_send_draft` | `_SENIOR` | — | ✅ | **✅** | — | ✅ |
| `gmail_read` | `_OWNER_ONLY` | — | — | — | ✅ | ✅ |
| `sheets_append` | `_MANAGEMENT` | — | ✅ | — | — | ✅ |
| `airtable_get` | `_ALL_EXTERNAL` | ✅ | — | — | ✅ | ✅ |
| `airtable_add` | `_INTERNAL` | ✅ | ✅ | **✅** | — | ✅ |
| `airtable_update` | `_MANAGEMENT` | ✅ | ✅ | **✅** | — | ✅ |
| `airtable_get_schema` | `_SENIOR` | — | — | — | ✅ | ✅ |
| `search_lead` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `resolve_contact` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `get_daily_report` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `search_business_memory` | `_MANAGEMENT` | — | — | — | ✅ | ✅ |
| `crm_mark_payment_paid` | `_SENIOR` | ✅ | ✅ | **✅** | — | ✅ |
| `media_save_to_memory` | `_INTERNAL` | — | ✅ | — | — | internal only |
| `send_followup` | `_INTERNAL` | — | ✅ | — | — | internal only |
| `send_recovery` | `_INTERNAL` | — | ✅ | — | — | internal only |
| `tma_write` | `{owner, manager}` (narrower than `_INTERNAL` by design — the union of roles that actually reach `_queue_tma_write_approval()` call sites) | — | ✅ | — | — | internal only |
| `external_execution.submit` | `_INTERNAL` | — | ✅ | — | — | internal only |

**Invariant confirmed by direct read:** no tool has `high_risk=True` without also `requires_approval=True`. All 12 approval-required tools also set `blocked_by_emergency=True`.

`tma_write` is the mechanism behind almost every TMA-initiated write across every screen (Leads, Tasks, Ventures, Assets) — a generic `{op: "post"|"patch", table, fields}` payload proposed through `core/action_gateway.py::propose_action(tool_name="tma_write", trusted_source="tma_api")`, never exposed to the Claude tool-use loop.

## 4. TMA write mechanics — the two patterns every screen's write actions follow

Every TMA write observed in this codebase goes through one of exactly two thin wrappers around `core/action_gateway.py`, never a direct Airtable write:

- **`_queue_tma_write_approval(...)`** — always creates a pending `ActionContract` and returns HTTP 202, **even for Owner**. Used by: `PATCH /api/leads/<id>/status`, `POST /api/followup`, `POST /api/projects`.
- **`_queue_or_owner_execute(...)`** — same proposal path, but if the caller `identity.is_owner`, the just-created contract is immediately claimed and executed inline in the same request (`_claim_and_execute_approval`) — synchronous HTTP 200 for Owner, HTTP 202 pending for Manager. Used by: `PATCH /api/leads/<id>`, `POST /api/leads/<id>/outcome`, `POST /api/leads/<id>/task`, `POST/PATCH /api/ventures*`, `PATCH /api/assets/<id>`.

**This split is inconsistent, not deliberate policy** — two nearly-identical Lead-mutation endpoints (`PATCH /status` vs `PATCH /api/leads/<id>` for the same status field) diverge on whether Owner gets synchronous execution. A spec that assumes uniform "Owner writes are instant" behavior is wrong for `/status`; flag this as a UX inconsistency to resolve during Pipeline screen build, not a documented feature.

**Hard runtime dependency (fails closed, does not degrade):** `POST/PATCH /api/approvals/<id>` (approve path) and every `_queue_tma_write_approval`/`_queue_or_owner_execute` call requires **both** `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS` to be live — both default OFF (`feature_flags.py:101-102`). If either is off in the target environment, the write path returns **HTTP 503** (`"durable approval infrastructure is not fully online"`) with no RAM-only fallback. Per Execution Map §9, `FEATURE_ATOMIC_CLAIMS` is *reportedly* live on Render per a 28/08/2026 snapshot — **not independently re-verified in this pass**. Any build-order plan (§ see Implementation Spec) must confirm both flags are live in the target environment before shipping any write-capable screen, or every write button silently 503s.

**Approval TTL:** TMA-side approvals expire 24h after `Approvals.בוקש בתאריך` (`_TMA_APPROVAL_TTL_SECONDS`); a malformed/missing timestamp fails closed as already-expired (opposite of the Telegram-side approval flow's more permissive TTL fallback) and auto-rejects with `rejected_by="ttl_expired"`.

**Bulk approval eligibility (`POST /api/approvals/bulk`):** only rows that are low-risk (`רמת סיכון = "נמוך"`), have an `action_contract_id`, are not `legacy_read_only`, and pass a canonical-TMA-contract scope check are auto-approved. Medium/high-risk approvals are never bulk-approved — the frontend independently re-derives this same eligibility rule client-side to compute the bulk-button count.

## 5. API Gap Matrix

Classification per the task brief: **READY** (wired end-to-end today) / **BACKEND EXISTS BUT UNWIRED** (a canonical writer or module exists in code but has zero live callers/registry entries) / **API MISSING** (no backend code addresses this at all) / **POLICY DECISION REQUIRED** (the gap is a role/scope/product decision, not a coding task — building it without an owner decision would be inventing scope BOSS_BUSINESS_INTENT.md forbids the Librarian/agent from doing unilaterally).

### Command Center

| UI requirement | Classification | Evidence |
|---|---|---|
| Attention feed, pending decisions, development-status roadmap tiles | **READY** | `GET /api/owner/command-center` (`tma_api.py:2735`), fully consumed by `OwnerControlCenter.tsx` today |
| System-health summary tile within Command Center | **READY** (partial data) | same endpoint's `system_status`, but `business_status`/`recent_activity` sections are a structurally-always-empty placeholder (`reason="unsupported_canonical_source"`) — no caller ever populates them |
| "What changed today" / daily delta feed | **API MISSING** | `BossDigest.tsx`'s own `TODO` comment confirms this is invented-empty client-side, no endpoint backs it |
| "Required actions today" digest section | **API MISSING** | same file, same `TODO` — comment says "load from Airtable Tasks table", never implemented |
| Real broken/partial/working system counts in the Daily Digest health bar | **BACKEND EXISTS BUT UNWIRED** | `/api/owner/control-center`'s `system_health.working_count/partial_count/broken_count` exist server-side and are correct, but `BossDigest.tsx` hardcodes magic numbers instead of calling that endpoint |
| Doctor-style diagnostics (`boss_doctor.run_doctor()`) on Command Center | **BACKEND EXISTS BUT UNWIRED** | `run_doctor()`/`DoctorReport` are pure-Python, side-effect-free, already used by the Telegram `/boss_doctor` command (`app.py:579`) — zero TMA route wraps it |
| Manager/Partner-visible Command Center (scoped) | **POLICY DECISION REQUIRED** | today it's `is_owner`-only with no scoped variant; deciding what a Manager should see requires an owner decision on scope, not just code |

### Ventures

| UI requirement | Classification | Evidence |
|---|---|---|
| List/filter-by-stage, detail, create, edit (stage/conviction/next_action/notes only) | **READY** | `GET/POST/PATCH /api/ventures*`, fully wired in `Ventures.tsx` |
| Editing `name`/`domain`/`estimated_potential`/`target_decision_date`/`decision_log`/`linked_contacts`/`owner` after creation | **BACKEND EXISTS BUT UNWIRED** | backend `PATCH` accepts these fields; the frontend detail view never sends them — UI-only gap |
| Filter by domain | **API MISSING** | no `domain` query param exists on `GET /api/ventures`; only `stage` is supported server-side |
| Adding `Media`/`Finance` as a Venture domain option | **POLICY DECISION REQUIRED** | `VentureDomain` enum + `domain_utils.py`'s `venture_legacy` vocabulary only recognize 5 values (`Real Estate, Import, SaaS, Recruitment, General`) — no `Media`, no `Finance`, plus `Recruitment` exists here but isn't one of the product's 6 named domains. Any fix requires an owner decision on the canonical Ventures domain list, then an Airtable single-select + enum change, not just a UI change |
| Venture → Deal conversion action | **BACKEND EXISTS BUT UNWIRED** | `Deals.VENTURE_LINK` (`commercial_crm.py::create_deal(venture_id=...)`) supports this relationship, but `create_deal()` itself has zero callers (see Finance row below) — building this button means wiring the underlying Deal writer first |
| Multi-tenant Ventures (per-tenant scoping) | **POLICY DECISION REQUIRED** | `tenant_provisioner.py` is dead code; even fully wired it only emits a paste-into-Render env snippet, not a live write — Ventures is single-tenant in practice regardless of any flag |

### Pipeline (Leads / Contacts / Deals)

| UI requirement | Classification | Evidence |
|---|---|---|
| Lead list (filterable by `active`/`monitoring`/`all` view, domain) | **BACKEND EXISTS BUT UNWIRED (partially)** | `GET /api/leads` supports `?view=` server-side but `LeadPipeline.tsx` never sends it — always the `active` view, no UI switcher |
| Lead detail, timeline, status/outcome/score changes, task creation, follow-up note | **READY** | fully wired, `LeadDetail.tsx` |
| Lead reopen (owner-only) | **READY** | wired, owner-gated in the same component |
| Manual score override | **READY** (owner-only) | `PATCH /api/leads/<id>` allows `score`; UI exposes it in an owner-only "Advanced" section |
| Tier display/edit | **API MISSING by design** | `tier` field is deliberately dropped from every PATCH (`_LEAD_IGNORED_PATCH_FIELDS`) — 0/39 live records populated; owner decision pending on whether to remove the field entirely |
| Lead → Contact conversion button | **BACKEND EXISTS BUT BROKEN** | `/convert` (Telegram-only, `LEAD_AUTO_CONVERT` flag off) calls `crm_add_contact(notes=...)`, but `Contacts` has no `Notes` field — `crm.py` rejects any non-empty `notes`, so conversion fails on the majority of real leads with a generic, unhelpful error. Fixing requires either dropping the notes payload or adding the field — not a wiring task, a bug fix, plus this has no TMA surface at all today (Telegram command only) |
| Deal list/detail/create/edit/stage-move | **API MISSING** | zero TMA route touches Deals as a first-class entity — the only trace is a read-only open-deals *count* inside the Projects dashboard KPI, and a dead-end `next_step === "create_deal"` label in `LeadDetail.tsx` with no button behind it |
| Deal creation with VAT/payment-term calculation | **BACKEND EXISTS BUT UNWIRED** | `commercial_crm.py::create_deal()`/`create_payment_term()`/`calculate_payment()` are fully built and correct, but have zero callers anywhere — not in `tool_registry.py`, `tools/dispatcher.py`, or `tools/schemas.py`. Building a Deals sub-screen means wiring this module for the first time, or building a parallel `tma_write`-style generic path and re-implementing its VAT logic client-side (not recommended — would bypass the existing calculation contract) |
| Payment "mark as paid" button on a Deal/Lead | **BACKEND EXISTS BUT UNWIRED (TMA-side)** | `crm_mark_payment_paid` is a real, approval-gated, wired *agent tool* (Telegram/tool-loop only) — no TMA route calls it; a TMA button needs a new endpoint following the same `_queue_or_owner_execute` pattern |

### Operations

| UI requirement | Classification | Evidence |
|---|---|---|
| "My work" (owner's own immediate/upcoming tasks) | **READY** (owner-only) | `GET /api/owner/my-work`, wired in `MyWork.tsx` |
| Manager-visible task list | **API MISSING** | `my-work` is hard owner-gated; no equivalent exists for Manager despite Manager being able to *create* tasks via Leads endpoints |
| Task complete/reassign/edit actions | **API MISSING** | `MyWork.tsx` renders read-only cards with zero click handlers or action buttons; no PATCH-task-status endpoint exists in `tma_api.py` at all (only the game-layer `Roadmap_Tasks` has a "done" PATCH, a different table) |
| Activity/audit feed | **READY (narrow)** | `GET /api/activity` merges Business Memory + a `[TMA receipt]`-tagged slice of Interaction Log — works, but the code's own comment flags `?domain=` as "reserved for future," and it excludes scheduler-job activity, task lifecycle events, and approval decisions |
| Scheduler / background-job status | **API MISSING** | no TMA route reads `schedule.jobs` or any job-run history; only visible via the Telegram `/boss_doctor` command |
| System doctor / diagnostics tile | **BACKEND EXISTS BUT UNWIRED** | same `boss_doctor.run_doctor()` gap noted under Command Center |
| Pending-actions-across-subsystems view | **API MISSING** | `event_bus.PendingActionsStore` (used by followup/abandoned-lead/lead-recovery/media/email/otp/scheduler) has no TMA read endpoint; `GET /api/approvals` is a different, non-authoritative store, not this one |
| Unified calendar/email/WhatsApp interaction timeline | **BACKEND EXISTS BUT FLAG-OFF, AND UNWIRED** | `interaction_engine.py` writes to `Interaction Log` but `INTERACTION_INTELLIGENCE` defaults off (documented as "(Future)" in the flag registry, not a rollout-ready toggle), and even when on has no dedicated TMA read surface beyond the narrow `/api/activity` slice |
| Tenant-scoped Tasks | **POLICY DECISION REQUIRED / bug** | `Tasks` table is absent from the dispatcher's `_TENANT_AWARE` set — every other canonical entity gets automatic tenant filtering, Tasks does not; this is a real cross-tenant leak risk once multi-tenant is ever activated, worth flagging to the owner regardless of screen scope |

### Finance

| UI requirement | Classification | Evidence |
|---|---|---|
| This-month income/pending/overdue/expenses/net KPI tiles, recent payments list | **READY** (owner-only) | `GET /api/finance/pulse`, wired in `FinancePulse.tsx` |
| Filter by view (`active`/`overdue`/`all`) or domain | **BACKEND EXISTS BUT UNWIRED** | both params are supported server-side; `fetchFinancePulse()` never sends either — zero UI filter surface |
| Assets/real-estate balance sheet (personal finance) | **READY** (owner, or partner scoped to `"personal"` domain) | `GET/PATCH /api/assets*`, fully wired in `PersonalMode.tsx` — note this is a pre-existing screen this spec should fold under Finance rather than re-invent |
| Deal/Payment/Payment-Term creation with correct VAT math | **BACKEND EXISTS BUT UNWIRED** | `commercial_crm.py` (see Pipeline row) — this is the single largest unwired-but-built surface in the whole app |
| Payment "mark as paid" | **BACKEND EXISTS BUT UNWIRED (TMA-side)** | see Pipeline row; would live on Finance too |
| Expense creation | **API MISSING** | `Expenses` table has zero writers anywhere in the codebase — not even an unwired one; read-only forever until someone builds a writer |
| Upcoming/overdue payment reminders as a Finance widget | **API MISSING** | `payment_reminder.py`'s scan results are transient (in-process, pushed once to the owner's Telegram) and never persisted or exposed via any API — surfacing this on Finance means calling `scan_due_soon()`/`scan_overdue()` directly from a new endpoint or persisting results somewhere new |
| AI cost / token-spend monitoring | **Out of scope for this screen** | `core/cost_watchdog.py`/`cost_monitor.py` track infrastructure spend, not business finance — do not conflate with Finance Pulse; belongs, if surfaced at all, on a system-health view |

### Approvals

| UI requirement | Classification | Evidence |
|---|---|---|
| Pending approvals list, single approve/reject, bulk-approve (low-risk only) | **READY** (owner-only) | `GET/POST /api/approvals*`, fully wired in `Approvals.tsx` |
| Approved/rejected history view | **API MISSING** | `GET /api/approvals` only ever queries `סטטוס='ממתין'` (pending); no endpoint returns decided approvals |
| Filter/search/sort on the pending list | **API MISSING** | no query params beyond the implicit pending filter; no UI controls either |
| Manager-visible approvals (their own requests) | **POLICY DECISION REQUIRED** | hard owner-only today; Manager can create approval-requiring actions (Leads/Tasks) but cannot see the resulting queue in the TMA at all — whether Manager should see their own pending requests is an owner scope decision |
| Medium/high-risk bulk approval | **Deliberately not supported — POLICY, not a gap** | bulk eligibility is intentionally restricted to low-risk only; treat as a confirmed design decision, not something to build around |

### Knowledge

| UI requirement | Classification | Evidence |
|---|---|---|
| Business-context / institutional-memory log (browsable) | **BACKEND EXISTS BUT UNWIRED** | `cmd_update.py` (`/update`, Telegram-only, `FEATURE_BUSINESS_UPDATE` off) writes real entries to `Business Memory`; `GET /api/activity` already surfaces this table (unfiltered) as part of its merged feed — the cheapest real build here is extending `/api/activity` into a dedicated, filterable Knowledge feed rather than building new plumbing |
| Decision entity (list/detail/create) | **API MISSING**, rich schema exists | `Decisions`/`Decision Events`/`Decision Stakeholders`/`Decision Inbox` Airtable tables and `cmd_decision.py` writers are real and detailed, but `FEATURE_DECISION_HUB` defaults off and there is zero TMA API wiring — building a Decision drilldown is a from-scratch API build on top of an already-designed schema |
| Uploaded file / media browsing | **API MISSING** | no file/media store exists in the TMA surface at all; `/api/assets` is unrelated (real-estate financial assets, not files), and `media_save_to_memory` only stores voice-memo *transcriptions* into Business Memory, not raw files |
| Unified interaction search ("what did we discuss with X?") | **BACKEND EXISTS BUT FLAG-OFF** | `search_business_memory` tool exists (agent/Telegram-only) and `interaction_engine.py` writes a real log, but `INTERACTION_INTELLIGENCE` is off and there's no TMA search endpoint over either table |
| Marketing status as a Knowledge sub-view | **READY** | `GET /api/marketing/demands`, wired in `MarketingStatus.tsx` — pre-existing screen, fold in rather than re-invent |

### Settings

| UI requirement | Classification | Evidence |
|---|---|---|
| Emergency stop (5 flags): view status, stop, clear-with-confirmation | **READY** (owner-only) | `GET /api/health`, `POST /api/health/emergency[/clear]`, fully wired in `SystemHealth.tsx` — this is a genuinely complete existing Settings baseline, don't re-invent it |
| General feature-flag view/toggle (any of the ~40 non-emergency flags) | **API MISSING** | confirmed by grep: zero TMA route reads or writes any flag besides the 5 emergency ones; every other flag is env-var/`_DEFAULTS`-only, invisible and immutable from the TMA |
| User/identity management (add/edit team member, assign role/domain/tenant) | **API MISSING, and POLICY DECISION REQUIRED before it's even a coding task** | `_REGISTRY` is a module-level global loaded once at process start from a static env var or JSON file; there is no write path, no reload mechanism, and (per `tenant_provisioner.py`'s own design) even the *tenant* side of this would only ever emit a paste-into-Render snippet, not a live write, without further infrastructure decisions |
| Channel/domain routing config (`CHANNEL_DOMAINS`) | **API MISSING** | hardcoded, currently-empty Python dict, edited only by a code deploy; no TMA surface, no runtime mutation path exists anywhere |
| Doctor/diagnostics as a Settings tile | **BACKEND EXISTS BUT UNWIRED** | same `boss_doctor.run_doctor()` gap as Command Center/Operations — one wiring task would satisfy all three call sites |
