# Phase 4C — Gap and Risk Report

Baseline: `origin/main` `4d3787e6e6fcbc93bd5a30f62f0834136b706f06`. Finding counts are **P0: 5, P1: 13, P2: 8**. Severity means architectural exposure in reachable code, not proof that a default-off or environment-gated path is active in production.

## P0 — approval-required mutation can bypass durable authorization

### P0-1 — Telegram approval callback explicitly fails open to direct dispatch

`_handle_approval_callback_impl()` tries to recover an AC by recomputed fingerprint, but a lookup exception logs that it is “falling back,” and absence of a contract calls `dispatch_tool()` directly ([app.py:1098](../../app.py#L1098), [app.py:1119](../../app.py#L1119), [app.py:1137](../../app.py#L1137)). This executes after only an EB item and callback role check: no durable authorization, no PostgreSQL claim, no canonical provider outcome. `test_pr0c_telegram_callback_gateway.py:137-193` deliberately asserts both fallback cases, so this is current intended legacy behavior rather than a hypothetical branch.

Impact: any approval-required agent tool can execute without AC+claim when persistence is disabled, EB and AC diverge, restart removes EB/AC cache, lookup fails, or a proposal silently never existed. Fix boundary: button must reference immutable contract ID; missing/unavailable contract fails closed.

### P0-2 — Tool Registry approval metadata is not enforced at dispatcher boundary

`tool_registry.enforce()` checks only tool existence and current role ([tool_registry.py:265](../../tool_registry.py#L265)). `dispatch_tool()` calls that method, emergency stop and input validation, but never evaluates `requires_approval` or verifies a canonical execution claim ([tools/dispatcher.py:136](../../tools/dispatcher.py#L136)). Ten approval-required tools therefore execute for any authorized in-process caller: calendar create, Gmail draft/send, Sheets append, Airtable add/update, mark payment paid, media memory save, follow-up, and recovery. Only `tma_write` independently requires a genuine active PostgreSQL claim ([tools/approval_actions.py:327](../../tools/approval_actions.py#L327)).

Impact: fixing one channel does not close internal/background/new-caller bypasses. Migration must add a dispatcher/tool boundary that accepts unforgeable gateway execution proof without blocking legitimate non-approval read tools.

### P0-3 — auto-capture lead handler ignores the proposed contract and writes directly

`_write_one_lead()` calls `ActionGateway.propose_action()` but then performs `airtable_patch()` or `airtable_create()` unconditionally ([core/lead_candidate_handler.py:401](../../core/lead_candidate_handler.py#L401), [core/lead_candidate_handler.py:455](../../core/lead_candidate_handler.py#L455)). The registry cross-check can classify an update as requiring approval, yet the write step does not inspect pending/approved status. It manually changes lifecycle afterward ([core/lead_candidate_handler.py:497](../../core/lead_candidate_handler.py#L497)).

Impact: a pending AC can coexist with an already-completed provider mutation; approval becomes cosmetic. Batch auto-capture inherits this path. The safe fix is to make the frozen handler execute through the normal claim/dispatcher path, not to add another direct lifecycle patch.

### P0-4 — voice “Edit” consumes approval UI state and directly writes Business Memory

The `voice_edit:` callback pops the EB item and stores only `domain`/`source` in RAM; the next text calls `_save_transcript_to_memory()` directly ([media_handler.py:213](../../media_handler.py#L213), [media_handler.py:245](../../media_handler.py#L245)). It neither rejects/supersedes the original AC nor creates a replacement contract for edited text.

Impact: a flow explicitly classified as requiring owner approval can mutate a different payload with no durable authorization, tenant recheck, claim, or restart recovery.

### P0-5 — default-off flags preserve the legacy bypass as a supported mode

`FEATURE_ACTION_GATEWAY`, contract persistence and atomic claims are source-default-off ([feature_flags.py:47](../../feature_flags.py#L47)). `_queue_approval()` still builds EB presentation and the callback intentionally dispatches directly when the gateway path is unavailable. Atomic executor itself also directly invokes its executor when the atomic flag is off ([core/action_gateway_atomic_executor.py:56](../../core/action_gateway_atomic_executor.py#L56)).

Impact: the target invariant is configuration-dependent. Phase 4C cannot claim a unified runtime until approval-required execution fails closed under every supported flag combination. This does not authorize changing deployment flags during research.

## P1 — restart, duplicate, identity, or partial-outcome risk

1. **Reject leaves canonical work pending.** Telegram `reject:` removes EB state but does not call `ActionGateway.reject()` ([app.py:1289](../../app.py#L1289)); after restart, durable pending lookup can resurrect the rejected action.
2. **EB presentation is RAM-only.** Its 30-minute store disappears on restart and its short action ID is the callback reference ([event_bus.py:28](../../event_bus.py#L28), [event_bus.py:41](../../event_bus.py#L41)). Durable ACs can become unapprovable from the original button; EB-only approvals disappear.
3. **Callback correlation recomputes a fingerprint instead of carrying AC ID.** The EB payload remains an independent mutable display object. Multiple equivalent contracts, TTL replacement, or normalization drift can select the wrong/no contract ([app.py:1005](../../app.py#L1005)).
4. **Numbered/reconfirmation/override state is partly RAM-only.** Contracts recover, but the displayed ordering/challenge context may not; a post-restart ordinal can be ambiguous ([core/action_gateway.py:1053](../../core/action_gateway.py#L1053), [core/action_gateway.py:1161](../../core/action_gateway.py#L1161)).
5. **Airtable lifecycle transition is optimistic read/patch/readback, not atomic CAS.** Expected status/version conflicts are detected after the fact, but two instances can race at Airtable ([core/action_contract_repository.py:184](../../core/action_contract_repository.py#L184)). PostgreSQL still prevents duplicate execution; audit fields can conflict.
6. **TMA has a second risk source.** `ACTION_RISK` controls low-risk bulk approval independently from Tool Registry/contract policy ([tma_api.py:392](../../tma_api.py#L392)). Policy drift can make bulk behavior disagree with canonical authorization.
7. **TMA owner branches write directly.** Owner lead patch/outcome/task paths bypass contracts while manager paths queue approval ([tma_api.py:1573](../../tma_api.py#L1573), [tma_api.py:1619](../../tma_api.py#L1619), [tma_api.py:1680](../../tma_api.py#L1680)). Role alone is being treated as implicit self-authorization without an explicit policy record or claim.
8. **File upload is a non-atomic two-provider mutation.** Drive upload precedes Airtable metadata; metadata failure returns an error while the file remains written ([media_handler.py:444](../../media_handler.py#L444), [media_handler.py:465](../../media_handler.py#L465)). Retry/idempotency and `outcome_unknown` semantics are not canonical.
9. **Scheduler-created Tasks lack uniform identity, tenant and idempotency.** Abandoned and interaction jobs write Tasks directly ([abandoned_lead_worker.py:240](../../abandoned_lead_worker.py#L240), [interaction_engine.py:358](../../interaction_engine.py#L358)). Model-derived task payloads are business mutations, not audit logging.
10. **No canonical scheduler/system principal.** Background jobs do not consistently freeze tenant/domain, system identity, delegation/policy or approver. This blocks safe generic pre-authorization.
11. **Follow-up evidence conflates notification and state mutation.** `send_followup()` increments `followup_count` even without checking owner-delivery success ([tools/approval_actions.py:83](../../tools/approval_actions.py#L83), [tools/approval_actions.py:112](../../tools/approval_actions.py#L112)). Its returned evidence only carries the output audit ID.
12. **WhatsApp has shared execution but no native approval adapter.** Twilio text can propose via shared Agent logic, while presentation is Telegram/EB-specific; Meta outbound is a stub, and Meta media can mutate before that guard ([app.py:2871](../../app.py#L2871), [app.py:3030](../../app.py#L3030), [app.py:3091](../../app.py#L3091)).
13. **Direct multi-write TMA/game paths have partial-success ambiguity.** Quest/coins/task completion routes execute multiple `_at_post/_at_patch` operations without canonical batch outcome or claim ([tma_api.py:3238](../../tma_api.py#L3238), [tma_api.py:3373](../../tma_api.py#L3373)).

## P2 — inconsistency and debt without a proven immediate unauthorized write

1. Router `_pending_approvals` calls raw-text plan confirmation “approval,” stores original text, and reruns it; this obscures authority boundaries ([app.py:82](../../app.py#L82), [app.py:626](../../app.py#L626), [app.py:1475](../../app.py#L1475)).
2. No production `bus.subscribe()` call exists; email/bounce approval UIs dead-end. Feature flags correctly hard-block activation, but the dead state machine remains ([feature_flags.py:191](../../feature_flags.py#L191)).
3. EB list/fingerprint cleanup iterates shared dictionaries without the same lock used by `pop()`, leaving process-local race potential ([event_bus.py:90](../../event_bus.py#L90), [event_bus.py:112](../../event_bus.py#L112)).
4. Approvals projection module header says unwired although TMA uses it; planning documentation can mislead reviewers ([core/approvals_projection.py:1](../../core/approvals_projection.py#L1)).
5. ActionContract has no durable provider receipt, rejection actor/time, presentation message ID/adapter, or explicit system initiator. Adding fields is justified only for concrete Phase 4C use cases; see draft spec.
6. Live feature values, tenant/number mapping and active scheduler flags cannot be proven from source. Conclusions about reachability must remain conditional.
7. Many tests use mocked gateways/providers and prove wiring, not the end-to-end authorization boundary. This is explicit in `test_phase_4b2_wiring.py:441-478` and `:634-678`.
8. Direct ingestion/session/audit writes are not consistently documented as bounded pre-authorization, so reviewers cannot distinguish intended persistence from missed approvals.

## Restart, duplicate, tenant and identity analysis

Durable AC proposal lookup and lifecycle recovery are well covered. What fails on restart is channel presentation and continuation state: EB actions, router plan confirmation, voice edit state and disambiguation/reconfirmation UX. TMA avoids this by listing durable AP projections and resolving immutable AC IDs.

Duplicate provider execution is prevented only on the canonical PG path. Telegram fallback, direct dispatcher calls, lead auto-write, file upload and direct background/TMA writes do not share that claim. Component-local idempotency (MessageSid, media hash, Airtable dedup) is useful but is not execution ownership and often cannot classify an ambiguous provider outcome.

Canonical AC execution freezes requester identity and keeps `approved_by` separate. Direct paths frequently use only current role/chat ID or no identity. Twilio/Meta sender canonicalization is stable enough to reuse, but `_channel_domain(destination_number)` selects domain rather than tenant. TMA validates contract tenant; other direct handlers often accept a domain string without proving it is in `identity.allowed_domains`.

## Policy inconsistencies

| Source | What it decides | Gap |
|---|---|---|
| Tool Registry `requires_approval/high_risk` | coarse tool policy | not enforced at execution boundary |
| ActionGateway classifier | `approval` versus narrow Leads `self_confirm` | correct frozen-field logic, but only for gateway callers |
| TMA `ACTION_RISK` | bulk low-risk eligibility | separate hardcoded list |
| app router approval set | raw-text command confirmation | not tool authorization; terminology collision |
| endpoint role branches | owner direct versus manager approval | implicit policy not recorded on AC |
| feature flags | whether canonical boundaries run | default-off legacy mode restores bypass |

The future policy decision should be a typed result derived from Tool Registry plus immutable action facts, stored on AC and revalidated at approval. Prompts and channel UI may describe policy but never own it.

## Test-gap matrix

Legend: **A** adequate boundary test; **M** mock/wiring only; **L** legacy behavior test that must change; **—** missing.

| Candidate | Auth | Identity | Tenant | Restart | Duplicate/concurrent | Stale/forged UI | Forged exec context/direct dispatch | Provider/receipt/outcome | Projection/rollback/flag/unrelated callback |
|---|---|---|---|---|---|---|---|---|---|
| Canonical ActionGateway core | A | A | M | A | A | M | M except TMA | A including `outcome_unknown` | A/M |
| TMA adapter | A | A | A/M | A via AC/AP | A | A for legacy/tampered context | A for `tma_write` | A/M | A; unrelated TMA routes not broad-regressed |
| Telegram agent proposal | A for role | M | M | L/— | EB single-process A; multi-instance — | callback forgery/stale — | L explicitly asserts fallback | failure A only on AC path | flag mismatch L; unrelated callbacks — |
| Telegram free text/selection | A | A | M | contract A, UX state — | M | stale ordinal/reconfirmation — | uses gateway A | core A | unrelated callback N/A |
| Lead auto-capture | M | M | M | AC recovery A but write bypass — | provider dedup M | N/A | direct-write boundary — | lifecycle failure M; claim — | flag matrix incomplete |
| Voice approval/edit | M | M | — | EB/edit — | EB process-only | forged/stale edit callback — | direct edit write — | provider partial — | unrelated callback regression — |
| Files/media | endpoint M | M | — | idem component | component idem M | N/A | direct provider | Drive success/Airtable failure M; ambiguous outcome — | rollback/cleanup — |
| WhatsApp adapter | signature M | identity M | domain M | shared AC A, presentation — | MessageSid M | reply forgery/parser — | inherits L fallback | provider core A only | outbound flag mismatch — |
| Background typed actions | — | — | — | — | — | N/A | direct writes | failure logs only | flag/rollback — |
| Dispatcher global boundary | role A | A | M | N/A | N/A | N/A | only TMA A; other 10 — | per-tool component tests | compatibility suite — |

Required Phase 4C-1 tests:

- authorization: authorized and unauthorized callback, self-confirm identity match, current role downgrade;
- identity/tenant: frozen requester used by provider, separate approver, cross-tenant/cross-domain refusal;
- restart: proposal in instance A, approval presentation/reply in instance B uses same AC ID;
- duplicates: duplicate, concurrent and stale button approval produce exactly one provider call;
- forged data: unknown/forged AC ID, mismatched channel target, forged `execution_context`, direct `dispatch_tool()` for every approval-required tool;
- failures: repository unavailable, PG unavailable, provider explicit failure, receipt verification failure, `outcome_unknown`, projection delivery failure;
- flags/rollback: every supported flag combination fails closed for approval-required writes; rollback can restore presentation without restoring direct fallback;
- callbacks: approval routing remains separate and all unrelated callback families still reach their existing handlers.

## Documentation drift

- `core/approvals_projection.py` header predates live wiring.
- `test_pr0c_telegram_callback_gateway.py` names direct fallback “unchanged” and asserts it; this must be marked as deliberately obsolete in migration, not silently deleted.
- Phase flags are described as default-off while recent Phase 4B live verification happened with deployment overrides. Source cannot prove current Render values.
- F52/roadmap documents were treated as discovery aids only; where they disagree with code, this report follows code and executable tests.
