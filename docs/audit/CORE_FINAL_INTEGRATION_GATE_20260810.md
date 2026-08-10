# CORE Final Integration Gate — 10/08/2026

Scope: final CORE integration gate only, covering Track A, Track C (TC8/TC9/TC10),
Track D, F14, F15, TC7-A/B1/B1.1/B2. No implementation work performed; no runtime
behavior changed to make this gate pass.

**Audited `main` SHA:** `62a903ceb70dd05b73e2fde794b0c9294b8d53a2` (PR #584 — F15).
A docs-only merge (PR #594, `CHANGE_CONTROL_LOG.md` only) landed on `main` after this
audit ran; it does not touch code and does not affect any finding below.

## 1. Merged-PR map

| Track | PR(s) | Merge SHA |
|---|---|---|
| Track A | #581, #582 | `f218e9c`, `5b575d3` |
| TC8 | #585 | `a945ee7` |
| TC9 | #588 | `cec3f83` |
| TC10 | #590, #592, #593 | `6f16d8e`, `f245d56`, `f540dba` |
| Track D | #580 | `f38c5e4` |
| F14 | #570 (B1), #577 (B2) | `ff9b574`, `cc67f9f` |
| F15 | #584 | `62a903c` |
| TC7-A | #573 | `c16245c` |
| TC7-B1 / B1.1 | #583, #587 | `7676ca6`, `0eafeeb` |
| TC7-B2 | #591 | `d60c8fb` |

No open PRs at audit time (`gh pr list --state open` → `[]`).

## 2. Gate 1 — merged-state audit

All required code confirmed on `main` by grep, not by PR status: durable turn-state
repository + migration 002 (TC8), MessageContract + 4 adapters (TC9), the TC10
harness scripts, RuntimeSchemaProvider + IngressEnvelope (Track D), the Contact
Gate wired at both entry points (F14), the Airtable-gateway write path in `crm.py`
(F15), evidence/claim-authorization modules (TC7-A/B1/B2). **No branch-only or
PR-only implementation outstanding. Gate 1: clear.**

## 3. Gate 2 — regression, exact counts

Ran the existing TC10 harness (`scripts/run_isolated_regression.py`) in an isolated
worktree — no second regression framework created. First pass (no `DATABASE_URL`)
produced 3 named-gate failures (12/5/4 failed tests), root-caused to
`TurnStateStoreError: turn-state store unavailable` (missing local Postgres, unlike
CI's service container). Provisioned a disposable `postgres:16` container matching
CI's exact config, applied migrations 001/002, reran:

- **TC10 `FULL_REGRESSION` (21 files) + 3 named gates: 24/24 PASS, `--repeat 2` →
  STABLE**, identical per-file outcomes both runs.
- 17 additional files required by this gate but outside TC10's own matrix
  (TC7-A/B1/B2, TC9 ×2, Track A, F14 ×3, F15, Track D ×2, router, ActionGateway ×2,
  smoke ×2): **17/17 PASS** (5 initially mis-invoked under pytest instead of script
  mode → INTERNALERROR; rerun in script mode, root-caused, not a real bug).

**Total: 41/41 file-level checks PASS, 0 unexplained failures, on current `main`.**

## 4. Gate 3 — cross-layer authority findings

- **Action lifecycle**: `ActionGateway.approve()` → `_execute_contract()`
  internally. Every production `.approve()` call site (`tma_api.py:2834`,
  `action_gateway.py:2080`) checked — no duplicate `dispatch_tool()` follow-up call
  anywhere in `app.py`/`tma_api.py`. Single authority confirmed.
- **Reply ownership**: `test_tc6_app_reply_ownership.py` 52/52 PASS; hard-set
  `reply_owner="gateway"` pattern intact, no silent fallback.
- **Evidence / TC7-B**: `core/evidence_message_adapter.py` is a documented pure
  projection of TC7-A's `EvidenceResult`; `authorize_claim()` (TC7-B1) is a pure
  function of `(evidence_status, lifecycle_state)`. **TC7-B2 confirmed
  shadow-only**: `observe_claim_authorization_shadow()`'s return value is discarded
  at both call sites (`core/action_gateway.py:2062`, `:3193`), wrapped in a
  swallowing `try/except`. No runtime semantics changed.
- **MessageContract / TC9**: `_state_from_lifecycle()`
  (`core/message_contract.py:393-427`) is a pure mapping over externally-supplied
  `lifecycle_state`/`evidence_status`. No second lifecycle authority.
- **TC8 durable turn state**: fail-closed confirmed empirically — removing DB
  access raised `TurnStateStoreError`, uncaught, cascading through dependent
  tests. No RAM fallback exists.
- **F14/F15 One Write Path**: `crm.py`'s only direct `httpx` call is the read path
  (`_get`, outside F15's write-path scope); `_post`/`_patch` route through
  `tools.airtable_gateway`. Both F14 write entry points (`tools/dispatcher.py:362`,
  `tools/approval_actions.py:370`) call the same
  `crm.find_or_create_contact(create_writer=airtable_create)` — single dedup gate,
  no bypass.
- **Track D**: `core/ingress_envelope.py` contains zero routing logic (pure
  data/trace classes) — structurally observation-only.

**Two out-of-scope observations** (not part of the 7 audited tracks, not fixed):
`lead_conversion.py:11` has a stale comment claiming `crm_add_contact` bypasses
`airtable_gateway` (false since F15, doc-only); `core/reasoning_ports.py`'s
`_ProductionContacts.find_or_create` has a broken import (wrong module path,
target function doesn't exist), always falls into its except-fallback — lives
behind the separate Decision Hub subsystem (`FEATURE_DECISION_HUB`, off by
default), not one of A/C/D/F14/F15/TC7.

## 5. Gate 4 — runtime verification matrix

| Capability | MERGED | WIRED | DEPLOYED | RUNTIME VERIFIED | Evidence |
|---|---|---|---|---|---|
| ActionGateway create/update/complete | done | done | done (prod `62a903c` live) | done | 43/43 + 34/34 local; prod `FEATURE_ACTION_GATEWAY=true` (Render API, live) |
| Atomic claims | done | done | done | done | 42/42 local (no-DB fail-closed scenario preserved) |
| TC8 durable turn state | done | done | done | done | fail-closed proven; prod `DATABASE_URL` -> real `my_bot_atomic_claims_produc*` DB (Render API) |
| TC9 MessageContract | done | done | done | STAGING RUNTIME VERIFIED (real canary, prior session) | 4/4 + 19/19 local |
| TC10 harness | done | done | done | done | this gate's own 24/24 + 17/17 run |
| RuntimeSchemaProvider | done | done | done | shadow only | prod `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=shadow` (Render API, live) |
| IngressEnvelope | done | done | done | done (observation-only) | 67/67 local |
| F14 Contact Gate | done | done | done | done | 3 files PASS; single-gate wiring confirmed by grep |
| F15 One Write Path | done | done | done (prod `62a903c` live) | STAGING RUNTIME VERIFIED (real canary, prior session) | write-path grep clean |
| TC7 evidence projection | done | done | done | done | 128/128 local |
| TC7 claim authorization (B1/B1.1) | done | done (via B2 shadow path only) | done | shadow only | 31/31 local |
| TC7-B2 shadow comparator | done | done | done | shadow only | 78/78 local; return-value-discarded confirmed |

**Deployment evidence (via Render API, not inferred from merge status)**: production
service `My-bot` (`srv-d80ehsf7f7vs73cq5rn0`) is live at `62a903c`, the exact
audited `main` HEAD. Staging service is live at `fd4df0b`; `git diff --stat
fd4df0b 62a903c` = empty, i.e. content-identical to main.

## 6. Duplicate authority / bypass findings

None found in-scope. The two out-of-scope observations in Section 4 are documented,
not fixed, not conflated with CORE authority.

## 7. Deployment/runtime evidence gaps

Closed for production (exact SHA match, live) and staging (content-identical,
live), both via direct Render API reads. Remaining gap: TC9/F15 runtime behavior
is staging-verified, not production-behavior-verified — production feature-flag
config is confirmed live, but no live production traffic was observed in this
pass.

## 8. Remaining-item classification

**CORE BLOCKER**: none.

**DEFERRED POLICY / ENFORCEMENT**: TC7-B3/RP5 enforcement —
`FEATURE_EVIDENCE_FINALIZER=shadow` in production (read live via Render API,
fresher than the previously-recorded 12-day-stale reading). No architecture doc
requires enforcement for CORE closure. Correctly deferred, no contradiction, no
owner decision needed.

**HARDENING**:
- Context Librarian "authoritative post-merge refresh check" (hard-blocking CI
  step, `main`-push only) has been failing on every push since before PR #579
  (2026-08-09, predates this entire work window) — 25 unregistered sources
  accumulated (4 `STOP`, 21 `REVIEW_REQUIRED`), none attributable to any single
  one of the 7 audited tracks; a systemic catalog-freshness gap, proven
  pre-existing via CI run history. Not a CORE blocker; backend-ci is technically
  red on `main` right now for this reason alone — the functional/test-execution
  surface itself is green (Section 3).
- Two stale-comment/doc items (Sections 4, 9).

**POST-CORE**: none identified in this pass.

## 9. Documentation inconsistencies

1. `lead_conversion.py:11` — stale bypass comment, contradicted by F15's actual
   code.
2. `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` row A — states TC7-B1/B1.1 has
   "zero callers anywhere outside the module's own `__main__` block and its test
   file... BUILT_UNWIRED." This predates TC7-B2 (PR #591), which added a real
   (shadow-only) caller chain: `authorize_claim()` <- `claim_authorization_shadow.py`
   <- `observe_claim_authorization_shadow()` <- `action_gateway.py`/`app.py`.
   Doc-only drift; runtime behavior unaffected (still shadow-only).

Both are documentation cleanup, not runtime blockers — code/runtime state is
correct in both cases.

## 10. TC7-B3

`DEFERRED POLICY / ENFORCEMENT — PENDING SHADOW EVIDENCE`. Verified: B2 correctly
shadow-only, no runtime semantics changed, `FEATURE_EVIDENCE_FINALIZER` untouched,
current production value `shadow`. No contradiction found requiring an owner
decision.

## 11. Final verdict

Zero CORE blockers. All 7 tracks' required code is on `main`, single-authority per
layer confirmed by direct code reading, 41/41 regression files pass with real
infra (Postgres, not mocked), production+staging deployment independently
confirmed via Render API at exact/content-identical SHAs. Only open items are
pre-existing governance debt (Context Librarian catalog, unrelated to any of the 7
tracks) and one correctly-deferred policy gate (TC7-B3).

**`CORE FINAL INTEGRATION GATE — PASS WITH DEFERRED NON-BLOCKING ITEMS`**

**`CORE — COMPLETE`**
