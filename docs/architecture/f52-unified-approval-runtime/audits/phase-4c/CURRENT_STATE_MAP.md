# Phase 4C — Current-State Approval Runtime Map

Program: F52 — Unified Approval Runtime Migration and Implementation
Document role: Latest verified current-state runtime audit
Historical research identifier: Phase 4C
Status: Verified research baseline

Research baseline: `origin/main` at `4d3787e6e6fcbc93bd5a30f62f0834136b706f06` (2026-07-14). This document is a static code and test audit. It does not assert deployed feature-flag values.

## Method and counting

An **entry point** is a distinct inbound route, callback, command/reply interpreter, scheduler job, or internal proposer that can begin an approval-like interaction or a business mutation. A read-only endpoint is included only when it is part of approval presentation. A **direct execution path** is a proven path to a provider/business-state write that does not pass both `ActionGateway.approve()` and the PostgreSQL atomic claim. This audit found **50 entry points** and **28 direct execution paths**. Several entry points share one implementation; they remain separate when requester, authority, or provider behavior differs.

Labels used below:

- Approval: a different authorized identity permits a mutation.
- Self-confirmation: the requester confirms a frozen action under the narrow `self_confirm` policy.
- Selection: chooses an item/interpretation and is not authority by itself.
- Read-only: no mutation.
- Notification: outbound message without business-state mutation.
- Pre-authorized bounded mutation: deterministic operational persistence whose authorization is implicit in enabling the workflow; this is a classification, not proof that the policy has been formally approved.

## Canonical runtime that already exists

`ActionContract` freezes tenant, canonical requester, tool/payload, fingerprint, origin, policy, trusted source, context-integrity facts, idempotency key, actors, timestamps, status and version ([core/action_gateway.py:136](../../../../../core/action_gateway.py#L136)). `ExecutionLedger` persists a proposal before indexing it, hydrates both RAM indexes on repository recovery, and persists lifecycle transitions before changing RAM ([core/action_gateway.py:355](../../../../../core/action_gateway.py#L355), [core/action_gateway.py:376](../../../../../core/action_gateway.py#L376), [core/action_gateway.py:400](../../../../../core/action_gateway.py#L400), [core/action_gateway.py:455](../../../../../core/action_gateway.py#L455)).

`ActionGateway.approve()` re-reads the contract, validates `approval` versus `self_confirm`, persists `approved`, and delegates execution ([core/action_gateway.py:1200](../../../../../core/action_gateway.py#L1200)). With atomic claims enabled, `_execute_contract()` delegates to `execute_with_atomic_claim()`; only a PostgreSQL `ACQUIRED` claim reaches the dispatcher, and database unavailability fails closed ([core/action_gateway.py:1301](../../../../../core/action_gateway.py#L1301), [core/action_gateway_atomic_executor.py:19](../../../../../core/action_gateway_atomic_executor.py#L19), [core/atomic_claim_repository.py:45](../../../../../core/atomic_claim_repository.py#L45)). Provider output is verified before `completed`; uncertain evidence remains `outcome_unknown` ([core/action_gateway.py:1487](../../../../../core/action_gateway.py#L1487)).

This runtime is feature gated. The singleton receives `ActionContractRepository` only when `FEATURE_ACTION_CONTRACT_PERSISTENCE` is enabled ([core/action_gateway.py:1826](../../../../../core/action_gateway.py#L1826)); the repository and atomic-claim flags are default-off in source ([feature_flags.py:47](../../../../../feature_flags.py#L47)). Therefore code proves capability, not live enablement.

## Current-state matrix

Compact values: `AC` = canonical ActionContract, `PG` = PostgreSQL atomic claim, `EB` = RAM-only EventBus pending store, `AP` = Airtable Approvals display projection. “Direct” means provider execution remains possible without AC+PG.

| ID | Channel/source | Entry point | Action/tool and classification | Policy source | Requester / approver / tenant | Pending and restart | AC / PG / dispatcher / provider evidence | Projection/UI | Direct? | Tests | Risk | Phase 4C destination |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AP-01 | Telegram or Twilio Agent | `run_agent()` tool loop | Seven agent-exposed `requires_approval` tools; approval | Tool Registry metadata | `resolve_identity`; callback approver separately resolved; tenant from identity | EB 30m plus AC when proposal succeeds; EB is lost on restart | AC proposed by `_queue_approval`; callback may use PG+dispatcher+evidence | Telegram buttons keyed by EB ID | Yes, callback fallback | `test_pr0c_telegram_callback_gateway.py:137-208` | P0 | Durable AC proposal is the only pending authority; presentation stores AC ID |
| AP-02 | Telegram callback | `_handle_approval_callback_impl`, `approve:` | Approval | Contract policy if contract recovered; otherwise UI action | callback identity role checked; contract found by recomputed fingerprint | Pops EB before execution; AC durable only if enabled | AC→approve→PG when found; otherwise direct dispatcher | edits Telegram message | Yes | same test deliberately asserts fallback | P0 | Resolve immutable contract ID and fail closed |
| AP-03 | Telegram callback | `_handle_approval_callback_impl`, `reject:` | Rejection | EB/UI | callback role checked | EB removed; linked AC is not rejected | no PG/provider | edits Telegram message | No write, but stale AC | `test_pr0c_telegram_callback_gateway.py` lacks reject/AC test | P1 | `ActionGateway.reject(contract_id)` only |
| AP-04 | Telegram/Twilio text | `run_agent()` confirm word | Self-confirm or approval depending contract | `ActionContract.approval_policy` | canonical identity + current role | durable AC lookup first; flag-off EB only blocks free-text approval | AC→approve→PG→dispatcher when live | channel reply | No when AC exists | `test_bug074_approval_authority.py`, `test_bug076_lead_confirmation_policy.py` | P1 | Keep as channel parser over contract IDs/candidate set |
| AP-05 | Telegram/Twilio text | `route_combined_word()` | Selection plus authorization (`כן 1`, `לא 2`) | contract policy | stable canonical ID/current role | AC ledger/repository | selected AC approved/rejected; siblings rejected | text response | No | `test_bug070_combined_wording.py` | P1 | Preserve semantics; presentation adapter only |
| AP-06 | Telegram/Twilio text | `route_disambiguation()` | Selection followed by authorization | contract policy | stable canonical ID/current role | AC plus RAM disambiguation ordering | chosen AC approved, siblings rejected | numbered text | No | gateway tests; restart ordering gap | P1 | Persist or deterministically reconstruct candidate ordering |
| AP-07 | Telegram/Twilio text | `route_cancellation_word()` | Cancellation/rejection | contract ownership | canonical requester | AC durable | rejects live contracts; no provider | text response | No | gateway tests | P1 | Adapter resolves explicit candidate(s), gateway rejects |
| AP-08 | Telegram/Twilio text | reconfirmation FSM | Reconfirmation after interrupted context | ActionGateway context-integrity checks | canonical requester/current role | contracts durable; reconfirmation/override state RAM-only | eventual AC approval | text response | No | `test_bug_reconfirmation_oneshot_fsm.py` | P1 | Durable/derivable challenge, never new authority |
| AP-09 | Telegram/Twilio text | `_pending_approvals` in `run_agent()` | Router-level confirmation of original free text, not tool authorization | hardcoded router action set | chat ID/identity | RAM dict, 10m, lost on restart | recursively re-runs original text with `_skip_approval=True`; later tool gate still applies | text preview | No direct provider at this stage | sparse | P2 | Rename/classify as plan confirmation or retire after callers migrate |
| AP-10 | Telegram/Twilio lead preview | `_propose_lead_write()` | Lead add/update; approval/self-confirm by frozen fields | Gateway policy classifier | identity memory key/tenant/domain | durable AC when persistence on | AC→free-text approval→PG→dispatcher→Airtable evidence | text preview | No | `test_pr0_pending_approval_context_safety.py`, `test_bug076_lead_confirmation_policy.py` | P1 | Retain canonical path |
| AP-11 | auto-capture | `_write_one_lead()` | Lead create/update; currently writes without waiting | Gateway policy is computed but ignored by write step | requester identity/tenant/domain; no approver | AC may exist, then lifecycle manually patched | direct `airtable_create/patch`; no PG/dispatcher; record ID evidence | normal response | Yes | no test proves claim boundary | P0 | Remove direct write; approved/self-confirmed AC executes handler |
| AP-12 | lead batch preview | `resolve_pending_lead_preview()` | Batch confirmation | handler/session policy | requester identity/chat | session state; restart behavior unknown | each write path eventually calls lead handler; direct risk depends auto path | text preview | Yes through AP-11 | Tier-2 tests are preview-focused | P0 | Typed bulk proposal or individual ACs with explicit batch result |
| AP-13 | TMA | `api_create_project()` | Projects create; approval | endpoint role + `ACTION_RISK` + tma_write registry policy | initData identity; owner requester; owner approver | AC durable + AP projection | AC→PG→dispatcher→tma_write→Airtable+receipt | AP projection | No in queued branch | `test_phase_4b2_wiring.py` | P1 | Retain; replace local risk list with central policy |
| AP-14 | TMA | `api_update_lead_status()` | Leads patch; approval | endpoint role + TMA risk | initData owner/manager | AC+AP | canonical path | AP | No | wiring tests | P1 | Retain/adapt policy source |
| AP-15 | TMA manager | `api_manager_patch_lead()` | Leads patch; approval | hardcoded manager branch | initData manager; owner approves | AC+AP | canonical path | AP | No for manager | wiring tests | P1 | Retain |
| AP-16 | TMA owner | `api_manager_patch_lead()` owner branch | Leads patch; requester-authorized direct mutation | endpoint role | initData owner | none | direct `_at_patch`; no AC/PG/dispatcher; boolean evidence | HTTP response | Yes | endpoint tests do not prove claim | P1 | Decide explicit self-confirm/pre-authorized policy; do not infer from role |
| AP-17 | TMA manager | `api_manager_set_outcome()` | Lead outcome patch; approval | hardcoded manager branch | manager/owner | AC+AP | canonical path | AP | No for manager | wiring tests | P1 | Retain |
| AP-18 | TMA owner | `api_manager_set_outcome()` owner branch | Lead outcome direct mutation | endpoint role | initData owner | none | direct `_at_patch` | HTTP response | Yes | unknown | P1 | Explicit policy/typed tool |
| AP-19 | TMA manager | `api_manager_create_task()` | Task create; approval | hardcoded manager branch | manager/owner | AC+AP | canonical path | AP | No for manager | wiring tests | P1 | Retain |
| AP-20 | TMA owner | `api_manager_create_task()` owner branch | Task create direct mutation | endpoint role | initData owner | none | direct `_at_post` | HTTP response | Yes | unknown | P1 | Explicit policy/typed tool |
| AP-21 | TMA | `api_create_followup_task()` | Task create; approval | endpoint route | owner/manager, owner approver | AC+AP | canonical path | AP | No | wiring coverage partial | P1 | Retain |
| AP-22 | TMA | `GET /api/approvals` | Read-only approval list | canonical status actionability | initData identity; owner-only route | AP survives restart; canonical AC rechecked | no execution | AP | No | wiring tests 15-16 | P2 | Presentation only, as today |
| AP-23 | TMA | `POST /api/approvals/<id>` approve | Approval | contract policy + TMA provenance checks | initData owner; separate requester/approver | AC+AP | AC→PG→dispatcher; projection sync after canonical result | AP | No | wiring/concurrency/direct-bypass tests | P1 | Reference model for other adapters |
| AP-24 | TMA | same route reject | Rejection | canonical TMA checks | owner | AC+AP | `ActionGateway.reject`; no provider | AP | No | wiring/concurrency | P1 | Retain |
| AP-25 | TMA | `POST /api/approvals/bulk` | Multiple approvals; low-risk subset | TMA `ACTION_RISK` | owner | AC+AP | calls single-item helper per row; partial success and conflicts | AP | No | wiring test 8 and concurrency | P1 | Keep orchestration; centralize policy and explicit batch outcome |
| AP-26 | TMA | legacy Approvals row | Read-only legacy display | missing Action Contract ID | unknown requester; owner viewer | AP durable, no AC | execution refused | AP legacy_read_only | No | wiring test 2/15 | P2 | Drain/expire/read-only; never replay |
| AP-27 | scheduler | `followup_engine.scan_and_propose()` | Follow-up owner notification plus lead-memory count mutation | internal adapter registry | system proposes for lead; owner approves | AC + EB; EB lost on restart | callback canonical when found; `send_followup` updates lead memory | Telegram EB buttons | Yes via callback fallback | adapter/gateway tests; delivery asymmetry untested | P0 | AC projection adapter; separate notification from state mutation evidence |
| AP-28 | scheduler | `lead_recovery.scan_and_propose()` | Recovery draft notification | internal adapter registry | system/lead context; owner approves | AC+EB | canonical path sends owner notification | Telegram EB buttons | Yes via callback fallback | adapter tests partial | P0 | AC presentation only |
| AP-29 | voice | `_send_voice_approval_request()` approve | Save transcript; approval | registry internal tool | original media user data; owner Telegram identity used as contract requester | AC+EB | canonical callback path when contract found | Telegram buttons | Yes via callback fallback | media/gateway adapter tests | P0 | AC ID buttons; preserve original initiator separately |
| AP-30 | voice | `voice_edit:` then next text | Selection/edit followed by direct save | callback identity only; no AC policy | Telegram user ID; no stable tenant recheck at write | `_pending_voice_edits` RAM-only | direct Business Memory Airtable write | Telegram response | Yes | media tests mock writes | P0 | Edit creates replacement frozen AC; old contract rejected/superseded |
| AP-31 | Telegram/Twilio/Meta file | `handle_file_upload()` | Drive upload + Media Files metadata | feature/route role, no approval policy | channel user ID/domain | idempotency store; not AC | direct Drive then Airtable; partial failure can orphan Drive file | channel response/log | Yes | media tests mock providers | P1 | Typed handler; decide upload self-confirm policy |
| AP-32 | TMA upload | `api_upload()`→`handle_tma_upload()` | Same file mutation | endpoint role + feature | initData identity/domain | idem only | direct Drive+Airtable | HTTP response | Yes | upload tests | P1 | Same typed handler/policy as AP-31 |
| AP-33 | Twilio WhatsApp text | `_webhook_whatsapp_impl()`→`run_agent()` | Agent reads/tools and approval words | same Telegram core parser | signed webhook; canonical sender; domain from destination number | same AC/EB state; UX output TwiML | same AP-01/AP-04 paths | Twilio response | Yes via AP-02 fallback | WhatsApp webhook tests partial | P0 | Shared runtime, WhatsApp presentation/reply adapter |
| AP-34 | Twilio WhatsApp media | webhook→media handlers | voice/file mutations | media policy | signed sender; domain by `To` number | AC+EB for voice approval; idem for files | AP-29/AP-31 | owner Telegram buttons / TwiML | Yes | media adapter tests | P0 | Channel-neutral contract; channel-specific target |
| AP-35 | Meta WhatsApp text | `webhook_meta_whatsapp()` | Agent path only if `META_OUTBOUND_ENABLED`; outbound is stub | flag + shared Agent policy | signed sender; destination domain | same core stores if enabled | can run Agent mutations, but no reply delivery | JSON stub | Yes if flag on | no end-to-end approval reply test | P1 | Do not enable mutation until reply adapter exists |
| AP-36 | Meta WhatsApp media | same webhook before outbound flag check | Drive/Airtable media mutation | media flag/path; notably precedes outbound guard | signed sender/domain | idem only | direct media write | log/JSON | Yes | partial mocks | P1 | Gate and type through common media handler policy |
| AP-37 | email scheduler | `poll_inbox()`→`bus.request_approval(send_email_reply)` | Intended approval; no executable handler | local event name | system/owner | EB only | no subscriber/tool, therefore no provider write | Telegram approval-like UI | No | adapter-gate tests | P2 | Remain disabled until typed tool exists |
| AP-38 | abandoned-lead scheduler | bounce→`bus.request_approval(send_bounce)` | Intended approval; no executable handler | local event name | system/owner | EB only | no subscriber/tool | Telegram UI | No | adapter-gate tests | P2 | Remain disabled until typed tool exists |
| AP-39 | abandoned-lead scheduler | voice lead→task creation | Task create business mutation | job feature only | scheduler/system; tenant unknown | no durable approval | direct `airtable_add(Tasks)` | logs | Yes | embedded mock self-test only | P1 | Typed system action; decide bounded pre-authorization |
| AP-40 | interaction scheduler | `process_interaction()` log | Interaction Log persistence | job feature | scheduler/system; tenant/domain weak | Airtable only | direct `airtable_add` | later Telegram summary | Yes | embedded mock tests | P2 | Pre-authorized audit persistence with tenant/idempotency contract |
| AP-41 | interaction scheduler | `create_tasks_from_analysis()` | Creates business tasks from analysis | model output/job flag | scheduler/system; tenant not passed | no approval/claim | direct `airtable_add(Tasks)` | Telegram summary | Yes | mock-only | P1 | Typed AC requiring approval or narrow bounded policy |
| AP-42 | lead-memory scheduler | `job_flush_lead_memory()` | Persist accumulated lead state | feature/job | system; memory key | in-memory state to Airtable | direct add/update; no claim | logs | Yes | lead-memory tests | P2 | Pre-authorized bounded persistence, not human approval |
| AP-43 | game scheduler | `_job_weekly_quest_reset()` | Roll quest status/week | GAME_SCHEDULER | scheduler/system | Airtable | direct patch | Telegram notification | Yes | no boundary test | P1 | Bounded policy or typed batch action |
| AP-44 | TMA | asset update | Asset mutation | endpoint role | initData identity | none | direct `_at_patch` | HTTP | Yes | route tests unknown | P1 | Registered/typed action; explicit policy |
| AP-45 | TMA | venture create/update | Venture mutation | endpoint role | initData identity | none | direct `_at_post/_at_patch` | HTTP | Yes | route tests unknown | P1 | Registered/typed action |
| AP-46 | TMA/game | quest status and coins | Quest/Coins mutation | endpoint role | initData identity | none | direct patches/posts; multi-write partial-failure risk | HTTP | Yes | route tests partial | P1 | Typed transaction/batch outcome |
| AP-47 | TMA/game | task complete/checkin/daily checkin | Roadmap/coins/checkin mutation | endpoint role | initData identity | none | direct patches/posts | HTTP | Yes | route tests partial | P1 | Typed handler or explicitly bounded domain operation |
| AP-48 | Telegram command | `/done` / lead conversion | Lead/task business transition | command role | Telegram identity | none | direct TMA Airtable helpers | Telegram response | Yes | command tests | P1 | Typed action with evidence |
| AP-49 | Decision/Business update features | `cmd_decision`, `/update` | Decision Inbox/Business Memory/file writes | feature + command role | Telegram identity/domain | Airtable/Drive only | direct provider adapters | Telegram response | Yes | mostly mock/local | P1 | Phase 4C-4 typed handlers; keep default-off until policy defined |
| AP-50 | ingress/attribution/session/funnel | inbound capture helpers | Lead/event/session/UTM workflow state | feature and ingress rules | channel identity/domain; varies | Airtable/idempotency/session | direct provider writes | implicit | Yes | component tests | P2 | Separate bounded ingestion persistence from user-authorized business mutations |

## Exact call-chain maps

### 1. TMA proposal and approval

Proposal (six queued route branches):

`require_tma_auth()` validates Telegram initData HMAC and resolves stable identity ([tma_api.py:709](../../../../../tma_api.py#L709), [tma_api.py:788](../../../../../tma_api.py#L788)) → endpoint role check → `_queue_tma_write_approval()` checks durable persistence and atomic claims, calls `ActionGateway.propose_action(tool_name="tma_write", trusted_source="tma_api")` ([tma_api.py:444](../../../../../tma_api.py#L444), [tma_api.py:542](../../../../../tma_api.py#L542)) → repository saves AC → `_ensure_approval_projection()` finds/repairs/creates AP row with blank `CONTEXT_DATA` ([tma_api.py:617](../../../../../tma_api.py#L617)) → returns pending/projection-missing response. The route call sites are project create ([tma_api.py:1018](../../../../../tma_api.py#L1018)), lead status ([tma_api.py:1457](../../../../../tma_api.py#L1457)), lead patch ([tma_api.py:1545](../../../../../tma_api.py#L1545)), outcome ([tma_api.py:1596](../../../../../tma_api.py#L1596)), task create ([tma_api.py:1642](../../../../../tma_api.py#L1642)), and follow-up task ([tma_api.py:1706](../../../../../tma_api.py#L1706)).

Approval: `POST /api/approvals/<approval_id>` ([tma_api.py:2705](../../../../../tma_api.py#L2705)) → `_load_actionable_projection()` requires immutable AC ID ([tma_api.py:2477](../../../../../tma_api.py#L2477)) → `_claim_and_execute_approval()` re-reads AC and validates pending/tool/source/origin/policy/tenant ([tma_api.py:2510](../../../../../tma_api.py#L2510)) → `ActionGateway.approve(contract_id, approver, role)` → durable `approved` → PostgreSQL claim → `_make_dispatch_executor()` reconstructs frozen requester ([core/action_gateway.py:1718](../../../../../core/action_gateway.py#L1718)) → `dispatch_tool("tma_write", ..., execution_context)` → `tma_write()` verifies a live matching EXECUTING claim ([tools/approval_actions.py:239](../../../../../tools/approval_actions.py#L239)) → Airtable provider write and receipt ([tools/approval_actions.py:363](../../../../../tools/approval_actions.py#L363), [tools/approval_actions.py:398](../../../../../tools/approval_actions.py#L398)) → canonical lifecycle → projection sync ([tma_api.py:2434](../../../../../tma_api.py#L2434)) → JSON `{ok, message, status_code, projected_lifecycle_status, projection_sync_pending}`. `outcome_unknown` returns HTTP 202 and is not collapsed.

### 2. Telegram agent proposal

Telegram webhook → `run_agent()` → Claude `tool_use` → `tool_registry.enforce()` → if `meta.requires_approval`, `_queue_approval()` ([app.py:1983](../../../../../app.py#L1983), [app.py:2000](../../../../../app.py#L2000), [app.py:2047](../../../../../app.py#L2047), [app.py:730](../../../../../app.py#L730)) → `ActionGateway.propose_action()` plus `bus.request_approval()` → Telegram buttons contain `approve:<event_bus_id>` / `reject:<event_bus_id>`, not the AC ID. Return is approval-queued text to Claude. The AC save is durable when enabled; the displayed EB pointer is not.

### 3. Telegram callback approval

Webhook callback routing keeps `approve:`/`reject:` separate from unrelated callbacks ([app.py:2633](../../../../../app.py#L2633)) → `_handle_approval_callback_impl()` verifies current role ([app.py:983](../../../../../app.py#L983)) → looks up EB item and recomputes a business fingerprint → pops EB → if gateway flag on and matching pending AC found, `ActionGateway.approve()` → PG → dispatcher → provider/evidence. If lookup throws or no AC is found, code explicitly calls `dispatch_tool()` directly ([app.py:1098](../../../../../app.py#L1098), [app.py:1119](../../../../../app.py#L1119), [app.py:1137](../../../../../app.py#L1137)). It then manually patches any recovered contract lifecycle ([app.py:1179](../../../../../app.py#L1179)). Return is edited callback message. This is not fail-closed.

Reject pops EB and notifies but does not call `ActionGateway.reject()` for the linked contract ([app.py:1289](../../../../../app.py#L1289)).

### 4. Telegram free text, selection and reconfirmation

`run_agent()` resolves identity → ingress context gate → router-level `_pending_approvals` (raw-plan confirmation) → ActionGateway combined word → numbered disambiguation → status query → confirmation → cancellation ([app.py:1475](../../../../../app.py#L1475), [app.py:1562](../../../../../app.py#L1562)). A live AC is always preferred for confirm words, even if the gateway feature is off ([app.py:1636](../../../../../app.py#L1636)). `route_confirmation_word()` finds pending contracts, may request disambiguation/reconfirmation, and finally calls `approve()` ([core/action_gateway.py:912](../../../../../core/action_gateway.py#L912)). Selection alone only identifies a contract; authorization remains in `approve()`. Multiple live contracts produce a numbered choice. Combined approval+ordinal calls the same authority boundary. Cancellation calls `reject()`.

### 5. WhatsApp mutation paths

Twilio: signed `/whatsapp` → sender phone canonicalization → destination-number domain → MessageSid idempotency → `resolve_identity("whatsapp", sender)` → media handlers and furniture funnel → `run_agent(channel="whatsapp")` ([app.py:2825](../../../../../app.py#L2825), [app.py:2836](../../../../../app.py#L2836), [app.py:2850](../../../../../app.py#L2850), [app.py:2951](../../../../../app.py#L2951)). Text therefore shares ActionGateway parsers and the same EB-ID callback weakness, but Twilio has no WhatsApp-native approval presentation; internal media proposals target Telegram owner buttons.

Meta: signature/normalization/idempotency/domain are present ([app.py:2979](../../../../../app.py#L2979)). Media processing happens before the outbound-enable guard and may write Drive/Airtable ([app.py:3030](../../../../../app.py#L3030)); text skips `run_agent()` by default. When enabled, Agent runs but outbound remains a log-only stub ([app.py:3091](../../../../../app.py#L3091)). There is no Meta reply parser or durable WhatsApp presentation state.

### 6. EventBus-confirmed mutation

`bus.request_approval()` → `PendingActionsStore.add()` (RAM, 30m) → Telegram button → callback normally bypasses `bus.confirm()` for tool payloads and handles them itself. Generic `bus.confirm()` atomically pops then emits `<action>.confirmed` ([event_bus.py:242](../../../../../event_bus.py#L242), [event_bus.py:253](../../../../../event_bus.py#L253)). Static search found no production `bus.subscribe()` calls; therefore email/bounce events dead-end rather than write. Current real mutation authority is in the Telegram callback fallback, not in a subscriber. Follow-up, recovery and voice publishers now also propose ACs before creating EB presentation rows ([followup_engine.py:198](../../../../../followup_engine.py#L198), [core/lead_recovery.py:245](../../../../../core/lead_recovery.py#L245), [media_handler.py:277](../../../../../media_handler.py#L277)).

### 7. Scheduler/background mutation

`start_scheduler()` registers 23 jobs behind `_automation_guard()` ([scheduler.py:770](../../../../../scheduler.py#L770), [scheduler.py:825](../../../../../scheduler.py#L825)). Representative mutation chains:

- follow-up/recovery scan → AC proposal → EB/Telegram presentation → callback chain above.
- lead-memory flush every 10m → `lead_memory` → direct Airtable add/update.
- interaction scan every 15m → `save_to_interaction_log()` → direct Airtable add, then `create_tasks_from_analysis()` → direct Tasks adds ([interaction_engine.py:276](../../../../../interaction_engine.py#L276), [interaction_engine.py:358](../../../../../interaction_engine.py#L358)).
- abandoned scan → direct task creation ([abandoned_lead_worker.py:240](../../../../../abandoned_lead_worker.py#L240)); bounce approval is disabled because no adapter exists ([feature_flags.py:191](../../../../../feature_flags.py#L191)).
- weekly quest reset → direct Airtable patch ([scheduler.py:586](../../../../../scheduler.py#L586)).

### 8. Media/file mutation

Voice: channel webhook → `handle_voice_note()` → risky transcript → `_send_voice_approval_request()` → AC+EB → generic callback. The Edit callback instead pops EB, stores only domain/source in `_pending_voice_edits`, and the next text directly calls `_save_transcript_to_memory()` ([media_handler.py:213](../../../../../media_handler.py#L213), [media_handler.py:245](../../../../../media_handler.py#L245)).

File: Telegram/Twilio/Meta/TMA → `handle_file_upload()` → idempotency check → `drive_adapter.upload_file()` → `save_asset()` Airtable record ([media_handler.py:418](../../../../../media_handler.py#L418), [media_handler.py:444](../../../../../media_handler.py#L444), [media_handler.py:465](../../../../../media_handler.py#L465)). There is no claim and Drive may remain written if metadata persistence fails.

### 9. Direct dispatcher map for every approval-required tool

`dispatch_tool()` calls `tool_registry.enforce()` but never checks `meta.requires_approval` ([tools/dispatcher.py:136](../../../../../tools/dispatcher.py#L136), [tool_registry.py:265](../../../../../tool_registry.py#L265)). Thus any authorized in-process caller can invoke the following cases without an AC or PG claim. `tma_write` is the only tool with its own live-claim guard.

| Tool | Registry policy | Direct dispatcher target | Provider/business write | Direct-call result |
|---|---|---|---|---|
| `calendar_create_event` | approval, management | [tools/dispatcher.py:176](../../../../../tools/dispatcher.py#L176) | Google Calendar create | Executes |
| `gmail_draft` | approval, management | [tools/dispatcher.py:185](../../../../../tools/dispatcher.py#L185) | Gmail draft create | Executes |
| `gmail_send_draft` | approval, senior | [tools/dispatcher.py:187](../../../../../tools/dispatcher.py#L187) | Gmail send | Executes |
| `sheets_append` | approval, management | [tools/dispatcher.py:197](../../../../../tools/dispatcher.py#L197) | Sheets append | Executes |
| `airtable_add` | approval, internal | [tools/dispatcher.py:241](../../../../../tools/dispatcher.py#L241) | Airtable create; Leads has additional source gate | Executes for allowed table/source |
| `airtable_update` | approval, management | [tools/dispatcher.py:306](../../../../../tools/dispatcher.py#L306) | Airtable patch; Leads has source gate | Executes for allowed table/source |
| `crm_mark_payment_paid` | approval, senior | [tools/dispatcher.py:365](../../../../../tools/dispatcher.py#L365) | CRM/Airtable payment update | Executes |
| `media_save_to_memory` | approval, internal | [tools/dispatcher.py:380](../../../../../tools/dispatcher.py#L380) | Airtable Business Memory create | Executes |
| `send_followup` | approval, internal | [tools/dispatcher.py:386](../../../../../tools/dispatcher.py#L386) | owner notification + lead-memory mutation | Executes |
| `send_recovery` | approval, internal | [tools/dispatcher.py:394](../../../../../tools/dispatcher.py#L394) | owner notification | Executes |
| `tma_write` | approval, owner/manager | [tools/dispatcher.py:405](../../../../../tools/dispatcher.py#L405) | Airtable create/patch | Refuses unless live matching PG claim ([tools/approval_actions.py:327](../../../../../tools/approval_actions.py#L327)) |

The first ten are direct execution paths. The Agent loop itself does not take them because it checks `meta.requires_approval`; the boundary remains bypassable by other Python callers.

## Tool Registry authority and mismatch inventory

The registry contains 21 tools; 11 require approval ([tool_registry.py:49](../../../../../tool_registry.py#L49), [tool_registry.py:238](../../../../../tool_registry.py#L238)). `tools/schemas.py` exposes 17 tools to Claude ([tools/schemas.py:4](../../../../../tools/schemas.py#L4)). The four approval tools absent from agent schemas—`media_save_to_memory`, `send_followup`, `send_recovery`, `tma_write`—are intentionally internal ([tools/schemas.py:234](../../../../../tools/schemas.py#L234)). Static comparison found no agent-exposed schema absent from the registry.

Mismatches:

1. `requires_approval` is metadata consumed by `run_agent()` and EventBus, not an execution boundary in `enforce()` or `dispatch_tool()`.
2. TMA maintains separate `ACTION_RISK` values ([tma_api.py:392](../../../../../tma_api.py#L392)); bulk eligibility therefore is not derived from Tool Registry or contract policy.
3. Gateway has its own policy classifier (`approval`/`self_confirm`) for Leads ([core/action_gateway.py:106](../../../../../core/action_gateway.py#L106)). This is legitimate policy detail but not represented by Tool Registry metadata.
4. Router-level `_APPROVAL_REQUIRED_ACTIONS` applies to raw user intents, not tool execution ([app.py:77](../../../../../app.py#L77)); its “approval” terminology conflates plan confirmation with mutation authorization.
5. EventBus now derives `ACTIONS_REQUIRING_APPROVAL` from Tool Registry ([event_bus.py:186](../../../../../event_bus.py#L186)); no mismatch there.
6. `approvals_projection.py` correctly implements display mapping, but its header still describes the module as unwired even though TMA imports it—documentation drift ([core/approvals_projection.py:1](../../../../../core/approvals_projection.py#L1), [tma_api.py:2029](../../../../../tma_api.py#L2029)).

Future single source: Tool Registry should own coarse tool risk/approval requirements; a typed policy service using immutable proposal facts should own allowed policy variants and return the policy stored on AC. Dispatcher must enforce proof of a live canonical execution context for every approval-required tool, not only `tma_write`.

## EventBus authority map

| Event/action | Publishers | Store/restart | Confirmation/execution | AC/claim | Classification/destination |
|---|---|---|---|---|---|
| Agent tool names | `app._queue_approval` | EB RAM / lost | Telegram callback, not subscriber | AC sometimes; claim only when found | Presentation pointer today; downgrade to notification/projection |
| `media_save_to_memory` | media handler | EB RAM / lost | callback tool branch; edit bypass separate | AC proposed | Projection only after AC-ID migration |
| `send_followup` | followup engine | EB RAM / lost | callback tool branch | AC proposed | Projection/notification only |
| `send_recovery` | lead recovery | EB RAM / lost | callback tool branch | AC proposed | Projection/notification only |
| `send_email_reply` | email inbound | EB RAM / lost | no subscriber/tool | none | Dead approval UI; keep feature hard-disabled |
| `send_bounce` | abandoned worker | EB RAM / lost | no subscriber/tool | none | Dead approval UI; keep feature hard-disabled |
| non-tool `.confirmed` | callback emits event | no production subscriber found | no write | none | Observability only or delete after proven caller migration |

EventBus is presently a pending/presentation mechanism and, through the callback’s fallback, indirectly participates in execution authority. Its own `confirm()` is process-local and at-most-once only inside one process; restart loses items. `PendingActionsStore.pop()` is locked, but list/fingerprint iterations are not consistently locked ([event_bus.py:69](../../../../../event_bus.py#L69), [event_bus.py:90](../../../../../event_bus.py#L90)). It can remain for notifications, but it cannot be authorization or execution authority.

## Identity map

| Representation | Source/conversion | Use and lossiness |
|---|---|---|
| `Identity.tenant_id`, `user_id`, `external_id`, `display_name`, `role`, `allowed_domains` | registry/env resolution in `identity.py` ([identity.py:104](../../../../../identity.py#L104), [identity.py:234](../../../../../identity.py#L234)) | Full runtime identity. Display name is not stable authority. |
| `canonical_user_id` | normally `identity.memory_key = tenant_id:user_id` ([identity.py:127](../../../../../identity.py#L127)) | Stored on AC; stable requester lookup. Some legacy callers pass chat-derived values; audit each migration. |
| Telegram user/chat IDs | update/callback/TMA initData | Callback re-resolves current role; TMA validates signed initData. Chat ID is presentation target, not identity authority. |
| WhatsApp sender | Twilio/Meta phone → `resolve_identity("whatsapp", sender)` | Known owner maps to canonical owner; unknown sender maps to lead. Phone normalization and registry matching are the conversion boundary. |
| WhatsApp destination | `_channel_domain(to_number)` | Domain selection only. It is not a tenant selector; current tenant config statically supports `boss_hq` ([core/tenant_config.py:55](../../../../../core/tenant_config.py#L55)). |
| TMA requester/approver | signed initData identity; `_identity_ref` | Contract freezes requester identity; `approved_by` receives current owner identity separately. |
| scheduler/system | usually implicit function execution | No uniform canonical system identity, tenant, allowed domain, or delegation record. This is lossy and blocks general pre-authorization design. |
| `requested_by` strings in TMA payload | display/user reference | Audit/display only; canonical requester remains AC fields. |

The canonical executor reconstructs the frozen requester from AC and passes actual approver separately ([core/action_gateway.py:1750](../../../../../core/action_gateway.py#L1750)). TMA also checks contract tenant against requester/projection context. Direct handlers generally do not preserve this separation.

## State-store map

| Store | Authority today | Durable | Atomic/multi-instance | Notes |
|---|---|---|---|---|
| Airtable ActionContracts | canonical contract/lifecycle when persistence enabled | Yes | lifecycle uses expected status/version plus readback, but Airtable is not CAS | proposal lookup fail-closed; lifecycle audit |
| PostgreSQL `action_execution_claims` | sole execution ownership when atomic flag enabled | Yes | unique claim / multi-instance | must remain sole claim primitive |
| Airtable Approvals | TMA display projection | Yes | no execution authority | legacy rows read-only; `CONTEXT_DATA` blank |
| EventBus `PendingActionsStore` | Telegram presentation and legacy pending | No | process-local lock only | action ID is not AC ID |
| `app._pending_approvals` | router raw-text plan confirmation | No | no multi-instance coordination | stores original request, not frozen tool |
| Gateway RAM indexes | cache | No | per process | repository hydrates ID/fingerprint/user indexes |
| `_pending_voice_edits` | voice edit continuation | No | process-local | stores domain/source only; direct write follows |
| session/lead preview state | clarification and batch UX | varies; repository implementation-specific | not execution claim | should never become authorization evidence |

## Background job classification

All registrations are visible at [scheduler.py:825](../../../../../scheduler.py#L825). Repository code proves schedule and calls, but not deployed flags.

| Job | Class | Mutation/evidence/idempotency | Phase 4C implication |
|---|---|---|---|
| daily digest, daily collector, overdue payments, payment reminders, learning, audience/attribution reports, security reminder, weekly summary, daily game digest, boss battle | A/B | reads and/or sends notification | Keep outside approval runtime |
| pending cleanup | D | process-local EB cleanup | Retire with EB pending authority |
| daily git audit | E | may touch git/external state; default-off | Separate operational policy |
| schema snapshot archive | D/E | writes snapshot/Airtable; flag-gated | Bounded operational policy, not human approval by default |
| lead-memory flush | D | direct Airtable persistence; memory-key dedup semantics | Formalize bounded state persistence |
| follow-up scan, lead recovery | C | create AC, then EB presentation | Migrate presentation to AC ID |
| email inbound | E | dead approval adapter; feature forced off | Do not enable |
| abandoned scan | C/E | direct task create plus dead bounce adapter | Typed action/policy required |
| interaction scan | C/D | direct Interaction Log and Tasks writes; source dedup can fail open | Separate audit persistence from task creation |
| weekly quest reset | C/D | direct batch patches, no claim | Explicit bounded policy or approval |
| cost watchdog | D | mutates emergency control flag | Operational safety control, outside business approval runtime but needs audit |
| daily usage report | D | AI usage audit write | Bounded telemetry persistence |

## Non-tool/direct-write destinations

- File/media uploads should become a typed deterministic handler because one logical action spans Drive and Airtable and needs explicit partial/ambiguous evidence. Whether upload requires self-confirmation is a product policy question.
- Lead/session/inbound/UTM memory are ingestion/state persistence, not automatically approvals. Keep outside the human approval UI only if bounded fields, identity/tenant scope and idempotency are explicit.
- Interaction-derived Tasks, abandoned-lead Tasks, quest/game transitions, `/done`, Decision Hub, and Business Memory commands are business mutations. They need registered tools or typed AC handlers; UI selection alone is insufficient.
- TMA bulk remains orchestration over individual contracts. Never deserialize `CONTEXT_DATA` as executable payload.
- Notifications remain outside approval unless they also mutate counters/status; `send_followup` currently does both and must expose both evidence facts.

## Existing test authority

Strong boundary tests exist for durable proposal/restart dedup (`test_phase_4b_1a_durable_proposals.py:104-255`, `test_phase_4b_1a_lookup_correctness.py:106-264`), lifecycle persistence (`test_phase_4b_1b_durable_lifecycle.py:113-327`), atomic concurrency (`test_phase_4b0_1c_concurrent_approvals.py:49-201`), TMA projection/wiring (`test_phase_4b2_wiring.py:308-967`), and TMA direct-dispatch refusal (`test_phase_4b2_direct_dispatch_bypass.py:173-357`).

The Telegram callback test is a legacy-behavior test that migration must deliberately change: it asserts direct dispatch when the gateway flag is off and when no contract is found ([test_pr0c_telegram_callback_gateway.py:137](../../../../../test_pr0c_telegram_callback_gateway.py#L137), [test_pr0c_telegram_callback_gateway.py:184](../../../../../test_pr0c_telegram_callback_gateway.py#L184)). TMA tests are mostly mocked wiring tests; the PostgreSQL opt-in/concurrency suites prove the claim boundary separately. Media, scheduler and direct TMA business routes generally have mock/component tests, not end-to-end authorization/claim tests.
