# F52 Gateway Cutover Readiness — Verified Runtime Authority

**Last Updated:** 2026-08-20  
**Status:** `READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`  
**Scope:** Gateway / approval runtime cutover readiness and runtime-path authority.  
**Production mutation:** None. Production flags were not changed during this readiness work.

---

## 1. Why this document exists

A feature-flag/path audit initially reported several approval-related code paths as if they were competing live execution paths. That interpretation was too broad.

The follow-up audit verified the actual Render configuration, current code branches, and staging execution behavior. The result is:

> **No proven `MULTIPLE LIVE PATHS` conflict exists for the same approval action in the same runtime configuration.**

The repository contains canonical paths, rollback/fallback branches, transport/recovery stores, shadow/transitional code, and separate legacy flows. Their coexistence in source code is **not** evidence that two executors are live for the same intent.

This document is the guardrail for future audits: do not reopen a duplicate-execution finding merely because multiple branches/stores exist in the repository.

---

## 2. Mandatory interpretation rule for future audits

A path may be called `MULTIPLE LIVE PATHS` only if all of the following are proven at the same time:

1. Both paths are reachable in the **same deployed runtime configuration**.
2. Both paths can receive the **same business intent / same pending action**.
3. Both paths are execution authorities, not projection/transport/shadow/recovery only.
4. Both can independently reach a real provider mutation.
5. The feature-flag/runtime condition does not make one branch mutually exclusive with the other.

If these conditions are not proven, classify the path instead as one of:

- `LIVE_CANONICAL`
- `LIVE_FALLBACK`
- `SHADOW_TRANSITIONAL`
- `FLAG_OFF_FUTURE_ACTIVATION`
- `DEAD_RETIRE_PENDING`
- `TRANSPORT_RECOVERY_ONLY`
- `PROJECTION_ONLY`

**Source-code existence alone is never sufficient evidence of a live execution conflict.**

---

## 3. Runtime facts captured during the audit

### Production

Verified target at the time of the audit:

- Service: `My-bot`
- Branch: `main`
- Live code/deploy SHA examined: `09fc8a7e1c2e85f349a3cade9272edc9c01f6487`
- `origin/main` matched that SHA during the audit.

Effective production flags:

| Flag | Production value | Effective meaning |
|---|---:|---|
| `FEATURE_ACTION_GATEWAY` | missing → code default `false` | Telegram legacy callback branch remains selected |
| `FEATURE_ACTION_CONTRACT_PERSISTENCE` | `true` | durable ActionContract repository enabled where used |
| `FEATURE_ATOMIC_CLAIMS` | `true` | canonical Gateway execution is claim-gated where reached |
| `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` | `true` | single-speaker ownership logic enabled |
| `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` | `true` | configured on, but Gateway-dependent behavior is not fully effective while Gateway is off |

Production was **not changed** during this readiness work.

### Staging

Current staging canary runtime verified in this work:

- Service: `my-bot-approval-staging`
- Canary code SHA: `4e44bcabb0109bfae41067a2acb90258a4d1ab93`
- All five approval/cutover flags were explicitly `true`.
- Durable Emergency Stop state: `False`.
- `DATABASE_URL` present.
- Pre-deploy migration command ran successfully.
- `/health` returned `200 {"status":"ok"}`.
- Runtime reported: `Atomic claims health: READY: atomic claims operational`.

No staging flag mutation was required for the final core canary because the five flags were already enabled.

---

## 4. Important staging/main provenance boundary

The staging canary SHA is **not identical to current `main`**.

Repository comparison on 2026-08-20 established:

- staging `4e44bca...` and production/main `09fc8a7e...` are **diverged**;
- staging is 5 commits ahead and 19 commits behind `09fc8a7e...`;
- `app.py` differs between the branches, primarily around lead-draft / deterministic confirmation precedence;
- `core/action_gateway.py` and `core/action_gateway_atomic_executor.py` are **not** among the changed files in that comparison;
- the compare patch does not modify `_handle_approval_callback_impl()`.

Therefore:

> The staging canary is valid proof of the **core Gateway + persistence + atomic-claim execution chain**, but it must not be described as byte-for-byte proof of every current `main` confirmation-routing behavior.

Before production activation, the reviewed production candidate must either:

1. contain the verified staging behavior, or
2. receive a final approval-path diff check proving no material cutover-path regression.

This is a release-alignment requirement, not evidence that the core canary failed.

---

## 5. Canonical authority model — code and rollout evidence

### 5.1 ActionContract is the lifecycle authority

`core/action_gateway.py` declares the intended authority boundary directly:

- `ActionContract` is the source of truth for business mutation lifecycle.
- `ExecutionReceipt` / verified provider evidence is the execution proof.
- the Agent is a signal source, not an execution authority.
- when `FEATURE_ACTION_GATEWAY=true`, mutating tools are intended to pass through the Gateway.

The Phase 4B rollout authority (`docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`) also records:

- `ActionContracts` = canonical contract/lifecycle record;
- PostgreSQL `action_execution_claims` = sole execution-ownership primitive;
- Airtable `Approvals` = non-authoritative TMA display projection only;
- provider write + verified receipt = evidence that the action actually happened.

### 5.2 PostgreSQL atomic claim is the execution-ownership primitive

`core/action_gateway_atomic_executor.py::execute_with_atomic_claim()` proves the branch semantics:

- Atomic flag OFF → backward-compatible direct executor fallback.
- Atomic flag ON → claim is required before executor invocation.
- PostgreSQL unavailable → fail closed; no legacy execution fallback.
- already-claimed contract → executor is not invoked.
- claim acquired → exactly that caller owns execution.
- failed/unknown outcomes are recorded explicitly.

This is the mechanism that prevents two approval attempts from becoming two provider writes.

### 5.3 Telegram callback is mutually exclusive by Gateway flag

`app.py::_handle_approval_callback_impl()` proves the callback cutover behavior.

When a canonical contract is found and Gateway is ON:

`callback → approve_with_lifecycle_result() → ActionGateway lifecycle/executor`

When Gateway is ON but no matching contract exists:

- the callback **fails closed**;
- code explicitly logs `refusing legacy dispatch`;
- it returns without calling `dispatch_tool()`.

The direct legacy callback executor exists only in the mutually exclusive branch:

`else:  # Legacy path — FEATURE_ACTION_GATEWAY entirely off`

and only there calls:

`dispatch_tool(...)`

Therefore the old callback executor is a **Gateway-off rollback path**, not a simultaneous Gateway-on executor.

### 5.4 TMA canonical execution

The Phase 4B rollout authority and `tma_api.py::_claim_and_execute_approval()` establish the TMA chain:

`ActionContract → ActionGateway.approve() → _execute_contract() → PostgreSQL claim → provider executor`

After execution, TMA updates projection fields; the projection does not re-authorize or re-derive execution authority.

Airtable `Approvals` remains a read/display projection, not an executor.

---

## 6. Runtime-path classification after the audit

| Path / component | Correct classification | Current production reachability | Execution authority? | Retirement / future role |
|---|---|---:|---:|---|
| Telegram `PendingActionsStore` → callback → direct `dispatch_tool()` | `LIVE_FALLBACK` while Gateway is OFF | Yes | Yes, only in Gateway-off callback mode | Callback direct execution is cut off immediately when Gateway becomes ON; kept as config rollback path for now |
| Telegram Gateway callback → `approve_with_lifecycle_result()` | `FLAG_OFF_FUTURE_ACTIVATION` in current production | No while Gateway=false | Yes when enabled | Becomes callback authority when Gateway=true |
| ActionContract lifecycle | `LIVE_CANONICAL` where contracts are used | Yes | Yes | Permanent canonical lifecycle authority |
| ActionContract persistence | `LIVE_CANONICAL` in production | Yes | No by itself | Permanent durability layer |
| Atomic claim wrapper | `LIVE_CANONICAL` for Gateway execution when reached | Yes where Gateway/TMA execution reaches it | Yes — execution ownership gate | Permanent canonical coordination layer |
| Atomic flag-off direct executor | `LIVE_FALLBACK` | Not selected while Atomic=true | Yes only if Atomic=false | Intentional rollback path; not immediate retirement |
| TMA ActionContract approval | `LIVE_CANONICAL` | Yes | Yes | Permanent canonical TMA path |
| TMA Airtable `Approvals` table | `PROJECTION_ONLY` | Yes | No | Remains read/display model |
| EventBus / `PendingActionsStore` after Gateway-on | `TRANSPORT_RECOVERY_ONLY` | Yes | No for canonical contract execution | Not immediate retirement; transport/recovery role remains |
| `_pending_approvals` router-level store | `LIVE_FALLBACK` / separate generic flow | Yes for `Handler.APPROVAL` routes not captured by Gateway | Yes through recursive `run_agent(_skip_approval=True)` | **No explicit retirement contract found**; track separately |
| `pending_lead_preview` Tier-2 batch preview | `LIVE_FALLBACK` / separate lead-preview flow | Yes where Tier-2 preview is used | Yes through its dedicated confirm flow | **No explicit retirement trigger found**; track separately |
| Gateway shadow proposals | `SHADOW_TRANSITIONAL` | Selected callers only | No write by proposal itself | Transitional until enforcement/soak completion |
| Single-speaker reply ownership | `SHADOW_TRANSITIONAL` / presentation authority | Yes | No | Presentation/ownership behavior, not execution authority |
| Deterministic approval resolver | Gateway-dependent cutover behavior | Not fully effective in production while Gateway=false | Routes approval; does not itself create a second provider executor | Must remain covered by free-text follow-up testing |

---

## 7. Why `_pending_approvals` is not proof of a duplicate canonical approval runtime

`app.py` defines `_pending_approvals` as a **router-level** pending store for `Handler.APPROVAL` messages.

Its confirm path re-runs the original request using:

`run_agent(..., _skip_approval=True)`

This is a separate legacy/generic route. The audit did **not** prove that it can concurrently execute the same ActionContract that the canonical Gateway is executing in the same runtime state.

Therefore it must not be labeled a duplicate canonical executor without a concrete reachability trace showing same intent + same action + both provider writes.

However, no explicit retirement contract was found for this store. It remains a documented migration follow-up.

---

## 8. Why `pending_lead_preview` is not proof of a duplicate canonical approval runtime

`core/lead_candidate_handler.py` documents the Tier-2 batch-preview mechanism explicitly.

It has its own `pending_lead_preview` session state and resolver. The code also contains explicit precedence logic (`should_prefer_batch_preview`) comparing the Tier-2 preview timestamp with the last prompted ActionContract bookmark.

That code is evidence that the two mechanisms can coexist as separate interaction flows and need deterministic precedence. It is **not**, by itself, evidence of two provider executors racing on one canonical contract.

No explicit retirement trigger was found for `pending_lead_preview`; treat that as a migration/documentation follow-up, not as a blocker to the already-proven core Gateway path.

---

## 9. Staging canary evidence — core cutover path

The final staging core canary ran on `4e44bca...` with all five approval flags enabled.

Verified results:

| Invariant | Result |
|---|---|
| Gateway enabled in staging | PASS |
| ActionContract persistence | PASS |
| PostgreSQL atomic claim | PASS |
| Provider write occurred | PASS |
| Exactly one provider write for successful approval | PASS |
| Duplicate/concurrent approval does not double execute | PASS |
| Exactly one final reply | PASS |
| Cleanup | PASS |
| Emergency Stop durable state allowed canary | PASS |
| Production unchanged | PASS |

The critical invariant was demonstrated:

> `one approved contract → one winning claim → one executor → one provider write → one final reply`

This is the evidence that the core atomic approval design behaves as intended under the staging canary.

---

## 10. Readiness verdict

### Decision

`READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`

This verdict means:

- the core Gateway cutover execution chain has passed in staging;
- no proven live duplicate-executor conflict was found;
- the canonical authority model is consistent with the code and Phase 4B rollout contract;
- remaining tests improve cutover completeness but do not currently demonstrate a core architecture failure.

This verdict does **not** authorize an unreviewed Production flag flip by itself.

Production activation still requires the candidate-code alignment check described in §4 and the normal production activation/rollback checklist.

---

## 11. Documented non-blocking follow-ups

The remaining completion checks recorded at the close of this readiness pass are:

1. **Free-text confirmation (`כן` / `לא`)**
   - prove the deterministic/Gateway routing behavior on the intended production candidate;
   - prove `כן` executes only the intended pending action once;
   - prove `לא` terminates with zero executor/provider write.

2. **Restart persistence**
   - create a pending durable ActionContract;
   - restart/redeploy staging;
   - prove the same contract survives and can be resolved exactly once.

3. **Executor failure / retry**
   - prove failure does not produce false success;
   - prove retry follows the existing policy;
   - prove no duplicate provider write is introduced.

These are **documented follow-ups**, not evidence that the core canary failed.

---

## 12. Retirement obligations

### Immediate on `FEATURE_ACTION_GATEWAY=true`

For the Telegram approval callback:

- the direct `dispatch_tool()` callback branch becomes unreachable by design;
- stale/unlinked callbacks fail closed instead of falling through to legacy dispatch;
- ActionContract/Gateway becomes callback execution authority.

### Intentionally retained rollback / support paths

Do **not** delete merely because Gateway is enabled:

- Atomic flag-off direct executor — intentional rollback mode.
- EventBus / `PendingActionsStore` — transport/recovery role remains.
- TMA `Approvals` — projection remains.

### Missing retirement contracts — track separately

No explicit retirement trigger was found for:

- `_pending_approvals`
- `pending_lead_preview`

They must not be silently deleted during Gateway cutover. If/when they are migrated, use a separate scoped migration decision with reachability tests and rollback criteria.

---

## 13. Evidence index

### Current code / authority files

- `feature_flags.py`
  - approval flag definitions and default-off semantics.
- `core/action_gateway.py`
  - ActionContract lifecycle authority and approval boundary.
- `core/action_gateway_atomic_executor.py`
  - claim-required execution, fail-closed behavior, already-claimed handling.
- `app.py::_handle_approval_callback_impl`
  - Gateway-on callback execution and fail-closed no-contract branch;
  - legacy `dispatch_tool()` only in Gateway-off branch.
- `app.py::_pending_approvals` / `approval_response()`
  - separate router-level generic approval store.
- `core/lead_candidate_handler.py`
  - Tier-2 `pending_lead_preview` flow and explicit precedence with ActionContract prompt bookmarks.
- `tma_api.py::_claim_and_execute_approval()`
  - TMA canonical contract execution and projection update boundary.
- `docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`
  - canonical authority model: ActionContracts, PostgreSQL claims, projection-only Approvals.

### Runtime / version evidence

- Production code examined: `09fc8a7e1c2e85f349a3cade9272edc9c01f6487`.
- Staging canary code: `4e44bcabb0109bfae41067a2acb90258a4d1ab93`.
- Git comparison: staging/main diverged; core Gateway/atomic modules were not changed in the comparison; `app.py` contains staging-specific lead/confirmation-precedence changes.

---

## 14. Future audit checklist — do this before reporting duplicates again

Before filing an approval-path duplication defect:

1. Read live Render flag values; do not infer production state from local env.
2. Record exact production/staging deploy SHAs.
3. Resolve code defaults for missing flags.
4. Trace the same intent through both claimed paths.
5. Prove each path can reach a provider write in the same runtime configuration.
6. Distinguish execution authority from projection, transport, recovery and shadow logic.
7. Check whether branches are mutually exclusive under a feature flag.
8. Check existing rollout/retirement documentation.
9. Only then report `MULTIPLE LIVE PATHS`.

If the evidence instead shows a canonical path plus disabled/rollback/shadow/separate flows, report that accurately and do not reopen the architecture as broken.

---

## 15. Final recorded conclusion

The approval runtime is **not** currently proven to contain competing live executors for the same action.

The architecture is a controlled migration state:

- durable ActionContracts are the canonical lifecycle authority;
- PostgreSQL atomic claims own execution coordination;
- TMA already uses the canonical contract/claim model;
- Telegram callback cutover is selected by `FEATURE_ACTION_GATEWAY`;
- with Gateway ON, the callback refuses legacy dispatch if no contract exists;
- legacy, transport, projection and separate preview stores remain for defined roles or future migration;
- the core Gateway path passed its staging canary;
- the readiness decision is `READY WITH DOCUMENTED NON-BLOCKING FOLLOW-UPS`.

Do not reinterpret the mere presence of legacy/fallback code as duplicate active authority without new runtime evidence.
