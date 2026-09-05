# BOSS Bot — ROADMAP

עודכן: 05/09/2026

## Commercial Completion Writer foundation — 03/09/2026

`CommercialCompletionWriter` is merged on `origin/main` through PR #1187 as a
pure, unwired deterministic foundation. S2A schema closure is now
`LIVE_SCHEMA_VERIFIED + STATIC_VERIFIED_ON_BRANCH`: thirteen additive canonical
fields plus two native Deal rollups and their dependent formula were directly
verified without record mutation. S2B now has three narrow mutation primitives
implemented and statically verified on its PR branch: universal Organization
find-or-create, Charge create, and Charge-required actual-movement Payment
create. They are internal-only and retain the existing approval and dispatcher
guards. S2C deterministic completion routing is now CODE_DONE on this branch;
static verification and review remain pending. No writer/reader cutover,
scheduler, Agent authority, live canary, or Airtable record change is claimed.
The exact design and blockers are tracked in
[`COMMERCIAL_COMPLETION_WRITER_DESIGN.md`](docs/architecture/commercial-completion/COMMERCIAL_COMPLETION_WRITER_DESIGN.md).

## Latest truth reconciliation — PR1152–1155

Truth Reset: `origin/main` = `a45f304ab2387139287bc13d07e3313ec6019b40` (01/09/2026) — one commit ahead of the `c6bcd0c` this section previously named; the intervening commit (merge `a45f304`, "close TR-15 through TR-17 evidence gaps") is CI/test-hygiene and doc reconciliation only, already captured by TR-15/16/17 = CLOSED_STATIC. PR1153 fixes the Contacts reasoning adapter, retimes `audience_report` to 08:05, and statically wires the three `commercial_crm` create tools. These items are **CLOSED_STATIC / RUNTIME_GATED**; the first-class Deal/Payment TMA surface, owner decision on raw-write ownership, and a real canary remain open. The remaining scheduler collision is Sunday 08:30 (`attribution_report`/`weekly_summary`) — still `OPEN_STATIC`, unchanged. The former 08:00 collision is historical/code-done. PR1154 is the authority for the Admin App screen/API gap classification, and PR1155 makes shared-checkout rules canonical in `AGENTS.md`.

**Fresh runtime/env reconciliation (01/09/2026, same SHA, TR-21–TR-27 in `BOSS_CURRENT_STATE.md`):** a Grade-A pass (read-only Render API + owner-authenticated diagnostic-endpoint reads, no code/flag/config changes) found live Render env already has `FEATURE_ACTION_GATEWAY`, `FEATURE_DECISION_HUB`, `FEATURE_MEDIA_UPLOAD`, `FEATURE_VOICE_NOTES`, `FEATURE_MARKETING_BRIDGE`, `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, and `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` set to `true` — several rows below describing these as "flag off" are stale relative to Render's actual configured state, though still accurate as *code-default* descriptions. The same pass found `config.py::OWNER_USER_ID_MAPPINGS` (WhatsApp/email/voice destination → owner) is empty, which fails closed **every** non-interactive canonical Lead writer (WhatsApp cutover, Voice, Email, Furniture) regardless of their own flags — **the WhatsApp/Voice canonical-write canary is NOT currently ready**, contrary to any prior "verify now" framing; it requires an owner-supplied `OWNER_USER_ID_MAPPINGS` value first. Full detail, plus three small diagnostic-only findings (scheduler health-check wiring, a since-corrected `FEATURE_PA01_ENFORCEMENT_STATE` malformed live value, a since-corrected malformed `GOOGLE_DRIVE_FOLDER_ID` Render key — **OLD_RUNTIME_STATE, both resolved same day, see TR-28/TR-29**): `BOSS_CURRENT_STATE.md` TR-21–TR-29.

**Gateway cutover verification closed (02/09/2026, `a45f304ab2387139287bc13d07e3313ec6019b40`):** controlled-staging runtime evidence from Render for the owner-approved Import canary `בדיקת-קנרית 12` verified one ActionContract → one atomic claim → one executor → one successful Deals write → one completed lifecycle → one final response, with `agent_calls=0`, RP5 `verified_write_success`, canonical claim `success`, and no divergence. The cutover verification stage is closed; remaining work is post-cutover soak/monitoring only for this Gateway path. This does not close unrelated capability canaries or RP5 `enforce` activation.

The older `SCHEMA_DATA_CONTRACTS` row below predates PR1153's wiring and must be read with this reconciliation as the current status: registration is closed-static; canary, TMA surface, and raw-write ownership remain open.

## Commercial CRM Owner SSOT remediation — 01/09/2026

`origin/main` at Truth Reset was `809ffc9054d68219cd1259b65b5ebc6f582e39cd`.
The Deal/Payment dispatcher boundary now resolves the authenticated canonical
identity through one shared Profile resolver before calling the canonical
writers. Display names are accepted only as a self-ownership presentation alias
and are never written; raw channel identifiers and unknown owners fail closed.
This is `STATIC_VERIFIED`
only. The failed Deal canary remains historical runtime evidence; a new
owner-approved canary is required after deployment.

**Architecture correction — 01/09/2026:** the post-deploy canary failures
after the above fix (unsupported natural-language field aliases, PR #1169)
exposed the actual root cause — Deal creation had no deterministic
`Intent` at all, so it always reached `Handler.AGENT` and the LLM chose
between `crm_create_deal` and generic `airtable_add`. That contradicts the
decided Turn Coordinator / Single Speaker architecture (the system routes
mutation intents deterministically; the agent is not relied on to choose).
PR #1171 (`route Commercial CRM through canonical tools`), which tried to
fix tool-selection via better tool descriptions, was **closed without
merging** for exactly this reason — it still left the choice to the agent.
`Intent.CREATE_DEAL` was added instead, mirroring `Intent.CREATE_TASK`'s
existing deterministic route exactly (`core/router/router.py`'s
`parse_deterministic_create_deal` → `Handler.TOOL`/`Handler.CLARIFY`,
`app.py`'s `_queue_deterministic_create_deal()` with `agent_calls=0`) —
see `docs/architecture/action-gateway/BUG-CRM-BYPASS_DETERMINISTIC_CREATE_DEAL_ROUTE_20260901.md`.
PR #1169's generic-write alias fix is held (not merged, not closed) as a
defense-in-depth layer, no longer the primary Deal-creation path. This is
`STATIC_VERIFIED` only — not merged, deployed, or runtime-verified.

## תחזוקת המסמך

- `ROADMAP.md` הוא current-state SSOT וניווט, לא implementation ledger.
- `CURRENT STATE` נקבע אך ורק לפי `origin/main` ב־Truth Reset מאומת. ענפים,
  PRs, commits מקומיים וטיוטות מוצגים לכל היותר כ־`PROPOSED / OPEN / NOT YET
  CURRENT` ואינם משנים סטטוס current.
- Program ID הוא זהות יציבה; שם תיאורי או implementation program אינו מחליף אותו.
- Horizon והמסמך הקנוני מחזיקים phase progress; archive מחזיק historical narrative.
- סטטוסי registry מותרים בלבד: `PLANNED`, `IN_PROGRESS`, `MERGED_STATIC`,
  `DEPLOYED`, `RUNTIME_VERIFIED`.
- כל תוכנית פעילה מפנה למקור קנוני מפורט אחד; runtime/deployment דורשים evidence מפורש.
- מסקנת audit/gate לקריאה בלבד שמשנה status, phase, Next, dependency או
  architecture decision חייבת להישמר במסמך current-state קנוני, גם אם לא נוצר PR קוד.
- יחסי תוכניות חייבים להירשם במפורש (`IMPLEMENTATION_OF`, `DEPENDS_ON`,
  `BLOCKED_BY`, `MERGED_INTO`, `CONTINUES`). אין להסיק אותם משמות דומים,
  קבצים משותפים, תחום ארכיטקטוני או כרונולוגיה; ללא marker מפורש היחס הוא `UNKNOWN`.

## 1. Current System Status

המערכת נמצאת ב־`IN_PROGRESS`: תשתיות הליבה, approval/action lifecycle,
Turn Coordinator, מסלולי הכתיבה הקנוניים ו־Command Center קיימים ב־main.
רוב התוכניות דורשות עדיין deployed-SHA או runtime verification; אין להסיק
הפעלה ממסמך תכנון, code default או test מקומי. CORE v1 הוא `MERGED_STATIC /
READY TO FREEZE`; הכרעת freeze ו־formal Layer 2 TurnCoordinator עדיין פתוחות.
מקור הראיות: [`CORE_COMPLETION_AUDIT_20260810.md`](docs/audit/CORE_COMPLETION_AUDIT_20260810.md).

**Truth reconciliation (01/09/2026):** the current execution map findings are
tracked in [`BOSS_CURRENT_STATE.md`](BOSS_CURRENT_STATE.md) and the detailed
evidence remains in [`BUG_AUDIT_LOG.md`](BUG_AUDIT_LOG.md). The active open
sequence is: (1) live Render verification, (2) owner-gated Voice canonical
write canary and legacy retirement, (3) commercial CRM canary/TMA surface and
raw-write ownership decision, and (4) separate owner decisions for missing
TMA capabilities. No
runtime-only item is represented here as static code work.

## 2. Active Programs

| ID | Canonical Name | Status | Evidence | Next | Canonical Source |
|---|---|---|---|---|---|
| TURN_COORDINATOR_PROGRAM | Turn Coordinator | IN_PROGRESS | MERGED_STATIC — TC7-B/RP5 paths recorded | RP5 activation decision and deployed-SHA verification | [`HORIZON.md`](docs/governance/HORIZON.md) |
| UNIFIED_APPROVAL_ACTIONGATEWAY | Unified Approval / ActionGateway | IN_PROGRESS | RUNTIME_VERIFIED — controlled-staging Gateway canary passed 02/09/2026 on `a45f304`; cutover verification closed | Post-cutover soak/monitoring | [`HORIZON.md`](docs/governance/HORIZON.md) |
| F52 | F52 Unified Approval Runtime — Unified User Messages | IN_PROGRESS | R4, R4.1 and R6.1–R6.6 MERGED / STATIC VERIFIED; R5 GATE_COMPLETE; R7.1–R7.2 MERGED / STATIC VERIFIED (`3c45a87`, `1ff1cee`) | Continue with the next gated WhatsApp adapter sequence or separately gated runtime/deployment work | [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md) |
| N18 | Canonical Write Infrastructure | IN_PROGRESS | MERGED_STATIC — Phase 1 (`create_lead()` service) and Phase 2 (shared primitives) closed 20–21/08/2026; Phase 3 Slice 1 (Telegram Lead Preview cutover, PR #1043 `3de2dcf`) and Phase 4 (Telegram approve/cancel buttons, PR #1065 `2484f3c`) closed and grep/test-verified on `origin/main` (30/08/2026 documentation-gate pass) — `test_n18_slice1_lead_preview.py` 6/6, `test_n18_phase4_telegram_buttons.py` 4/4, `test_n18_draft_dispatch_unification.py` 8/8. WhatsApp (`lead_capture.py` / `core/whatsapp_lead_cutover.py`), Email (`inbound_handler.py` / `core/noninteractive_lead_cutovers.py`) and Furniture (`furniture_lead_funnel.py` via the same module) already call `create_lead()` in code today. Owner Resolution for non-interactive sources is already implemented (`core/source_owner_mapping.py`'s `resolve_owner_user_id()`/`resolve_furniture_owner_user_id()`, consumed by all three `noninteractive_lead_cutovers.py` wrappers) — not an open prerequisite. `LeadMemory` is a post-write enrichment/update path (`core.lead_service.update_lead_fields()`) and never creates a Lead, so it is not a creation-writer gap. | Voice IVR (`voice_adapter.py`) is the only writer with a live legacy `airtable_add()` bypass when `VOICE_CANONICAL_LEAD_WRITE` is off (its canonical path, `create_voice_inbound_lead()`, already exists and already resolves Owner). **Corrected 01/09/2026 (`BOSS_CURRENT_STATE.md` TR-22):** "Owner Resolution is already implemented" describes the *mechanism* only — `config.py::OWNER_USER_ID_MAPPINGS` (the data `resolve_owner_user_id()` looks up) is currently empty for all three sources, so every non-interactive canonical writer fails closed regardless of flag state. Before any `WHATSAPP_CANONICAL_LEAD_WRITE`/`VOICE_CANONICAL_LEAD_WRITE` activation or canary: owner must supply real destination→owner-user-id values via the `OWNER_USER_ID_MAPPINGS` env var (mechanism to accept this is `8b14600`, merged into `origin/main` via PR #1159 and deployed to Render — see `BOSS_CURRENT_STATE.md` TR-24/TR-28 — the env var itself is still unset, so this remains an open A2_OWNER_CONFIG_DECISION prerequisite, not a code gap). Only after that: owner-gated flag activation + live canary, then retiring Voice's legacy branch. Additional entity consumers (Tasks/Payments/Deals/Contacts/Expenses) require a separate owner-approved slice. | [`N18_PHASE_3_CANONICAL_LEAD_WRITERS_SPEC.md`](docs/architecture/n18-canonical-lead-writers/N18_PHASE_3_CANONICAL_LEAD_WRITERS_SPEC.md) |
| LEAD_CRM_CANONICAL_FLOW | Lead / CRM canonical flow | IN_PROGRESS | MERGED_STATIC — canary pending | Draft → Approval → Write → Evidence canary | [`HORIZON.md`](docs/governance/HORIZON.md) |
| MEDIA_LAYER_F16 | Media Layer (F16) | RUNTIME_VERIFIED | STATIC CLOSED + BASIC TELEGRAM CANARY RUNTIME_VERIFIED on Render production SHA `0f801225` (03/09/2026): photo persisted through Drive + Airtable and voice-note STT/action flow completed. M5 remains DEFERRED / ACCEPTED: repeated/forwarded content may persist again because Telegram identity is provider-ID based; content-hash dedup is not required. No `/media` command/button is part of the contract. | Normal monitoring only. Telegram `audio`, `video_note`, and storing original voice bytes remain separate, unapproved capabilities and do not reopen this program. | [`F16_MEDIA_RUNTIME_CANARY_20260903.md`](docs/evidence/F16_MEDIA_RUNTIME_CANARY_20260903.md) |
| COMMAND_CENTER_KNOWLEDGE_HUB | Command Center / Knowledge Hub | IN_PROGRESS | MERGED_STATIC — endpoint verification pending | Verify endpoint | [`HORIZON.md`](docs/governance/HORIZON.md) |
| BOSS_MEMORY_RETRIEVAL | BOSS Memory & Retrieval Architecture | IN_PROGRESS | MERGED_STATIC — retrieval shadow-only | Accumulate shadow evidence before cutover | [`BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md`](docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md) |
| DECISION_HUB | Decision Hub | IN_PROGRESS | STATIC COMPLETE / RUNTIME NOT ESTABLISHED. DH-S1 formula safety CLOSED / STATIC VERIFIED; DH-S2 access-policy wording DOC/POLICY DRIFT — CLOSED; DH-S3 fail-closed reads STATIC VERIFIED; DH-S4 partial-persistence observability CLOSED / STATIC VERIFIED; DH-CB-01–DH-CB-09 CLOSED / STATIC VERIFIED with direct callback and scope regressions. Structured persistence outcomes prevent false full success; runtime/deployment is not claimed. | Pursue separately gated runtime evidence without broadening permissions | [`HORIZON.md`](docs/governance/HORIZON.md) |
| COST_AGENT_LAST | Cost / Agent-Last architecture | IN_PROGRESS | MERGED_STATIC — telemetry remains shadow | Validate live usage/cost and decide progression | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| ARCHITECTURE_AUTHORITY_BOUNDARIES | Architecture authority / execution boundaries | IN_PROGRESS | MERGED_STATIC — runtime evidence separate | Verify deployed-SHA authority | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| SCHEMA_DATA_CONTRACTS | Schema / Data Contracts | IN_PROGRESS | MERGED_STATIC + S2A LIVE_SCHEMA_VERIFIED; S2B narrow primitives CODE_DONE + STATIC_VERIFIED on PR branch, with no record changes or cutover. | Review/merge S2B; writer/read switch remains separately gated | [`COMMERCIAL_SCHEMA_V2_ADD_ONLY_STATUS_20260903.md`](docs/governance/COMMERCIAL_SCHEMA_V2_ADD_ONLY_STATUS_20260903.md) |
| COMMERCIAL_COMPLETION_WRITER | Canonical Commercial Completion Writer | IN_PROGRESS | FOUNDATION MERGED (PR #1187); S2A CLOSED; S2B primitives merged; S2C deterministic completion routing CODE_DONE on this branch, STATIC_VERIFIED pending | Review/merge S2C; deployment/runtime and reader/writer cutover remain separately gated | [`COMMERCIAL_COMPLETION_WRITER_DESIGN.md`](docs/architecture/commercial-completion/COMMERCIAL_COMPLETION_WRITER_DESIGN.md) |
| N17 | Context Librarian Follow-up Hardening & Verification Backlog | IN_PROGRESS | MERGED_STATIC — maintenance remains ongoing | Continue bounded reconciliation and owner-gated follow-ups | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| BOSS_CONTEXT_LIBRARIAN_PHASE_0 | BOSS Context Librarian | IN_PROGRESS | MERGED_STATIC — mandatory bootstrap/index layer | Continue bounded reconciliation and maintenance PRs | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| ROADMAP_CORE | ROADMAP current-state SSOT | IN_PROGRESS | MERGED_STATIC — registry cleanup is this program's current slice | Keep current-state view compact and reconciled | [`ROADMAP.md`](ROADMAP.md) |
| APPROVAL_POLICY_SINGLE_SOURCE | Approval Policy Single Source | IN_PROGRESS | MERGED_STATIC — policy source and enforcement merged | Verify production reachability | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| MARKETING_EXECUTION_MAP | Marketing Execution Map | IN_PROGRESS | MERGED_STATIC — revenue execution mapping exists | Run the approved live canary | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| TASKS_DEADLINES_ROADMAP_TASKS | Tasks / Deadlines / Roadmap Tasks | IN_PROGRESS | MERGED_STATIC — current consolidation remains tracked | Resolve the remaining data-model work | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| AIRTABLE_SCHEMA_REFRESH | Airtable Schema Refresh | IN_PROGRESS | MERGED_STATIC — runtime verification remains scoped | Continue shadow validation before broader enforcement | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| SPEC_A1_ATOMIC_FAIL_CLOSED | SPEC A1 — Atomic Fail-Closed | IN_PROGRESS | MERGED_STATIC — current follow-up remains tracked | Continue the canonical error-propagation sequence | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| SPEC_PREVIEW_CONTENT_FIX | SPEC Preview Content Fix | IN_PROGRESS | MERGED_STATIC — production verification remains pending | Perform post-merge production verification | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| BUG_099_LEAD_EXTRACTION | BUG-099 Lead Extraction Integrity | IN_PROGRESS | MERGED_STATIC — current remediation/status is canonicalized | Follow the registered next gate | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| HERMES_INTERNAL_ARCHITECTURE_LEARNINGS | Hermes Internal Architecture Learnings | IN_PROGRESS | MERGED_STATIC — selective adoption only | Continue only for a concrete architecture gap | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| U1 | Understanding Layer Architecture | MERGED_STATIC | Owner decision recorded: no new general Understanding Contract or PendingAction Store; reuse existing layers | Continue with the approved reuse architecture | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5 |
| UX-01 | Unified BOSS Experience | IN_PROGRESS | R0.1, R1.1, R2.0, R2.1, R3.1, R3.2, R4, R4.1 and R6.1–R6.6 MERGED / STATIC VERIFIED; R5 GATE_COMPLETE; R7.1–R7.2 MERGED / STATIC VERIFIED (`3c45a87`, `1ff1cee`) | Continue only with the next gated channel-adapter phase | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5 |
| ORACLE_MIGRATION_M0 | Oracle Always Free Migration — M0 Repository Readiness | IN_PROGRESS | MERGED_STATIC — PR #1095 (`881ea33`); Dockerfile, Oracle Compose/Caddy/env template, gated deploy workflow, Postgres backup/restore, healthcheck alerting; overall migration verdict remains FULL MIGRATION POSSIBLE — REMEDIATION REQUIRED, STATIC VERIFIED / RUNTIME NOT ESTABLISHED; ARM64 status is STATIC ARM64 READY, not runtime-verified | M1 OPEN / NOT STARTED: provision Oracle VM, perform real Ampere A1 ARM64 verification, and complete DNS, TLS, and secrets cutover | [`ORACLE_MIGRATION_M0.md`](docs/operations/ORACLE_MIGRATION_M0.md) |

The historical dependency Pending Approval stable → U1 decision → UX-01 is
satisfied. U1 is resolved at architecture/static level. F52 / Single-Speaker
Approval UX is the implementation program/slice of UX-01; it does not rename
or replace the UX-01 identity. U1 is an architecture decision/gate resolved at
static level and is not an active blocker. F52 is explicitly
`IMPLEMENTATION_OF: UX-01`; no other parent/child or dependency relation is
assumed without an explicit marker.

## 3. Open Architecture / Owner Decisions

### RP5 Production Activation

Status: PLANNED / ACTIVATION DEFERRED. Owner decision: continue shadow evidence
collection and keep `FEATURE_EVIDENCE_FINALIZER=enforce` OFF. Reconsider activation
only after production shadow evidence review, deployed-SHA/canary conditions,
rollback readiness, and separate owner approval. This is an activation decision,
not permission to change the implementation. Canonical source:
[`RP5_PREFLIGHT_BLOCKER.md`](RP5_PREFLIGHT_BLOCKER.md).

## 4. Deferred / Blocked

### Queue / Worker Architecture

Status: PLANNED. Deferred until an explicit product/scheduler requirement and
ownership decision exists. Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md).

### Generic Draft Capability

Status: PLANNED. Deferred until the business requirement and scope are confirmed.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md).

## 5. Canonical References

- [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) — canonical Active Work Registry.
- [`HORIZON.md`](docs/governance/HORIZON.md) — management-level program map and phase boundary.
- [`MAINTENANCE_STATUS_MATRIX.md`](MAINTENANCE_STATUS_MATRIX.md) — maintenance/audit evidence status.
- [`BOSS_CURRENT_STATE.md`](BOSS_CURRENT_STATE.md) — operational current-state companion.
- [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md) — F52/Single-Speaker canonical plan.
- [`PROGRAM_DEPENDENCY_STATUS_DRIFT_AUDIT_20260828.md`](docs/audit/PROGRAM_DEPENDENCY_STATUS_DRIFT_AUDIT_20260828.md) — read-only drift audit and reconciliation evidence.
- [`BUG_AUDIT_LOG.md`](BUG_AUDIT_LOG.md) — audit evidence and historical findings.
- [`archive/ROADMAP_HISTORICAL_ARCHIVE_20260828.md`](archive/ROADMAP_HISTORICAL_ARCHIVE_20260828.md) — complete pre-cleanup ROADMAP snapshot, HISTORICAL only.

### Commercial human-link lookup incident — 04/09/2026

Production reported a `NameError` on the Telegram human Contact-link path
because `commercial_crm.lookup_human_reference()` referenced `ContactFields`
without importing it. Follow-up PR #1199 adds the missing schema import and a
regression test; merge, deployment, and runtime verification remain pending.

### Diamond Path completion runtime audit follow-up — 04/09/2026

A read-only mini-audit of Commercial Completion (human UX / router / session
/ renderer / canonical handoff) found `CommercialCompletionRouter.answer_human()`
raised `TypeError` on every non-trivial Contact/Organization resolution
(ambiguous match, no match, create-allowed) — a duplicate `choices` keyword
passed to `CompletionRoute(...)`. Fixing it surfaced adjacent gaps in the same
flow: `commercial_crm.lookup_human_reference()` accepted `identity`/`scope`
but never enforced them (unscoped Airtable read); Telegram `callback_data`
embedded raw choice labels (unsafe for Telegram's 64-byte limit and unable to
disambiguate duplicate labels); `field_presentation()`'s labels covered only
the Deal entity, leaving Organization/Payment Term/Charge/Payment prompts
generic; and an invalid SELECT answer's BLOCK reason leaked a raw internal
field name and Python-repr enum tuple. PR #1201 fixes all of the above and
adds a permanent runtime-integration regression pack
(`tests/test_commercial_completion_runtime_integration.py`) covering the full
LINK/SELECT/SCALAR/SESSION/COUNTERPARTY/OUTPUT branch matrix. One finding —
the Organization create path (`resolve_human_link()` returning
`status="create"` still resolves to `BLOCK`) — was intentionally left
unimplemented pending an owner decision, since the canonical
`crm_find_or_create_organization` writer requires async owner approval and
there is no existing mechanism to resume a paused `CompletionSession` once
that approval executes; the BUG-2 create-allowed no-match message now hands
the user to the separate, already-live `"צור ארגון <name>"` completion
intent instead as an interim fix — see PR #1201 for the full tradeoff. PR
#1201 merged to `main` (`18ffe1bf`, 04/09/2026); deployment and runtime
verification remain pending.

### DIAMOND PATH — nested-entity approval continuation — 04/09/2026 (production-reported)

Closes the gap the entry above left open (the Organization create path, and
the equivalent Contact case reported live in production — "עם מי העסקה?" →
"איש קשר" → "יאיר ממן" → dead-ended on "לא מצאתי התאמה; נא לנסות שם אחר."
with no path forward). Owner-directed design (three revisions before
implementation; see `docs/architecture/commercial-completion/` for the full
A–J contract) implements the full resume bridge instead of the prior
interim hand-off: a LINK field with no match now offers
`"לא מצאתי את <שם>. ליצור <איש קשר/ארגון> חדש? [כן] [לא]"`; confirming
enters a nested `CompletionSession` (`begin_nested()`, deferred until after
`"כן"` so declining needs zero rollback), completes it, and queues its
create through the existing `ActionGateway`/approval flow — never a second
writer (`crm_find_or_create_contact` reuses `crm.create_contact_from_fields()`
internally, mirroring the existing `crm_find_or_create_organization`
primitive; `"contact"` stays deliberately absent from
`SUPPORTED_COMPLETION_ENTITIES`, reachable only via `begin_nested()`, so the
existing standalone `CREATE_CONTACT` conversational flow is untouched).

A typed, versioned `ContinuationRef` (`commercial_completion.py`) — never a
free dict — travels on the `ActionContract` itself
(`core/action_gateway.py`, `core/action_contract_repository.py`, plus a new
`continuation_ref` field on the live `ActionContracts` Airtable table) from
proposal through to the approval callback. A nonce minted when the nested
completion is queued and embedded in its own frame is the actual resume
correlation key: the approval callback (`app.py`'s
`_resolve_diamond_path_continuation()`, `commercial_completion_routing.py`'s
`CommercialCompletionRouter.resume_nested()`) distinguishes "a different
session now occupies this slot" (nonce/shape mismatch → fail-closed,
untouched, logged `CONTINUATION_STALE_OR_MISMATCH`) from "the same
continuation, but now unresumable" (rejected, or no verified evidence
record id → actively cleaned up via `abandon_nested()`, never left orphaned)
from the real resume case (folds the canonical record id via
`resume_parent()` and continues inspection — possibly auto-completing and
re-queuing the parent Deal itself, through the same `queue()` boundary,
never a second write path). The resumed prompt (or cleanup) is composed
into the SAME single Telegram message the approval's own success/rejection
text uses (`_deliver_callback_final()`'s existing Single-Speaker boundary,
untouched) — never a second message. `session_store.py`'s
`get_commercial_completion()`/`set_commercial_completion()`/
`clear_commercial_completion()` gained an optional `channel` parameter so a
Contact/Organization approved via the owner's Telegram inline keyboard
correctly resumes a parent completion that started on a different channel
(e.g. WhatsApp) rather than silently missing it (`BUG-SESSION-DUP-RAM`'s
channel-scoping applied to this new cross-request read/write path).

Regression coverage: `tests/test_commercial_completion.py` (`ContinuationRef`
round-trip/never-guesses, `abandon_nested()`), `tests/test_commercial_completion_routing.py`
(`resume_nested()` resumed/mismatch/corrupted branch matrix),
`tests/test_commercial_completion_runtime_integration.py` (full pure-router
lifecycle, both entities, confirm/decline/unrecognized-reply), `tests/test_commercial_v2_mutation_primitives.py`
(`crm_find_or_create_contact`, including a source-inspection assertion that
it never calls a second writer), and the new root-level
`test_diamond_path_approval_continuation.py` exercising
`_resolve_diamond_path_continuation()` itself (no-continuation, nothing-
parked, nonce-mismatch, no-evidence-cleanup, resumed-to-CLARIFY,
resumed-to-TOOL-requeues-parent). PR #1205 merged to `main`
(`9b776631`, 04/09/2026; post-merge symbol verification via `git fetch
origin main` + grep of every changed symbol against `origin/main`,
per this repo's post-merge protocol). `CODE_DONE / STATIC_VERIFIED` —
deployment and production runtime verification remain pending.

### S2C stale-session fresh-command escape — 05/09/2026 (production-reported)

Production incident, reported live by the owner the day after PR #1205
deployed: a stale/abandoned S2C session (parked from an earlier,
unrelated Deal/Organization flow, from before this conversation) force-fed
a brand-new, well-formed command — "צור משימה בדיקת דגימות לייבוא סיבים
בתחום יבוא" — into `CommercialCompletionRouter.answer_human()` as a
literal answer to whatever field it was parked on. The no-match then
triggered DIAMOND PATH's own confirm-to-create offer ("ליצור איש קשר
חדש?"), and because the follow-up reply wasn't כן/לא, `answer_human()`'s
own designed behavior (re-render the identical pending confirm question
on an unrecognized reply) repeated the SAME stale text verbatim on the
next turn too — an inescapable loop, since neither message matched
`_CANCEL_WORDS` either.

Root cause predates DIAMOND PATH: `app.py`'s S2C resume block (`run_agent()`,
section "1.7") runs before `_safe_route()`/create_task routing and
force-feeds ANY non-cancel-word text into the parked session — the
04/09/2026 `S2C completion cancel-escape hatch` entry below only closed
this for an explicit cancel word, not a brand-new command; DIAMOND PATH's
confirm-to-create simply turned the pre-existing trap into a loop with no
escape at all instead of a per-turn dead-end BLOCK.

Fix: generalizes the same escape hatch to a second, precise trigger — a
message that deterministically parses as one of the same structured
commands this exact function already special-cases below it
(`create_task`, `create_deal`, or an S2C completion entity prefix, via the
existing pure parsers `parse_deterministic_create_task`/
`_create_deal`/`_commercial_completion` — the last one existed in
`core/router/router.py` but was never re-exported from
`core/router/__init__.py`, fixed here too) clears the stale completion and
falls through to normal routing the same turn. No heuristic/fuzzy
matching; `update_task`/`complete_task` and the general Agent-routed case
are intentionally left out of scope (no equivalent standalone deterministic
parser without a larger routing refactor). Regression:
`test_bug_s2c_stale_session_fresh_command_escape.py`, driven against the
exact reported message; `test_bug_s2c_cancel_escape.py` (18 assertions)
still passes unchanged. Expanded further the same day into the full
39-assertion acceptance matrix after the owner's own test-case request
caught a SECOND bug in the same area: the confirm-to-create offer's "לא"
decline was being intercepted by this same outer cancel-word check and
cancelling the entire Deal flow instead of just declining the offer (the
router's own narrower, already-correct decline design) — fixed by
excluding `_CREATE_DECLINE_WORDS` from the outer cancel branch while a
nested-create confirm is genuinely pending. PR #1206 merged to `main`
(`8e60cbc6`, 05/09/2026; post-merge symbol verification via `git fetch
origin main` + grep against `origin/main`, per this repo's post-merge
protocol). `CODE_DONE / STATIC_VERIFIED` — deployment and production
runtime verification remain pending.

### CREATE_DEAL optional "בשם" name marker — 05/09/2026 (production-reported)

Production report: "צור עסקה ניהול משרד גיוס בבורסה תחום גיוס" and "פתח
עסקה ניהול משרד בתחום גיוס" — `route_request()` already classified both as
`Intent.CREATE_DEAL` with domain=recruitment at 0.95 confidence, but
`parse_deterministic_create_deal()`'s structured regex required the
literal marker "בשם" before the Deal name in either field order; neither
production message uses it, so the parser never matched at all
(matched=False) and both CLARIFIED with a generic "not sure about the name
or the domain" message — even though the domain was never in question.

Owner directive: fix the extraction CONTRACT, not one more regex variant
for "no בשם." Rewrote `parse_deterministic_create_deal()` from a single
anchored fullmatch regex into an explicit strip-based algorithm: match the
mandatory command prefix, locate and remove the domain clause (`ב?תחום
<word>`, wherever it sits — field order is not fixed), strip an optional
trailing self-ownership suffix and an optional bare "בשם" marker, and
treat whatever text remains as the Deal Name — never a second phrasing-
specific pattern again. A genuinely empty remainder (e.g. "צור עסקה בתחום
יבוא", no name text anywhere) is now a distinct, real state — domain
confidently resolved, name genuinely absent — rather than "unparseable."

`DeterministicDealParse` gained a `domain_resolved` property (matched, not
uncertain, domain present — independent of whether a name was also found)
that both `route_request()`'s CREATE_DEAL gates and app.py's own
create_deal handling now use instead of `certain` (which still requires
both, unchanged, for callers needing the complete pair). Once the domain
is confidently known, Handler.TOOL fires and the Commercial Completion
writer starts with that domain already seeded — a missing Deal Name is
asked for by the writer's own per-field CLARIFY ("מה שם העסקה?") exactly
like any other missing field, never a router-level generic message and
never a repeated domain question. The S2C stale-session escape hatch
above (BUG-S2C-STALE-SESSION-SWALLOWS-NEW-COMMAND) was updated to the same
`domain_resolved` gate for consistency.

Every existing extraction invariant in
`test_bug_crm_bypass_create_deal_deterministic_route.py` (order-
independence, the self-ownership suffix, the named-owner-in-domain guard,
the English-slug identity mapping, the unrecognized-domain fail-closed
path, both live canaries) passes unchanged except the one assertion the
new contract deliberately supersedes (a name-missing message used to
assert "no structural match at all"; it now asserts "domain resolved,
name genuinely missing" instead — updated in place, comment explains why).
New regression: `test_bug_crm_bypass_deal_optional_name_marker.py` (20
assertions) — the exact production strings, the four "בשם"-optional
shapes named in the fix request, the missing-name end-to-end CLARIFY, and
confirmation that the resolved domain is never re-asked. PR #1207 merged
to `main` (`75934532`, `CODE_DONE / STATIC_VERIFIED` — grep-confirmed
against `origin/main`; production runtime verification via a live Render
deploy hash remains outstanding, per this repo's own verification rule).

### DIAMOND PATH CREATE_CONFIRM precedence — 05/09/2026 (production-reported)

Production report (live Telegram transcript + Render logs, owner): a Deal
parked on the counterparty question ("פתח עסקה בשם ניהול משרד בתחום
גיוס" → "מה שם איש הקשר?" → "אבי חזן" → no match → "לא מצאתי את אבי חזן.
ליצור איש קשר חדש?") — replying "כן" (typed, and the inline button, which
sends the same text) got "אין פעולה שממתינה לאישור" instead of beginning
the nested Contact creation.

Root cause, confirmed directly against the production log's own
`deterministic=True` marker: `app.py`'s PR2 fast path
(`_resolve_pr2_deterministic_approval`) intercepts every bare "כן"/"לא"
BEFORE the S2C block ever restores the persisted `commercial_completion`
session — with no live ActionGateway contract to route to, it answers the
canonical "no pending approval" reply. Gated only on
`should_prefer_lead_draft()`, which has zero knowledge of DIAMOND PATH's
own CREATE_CONFIRM state. Existing coverage
(`test_bug_s2c_stale_session_fresh_command_escape.py`) never caught this
because `FEATURE_ACTION_GATEWAY`/`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`
both default off in tests, so that resolver never even ran there —
production has both on.

Fix: `_has_pending_nested_create_confirm()` (`app.py`) — same self-
fetching-Sessions-read pattern `should_prefer_lead_draft()` already uses —
makes the PR2 fast path stand down while a nested-create CREATE_CONFIRM is
genuinely pending (the persisted session's active frame still carries the
`_ux_pending_nested_create` marker), so control falls through to the S2C
block's own already-correct handling instead. Fixes both the typed
fallback and the inline-button path (the "commercial_completion:" callback
namespace already existed and already avoids generic yes/no callback_data —
verified during this investigation, not changed).

Follow-on gap surfaced while testing the fix end-to-end: once "כן" reaches
`begin_nested()`, the next genuinely-missing Contact field (phone) rendered
the generic "נא להשלים את הפרט הבא." fallback — Contact's own fields
(phone/email/company/role_category) were never added to
`commercial_completion_ux.py`'s `_LABELS` when BUG-3-MISSING-PROMPTS fixed
this for Organization/Payment Term/Charge/Payment (contact is DIAMOND-PATH-
nested-only, so it fell outside that pass's `SUPPORTED_COMPLETION_ENTITIES`
scope). Added the four missing entries.

New regression: `test_bug_diamond_create_confirm_precedence.py` — the
exact production scenario for both "כן" (begins nested Contact, pre-filled
name, asks for phone with a real label) and "לא" (declines locally, parent
Deal stays alive, re-asks the counterparty field, never the "❌ הפעולה
בוטלה" full-cancel text), a no-pending-completion control case (PR2's own
generic confirm/cancel handling is unaffected), and the fresh-command-
supersedes-CREATE_CONFIRM case still holding. `CODE_DONE / STATIC_VERIFIED`
— review, merge, deploy, and production runtime verification pending.

### DIAMOND PATH create-contact approval execution + contact search — 05/09/2026 (production-reported)

Production report (live Telegram transcript + Render logs, owner) on the
very next step after the CREATE_CONFIRM fix above: Deal "ניהול משרד 2"
parked on the counterparty question, "אבי חזן" not matched, offer to
create accepted, phone supplied — then:

```
❌ אושר אך נכשל בביצוע
לא הצלחתי להכין תיאור ברור לבקשה הזו. נא לנסח את הבקשה שוב.
הפעולה לא הושלמה
```

The owner diagnosed both root causes directly from the log himself:

**Bug 1 — "הכלי לא נרשם ככותב מורשה"**: the log shows `[ERROR]
action_validator: Unknown tool blocked: crm_find_or_create_contact` even
though the tool is registered in `tool_registry.py` and wired into
`tools/dispatcher.py`'s dispatch switch — ActionGateway approves the
contract, the atomic executor claims it, and `dispatch_tool()` then blocks
it anyway because `action_validator.py`'s own independent `_REQUIRED`
allowlist (checked before either of those) was never updated when
`crm_find_or_create_contact` was added, so an *approved* action could never
execute. Fix: added `"crm_find_or_create_contact": ["name"]` to
`_REQUIRED` and to `_SENSITIVE_TOOLS`, matching
`crm_find_or_create_organization`'s existing entry exactly.

**Bug 2 — "המערכת לא באמת מחפשת באנשי קשר אלא רק 7 הראשונים"**: the log's
own `GET .../Contacts?maxRecords=7&fields[]=שם` call shows
`commercial_crm.lookup_human_reference()` never sent the query text to
Airtable at all — for an internal/owner identity
`tools.airtable_security.enforce_tenant_scope()` applies no filter, so the
call fetched only the first `limit + 1` (= 7) records in default table
order and matched the query client-side; a real contact anywhere past
those first rows was invisible no matter how exact the name match was.
Fix: build a `SEARCH()` pre-filter formula (escaped via the sanctioned
`tools.airtable_gateway.escape_formula_value()`, confirmed by
`tools/audit_formula_escaping_boundary.py` reporting zero new violations)
from the query and pass it through `enforce_tenant_scope()` the same way
every other call site's filter is combined — AND'd with tenant/domain
scope, never replacing it — so the actual query now constrains what
Airtable returns; the existing client-side casefold/whitespace-normalized
exact match remains the authoritative disambiguator, unchanged. A blank/
whitespace-only query now fails closed to no results instead of risking an
unfiltered scan.

Note: `commercial_crm.lookup_human_reference()`'s "an internal owner sees
no formula at all" behavior was itself asserted by name in an existing
test (`test_lookup_human_reference_owner_sees_matching_record`) — that
assertion encoded this exact bug and was corrected as part of this fix to
assert the query is present in the formula instead.

New regression: `test_bug_diamond_contact_approval_and_search.py` (9
assertions) — `crm_find_or_create_contact` allowed/presence-checked (not
"unknown tool"); a simulated 10-Contact table where the target sits past
the first 7 default-order rows is still found via the SEARCH() formula;
blank query fails closed. `CODE_DONE / STATIC_VERIFIED` — review, merge,
deploy, and production runtime verification pending.

### S2C completion cancel-escape hatch — 04/09/2026 (production-reported)

Production incident, reported live by the owner immediately after PR #1201
deployed: a stale/abandoned Commercial Completion session parked mid-flow
(e.g. a "who is this deal with?" prompt the owner never answered) silently
swallowed every subsequent message forever, including brand-new, unrelated
commands like "צור עסקה בשם ...". `app.py`'s S2C resume block
unconditionally fed `user_text` into `CommercialCompletionRouter.
answer_human()` as a literal answer to whatever field was pending, with no
check for a cancel word and no way for a fresh command to be recognized as
one — the owner was stuck getting "לא מצאתי התאמה; נא לנסות שם אחר." on
every message, including the standard `_CANCEL_WORDS` (בטל/ביטול/לא/...)
that every other confirm/cancel surface in the file already honors. Fixed
by checking `_CANCEL_WORDS` first, before any `restore()`/`answer_human()`
call, and clearing the persisted session with an explicit cancellation
reply when matched. Regression test: `test_bug_s2c_cancel_escape.py`
(18 assertions: 4 cancel words each verified to clear the session, never
reach `answer_human()`, and reply explicitly; one sanity case confirming a
normal in-flow answer is unaffected). This bug pre-dates PR #1201 — the S2C
resume block itself was not touched by that PR — but lives in the same
subsystem and was only surfaced by the owner's post-deploy runtime
verification of it. PR #1202 merged to `main` (`e56570e6`, 04/09/2026);
deployment and runtime verification remain pending.

### Session canonicalization — 04/09/2026 (owner-directed, production audit)

The S2C incident above led to a wider audit: production's Sessions table had
18 rows for one Sender ID (`7228089151`). Confirmed via direct read of the
live table: 17 are historical debris (created 2026-06-25 to 2026-07-04,
never touched since — the current write-path dedup, from prior fixes
BUG-106/BUG-NEW-12, already stops new duplicates for the common case). One
real, still-live gap found: 17 of the 18 are `Channel=whatsapp`, but one is
`Channel=telegram` — the same raw Sender ID string used on both channels,
and the live dedup lookup was Sender-ID-only with **no channel scoping**, so
a WhatsApp and Telegram identity sharing a raw ID string were treated as the
same session. `SessionsFields.SESSION_ID` ("Session ID") was also found to
be schema-defined but never written or read by any code.

Owner-decided fix, implemented in `session_store.py`:
`_canonical_session_key()` composes the deterministic `tenant:channel:sender`
key (tenant defaults to the constant `"boss_hq"` — single-tenant today, F08
multi-tenancy will thread a real value through later) and is now stamped
into `SessionsFields.SESSION_ID` on every create/update. `get_or_create()`
never reuses a same-sender session on a different channel (cross-channel
isolation at the one place `channel` is actually known). `_sync_to_db()` /
`_find_best_session_in_db()` scope the Airtable lookup formula by
`AND(Sender ID, Channel)` when channel is known, falling back to the
original Sender-ID-only formula for legacy callers/rows (deterministic
fallback, no migration required — a legacy row without `Session ID` still
resolves correctly and heals forward the next time anything writes to it).
Both the write-path and read-path duplicate-selection points now log a
distinct, greppable `SESSION_DUPLICATE_DETECTED` signal (with
`cross_channel=True/False`) instead of a plain info/warning line, so
recurrence is visible rather than silently resolved forever — this is
detection/visibility, not an automated repair job; no such job exists to
hook into safely without inventing new infrastructure, which was out of
this fix's scope.

Original scope boundary here claimed the in-process RAM cache staying keyed
by bare `sender` (not the composite key) was safe because "the DB layer —
the thing that actually accumulates duplicate rows and survives restarts —
is fully channel-scoped regardless of any RAM-layer edge case." **That
claim did not hold and is superseded the same day — see "RAM cache
cross-channel isolation follow-up" below**: a WhatsApp and Telegram request
sharing a raw sender-id string could still read/mutate each other's live
session object in RAM before either write ever reached the (correctly
DB-scoped) Sessions row — a scoped DB write does not help if the state it
persists was already cross-channel contaminated in RAM first.

Regression pack: `test_bug_session_dup_canonicalization.py` (14 tests —
canonical key determinism, 0/1/>1-match write behavior, cross-channel
isolation at both the DB-lookup and `get_or_create()` layers, the
greppable duplicate-detected log signal, stale-duplicate-cannot-win,
legacy-row-without-Session-ID still resolves and heals forward, repeated
writes / simulated restart / simulated concurrent writes never create a
second row, and `commercial_completion` surviving a normal resume /
being cleanly replaced by a new explicit one). Existing suites re-verified
unaffected: `session_store.py`'s own 54 self-tests, `test_bug106_session_
determinism.py` (7), `test_session_store_contract.py` (17 of 18 — the 18th,
`test_raw_records_reader_follows_airtable_pagination`, fails identically on
`origin/main` before this change; confirmed pre-existing and unrelated),
`test_bug_s2c_cancel_escape.py` (18), the `tests/` pytest pack (127), and
`smoke_tests.py`. `tools/audit_dispatcher_bypass.py`'s baseline line numbers
for `session_store.py`'s 4 pre-existing `tools.airtable_tools` imports were
updated to match this change's line shift (same imports, same precedent as
the prior S2C-era shift already recorded in that file).

**One-time cleanup of the 17 stale duplicate rows for sender
`7228089151`** and **a separate, read-only audit of a much larger
(492-row) Sessions table pollution pattern** (`bug111_*`/`chat_t2_*`/
`boss_hq:*` Sender IDs matching automated test-script output, apparently
written to the production base directly) are tracked and executed
separately per explicit owner decision — see the follow-up entries below.
Merge, deployment, and runtime verification of this canonicalization fix
remain pending.

### RAM cache cross-channel isolation follow-up — 04/09/2026 (PR #1203 review)

Review of PR #1203 (session canonicalization, above) required proving the
in-process RAM cache had the same channel isolation as the DB layer before
merge, not documenting it as a deferred edge case. Reproduced directly:
`PersistentSessionStore._store` was keyed by bare `sender`, so a WhatsApp
and a Telegram identity sharing a raw sender-id string (the same production
shape as the 18-duplicate-row incident) could overwrite each other's RAM
slot — a request on one channel could read or mutate the OTHER channel's
live session object before the (correctly DB-scoped) write ever happened.

Fix, in `session_store.py`: the RAM key now uses the same canonical shape
as persistence — `_ram_key()` builds `_canonical_session_key(channel,
sender)` whenever `channel` is known, resolved with a three-tier
precedence (explicit argument → the current request's channel → the
pre-existing implicit default `"whatsapp"` as the last resort, matching
what this store's public API already defaulted to everywhere before this
fix). `get_or_create()` (which already received `channel` explicitly)
switched its own default from a hardcoded `"whatsapp"` to this same
resolution, closing a related pre-existing gap where any lazy-create call
site that omitted `channel` (most of them) mislabeled a brand-new
Telegram-only sender's session as `channel="whatsapp"` from creation.

Threading an explicit `channel` parameter through every one of this
store's ~20 public methods and their ~60 call sites across `app.py` and
`core/lead_candidate_handler.py` was considered and rejected as
disproportionate — reviewed and confirmed instead that every real call
site already runs downstream of exactly one channel-aware choke point per
request (`run_agent()`, or a channel-fixed entry like the Telegram
callback-query dispatcher / `cmd_decision.py`'s registered handlers, which
never receive WhatsApp traffic, or `furniture_lead_funnel.py`, which is
WhatsApp-only by its own module contract). `session_store.set_request_channel()`
— a `contextvars.ContextVar`, thread-scoped so a reused worker thread never
sees another thread's concurrent request — is now stamped once at each of
those choke points (`run_agent()`, `_webhook_telegram_impl`,
`_webhook_whatsapp_impl`, `webhook_meta_whatsapp` in `app.py`) and every
method that only ever received `sender` reads it back transparently; zero
change to any of the ~60 call sites' signatures or call shape. `get_all_active()`
and LRU eviction sync were also fixed to recover the raw sender from the
now-composite key rather than leaking it (as `"boss_hq:whatsapp:<sender>"`)
into `interaction_engine.py` or writing it verbatim into `SF.SENDER_ID`.
`_load_from_db()` (the RAM-cache-miss/cold-restart DB fallback) also
gained the same optional channel scoping `_find_best_session_in_db()`
already had, so a cold cache never restores the wrong channel's row for a
cross-channel-shared sender-id either.

Regression pack: `test_bug_session_dup_ram_isolation.py` (6 tests) —
the exact required sequence (create Telegram session, create WhatsApp
session for the same sender, mutate Telegram `commercial_completion`,
assert WhatsApp unchanged, mutate WhatsApp state, assert Telegram
unchanged, assert both DB writes carry their own `Session ID`), the same
sequence in reverse creation order, `get()`/`get_or_create()` read-path
isolation and object-identity checks, and the no-request-context fallback
(proving `get_or_create()` and a later context-free `get()`/
`get_commercial_completion()` resolve to the identical RAM slot — the
literal regression this fix's first draft introduced and this suite
caught before merge, fixed by making `"whatsapp"` the consistent
last-resort default everywhere instead of only in `get_or_create()`).
Existing suites re-verified unaffected: `session_store.py`'s own 54
self-tests, `test_bug_session_dup_canonicalization.py` (14),
`test_bug_s2c_cancel_escape.py` (18), `smoke_tests.py`, `test_integration.py`,
and the `tests/` pytest pack (127). `tools/audit_dispatcher_bypass.py`'s
baseline line numbers for `session_store.py`'s 4 pre-existing
`tools.airtable_tools` imports were updated again to match this change's
line shift (same imports, same precedent as the prior two shifts already
recorded in that file). Merge, deployment, and runtime verification remain
pending — this is `DIAMOND_PATH_STATIC_HARDENED`, not `RUNTIME_VERIFIED`.

### Create-Deal domain-prefix parsing gap — 04/09/2026 (production-reported)

Production logs, pasted by the owner: two real attempts to open a Deal —
`"צור עסקה בשם הבאת דוגמאות מסין תחום ייבוא"` and `"פתח עסקה בשם רכישת סיבים
וקונקטורים תחום ייבוא"` — both got the same generic CLARIFY reply ("לא בטוח
שהבנתי את שם העסקה או את התחום..."), with no way to retype into something
that would work.

Root cause: `core/router/router.py`'s `_STRUCTURED_CREATE_DEAL_RE` required
the ב-prefix on "בתחום" (`"...שם X בתחום Y"`); the owner's own natural
phrasing omits it (`"...שם X תחום Y"`, no ב). The regex simply didn't match
(`matched=False`) — confirmed by direct reproduction with the exact
production strings before making any change. Per the router's own
BUG-CRM-BYPASS-DEAL-AGENT-FALLTHROUGH design (any non-certain
`Intent.CREATE_DEAL` parse — matched or not — must CLARIFY, never fall
through to `Handler.AGENT`), this is fail-safe rather than fail-silent, but
the CLARIFY message itself only offers the "בתחום" form the owner had
already (unknowingly) rejected, so the two attempts looped identically.

Fix: `_STRUCTURED_CREATE_DEAL_RE` now accepts `ב?תחום` — both "בתחום" and
bare "תחום" — in both name-then-domain and domain-then-name orderings.
Does not reopen BUG-CRM-BYPASS-DEAL-AGENT-FALLTHROUGH's own canary #7 (the
English word "domain" instead of the Hebrew word) — that phrasing still
fails to match and CLARIFIES; only the Hebrew word's optional ב-prefix
changed.

Regression pack: `test_bug_crm_bypass_create_deal_deterministic_route.py`
gained "canary #8" — both exact production strings now parse `.certain`
with the correct name/domain and route to `Handler.TOOL`, plus an explicit
re-check that canary #7 (the English-word case) is unaffected. Existing
suites re-verified unaffected: the file's own full run (all prior
assertions, including canaries #1–#7), `test_lead_to_deal_origin_link.py`,
`test_bug_crm_deal_duplicate_approval_reply.py`, `core/router/test_router.py`
(54/54), `smoke_tests.py`, the `tests/` pytest pack (127). Every governance
audit (gateway/provider/model-call/dispatcher/turn-coordinator/
writer-authority/renderer-contract/formula-escaping bypass) re-run clean,
`new=0` throughout — this change touches only a regex literal and its test
file, no new import/call-site surface. Merge, deployment, and runtime
verification remain pending.

### N18 shared field metadata reconciliation — 04/09/2026

`core/draft_fields.py` provides the provider-neutral `FieldMetadata` shape and
atomic field operations. The implementation is isolated in PR #1198, pending
merge; Commercial UX consumes the metadata shape in PR #1196 while retaining
ownership of commercial labels, link resolution, and choice semantics.
