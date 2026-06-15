# BOSS CURRENT STATE

Last updated: 12/06/2026
Reflects: Stabilization Sprint + W0/W1 + Security Audit Fixes (H1-H3) + TIER read-only fix + Game Dashboard fix + Ghost Button Audit + Airtable Gateway (W2)

## Classification Key
- WORKING: implemented, reachable, no blocking issue.
- PARTIAL: implemented but limited or missing some path.
- STUB: returns coming_soon / empty — honest, not misleading.
- BROKEN: fails or blocked by known runtime error.
- NOT IMPLEMENTED: no runtime implementation found.

---

## What Changed Since Last Audit (07/06/2026)

| Item | Status | Detail |
|------|--------|--------|
| W0 WhatsApp Lead Capture | ✅ NEW | lead_capture.py — unknown WhatsApp number → Leads record created in Airtable (commit 2b861bd) |
| W1 Airtable Schema Fix | ✅ MERGED | LeadFields.SCORE="score", TIER="tier", schema_intelligence synced (commit f095036, PR #36) |
| CLAUDE.md | ✅ LIVE | Architecture docs on main — Codex reads at session start (PR #35) |
| ROADMAP/CURRENT_STATE | ✅ UPDATED | Now reflects actual state including W0, W1, removed C14 |
| C40 Golden Path Approval Gate | ? NEW | TMA write endpoints queue approval before writes; approve executes write; reject does not write; receipt returned; audit after successful execution only (tma_api.py, commit 4e5d00d on origin/approval-gate) |

---

## What Changed — 12/06/2026

| Item | Status | Detail |
|------|--------|--------|
| H1 Voice/IVR Twilio validation | ✅ FIXED | `_validate_twilio_signature()` added to `/voice/incoming`, `/voice/step` (commit c1913f5) |
| H2 /schema owner-only | ✅ FIXED | `identity.role` check added; non-owner gets generic block (commit 7b8cc0a) |
| H3 TMA formula injection | ✅ FIXED | `_safe_formula_param()` allowlist regex (Hebrew+ASCII); 400 on invalid (commit b66ca64) |
| TIER write isolation | ✅ FIXED | `lead_memory.py`, `lead_capture.py`, `tma_api.py`, `airtable_schema.py`, `LeadDetail.tsx` — TIER is read-only formula field everywhere |
| Game Dashboard "בוצע" button | ✅ FIXED | `game_today` now reads `Roadmap_Tasks` (was empty `Daily_Tasks`); PATCH writes `Status=Done` + `Coins_Log` |
| GameScreen error toast | ✅ FIXED | Failed task completion shows "⚠️ שגיאה בשמירה — נסה שוב" (3.5s), no silent revert |
| scan_ghost_buttons.py | ✅ NEW | 24/24 api.ts functions mapped — 0 broken endpoints found |
| search_lead schema | ✅ FIXED | Added to `tools/schemas.py` — Claude can now call it |
| audit_log_airtable wiring | ✅ FIXED | Wired into `airtable_get`/`add`/`update`/`get_schema` |
| .env.example | ✅ UPDATED | `TWILIO_AUTH_TOKEN`, `GOOGLE_*`, `DIGEST_CHAT_ID`, `OWNER_TELEGRAM_ID`, `TMA_ALLOWED_ORIGINS` added |
| N03 scoring threshold | ✅ FIXED | "כמה עולה?" and price-intent questions now score WARM+ (was COLD) |
| Airtable Gateway | ✅ FIXED | Single write-path (f964070) — resolves recurring Score/Tier field-name drift class of bugs |

---

## Airtable Gateway — 12/06/2026 (commit f964070)

### Problem (recurring for ~1 month)
5 competing sources of truth for Airtable field names: `airtable_schema.py`, `schema_intelligence.py`, `schema_validator.py`+`schema_cache.json`, `tools/airtable_tools.py` (`_TABLE_FIELDS`), `tma_api.py` (`_LEAD_FIELD_ALIASES`). Result: Score/score mismatch returned 3 times under different names (W1 → today's fix → still broken → root-caused). Every fix in one layer left the other layers stale.

### Solution
`tools/airtable_gateway.py` — single write path. Every Airtable PATCH/POST goes through:
```
normalize aliases → filter read-only → validate vs schema_cache.json
  → coerce linked records → audit_log(source=) → HTTP write
```
- `validate_before_write` (airtable_tools.py) removed — 0 references
- `_sv.validate_fields` (tma_api.py) removed — 0 references
- Gateway is the sole consumer of `schema_validator.py`

### Architectural decisions (for future reference)
- ❌ **NOT done:** full auto-generation of `airtable_schema.py` from `schema_cache.json` — `airtable_schema.py` contains business logic (table names, statuses, comments) that a generator would overwrite. Deferred to Phase 2.
- ❌ **NOT done:** startup fail-on-schema-mismatch — risk of taking down production on a minor Airtable UI rename. If/when added: WARN only + Telegram to `OWNER_TELEGRAM_ID`, never refuse-to-start. (Startup consistency check already emits CRITICAL log + Telegram notification, but does not block.)
- ✅ `schema_cache.json` is fallback/cache. Airtable live schema (Metadata API) is the principled source of truth — live schema load at runtime not yet implemented (Phase 2).

### Validated edge cases (test_airtable_gateway.py — 26/26)
| Input | Outcome |
|-------|---------|
| `{"score":80}` | → `{"Score":80}` — all 3 paths (TMA/lead_capture/agent) |
| `{"Tier":"HOT"}` | → rejected (read-only formula field) |
| `{"Next Action":"none"}` | → stripped (UI sentinel, not a valid select option) |
| `{"Owner":"recABC123"}` | → `["recABC123"]` (multipleRecordLinks coercion) |
| `{"Owner":"John Doe"}` | → rejected (plain name, would cause 422) |
| audit source= | → correct per-caller tag (tma/lead_capture/agent) |

### Open follow-up (non-blocking)
- **Fable 5 architecture review** (race/staleness conditions, generic linked-record coverage beyond Leads, audit failure mode, JS-side null variants beyond "none", tenant-scope ordering) — not run yet. Recommended as post-merge sanity check.
- **Phase 2** (later, not now): live Airtable Metadata API sync at startup; cautious constant generation to `airtable_generated_schema.py` (not overwriting `airtable_schema.py`).

---

## Lead Flow — Live Path (post W0)

```
Unknown WhatsApp number
    ↓
identity.resolve() → Role.LEAD
    ↓
lead_capture.capture_inbound_lead() [NEW — W0]
    ↓ (gated: LEAD_CAPTURE flag)
Airtable Leads: create (first contact) or no-op (returning)
    ↓
run_agent() → conversational reply only
    ↓
[N02 next: scoring written at capture time]
[N03 next: lead_memory wired after score]
[N04 next: followup triggered on HOT tier]
```

**Previously:** WhatsApp lead → conversational reply only. No Airtable record. No scoring. No followup possible.
**Now:** WhatsApp lead → Airtable record created → scoring/followup chain unlocked (pending N02–N04).

---

## Module State Matrix

| Module | Status | Notes |
|--------|--------|-------|
| Telegram agent | PARTIAL | Tool chain unblocked; approval flow honest |
| WhatsApp webhook (Twilio) | PARTIAL | Twilio validation active; lead capture live (flag); outbound = honest stub |
| Meta WhatsApp (Phase 1) | PARTIAL | Inbound webhook only; GET verify + POST receive → run_agent; outbound stub; EMERGENCY_STOP_WHATSAPP gated |
| Strategic Pipeline TMA card | WORKING | קורא `occData.strategic_pipeline` מ-`/api/owner/control-center` (כבר קיים בresponse); 3 ספירות מוצגות |
| Strategic Pipeline counts | WORKING | `Deals.שלב` הוגדר ב-Airtable עם הערכים האנגליים (Idea/Feasibility Check/Legal-Tax Review/Pending Decision) — ספירות חיות |
| Lead Capture | WORKING | lead_capture.py — gated by LEAD_CAPTURE flag |
| Approval system | PARTIAL | Honest UX; 4 subscribers; pending_approvals in app.py; TMA write approval path executes queued writes after approve |
| Event Bus | WORKING | Fail-closed: success only on real handler execution |
| lead_qualifier | PARTIAL | TypeError fixed (C26); state machine = dead code (no live callers) |
| lead_memory | PARTIAL | מחובר ל-`lead_capture.py` (N04-A/B, commit 02f7e75); stores domain/channel/contact_name/score/tier/record_id; LEAD_MEMORY כבוי ברירת מחדל |
| Lead Scoring (N02) | PARTIAL | `lead_capture.py` — scoring + gateway write; LEAD_SCORING כבוי ברירת מחדל; לא אומת בפרודקשן |
| Lead Memory (N03/N04-A/B) | PARTIAL | `lead_memory.update()`: basic info בכל create (N04-A) + tier/score/record_id אחרי scoring (N04-B); LEAD_MEMORY כבוי ברירת מחדל |
| Followup Automation (N04) | PARTIAL | scheduler `_job_followup_scan()` → `run_followup_scan()` קיים ומחובר; `FOLLOWUP_AUTOMATION=false` ברירת מחדל; `all_active()` מחזיר data אמיתי אחרי N04-A/B |
| Google integrations | PARTIAL | Merge conflict resolved; OAuth/env still required |
| Email tools | PARTIAL | Import fixed; honest stub until Google Tools live |
| Airtable integrations | WORKING | Single write-path (W2 gateway); schema/alias/read-only/linked-record all centralized |
| Daily Digest | PARTIAL | Failures visible; score/tier now correct field names |
| Payment Reminder | WORKING | self-test passing (0744ce9) |
| Workers / scheduler | PARTIAL | Mock fallbacks removed; subscribers registered |
| Guards / safety | PARTIAL | Emergency Stop persists; Voice/IVR Twilio validation added (H1) |
| Memory system | PARTIAL | RAM-only; lead_memory built but not wired |
| Learning system | STUB | Mock events; no real production loop |
| TMA / Mini App | PARTIAL | CORS + auth fixed; write endpoints approval-gated; stubs honest |
| Projects Hub | PARTIAL | Real Airtable data; no navigation |
| Finance Pulse | STUB | coming_soon |
| Activity Feed | STUB | coming_soon; approval receipts are returned by API but not persisted/shown in Activity Feed |
| Assets | STUB | coming_soon |
| Personal Mode | STUB | Auth works; screens not implemented |
| Recruitment | PARTIAL | Domain prompt works; lead flow pending N02+ |
| Investor tools | NOT IMPLEMENTED | Roadmap only |

---

## Golden Path Status

| Path | Status | Current Reality |
|------|--------|-----------------|
| Mini App ? Auth ? Real Airtable Data ? Approval ? Write ? Receipt | PARTIAL / IMPROVED | TMA write endpoints now require approval and execute writes only after approve. Reject does not write. Receipt is returned from the approval execution response, but receipt persistence/display is not implemented yet. |

Protected TMA write endpoints:
- POST /api/projects
- PATCH /api/leads/<lead_id>/status
- POST /api/followup

## Ghost Buttons Inventory — Sweep 2026-06-12

Full audit: 54 onClick handlers across 12 components. Results:

| Class | Count | Meaning |
|-------|-------|---------|
| A ✅ | 52 | Connected to working backend endpoint |
| B ❌ | 2 | Ghost — does nothing (TODO stub) |
| C ❌ | 0 | Calls non-existent endpoint |
| D ⚠️ | 0 | Silent success/failure (no feedback) |

### Ghost Button Detail (B — requires fix)

| Component | Button | Issue | Priority |
|-----------|--------|-------|----------|
| `BossCheckin.tsx:363` | Urgency / Source / Topic / Required tags | `saveTaskUpdate()` = `void task` — selections not persisted to Airtable between sessions. UX works locally (XP calc, canComplete gate), but state lost on close. | 🟡 Medium — not blocking critical flow |
| `BossCheckin.tsx:530` | "יום חדש →" | `resetDay()` = `void incompleteTasks` — carry-over candidates never written. Button effectively just calls `load()`. | 🟡 Medium — not blocking critical flow |

**Critical flows (Approvals, Lead actions, Game completion) — all A ✅. No blocking ghosts.**

### Fix plan (deferred — scheduled as separate batch)
1. `saveTaskUpdate` → add `PATCH /api/game/checkin/tasks/{id}` or persist metadata as part of `completeTask` payload
2. `resetDay` → add `POST /api/game/checkin/summary` that logs incomplete + carry-over candidates

---

## Active Issues — Audit 2026-06-12

| Fix | Status | Detail |
|-----|--------|--------|
| 1. search_lead schema missing | ✅ RESOLVED | tools/schemas.py — schema added; Claude can now call search_lead |
| 2. Audit logging on Airtable ops | ✅ RESOLVED | tools/airtable_tools.py — _audit() wired into get/add/update/get_schema |
| 3. .env.example incomplete | ✅ RESOLVED | Added Twilio, Google, DIGEST_CHAT_ID, TMA CORS, LEAD_CAPTURE flags |
| 4. Price questions scored COLD | ✅ RESOLVED | lead_capture.py — price_intent weight 15→30; "כמה עולה?" = WARM |
| 5. Score reasoning in audit log | 🔄 IN PROGRESS | audit_log_airtable writes score+tier+signals; dashboard not yet built |

---

## Open Items

| Item | Priority | Blocker / Notes |
|------|----------|-----------------|
| Receipt persistence/display | ?? | Receipt is returned after approval execution, but not persisted or shown in Activity Feed |
| N02 Live Lead Scoring | 🟡 PARTIAL | קוד תקין ו-write path תוקן (gateway, f964070). Score נכתב רק כש-LEAD_CAPTURE=True **וגם** LEAD_SCORING=True — שניהם כבויים ברירת מחדל. לא אומת בפועל עם הודעת WhatsApp אמיתית. |
| N03/N04-A/B Lead Memory wire-up | ✅ CODE DONE | lead_capture.py + lead_memory.py — commit 02f7e75; לא אומת בפרודקשן |
| N04 Followup Activation (scheduler) | ✅ CODE DONE | scheduler._job_followup_scan() מחובר; FOLLOWUP_AUTOMATION=false; ממתין לאמות ב-Render |
| Airtable schema formula mismatch (remaining fields) | ✅ RESOLVED | airtable_gateway.py is now the single write path — all normalization/validation/coercion centralized (W2, f964070) |
| core_knowledge.py smoke test false positive | 🟡 | Known — _NEVER_FAKE_CONTROL phrase triggers fake-approval check |
| WhatsApp outbound (real) | ⏸ Blocked | Meta Cloud API approval pending |
| Memory durability | 🟡 | RAM-only; undercuts lead-memory and learning plans |
| lead_qualifier state machine | 🔵 Deferred | Dead code — decide: wire or remove after N04 |
| ROI Dashboard | 🔵 Future | Score reasoning logged (Fix 5); dashboard build pending |

---

## Known Architectural Drift

See `docs/governance/ARCHITECTURE_DRIFT_MAP.md` for the full list of 8 deferred drift items, their Piggyback Triggers, and migration steps. Items are not to be executed autonomously — only when their trigger sprint is active.

---

## Open Risks (post-sprint)

1. Memory is RAM-only — not durable across restarts.
2. WhatsApp outbound is honest stub — blocked on Meta Cloud API.
4. TMA partner authorization sometimes happens after record fetch.
5. Learning engine uses mock events — no real production loop.

---

## Manual Verification Needed

| Check | How |
|-------|-----|
| LEAD_CAPTURE flag enabled on Render | Render env vars |
| WhatsApp lead → Airtable record created | Send test message from unregistered number → check Leads table |
| Lead Pipeline TMA screen shows real score/tier | Open TMA → Lead Pipeline → confirm non-zero scores |

---

## Resolved Security Findings (audit 12/06)

| # | Finding | Severity | Fix | Commit |
|---|---------|----------|-----|--------|
| 4 | `_safe_route()` drops approval gate on router exception | MEDIUM | Fail-closed: `Risk.NEEDS_APPROVAL, Handler.APPROVAL, needs_approval=True` | aca037b |
| 5 | DEV_MODE HMAC bypass wired in `require_tma_auth` + CORS | MEDIUM | Removed dead `if _DEV_MODE:` block; stripped `X-Dev-Telegram-Id` from CORS headers | (Batch 2) |
| 6 | `/worker/trigger` accepts caller-controlled `chat_id` | MEDIUM | `chat_id` removed from payload; derived server-side from `ELIYAHU_CHAT_ID` | (Batch 2) |
| 7 | `/health` exposes version + internal check state publicly | MEDIUM | Public `/health` → `{"status"}` only; full detail moved to `/api/owner/health` (owner-auth) | aca037b |

---

## עדכון: CORE_05 Cost Watchdog — מיושם (2026-06-13)

**תיקון תיעוד**: `interaction_engine.py` לא קיים בקודבייס הנוכחי. `context.py` כולל `_select_model()` שעושה Haiku/Sonnet routing נכון לפי role+research-mode.

**דליפת עלות שתוקנה**: `creative_generator.py` תמיד קרא ל-Sonnet — עבר ל-Haiku (חסכון מיידי).

| מרכיב | סטטוס | פרטים |
|--------|--------|--------|
| `core/cost_watchdog.py` | ✅ חדש | `log_usage()` → `logs/usage.jsonl` (append-only, ephemeral) |
| `creative_generator.py` | ✅ תוקן | claude-sonnet → claude-haiku + log_usage אחרי קריאה |
| `app.py` run_agent | ✅ מחובר | log_usage אחרי כל client.messages.create |
| `scheduler.py` | ✅ נוסף | `_job_daily_usage_report` כל יום 08:00 |
| `AI_Usage_Daily` Airtable | ⏳ טבלה חדשה | יש ליצור ב-Airtable לפני שה-daily job כותב לה |
| `COST_WATCHDOG_ENABLED` | default on | Pipes first |
| `SONNET_DAILY_LIMIT` | default 50 | configurable via env |

**החלטות ארכיטקטורה**:
- Usage log: JSONL מקומי (ephemeral, ל-watchdog יומי בלבד)
- Aggregation ארוך-טווח: שורה יומית ל-Airtable `AI_Usage_Daily`
- התראה: טלגרם לאליהו, סף 50 קריאות Sonnet/יום
- `cost_monitor.py` (dollar-based emergency stop) — נשאר ולא שונה
- ארכיטקטורה גנרית: להוסיף `whatsapp_conversation` כ-source_type ללא שינוי מבני

---

## עדכון: Strategic Layer — Schema (2026-06-13)

| שינוי | סטטוס | פרטים |
|-------|--------|--------|
| `DealStatus` — ערכים חדשים | ✅ ב-schema | `"Idea" / "Feasibility Check" / "Legal/Tax Review" / "Pending Decision" / "Rejected"` |
| `ContactFields.ROLE_CATEGORY` + `SPECIALTY` | ✅ ב-schema | `"Role Category"` (single-select) + `"Specialty"` (text) + `ContactRoleCategory` class |
| ⚠️ Airtable Deals.Status | **דרוש** | להוסיף 5 ערכים ידנית: `Idea / Feasibility Check / Legal/Tax Review / Pending Decision / Rejected` |
| ⚠️ Airtable Contacts | **דרוש** | להוסיף שדה `"Role Category"` (single-select, 9 ערכים lowercase) + שדה `"Specialty"` (text) |
| שלבים 3-4 (OCC + TMA card) | 🔲 ממתין | לא התחלנו — ממתין לאישור |

---

## עדכון: Business Lifecycle Gap (2026-06-13)

זוהה פער בין ה-"Operating Layer" הקיים (CRM/Leads/Tasks/Approvals — מכסה ~20-25% ממחזור החיים העסקי) לבין שכבת "Business Management" המלאה (8 שלבים — ראה `ROADMAP.md`). לא משנה תעדוף נוכחי — שלבים 1-4, 7-8 עוברים ל-Future לתיעוד בלבד. המסקנה המעשית: להמשיך ולחזק את שכבת התפעול לפני הרחבה ל"חצי העליון" של העסק.

---

## Stabilization Sprint — Final Status: 10/10 ✅

| Fix | Status |
|-----|--------|
| F1 Approval dead-end | ✅ |
| F2 lead_qualifier TypeError | ✅ |
| F3 Airtable schema mismatch | ✅ (W1) |
| F4 Daily Digest honest | ✅ |
| F5 Payment Reminder | ✅ |
| F6 Mock fallbacks removed | ✅ |
| F7 Emergency Stop persistence | ✅ |
| F8 Health Monitor real checks | ✅ |
| F9 TMA stubs honest | ✅ |
| F10 Duplicate Scheduler | ✅ |
# Audit addendum - 2026-06-14

This file is one of the two active planning sources of truth. The other is `ROADMAP.md`.

## Code reality summary

| Item | Status | Runtime evidence |
|---|---|---|
| N02 Live Lead Scoring | PARTIAL | `lead_capture.py` has inline first-message scoring behind `LEAD_SCORING`; the old `lead_scoring.py` zombie path was removed. `LEAD_CAPTURE` and `LEAD_SCORING` default off. |
| N03 Lead Memory Wire-up | PARTIAL | `lead_memory.update()` is wired from `lead_capture.py` after successful scoring when `LEAD_MEMORY` is enabled; `LEAD_MEMORY` defaults off. |
| N04 Followup Activation | PARTIAL | `scheduler.py` registers `_job_followup_scan`; `followup_engine.py` queues approval requests behind `FOLLOWUP_AUTOMATION`; depends on populated `lead_memory`. |
| N05 Daily Digest upgrade | PARTIAL | `daily_digest.py` displays score, but `_hot_leads()` filters only by `status=hot/Hot/HOT`, not by score/tier. |
| Meta WhatsApp work | BLOCKED | Inbound Twilio webhook exists with signature validation; outbound remains an honest stub / not active pending Meta Cloud API. |
| Approval flow | PARTIAL | Event bus approvals and TMA approval execution exist; receipts are returned/persisted to Interaction Log in code, but Activity Feed display remains incomplete. |
| Feature flags | DONE | `feature_flags.py` supports env/runtime flags and persistent emergency flags. Product flags default off unless env-enabled. |
| Scheduler jobs | PARTIAL | Jobs are registered for digest, collector, cleanup, lead memory flush, followup scan, payments, recovery, learning, email, abandoned scan; several are gated by flags/env or depend on incomplete flows. |

## N02 exact audit

Lead Scoring is partially implemented and flag-gated, not missing and not proven active:

- `lead_capture.py:32` defines `_score_inbound_message()`.
- `lead_capture.py:90` defines `capture_inbound_lead()`.
- `lead_capture.py:96` exits unless `LEAD_CAPTURE` is enabled.
- `lead_capture.py:130` runs inline scoring only when `LEAD_SCORING` is enabled.
- `lead_capture.py:134-138` computes score/tier but writes only `LeadFields.SCORE` via `tools.airtable_gateway.airtable_patch()`.
- `lead_capture.py` syncs `lead_memory` after successful scoring only if `LEAD_MEMORY` is enabled.
- `app.py` calls `capture_inbound_lead()` for `Role.LEAD`; there is no separate scoring module import.

Resolved mismatch: scoring is consolidated into `lead_capture.py`; the old separate scoring path was removed.

## Security checklist consolidation

`SECURITY_CHECKLIST.md` is archived as a historical checklist. Active security risks to carry forward here:

- `_safe_route()` can drop the approval gate on router exception.
- `DEV_MODE` HMAC bypass remains a production risk if enabled.
- `/worker/trigger` accepts caller-controlled `chat_id` if `WORKER_SECRET` leaks.
- `/health` is public and exposes internal check state/version-style data.
