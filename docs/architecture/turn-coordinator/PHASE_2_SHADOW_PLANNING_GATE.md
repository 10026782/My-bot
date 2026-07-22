# Phase 2 Shadow — Planning Gate & Runtime Grounding

Program: TurnCoordinator (see `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`, CONTRACT FREEZE / MANDATORY GATE, not yet approved).
Status: **PLANNING AND RESEARCH ONLY.** No runtime code written, no feature flag changed, no routing/reply/tool/approval/ActionContract/Airtable behavior changed. This document itself is the only artifact this task produced.
Baseline: `claude/turn-coordinator-contract-v1` @ `eca66b5` (2026-07-22).
Cross-Layer gate: `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` applies — §10 below is the Impact Matrix required before any implementation PR.
Scope: Phase 2 (Shadow Decision) only, as defined in the frozen contract's "סדר היישום" — compute and log what the Coordinator *would* decide, while the legacy runtime keeps owning all real routing/replies/approvals/execution. Phases 3-7 and the RP5 gate are out of scope here (see §9's `earliest_enforcement_phase` tagging in the frozen contract).

**Compliance with the hard prohibitions (restated, not re-argued below):** no runtime implementation, no routing/reply behavior change, no ActionContract/approval change, no tool execution or Airtable write, no new source of policy truth, no redefinition of `ActionFact`, no new evidence validator parallel to RP4/RP5 or `core/anti_hallucination.py`, no claim that BUG-130 is fixed, no claim that TurnCoordinator is active, no model-based inference for structural queue correlation. Every design choice below was checked against this list before being written down; §10 and §13 flag the two places a naive design would have violated it and how the proposal avoids that.

---

## 0. Method note

Sections 1-3 below were produced by three parallel read-only research passes over the working tree (not the live production process — this session has no access to production Render logs or live traffic). All file:line citations were re-verified by direct `Read`/`Grep` against `eca66b5` before being included here; a small number of items the research passes flagged `UNCERTAIN` were independently re-checked and are resolved inline (marked **[resolved]**). Anything still open is carried into §13 (Owner-Decision Table), not silently assumed.

---

## 1. Current Runtime Path Map

### 1.0 Two "envelope" concepts — do not conflate

- **`IngressEnvelope`** (`core/ingress_envelope.py`) — a C90/C94 per-message evidence-tracking object, keyed by `envelope_id`. Built at `app.py:2953-2968` inside `run_agent()`, via `core/telegram_ingress_adapter.py::build_telegram_envelope()` / `core/whatsapp_ingress_adapter.py::build_whatsapp_envelope()`.
- **`TurnEnvelope`** (`core/turn_envelope.py`) — the TurnCoordinator Phase-0 scaffold. A different dataclass for a different purpose (pending-queue snapshot for the future Coordinator). Built and logged via `_build_and_log_turn_envelope()` (`app.py:1455-1626`), called once from `app.py:2635-2637` inside `run_agent()`.

Both are called "envelope" in the codebase; this is a naming collision, not a shared object. The Shadow hook (§3) attaches near the second one, not the first.

### 1.1 Ingress entry point

- **Telegram**: `app.py:4226-4227` `@app.route("/telegram", methods=["POST"])` → `def webhook_telegram()` delegates to `_webhook_telegram_impl()` (`app.py:4237`). Parses `telebot.types.Update.de_json(...)` at `app.py:4247`; text-message branch starts `app.py:4276`.
- **WhatsApp (Twilio, primary)**: `app.py:4445-4446` `@app.route("/whatsapp", methods=["POST"])` → `_webhook_whatsapp_impl()` (`app.py:4456`). Pulls `Body`/`From`/`To`/`MessageSid` from `request.values` at `app.py:4460-4464`.
- **WhatsApp (Meta Cloud API, secondary)**: `app.py:4614-4615` `@app.route("/webhooks/meta/whatsapp", ...)` → `webhook_meta_whatsapp()`. Explicitly **inbound-only** per its own section-header comment (`app.py:4610-4612`) and deliberately excluded from `IngressEnvelope`/`raw_event_id` (comment at `app.py:2943-2945`, "never passes raw_event_id"). No outbound send implementation was found wired to this route.

Both primary channels converge on the shared `resolve_identity(channel, external_id)` (`identity.py:234`) and the shared `run_agent()` (`app.py:2528`). CLAUDE.md's "Identity → Router → Context → Agent" claim is accurate **from `run_agent()` onward**; §1.7 below documents the one confirmed structural divergence (reply emission).

### 1.2 Turn/envelope creation (TurnCoordinator Phase 0)

`core/turn_envelope.py` is genuinely observation-only, log-only, with no runtime side effects — confirmed by direct read, not assumed from its docstring.

- Call site: `app.py:2635-2637`, inside `run_agent()`, identical for both channels (channel is a string parameter, not a branch).
- Sequence inside `_build_and_log_turn_envelope()` (`app.py:1455-1626`):
  - `find_live_contracts()` → `PendingQueueAwareness(queue_id=f"ac:{fp}", ...)` at `app.py:1515-1532`.
  - Lead-preview session state → `PendingQueueAwareness(queue_id=f"lead_preview:{fp}", ...)` at `app.py:1545-1571`.
  - `event_bus.batch_queue.count_pending()` → `PendingQueueAwareness(queue_id=f"batch_queue:{fp}", ...)` at `app.py:1573-1585`.
  - `build_turn_envelope(...)` (`core/turn_envelope.py:229-286`), called `app.py:1587-1593`.
  - `log_turn_envelope(envelope, canonical_user_id=identity.memory_key)` (`core/turn_envelope.py:302-330`) at `app.py:1594` — the module's only write, one structured `logger.info` line.
  - `log_case_c_signal("C1", ...)` at `app.py:1601-1605` when `len(live_contracts) > 1` (`core/turn_envelope.py:418-436`).
- Placement: after identity resolution, lead capture, session snapshot, live-contracts snapshot — but **before** the Pending Approval Gate (§1.5, `app.py:2643`) pops anything. It snapshots turn-start state.
- **[resolved]** A second, independent Phase-0 observation point exists later in the same function: `build_ownership_signal()` (`core/turn_envelope.py:509-530`) is called at `app.py:3569-3575`, logged via `log_ownership_signal()` at `app.py:3586` — after the handler/tool-use outcome is already known. Relevant to §3's hook-point analysis (this point is *after* irreversible action, not before, so it is not itself a candidate Shadow hook — but it shows the module already has a "post-outcome" logging pattern the Shadow schema in §5 can follow for its own after-the-fact fields).

### 1.3 Intent classification

- `core/router/intent_router.py:128` `detect_intent(text, confidence_threshold=0.75) -> tuple[str, float, str]`.
- Invoked at `core/router/router.py:43`, inside `route_request()` (`core/router/router.py:23-189`).
- `route_request()` is wrapped by `_safe_route()` (`app.py:2452-2486` — fail-closed: any exception becomes `Intent.UNKNOWN`/`Risk.NEEDS_APPROVAL`/`Handler.APPROVAL`), called once at `app.py:2971` inside `run_agent()`. Shared for both channels.
- Engineering-note override (`count_engineering_markers`) at `core/router/router.py:54-59`, takes priority over business intent for staff roles — a second, non-`_RULES` signal source that isn't part of `IntentSignal` as the frozen contract defines it.
- **`DESTRUCTIVE_ENTITY_REQUEST` confirmed absent**: `grep -rn "DESTRUCTIVE_ENTITY_REQUEST" --include="*.py" .` → 0 matches anywhere in runtime code (only in the frozen contract docs). Relevant to §8.
- **[resolved]** `context.py::build_context()` **is** a real, separately-named pipeline stage — imported at `app.py:51`, called at `app.py:3073`. (One research pass flagged this uncertain; grep confirms CLAUDE.md's architecture description is accurate here, not inlined.)

### 1.4 Capture classification

Two independent mechanisms — do not conflate:

**(a) Router-level classification (observability + Tier-4 stop-gate), runs for every internal-identity message:**
- `core/ingress_classifier.py:793` `classify_ingress(text, source_type="text") -> IngressClassification`, via `_classify_ingress_core()` (`:819`) → `_extract_lead_candidates()` (`:494`).
- Called from `core/router/capture_router.py:65`, inside `classify_capture_ic()` (`:48-85`), invoked from `core/router/router.py:92-94`, gated on `identity.is_internal` (`:90`). Result stashed on `RouteDecision.capture_ic`/`capture_tier` (`:183`, `:99`).
- Tier-4 stop-gate: `core/router/router.py:128-140` — `capture_ic.tier == 4` forces `Handler.CLARIFY`, `tool_allowed=False`, terminating routing regardless of what `intent_router` matched in the same text.

**(b) Lead Candidate Handler — the actual write/dictation path:**
- `core/lead_candidate_handler.py:1022` `handle_lead_candidate(identity, text, chat_id, channel, domain="", ic=None, intent="", session=None) -> Optional[str]`.
- Called at `app.py:3006-3010`, gated on `identity.is_internal` (`app.py:3004`) — same gate as (a) by explicit design (comment `app.py:3000-3003`).
- Deliberately reuses `route.capture_ic` from (a) rather than re-classifying (BUG-056 single-classification-per-turn invariant, comment `app.py:3001-3003`).
- Runs **after** `_safe_route()`/`route_request()` — capture classification (a) happens *inside* routing, but capture *handling* (b) happens *after* routing returns.
- Shared code for both channels (no channel branching inside the function itself).
- **Separate, WhatsApp-only pre-Router lead path**: `app.py:2572-2590` — an external `identity.role == Role.LEAD` contact (not internal staff) triggers `lead_capture.capture_inbound_lead()` directly at `app.py:2578`, **before** the Router runs at all (comment `app.py:2575-2577`: domain is hardcoded `"general"` here precisely because Router hasn't run yet). This is a structurally different mechanism from (a)/(b) — inbound external-lead ingestion, not staff dictation.

### 1.5 Pending-state lookup

**Four coexisting, independently-keyed pending-state stores are checked per turn.** This is the single most consequential finding for §4 (legacy-to-canonical mapping) — see the "structural exposure" analysis at the end of this section.

**(a) `app.py`'s own in-memory dict, `_pending_approvals`** (`app.py:168-172`, lock `_pending_approvals_lock`):
- `dict[chat_id, dict[approval_id, entry]]` — outer key is raw `chat_id` (Telegram numeric id or WhatsApp phone — **not** a canonical cross-channel identity), inner key `approval_id = uuid.uuid4().hex[:8]` (`app.py:731`).
- **[resolved]** Confirmed as an *active* write path (one research pass flagged this uncertain): `_add_pending_approval()` is called at `app.py:805`.
- Lookup/resolve: `_resolve_pending_reply(chat_id, user_text)` (`app.py:738-764`); pop: `_pop_pending_approval(chat_id, approval_id)` (`app.py:767-775`).
- Checked in `run_agent()`'s "2.5 Pending Approval Gate" (`app.py:2643-2723`), the lock-guarded lookup at `app.py:2661-2703`. Runs identically for both channels.

**(b) `event_bus.py`'s `PendingActionsStore`** (`event_bus.py:28-178`, module singleton `bus`):
- `dict[action_id, {"action", "payload", "chat_id", "expires", ...}]`, `action_id = str(uuid.uuid4())[:8]` generated in `.add()` (`:41-56`).
- Used by the tool-approval-queueing flow: `bus.request_approval()` at `app.py:1239-1252`, inside `_queue_approval_detailed_impl()` (`app.py:1079-1420`).
- `action_id` is embedded **structurally** in the Telegram inline keyboard: `callback_data=f"approve:{action_id}"` (`app.py:1295-1296`), round-tripped verbatim through `callback_query.data`, parsed at `app.py:1978`. This is the strongest existing case of a genuinely non-text-parsed, structural queue key in the whole system — but Telegram-only (WhatsApp has no inline-button equivalent).
- Explicit code comment confirming this is a separate namespace from (c): `app.py:1994-1995` — *"action_id is an event_bus key, NOT a contract_id — must go via fingerprint."*
- Peek: `bus.peek(action_id)` (`app.py:2003`); consume: `bus.pop(action_id)` (`app.py:2042`, `app.py:2400`).
- Identity-keyed (not id-keyed) lookups for bare confirm-word flows: `bus.find_pending_tool_approval(canonical_user_id)`, `bus.find_pending_by_business_fingerprint(...)` (`event_bus.py:139-147`, `:112-137`) — keyed off `identity.memory_key`, a **different key space** from `_pending_approvals`'s raw `chat_id`.

**(c) `core/action_gateway.py`'s ExecutionLedger / `ActionContract`** — the newer, canonical mechanism, running *simultaneously* with (a)/(b), not replacing them yet (shadow-mode comments `app.py:1117-1236`):
- Keyed by `contract_id = str(uuid.uuid4())` (`core/action_gateway.py:920`, inside `propose_action()`).
- Read-side: `find_live_contracts(identity.memory_key)` — called at `app.py:2612-2613` (turn-start snapshot), `app.py:2321-2322` and `app.py:2489-2490` (ingress-gate prefetch, both channels).
- This is the store `_build_and_log_turn_envelope()` (§1.2) reads to build the `"ac:{fp}"`-prefixed `PendingQueueAwareness`.
- `contract_id` is separately bookmarked per-identity: `session_store.lead_sessions.set_last_prompted_contract()`, called right after an owner notification send succeeds inside `_queue_approval_detailed_impl()` — lets a bare "כן"/"מאשר" resolve to a specific contract without a callback round-trip (BUG-115 "bookmark").

**(d) `event_bus.py`'s `BatchQueueStore`** (`event_bus.py:200-235`, singleton `batch_queue`):
- `dict[canonical_user_id, list[dict]]` — holds mutating tool calls deferred within one turn when more than one appears (defer logic `app.py:3297-3343`). Keyed by `identity.memory_key`.

All four are read at different points inside `run_agent()`; a further layer — `core/action_gateway.py`'s `route_override_word()`, `route_combined_word()`, `route_disambiguation()`, `route_confirmation_word()`, `route_cancellation_word()` (`:1639`, `:1573`, `:1523`, `:1176`, `:1455`) — sits on top of store (c) at `app.py:2725-2905` ("2.55 Confirm-word + canonical tool-approval intercept"), independent of (a)/(b)/(d).

**Structural exposure of `queue_id` — direct finding:** `TurnEnvelope.active_queue_id` (`core/turn_envelope.py:194`, computed `:266-273`) *is* a real structured field, not text-parsed. But it is coarse-grained (one of exactly three synthetic patterns per identity: `"ac:{fp}"` / `"lead_preview:{fp}"` / `"batch_queue:{fp}"`), the embedded identifier is **irreversibly SHA-256-fingerprinted** by explicit design (`core/turn_envelope.py:194-197`, `:289-299`), and it is **currently only ever logged** — nothing reads it back programmatically today (Phase-0 scope docstring, `core/turn_envelope.py:8-27`). It identifies *which class* of queue is active, not *which specific pending item*.

The identifiers a Coordinator actually needs to resolve a *specific* pending item are real and structural, but live in **three separate, non-unified key spaces**: `approval_id` in `_pending_approvals` (keyed by raw `chat_id`), `action_id` in `event_bus.PendingActionsStore` (keyed by `action_id` itself, round-tripped via Telegram `callback_data`), `contract_id` in `ActionGateway` (keyed by `identity.memory_key`, unfingerprinted — comment `app.py:1525` notes `contract_id` is "not PII"). §4 below builds `current_active_queue_id` directly from these three stores, not from `TurnEnvelope.active_queue_id`.

### 1.6 Current route/handler selection

- `core/router/router.py:23-189` `route_request(text, channel_raw, identity, domain_from_channel="", envelope_id="") -> RouteDecision` — pure orchestrator over 4 sub-routers, fully shared across channels.
- Wrapped by `_safe_route()` (`app.py:2452-2486`, fail-closed to `Handler.APPROVAL` on exception).
- Called once at `app.py:2971` inside `run_agent()`, called identically from both webhook impls.

### 1.7 Current reply owner / reply emitter — confirmed structural divergence

This is where the two channels diverge, contrary to a naive reading of "one shared pipeline":

- **Telegram**: `bot.send_message(reply_chat_id, reply)` at `app.py:4409`, **directly** after `run_agent()` returns. Does **not** go through `core/output_gateway.py::send_outbound()`. By design: `core/output_gateway.py:29,33` (`_ALWAYS_INTERNAL_CHANNELS`) classifies Telegram as always-`INTERNAL` — exempt from the Financial Gate that customer-facing channels require.
- **WhatsApp (Twilio)**: `_gateway_whatsapp_reply(...)` (`app.py:268-298`) **does** route through `send_outbound(OutboundEnvelope(channel=OutputChannel.TWILIO_WHATSAPP, audience=AudienceClass.CUSTOMER, ...))` (`core/output_gateway.py:93`, called `app.py:4598-4599`) — passes the Financial Gate. Actual delivery is the synchronous TwiML response (`app.py:4600-4607`).
- `tools/telegram_adapter.py:37` / `tools/whatsapp_adapter.py:41` are the registered Send Adapters for `core/output_gateway.py`'s dispatch table, used by *other* proactive-send call sites (followup engine, scheduler) — **not** this direct inbound-reply path. `tools/whatsapp_adapter.py` is an explicit "honest stub" (module docstring `:3-9`) — `send_whatsapp()` always returns `delivery_success=False`, `adapter_mode="stub"`; it is not the code path that actually delivers WhatsApp replies today.

**Consequence for §4/§5:** "current_reply_owner" cannot be defined uniformly across channels from a single code location — Telegram's reply owner is "the direct `bot.send_message()` call site," WhatsApp's is "whatever `send_outbound()` resolved the audience/channel to," and these are genuinely different mechanisms, not the same function branching on a string.

### 1.8 Tool and approval boundary

Shared `run_agent()` tool-use loop (`app.py`, roughly lines 3195-3410), identical for both channels:

- `enforce(tool_name, identity)` (`tool_registry.py:481-493`, raises `ToolDenied`), called `app.py:3225`.
- Approval-required branch: `app.py:3241` (`meta.requires_approval`, from `TOOLS_REQUIRING_APPROVAL`, `tool_registry.py:414-416`).
  - Preflight leads-write block: `enforce_leads_write_gate()` at `app.py:3251` (`airtable_add`/`airtable_update` only).
  - Batch-defer (2nd+ mutating tool call in one turn): `app.py:3297-3343`, via `batch_queue.enqueue()`.
  - Otherwise `_queue_approval_detailed()` (`app.py:3344-3346`) → `_queue_approval_detailed_impl()` (`app.py:1079-1420`): `resolve_canonical_tool()` (`:1082`), `executed_action_cache` dedup (`:1085-1094`), `bus.find_pending_by_business_fingerprint()` cross-channel dedup (`:1098-1113`), `propose_action()` (FEATURE_ACTION_GATEWAY-gated, `:1122`, enforce-mode `:1123-1135` / shadow-mode `:1171-1183`), `bus.request_approval()` (`:1239-1252`), owner-notification send with inline keyboard (`:1292-1327`).
  - `_CONFIRM_WORDS`/`_CANCEL_WORDS` (`app.py:173-176`), consumed at the Pending Approval Gate (`app.py:2668-2671`) and the "2.55" intercept (`app.py:2802`, `:2905`).
- Non-approval dispatch: `dispatch_tool(tu.name, tu.input, identity, trusted_source="agent")` at `app.py:3405` → `tools/dispatcher.py:99`, which **re-checks** `enforce()` at `:143` (defense-in-depth, never trusts the caller's prior check — docstring `:136-138`), then Emergency Stop (`:148-154`), then `validate_action()` (`:156+`).
- Approval **callback** boundary (Telegram-only): `_handle_approval_callback_impl()` (`app.py:1969-2450`), reached from `app.py:4267-4268`, calls `dispatch_tool()` again at `app.py:2237` — a **second**, separate call site from the tool-loop's `app.py:3405`.

### 1.9 Final send point

- Telegram normal reply: `app.py:4409`. Telegram approval-notification: `app.py:1323-1327`. Telegram post-approval confirmation: downstream of `dispatch_tool()` at `app.py:2237`, exact send-line not pinned in this pass — **needs a targeted `grep -n "bot.send_message" app.py` in the 2200-2450 range before implementation** (flagged, not asserted).
- WhatsApp (Twilio): not a discrete function call — attached to `resp.message(gated_reply)` (`app.py:4606`), delivered as the literal Flask `Response(str(resp), mimetype="application/xml")` (`app.py:4607`); Twilio performs delivery as a side effect of parsing that TwiML.
- WhatsApp (Meta Cloud API): inbound-only, no outbound implementation found (§1.1).

### 1.10 TMA participation — does it enter this pipeline at all?

Grounded finding (separate research pass, `tma_api.py`): **`route_request()`/`run_agent()` are never called from `tma_api.py`** (`grep -n "route_request\|run_agent" tma_api.py` → 0 matches). TMA is a CRUD REST API with its own `require_tma_auth` decorator (`tma_api.py:793-817`), not a participant in the chat-turn pipeline.

Two partial exceptions, neither of which is full participation:
1. **`ask_ai`** (`/api/ai/ask`, `tma_api.py:1933-2007`) calls `context.py::build_context()` directly (`:1982,1986`) and reuses `memory_store`/`llm_fallback.call_anthropic_text`, but explicitly bypasses the agent tool loop — docstring `:1938-1939`: "single turn, no tool loop." Never calls `run_agent()`/`route_request()`.
2. **Approval execution** shares `core/action_gateway.py`'s `ActionGateway`/`dispatch_tool()` backbone: `_claim_and_execute_approval` (`tma_api.py:2710-2860`) calls `_gw.approve(contract_id, ...)` (`:2834`) → `ActionGateway._execute_contract()` (`core/action_gateway.py:1779`) → `dispatch_tool(...)` (`:2406-2409`) — the same dispatcher Telegram/WhatsApp approvals use. **But** TMA does **not** use `event_bus.py`'s `PendingActionsStore`/`_pending_approvals` — `tma_api.py:2845-2850` explicitly hardcodes `bus_synced=False` ("event_bus sync is not part of the ActionContract-backed flow"); `_try_bus_action` (`:345-371`) attempts a best-effort legacy sync for observability only, treating a miss as normal.
3. TMA does log its own `TurnEnvelope` observation: `tma_api.py:556-557` calls `app.py`'s `_build_and_log_turn_envelope(identity, identity.user_id, None, entry_point="tma")` before proposing a new contract — but the comment there (`:544-551`) states this is "observation only," a cross-channel conflict signal, not real pipeline execution.

**Conclusion (per §9's channel-coverage rule): TMA does not need a full 9-checkpoint path trace for Phase 2 Shadow.** It never reaches `route_request()`, so `intent_signal`/`capture_signal`/most of `pending_reply_signal` are structurally inapplicable to TMA turns. TMA's only Phase 2-relevant surface is its shared `ActionGateway`/`dispatch_tool()` approval-execution path — already covered by §1.5(c)/§1.8, not a separate map.

---

## 2. Signal-Provider Map

For each `TurnSignals` field (frozen contract §1): existing source, current shape, adapter need, failure semantics.

### Supporting types check (referenced in the contract, not defined within it)

| Type | Found? | Location |
|---|---|---|
| `PendingQueueAwareness` | **Yes** | `core/turn_envelope.py:63` — frozen dataclass (`queue_id, source, kind, summary, items, approval_granularity, priority`). Actively constructed today (§1.2). |
| `AgentAvailabilityStatus` | **Yes, type only** | `core/turn_envelope.py:153` — shape matches (`mode: AgentAvailability, active_provider_id, selection_reason`). But **never computed** — hardcoded constant `_PHASE0_AGENT_AVAILABILITY` (`:163-167`), always `mode=PRIMARY`. Module's own docstring (`:159-162`): "do not read this as proof AGENTLESS detection exists yet." `grep` for `AGENTLESS`/`AgentAvailability` across the repo: matches only inside this one file. |
| `CapabilityScope` | **No** | 0 matches repo-wide. Closest partial analogs are both narrower: `tool_registry.py:441` `get_availability(tool_name, role=None)` is per-tool, on-demand, not a turn-level scope snapshot; `tma_api.py:2321` `_load_capability_map()` is a static-JSON owner-dashboard artifact, unrelated to routing. |
| `MessageKind` | **No** | 0 matches repo-wide. `core/turn_envelope.py:200` has a same-named-in-spirit but different `message_kind: Optional[str]` field on `TurnEnvelope`, always hardcoded `None` (`:283`, comment: "not computed until Phase 4") — a stub field, not a real type, and dead (always `None`). |

### Field-by-field

| # | Field | Existing source | Current shape | Adapter needed | Failure semantics today |
|---|---|---|---|---|---|
| 1 | `intent_signal` | `core/router/intent_router.py:128` `detect_intent()` | Raw 3-tuple `(str, float, str)`. `Intent` (`route_decision.py:17`) is a plain string-constant class, **not an Enum** — `Optional[Intent]` in the contract has no matching runtime type. No-match returns the sentinel `Intent.UNKNOWN`, not `None`. `matched_rule` is the regex pattern string, not an `evidence_span` offset — no span computation exists. `detect_ambiguous_phrase()` (`:185`) is a second, separate signal source not folded into `detect_intent()`. | Yes, moderate: wrap tuple → `IntentSignal`; map `UNKNOWN` → `None`; hardcode `classification=EXPLICIT` (file has no heuristic path); newly compute `evidence_span` via `re.search(matched_rule, text).span()` (not returned today). `DESTRUCTIVE_ENTITY_REQUEST` intent is simply not producible — see §8. | Never raises (pure regex loop); `logger.debug()` on both match/no-match paths. |
| 2 | `capture_signal` | `core/ingress_classifier.py:793` `classify_ingress()` + `core/lead_candidate_handler.py:1022` `handle_lead_candidate()` | `IngressClassification.candidates` is a **tuple of untyped dicts** (`{"name","phone","confidence","context","raw_text","domain_hint"}`) — `CaptureCandidate` as a type has 0 matches anywhere. No `evidence_span`. No `classification` field (contract's own assumption of "almost always HEURISTIC" is consistent with the regex-only extraction, but the field doesn't exist in the source). `handle_lead_candidate()` is **side-effecting** (writes to Airtable, returns a reply string or `None`), not a pure signal producer — not decomposable into a `CaptureSignal` without extraction work. | Yes, substantial: define `CaptureCandidate`; map dict → dataclass; hardcode `classification=HEURISTIC`; compute `evidence_span` newly. `InputProvenance` has **zero backing data** — grep for `reply_to`/`quoted`/`is_reply`/`in_reply_to` across all ingress adapters returns 0 hits; no adapter today captures reply-to/quote metadata. | `classify_ingress()` core path unguarded but low-risk (pure string ops); two helper writes (`_save_raw_capture`, `_record_classification_observation`) individually wrapped, log-and-continue, never block. `handle_lead_candidate()` wraps its own `classify_ingress()` call: `except Exception: logger.warning(...); return None` (`:1096-1098`) — **falls through to the agent silently** on failure, not to an error state. |
| 3 | `pending_reply_signal` | Scattered across `core/action_gateway.py`'s `route_confirmation_word()` (`:1176`), `route_disambiguation()` (`:1523`), `route_cancellation_word()` (`:1455`), `route_combined_word()` (`:1573`), `route_override_word()` (`:1639`) | All return **plain, fully-resolved strings** (or `None`) — they are **side-effecting resolvers** (mutate `self._disambiguation`, transition `ActionContract.status`), not pure observers. No function returns `queue_id`+`match_basis` as data; the match-basis reasoning is implicit in *which function ran* and *what internal state it found*, never externalized. Telegram callback correlation (`callback_data=f"approve:{action_id}"`) is real `callback_correlation`-shaped structural data, but correlates to `event_bus`'s store, a *different* pending mechanism than `ActionContract`'s `contract_id` (§1.5). | **Yes, the largest gap of the seven fields** — requires decomposing each `route_*` function's internal branching (session bookmark hit vs count-based fallback vs disambiguation-list hit) into an explicit `match_basis` classification, computed **without** executing the resolution as a side effect (i.e., a read-only variant of the same logic). | No global guard; `find_live_contracts()`/`find_by_id()` are direct in-memory reads, unlikely to raise. Session-bookmark lookup inside `route_confirmation_word()` is defensively wrapped: `except Exception: _bookmark = None` (`:1194-1198`) — fails open to the count-based fallback. |
| 4 | `pending_queues` | `core/turn_envelope.py:229` `build_turn_envelope()`, assembled in `app.py:1455` `_build_and_log_turn_envelope()` | **Closest match of all seven fields.** `TurnEnvelope.pending_queues: tuple[PendingQueueAwareness,...]` — type matches the contract almost exactly (§ supporting-types table above). | Minimal: `tuple` → `list`. Caveat: `build_turn_envelope()` itself takes already-resolved queue objects as arguments (pure, no I/O, per its own docstring) — the *assembly* logic (which live contracts, which lead-preview field, which batch count) lives in `app.py`, not in `core/turn_envelope.py`. A Coordinator needs that assembly logic, not just the type. | Entire `_build_and_log_turn_envelope()` body wrapped in `try/except Exception` (`app.py:1500...1607-1618`) — logs `type(exc).__name__` only (never `str(exc)`, to avoid leaking user content), returns `None` silently. Explicitly documented as "fail-open, not silent" (`app.py:1608`); the module's own docstring says it "never raises into the caller" (`core/turn_envelope.py:14-15`). |
| 5 | `capability` | **None.** | No aggregate/turn-level capability object exists. | N/A — new design needed, not an adapter. | `get_availability()` (the closest per-tool analog) fails closed (`available=False`) on any internal error (`tool_registry.py:455-466`), also validates the check's own return shape and falls back on malformation (`:468-473`). |
| 6 | `agent_availability` | Type exists (`core/turn_envelope.py:152-156`), computation doesn't | Hardcoded constant, always `PRIMARY`, `selection_reason="phase0_not_tracked"`. | Type reusable as-is; the actual degraded/fallback-provider detection logic does not exist anywhere in the repo (no `ModelProviderRegistry`, no `select_provider`). | N/A — no live computation to fail; it's a Python literal. |
| 7 | `last_outbound_kind` | **None.** | `memory_store.py` is generic key/value, no message-kind tracking. `session_store.py`'s `last_prompted_contract` (used by field 3) is the nearest conceptual cousin but scoped narrowly to approval prompts only. `core/output_gateway.py`'s `OutboundEnvelope` (`:46-57`) carries no `kind`/shape field and doesn't persist anything (pass-through gateway). `grep` for `last_outbound\|outbound_kind\|LastOutbound`: 0 matches. | N/A — nothing to adapt; would need to be built from scratch (both the `MessageKind` type and a tracking mechanism, most naturally piggybacking on `OutboundEnvelope`/`send_outbound()` or a new `session_store` field). | N/A. |

**Bottom line:** 2 of 7 fields (`pending_queues`, and `agent_availability`'s *type*) are close to reusable; `intent_signal`/`capture_signal` need moderate-to-substantial adapters over real existing logic; `pending_reply_signal` needs the resolvers rebuilt as observers (largest single gap); `capability` and `last_outbound_kind` have no existing source of truth at all and need new design, not adaptation. This directly shapes §11's slice boundary — a Phase 2 implementation that tried to build all seven fields with full fidelity would not be a narrow slice.

---

## 3. Exact Shadow Hook Point(s)

### 3.1 Why a single hook point does not exist for every turn

The naive assumption — "one line in `run_agent()`, after all signals are computed, before anything irreversible happens" — does not hold, because the **Pending Approval Gate itself can return early**. If `_resolve_pending_reply()` (§1.5a, `app.py:738-764`) matches, or the "2.55" confirm-word intercept (§1.8, `app.py:2725-2905`) resolves against `ActionGateway`, the turn is fully handled and the function returns **before** `route_request()` (§1.6, `app.py:2971`) or `handle_lead_candidate()` (§1.4b, `app.py:3006-3010`) ever run. This means `intent_signal`/`capture_signal` are **not computed at all** on a genuine pending-reply turn under the current code — there is nothing to "hook after" for those signals on that turn.

This is a real structural finding, not a design nicety to gloss over: proposing a single fixed hook line would silently produce an incomplete `TurnSignals` (missing `intent_signal`/`capture_signal`) on every pending-reply turn, which is exactly the kind of turn the Shadow system most needs to observe correctly (it's the "Pending Ownership" scenario family, tagged `earliest_enforcement_phase=2→3` in the frozen contract).

### 3.2 Proposed design: two hook call sites, one shared computation function

Both call sites invoke the **same** new function, e.g. `core/turn_coordinator_shadow.py::compute_and_log_shadow_decision(identity, text, chat_id, channel, ..., legacy_outcome_hint)` — never inlined logic at either call site, so there is exactly one place that can affect behavior to review, not two.

**Hook A — inside the Pending Approval Gate's early-return branch**, immediately before the `return` that ends the turn on a matched pending reply (`app.py`, inside the `app.py:2643-2723` block, at whichever exact line the existing `return`/`reply=...` happens for a match — needs the follow-up `grep` noted in §1.9 to pin exactly, since the Gate has multiple internal branches). At this point `pending_reply_signal` is fully known (the legacy code just computed it as a side effect of resolving), but `intent_signal`/`capture_signal` are not — Hook A's shared function must **explicitly call** `detect_intent()`/`classify_ingress()` itself (defensively, wrapped, read-only) to complete the `TurnSignals` record. This is calling the *existing, canonical* signal sources, not re-deriving a new parser — consistent with "the Coordinator must consume signals," since the Shadow function is a consumer of `detect_intent()`, not a reimplementation of it.

**Hook B — after `handle_lead_candidate()` returns** (`app.py`, immediately after `app.py:3006-3010`, before the tool-use loop begins at `app.py:3225`). At this point `intent_signal` (from `route_request()`, already run at `app.py:2971`) and `capture_signal` (from `handle_lead_candidate()`, just run) are both known. `pending_reply_signal` must be computed here too (the Gate did **not** match on this turn, by construction — we only reach Hook B when Hook A's branch wasn't taken), via a read-only call into the same `_pending_approvals`/`bus`/`ActionGateway` lookups §1.5 already documents, without executing `_resolve_pending_reply()`'s consuming side effect.

Both hooks sit **before** `app.py:3225`'s `enforce()` call — i.e., before the tool loop can dispatch anything, queue an approval, or send a reply. Hook A additionally sits before the Pending Approval Gate's own `return`, so it observes the *same* state the legacy path is about to act on, not a stale snapshot.

### 3.3 Non-interference proof

`compute_and_log_shadow_decision()` is specified as:
1. **Pure with respect to legacy state** — every read it performs (`_pending_approvals` dict access, `bus.peek()`/`find_pending_tool_approval()`, `find_live_contracts()`, a fresh `classify_ingress()`/`detect_intent()` call) is a read-only call already proven non-mutating in §1.5/§2's failure-semantics columns (none of `.pop()`, `.request_approval()`, `.propose_action()`, `_pop_pending_approval()`, `_add_pending_approval()` are ever called from this function).
2. **Return-value-discarding at both call sites** — the function returns `None` (or nothing at all); its only externally observable effect is a `logger.info(...)` call emitting the schema in §5, following the exact pattern `log_turn_envelope()`/`log_ownership_signal()` already establish (§1.2) as a safe, precedented "observe and log, never touch legacy variables" call shape in this exact function (`run_agent()`).
3. **Wrapped in a blanket `try/except Exception`** at both call sites (matching `_build_and_log_turn_envelope()`'s own `app.py:1500...1607-1618` pattern) — any internal failure degrades to a `degraded/error` reason code in the logged record (§5's `error/degraded reason` field) and never propagates.
4. **Gated by the flag from §7**, `off` by default — when `off`, the call sites are no-ops (an `if state == "off": return` guard at the top of the function, or the call sites themselves skip the call — either way, zero added work when the flag is off).

Given (1)-(4): the proposed hooks cannot alter selected legacy handler, reply text, reply count, approval state, `ActionContract` state, tool execution, or Airtable writes — every one of those is owned by code that runs strictly after both hook points and reads none of the Shadow function's state (the Shadow function writes only to its own log line and, in a later phase, its own comparison record — never back into `RouteDecision`, `_pending_approvals`, `bus`, or `ActionGateway`).

---

## 4. Legacy-to-Canonical Comparison Mapping

`current_handler` / `current_reply_owner` / `current_active_queue_id` must be derived from **structural** sources per §1, never from parsing the final reply text when a structural source exists (per the task's own instruction). Per-case mapping:

| Legacy branch taken | `current_handler` | `current_reply_owner` | `current_active_queue_id` |
|---|---|---|---|
| Pending Approval Gate matches (§1.5a) | `"pending_approval_gate"` | Telegram: **structurally known** — the branch that resolved is deterministic from which store matched (`_pending_approvals` vs `bus` vs `ActionGateway`); tag with the store name. WhatsApp: same stores are reachable but Telegram-only inline-button correlation (§1.5b) doesn't apply — **mark `UNKNOWN`** for the sub-case where WhatsApp resolves via bare confirm-word only, since no structural per-item key round-trips through WhatsApp's medium the way `callback_data` does for Telegram. | The real key from whichever store matched — `approval_id` (a), `action_id` (b), or `contract_id` (c) — **not** `TurnEnvelope.active_queue_id` (too coarse/fingerprinted/write-only, §1.5). |
| "2.55" confirm-word/disambiguation intercept matches (§1.8) | `"action_gateway_intercept"` | Structurally known — one of `route_confirmation_word`/`route_disambiguation`/etc. by name (§2 field 3) | `contract_id` from `ActionGateway`, or `None` if the intercept found nothing live (a real, structural "no queue" case, not `UNKNOWN`). |
| Neither gate matches, `route_request()` → `Handler.AGENT`, no capture fires | `"agent"` (from `RouteDecision.handler`, `route_decision.py`'s `Handler` enum — structurally known, not inferred) | `"agent"` — Telegram: `bot.send_message()` direct call (§1.7); WhatsApp: `send_outbound()` via Financial Gate (§1.7). **These are genuinely different mechanisms**, not the same value — tag with which one, don't collapse them. | `None` (no queue involved). |
| `Handler.AGENT`, capture fires and writes (`handle_lead_candidate()` returns non-`None`) | `"capture_flow"` | Same channel-split as above, but the reply text originated from `handle_lead_candidate()`'s return value, not the agent loop | Usually `None` (single-turn capture), unless the write itself creates a new pending clarification (`Optional[str]` return meaning "clarification needed") — in that specific sub-case, **mark `UNKNOWN`**: `handle_lead_candidate()` does not expose a structural id for its own clarification state the way `ActionGateway` does for approvals; only text/session-state inference exists, which the task's own instruction forbids using in place of a real structural source. |
| `Handler.APPROVAL` (tool call queued) | `"approval_queue"` | Owner-notification send at `app.py:1292-1327` — Telegram-only path structurally (WhatsApp has no observed equivalent owner-notification call site in this trace — **mark `UNKNOWN`** for WhatsApp-originated approval-queueing until a dedicated follow-up trace confirms whether one exists) | `action_id` from `bus.request_approval()`'s return (structural), cross-referenced with the `contract_id` from `propose_action()` when `FEATURE_ACTION_GATEWAY` is not `off` (§1.8) — **two ids may exist simultaneously for the same logical queue item**; the Shadow schema (§5) should carry both rather than collapsing them, since collapsing would itself be an inference. |
| `Handler.CLARIFY` (Tier-4 capture stop-gate, §1.4a) | `"clarify"` | `"agent"` reply path (clarification is delivered as a normal reply, not a distinct emitter) | `None` — Tier-4 clarification is not queue-backed in the current code; confirmed absent, not inferred. |
| `_safe_route()` caught an exception (§1.6) | `"safe_route_fallback"` | `"agent"` fallback reply | `None` |

**General rule for `UNKNOWN`:** applied wherever (a) no structural source exists at all (confirmed by grep/read, not by absence-of-search), or (b) a structural source exists but only for one channel and the other channel's equivalent has not been traced/confirmed in this pass. `UNKNOWN` is never applied because deriving the real answer would merely be *inconvenient* — every `UNKNOWN` above cites the specific gap.

---

## 5. Shadow Decision Schema

New type, distinct from the frozen contract's `TurnDecision` (which is the Coordinator's *canonical output*, once it exists as real code) — this is the **emitted log record** comparing legacy vs. Coordinator-computed, Phase 2-specific:

```python
@dataclass(frozen=True)
class ShadowDecisionRecord:
    # Identity of the record
    timestamp: str                        # ISO-8601 UTC, generation time
    turn_id: str                          # per §1's turn identification (envelope_id or newly minted)
    decision_id: str                      # unique per Shadow computation, distinct from turn_id

    # Privacy-safe identity (never raw chat_id/phone/user content)
    tenant_fingerprint: str               # SHA-256-truncated, same scheme as core/turn_envelope.py's existing _fingerprint()
    role: str                             # identity.role — not PII, needed for disagreement analysis by role

    channel: str                          # "telegram" | "whatsapp" | "tma" (tma only via §1.10's narrow surface)

    # Legacy side (§4)
    current_handler: str
    current_reply_owner: str              # or "UNKNOWN", with a paired current_reply_owner_reason field
    current_reply_owner_reason: Optional[str]
    current_active_queue_id: Optional[str]  # or "UNKNOWN"

    # Coordinator side (computed, never acted on)
    coordinator_selected_handler: str     # HandlerId value, as a string for log stability across contract_version bumps
    coordinator_reply_owner: str          # ReplyOwnerKind value
    active_queue_id: Optional[str]        # Coordinator's own resolution, kept separate from current_active_queue_id even when equal

    # Signal snapshot (§2) — enough to reconstruct the decision, not the full objects
    intent_classification: Optional[str]  # SignalClassification value or None if intent_signal itself is None
    intent_source: Optional[str]
    intent_confidence: Optional[float]
    capture_classification: Optional[str]
    capture_source: Optional[str]
    capture_confidence: Optional[float]
    pending_reply_queue_id: Optional[str]
    pending_reply_match_basis: Optional[str]
    pending_reply_valid: Optional[bool]   # result of the §1.1-rules validity check, not just presence

    reason_code: str                      # DecisionReason value, as a string

    contract_version: str
    policy_snapshot_version: str

    # Comparison metadata
    contested_signal_category: Optional[str]  # one of the 5 §8-exit-criteria categories, or None if not contested
    disagreement: str                     # "agree" | "disagree_documented" | "disagree_undocumented"
    disagreement_note: Optional[str]      # bug number / decision log reference, required when disagreement != "agree"

    error_or_degraded_reason: Optional[str]  # populated only if the Shadow computation itself failed (§3.3 point 3)
```

Design notes:
- No raw message text, no raw phone/chat_id anywhere in the record — `tenant_fingerprint` reuses the same fingerprinting scheme `core/turn_envelope.py` already established, rather than inventing a second one (avoids the "parallel sources of truth" prohibition at the mechanism level, not just the policy level).
- `current_active_queue_id`/`active_queue_id` are kept as two separate fields even when they're expected to match — collapsing them into one field would itself be the Coordinator quietly asserting agreement, which is exactly what this record exists to check independently.
- `disagreement_note` being required (not optional in practice) whenever `disagreement != "agree"` operationalizes the frozen contract's §8 item 2 ("every disagreement must carry an explicit artifact") directly in the schema, not just as a process rule someone might skip.

---

## 6. Render Log Export — Research & Validation (not executed)

### 6.1 Credential — cannot be verified from this session

This remote execution environment's full environment-variable name list (127 variables) contains **zero** Render-related names — verified via `env | cut -d= -f1 | grep -i render` (empty) and a full unfiltered listing (attached to the research transcript, not reproduced here since it's not sensitive but is irrelevant to Render). The task states the credential is "already available in the owner's Windows terminal environment" — that is a different machine from this container; nothing about it is discoverable, verifiable, or testable from here, by construction, not by omission.

Also checked (repo-side, for any documented convention): `render.yaml` does not exist; `.env.example` has no `RENDER_API_KEY`-style entry (only `RENDER_APP_URL`, which is the app's own public ngrok/deploy URL, unrelated to the Render *management* API); `scripts/` has no existing log-export tooling; `docs/operations/DEPLOYMENT.md`/`RUNBOOK.md` reference the service only by its public URL (`my-bot-jqz2.onrender.com`), never a service ID (`srv-...`) or an API-key variable name.

**This is a hard, repo-unresolvable gap — see §13, item 1.** The safe next step is for the owner to run a names-only check in their own terminal (never printing the value), e.g. in PowerShell: `Get-ChildItem Env: | Where-Object Name -match 'RENDER' | Select-Object Name` — and report back only the variable *name(s)* that exist.

### 6.2 Service identifier

Not found documented anywhere in the repo as a `srv-...` id. The public hostname `my-bot-jqz2.onrender.com` (docs/operations/DEPLOYMENT.md, RUNBOOK.md) implies a service name, but Render's API keys logs by service **ID**, not by hostname — the exact `srv-...` value needs to come from the Render Dashboard (Settings → service info) or `GET /v1/services` filtered by name, once a credential exists to make that call at all.

### 6.3 Supported log-query method — **not verified live this session**

Attempted to confirm Render's current Logs API shape directly against `api-docs.render.com`/`render.com/docs` via `WebFetch` (three URLs tried: the API reference page, the docs root, the log-streams doc page) — **all three returned HTTP 403** (the docs site's bot protection blocks this session's fetcher; not a credential or network-policy issue on this session's side, and not something a code change here can fix).

What follows is training-knowledge, **explicitly flagged as unverified against current live documentation** — do not treat as confirmed fact, and re-verify against `https://api-docs.render.com` directly (from a browser or an authenticated tool) before writing any exporter code: Render's REST API (`api.render.com/v1`) has historically exposed a logs-listing endpoint accepting a resource/service-id filter, a time-range window (`startTime`/`endTime`), a `limit`, and time-window-based pagination (fetch a window, use the last record's timestamp as the next window's start) rather than an opaque cursor token — authenticated via an `Authorization: Bearer <API_KEY>` header using a key generated under Account Settings → API Keys. **Exact parameter names must be confirmed live before implementation** — this is the second hard gap for §13.

### 6.4 Proposed exporter design (design only, not implemented, not executed)

- **Trigger**: a new standalone script, e.g. `scripts/render_log_export.py` — explicitly **not** wired into `scheduler.py`/`worker.py` in this planning-only task, and not registered anywhere that would cause it to run automatically.
- **Read-only**: performs `GET` requests only; never calls any Render mutation endpoint (deploy, restart, env-var-write, etc.) — this satisfies "no runtime or production-service changes."
- **Cursor**: a time-window cursor (last exported record's `timestamp`, stored in the checkpoint file below), not a byte-offset or line-count cursor — resilient to Render's own log retention/rotation, and naturally supports catch-up (a missed day just means a wider `startTime`→`now` window on the next run, still only downloading records after the last checkpoint).
- **Storage** (outside Git, per the task's explicit requirement):
  - Raw exports: `render_logs/YYYY-MM-DD.jsonl` — one JSON object per line, one file per calendar day (UTC), append-only within a day, new file at day rollover.
  - Checkpoint: `render_logs/.checkpoint.json` — `{"last_exported_timestamp": "...", "last_run_at": "...", "service_id": "..."}`. A single small JSON file, not a database, so "last successful export" survives a crashed mid-export run cleanly (checkpoint is only updated after a batch is durably written).
  - Derived database (if a future phase wants queryable storage, e.g. SQLite): `render_logs/render_logs.db` — mentioned by the task explicitly; not designed in detail here since no consumer of it exists yet in this planning-only slice.
- **`.gitignore` additions** (proposed, not yet applied — see §11 for why this one edit is deferred to the implementation PR rather than made now):
  ```
  render_logs/
  ```
  (A directory-level ignore covers the daily JSONL files, the checkpoint, and the derived `.db` file in one line, consistent with this repo's existing `.gitignore` style of directory-level ignores like `reports/runtime/` and `output/`.)
- **Cadence**: daily, via a manual or `cron`-triggered run (not `scheduler.py`, which runs inside the live Flask process — an export tool with its own Render API credential should not share a process/lifecycle with the production bot, to keep the credential's blast radius separate from the app's own secrets). Catch-up is a property of the cursor design (§ above), not a separate code path.
- **Never executed in this task**: no script file has been created; this is a design for the owner to approve, per the task's own explicit constraint ("Do not execute the exporter until the owner approves the command and destination path").

---

## 7. Feature-Flag Plan

**Existing-flag search first** (per the task's instruction): `grep -n "FEATURE_TURN\|TURN_COORDINATOR\|SHADOW" feature_flags.py` — no existing flag name matches "TurnCoordinator" or a Shadow-decision concept for this program. `feature_flags.py`'s own docstring registry (the file's stated single source of truth for flag defaults/purpose) lists five existing three-state (`off`/`shadow`/`enforce`, or `off`/`shadow`/`on`) flags: `FEATURE_TOOL_AVAILABILITY_FILTER`, `FEATURE_EVIDENCE_FINALIZER`, `FEATURE_PA01_ENFORCEMENT_STATE`, `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE`, `FEATURE_CORE_REASONING_LEADS_STATE` — each read through its own dedicated `get_*_state()` accessor, never `is_enabled()`. This is the repo's established canonical tri-state feature-flag contract, not a one-off pattern.

**Proposal**: `FEATURE_TURN_COORDINATOR_SHADOW_STATE`, three-state (`off` default / `shadow` / `enforce`), accessed via a new `get_turn_coordinator_shadow_state()` function in `feature_flags.py`, following the exact precedent of `get_evidence_finalizer_state()` (`feature_flags.py:284`). This satisfies the task's instruction two ways at once: it reuses "an existing canonical tri-state feature-flag contract" (the repo's own established pattern) rather than inventing a bespoke two-state flag that would break convention, while still meeting "no enforcement path in this implementation slice" — `enforce` is defined as an **accepted value with no behavioral difference from `shadow`** in this slice, exactly mirroring how `FEATURE_EVIDENCE_FINALIZER`'s `enforce` value is accepted but "still shadow-only in PR-RP4" (per that flag's own docstring, `feature_flags.py:53-56`) until a separate, later PR (RP5) actually wires enforcement. A future Phase 3 implementation PR is what would give `enforce` real teeth here, not this one.

Required semantics (all satisfied by the above): default `off` (no computation, no logging, hook call sites are no-ops per §3.3 point 4); `shadow` computes and logs only (§5's record, never acts); no code path in this slice reads the flag and then changes routing/reply/tool/approval behavior.

---

## 8. `DESTRUCTIVE_ENTITY_REQUEST` Signal Prerequisite

**Confirmed absent from runtime** (§1.3): 0 matches anywhere outside docs. The frozen contract's own §3.2 already notes this doesn't block contract approval, only blocks Shadow classification of real destructive requests specifically (`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`'s "סטטוס-מימוש" note) — this section is exactly that missing piece, planned only.

**Design constraint**: `core/router/intent_router.py`'s `_RULES` list (`:23-100`) is **live** — it feeds `detect_intent()`'s return value, which `route_request()` and therefore the *real* running router consult for actual `Handler` selection (§1.3, §1.6). Adding a destructive-intent rule directly to `_RULES` would risk changing live routing behavior the moment the rule matches something today's router currently treats differently — a direct violation of "the legacy runtime remains unchanged." Even adding an inert new `Intent.DESTRUCTIVE_ENTITY_REQUEST` string constant to the shared `Intent` class (`core/router/route_decision.py:17`) touches a file the live router reads from, which is avoidable.

**Proposed design**: a fully isolated, new, additive-only module — e.g. `core/router/destructive_entity_signal.py` — exposing one pure function, e.g. `detect_destructive_entity_signal(text: str) -> DestructiveEntitySignalObservation`, with its own **locally-scoped** sentinel value (not added to the shared `Intent` class), doing its own regex match for destructive verbs (מחק/תמחק/הסר/תוריד and equivalents) combined with entity-reference context (contact/lead keywords, or a phone-number-shaped substring — reusing existing phone-pattern regex from `core/ingress_classifier.py` by reference/import, not by copy, to avoid a second maintained copy of that pattern). This function is called **only** from the Shadow computation function (§3.2) — never imported by `core/router/router.py`, `core/router/intent_router.py`, or anything on the live routing path. Its output feeds `IntentSignal(intent="destructive_entity_request", ...)` purely inside the Shadow record (§5); the string literal never needs to exist in the shared `Intent` class at all for Shadow-only comparison purposes.

This satisfies every constraint in the task's item 8 simultaneously: explicit destructive wording can win in the *computed Shadow decision* (comparable against `capture_signal` per the frozen contract's §3.2 precedence rule) without the legacy runtime importing, calling, or being affected by the new module in any way; no delete/archive/Do-Not-Contact action is proposed or executed (the function only classifies text, it has no write path, no tool call, no reply-emission capability at all); it can exist and accumulate Shadow observations before Phase 2 exit, since the frozen contract's approved 20-case Shadow quota requires ≥3 "Destructive Request vs Capture" observations (`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §8).

---

## 9. Tests — `earliest_enforcement_phase = 2→3` Scenarios Mapped to Test Types

The frozen contract (`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`, Acceptance Corpus header table) already tags all 25 scenarios; the 19 tagged `2→3` are: **1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 18, 19, 20, 21, 22, 23, 24, 25**. Scenarios 9-10 (phase 4), 14-15 (RP5 gate), 16-17 (phase 6) remain documented in the corpus and are **not** mapped to any Phase 2 test file below — they must not block Phase 2 implementation or the Phase 2→3 exit gate, per the contract's own §8 (already fixed for this exact circularity in the prior round).

| Test type | Scope | Proposed file | Scenarios covered |
|---|---|---|---|
| **Deterministic unit fixtures** | Pure precedence-decision logic: constructed `TurnSignals` in, `TurnDecision`-shaped output out — no Flask, no Airtable, no real signal providers, following the existing `test_bugNNN_*.py` / `chk()`-helper convention (`core/router/test_router.py`'s `TESTS` list-of-tuples pattern is the closest existing precedent for this repo). | New: `test_turn_coordinator_shadow_decision.py` (root-level, auto-discovered by CI's `test_*.py` glob per `.github/workflows/ci.yml:60-63`) | 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 18, 19, 20, 21, 25 (precedence outcome), plus 22, 23, 24 layered as `reason_code`/echo assertions on the same fixtures |
| **Current-vs-coordinator comparison tests** | Feeds the same synthetic (or captured-shape) input through *both* the legacy path (§4's mapping functions) and the new Shadow computation, asserts the `ShadowDecisionRecord`'s `disagreement` field is `"agree"` for all 19 scenarios pre-rollout. Requires §4's legacy-normalization functions to exist as testable units, not just inline in `app.py`. | New: `test_turn_coordinator_shadow_comparison.py` | Same 19, as comparison pairs rather than isolated decisions |
| **Channel integration tests** | Exercises the real webhook handlers (`_webhook_telegram_impl`/`_webhook_whatsapp_impl`) via Flask's test client, flag `shadow` on, asserting **zero behavioral diff** — identical reply text, reply count, `_pending_approvals`/`bus`/`ActionGateway` state before vs. after, with flag off vs. `shadow` — formalizing the manual-curl pattern CLAUDE.md already documents ("POST simulated Telegram/WhatsApp webhook payloads with curl") into an automated regression check specific to the Shadow hook's non-interference claim (§3.3). | New: `test_turn_coordinator_shadow_noninterference.py` | Not scenario-specific — a cross-cutting proof test that §3.3's claim holds for real webhook traffic shapes, not just the pure unit fixtures |
| **Incident replay fixtures** | Reuses the frozen contract's own §8 item 4 requirement (Incident Replay & Classification) — captures the real text/state from the phantom-approval incident (scenario 11) and the BUG-129 self-output-ingestion incident (scenario 21), replays through the Shadow computation, asserts `PREVENTED`. This is infrastructure the contract's *own* Shadow Exit Criteria already requires before Phase 2→3 — building the fixture mechanism is in-scope for this implementation slice even though the actual 7-day production observation window is a later runtime activity, not achievable inside a planning/test-authoring task. | New: `test_turn_coordinator_incident_replay.py` | 11, 21 (the two `2→3`-tagged incidents; scenario 16's concurrency incident is explicitly Phase 6's own gate per the contract, not replayed here) |

All four new files are root-level `test_*.py`, matching the existing convention CI already auto-discovers — no CI workflow change is needed to pick them up (verified: `.github/workflows/ci.yml:60-63`'s `for f in test_*.py` loop requires no modification).

---

## 10. Cross-Layer Impact Matrix — Phase 2 Shadow Implementation Slice

**Distinct from `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §9** (which describes the frozen *contract's* eventual full impact) and from `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1.6 (which describes *PR #446*, a docs-only PR). This matrix is for the **Phase 2 Shadow implementation slice specifically** — the first actual runtime code this program would produce, following the same precedent §1.6 established (a slice/PR-level matrix can differ from the contract-level one).

### Layer 1 — Core Reasoning / BUG-104
**touched: not touched.** Proof: no design element in §1-§9 above references `core/leads_reasoning_projection.py`, `core/adapters/leads_adapter.py`, or `FEATURE_CORE_REASONING_LEADS_STATE`; `grep` for these across this document returns 0 matches outside this evidentiary sentence itself. No new coupling: the Shadow hook (§3) reads only `_pending_approvals`/`event_bus`/`ActionGateway`/`intent_router`/`ingress_classifier` — none of which import from BUG-104's module tree.

### Layer 2 — TurnCoordinator
**touched: directly.** This slice is TurnCoordinator's first actual runtime code.
- **input impact**: real `TurnSignals` construction begins (§2), even if partial (2 of 7 fields close to reusable, the rest needing new adapters/design per §2's table) — no longer purely a documented type.
- **output impact**: `ShadowDecisionRecord` (§5) is a new, real, logged artifact — but explicitly **not** `TurnDecision` acted upon by anything; no `selected_handler` from this slice is ever consulted by a real handler.
- **authority impact**: **none** — §3.3 proves the hook cannot alter legacy state; Shadow computation has read-only access to every store it touches.
- **shared identifiers**: `ShadowDecisionRecord`, `compute_and_log_shadow_decision()`, `detect_destructive_entity_signal()` — all new, none redefine an existing name from another layer.
- **invariants**: the frozen contract's `PendingReplySignal` validity rules (§1.1) become real code for the first time in this slice (used to compute `pending_reply_valid` in §5's schema) — must be unit-tested against the contract's own text, not reinterpreted.
- **failure semantics**: §3.3 point 3 (blanket `try/except`, degrade to logged error, never propagate).
- **observability**: the entire point of this slice — `ShadowDecisionRecord` logging is the new observability surface.
- **cross-layer tests**: §9's four new test files are exactly this slice's cross-layer test obligation, satisfied within the slice itself (not deferred).

### Layer 3 — F52 / Phase 4C Action & Tool Contract
**touched: indirectly, read-only.** The Shadow computation reads `tool_registry.py`'s `get_availability()` conceptually (§2 field 5's closest analog) if/when `capability` is built out beyond a placeholder, and correlates `contract_id`/`action_id` (read-only, §1.5/§1.8) — but never calls `dispatch_tool()`, `enforce()` in write-consequential mode, or `action_validator.validate_action()`. No `ToolMeta`/dispatcher code is modified. Proof of non-mutation: §3.3 point 1 lists every read call by name and confirms none of the mutating counterparts (`dispatch_tool`, `propose_action`, `.pop()`, `.request_approval()`) appear in the Shadow function's design.

### Layer 4 — Durable Atomic Approval
**touched: indirectly, read-only.** Same proof as Layer 3 — `find_live_contracts()`, `bus.peek()`/`find_pending_tool_approval()`/`find_pending_by_business_fingerprint()`, and `_pending_approvals` dict reads are all read-only per §1.5's own citations; none of `ActionGateway.approve()`, `.propose_action()`, `.pop()` (event_bus), or `_pop_pending_approval()`/`_add_pending_approval()` are called from the Shadow path. `TurnActionReference` (frozen contract §6) is **not** constructed by this slice at all — Phase 2 Shadow has no cross-turn correlation need yet (that's Phase 4/Phase 6 territory per the contract's own phase tagging), avoiding any premature use of that type.

### RP4/RP5 Evidence Finalization guard (`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1.5)
**applies: no, for this specific slice** — narrower than the frozen contract's general "applies: yes." Phase 2 Shadow compares **handler selection** (`current_handler` vs `coordinator_selected_handler`), not **evidence/grounding claims** (was a claimed success actually verified) — that comparison dimension belongs to scenarios 14-15, explicitly tagged `RP5 gate` and out of scope for this slice (§9). This slice's `ShadowDecisionRecord` (§5) contains no field asserting whether an outcome was "verified" — deliberately, to avoid needing RP4/RP5 machinery before its own gate is ready, and to avoid the exact category of mistake (`core/anti_hallucination.py` §1.5 already flagged) of a layer inventing its own grounding check. If a future revision of this slice's schema wants to add such a field, it must route through RP4/`core/turn_evidence.py`, never a new validator — noted here as a standing constraint on any amendment to §5, not just a one-time check.

---

## 11. Implementation-Slice Plan — Exact Files Expected to Change

**New files** (all additive, none modify existing behavior by themselves):
- `core/turn_coordinator_shadow.py` — `ShadowDecisionRecord` (§5), `compute_and_log_shadow_decision()` (§3.2), the §4 legacy-normalization functions as separately-testable units (not inlined into `app.py`).
- `core/router/destructive_entity_signal.py` — `detect_destructive_entity_signal()` (§8), fully isolated from the live `_RULES`/`Intent` class.
- `test_turn_coordinator_shadow_decision.py`, `test_turn_coordinator_shadow_comparison.py`, `test_turn_coordinator_shadow_noninterference.py`, `test_turn_coordinator_incident_replay.py` (§9).

**Modified files** (minimal, additive-only diffs):
- `feature_flags.py` — add `FEATURE_TURN_COORDINATOR_SHADOW_STATE` to the docstring registry (per the file's own "every flag must appear here" convention) and `get_turn_coordinator_shadow_state()` (§7), following `get_evidence_finalizer_state()`'s exact shape.
- `app.py` — two new call sites (Hook A, Hook B, §3.2), each a single guarded call to `compute_and_log_shadow_decision(...)`; no existing line in `app.py` is changed, only new lines added at the two hook points.

**Explicitly deferred, not part of this slice** (flagged so a future implementer doesn't assume they're included):
- `.gitignore` addition for `render_logs/` (§6.4) — deferred to whichever PR actually adds `scripts/render_log_export.py`, since adding an ignore rule for a directory that doesn't exist yet is harmless but premature; bundling it here would blur this slice's actual scope (Shadow decision computation) with an unrelated ops-tooling concern.
- `scripts/render_log_export.py` itself — design only (§6.4), not written, per the task's explicit "do not execute... until the owner approves."
- Any change to `core/turn_envelope.py`, `route_decision.py`'s `Intent` class, or any file on the live routing/reply/approval path — none are needed for this slice, and §8's design specifically avoids needing to touch `Intent`.
- `CapabilityScope`/`MessageKind`/`last_outbound_kind` full implementations (§2 fields 5, 7) — this slice's `ShadowDecisionRecord` (§5) does not include a `capability`/`last_outbound_kind` field precisely because no source of truth exists yet; adding placeholder/constant values for them would misrepresent the comparison as more complete than it is. Owner-decision item (§13) covers whether to build them now or defer further.

---

## 12. Test & Rollout Plan

1. **Land the 4 new test files (§9) and the 2 new source files (§11) with the flag hardcoded `off`** — CI runs them, but production behavior is provably unchanged (flag off ⇒ hook call sites are no-ops per §3.3 point 4). This is the only state in which a PR for this slice should be opened, per the task's "do not open an implementation PR... until the Planning Gate receives explicit owner approval" — i.e., this step happens only *after* §13's items are resolved, not as part of this planning task.
2. **Owner sets `FEATURE_TURN_COORDINATOR_SHADOW_STATE=shadow` on a non-production environment first** (if one exists — needs confirmation, see §13), or directly in Render production behind the existing operator-driven manual-flag-change process already used for every other three-state flag in this repo (`RP5_PREFLIGHT_BLOCKER.md`'s own precedent: "an operator with Render dashboard access sets the flag... per the same manual process already used for other three-state flags").
3. **Observation window**: the frozen contract's §8 is explicit and already-approved — 7 consecutive days, ≥100 `TurnDecision`s, ≥20 contested-signal cases matching the approved category split, 0 unexplained disagreements, 100% of the 19 Phase-2-tagged Acceptance Corpus scenarios passing in automated re-runs, incident replay 100% `PREVENTED` for the `2→3`-tagged incidents (11, 21), explicit owner sign-off — this Planning Gate does not re-derive those criteria, it only confirms the implementation slice is capable of producing the data they require.
4. **No enforcement, no `enforce` value activation**, in this slice or its rollout — `enforce` stays an accepted-but-inert value (§7) until a separate, later Phase 3 Planning Gate (not this document) authorizes real routing changes.

---

## 13. Owner-Decision Table

Only items that cannot be resolved from the repository:

| # | Decision needed | Why it can't be resolved here |
|---|---|---|
| 1 | Exact Render API credential environment-variable name, and confirmation it's set | This session has zero access to the owner's local Windows terminal environment — genuinely unreachable, not merely unsearched (§6.1). Needs the owner to run a names-only check locally and report the name(s) only. |
| 2 | Render service ID (`srv-...`) for the `my-bot-jqz2` service | Not documented anywhere in the repo (only the public hostname is); requires either Dashboard access or an authenticated API call this session cannot make (§6.2). |
| 3 | Exact Render Logs API query-parameter names and pagination shape | `WebFetch` was blocked (HTTP 403) on all three attempted doc URLs this session — a genuine live-verification gap, not an assumption I chose not to check (§6.3). Needs confirmation against `api-docs.render.com` before `scripts/render_log_export.py` is written. |
| 4 | Whether `_pending_approvals`/`event_bus.PendingActionsStore`/`ActionGateway` are on a known consolidation path, or intended to coexist indefinitely | `AI_CONTEXT.md` has no note on this; `FEATURE_ACTION_GATEWAY`'s shadow-gating (`app.py:1122`) suggests `ActionGateway` is the intended eventual canonical store, but that's my inference from a flag name, not a documented decision. Affects whether §4's multi-store mapping is a permanent design or a temporary one this slice should build for. |
| 5 | Whether to build minimal `CapabilityScope`/`last_outbound_kind` providers now (partial fidelity, e.g. hardcoded-`available` constants) or omit them from `ShadowDecisionRecord` entirely until real sources exist (§2 fields 5/7, §11) | Both are legitimate scope choices with different implementation cost and different Shadow-comparison completeness; no repo precedent settles which the owner prefers for this specific slice. |
| 6 | Whether a non-production Render environment exists to run `shadow` mode against before touching the production flag (§12 step 2) | Not documented in `docs/operations/DEPLOYMENT.md`/`RUNBOOK.md` — those describe one Render service (`my-bot-jqz2`), no staging environment is named. |

---

## 14. Final Status

```
READY FOR OWNER DECISION
```

Planning and research for Phase 2 Shadow are complete and grounded (10 required research areas covered, Cross-Layer Impact Matrix filled with proof-of-non-impact/proof-of-read-only-access, implementation-slice plan names exact files, test plan maps every `earliest_enforcement_phase=2→3` scenario). This is **not** `PLANNING BLOCKED` — no Impact Matrix gap remains unfilled. It is **not** `READY FOR PHASE 2 SHADOW IMPLEMENTATION` — six genuine owner-decision items remain (§13), three of them (1-3) hard blockers for the Render log-export sub-piece specifically, and three (4-6) real design choices affecting the main Shadow-decision slice that this document deliberately did not resolve unilaterally. No runtime code, no flag change, no PR has been opened, consistent with the task's explicit constraint.
