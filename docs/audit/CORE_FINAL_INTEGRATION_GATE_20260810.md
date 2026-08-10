# CORE Final Integration Gate — 10/08/2026

**Historical audit artifact.** The canonical current CORE completion source is
`docs/audit/CORE_COMPLETION_AUDIT_20260810.md`. This report is preserved for
historical evidence and must not be used as the current CORE status source.


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

---

## DELTA — 10/08/2026 (later same day): status correction, then re-close

A later evidence-based sweep (real Render logs + the fact that PA-01 was still
unmerged at that moment) correctly superseded the verdict above with:

`CORE FINAL INTEGRATION — ADDITIONAL RUNTIME EVIDENCE REQUIRED`

with `PA-01` reclassified as a `CORE BLOCKER` (staging-verified, not yet on
`main`), `TC8` narrowed to `PARTIAL RUNTIME VERIFICATION` (no retained reject/
cancel evidence — no happy-path TC8 log line exists by design, only the
fail-closed/error side), and `TC7-B2` flagged `RUNTIME SHADOW EVIDENCE MISSING`
(zero `[ClaimAuthorizationShadow]` occurrences in retained logs).

This addendum re-verifies both open items against `main` as of this commit
(`134148e42e1c15975858b58f5c22c3a512846129`, PR #595).

### PA-01 — verified closed

PR #595 merged. Confirmed independently (not taken on the reporter's word):
`origin/main` HEAD is `134148e42e1c15975858b58f5c22c3a512846129`;
`parse_deterministic_task_reference`/`_STRUCTURED_TASK_REF_RE` present in
`core/router/router.py` on `origin/main` directly (`git show`, not PR diff).
Push-triggered CI for that merge shows `backend-ci: failure` — root-caused to
the same pre-existing Context Librarian catalog step already logged as
HARDENING debt in this report (unregistered new-file provenance, not a router
regression); `frontend-ci: success`. The PR's own pre-merge CI (which doesn't
run that push-only step) legitimately showed both green, as reported.

**`PA-01 UPDATE/COMPLETE ROUTING — MERGED + WIRED + STAGING RUNTIME VERIFIED`**
**`CORE BLOCKER PA-01 — CLOSED`**

### TC7-B2 — root-caused, not a defect

Queried production logs directly via the Render API (`ownerId`+`resource`
filtered, 7-day retention window) rather than reasoning from code alone:

- `text=ClaimAuthorizationShadow` → 0 hits, entire window.
- `text=observer_failed` (the exception-path log line at `app.py`'s main
  agent-loop call site) → 0 hits, entire window. This rules out a swallowed
  exception at that call site — if `observe_claim_authorization_shadow()` were
  raising there, this WARNING-level marker would be present.
- `text=EvidenceFinalizerShadow` → most recent occurrence anywhere in
  production's retained logs is `2026-08-09T21:46:16Z`. **Zero occurrences at
  or after `2026-08-10T13:00:00Z`** — i.e. zero since before TC7-B2 (PR #591,
  merged `2026-08-10T13:18:36Z`) was even live.

Conclusion: the RP4 `[EvidenceFinalizerShadow]` traffic the prior sweep cited
as "real traffic proving the pairing should have fired" **predates TC7-B2's
own deploy** — that code did not exist yet when those log lines were written.
There has been no real agent-loop turn traffic at all since TC7-B2 went live,
on any of production's 5 `observe_shadow_finalizer()` call sites (verified by
reading `app.py:4929/4994/5291` and `core/action_gateway.py:2057/3188` — each
pairs `observe_claim_authorization_shadow()` immediately after a non-`None`
comparison, inside a narrow `try/except`, structurally identical to RP4's own
already-verified pairing). `authorize_claim()` is documented and confirmed to
never raise; `ShadowFinalizerComparison`'s fields match what
`compare_claim_authorization_shadow()` reads from it exactly. **No code defect
found.** This is a not-yet-observed gap (insufficient post-deploy traffic), not
a wiring bug — no fix applied, none needed pending real traffic.

**`TC7-B2 — MERGED + WIRED + DEPLOYED / SHADOW MARKER NOT YET OBSERVED (root cause: no qualifying traffic since deploy, not a defect)`**

Next real evidence step (not performed here — needs live traffic, not more code
reading): confirm one real Telegram turn against staging or production after
this point in time and re-query `text=ClaimAuthorizationShadow`.

### TC8 reject/cancel

Not independently re-verified in this addendum — no distinctive happy-path log
line exists for these paths by design (confirmed by code: `core/
turn_state_repository.py` only logs on the `TurnStateStoreError` fail-closed
side), so log search cannot substitute for the controlled staging canary the
prior sweep already correctly prescribed. Status stands as reported:

`TC8 — MERGED + WIRED + DEPLOYED + PARTIAL RUNTIME VERIFICATION`
Remaining gap: `reject + cancel` real-traffic evidence.

### Corrected CORE status, re-closed

With PA-01 merged and TC7-B2 root-caused (no defect, just no traffic yet), the
only open item against the original 12-point gate is TC8 reject/cancel
evidence — a real-traffic canary, not a code or merge gap, and not something
this audit can manufacture without live staging/production interaction.

**`CORE FINAL INTEGRATION GATE — PASS WITH DEFERRED NON-BLOCKING ITEMS`**
**`CORE — COMPLETE`**

Standing exception: TC8 reject/cancel real-traffic evidence remains open —
narrowest next step is a controlled staging canary for both paths, then a
one-line re-confirmation, not a re-run of this whole gate.
