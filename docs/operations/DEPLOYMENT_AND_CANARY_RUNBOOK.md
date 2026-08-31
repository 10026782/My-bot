# Deployment & Canary Runbook — generated from the Master Verification Matrix

**Source:** `docs/operations/MASTER_VERIFICATION_MATRIX.md` (31/08/2026). **Truth Reset SHA:** `origin/main` = `5387c909818d80af667d439e297e1f255508b610`. **Type:** execution sequence for the next deployment window, derived directly from the matrix's per-capability "Canary Required"/"Runtime Evidence Required" columns.

**Relationship to `docs/operations/RUNTIME_VERIFICATION_MASTER_RUNBOOK.md`:** that document is the existing flag-sequenced canary runbook and remains authoritative for every step it already defines (§A–§F, cited by ID below). This document does not re-derive those steps — it **orders them by capability** (so "what do I do about Leads today" reads as one block instead of being split across flag-named sections) and adds the canaries/tests the matrix found **missing from both existing runbooks entirely** (marked **NEW** below). Where the two documents overlap, the older one's GO/STOP/rollback criteria are the ones that apply.

**Ground rule inherited from CLAUDE.md's own "כלל ברזל" (unchanged):** no step below may be marked done from a code default or a merged PR. "GO" requires the evidence listed, observed live. **This runbook authorizes nothing by itself** — every activation still requires the owner decision its governing program (ROADMAP.md/HORIZON.md) already calls for.

**Explicit non-goal, per the audit that produced this document:** none of the test/CI gaps logged in the matrix (§0.2 false-pass tests, Knowledge's zero coverage, the Tasks tenant-scoping gap, etc.) are fixed here. They are sequenced as **Phase 4** items for a deliberate follow-up decision, not silently patched.

---

## Phase 0 — Pre-flight read-only checks (no risk, ~15 min)

Do these first, every time. Identical to `RUNTIME_VERIFICATION_MASTER_RUNBOOK.md` §A1–A5 — cited, not repeated:

- **A1** Confirm Google OAuth env vars (frozen vs. live discrepancy between CLAUDE.md and `ORACLE_MIGRATION_M0.md`).
- **A2** Confirm `FEATURE_ATOMIC_CLAIMS`/`DATABASE_URL` current live values.
- **A3** Confirm `/health` is not wired as Render's platform health check (documented either way).
- **A4** Pull current Telegram `getWebhookInfo` — matches expected URL, no pending backlog.
- **A5** One real Airtable metadata read via `/health` — `airtable: ok`.

**STOP condition for the whole day:** A5 fails → do not proceed past Phase 0.

---

## Phase 1 — Zero-risk shadow canaries (~1 day of passive observation each)

These require no user-facing change. Run them in parallel; they don't depend on each other except where noted.

| Capability (matrix §) | Flag/config | Canary | Evidence | GO | STOP |
|---|---|---|---|---|---|
| Schema/data contract (§2.23) | `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=shadow` | Ordinary Airtable writes across 2-3 tables | Discrepancy log, provider vs. `schema_validator` | Zero/explainable discrepancies over a full day | Any unexplained mismatch on a `TABLE_CLASS_MAP` table |
| Schema/data contract (§2.23) | `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE=shadow` (after the row above is clean, only on tables reporting `mode="full"`) | Same write flow, watch invalid-select-value warnings | Log output | Zero unexpected invalid-value logs on live tables | Any select field structurally mismatched |
| RP5 (§2.10) | `FEATURE_EVIDENCE_FINALIZER=shadow` | Normal agent tool-use traffic, one day | Shadow comparison logs (claim-authorization vs. evidence-derived status) | Comparison agrees on the large majority of turns, disagreements individually explainable | Systematic disagreement |
| F52 (§2.8) | `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` | Normal approval-flow traffic | Side-by-side legacy vs. unified text logs | Unified output matches legacy semantics | Unified output drops information legacy carried |
| Memory (§2.19) | `FEATURE_MEMORY_SHADOW_LOGGING` (already presumed on) | One day of scheduler cycles | `core/memory_retrieval_shadow.py` comparison counts | Counts accumulate without error | Job errors or never fires |

Full detail: `RUNTIME_VERIFICATION_MASTER_RUNBOOK.md` §B1–B5.

---

## Phase 2 — Business-write canaries, ordered by matrix dependency (real writes, small blast radius, reversible)

Run in this order — later rows assume owner approval on earlier ones where the capability is related.

1. **Lead creation — WhatsApp (§2.1)**: owner approval (ROADMAP N18) → `WHATSAPP_CANONICAL_LEAD_WRITE=true` for one non-furniture WhatsApp number → send one real test inbound message → confirm new Lead record via `core.whatsapp_lead_cutover.create_whatsapp_inbound_lead`, correct Owner via `core/source_owner_mapping.py`, no duplicate. Rollback: flag back to false.
2. **Lead creation / Voice (§2.1, §2.16)**: requires step 1's GO plus a **separate** owner approval (this touches a live-bypass path with no current safety net) → `VOICE_CANONICAL_LEAD_WRITE=true` → one real test call through the IVR to completion → confirm `create_voice_inbound_lead()` ran (not the legacy `airtable_add()` bypass), Owner resolved correctly. Rollback: flag back to false — legacy bypass resumes, zero-risk since that's already current production behavior.
3. **Deals / Payments / Finance (§2.3, §2.4, §2.21)**: owner decision to register `commercial_crm.py`'s 3 tools (`create_deal`/`create_payment`/`create_payment_term`) in `tool_registry.py`+`tools/dispatcher.py`+`tools/schemas.py`, `requires_approval=True`, `tenant_scoped=True` → one real test Deal + Payment Term via the agent, owner-approved → confirm Airtable records match the VAT/calculation contract, no orphaned raw writes bypassing it. Rollback: remove the registry/dispatcher/schema entries — no data migration needed, since nothing wrote through them before.
4. **Decision Hub (§2.12)**: `FEATURE_DECISION_HUB=true` for owner-only testing → one real `/decision new` → `/decision status` cycle → confirm full lifecycle completes via the correct storage adapter. Rollback: flag back to false. *(The Contacts adapter this depends on is confirmed already fixed on `main` — see matrix §0.3/§2.2, no separate contact-adapter canary needed.)*
5. **Marketing (§2.20)**: `FEATURE_MARKETING_BRIDGE=true` for owner-only testing → one real `/marketing_new` wizard run to `record_publication()` → confirm records across `MARKETING_DEMAND`/`MARKETING_CREATIVES`/`MARKETING_PUBLICATIONS`, no orphaned partial state. Rollback: flag back to false.
6. **Media (§2.11)** — recommended addition, not in the older runbook: before any flag flip, note that **zero tests cover the flag-ON path** for either `FEATURE_VOICE_NOTES` or `FEATURE_MEDIA_UPLOAD`. When an owner decides to activate: one real Telegram voice-note and one real photo upload against the flipped flag, specifically to catch a live-wiring regression no test would catch first.

Full detail for items 1-5: `RUNTIME_VERIFICATION_MASTER_RUNBOOK.md` §C1–C5.

---

## Phase 3 — Enforcement flips (state transitions with real blocking behavior — only after Phase 1/2 rows they depend on are clean)

| Change | Precondition | GO | STOP | Rollback |
|---|---|---|---|---|
| ActionGateway (§2.7) `FEATURE_ACTION_GATEWAY=true` | Phase 2 stable ≥1 week; understand the Gateway already runs unconditionally for dedup + 6 other callers today (§0's cross-cutting note) — this flag only changes the *general agent* path's strength | One real high-risk tool call correctly blocked/approved end-to-end | Any legitimate approval incorrectly blocked | Flag back to false |
| Approval (§2.6) `FEATURE_PA01_ENFORCEMENT_STATE`: shadow→enforce | A full day of shadow `would_block` logs reviewed, acceptable false-positive rate | Live enforce run produces no unexpected `final_reply` overwrites on legitimate turns | Any legitimate success reply gets replaced | Set back to shadow |
| RP5 (§2.10) `FEATURE_EVIDENCE_FINALIZER`: shadow→enforce | Phase 1's shadow row shows sustained agreement | Same GO/STOP as Phase 1's shadow row, at enforce strength | Systematic disagreement | Set back to shadow |
| F52 (§2.8) `FEATURE_UNIFIED_STATUS_FORMATTER`: shadow→on | Phase 1's shadow row shows sustained parity | Unified formatter output sent with no meaning divergence | Any meaning divergence found | Set back to shadow |

Full detail: `RUNTIME_VERIFICATION_MASTER_RUNBOOK.md` §E1–E3.

---

## Phase 4 — Logged gaps needing a decision before any canary is possible (NEW — from this audit, not in either prior runbook)

None of these are fixed here. Each needs an owner/engineering decision on whether and how to close it before a canary makes sense.

| Capability (matrix §) | Gap | Why it can't canary yet | Suggested first step |
|---|---|---|---|
| Tasks (§2.5) | `Tasks` table absent from dispatcher's `_TENANT_AWARE` set — zero test coverage of the gap | No tenant scoping exists to canary | Owner decision: add `"Tasks"` to `_TENANT_AWARE`, then write the missing test, then canary a real cross-tenant Task write |
| Turn Coordinator (§2.9) | No test — including TC10 — exercises the real Postgres `TurnStateRepository` under concurrent dual-channel (Telegram + TMA) writes | Real-DB seam is currently proven only via a monkeypatched repository class | Write the missing concurrent-dual-channel test against the CI Postgres service first; only then consider a live concurrency canary |
| Authentication/authorization (§2.22) | No test calls the real `enforce_tenant_scope()` and asserts a `TenantScopeViolation` — every test mocks it away | Can't canary a hard-fail path with zero direct unit coverage | Write a direct unit test against the real function first (two identities, mismatched `tenant_id`, assert the exception) — ties to the still-open C06-F5 finding |
| Finance / cost_watchdog (§2.21) | `cost_monitor.py::check_thresholds()`'s actual comparison (`daily > COST_DAILY_LIMIT`) is never exercised — only the trigger function, called directly with a hardcoded value | Can't be sure a real breach would even reach the trigger | Write a test that drives `check_thresholds()` itself past a real (test) limit before canarying a real breach simulation |
| Scheduler (§2.17) | No test asserts `.at()` schedule times — the two known Sunday collisions (`audience_report`/`weekly_quest_reset` both 08:00; `weekly_summary`/`attribution_report` both 08:30) are invisible to CI | Not a flag — this is a code fix (retime one job), and there's no regression test to prove it stays fixed | Retime one job in each pair (already an explicit open item in the older runbook's cross-cutting notes) and add a schedule-collision assertion so it can't silently recur |
| Knowledge (§2.18) | Zero dedicated tests exist for `core_knowledge.py`/`domain_prompts.py` content assembly | Nothing to regress-test against | Write a first content-assembly test (role+domain → expected manifest sections/prompt variant) before treating any future prompt change as low-risk |
| Approval / ActionGateway (§2.6, §2.7) | `test_phase_4b0_1c_concurrent_approvals.py` and `test_phase_4b0_1b_concurrency.py` use non-raising `chk()` helpers inside real `def test_` functions — structurally cannot fail CI | This is a CI-signal integrity gap, not a canary gap | Convert the `chk()` calls to real `assert`s (or route both files through TC10-style real assertions) — separate engineering ticket, not part of this deployment window |

**Structurally non-canary-able regardless of decision** (per the older runbook's own cross-cutting notes, reconfirmed here): `EMAIL_INBOUND` and `ABANDONED_LEADS` are hard-blocked until `send_email_reply`/`send_bounce` exist as registered dispatcher tools — that's new feature work. `META_OUTBOUND_ENABLED` cannot produce any observable outbound change — no send path exists in the repo at all.

---

## Phase 5 — Legacy retirement (only after the corresponding canonical path has sustained proof)

Unchanged from `RUNTIME_VERIFICATION_MASTER_RUNBOOK.md` §F — cited, not repeated: F1 (`voice_adapter.py`'s direct bypass), F2 (`_ALIAS_MAP` `Payments` re-check), F3 (old `crm.py` Deal/Payment functions), F4 (`core/reasoning_ports.py::_ProductionContacts.find_or_create()` fix — **note: this item is already done**, see matrix §0.3/§2.2; the older runbook's F4 row predates the fix and should be marked closed in that document on its next edit, not here).

---

## Quick-reference: what "done" requires today

Per CLAUDE.md's Hebrew "כלל ברזל," no row above may be marked ✅ without, in order: `git log -1 --oneline` (commit exists locally), actual `git push` output (not just commit), Render deploy-hash match against `origin/main` if the change is deploy-dependent, and current flag state in Render env if flag-relevant. This runbook sequences *which* evidence to collect and *when* — it does not substitute for producing it.

## What this runbook deliberately does not do

- Fix any of the Phase 4 test/CI gaps — they are logged and sequenced for a decision, per this audit's scope.
- Authorize any flag flip by itself — every GO above still requires the owner decision its governing program already calls for.
- Re-verify anything the matrix already marked STATIC VERIFIED without new evidence — this is a sequencing tool over already-established facts, not a re-audit.
