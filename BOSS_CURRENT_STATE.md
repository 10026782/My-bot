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
| WhatsApp webhook | PARTIAL | Twilio validation active; lead capture live (flag); outbound = honest stub |
| Lead Capture | WORKING | lead_capture.py — gated by LEAD_CAPTURE flag |
| Approval system | PARTIAL | Honest UX; 4 subscribers; pending_approvals in app.py; TMA write approval path executes queued writes after approve |
| Event Bus | WORKING | Fail-closed: success only on real handler execution |
| lead_qualifier | PARTIAL | TypeError fixed (C26); state machine = dead code (no live callers) |
| lead_memory | PARTIAL | Debounce engine built and tested; not wired (N03) |
| Lead Scoring | PARTIAL | `lead_capture.py` — קוד ו-write path תקינים; LEAD_SCORING flag כבוי ברירת מחדל, לא אומת בפרודקשן |
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
| N03 Lead Memory wire-up | 🟠 After N02 | lead_capture.py + lead_memory.py |
| N04 Followup Activation | 🟠 After N03 | scheduler + followup_engine |
| Airtable schema formula mismatch (remaining fields) | ✅ RESOLVED | airtable_gateway.py is now the single write path — all normalization/validation/coercion centralized (W2, f964070) |
| core_knowledge.py smoke test false positive | 🟡 | Known — _NEVER_FAKE_CONTROL phrase triggers fake-approval check |
| WhatsApp outbound (real) | ⏸ Blocked | Meta Cloud API approval pending |
| Memory durability | 🟡 | RAM-only; undercuts lead-memory and learning plans |
| lead_qualifier state machine | 🔵 Deferred | Dead code — decide: wire or remove after N04 |
| ROI Dashboard | 🔵 Future | Score reasoning logged (Fix 5); dashboard build pending |

---

## Open Risks (post-sprint)

1. Memory is RAM-only — not durable across restarts.
2. WhatsApp outbound is honest stub — blocked on Meta Cloud API.
3. Worker trigger can impersonate arbitrary chat_id if WORKER_SECRET leaks.
4. TMA partner authorization sometimes happens after record fetch.
5. Learning engine uses mock events — no real production loop.
6. TMA DEV_MODE bypass risk if enabled in production.

**MEDIUM findings #4–7 from audit 12/06 — separate batch planned** (see Open MEDIUM Security Findings below).

---

## Manual Verification Needed

| Check | How |
|-------|-----|
| LEAD_CAPTURE flag enabled on Render | Render env vars |
| WhatsApp lead → Airtable record created | Send test message from unregistered number → check Leads table |
| Lead Pipeline TMA screen shows real score/tier | Open TMA → Lead Pipeline → confirm non-zero scores |

---

## Open MEDIUM Security Findings (12/06 audit — pending)

| # | Finding | Severity |
|---|---------|----------|
| 4 | `_safe_route()` drops approval gate on router exception | MEDIUM |
| 5 | DEV_MODE HMAC bypass still wired in `require_tma_auth` + advertised in CORS | MEDIUM |
| 6 | `/worker/trigger` accepts caller-controlled `chat_id` (impersonation risk) | MEDIUM |
| 7 | `/health` endpoint public — exposes version + internal check state | MEDIUM |

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
