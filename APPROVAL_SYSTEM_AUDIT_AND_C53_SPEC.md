# C53 — Approval System Full Audit & Test Harness Design

Status: **SPEC ONLY.** No code was modified, no tests were created, nothing was deployed or merged as part of this document. Every claim below is sourced directly from the current code on `main` (post PR #70 / C52) — file:line references are given so each finding can be re-verified independently.

> **תיעוד מקור (נוסף 23/06/2026):** המסמך נכתב ב-17/06/2026 בענף `claude/spec-c52-implementation-uqmu1g`, שלא מוזג מעולם. אותר ונשמר בעת ניקוי ענפי `claude/*` ישנים — הענף עצמו נמחק, אך תוכן המסמך נחשב בעל ערך מספיק לשימור. **כל טענות ה-file:line כאן לא אומתו מחדש מול `main` הנוכחי** ועלולות להיות לא מדויקות אחרי שינויי קוד מאז 17/06/2026 — לפני שמתחילים לבנות test harness לפי §4, יש לאמת מחדש כל ממצא Critical/High מול הקוד החי.

---

## 0. Systems Inventory

The "approval system" is not one system — it is **four independent approval/guard mechanisms** plus **two cross-cutting kill switches**, all touching customer- or data-affecting actions:

| # | System | File(s) | Storage | TTL | Confirm UX |
|---|--------|---------|---------|-----|------------|
| 1 | Router-level pending approval | `app.py` (`approval_response`, `_pending_approvals`, `_CONFIRM_WORDS`/`_CANCEL_WORDS`) | in-memory dict, keyed by `chat_id` | 600s (`_PENDING_APPROVAL_TTL`) | free-text "כן"/"לא" reply |
| 2 | Tool-level approval (Event Bus) | `event_bus.py`, `app.py` (`_queue_approval`, `_handle_approval_callback`) | in-memory `PendingActionsStore._store` | 30 min (`PENDING_TTL_MINUTES`) | Telegram inline-keyboard callback (`approve:<id>` / `reject:<id>`) |
| 3 | TMA write approval (C40 Golden Path) | `tma_api.py` (`_queue_tma_write_approval`, `act_on_approval`) | Airtable `Approvals` table | **none** | TMA UI → `POST /api/approvals/<id>` |
| 4 | OTP gate (Emergency Window only) | `core/otp.py` | in-memory `_store` | 5 min, max 5 attempts | 6-digit code via Telegram DM, returned to caller out-of-band |
| 5 | Emergency Stop (kill switch) | `feature_flags.py`, checked in `tools/dispatcher.py`, `core/output_gateway.py`, `health_monitor.py` | persisted `/tmp/emergency_flags.json` | n/a (manual toggle) | owner-only, instant |
| 6 | Emergency Window (temporary risk-ceiling exception) | `core/emergency_window.py` | Airtable `Emergency_Window` table | 24/48/72h, lazy auto-expire on read | owner activates via tool, max risk = High, never stacks |

C52 (`core/output_gateway.py`, `core/financial_gate.py`) sits **downstream** of all of the above: regardless of which approval path produced an outbound customer message, every send must still pass through `send_outbound()` (Secondary Guard in the adapters enforces this at runtime).

**This fragmentation across 3 separate pending-approval stores (in-memory dict / in-memory dict / Airtable) with 3 different TTLs and 3 different confirm UIs is itself the single largest architectural risk surfaced by this audit** — see Gap Analysis §3.1.

---

## 1. Approval Flow Map

### 1.1 Entry points (where an approval gets created)

| Entry point | File:line | Triggers via |
|---|---|---|
| Router classifies turn as high-risk intent/domain | `core/router/risk_router.py:93-113` → `Handler.APPROVAL` | `app.py` calls `approval_response()` |
| Router fails (exception) | `app.py` `_safe_route()` (fail-closed fallback) | `RouteDecision(risk=NEEDS_APPROVAL, handler=APPROVAL)` |
| Agent picks a tool with `requires_approval=True` | `app.py:921` (`if meta.requires_approval`) | `_queue_approval()` → `event_bus.bus.request_approval()` |
| Followup scan finds a lead due for outreach | `followup_engine.py` `request_followup_approval()` (called from `run_followup_scan()`, scheduled job) | `event_bus.bus.request_approval(action="send_followup", ...)` |
| Lead recovery scan finds a dormant lead | `core/lead_recovery.py:217` `request_recovery_approval()` (called from `run_recovery_scan()`, scheduled job) | `event_bus.bus.request_approval(action="send_recovery", ...)` |
| TMA write endpoints | `tma_api.py` — `POST /api/projects`, `PATCH /api/leads/<id>/status`, `PATCH /api/leads/<id>`, `POST /api/leads/<id>/outcome`, `POST /api/leads/<id>/task`, `POST /api/followup` | `_queue_tma_write_approval()` (`tma_api.py:365-432`) → Airtable `Approvals` record |
| TMA write under active Emergency Window, Critical/High+mobile | `tma_api.py` (inside `_queue_tma_write_approval`) | `core/otp.py` `request_otp()` issues a 6-digit code first |
| C52 Financial Gate trips on a customer-bound message | `core/financial_gate.py:check()` → `core/output_gateway.py:_handle_escalation()` | Not a queued "approval" in the formal sense — see §1.5 |

### 1.2 Execution paths (what happens on approve)

| Path | File:line | Re-validates identity/role before executing? |
|---|---|---|
| Router-level confirm (free-text "כן") | `app.py:778-784` — pops `_pending_approvals[chat_id]`, re-runs `run_agent()` for the same original text | **No explicit re-check** — relies on `chat_id` continuity (same channel identity); the re-run still passes through `tool_registry.enforce()` downstream |
| Event Bus tool approval (Telegram button) | `app.py:596-637` (`_handle_approval_callback`) — pops item, calls `enforce(tool_name, identity)` again, then `dispatch_tool()` | **Yes** — `enforce()` re-run at confirm time (line 627), and `dispatch_tool()` enforces again independently (`tools/dispatcher.py:112-116`) — double-checked |
| Event Bus non-tool approval (e.g. `send_followup`) | `app.py:614-621` — `bus.emit(f"{action}.confirmed", ...)` → only handler registered is `_handle_send_followup_confirmed` (`app.py:255`) | No identity re-check inside the handler itself; relies on the approver-role check already done at `app.py:585-594` before either approve/reject branch runs |
| TMA approval | `tma_api.py:1953-1978` (`act_on_approval`) — 3-state claim (PENDING→PROCESSING→APPROVED/FAILED) inside a per-`approval_id` lock, re-reads the Airtable record fresh inside the lock | **Yes** — `@require_tma_auth` re-validates Telegram initData HMAC + `identity.is_owner` on every request, including the approve call itself |
| Recovery approval (`send_recovery.confirmed`) | `event_bus.py:196` `emit()` → **no handler registered anywhere in the codebase** | n/a — see Gap §3.2 (Critical) |

### 1.3 Rejection paths

| Path | File:line | Confirmed no write occurs? |
|---|---|---|
| Router-level cancel ("לא") | `app.py:789-792` — pops pending, returns a fixed Hebrew cancel message | Yes — never reaches `run_agent()` |
| Event Bus reject | `app.py:656-678` — pops item (note: double-pop, see Gap §3.6), sends cancel message to user | Yes — `dispatch_tool()` never called on the reject branch |
| TMA reject | `tma_api.py:1934-1951` — single PATCH to `Approvals.Status=REJECTED`, calls `_try_bus_action(ctx_id, "reject")` | Yes — verified by existing test (`test_approval_concurrency.py` Test 2: exactly 1 PATCH, no execution) |

### 1.4 Timeout paths

| Path | File:line | What happens at expiry |
|---|---|---|
| Router-level (600s) | `app.py` — no active expiry check found; a stale entry is only cleared lazily the next time the same `chat_id` sends *any* message (`app.py:793-795`, "new unrelated message → clear stale pending") | **Passive only** — if the user never sends another message, the entry sits in `_pending_approvals` forever (until process restart) |
| Event Bus (30 min) | `event_bus.py:54-58` (`get`), `:65-68` (`pop`) check TTL lazily on access; `event_bus.py:95-105` (`cleanup()`) is the active sweep, called by `scheduler.py` job `_job_cleanup_pending` every **360 minutes** | Item silently deleted; a confirm/reject tap arriving after expiry gets "⚠️ הפעולה פגה או לא נמצאה" |
| TMA (Airtable `Approvals`) | **No TTL exists.** | A `PENDING` record can sit indefinitely. Nothing expires it. |
| OTP (5 min) | `core/otp.py:84-86` checked inside `verify_otp()`; `cleanup_expired()` exists but is **not wired into the scheduler** (grep confirms `cleanup_expired` is never called anywhere outside its own definition) | Verify call simply returns `False` after expiry; the dangling entry stays in `_store` until process restart (small memory leak, not a security issue since it's already unusable) |
| Emergency Window (24/48/72h) | `core/emergency_window.py:76-95` (`_auto_expire`) — lazy, checked every time `get_active_window()` is called | Flips Airtable status to `EXPIRED` on next read; no active sweep needed since every check path re-reads |

### 1.5 Override paths

| Override | File:line | Guard |
|---|---|---|
| Financial Gate `APPROVED_SOURCES` override | `core/financial_gate.py:88-102` | Requires `source_type` in `{airtable_record, pricing_script, owner_approved, manual_override}` **AND** all of `approved_by` + `approval_id` + `approved_at` truthy in `envelope.meta`, otherwise override is rejected and normal escalation logic applies (fixed in the PR #70 audit pass) |
| `draft=True` forcing CUSTOMER classification | `core/output_gateway.py:129-139` (`_classify_audience`) | Cannot be overridden — applies even if `audience` was (mis)marked `INTERNAL` |
| Emergency Window risk ceiling | `core/emergency_window.py:118-120` | Hard-capped at `High` in code (`max_risk_allowed()` always returns `HIGH`) — `Critical` actions can never be downgraded through this path, by construction, not by convention |
| Secondary Guard bypass (fail-open in non-prod) | `tools/whatsapp_adapter.py:15-33`, `tools/telegram_adapter.py:14-32` | `APP_ENV != "production"` → logs only, does not raise. **This is itself an override path** — see Gap §3.7 |
| Router-level confirm re-running the agent | `app.py:778-784` | Not a tool-permission override — `tool_registry.enforce()` still runs on whatever tool the re-run agent call eventually invokes |

---

## 2. Risk Matrix

| Severity | Finding | Where |
|---|---|---|
| **Critical** | `send_recovery.confirmed` (and `send_email_reply.confirmed`, `send_bounce.confirmed`) have **no registered event-bus handler** anywhere in the codebase. Owner taps "approve" on a recovery approval → `EventBus.confirm()` → `emit()` finds zero handlers → returns "⚠️ אין handler לפעולה זו" → **the recovery message is silently never sent, but the owner has already seen a UI flow that looked like a normal approve.** | `core/lead_recovery.py:217-237` queues `action="send_recovery"`; only `event_bus.py`/`app.py` subscriber found anywhere is `send_followup.confirmed` (`app.py:255`) |
| **High** | `event_bus.PendingActionsStore._store` is a plain `dict` with **no lock**, mutated concurrently from: Flask request threads (Telegram webhook callbacks), the daemon scheduler thread (queueing followups/recovery, running cleanup), and potentially overlapping Telegram callback retries for the same `action_id`. `pop()` is "get → check TTL → del" — three separate statements, not atomic. Telegram is known to redeliver the same `callback_query` on client retry. | `event_bus.py:60-70`, consumed by `app.py:598`/`657` |
| **High** | `EMERGENCY_STOP_AUTOMATION` is documented in the flag registry as "blocks scheduler jobs" but is **never read anywhere in the codebase** outside its own comment/registry entry. Neither `followup_engine.run_followup_scan()` nor `core.lead_recovery.run_recovery_scan()` check any emergency-stop flag before queueing new approvals. | `feature_flags.py:15` (doc only); confirmed absent via repo-wide grep |
| **High** | Three independent "list of tools/actions needing special treatment" exist with no single source of truth and already-drifted contents: `tool_registry.ToolMeta.requires_approval` (per-tool), `event_bus.ACTIONS_REQUIRING_APPROVAL` (4 hardcoded names, self-documented as needing to "match exactly"), `tools/dispatcher._RISKY_TOOLS` (6 hardcoded names gating Emergency Stop). `airtable_delete` appears in the event_bus list but is **not a registered tool** in `tool_registry.py` and **not a dispatcher case** — a landmine for whoever implements it later without touching all three lists. | `event_bus.py:115-120`, `tools/dispatcher.py:120-124`, `tool_registry.py` (no `airtable_delete` entry) |
| **Medium** | TMA `Approvals` Airtable records have **no TTL at all** — unlike every other approval mechanism in the system (30 min, 600s, 5 min). A approval can sit `PENDING` for weeks; nothing re-validates that the underlying record (e.g. the lead) hasn't changed state in the meantime, only that the table is still allowlisted. | `tma_api.py` `_execute_tma_write` (re-validates allowlist, not record freshness) |
| **Medium** | `_notify_owner_escalation()` (C52) sends a free-text prompt asking the owner to reply "שלח / ערוך / בטל", but **no handler anywhere parses these words against an `audit_id`** to actually resend/edit/cancel the held message. This is the deliberate, user-approved "Keep manual, add function unwired" design decision from the C52 build — **intentional, not a bug** — but it means the escalation path is observability-only today, and there is no regression coverage proving the owner notification itself is reliably delivered (`httpx.post` with no retry, no response-code check). | `core/output_gateway.py:255-282` |
| **Medium** | Secondary Guard (`_assert_gateway_context`) fails **open** (log-only, no raise) whenever `APP_ENV != "production"`. If a staging/UAT deployment is ever pointed at real Twilio/Telegram credentials, a direct-adapter bypass of the Gateway (and therefore of the Financial Gate) would only be logged, not blocked. | `tools/whatsapp_adapter.py:23-33`, `tools/telegram_adapter.py:22-32` |
| **Medium** | BOSS_CURRENT_STATE.md (pre-this-session) claimed TMA approval receipts are "not persisted/shown in Activity Feed" — verified code shows receipts **are** persisted to `Interaction Log` and **are** returned by `activity_feed()`. Documentation cannot currently be trusted as ground truth for this subsystem; any merge-readiness sign-off must be based on code, not on prior docs. | `tma_api.py:435-468`, `:2009-2057` (`activity_feed`) |
| **Low** | Router-level pending approval (`_pending_approvals`, 600s TTL) has no active expiry sweep — only cleared lazily on the next message from the same `chat_id`. A user who triggers approval-required intent and then goes silent leaves the entry in memory indefinitely (bounded by # of distinct chat_ids, not unbounded growth, but still a latent leak). | `app.py:778-795` |
| **Low** | `event_bus.cleanup()` (the active TTL sweep) runs every 360 minutes while the TTL itself is 30 minutes — up to ~6 hours of expired entries can sit in memory between sweeps. Functionally harmless (lazy TTL check on every `get`/`pop` already prevents stale execution) but a hygiene gap on a long-lived process. | `scheduler.py` `_job_cleanup_pending` interval vs. `event_bus.py:22` |
| **Low** | `core/otp.cleanup_expired()` exists but is never called from the scheduler or anywhere else — dead/unreachable cleanup function; OTP itself is also dormant by default since `EMERGENCY_WINDOW` defaults off, so this whole path is effectively unexercised in production today (dead-code-rot risk for the next time it's needed under real incident pressure). | `core/otp.py:108-114`; confirmed via grep, zero call sites |

---

## 3. Gap Analysis

### 3.1 Fragmentation: three approval stores, no unified view
There is no single place to answer "what is pending right now, for whom, since when." An owner (or an incident responder) would have to check the Telegram inline-keyboard backlog (ephemeral, in-memory, invisible if the bot restarted), the TMA Approvals dashboard (Airtable, persistent), and `_pending_approvals` (in-memory, no UI at all — only visible by sending a follow-up message) separately. This is the same drift pattern already root-caused once for Airtable field names (the W2 Airtable Gateway fix) — same class of bug, different subsystem. **Out of scope to fix in C53**, but should be tracked as an architectural-drift item.

### 3.2 Missing coverage (confirmed bypasses / dead ends)
- **`send_recovery.confirmed` has no handler** (Critical, §2). This is a functional bypass disguised as a working approval: the owner believes they approved an action that silently no-ops.
- **`EMERGENCY_STOP_AUTOMATION` is unimplemented** — the flag exists in the registry and is documented, but nothing reads it. An incident responder flipping this flag would get no actual effect on followup/recovery scan queueing.
- **No emergency-stop check exists at *queue* time** for any of the three approval stores — only at *execute* time (`tools/dispatcher.py:125` for tool approvals scoped to `_RISKY_TOOLS`; `core/output_gateway.py:176` for any customer-bound send). This means approvals keep piling up in front of the owner during an incident, even though none of them can actually execute. Functionally safe (nothing leaks), but operationally noisy and a UX trap (looks safe to "rubber stamp" during an incident because nothing seems to be happening — until the stop is lifted and the backlog fires all at once if Emergency-Stop is reverted without first auditing the backlog).

### 3.3 Concurrency risks
- **Event Bus (`PendingActionsStore`) — no lock.** `add`, `get`, `pop`, `cancel`, `list_for_chat`, `cleanup` are all unsynchronized dict operations across three threads of execution (Flask request thread, scheduler daemon thread, and — in principle — multiple Flask worker threads if the WSGI server is multi-threaded). Contrast with the TMA path, which solved exactly this with a per-`approval_id` `threading.Lock` plus a durable Airtable-side `PROCESSING` claim state (`tma_api.py:1898-1969`). The Event Bus path has no equivalent.
- **`_handle_approval_callback` reject branch double-pops** (`app.py:657-658`): `bus.pop(action_id)` followed immediately by `item = bus._pending.pop(action_id, None)`. The first call already removes and discards the item; the second is a redundant no-op today (since `dict.pop(..., None)` against a now-missing key just returns `None` safely), but it reaches into `bus._pending` (a "private" attribute) directly, bypassing the `EventBus` interface — fragile, and the comment ("atomic: remove + return in one step") suggests the intent was the opposite of what's implemented (the *first* pop already did the atomic remove-and-return; the second call discards that result entirely and is functionally dead code).

### 3.4 Replay risks
- **Double-tap / duplicate Telegram callback delivery on Event Bus approvals.** Because `pop()` is not lock-protected, two near-simultaneous deliveries of the same `approve:<id>` callback (a known Telegram Bot API behavior on client retry) could both pass the "item exists" check before either deletes it, leading to the *same* high-risk tool (e.g. `gmail_send_draft`, `sheets_append`) being dispatched twice. This is the concrete, real-world trigger for the concurrency risk in §3.3 — not just a theoretical race.
- **TMA path is replay-safe** — verified by existing test (`test_approval_concurrency.py` Test 4): concurrent double-approve produces exactly one 200 and one 409, and the underlying write executes exactly once.
- **Router-level approval (free-text confirm) is single-shot by construction** — `_pending_approvals.pop(chat_id, None)` happens before `run_agent()` is invoked, so a duplicate "כן" sent immediately after simply finds nothing pending and falls through to normal agent handling of "כן" as a standalone message. Low replay risk here.

### 3.5 TOCTOU risks
- **Event Bus `pop()`**: time-of-check (`item = self._store.get(...)`, TTL check) to time-of-use (`del self._store[action_id]`, then the caller proceeds to act on `item`) is not atomic relative to other threads calling `pop()` on the same key — this is the same root cause as §3.3/§3.4, named explicitly as TOCTOU here because the window between "we decided this approval is valid" and "we removed it so no one else can use it" is non-zero and unguarded.
- **TMA path**: re-reads the Airtable record *inside* the lock immediately before claiming it (`tma_api.py:1953-1962`), which is the correct TOCTOU-safe pattern — check and claim happen under the same lock, against a freshly-read value, not a cached one.
- **TMA execution-time data staleness (not a lock issue, a freshness issue)**: even with the claim lock preventing double-execution, nothing re-verifies that the *target record* (e.g., the lead being PATCHed) hasn't been independently modified by someone else between when the approval was *requested* and when it is finally *approved* (which, per §2 Medium, can be arbitrarily long since there's no TTL). This is a business-logic TOCTOU, distinct from the approval-record's own concurrency safety.

### 3.6 Audit trail integrity
- **TMA path**: well-instrumented — `_audit()` calls on queue/approve/reject, receipts written to `Interaction Log`, queryable via `activity_feed()`. This is the most mature audit trail in the system.
- **Event Bus path**: **no structured audit log** — only `logger.info`/`logger.warning` statements (`event_bus.py` throughout). If the process restarts or log retention expires, there is no durable record that an approval was ever requested, confirmed, or rejected via this path. Compare to C52's `_audit_log()` (`core/output_gateway.py:223-232`), which is also logger-only today but at least centralizes the format around a single `audit_id` per send — Event Bus approvals have no equivalent correlation id once popped.
- **C52 (Output Gateway)**: `_audit_log()` is logger-only, no persistence layer (no Airtable/DB write). Every `GatewayResult` carries an `audit_id`, but that id is only meaningful as long as the log line exists. This is acceptable for shadow-mode (current state) but should be revisited before `FINANCIAL_COMMITMENT_GATE=true` goes to production for real (this is the user's own standing 7–14 day hold, unrelated to this audit, but the lack of a persisted/queryable audit trail strengthens the case for not rushing that flag).
- **Router-level path**: no audit trail beyond `logger.info` at queue time (`app.py:487`) and at confirm/cancel (`app.py:780-792`) — least observable of the four paths, consistent with it being the lowest-stakes gate (a courtesy confirmation, not a permission boundary).

### 3.7 Fail-open conditions (cross-cutting)
- Secondary Guard fail-open outside `APP_ENV=production` (§2 Medium).
- Event Bus `emit()` returning `None` when no handler is registered is *correctly* treated as a failure by the caller (`app.py:619-621` shows the user an explicit "no handler" message) — this is a good fail-closed pattern *for visibility*, but it doesn't change the fact that the underlying action (e.g. the recovery message) never happens. "Fails loud" is still "fails."

---

## 4. C53 Test Harness Specification

### 4.1 Relationship to existing coverage
`test_approval_concurrency.py` already covers the TMA path's 4 core scenarios (normal approve, normal reject, execution failure, double-approve concurrency) well. **C53's harness extends coverage to the other three approval mechanisms and the cross-cutting interactions the existing suite does not touch** — it should not duplicate the TMA tests, only add a regression for any TMA-side fix this audit recommends (none required — TMA path graded sound).

### 4.2 Test categories

| Category | Target system(s) | Priority |
|---|---|---|
| A — Event Bus concurrency & replay | `event_bus.py`, `app.py:_handle_approval_callback` | **P0** (covers Critical + High findings) |
| B — Missing-handler detection | `event_bus.py` subscriber registry vs. all `request_approval(action=...)` call sites | **P0** |
| C — Emergency Stop coverage matrix | `feature_flags.py`, `tools/dispatcher.py`, `core/output_gateway.py`, `followup_engine.py`, `core/lead_recovery.py` | **P0** |
| D — TTL/expiration behavior | `event_bus.py`, `app.py:_pending_approvals`, `core/otp.py`, `core/emergency_window.py`, TMA `Approvals` (absence test) | **P1** |
| E — Router-level approval flow | `app.py:approval_response`, `_CONFIRM_WORDS`/`_CANCEL_WORDS` | **P1** |
| F — OTP issuance/verification | `core/otp.py` | **P1** |
| G — C52 ↔ Approval interaction | `core/output_gateway.py`, `core/financial_gate.py`, approval `meta` proof fields | **P1** (regression for the PR #70 audit fixes already shipped — keep green, don't re-derive) |
| H — Cross-system consistency | `tool_registry.requires_approval` vs. `event_bus.ACTIONS_REQUIRING_APPROVAL` vs. `tools/dispatcher._RISKY_TOOLS` | **P2** |
| I — Audit trail presence | All four approval paths | **P2** |
| J — Secondary Guard fail-open boundary | `tools/whatsapp_adapter.py`, `tools/telegram_adapter.py` | **P2** |

### 4.3 Required fixtures

- **`fake_event_bus`**: a fresh `EventBus(PendingActionsStore())` instance per test (never the module-level singleton) so tests don't leak state into each other — current `event_bus.py` exposes `pending`/`bus` as singletons, so the harness needs a constructor-based fixture, not a monkeypatch of the singleton.
- **`frozen_clock`**: ability to control `datetime.now()` seen by `PendingActionsStore` to deterministically test TTL boundaries (just-before-expiry vs. just-after) without real sleeps. Given the current implementation calls `datetime.now()` directly (not injected), this requires either (a) `freezegun`/`time-machine`-style monkeypatching of `event_bus.datetime`, or (b) a small seam added to `PendingActionsStore.__init__` to accept a clock callable — **note for implementation phase, not this spec**: the latter is a testability improvement, not a behavior change, and would need to be flagged separately since this task is audit-only.
- **`identity_factory`**: builds `Identity`-like objects for every role (`owner`, `partner`, `manager`, `employee`, `lead`, `guest`, `readonly`) and every channel (`telegram`, `whatsapp`) so role-matrix tests (Category C, H) don't hand-roll `SimpleNamespace` per test.
- **`approval_callback_factory`**: builds a fake Telegram `CallbackQuery`-like object (`cq.data`, `cq.from_user.id`, `cq.message.chat.id/message_id`) matching what `_handle_approval_callback` expects, parameterized by `action` (`approve`/`reject`) and `action_id`.
- **`tma_request_context`**: reuse the pattern already in `test_approval_concurrency.py` (`_app.test_request_context` + patched `_at_get_record`/`_at_patch`/`_try_bus_action`/`_audit`/`_notify_owner`) as a fixture rather than inline boilerplate, so Category D/I tests touching TMA don't re-derive it.
- **`flag_sandbox`**: a context manager that snapshots and restores `feature_flags._RUNTIME` (and removes/restores `/tmp/emergency_flags.json` if a test needs persistence behavior) so Category C tests can flip flags without bleeding into other tests or the real `/tmp` file used by a running dev server.

### 4.4 Required mocks

- `bot.send_message` / `bot.answer_callback_query` / `bot.edit_message_text` (telebot) — never hit the real Telegram API.
- `tools.dispatcher.dispatch_tool` — for Category A/C tests that need to assert *whether* it was called and with *what* identity, without executing real Airtable/Gmail/Calendar side effects.
- `core.output_gateway._dispatch_to_adapter` — for Category G tests, so no real (even stub) adapter call is needed; assert on the `GatewayResult` and on `_audit_log` call arguments instead.
- `httpx.post` — for OTP send (`core/otp.py:_send_code`), escalation owner-notify (`core/output_gateway.py:_notify_owner_escalation`), and `telegram_adapter.send_telegram` — assert call count/args, never make a network call.
- `schedule` job invocation — Category C/D tests that exercise `_job_cleanup_pending`/`_job_followup_scan`/`_job_lead_recovery` should call the underlying functions directly (`event_bus.pending.cleanup()`, `run_followup_scan()`, `run_recovery_scan()`), not go through the `schedule` library's timing — timing itself is out of scope, behavior is in scope.
- Airtable HTTP layer (`_at_get_record`/`_at_patch`/`_at_post` in `tma_api.py`, or `tools/airtable_gateway.py` functions for `core/emergency_window.py` tests) — already the established pattern in `test_approval_concurrency.py`; reuse it.

### 4.5 Required assertions (by category, representative — not exhaustive)

**Category A (Event Bus concurrency & replay)**
- Two concurrent `_handle_approval_callback(approve_cq)` calls for the *same* `action_id` against a real (non-mocked) `PendingActionsStore` result in `dispatch_tool` being called **at most once** (this is expected to **fail** against current code — that failure is the deliverable, proving the gap from §3.3/§3.4; if it's later fixed, this test should flip to asserting exactly-once and a 2nd/duplicate response).
- A `pop()` call on an already-popped `action_id` returns `None` and never raises.
- Cleanup running concurrently with a confirm on the *same* `action_id` does not raise and does not result in the action firing twice.

**Category B (Missing-handler detection)**
- For every distinct `action` string passed to any `bus.request_approval(action=..., ...)` call site in the codebase (statically enumerable: `gmail_send_draft`/etc. via `_queue_approval`, `send_followup`, `send_recovery`), assert a handler is registered via `bus.subscribe()` before the app reaches steady state. This test should be written so it **fails today** for `send_recovery` (and would fail for `send_email_reply`/`send_bounce` if those call sites existed) — the failure is the point: it converts a silent production bug into a loud test failure.
- `bus.confirm(action_id)` for an action with no handler returns the "no handler" message (current behavior) **and** logs at `ERROR` (not `WARNING`) — assert log level, since a silently-no-op'd approval deserves louder visibility than it currently gets.

**Category C (Emergency Stop coverage matrix)**
- With `EMERGENCY_STOP_ALL=true`: `dispatch_tool("airtable_add", ...)` is blocked; `dispatch_tool("airtable_get", ...)` (read-only, not in `_RISKY_TOOLS`) is **not** blocked — confirms the scoping is intentional and documented, not accidental.
- With `EMERGENCY_STOP_ALL=true`: `core.output_gateway.send_outbound(...)` for any `OutputChannel` returns `GatewayResult.status == "EMERGENCY_STOP"` and `_dispatch_to_adapter` is never called.
- With `EMERGENCY_STOP_AUTOMATION=true`: assert whether `run_followup_scan()`/`run_recovery_scan()` queue any approvals — current expected result is **they still do** (the flag is unread); this test documents the gap from §3.2 and should be the regression that proves it's fixed once `EMERGENCY_STOP_AUTOMATION` is actually wired in.
- A tool present in `event_bus.ACTIONS_REQUIRING_APPROVAL` but absent from `tools/dispatcher._RISKY_TOOLS` (currently `airtable_delete`) is flagged by a static consistency check (Category H), not re-derived here.

**Category D (TTL/expiration)**
- `PendingActionsStore.add()` then `get()` at `now + 29min` returns the item; at `now + 31min` returns `None` and the entry is removed from `_store`.
- `cleanup()` removes only expired entries, leaves non-expired ones untouched, and is idempotent (calling twice in a row is a no-op the second time).
- OTP: `verify_otp()` after `OTP_TTL_MINUTES` returns `False` and removes the entry; `MAX_ATTEMPTS + 1`th attempt (even with the correct code) returns `False` and marks `consumed=True`.
- Emergency Window: a record with `Expires At` in the past is flipped to `EXPIRED` on the *next* `get_active_window()` call (lazy expiry), and `is_active()` returns `False` immediately after.
- **Negative test for TMA**: assert there is currently **no** code path that expires a `PENDING` `Approvals` record purely by elapsed time (i.e., a record created arbitrarily long ago with no action taken is still returned as actionable) — this documents §2 Medium and should be deliberately kept as a known-gap test (skipped/xfail) rather than silently absent, so a future fix is visible as "this test now needs updating" rather than discovered by accident.

**Category E (Router-level approval flow)**
- `approval_response()` stores under the right `chat_id`, includes `created_at`.
- A `_CONFIRM_WORDS` reply pops the entry and invokes `run_agent()` with the original stored text (assert the text passed matches, not just that *some* call happened).
- A `_CANCEL_WORDS` reply pops the entry and never calls `run_agent()`.
- An unrelated message (neither confirm nor cancel word) while a pending entry exists clears the stale entry (per `app.py:793-795`) and is processed as a new message.

**Category F (OTP)**
- `request_otp()` returns `None` (not an exception) when `OWNER_TELEGRAM_ID`/`TELEGRAM_TOKEN` env vars are missing — confirms fail-closed-by-return-value rather than crash.
- Code is never present in the `request_otp()` return value (only `request_id`) — assert the return type/shape, not just behavior.
- `verify_otp()` is single-use: a second `verify_otp()` call with the *correct* code after a first successful verification returns `False`.

**Category G (C52 ↔ Approval interaction — regression, already covered by manual testing this session, formalize here)**
- `draft=True` + `audience=INTERNAL` on a `_CUSTOMER_CAPABLE_CHANNELS` channel still classifies as `CUSTOMER` and is subject to the Financial Gate.
- `meta.source_type` in `APPROVED_SOURCES` without all three of `approved_by`/`approval_id`/`approved_at` → override rejected, normal escalation path taken.
- Same, with all three present and truthy → override accepted, `FinancialGateResult.escalated == False`.
- `FINANCIAL_COMMITMENT_GATE=false` (shadow mode, current production default) with a triggering message → `shadow_only=True`, message is still sent (not blocked), and the would-have-escalated reason is logged.

**Category H (Cross-system consistency — static/structural tests, not runtime)**
- Every action name in `event_bus.ACTIONS_REQUIRING_APPROVAL` either has a matching entry in `tool_registry` with `requires_approval=True`, **or** is explicitly documented as a non-tool action (e.g. `send_followup`, `send_recovery`) in an allowlist maintained alongside the test — fails loudly if a new entry is added to one list and not reconciled.
- Every tool in `tools/dispatcher._RISKY_TOOLS` exists as a registered tool in `tool_registry` (catches the `airtable_delete`-style dangling reference in reverse — i.e. also check nothing in `_RISKY_TOOLS` is itself a ghost).

**Category I (Audit trail presence)**
- For each of the 4 approval paths, assert that *some* identifiable log line or persisted record is produced for: request, approve, reject. For TMA this asserts against `_audit()` call args (already partially covered); for Event Bus/router-level this is currently log-only, so the assertion is "a log record at the expected level was emitted with the expected fields" using `caplog`/`logging` test capture — not a persistence check, since none exists yet (documents the gap from §3.6 rather than papering over it).

**Category J (Secondary Guard)**
- `APP_ENV=production` + calling `send_whatsapp`/`send_telegram` directly (outside `_gateway_context.approved`) raises `AssertionError`.
- `APP_ENV` unset (default) behaves identically to `production` (raises) — confirms the safe-by-default fallback.
- `APP_ENV=staging` + same direct call does **not** raise, only logs at `ERROR` — confirms the documented fail-open behavior is exactly what's intended, not accidentally broader (e.g. doesn't also suppress the log).

### 4.6 Pass/fail criteria

- **A test suite file per category** (e.g. `test_c53_eventbus_concurrency.py`, `test_c53_missing_handlers.py`, ...) mirroring the existing flat-script style of `test_approval_concurrency.py` (no pytest harness exists in this repo — see `CLAUDE.md` Tests section — so each file should remain a standalone runnable script with its own `passed`/`failed` counters and `sys.exit(0 if failed == 0 else 1)`, consistent with project convention).
- **Pass** = the script exits 0. For tests in Categories A, B, C, D (the "documents a known gap" tests), the initial pass criterion is the test correctly *detecting and reporting* the gap (e.g. asserting the missing-handler case *does* produce the "no handler" message) — these are regression tests for *current, accepted* behavior, not yet for the fix. They should be clearly labeled in-file (e.g. `# KNOWN GAP — see APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md §3.2`) so a future fix is expected to *change* the assertion, not be blocked by it.
- **Fail** = any assertion mismatch, any uncaught exception, or (for concurrency tests) any flaky non-deterministic result across N repeated runs (recommend running Category A's concurrency test in a loop of at least 20 iterations in CI, since thread-scheduling races may not reproduce every run — this mirrors how `test_approval_concurrency.py` Test 4 already structures its threading test, but that test is deterministic by design via the lock; Category A's tests are explicitly probing the *absence* of a lock, so they need repetition to have any power).
- No test in this harness should make a real network call (Telegram, Twilio, Airtable, Anthropic) — full mock/stub coverage per §4.4 is a hard pass/fail gate on its own (a CI check grepping for unmocked `httpx`/`telebot`/`anthropic` usage in any `test_c53_*.py` file is recommended).

---

## 5. Merge Readiness Assessment

### 5.1 What is verified (by direct code reading + existing tests this session)
- TMA approval path (C40): 3-state claim, lock-protected, replay-safe, audit-logged, receipts persisted and queryable — confirmed both by code reading and by the existing `test_approval_concurrency.py` suite (4/4 scenarios passing as of this audit).
- C52 Customer Output Gateway: Emergency Stop check ordering, audience classification (including the `draft=True` fix), Financial Gate shadow-mode behavior, and the approved-source override proof-field requirement — all manually re-verified against current code this session and match the PR #70 audit fixes exactly as shipped (commit `8a9820a`).
- Tool-level Event Bus approval (Telegram inline button) does re-run `enforce()` at confirm time, and `dispatch_tool()` independently re-enforces — defense in depth confirmed, not just claimed.
- Secondary Guard exists in both Send Adapters and defaults to fail-closed (`APP_ENV` unset → production behavior).

### 5.2 What remains unverified (no test exists today, behavior only confirmed by reading)
- Event Bus concurrency safety under real concurrent load (no test exists; this audit's reading-based analysis predicts a race, but it has not been reproduced under test).
- `send_recovery.confirmed`'s missing-handler behavior in an actual running process (confirmed structurally via grep — zero `subscribe` call sites for that action — but not exercised end-to-end against a live `core.lead_recovery.run_recovery_scan()` → owner-taps-approve flow).
- `EMERGENCY_STOP_AUTOMATION`'s real-world effect (or lack thereof) on the scheduler — confirmed unread via grep, not exercised under test.
- Router-level approval (`_pending_approvals`) behavior under multiple concurrent chats / TTL boundary conditions.
- OTP and Emergency Window flows end-to-end — both gated behind `EMERGENCY_WINDOW` (default off) and never exercised in production traffic; only unit-level reasoning from reading the code, no integration test of the full "Critical action from mobile → OTP issued → code verified → action proceeds" chain.

### 5.3 What blocks full production confidence
1. **The `send_recovery` dead-handler bug should be fixed (or the recovery-approval feature explicitly disabled/flagged off) before relying on lead-recovery approvals in production** — today, approving a recovery action gives the owner false confidence that it executed.
2. **Event Bus locking** should be added (mirroring the TMA pattern) before Event Bus approvals are used for genuinely high-stakes, hard-to-reverse actions at meaningful volume — today's risk is bounded by low traffic and human-paced approval taps, not by any code guarantee.
3. **`EMERGENCY_STOP_AUTOMATION` should be wired in or removed from the flag registry** — an undocumented no-op flag is worse than no flag, because an incident responder may toggle it expecting an effect it doesn't have.
4. **The three approval-relevant tool/action lists (`tool_registry`, `event_bus.ACTIONS_REQUIRING_APPROVAL`, `dispatcher._RISKY_TOOLS`) should gain a structural consistency check** (Category H above) before any new high-risk tool is added — otherwise the next tool added under the existing "Adding a new tool checklist" (CLAUDE.md) can silently miss Emergency Stop coverage exactly as `airtable_delete` already would if implemented today.
5. **None of the above blocks the existing `FINANCIAL_COMMITMENT_GATE` shadow-mode hold** — that decision (flag stays `false` for 7–14 days pending real-traffic shadow logs) is unrelated to this audit's findings and remains entirely the user's call, unaffected by anything found here.

This document recommends building the C53 test harness in the priority order given in §4.2 (Categories A/B/C first), with the explicit understanding that several of the first tests written are expected to **fail against current code** — that is the intended initial signal, converting today's silent gaps into named, tracked, visible test failures before anyone decides whether/how to fix them.
