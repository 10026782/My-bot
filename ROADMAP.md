# BOSS Bot — ROADMAP

עודכן: 04/09/2026

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
that approval executes; see PR #1201 for the tradeoff. Merge, deployment, and
runtime verification remain pending.

### N18 shared field metadata reconciliation — 04/09/2026

`core/draft_fields.py` provides the provider-neutral `FieldMetadata` shape and
atomic field operations. The implementation is isolated in PR #1198, pending
merge; Commercial UX consumes the metadata shape in PR #1196 while retaining
ownership of commercial labels, link resolution, and choice semantics.
