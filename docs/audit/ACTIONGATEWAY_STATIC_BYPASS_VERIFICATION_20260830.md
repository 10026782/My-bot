# ActionGateway Static Bypass Verification — 20260830

**Scope:** Code + tests only. No production services called, no live Airtable, no deployed-SHA
verification, no feature flags activated or modified. This document records a completed
static-verification pass, not a remediation plan — the three follow-ups in §7 are tracked here
so they are not lost, but none of them block the verdict in §1.

**Truth reset**
- origin/main: `a8c06c9c185b65299866fac328eafd2214331134`
- branch verified from: `oracle-m0-readiness`, HEAD `41233988291d743fc0920b8f1cd52f70e90dad33` — a
  strict ancestor of origin/main (0 unique commits, 6 commits behind), worktree clean.
- The 6 commits between HEAD and origin/main touch none of `core/action_gateway.py`,
  `tools/dispatcher.py`, `tools/approval_actions.py`, or `tool_registry.py`. The one relevant
  diff, `tools/whatsapp_adapter.py` (`normalize_whatsapp_action()`), is a pure inbound-label
  parser (confirm/cancel/edit/choice/text) — it calls no execution or approval function and does
  not change any finding below.

---

## 1. Final verdict

**STATIC VERIFIED — NO SUPPORTED BYPASSES FOUND** for an agent-initiated, `requires_approval=True`
business action. Every traced execution path — Telegram inline-button approval, free-text
confirm/cancel words, TMA approval, and system self-approval (scheduler/abandoned-lead/interaction
jobs) — re-enters `tools/dispatcher.py::dispatch_tool()`, which re-runs `tool_registry.enforce()`
and `action_validator.validate_action()` regardless of how the call arrived.

`CODE CHANGE REQUIRED: NO` — no fixes were applied or required to reach this verdict.
`BLOCKER TO STATIC ACTIONGATEWAY VERIFICATION: NO`.

## 2. Canonical chain (verified by code read, not by naming)

```
Intent (Agent tool_use / system job)
  -> ActionGateway.propose_action()            core/action_gateway.py:1586
     -> ActionContract (status=pending)         ExecutionLedger, CAS fingerprint claim :699
  -> approve() / approve_with_lifecycle_result() :3033 / :2080
     -> role/policy check                       _has_approval_authority / APPROVAL_POLICY_SELF_CONFIRM :3069-3084
     -> fail-closed if no _tool_executor
  -> _execute_contract()                         :3134
     -> optional atomic claim (execute_with_atomic_claim) :3336
     -> OR legacy direct dispatch                :3454
  -> single writer: self._tool_executor          built by _make_dispatch_executor() :4248
     -> tools.dispatcher.dispatch_tool()          :4386
        -> tool_registry.enforce() + action_validator.validate_action()
        -> provider write (airtable_tools / gmail_tools / calendar_tools / ...,
           or core.lead_service.create_lead() for the N18 lead-slice special case)
  -> evidence: C53a {ok, evidence, external_id} contract + verify_execution()
  -> terminal ActionContract.status: completed / failed / outcome_unknown / rejected
```

`FEATURE_ACTION_GATEWAY` and `FEATURE_ATOMIC_CLAIMS` are both coded **off by default**
(`feature_flags.py:93,102`). Confirmed by tracing both flag states: this changes *how* a contract
reaches execution, never *whether* it re-enters `dispatch_tool()`.

## 3. Supported action inventory

| Action/Path | Canonical? | Approval enforced? | Replay guarded? | Direct writer | Tests | Status |
|---|---|---|---|---|---|---|
| Telegram button approve (`app.py:3044`) | Yes | Yes (`enforce()` @3224 + Gateway `approve()`) | Yes (atomic `bus.pop`, TTL, TC8 claim) | via dispatcher | test_bug_approval_callback_hardening, test_bug112/158/123 | Fails closed (not bypass) when flag off |
| Free-text "כן"/"לא" confirm (`app.py:4442`) | Yes — always calls Gateway regardless of flag | Yes | Yes (TC8 claim when exactly 1 live contract) | via dispatcher | test_approval_gate_registry (triple-confirm = 1 dispatch) | Compliant |
| TMA approve (`tools/approval_actions.py`, `tma_api.py`) | Yes | Yes | In-process `threading.Lock` per approval_id (not cross-process) | via dispatcher; `tma_write` also requires a live Postgres claim | test_c84_tma_approval_ttl, test_pr0c0 | Compliant; cross-process race only closed by `FEATURE_ATOMIC_CLAIMS` |
| System self-approve (scheduler.py, abandoned_lead_worker.py, interaction_engine.py) | Yes | Self-approval by design (no human in loop), still `enforce()`-gated | Yes | via dispatcher | — | Approved specialized pattern |
| Inbound lead intake (lead_capture.py, inbound_handler.py, N18 lead_service) | No — `airtable_tools` direct | N/A (pre-agent ingestion, not an agent-tool-call) | N/A | direct `airtable_gateway` | test_inbound_handler, test_furniture_lead_funnel | Tracked LEGACY (36-entry CI baseline), not new |
| Gmail/Calendar/Sheets/Airtable writes via Agent | Yes | Yes (`requires_approval=True`, execution_context required) | Yes | via dispatcher | test_action_gateway, test_c53a | Compliant |

## 4. Bypass inventory

| File/function | Reachable? | Mutation? | Canonical boundary | Classification |
|---|---|---|---|---|
| `lead_capture.py:132`, `inbound_handler.py:34,110`, `session_store.py`, `ad_attribution.py:203`, `voice_adapter.py:242` | Yes | Yes | None (no `enforce_tenant_scope`, no dispatcher) | CURRENT STATIC BYPASS (literal) / ACCEPTED DEFERRED (pre-existing, CI-frozen, non-agent ingestion path) |
| `lead_conversion.py` (`crm_add_contact`), `cmd_update.py` | Yes, owner-only + flag-gated | Yes | Self-documented + self-audited (`audit_log_airtable`) | ACCEPTED DEFERRED (mitigated, documented) |
| `tenant_provisioner.py`, `project_timeline.py`, `providers/airtable_shim.py` | No (only test importers) | N/A | N/A | DEAD/UNREACHABLE |
| `ActionGateway.approve()`/`update_status()` check-then-write (`core/action_gateway.py:3062,3101`) | Yes, but every current caller wraps externally (TC8 in app.py, lock in tma_api.py) | Would be, if unwrapped | Missing internal CAS; external convention only | CURRENT STATIC CODE GAP (no live exploit path found — all callers mitigate) |
| Telegram button vs free-text asymmetry when flag off (`app.py:3251` vs `:4442`) | Yes | No (button path fails closed) | N/A | CURRENT STATIC CODE GAP (availability, not security) |
| `media_handler.py:852` "✅" text pattern | Yes | No (parsing risk only) | `audit_result_parsing.py` (warning-only) | TEST COVERAGE GAP |
| `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` claim ("FEATURE_ACTION_GATEWAY off by default, infra not fully live") vs. current code's flag-off hardening (LEGACY_GATEWAY_DISABLED, TC8-independent free-text execution) | — | — | — | DOC DRIFT — doc understates how much of the Gateway is unconditionally live (fingerprint dedup, free-text execution, evidence) regardless of the flag |

## 5. Guard status

| Guard | CI blocking? | Local result | Negative test proven? |
|---|---|---|---|
| `tools/audit_gateway_bypass.py --boundary` | Yes | PASS, 0 violations (empty allowlist) | Not re-run negatively this pass |
| `tools/audit_dispatcher_bypass.py` | Yes (on `new` only) | legacy=36, sanctioned=3, cross_track=2, accepted=1, **new=0** | **Yes** — injected `from crm import crm_add_contact` into `config.py`, guard failed (exit 1, `new=1`), reverted, `git status` clean |
| `tools/audit_provider_boundary.py` | Yes | legacy=1, new=0 | — |
| `tools/audit_model_call_boundary.py` | Yes | legacy=3 (app.py direct Anthropic calls, sanctioned non-tool-loop) | — |
| `tools/audit_writer_authority_registration.py` | Yes | 0 candidates | — |
| `tools/audit_public_renderer_contract.py` | Yes | 0 candidates | — |
| `tools/audit_formula_escaping_boundary.py` | Yes | legacy=5, new=0 | — |
| `tools/audit_result_parsing.py` | **No** (`\|\| true`) | **1 new**: `media_handler.py:852` | — |
| `tools/schema_governance.py` | **No** (`\|\| true`, ×2) | fails locally (no live Airtable creds — expected) | — |
| `docs/governance/SECURITY_CHECKLIST.md` grep patterns | N/A — doc marked ARCHIVED since 2026-06-14 | Its own patterns produce false positives on current webhook code (secret checks exist, just outside its 5-line scan window) | — |

Zero `continue-on-error` in `.github/workflows/ci.yml`; exactly 4 `|| true` lines (schema
governance ×2, result-parsing audit, Context Librarian freshness check) — none are
architecture/bypass guards.

## 6. Test execution

- passed: **≈842+** across 33 directly-executed suites, including: ActionGateway core (43), PR-0C
  adapters (34), approval concurrency (22), approval-gate registry incl. triple-confirm idempotency
  (41), approval-gateway safety incl. atomic pop (27), fingerprint CAS/BUG-157 (34), PA-01
  enforcement (108), TMA approval TTL (44), C53a evidence contract (50), turn-state CAS race tests
  (7), router (50), inbound handler (8), furniture funnel (22), identity smoke (4), integration
  (4), plus ~15 more suites (each individually green).
- `smoke_tests.py` and `python -m compileall -q .` both pass; `git diff --check` clean.
- failed: **0**
- skipped/xfail: none observed

## 7. Follow-ups (tracked, not blocking this verdict)

These are the findings that survived triage in §4 as genuine, currently-open items. They are
recorded here so they are not lost — none of them is a live bypass, and none requires action to
close Phase 4 of this verification.

1. **`ActionGateway.approve()`/`update_status()` — no internal CAS on the check-then-write
   transition** (`core/action_gateway.py:3062,3101`). Safety today depends entirely on every
   caller externally serializing (TC8 turn-claim in `app.py`, a `threading.Lock` in
   `tools/approval_actions.py`/`tma_api.py` that is not cross-process-safe). No live exploit
   exists because every current caller mitigates, but this is a convention, not an enforced
   invariant — a new caller could reintroduce the double-execution race unless
   `FEATURE_ATOMIC_CLAIMS` is on.
2. **Telegram button vs. free-text asymmetry when `FEATURE_ACTION_GATEWAY` is off**
   (`app.py:3251` vs. `:4442`). Button approvals fail closed with `LEGACY_GATEWAY_DISABLED` even
   against a live, valid contract, while free-text confirm still executes the same contract. This
   is an availability/consistency gap, not a security issue (it fails closed, not open).
3. **`media_handler.py:852`** — a new, warning-only (non-blocking) `tools/audit_result_parsing.py`
   finding: a literal `"✅"` in a tool result could be mis-treated as a structured success signal
   instead of the `{ok, evidence}` contract. Not yet triaged or explicitly allowlisted.

Additionally, `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`'s characterization of
`FEATURE_ACTION_GATEWAY` as "infra code-complete, not fully live" understates how much of the
Gateway executes unconditionally today (fingerprint dedup, free-text confirm execution, evidence
projection) regardless of the flag's value — worth a wording pass next time that doc is touched,
but not a correctness issue.
