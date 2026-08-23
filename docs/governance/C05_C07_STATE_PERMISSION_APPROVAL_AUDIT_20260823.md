# C05-C07 — State / Permission / Approval Audit (preserved record)

**Audit date:** 2026-08-23
**Audit type:** READ-ONLY. No files were modified, no branch was opened, no
PR was created, and nothing was fixed as part of the audit itself.
**Preserved by:** this document, added 2026-08-23 as part of the Finding #3
remediation PR (see the DECISION and REMEDIATION sections below). The audit
text in the "Original audit (verbatim)" section is reproduced **substantially
as delivered** at audit time — findings, severities, classifications,
evidence levels, and recommended actions are unchanged from the original
report. Only this preservation header, the DECISION section, and the
Finding #3 REMEDIATION note were added after the fact; they are clearly
separated from the original text and dated independently. Do not edit the
"Original audit (verbatim)" section to retroactively make it look like the
policy decision below already existed at audit time — it did not.

Scope of the original audit: `app.py`, `core/`, `tools/`, `tma_api.py`,
`scheduler.py`, `identity.py`, approval-related files. Frontend and
`.worktrees/` were explicitly excluded.

---

## Original audit (verbatim)

**Scope:** app.py, core/, tools/, tma_api.py, scheduler.py, identity.py, approval-related files. Read-only — no files modified, no branch opened. All findings below are static code analysis; three independent research passes cross-checked each other, and I directly re-verified the top candidates (session_store.py, core/otp.py, app.py:2925-2934, tma_api.py:1782-1832) against the live files myself before including them.

### Top 3 highest-risk findings

**1. Systemic dispatcher/tool_registry bypass — ~25+ modules write via `tools/airtable_gateway.py` directly, never through `dispatch_tool()`**
`lead_capture.py`, `inbound_handler.py`, `session_store.py`, `interaction_engine.py`, `voice_adapter.py`, `tenant_provisioner.py`, `ad_attribution.py`, `abandoned_lead_worker.py`, `cmd_update.py`, `lead_conversion.py`, `core/emergency_window.py`, `core/cost_watchdog.py`, and others call `airtable_create`/`airtable_patch` directly. None of this traffic passes through `tool_registry.enforce()` or `requires_approval`. This means `TOOLS_REQUIRING_APPROVAL` policy governs only the agent tool-use loop and TMA's `tma_write` path — the majority of Leads/Tasks/Sessions/Business_Memory/Tenant writes in the system are outside its reach. The repo's own `tools/audit_dispatcher_bypass.py`/`audit_gateway_bypass.py` already track this (baseline dated 2026-07-03) but report 23 and 13 new, unreviewed entries since that baseline — the tracking tool itself is stale.
Classification: **LEGACY_WRITER** (systemic, largely by design with ad hoc per-module mitigations, not a single bug).
Severity: **HIGH**. Evidence: **LIVE STRUCTURE CONFIRMED** (repo's own audit scripts, re-run for this audit). Action: **NEEDS_RUNTIME_VERIFICATION** — re-run/re-baseline both audit scripts against current `main` and review the new entries.

**2. `core/otp.py::verify_otp()` — unlocked check-then-increment-then-consume race on the Critical-action approval gate**
`core/otp.py:76-99`: `entry["attempts"] += 1` → compare to `MAX_ATTEMPTS` → `hmac.compare_digest(...)` → set `consumed=True`, all against a bare module-level `dict` (`_store`, line 27) with **no lock**. `event_bus.py` uses an explicit `threading.Lock()` for the analogous pop/confirm operation ("LL-13"); `core/otp.py` — gating Critical-risk actions via the Emergency Window — has no equivalent. Two concurrent `verify_otp()` calls for the same `request_id` can both read `attempts` before either increments, allowing more than 5 guesses, or both observe `consumed=False` and proceed, breaking the "consumed once even on exhaustion" guarantee its own docstring claims.
Classification: **APPROVAL_BYPASS** (weakens the OTP lockout guarding Critical/Emergency-Window approvals).
Severity: **HIGH**. Evidence: **LIVE STRUCTURE CONFIRMED** (read directly, lines quoted above). Action: **NEEDS_CODE_CHANGE**.

**3. `tma_api.py` — owner writes to Leads/Tasks bypass ActionGateway entirely; Manager writes for the identical action go through full approval**
`patch_lead` (`tma_api.py:1782-1832`), `set_lead_outcome`, `create_lead_task`: `if identity.is_owner: ok = _at_patch(...)` — direct write via the gateway, no `ActionGateway.propose_action`, no `tool_registry`, no C53a evidence contract, no dispatcher involvement at all. The identical action from a Manager routes through `_queue_tma_write_approval()` → full `ActionGateway`/dispatcher `tma_write` pipeline. This is explicitly commented as intentional ("Owner — מיידי; Manager — דרך approval"), but it means two structurally different authorization/evidence mechanisms exist for one conceptual action, and it's inconsistently applied even within TMA itself (`POST /api/projects` requires approval for **everyone including the owner**, while `patch_lead`/lead-task endpoints do not).
Classification: **DUPLICATE_APPROVAL_PATH** (bordering **OWNER_BYPASS** in effect, even though role-gated correctly at the route).
Severity: **MEDIUM-HIGH** (not exploitable by a lower role, but real drift risk — a new endpoint copy-pasted from `patch_lead` silently inherits an owner-bypass pattern nobody re-decided for it). Evidence: **LIVE STRUCTURE CONFIRMED** (read directly). Action: **NEEDS_CODE_CHANGE** (or an explicit, documented policy decision) — unify or formally scope the owner-bypass pattern.

### Full finding list (10 max)

| # | Finding | Class | File:Function:Line | Severity | Evidence | Action |
|---|---|---|---|---|---|---|
| 1 | Dispatcher/tool_registry bypass ecosystem (~25 modules write via gateway directly) | LEGACY_WRITER | multiple; see `tools/audit_dispatcher_bypass.py` output | HIGH | LIVE STRUCTURE CONFIRMED | NEEDS_RUNTIME_VERIFICATION |
| 2 | `verify_otp()` unlocked race on attempts/consumed | APPROVAL_BYPASS | `core/otp.py:76-99` | HIGH | LIVE STRUCTURE CONFIRMED | NEEDS_CODE_CHANGE |
| 3 | TMA owner-bypass vs manager-approval split for same action | DUPLICATE_APPROVAL_PATH | `tma_api.py:1782-1832` (+ `set_lead_outcome`, `create_lead_task`) | MEDIUM-HIGH | LIVE STRUCTURE CONFIRMED | NEEDS_CODE_CHANGE |
| 4 | `session_store.py::set_lead_draft()` writes `lead_draft` in-memory but `_sync_to_db()` omits it from the persisted payload, and `_load_from_db()` never restores it — silently lost on restart/LRU eviction | STATE_SKIP | `session_store.py:397-409` (write) vs `504-519` (persist, field absent) vs `678-693` (restore, field absent) | HIGH (data-loss, not auth) | LIVE STRUCTURE CONFIRMED | NEEDS_CODE_CHANGE |
| 5 | Approval-clicker check is `is_owner or can("actions.approve")` with no tenant match against the original requester's `tenant_id` — tracked as BUG-074 but the regression test only pins the literal expression, not a tenant check | OWNER_DRIFT | `app.py:2925-2934`; `PendingActionsStore` in `event_bus.py:28-56` keyed by `action_id` only | MEDIUM (dormant — single-tenant deployment today) | LIVE STRUCTURE CONFIRMED | DEFER (must fix before any multi-tenant/F08 activation) |
| 6 | Three parallel representations of approval state (EventBus / `ActionContract` / Airtable `Approvals.STATUS` projection) reconciled by hand in `app.py` via named point-patches (BUG-SB-02, BUG-158, BUG-112) | DUPLICATE_APPROVAL_PATH | `app.py:2914-3131`; `core/action_gateway.py:219-286` | MEDIUM | STATIC FINDING | DEFER (architecture review) |
| 7 | `core/emergency_window.py::activate_window()` "no stacking" invariant enforced via non-atomic read-then-write; `_auto_expire()` ignores its own Airtable patch's success/failure | UNDOCUMENTED_RECOVERY | `core/emergency_window.py:134-152`, `76-95` | MEDIUM | STATIC FINDING (not independently re-verified) | NEEDS_RUNTIME_VERIFICATION |
| 8 | `identity.py::resolve_identity()` never returns `None` (fails open to LEAD/READONLY) — contradicts CLAUDE.md's stated "identity is None must hard-fail" rule; its own docstring explicitly states the opposite | Contract/doc mismatch (not exploitable — fallback is lowest-privilege) | `identity.py:235-284` | LOW-MEDIUM | STATIC FINDING | DEFER (fix documentation or add real hard-fail path) |
| 9 | `ActionContract.status == "draft"` is declared in the state enum but structurally unreachable — always overwritten before first persistence | Orphan state | `core/action_gateway.py:1778, 1793-1799` | LOW | STATIC FINDING | DEFER |
| 10 | `scheduler.py` game jobs (`_job_weekly_quest_reset`, boss-battle/digest jobs) write via `tma_api._at_patch` directly, fully outside dispatcher/tool_registry, with no requester identity at all | DIRECT_MUTATION | `scheduler.py:584-659` (+ similar jobs) | LOW (gamification data only) | STATIC FINDING (grep-confirmed) | DEFER |

### Writer / approval coverage summary

- **Agent tool-use loop (Telegram/WhatsApp → `run_agent` → `dispatch_tool`)**: CLEAN. All 22 registered tools are 1:1 covered between `tool_registry.py` and `tools/dispatcher.py`'s switch; role check always runs before `action_validator.validate_action()`; `requires_approval` tools are queued via `ActionGateway.propose_action()` before dispatch, never dispatched directly; approval callback re-checks `enforce()` for the original requester (confirmed, not the clicker's own permissions — matches CLAUDE.md).
- **TMA (`tma_api.py`)**: split personality — `tma_write`/`POST /api/projects`/follow-ups go through the full `ActionGateway` pipeline; `patch_lead`/`set_lead_outcome`/`create_lead_task` bypass it entirely for owners (finding #3); Game/Assets/Ventures endpoints are owner-only and never approval-gated by design.
- **Scheduler & background jobs**: mostly read-only + Telegram-send (`daily_digest`, `payment_reminder`, `daily_collector` — confirmed no mutating Airtable calls); the game-reset jobs are the one direct-mutation exception (finding #10).
- **Legacy/system writers** (inbound webhooks, session persistence, lead capture, `cmd_update.py`, `lead_conversion.py`): a large, largely-necessary category since these have no per-request `Identity` to check against `tool_registry` — but they collectively mean the approval-coverage guarantee in CLAUDE.md ("no Tool without a permission check") only fully holds for the agent tool-use loop, not for the system as a whole (finding #1).
- **`contact_merge.py` / `scripts/classify_contacts_for_airtable.py`**: confirmed genuinely offline, no live Airtable calls — matches CLAUDE.md.
- **`core/financial_gate.py`**: genuinely wired into `output_gateway.py` for CUSTOMER-audience sends, escalates for real when its flag is on; when off it shadow-logs only and lets the message through unmodified — live flag state not verifiable statically.

### State-transition summary

- **Approval flow** is not one state machine but three layered ones (EventBus `pending→confirmed/rejected`, `ActionContract`'s richer `draft→pending→approved→completed|failed|outcome_unknown|rejected|superseded`, and a non-authoritative Airtable `Approvals.STATUS` projection), reconciled by hand with several named point-patches in `app.py`. Terminal-state protection is solid (`approve()`/`reject()` both refuse non-`pending` contracts via compare-and-set). CLAUDE.md documents only the legacy EventBus layer — real documentation drift, not a runtime bug.
- **Lead lifecycle** (`furniture_lead_funnel.py`, `lead_qualifier.py`): clean, linear, forward-only step machines with correctly-guarded terminal/replay behavior. The one real defect found is data-loss, not an invalid transition (finding #4).
- **Emergency stop flags**: precedence (env override > durable > cache > fail-closed-unknown) matches its documentation exactly; no orphan/invalid transitions found.
- **Emergency window / OTP** (the flag-gated Approval Policy override stack): two independent, non-atomic race conditions found (findings #2, #7) in code that exists specifically to gate high-risk approvals under time pressure — the concurrency gap matters more here than it would elsewhere in the codebase.

---

## DECISION — SINGLE BUSINESS WRITE PATH

**Decided:** 2026-08-23. **Status:** approved, remediation in progress (see
REMEDIATION below). This decision resolves the policy question raised by
Finding #3 above.

All meaningful business mutations must enter through ActionGateway.

**Owner policy:**
- Owner does NOT require manual approval for their own permitted action.
- Owner must NOT bypass ActionGateway with a direct business-data write.
- ActionGateway performs identity/permission validation and normal action
  validation.
- Owner policy then allows automatic approval / immediate execution.
- Execution must still produce the normal action contract, result/evidence,
  and audit trail.

**Non-owner policy:**
- Uses the same ActionGateway path.
- Manual approval remains governed by the normal permission/approval policy.

**System/background operations:**
- Must have an explicit system/service policy.
- Must not silently use an owner-direct-write pattern.
- Technical persistence/telemetry is not automatically classified as a
  business mutation; this decision does not broaden into those paths.

**Policy invariant:**

```
BUSINESS MUTATION
  -> ActionGateway
  -> identity + permission + validation
  -> approval policy
       Owner: auto-approved
       Others: normal approval policy
  -> execute
  -> evidence/result
```

**Explicitly deprecated pattern:**

```
Owner
  -> direct Airtable business write
```

---

## REMEDIATION — Finding #3

- **Original finding:** preserved verbatim above (see "Original audit
  (verbatim)" → Top 3, item 3, and Full finding list, row 3).
- **Architecture decision:** SINGLE BUSINESS WRITE PATH (this document,
  DECISION section above).
- **Remediation:** implemented in PR #TBD
  (`claude/state-permission-approval-audit-836k3p`) — `tma_api.py`'s
  `patch_lead`, `set_lead_outcome`, and `create_lead_task` no longer branch
  on `identity.is_owner` to call `_at_patch()`/`_at_post()` directly. Both
  Owner and Manager now call a new shared entry point,
  `_queue_or_owner_execute()`, which always proposes the write through
  `_queue_tma_write_approval()` (the same `ActionGateway.propose_action()`
  call as before, unchanged) and, for Owner only, immediately drives the
  resulting pending contract through `_claim_and_execute_approval()` — the
  same claim → approve → execute helper the manual `/api/approvals/<id>`
  click endpoint already used. Manager is unaffected: the write stays
  `pending_approval` for a human to act on, exactly as before. See the PR
  description for the full file list, diff summary, and test results.
- **Runtime verification:** NOT YET VERIFIED. The fix is code-complete and
  covered by new + updated regression tests (see the PR), run against a
  local sandbox only — no production write, no deployment, no merge has
  occurred as part of this remediation.
- **Production status:** unchanged until deployment + the CLAUDE.md
  "כלל ברזל" verification protocol (commit hash on Render matched against
  `origin/main`, current flag state) is completed.

**Distinction preserved (do not collapse these two):**
**STATIC/LIVE STRUCTURE evidence** from the original audit (what the code
was observed to do, read directly, at audit time) is **not** the same claim
as **RUNTIME BEHAVIOR VERIFIED** (what has been proven to happen against a
running/production system). This remediation entry is STATIC/LIVE STRUCTURE
evidence for the fix's presence in the diff — it is explicitly **not** a
runtime-verified or production-verified claim.

## Related findings explicitly deferred (not touched by this remediation)

- **Findings #1, #2, #4-#10** (see Full finding list above) — untouched by
  this PR. Finding #2 (`core/otp.py` OTP race) and finding #4
  (`session_store.py` `lead_draft` persistence gap) were already remediated
  separately in commit `f2030b0` (PR #845, "C05-C07 FIX BATCH 1") — the
  audit table above is left unedited per this document's own preservation
  rule; see PR #845 for that fix's detail.
- **`update_lead_status` (`PATCH /api/leads/<lead_id>/status`)** — found
  during this remediation's PART 4 neighboring-consistency check. It is in
  the same Leads mutation family as `patch_lead`, but does **not** exhibit
  Finding #3's pattern (it has no owner-direct-write branch at all — Owner
  and Manager already share the same `_queue_tma_write_approval()` call).
  Its inconsistency is the reverse of Finding #3: after this remediation,
  Owner gets immediate execution on `patch_lead`/`set_lead_outcome`/
  `create_lead_task` but still has to wait for manual approval on
  `update_lead_status`, the one other Leads-table PATCH endpoint. Deferred
  to the existing writer-coverage backlog, not fixed here, since it was not
  a named operation in this remediation's scope and folding it in would
  have widened this PR beyond "exactly these two findings" / "exactly this
  operation family."
