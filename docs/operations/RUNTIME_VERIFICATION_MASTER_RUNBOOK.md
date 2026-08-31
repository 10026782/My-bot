# Runtime Verification Master Runbook

**Companion to:** `docs/architecture/CURRENT_SYSTEM_EXECUTION_MAP.md` (the execution map this runbook sequences against). **Truth Reset SHA:** `origin/main` = `894320409a67df992afedeb70aae8e76fdfd00d1` (01/09/2026).

**Purpose:** an ordered, dependency-aware runtime verification sequence for the next deployment window, derived from the execution map's feature-flag dependency chains and current runtime-evidence gaps. This is a sequencing tool, not a new authorization — every activation below still requires the owner decision its governing program (ROADMAP.md/HORIZON.md) already calls for. Nothing in this document changes a flag, deploys anything, or grants an activation by itself.

**Ground rule inherited from CLAUDE.md's own "כלל ברזל":** no step below may be marked done from a code default or a merged PR. "GO" for any step requires the evidence listed in that step, observed live, not inferred from tests.

---

## A — Safe read-only / live verification (no flag changes, no risk)

These confirm facts this audit could not check without live access, and resolve the two open contradictions from the execution map (§10, items 7 and 10-adjacent Render-state questions).

| Step | Action | Evidence to capture | GO criteria | STOP criteria |
|---|---|---|---|---|
| A1 | ~~Confirm current Render env: `GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN` set or unset~~ — **RESOLVED 31/08/2026 (owner confirmation)**: Google Workspace was frozen, then unfrozen; `ORACLE_MIGRATION_M0.md` ("live") is current, CLAUDE.md/`ARCHITECTURE_DRIFT_MAP.md`'s "frozen" notes were stale and have been updated | Owner statement (chat) | Resolved | N/A — read-only |
| A2 | Confirm `FEATURE_ATOMIC_CLAIMS` and `DATABASE_URL` current live values on Render | Render env export | Matches or corrects `ORACLE_MIGRATION_M0.md`'s 28/08/2026 snapshot | N/A |
| A3 | Confirm `/health` route is (still) not wired as Render's platform health check | Render service settings screenshot | Documented either way in `DEPLOYMENT.md` | N/A |
| A4 | Pull current `GET /telegram` webhook info (`getWebhookInfo`) to confirm the live webhook URL/secret match this deploy | Telegram API response | Matches expected URL, no pending update backlog | Backlog present → investigate before touching anything else |
| A5 | One real Airtable metadata read via `health_monitor.py`'s own check path (already wired to `/health`) | `/health` response body | `airtable: ok` | `airtable: degraded/error` → do not proceed past step A |

## B — Low-risk canaries (shadow/off-path observation only, zero user-facing change)

| Step | Preconditions | Flag/config | Canary | Evidence | GO | STOP | Rollback |
|---|---|---|---|---|---|---|---|
| B1 | A1-A5 clean | `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=shadow` | Trigger a handful of ordinary Airtable writes across 2-3 tables | Discrepancy log between provider and `schema_validator` | Zero or explainable discrepancies over a full day | Any unexplained mismatch on a table already in `TABLE_CLASS_MAP` | Unset the flag (defaults to off) |
| B2 | B1 GO | `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE=shadow` (only meaningful on tables where B1 reports `mode="full"`) | Same ordinary write flow, watch for logged invalid-select-value warnings | Log output | Zero unexpected invalid-value logs on live-traffic tables | Any select field structurally mismatched | Unset the flag |
| B3 | none | `FEATURE_EVIDENCE_FINALIZER=shadow` | Normal agent tool-use traffic for one day | Shadow comparison logs (claim-authorization vs evidence-derived status) | Comparison agrees on the large majority of turns; any disagreement is individually explainable | Systematic disagreement (would suggest RP5 enforce would break real replies) | Unset the flag |
| B4 | none | `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` | Normal approval-flow traffic | Side-by-side legacy vs unified text logs | Unified output matches legacy semantics (wording differences acceptable, meaning must not diverge) | Unified output drops information the legacy text carried | Unset the flag |
| B5 | none | `FEATURE_MEMORY_SHADOW_LOGGING` (already presumed on per ROADMAP context; if not, turn on) | One day of scheduler cycles | `core/memory_retrieval_shadow.py` comparison counts | Counts accumulate without error | Job errors or never fires | Unset |

## C — Canonical business-write canaries (real writes, small blast radius, reversible)

These specifically target the execution map's biggest gap: the canonical write path exists in code but is unreachable at default flags, or exists in parallel with a still-live legacy path.

| Step | Preconditions | Flag/config | Canary | Evidence | GO | STOP | Rollback |
|---|---|---|---|---|---|---|---|
| C1 | Owner approval (per ROADMAP N18 "remaining work") | `WHATSAPP_CANONICAL_LEAD_WRITE=true` for one non-furniture WhatsApp number only | Send one real test inbound WhatsApp message from that number | New Lead record created via `core.whatsapp_lead_cutover.create_whatsapp_inbound_lead`, Owner correctly resolved via `core/source_owner_mapping.py` | Record correct, Owner correct, no duplicate | Missing/duplicate lead, wrong Owner | Set flag back to false |
| C2 | C1 GO, separate owner approval (Voice canonical write touches a live-bypass path with no current safety net) | `VOICE_CANONICAL_LEAD_WRITE=true` | One real test call through the IVR to completion | Lead created via `create_voice_inbound_lead()` instead of the legacy `airtable_add()` bypass; Owner resolved | Record correct, Owner correct | Any regression vs the legacy path's current (admittedly worse) behavior | Set flag back to false — legacy bypass resumes, which is the current production behavior, so rollback is zero-risk |
| C3 | Owner-approved canary for the 3 commercial_crm.py tools now wired by PR1153 (`crm_create_deal`, `crm_create_payment_term`, `crm_create_payment`) | Execute one test Deal + Payment Term through the registered tools with `requires_approval=True`, `tenant_scoped=True`, emergency-stop policy | One real test Deal + Payment Term via the agent, owner-approved | Airtable records match the VAT/calculation contract and evidence/tenant policy | Contract math correct; ownership against generic raw `airtable_add`/`airtable_update` is explicit | Calculation mismatch, missing evidence, or raw bypass remains the accepted path | Disable the three registry/dispatcher/schema entries; no migration expected for pre-existing records |
| C4 | None (already merged/gated) | `FEATURE_DECISION_HUB=true` for owner-only testing | One real `/decision new` → `/decision status` cycle | Record in Decisions table, correct storage adapter path | Full lifecycle completes | Any write failure or missing storage | Set flag back to false |
| C5 | None | `FEATURE_MARKETING_BRIDGE=true` for owner-only testing | One real `/marketing_new` wizard run to `record_publication()` | Records across `MARKETING_DEMAND`/`MARKETING_CREATIVES`/`MARKETING_PUBLICATIONS` | Full lifecycle completes, no orphaned partial state | Any stage fails silently | Set flag back to false |

## D — Feature-flag activations (broader rollout after C canaries are clean)

Sequenced per the execution map's §3 dependency chains — do not activate a dependent flag before its prerequisite has a GO from section C above.

1. `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE`: shadow → enforce (only after B1 is clean for an extended period, per-table if needed).
2. `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE`: shadow → enforce (only after step 1 is in `enforce` for the same table).
3. `WHATSAPP_CANONICAL_LEAD_WRITE`: broaden from the C1 single-number canary to all non-furniture WhatsApp numbers.
4. `VOICE_CANONICAL_LEAD_WRITE`: broaden from the C2 single-call canary to all IVR traffic.
5. `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` → then `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` (second is a no-op without the first, per `feature_flags.py`'s own special-case).
6. `FEATURE_EVIDENCE_FINALIZER`: shadow → enforce (only after B3 shows sustained agreement).
7. `FEATURE_UNIFIED_STATUS_FORMATTER`: shadow → on (only after B4 shows sustained parity).
8. `FEATURE_DECISION_HUB`, `FEATURE_MARKETING_BRIDGE`, `FEATURE_MEDIA_UPLOAD`/`FEATURE_VOICE_NOTES`: each independent, activate per its own owner decision — no cross-dependency with the chains above.

## E — Enforcement changes (state transitions with real blocking behavior)

| Step | Change | Precondition | GO criteria | STOP criteria | Rollback |
|---|---|---|---|---|---|
| E1 | `FEATURE_ACTION_GATEWAY=true` (general-agent tool-use approval path becomes blocking, not shadow) | D-phase flags stable for at least one week; §10 finding #1 understood by whoever flips this — the Gateway is already exercising 6+ other unconditional callers today, so this flag only changes the *general agent* path's strength | One real high-risk tool call correctly blocked/approved end-to-end through the now-enforcing Gateway | Any legitimate approval incorrectly blocked | Set back to false |
| E2 | `FEATURE_PA01_ENFORCEMENT_STATE`: shadow → enforce | A full day of shadow `would_block` logs reviewed, false-positive rate acceptable | Live enforce run produces no unexpected `final_reply` overwrites on legitimate turns | Any legitimate success reply gets replaced | Set back to shadow |
| E3 | `FEATURE_ACTION_CONTRACT_PERSISTENCE=true` (if not already, pending A2's finding) | A2 confirms current state; if off, requires a durable ledger migration decision | Durable proposal/recovery lookups work across a process restart | Any lookup failure post-restart | Set back to false (accepting RAM-only ledger loses history on restart, not data corruption) |

## F — Legacy retirement (only after the corresponding canonical path has sustained proof)

| Step | Retire | Precondition |
|---|---|---|
| F1 | `voice_adapter.py::_save_voice_lead()`'s direct `airtable_add()` bypass | C2 canary GO + D4 broad rollout GO + at least one full week of zero fallback incidents |
| F2 | `tools/dispatcher.py`'s legacy `_ALIAS_MAP` `Payments` entry re-check (already pruned per Track 8C — just confirm no regression before it's fully forgotten) | One deploy cycle post-Track-8C with no `Payments`-table write errors |
| F3 | Old `crm.py` Deal/Payment functions (`crm_add_deal`, `crm_update_deal_status`, `crm_list_deals`, `crm_add_payment`, `crm_upcoming_payments`, `crm_overdue_payments`) | C3 GO + `commercial_crm.py` registered and carrying all real Deal/Payment traffic for a full billing cycle |
| F4 | `core/reasoning_ports.py::_ProductionContacts.find_or_create()`'s former broken import | PR1153 fixed the adapter and added regression coverage; before gated activation, verify the deployed commit and run the existing canary/read path |

---

## Cross-cutting notes for whoever runs this window

- `EMAIL_INBOUND` and `ABANDONED_LEADS` are **not** part of any phase above — they are structurally hard-blocked (`_ADAPTER_GATED_FLAGS`) until `send_email_reply`/`send_bounce` exist as registered dispatcher tools. That is new feature work, not a flag flip; do not attempt to activate either flag as part of this runbook.
- `META_OUTBOUND_ENABLED` similarly cannot produce any user-visible change — no outbound Meta send path exists in the codebase at all. Flipping it only changes whether a reply is computed and logged, never sent.
- The Sunday 08:30 collision (`attribution_report` vs conditionally registered `weekly_summary`) should be resolved or explicitly accepted before steady traffic. The former 08:00 collision is code-done after PR1153 retimed `audience_report` to 08:05; no runtime firing or scheduler regression test is claimed.
- Every "GO" in this document requires the STATUS/EVIDENCE template CLAUDE.md's Hebrew "כלל ברזל" section mandates before any ✅ is recorded anywhere: commit hash, actual `git push` output, Render deploy hash match, and current flag state — this runbook does not substitute for that per-change protocol, it only sequences which changes happen in which order.
