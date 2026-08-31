# BOSS Admin App — Implementation Spec

**Status:** Draft implementation-ready spec artifact. No frontend code was written to produce this — reconstruction and specification only.
**Date:** 31/08/2026.
**Companions:** `docs/product/BOSS_SCREEN_CONTRACTS.md` (per-screen field/action contracts — read alongside this document, not instead of it), `docs/product/BOSS_PERMISSION_AND_ACTION_MATRIX.md` (role reality, tool registry, full API gap classification).
**Relationship to `docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md`:** that document (status `DESIGN / UX ARCHITECTURE GATE — WIP`, PR #600, `reports/tma-audit/TMA_UX_AUDIT_HE.md`) is the **UX/component-language gate** — canonical screen anatomy, shared components (`AppShell`/`PageHeader`/`Card`/`StatusBadge`/etc.), action-flow UX (`Initiate → Preview/Validation → Execute/Approve → Result → Receipt`), and a deliberately open set of navigation/architecture questions (its §11). This spec is the **data/API/permission-truth layer** underneath that gate: it does not answer UX questions (navigation count, board-vs-list pattern, Action Center vs. My Work) and defers to that document for them, but it does supply grounded answers to several of its open questions from actual code — e.g. §11 asks "is Finance always primary or role-gated?": this spec's Permission Matrix shows Finance is owner-only today, full stop. §11 asks about the Operations/Ventures/Projects boundary: this spec's entity drilldowns show Ventures (pre-deal evaluation) and Projects (`ProjectsHub`, live operational cards) are already two distinct tables in code, not a naming choice still open. Read both before designing a screen — this one for *what data and actions exist and who may use them*, that one for *how the screen should look and behave*.
**Method:** every claim below is grounded in a direct read of current code on this branch — `tool_registry.py`, `tma_api.py`, `airtable_schema.py`, `feature_flags.py`, `identity.py`, `commercial_crm.py`, `event_bus.py`, `core_knowledge.py`, `cmd_update.py`, `cmd_decision.py`, plus every existing `tma-frontend/src` component — cross-checked against `docs/architecture/CURRENT_SYSTEM_EXECUTION_MAP.md` (31/08/2026 ground-truth audit). Where no code exists for a described capability, it is explicitly labeled a gap with its API-gap classification, not described as if built. This spec reflects current backend truth; it does not propose a parallel product model.

## Governing constraint

`docs/governance/BOSS_BUSINESS_INTENT.md` (owner-authority document, unchanged by this spec) sets the golden-rule test every screen/action in this spec must clear:

> **האם השימוש ב-BOSS פשוט, מהיר, ברור או בטוח יותר מפתיחת הכלי המקורי וביצוע הפעולה ישירות?**
> (Is using BOSS simpler, faster, clearer, or safer than opening the original tool and doing it directly?)

A feature fails this test — and should be `SIMPLIFY`/`AUTOMATE_MORE`/`KEEP_NATIVE`/`REMOVE`'d per that document's own Librarian classification — unless it reduces at least one of: user actions, information the user must enter, need to know the tool's internal structure, system-switching, time, error risk, or manual tracking. Every screen section below that recommends a new build is written with this test in mind; where a recommendation is genuinely a new business capability rather than a UI wrapper on an existing one, this spec flags it for an explicit **owner decision** (per that document's §7 Librarian classifications — `KEEP / ADAPT / MERGE / FREEZE / REMOVE / VERIFY / OWNER_DECISION`) rather than assuming it should be built.

## Screens overview

| Screen | Contract | Today's reality (one line) |
|---|---|---|
| Command Center | `BOSS_SCREEN_CONTRACTS.md#command-center` | Fully wired, owner-only, read + navigate |
| Ventures | `BOSS_SCREEN_CONTRACTS.md#ventures` | Fully wired CRUD, owner-only, real domain-vocabulary gap |
| Pipeline | `BOSS_SCREEN_CONTRACTS.md#pipeline` | Leads fully wired; Deals have zero TMA surface |
| Operations | `BOSS_SCREEN_CONTRACTS.md#operations` | Read-only MVP; no task actions exist yet |
| Finance | `BOSS_SCREEN_CONTRACTS.md#finance` | Read-only P&L snapshot + a real, working Assets balance sheet |
| Approvals | `BOSS_SCREEN_CONTRACTS.md#approvals` | Fully wired, owner-only, the single execution choke point |
| Knowledge | `BOSS_SCREEN_CONTRACTS.md#knowledge` | No dedicated backend; built here as a recommendation on top of Activity |
| Settings | `BOSS_SCREEN_CONTRACTS.md#settings` | Emergency Stop is fully built; everything else is a gap |

**Pre-existing screens this spec folds in rather than re-invents** (not among the 8, but real, wired, and referenced above): Projects Hub (`/api/projects`, the current app landing screen and KPI source), Assets/"Personal Mode" (folded into Finance), Marketing Status (folded into Knowledge), and the gamification layer (Game/Checkin — out of scope for these 8 screens; its writes bypass ActionGateway entirely, which is worth the owner's attention independent of this spec but is not this spec's concern).

## Entity drilldowns

Per the task brief's required entity list. Each entry states: canonical fields, canonical writer (or the absence of one), current TMA surface, and what a detail page should show if/when built.

### Lead
**Fields** (`LeadFields`): `Name, phone, status, Score, tier (dead — 0/39 populated, owner decision pending on removal), notes, summary, answers, source, channel, created_at, memory_key, tenant_id, domain, converted_at, Business Outcome, Next Followup, Owner (→Profile), Next Action (has a known live field-value mismatch — code constants don't match the actual Airtable option strings, latent because this field isn't written from the TMA), external_id, sender_id`.
**Status values:** `waiting_call, active, high_confidence, new, waiting_response, archived, lost, duplicate, not_relevant, done`. **Outcome keys:** `open, needs_followup, meeting_scheduled, converted, not_relevant, lost, duplicate, archived`.
**Canonical writer:** `core/lead_service.py::create_lead()` — Owner resolution (hard-fail if unresolvable), dedup, `ActionGateway.propose_action()`, write via `airtable_gateway`. **Live legacy bypass:** `voice_adapter.py::_save_voice_lead()` writes directly via `airtable_tools.airtable_add()` — no Owner resolution, no dedup, no tenant scope — because `VOICE_CANONICAL_LEAD_WRITE` defaults off and its canonical wrapper is unreachable. This is a real, current production gap independent of this spec.
**TMA surface:** fully built — this **is** the Pipeline screen's detail view (see Screen Contracts). **Recommended cheap addition:** a "Tasks for this lead" panel — `Tasks.LEAD_LINK` is already populated by the existing `create_lead_task` writer, so this is a read-only query away, not a new writer (**BACKEND EXISTS BUT UNWIRED**).

### Contact
**Fields** (`ContactFields`): `שם, חברה, אימייל, טלפון, תאריך פולו אפ, סטטוס (חדש/בתהליכים/פולו-אפ/לא רלוונטי), Role Category, Specialty, עסקאות (Deals) [link], משימות (Tasks) [link], Origin Lead`. **No `Notes` field exists** — this is the direct cause of `/convert`'s live bug (below).
**Canonical writer:** `crm.py::create_contact_from_fields()` → `find_or_create_contact()` (lock-serialized dedup) → `airtable_create()`; updates via `crm.py::update_contact()`.
**TMA surface: none.** There is no Contact list or detail screen anywhere in the TMA today. The only path from Lead to Contact is the Telegram-only `/convert` command (`LEAD_AUTO_CONVERT` flag, default off), and it is **currently broken for most real leads** — it passes a `notes` string built from the lead's summary/source into `crm_add_contact(notes=...)`, but `crm.py` explicitly rejects any non-empty `notes` since the field doesn't exist on `Contacts`, so conversion fails with a generic, unhelpful error on nearly every real lead.
**If built:** detail page = identity fields + linked Deals + linked Tasks + Origin Lead backlink. **Fix the notes-field bug first or alongside** — building a pretty Contact screen on top of a broken conversion path just moves the failure point.

### Deal
**Fields** (`DealFields`, table `עסקאות (Deals)`, a legacy Hebrew-named table with real-estate-shaped deprecated fields that must never be written): `שם העסקה, סכום, שלב (הזדמנות/במשא ומתן/סגור-ניצחון/סגור-הפסד), תאריך סגירה, מקושר לאנשי קשר, משימות (Tasks), תשלומים (Payments), Origin Lead, Domain, Owner, Ventures [link], Priority, Payment Terms [link]`.
**Canonical writer (fully built and statically wired by PR1153):** `commercial_crm.py::create_deal(name, domain, owner_id, *, origin_lead_id, venture_id, contact_ids, amount, stage=OPPORTUNITY, priority, risk_level, notes)` is exposed as `crm_create_deal` through `tool_registry.py`, `tools/dispatcher.py`, and `tools/schemas.py` with approval, tenant, and emergency-stop policy. **Runtime canary not yet verified.**
**TMA surface: none**, except a read-only open-deal *count* inside the Projects Hub dashboard KPI. There is no Deal list, detail, create, or stage-move UI anywhere.
**If built:** the remaining build is the first-class TMA Deal surface and an owner decision on whether TMA or the agent tool loop owns Deal creation; both must call the same VAT-aware writer rather than bypassing it with generic `airtable_add`.

### Payment
**Fields** (`PaymentFields`): `reference, amount, date (due date), status, deal_id [link], domain, Notes`, plus the newer canonical-track fields written only by the unwired path: `Origin Lead, Payment Term, Base Amount, Rate %, VAT Rule, VAT Amount, Trigger Evidence, Paid At, owner`.
**Status values:** `pending, received, overdue, canceled` (American spelling live; aliases `in_progress→pending`, `paid→received`).
**Canonical writer (fully built and statically wired by PR1153):** `commercial_crm.py::create_payment()` (always creates `status=pending`) + `calculate_payment()` + `create_payment_term()` are exposed as `crm_create_payment`/`crm_create_payment_term` with approval, tenant, and emergency-stop policy. **No production canary is claimed.** `crm_mark_payment_paid` remains the existing approval-gated agent tool; no TMA route calls it.
**TMA surface:** read-only, via Finance Pulse's aggregates and recent-payments list (no per-payment detail page, no click-through).
**If built:** detail page = ref, amount, date, status, linked deal, VAT breakdown once real VAT-calculated payments exist, trigger evidence, paid-at. "Mark as Paid" action needs a new TMA route wrapping the existing tool's logic through the same approval pattern every other Finance write uses.

### Task
**Fields** (`TaskFields`): `כותרת המשימה, תיאור, תאריך יעד, סטטוס (ממתין/בביצוע/בוצע), מקושר לאנשי קשר, מקושר לעסקאות, Domain, Owner, Leads [link]`.
**Canonical writer:** generic `airtable_add`/`airtable_update` via the dispatcher (`table=Tasks`), or one of two divergent TMA-specific endpoints (`create_lead_task` — full field population; `create_followup` — bare row, no domain/owner/lead-link copy). **Known gap:** `Tasks` is absent from the dispatcher's `_TENANT_AWARE` set — every other canonical entity gets automatic tenant filtering, Tasks does not; this is a cross-tenant leak risk once multi-tenant is ever activated, independent of screen scope.
**TMA surface:** cards only (My Work, Lead-detail creation confirmation) — **no dedicated Task detail page, and no status-change action anywhere** (API MISSING; only the unrelated gamification `Roadmap_Tasks` table has a "done" PATCH).
**If built:** detail = title, description, due date, status, linked lead/contact/deal, domain, owner, with a status-change action (needs a new `PATCH`-task-status endpoint — doesn't exist for this table today).

### Project
**Fields** (`ProjectsHubFields`, table `"ProjectsHub"` — comment in code: "must be created manually in Airtable," a distinct table from Ventures): `Name, Emoji, Slug, Mode, Project Type, Domain, KPI Fields (json), Quick Actions (json), Status, Owner Ids, tenant_id`.
**Not the same entity as a Venture** — a Venture is a pre-deal evaluation record; a Project is a live operational card (KPI counts, leads/tasks) once something is actually running. `Deals.VENTURE_LINK`/`Ventures.CONVERTED_TO_DEAL` connect Ventures to Deals, not to Projects.
**TMA surface:** `GET /api/projects/<slug>/dashboard` — owner or partner-with-domain-access — returns `{project_slug, domain, name, leads_count, open_deals, open_tasks, tasks_note (explicitly notes Tasks aren't domain-scoped), leads}`. This is the pre-existing app's home-screen drilldown, referenced but not redesigned by this spec.

### Decision
**Fields** (`airtable_schema.py`, a genuinely rich, already-designed schema — `Decisions` table): `Title, Domain (נדל"ן/ייבוא/גיוס/שותפות/כללי), Estimated Exposure, Exposure Type (כספי/משפטי/תפעולי/מוניטין), Status (Open/Pending Input/Decided Yes/Decided No/Cancelled), Readiness (READY/NOT_READY/REVIEW), Urgency (אין/שבוע/48 שעות/עכשיו), Current Draft #, Risk If Yes, Risk If No, Missing Info, Final Decision, Lessons Learned, links to Contacts/Deal/Tasks/Business Memory`, plus child tables `Decision Events` (timeline/evidence with trust level, source reliability, confidence score) and `Decision Stakeholders` (role: מחליט/מייעץ/מושפע/מתנגד) and `Decision Inbox` (raw-capture → suggested-match).
**Canonical writer:** `cmd_decision.py` (Telegram-only: `/decision new|update|status`), gated by `FEATURE_DECISION_HUB` (default off).
**TMA surface: none, zero wiring found anywhere in `tma_api.py`.** This is 100% new API build on top of an already-well-designed schema — genuinely the best-prepared "next" entity to wire, but explicitly flag-gated off pending an owner decision to activate it at all, per `BOSS_BUSINESS_INTENT.md`'s Librarian `OWNER_DECISION` classification.

### Media
**No dedicated media/file entity exists in the TMA surface at all.** `media_save_to_memory` (the one media-related tool) stores a **voice-memo transcription as text** into Business Memory — it is not a file store. `/api/assets` is unrelated (financial real-estate assets, not files). Drive/Sheets/Calendar/Gmail tools exist for the agent but have no TMA-facing browse UI. `FEATURE_MEDIA_UPLOAD`/`FEATURE_VOICE_NOTES` (F16, both default off) gate the underlying capture pipeline (`drive_adapter.py`) but even fully on, produce Drive-linked records with no TMA read surface.
**Recommendation:** do not design a Media drilldown against current backend — there is nothing to draw on. If the owner wants this, it starts as a new capability decision (what gets stored, retention, who can browse it), not a UI task.

### Approval
Covered in full in the Approvals screen contract — the list card **is** effectively the drilldown given the entity's flat structure. **Recommended addition:** an expand showing the full `CONTEXT_DATA` JSON payload (captured server-side today, never surfaced to the owner beyond the one-line `action` string) — cheap, since the data already exists on the row.

## Cross-screen navigation

The task brief's example lifecycle — **Lead → Contact/Deal → Payment → Task/Project → History/Evidence** — traced against real code:

1. **Lead created** via `create_lead()` (WhatsApp/Email/Furniture-funnel unconditional; WhatsApp/Voice behind not-yet-flipped canonical-write flags) → appears in **Pipeline**.
2. **Worked in Pipeline**: outcome progression, score, follow-up notes, task creation (`Tasks`, linked via `LEAD_LINK`).
3. **Terminal "converted" outcome → Contact**: today this step is **Telegram-only and broken** (see Contact drilldown above) — **the product's own headline lifecycle has no working TMA path from Lead to Contact.** This is the single most important gap this spec surfaces for the cross-screen-navigation requirement specifically.
4. **Contact → Deal**: no UI, no wired writer (`commercial_crm.create_deal()`, unwired) — would carry an `Origin Lead` backlink if built.
5. **Deal → Payment(s)**: via Payment Terms (`commercial_crm.create_payment_term()` → `create_payment()`, unwired) — would surface on **Finance** once wired; only "mark paid" exists today, and only as a Telegram-only agent tool.
6. **Task/Project**: Tasks link to Lead/Deal/Contact via `LEAD_LINK`/`DEALS_LINK`/`CONTACTS_LINK`; visible today only in **Operations**' My Work (owner-only) — no "tasks for this lead" panel exists on the Lead detail page despite the link data already existing (cheap fix, see Lead drilldown).
7. **History/Evidence**: `Interaction Log` entries are matched to a lead by a free-text `contains(lead_id)` scan on the summary field (not a real foreign key) — shown in the Lead detail timeline. The `Approvals` table shows the execution/evidence trail for any high-risk step along the way, tagged by `context_type` (`lead|deal|asset|general`).

**Command Center deep-linking:** `attention.items` carry a `destination` field (a screen name: `approvals`/`system_health`/`marketing`/`ventures`) that `OwnerControlCenter.tsx` already uses to route between screens. **Whether `destination` carries a record-level id for a direct deep link into a specific Lead/Deal/Approval was not confirmed in this pass** — worth verifying before assuming Command Center can jump straight to a specific record rather than just the right screen.

## Search

**No global search exists anywhere in the TMA today** — confirmed by reading every list screen; none has a search box, and no `tma_api.py` route implements cross-entity search. The agent-facing tools `search_lead`, `resolve_contact`, `search_business_memory`, and the generic `airtable_get` exist but are Telegram/tool-loop-only, never TMA-exposed.

**Recommended design**, grounded in the existing data architecture rather than inventing a new index:
- A single new `GET /api/search?q=` fanning out to per-entity Airtable formula searches: Leads (name/phone), Contacts (name/phone/company — once that screen exists), Deals (name — once wired), Tasks (title), Ventures (name), Business Memory (title/description).
- **Every fan-out branch must apply the same role/domain scope its own screen already enforces** — a search result must never surface a record the caller couldn't otherwise open directly. This is not a new authorization model; it's the existing per-route gates (§ Permission Matrix) applied inside one aggregating endpoint, not bypassed by it.
- Unified result shape: `{entity_type, id, title, subtitle, screen_deep_link}`.
- **Classification: API MISSING, whole capability.** This is new build with a role-scoping design step before any code, not a wiring task.

## AI assistant integration

`docs/governance/BOSS_BUSINESS_INTENT.md` §6 sets the binding boundary. **Allowed:** language understanding, information extraction, ambiguity detection, summarization, drafting, presenting alternatives, classifying against existing decisions, reasoning only where no reliable simple rule exists. **Forbidden:** guessing internal tokens, inventing a business process, unrestricted tool choice, reading unrequested information, expanding a simple task into an investigation, bypassing validation/permissions/approval, declaring success without evidence, continuing after ownership has passed to another component, creating a parallel source of truth.

Mapped onto the requested READ / SUGGEST / DRAFT / REQUEST APPROVAL / NEVER framework, against what's actually live:

| Tier | What it means | Current live surface | Where it could extend |
|---|---|---|---|
| **READ** | Assistant reads and explains data already loaded on the current screen | `POST /api/ai/ask` (context `lead_card`) — single-turn `llm_fallback.call_anthropic_text()` call via `core.turn_coordinator_runtime.resolve_tma_contextual_answer_capability()`, **not** the tool-use loop, no write capability | Same pattern on Venture/Deal/Approval detail pages if/when built — new endpoint, same guardrails |
| **SUGGEST** | Assistant proposes a classification/next step, never writes | Not a distinct TMA capability today — exists implicitly inside the general Telegram/WhatsApp `run_agent()` conversational loop, not surfaced as a discrete UI affordance in the TMA | A TMA "suggested outcome" chip on Lead detail — must remain suggestion-only, no auto-apply |
| **DRAFT** | Assistant composes text for human review before anything is sent | `gmail_draft` (management, approval-gated), `send_followup`/`send_recovery` (internal-only, approval-gated) — **Telegram/tool-loop only, never exposed on the TMA today** | A TMA "AI-draft follow-up" button would call one of these existing draft-only tools through a new approval-gated route — never auto-send, ever |
| **REQUEST APPROVAL** | Assistant proposes an action that must clear the same approval path as any human-initiated write | This is what every one of the 12 approval-required tools already does | An AI-initiated TMA action must land in the same `Approvals` queue as everything else — no separate, lighter-weight path for AI-originated proposals |
| **NEVER** | — | — | Direct write bypassing `ActionGateway`/`tool_registry.enforce()`; claiming success without evidence; inventing a process/table/field not already in the schema; reading beyond the current screen/record's own role+tenant scope |

**One concrete decision point this spec surfaces:** `run_agent()`'s conversational path is protected by `core/anti_hallucination.py` (`verify_execution`/`sanitize_agent_response`) plus the PA-01/RP5 evidence gates before any "I did X" claim reaches the user. `POST /api/ai/ask`, being a single non-tool-loop call, **does not go through those same evidence gates** — it has no tool access, so it cannot claim to have executed anything, but nothing in its response path today explicitly prevents it from *phrasing* an answer as if an action happened. Recommend: keep `/api/ai/ask` and any extension of it strictly read/summarize/explain, and treat "should this surface ever be allowed to propose or draft, not just answer" as its own explicit owner decision before building SUGGEST/DRAFT into it.

## Mobile / TMA vs. desktop behavior

The entire existing frontend **is** the mobile experience — a Telegram Mini App (React + Vite + TS), single-column throughout, full-screen-push navigation driven by a stack of booleans in `App.tsx` (not a router library — already at roughly a dozen screens toggled this way, a scaling concern independent of this spec), bottom sticky action bars (the pattern in `LeadDetail`/`PersonalMode`), two-step confirm for destructive/irreversible actions (`SystemHealth`'s emergency-stop buttons), and optimistic updates with a toast (`Approvals`, `LeadDetail`). **Codify these as the mobile design system for the 8 new/extended screens rather than inventing a different pattern per screen** — every screen contract in the companion document was written to fit this existing vocabulary.

**No desktop experience exists in this codebase today.** There is no separate desktop app, no responsive-breakpoint strategy, and no evidence of a planned one in any file read during this pass. If a desktop admin surface is wanted, it is new build, not a responsive tweak: recommend a persistent sidebar nav (the current emoji-button-row header pattern does not scale past its current ~12 entries) and master-detail multi-column layouts for the list-heavy screens (Pipeline, Ventures, Approvals). Flag this explicitly to the owner as its own decision — this spec does not assume desktop is in scope.

## Build order

Grounded in the API Gap Matrix — cheapest and lowest-risk first, genuinely-new capability last, policy-gated work explicitly held for an owner decision rather than built speculatively.

**Phase 0 — verify, don't build.** Confirm `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS` are both live in the target environment. Every write-capable screen in this spec 503s without both — this is a one-time environment check, not a feature.

**Phase 1 — shell, READY screens only, no new backend code.**
- Command Center as the landing screen (fully wired, read-only).
- Approvals (fully wired) — ship early precisely because every other screen's writes ultimately land here; reviewability from day one matters more than screen count.
- Pipeline: list + detail as they exist today (without yet exposing the unwired filters).
- Settings: Emergency Stop only.

**Phase 2 — close "BACKEND EXISTS BUT UNWIRED" gaps: UI work only, zero new backend code.**
- Ventures: full CRUD (already wired both directions end-to-end).
- Pipeline: wire the existing `?view=`/`?domain=` query params into real UI filters.
- Finance: wire `?view=`/`?domain=` on Finance Pulse; fix the Daily Digest health bar to call `/api/owner/control-center`'s real counts instead of its current hardcoded numbers.
- Command Center + Operations + Settings: one shared Doctor-diagnostics route (`boss_doctor.run_doctor()` is already pure and safe) satisfies all three screens' "system health tile" gap at once.

**Phase 3 — small, well-scoped new backend work.**
- Task status-change endpoint (`PATCH`) + wire My Work's action buttons + a Manager-visible task list.
- Knowledge: extend `/api/activity` into a filterable feed (domain, date range) rather than building a parallel endpoint.
- "Tasks for this lead" panel on Lead detail (`Tasks.LEAD_LINK` already populated — a query, not a new writer).
- A TMA route for `crm_mark_payment_paid`, following the existing `_queue_or_owner_execute` pattern used everywhere else.

**Phase 4 — genuinely new capability. Each item needs its own scoping pass, not just an API contract.**
- Deal/Payment/Payment-Term screens on `commercial_crm.py` — the first real caller of that module; decide up front whether the TMA or the agent tool loop gets first-class Deal-creation ownership, since both currently have equal (zero) claim to it.
- Contact list/detail screen (doesn't exist at all) — fix the `/convert` notes-field bug before or alongside, not after.
- Ventures domain-vocabulary reconciliation (5-value `VentureDomain` vs. the product's 6 named domains) — needs an owner decision on the canonical list before any Airtable schema or enum change.
- Global search — new build, needs the per-entity role-scoping design pass described above before any code.

**Phase 5 — explicitly policy-gated. Do not build without an owner decision** (this is precisely what `BOSS_BUSINESS_INTENT.md`'s `OWNER_DECISION` Librarian classification exists for — building ahead of the decision would be the Librarian/agent inventing scope the business-intent document forbids):
- Manager/Partner-scoped variants of Command Center, Approvals, Ventures, Finance, My Work.
- General feature-flag management UI, and only with server-side enforcement of the documented activation ordering (several flag pairs have a hard dependency sequence) — a naive toggle list would let an operator skip required rollout steps.
- Identity/user management UI — blocked on a real runtime-mutable identity store; today's `_REGISTRY` is a static, once-per-process env/file load with no write path at all.
- Decision Hub TMA surface — flag currently off; the schema is ready, the decision to activate it is not this spec's to make.
- Multi-tenant Ventures/Settings — blocked on `tenant_provisioner.py` being more than the half-manual, paste-into-Render tool it is today.
