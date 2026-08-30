# Lead / CRM Static Local Verification — 30/08/2026

Scope: Draft → Approval → Cancel → Replay/Idempotency → Write Guards, using only
local tests, mocks, fixtures, and static code/AST inspection. No live Airtable
calls, no production credentials, no deployed-SHA canaries, no feature-flag
activation, no runtime-configuration changes. This is **not** production
verification — see `AGENTS.md`'s post-merge verification protocol and
`GOVERNANCE_RULES.md` Rule 15 for what would be required to claim that.

## Truth reset

- `origin/main` at verification time: `a8c06c9c185b65299866fac328eafd2214331134`
- Working branch at verification time: `oracle-m0-readiness`, worktree clean,
  HEAD (`4123398`) confirmed an **ancestor** of `origin/main` (6 commits behind,
  not diverged). The only files differing from `origin/main` were docs,
  context-librarian state, and the WhatsApp semantic-action normalizer — none
  touch Lead/CRM code — so verification proceeded directly against the working
  tree as main-equivalent for this scope.

## Canonical Lead flow

```
Draft (core/draft_flow.py — pure state machine, no I/O)
  → filling/edit_choice/review; entity semantics from core/lead_service.py's LEAD_DRAFT_SPEC
Approval (core/action_gateway.py — ActionGateway)
  → propose_action() computes business_action_fingerprint = hash(tenant+user+tool+payload),
    CAS-claims it (claim_fingerprint_cas), creates a pending ActionContract
  → approve()/approve_with_lifecycle_result() re-check status=="pending" before executing —
    never trust a stored decision
Write (core/lead_service.py::create_lead() / update_lead_fields())
  → the intended single writer: validates payload, hard-enforces Owner, checks
    EMERGENCY_STOP_ALL, opens/reuses the ActionContract, then calls
    tools/airtable_gateway.py::airtable_create/airtable_patch("Leads", ...)
Evidence (LeadCreateResult{ok, action, record_id, evidence:{contract_id}})
  → contract lifecycle status updated to completed/failed; lifecycle_persistence_failed
    is a distinct terminal state when the write succeeded but the ledger couldn't
    record it (never silently reported "ok")
```

Every *supported* creation entry point — chat capture
(`core/lead_candidate_handler.py`'s `_write_one_lead`/`_propose_lead_write`/
`_finalize_draft_confirm`), WhatsApp (`lead_capture.py`), email
(`inbound_handler.py` → `core/noninteractive_lead_cutovers.py`), the furniture
funnel, the structured `ליד חדש | ...` command, and the approved
Telegram-Lead-preview execution path (`core/action_gateway.py`'s `_lead_payload`
special case) — converges on `create_lead()`. `tools/dispatcher.py`'s
`enforce_leads_write_gate()` (`tools/airtable_security.py:39`) is the
last-line defense blocking direct agent-driven writes to `table="Leads"`
unless `trusted_source="lead_capture"` or a valid ActionContract
`execution_context` is present.

## Local verification matrix

| Area | Status | Representative tests |
|---|---|---|
| Draft | PASS | `test_draft_flow.py` (16), `test_lead_service_phase1.py` (109), `test_n18_slice1_lead_preview.py` (6), `test_n18_draft_dispatch_unification.py` (8) |
| Approval | PASS | `test_bug076_lead_confirmation_policy.py` (32), `test_pa01_phantom_approval_enforcement.py` (108), `test_bug074_approval_authority.py` (22), `test_pr0c_*` suite (~117), `test_action_gateway.py` (43), +~15 more approval files |
| Cancel | PASS | `test_draft_flow.py` (cancel outcome), `test_n18_draft_dispatch_unification.py` (cancel branch), `test_bug056_legacy_cancel_replay_guard.py` (6) |
| Replay/Idempotency | PASS | `test_hotfix_e_shared_replay_policy.py` (56), `test_f15_idempotency_retry.py`, `test_f5_voice_idempotency_retry.py`, `test_bug_telegram_idempotency_key.py` (17), `test_phase_4b0_1c_concurrent_approvals.py` (12), `test_inbound_handler.py` (8) |
| Write guards (supported paths) | PASS | `test_c02_c04_approval_legacy_inbound_leads.py` (3, AST-level), `test_airtable_gateway.py` (37), `smoke_tests.py` |
| Write guards (full inventory) | **GAP FOUND** | see below — two legacy bypasses + one parallel sanctioned writer sit outside `create_lead()`'s invariants |

**Test totals:** ~1,537 passed, 0 failed, 0 skipped across ~85 executed test
files (both script-style `python3 file.py` runners and pytest-collected
files), plus `py_compile` on all touched modules and the core suite
(`smoke_tests.py`, `test_integration.py`, `core/router/test_router.py`,
`test_airtable_gateway.py`, `test_c53a.py`, `test_a32_enforcement.py`).

**Methodology note:** ~15 test files matching the Lead/CRM naming patterns are
pure pytest-style (bare `def test_*()`, no `__main__`/`sys.exit`) —
e.g. `test_noninteractive_lead_cutovers.py`, `test_whatsapp_lead_cutover.py`,
`test_f52_g3_s6/s7_*.py`, `test_f52_g4_s1/s3_*.py`,
`test_audit3_finding1_*.py`, `test_c02_c04_approval_legacy_inbound_leads.py`.
Running them as `python3 <file>.py` silently executes **zero** test functions
and returns exit code 0 — a false-pass trap if only the return code is
checked. Re-running through `pytest` executed all 161 test cases in that
group (all passed).

## Write-path inventory (full)

| Caller | Canonical? | Guarded? | Status |
|---|---|---|---|
| `core/lead_service.py::create_lead()`/`update_lead_fields()` | **Intended sole writer** | ActionGateway proposal + Owner/domain/EmergencyStop checks | OK |
| `core/lead_candidate_handler.py` (`_write_one_lead`/`_propose_lead_write`/`_finalize_draft_confirm`), `lead_capture.py`, `inbound_handler.py`→`core/noninteractive_lead_cutovers.py`, `furniture_lead_funnel.py` | Delegate to `create_lead()` | Same, AST-verified no direct writer in these functions | OK — `test_c02_c04_approval_legacy_inbound_leads.py` |
| `tools/dispatcher.py` (agent tool_use path) | N/A — gate, not writer | `enforce_leads_write_gate()` blocks `table="Leads"` for `source="agent"` unless approved-contract proof matches | OK — `test_bug090_leads_gate_message.py` |
| `voice_adapter.py:242-257` — `_save_voice_lead()` legacy branch: `airtable_add(Tables.LEADS, fields)` via direct `tools.airtable_tools` import | Bypasses `create_lead()`'s Owner-resolution/EmergencyStop/dedup-fingerprint | Reached whenever `VOICE_CANONICAL_LEAD_WRITE` is off — the **documented default** (`feature_flags.py:36`: *"Voice LeadPayload → create_lead(); default OFF until E2E/runtime verification"*). Named, in-progress migration, not undiscovered drift — but it is the currently-active default for the Voice channel (itself gated separately behind `VOICE_IVR`/F07, off by default). | CURRENT STATIC GAP (tracked, pre-named) |
| `ad_attribution.py:203/222` — `mark_converted()`: `airtable_update("Leads", record_id, fields)` via direct `tools.airtable_tools` import | Bypasses the ActionGateway proposal/idempotency ledger and `EMERGENCY_STOP_ALL` check | Always active, no flag. Narrow scope: 3-field status update (`Status`/`Outcome`/`ConvertedAt`) on an already-existing Lead found by `memory_key`, not a create. Still reaches `tools/airtable_gateway.py::airtable_patch()` internally (module's own comment; independently confirmed by `tools/audit_gateway_bypass.py` reporting 0 raw-HTTP bypasses) — field validation/audit-logging still apply. | CURRENT STATIC GAP |
| `tools/approval_actions.py:384` — `tma_write()` (TMA Leads-screen writes) → `airtable_create`/`airtable_patch` directly | Second **sanctioned** writer — reached via `tools/dispatcher.py`'s `case "tma_write"`, protected by `_validate_execution_proof()`'s approval-sensitive fingerprint check (not a raw identity/tenant bypass) | Duplicates write logic instead of calling `create_lead()`/`update_lead_fields()` — doesn't reproduce Owner-resolution, name+phone dedup, or the `EMERGENCY_STOP_ALL` check for Leads specifically. | DOC DRIFT / architecture note — two parallel canonical writers for Leads exist (chat-side `create_lead()`, TMA-side `tma_write()`), not formally reconciled |
| `lead_conversion.py:21/100` — `from crm import crm_add_contact` (Contacts, not Leads) + `_at_patch(Tables.LEADS, ...)` status update on conversion | Bypasses dispatcher/identity/tenant enforcement for the Contacts write | Self-documented in the file's own header comment; owner-only `/convert` command; `LEAD_AUTO_CONVERT` flag off by default; has its own audit log call | ACCEPTED DEFERRED (pre-existing, documented) |

The repo's own auditors (`tools/audit_gateway_bypass.py`, run live: `0 Airtable
bypass call-sites found, 0 new`; `tools/audit_dispatcher_bypass.py`, run live:
`legacy=36 sanctioned=3 cross_track=2 accepted=1 new=0`) already track all of
the above as known `LEGACY`/tracked entries — this verification did not
surface fresh, unknown drift, but it does correct an initial narrower claim
(made mid-audit, before the full write-path sweep completed) that no bypass
existed at all.

## Replay/idempotency mechanism inventory

- **ActionGateway proposal-level** (`core/action_gateway.py:1561`
  `compute_business_fingerprint`, checked at `propose_action()` via
  `claim_fingerprint_cas`): key = `hash(tenant_id + canonical_user_id +
  tool_name + normalized_payload)`.
- **ActionGateway approval-level** (`approve()`/`approve_with_lifecycle_result()`,
  `core/action_gateway.py:3033`/`2080`): key = `contract_id` + `status=="pending"`
  check — re-approving/re-executing a terminal contract is rejected without a
  second execution; `reject()`/`reject_if_pending()` use the identical guard
  for cancel, with `reject_if_pending()` using an atomic CAS transition to
  close a TOCTOU window the plain check-then-write has.
- **Telegram confirm-word bookmark** (`session_store.lead_sessions`,
  `last_prompted_contract`, BUG-115): key = `canonical_user_id`, TTL 600s.
- **F06 inbound dedup** (`inbound_handler.py`): key = `external_id` —
  `test_inbound_handler.py` ("duplicate external_id → no create call").
- **Optional staging-only layer** (`core/action_gateway_atomic_executor.py`,
  `FEATURE_ATOMIC_CLAIMS`, off in production): key =
  `sha256(contract_id:approver)[:16]`, PostgreSQL-backed row claim,
  fail-closed if Postgres is unavailable.

There is no message-id-keyed replay guard in the ActionGateway layer — dedupe
is entirely `contract_id` (per-attempt lifecycle) plus
`business_action_fingerprint` (per-business-action identity at proposal time).

## Gap classification

- **ALREADY CLOSED — TEST STILL PASSING:** Draft/Approval/Cancel/Replay areas
  in full; the supported-path write-guard claims (`test_c02_c04_approval_legacy_inbound_leads.py`).
- **CURRENT STATIC CODE GAP:** `voice_adapter.py`'s legacy Leads writer
  (active by default while `VOICE_CANONICAL_LEAD_WRITE` stays off);
  `ad_attribution.py::mark_converted()`'s direct `airtable_update("Leads", ...)`.
- **DOC DRIFT:** `tools/approval_actions.py::tma_write()` as a second,
  unreconciled Leads writer alongside `create_lead()`.
- **ACCEPTED DEFERRED:** `lead_conversion.py`'s direct `crm` import (Contacts
  write, not Leads) — pre-existing, documented, mitigated.
- **TEST COVERAGE GAP:** none found — every claim above traces to a specific
  test or a specific static/AST check.
- **RUNTIME-ONLY — NOT TESTABLE LOCALLY:** the `FEATURE_ATOMIC_CLAIMS` staging
  path (flag off in production by the module's own design).
- **OUT OF SCOPE:** UX/F52/Oracle work, live Airtable verification, feature
  flag activation — none attempted, per this audit's scope.

## Final output

```
CODE CHANGE REQUIRED: NO (for this audit — findings are pre-existing, already
  tracked by the repo's own audit scripts; fixing them was explicitly out of
  scope for this pass)
BLOCKER TO STATIC LEAD/CRM VERIFICATION: NO
FINAL VERDICT: STATIC GAP FOUND
```

Draft/Approval/Cancel/Replay fully PASS. Write Guards is PASS for every
*supported, tested* creation path (chat/WhatsApp/Email/Furniture/
Telegram-draft — all provably funnel through `create_lead()` with zero
bypass, AST-verified) but carries two pre-existing, already-tracked legacy
gaps (Voice default branch, `ad_attribution.mark_converted()`) and one
parallel sanctioned writer (TMA `tma_write()`) that sit outside
`core/lead_service.py`'s invariants. None of these are newly-introduced —
the repo's own bypass-scanner baselines already carry them as `LEGACY`/
tracked debt with `0 new` — so this does not block sign-off on the areas this
audit was scoped to, but is recorded here for the record per Rule 15
("no claim without verification").

```
STATUS: 🟡 CODE DONE (verification-only — no code changed), NOT RUNTIME VERIFIED
EVIDENCE: local test runs + static/AST audits only; no production/network calls made
```
