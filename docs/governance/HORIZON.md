# HORIZON — Program Management Map

**Role:** management-level status map across the D-Structure numbered audit
track program (#1–#24) referenced by `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s
"Future-audit cross-reference" table. Not an audit report — full bodies and
evidence live in each track's own audit/remediation documents; this file
records only CLOSED / ACTIVE / DEFERRED / handoff status at a glance.
Reconcile this file rather than duplicating audit content into it.

**Distinct from** `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md`
— a one-off dated Truth-Reset audit for an unrelated H0–H9 finding series
(deployed-SHA evidence, Command Center, N18 terminal-result chain, H4 media
gates). That document is historical and is not the D-Structure track map.
This file (`HORIZON.md`, no date suffix) is the persistent, update-in-place
management map; no canonical version of it existed before this entry — see
the closure PR that created it for the search that established this.

**Last updated:** 30/08/2026
**Truth Reset SHA at last update:** `8574e9a1ece5831cbc9bd0b3119d64532f486a13`
(Decision Hub callback/record-scope audit recorded; no deployment or runtime claim)

All SHA values inside the dated audit and remediation notes below are
historical evidence references. They are not current-main claims; current
program status is summarized here from the canonical Active Work Registry in
`BOSS_UNIFIED_MASTER_PLAN.md` §3.5.

## CURRENT MAJOR PROGRAM MAP

This is a concise owner-facing projection of §3.5, not a second registry.
Current state is determined only from `origin/main` at the recorded Truth Reset
SHA. Open PRs, branches, local commits and drafts are proposed/not-current
evidence and never override this map.

| Initiative | Work State | Evidence State | Needs Verification | What materially advanced | What remains | Next Step |
|---|---|---|---|---|---|---|
| Turn Coordinator | ACTIVE | MERGED | YES | routing, lifecycle and reply-ownership work merged; TC7-B claim-authorization wiring + RP5 evidence enforcement merged 26/08/2026 (PR #1036), both ActionGateway sink sites + `mixed`-claim coverage closed 27/08/2026 (PR #1041, `09935a8`) — STATIC VERIFIED, RUNTIME NOT ESTABLISHED, RP5 off by default | RP5 shadow evidence review; enforce activation remains deferred | continue shadow; owner approval required before `FEATURE_EVIDENCE_FINALIZER=enforce` |
| Unified Approval / ActionGateway | ACTIVE | MERGED | YES | canonical lifecycle and approval paths merged | staged rollout/runtime verification | verify approved paths |
| Cost / Agent-Last | ACTIVE | MERGED | YES | cost attribution lineage merged | shadow telemetry and enforcement decision | validate live cost and decide progression |
| Architecture authority / execution boundaries | ACTIVE | MERGED | YES | static authority boundaries reconciled | deployed/runtime evidence | verify deployed-SHA authority |
| No-new-architectural-debt | CLOSED | WIRED | NO | blocking guards established in CI | normal monitoring only | monitor |
| Schema / Data Contracts | ACTIVE | MERGED | YES | #2/#3 statically reconciled | live schema/contract evidence | perform live verification |
| Maintenance program | CLOSED | MERGED | YES | numbered audits closed; no owned static gaps | accepted deferred/runtime triggers | monitor triggers |
| Test / CI hygiene | CLOSED | WIRED | NO | #8/#9 closure and CI enforcement | normal monitoring only | monitor |
| Security / permissions | CLOSED | WIRED | YES | static gaps closed; CI guard present | production reachability evidence | perform production verification |
| Lead / CRM canonical flow | ACTIVE | MERGED | YES | shared write infrastructure and Lead consumer merged | end-to-end canary | run live canary |
| Decision Hub | ACTIVE | STATIC AUDIT COMPLETE | YES | PROGRAM STATUS DRIFT FOUND — CALLBACK / RECORD-SCOPE REMEDIATION REQUIRED — RUNTIME NOT ESTABLISHED. Stage 0–1 and formula-safety fixes are statically verified; DH-S1 CLOSED / STATIC VERIFIED; DH-S2 access-policy wording DOC/POLICY DRIFT / REMEDIATION REQUIRED; DH-S3 fail-closed reads STATIC VERIFIED; DH-S4 partial-persistence observability OPEN; DH-CB-01–DH-CB-09 are recorded. Protected CLI paths remain positive evidence; the full authorization layer is not claimed broken | callback enumeration + mutation scope hardening, tenant/domain propagation, callback regression coverage; runtime/deployment evidence remains NOT ESTABLISHED | bounded callback/record-scope remediation |
| Media | ACTIVE | MERGED + PARTIALLY REMEDIATED | YES | gateway/probe and staging artifacts merged; F16-M1/M4 statically verified fixed (Slice 1); F16-M2/M3 OWNER DECISION COMPLETE / REMEDIATION REQUIRED (MIME allowlist + durable failure trace, decided 30/08/2026, not implemented) | implement the recorded MIME-allowlist (M2) and durable-failure-trace (M3) remediation as the next Media slice, then low-risk cleanup, then deployed-SHA canary | implement the recorded M2/M3 remediation |
| Distribution / messaging | ACTIVE | MERGED | YES | canonical Marketing mapping exists | runtime gateway canary | run Marketing-map canary |
| Command Center | ACTIVE | MERGED | YES | read-only API/UI and registry projection merged; `system_health` UNKNOWN-source bug already fixed (`3e10dbc`, 18/08/2026, predates this table's prior citation of it as open) | endpoint verification (deployed-SHA) | verify endpoint |
| Contacts Brain | PLANNED | UNKNOWN | NO | partial resolver exists | full capability and owner decision | decide whether capability is wanted |
| Queue / worker architecture | PLANNED | PLANNED | NO | no queue implementation assumed | requirement decision | decide whether queue is required |
| Generic Draft capability | PLANNED | PLANNED | NO | no generic capability claimed | business requirement confirmation | confirm requirement |

### F52 / UX-01 reconciliation

`U1 — Understanding Layer Architecture` is resolved at architecture/static
level. `UX-01 — Unified BOSS Experience` is `IN_PROGRESS`; its implementation
program/slice is `F52 / Single-Speaker Approval UX`, which preserves UX-01 as
the canonical identity. R3.2, R4, R4.1, R6.1 and R7.1–R7.2 are merged/static at the current
truth-reset SHA; R5 completed a read-only gate that rejected a new abstraction.
R6.2–R6.6 are merged/static. R7.1 (PR #1102, `3c45a87`) added the WhatsApp
semantic presentation adapter, and R7.2 (PR #1103, `1ff1cee`) normalized
inbound WhatsApp actions; both remain static/merged only. The R6 uniform consumer set is now closed: Lead
Draft, Decision New, `/update`, and `/marketing_new` are DraftFlow consumers.
Furniture and Voice remain specialized flows and are not forced into DraftFlow.
This is a documentation status, not a deployment or runtime claim. Detailed evidence is recorded in
`docs/audit/PROGRAM_DEPENDENCY_STATUS_DRIFT_AUDIT_20260828.md`.

Read-only discovery, audit and gate conclusions that change status, phase, Next,
dependency, blocker or architecture must be persisted in a canonical current-state
document, even when no code PR is created. Program relationships are explicit
only: use `IMPLEMENTATION_OF`, `DEPENDS_ON`, `BLOCKED_BY`, `MERGED_INTO` or
`CONTINUES`; otherwise report `UNKNOWN` / no explicit relationship.

### N18 Phase 3/4 reconciliation (documentation gate, 30/08/2026)

A documentation-gate pass requested a Phase 3 status write-up assuming Slice 1
was still open and Owner Resolution for non-interactive sources was an
unsolved prerequisite. Read-only Truth Reset against `origin/main` (git
ancestry + running the actual test files, not just doc claims) found both
assumptions **stale**:

- **N18 Phase 2 (Shared Write Primitives) — CLOSED** (20–21/08/2026).
- **N18 Phase 3 Slice 1 (Telegram Lead Preview → `create_lead()`) — CLOSED**
  (PR #1043, `3de2dcf`, 27/08/2026). `test_n18_slice1_lead_preview.py` 6/6 on
  current `origin/main`.
- **N18 Phase 4 (Telegram approve/cancel buttons slice) — CLOSED** (PR #1065,
  `2484f3c`, 28/08/2026) — a phase the request didn't even know had already
  landed. `test_n18_phase4_telegram_buttons.py` 4/4,
  `test_n18_draft_dispatch_unification.py` 8/8.
- **Owner Resolution for non-interactive Lead sources — already implemented**,
  not `PLANNED`: `core/source_owner_mapping.py` (`resolve_owner_user_id()`,
  `resolve_furniture_owner_user_id()`) is consumed by
  `core/noninteractive_lead_cutovers.py`'s `create_email_inbound_lead()`,
  `create_furniture_inbound_lead()` and `create_voice_inbound_lead()`, all
  three of which call the canonical `create_lead()` directly.
- Of the 5 writers the request listed as "remaining legacy/direct": WhatsApp
  (`lead_capture.py` and the flag-gated `core/whatsapp_lead_cutover.py`),
  Email and Furniture are **already canonical in code today**. `LeadMemory`
  is a post-write enrichment/update path (`core.lead_service.update_lead_fields()`)
  and never creates a Lead — not a creation-writer gap at all. **Voice IVR**
  is the one genuine remaining gap: its canonical path
  (`create_voice_inbound_lead()`) exists and already resolves Owner, but a
  live `airtable_add()` fallback still executes whenever
  `VOICE_CANONICAL_LEAD_WRITE` is off (its current default).

**ACTIVE status stands** — this is Phase 5/N18 remaining-work reconciliation,
not a reopening. Remaining work is exactly what `N18` already said in
`BOSS_UNIFIED_MASTER_PLAN.md` §3.5 and `ROADMAP.md`: owner-gated
`WHATSAPP_CANONICAL_LEAD_WRITE`/`VOICE_CANONICAL_LEAD_WRITE` activation and a
live canary, constrained today by the inability to perform a new deployment
from this environment — a runtime-verification constraint, not a development
freeze. Full writer-by-writer detail:
[`N18_PHASE_3_CANONICAL_LEAD_WRITERS_SPEC.md`](../architecture/n18-canonical-lead-writers/N18_PHASE_3_CANONICAL_LEAD_WRITERS_SPEC.md).

---

## NUMBERED AUDIT SNAPSHOT — CURRENT TERMINAL STATUS

- **#8 Test Gap** — **CLOSED / STATIC VERIFIED + CI ENFORCED**
  (remediation 26/08/2026, Truth-Reset SHA
  `00853b09f1c65a53535240545ba410da012c14f3`). Both findings from the
  status-reconciliation pass remediated; full record: `BUG_AUDIT_LOG.md`
  ("Audit #8 — Test Gap — CLOSURE (Combined Fix)"). The 24/08/2026
  "ALREADY CLOSED" line and the 26/08/2026 "OPEN — CURRENT TEST GAPS"
  reconciliation are both preserved as-written in `MAINTENANCE_STATUS_MATRIX.md`/
  `MAINTENANCE_DEFERRED_REGISTER.md` — not rewritten; this is the next
  closure in the chronology.
  - **#8-1** — CLOSED / VERIFIED, evidence adopted from PR #1017's existing
    regression (`test_approval_concurrency.py` Test 1 + Test 6) — no
    duplicate test added. Satisfies all 4 required proof criteria: matching
    tenant succeeds, mismatched tenant is rejected (HTTP 409), the canonical
    `action_gateway.approve()` path is never called on mismatch, and the
    real production `_is_canonical_tma_contract()` guard (`tma_api.py:2344`)
    is exercised end-to-end, not just a local fake.
  - **#8-2** — CLOSED / CI ENFORCED. New dedicated blocking `pytest` step in
    `.github/workflows/ci.yml` for `test_phase_4b_1b_durable_lifecycle.py`,
    matching the existing `test_context_librarian.py`/
    `test_refresh_after_merge.py`/`test_reconcile.py` pattern. Verified: 18
    tests collected, 18 executed, 18 PASS (0 xfail/skip), an intentionally
    sabotaged assertion correctly failed `pytest -x` (then fully reverted),
    the `ALLOWED_CONTRACT_TRANSITIONS` legality regression (#9-3) is
    included, no `continue-on-error`/`|| true`. **Incidental discovery
    during first-ever CI execution (not a production defect, not a new #8
    item):** `test_stale_lifecycle_update_is_rejected_without_mutating_ram_cache`'s
    assertion predated `ExecutionLedger.update_status()`'s intentional
    BUG-127A stale-cache refresh (`core/action_gateway.py:940`) — corrected
    to assert the current intentional contract (conflict still raised,
    forbidden transition never persisted, durable truth stays authoritative,
    RAM cache may legitimately refresh from durable truth) rather than
  marked `xfail`; production code untouched.

- **#10 Dependency Risk** — **ENGINEERING CLOSED — HIGH/MEDIUM GAPS RESOLVED**.
  Truth-Reset SHA `dddacc4c00fdebec247dc54000fbfd74b263951e` (`origin/main`).
  DG-1 through DG-6 are **CLOSED**, evidenced by PRs #1003, #1004, and #1006.
  DG-7 is **DEFERRED — LOW** because the transitive Google API dependencies
  are intentional. DG-8 is **DEFERRED — LOW** because the PostgreSQL
  dependency is intentionally feature-gated. Package lifecycle/EOL remains
  **EXTERNAL VERIFICATION REQUIRED**. Current HIGH/MEDIUM gaps: **0**.
  This is not `CLEAN` while deferred items and external verification remain.

- **#22 Performance Smell** — **CLOSED / STATIC VERIFIED — RUNTIME
  VERIFICATION REMAINS** (26/08/2026, Truth-Reset SHA
  `15004c8397763e605727a63066106df455efc421`). P22-01 measurement
  instrumentation remains present for pending/executed Approvals reads; runtime
  measurement is not established. P22-02 is **CROSS-TRACK → #5 Async /
  Concurrency** and non-blocking for #22. P22-03 is a LOW accepted
  non-blocking observation. No current MEDIUM/HIGH #22-owned static gap
  remains.

- **#20 Code-to-Docs** — **CLOSED / STATIC VERIFIED** (26/08/2026, PR #1030,
  merge `15bad2e08129b96954dacfee442da7501f622040`). H1-H6 and H9/O1-O6 are
  documented in the canonical media/file/session/idempotency contract.
  Production/deployed-SHA verification was not claimed and is outside this
  static Code-to-Docs closure scope.

- **#3 Data Contract** — **AUDIT COMPLETE — ALL CURRENT CODE GAPS CLOSED /
  FINDING #2 EXPLICITLY DEFERRED** (remediation 26/08/2026, Truth-reset SHA
  `a52977278c1db0be41eeec026ce72e22fd0308a9`). Original findings #1, #3, #4,
  #5, and #6 are CLOSED; Finding #2 remains **DEFERRED — LIVE/SCHEMA CONTRACT
  DECISION**. Routed I3 is **CLOSED / STATIC VERIFIED**: `Logical Media Key`
  is provider-neutral, while `"Telegram File ID"` is now compatibility storage
  only for Telegram-originated assets. No Airtable field rename or live schema
  migration was performed. Full record: `BUG_AUDIT_LOG.md` and
  `MAINTENANCE_FILE_DRIFT_REGISTER.md`.

- **#9 Mock Fidelity** — **CLOSED / STATIC VERIFIED**
  (remediation 25/08/2026, Truth-Reset SHA
  `74808625cd59a26a06d666dfa266540e7f0d1c89`). All 4 findings from the
  Phase-1 read-only audit remediated (test/test-double changes only —
  0 production code changes); full record: `BUG_AUDIT_LOG.md` ("Audit #9 —
  Mock Fidelity (Phase 1, Read-Only)" and its closure entry).
  - **#9-1 HIGH** — CLOSED / VERIFIED. `test_approval_concurrency.py` and
    `test_pr0c0_tma_approval_truthfulness.py`'s identity/contract test
    doubles now carry a real, matching `tenant_id="boss_hq"` (was two
    vacuously-equal `None`s) — `test_phase_4b2_wiring.py` already did.
    A new negative-path regression (`test_approval_concurrency.py` Test 6)
    proves a cross-tenant contract is refused (HTTP 409, gateway never
    called) through the real `_is_canonical_tma_contract` end-to-end path.
    **CROSS-TRACK → #8 was subsequently resolved** — the broader Test Gap was
    closed by #8 remediation PR #1024; this does not change #9's findings.
  - **#9-2 MEDIUM (latent)** — CLOSED / VERIFIED. All 5 affected
    `MockIdentity.is_internal` copies now derive from `role`
    (`role in ("owner", "partner", "manager", "employee")`), matching
    `identity.py:151`, with a focused assertion per file proving both
    branches.
  - **#9-3 LOW** — CLOSED / VERIFIED. `LifecycleRepository.transition()`'s
    test fake now enforces `ALLOWED_CONTRACT_TRANSITIONS` (imported from
    `core.action_contract_repository`, not duplicated), proven by a new
    illegal-transition regression test.
  - **#9-4 LOW** — CLOSED / VERIFIED. `tc8_test_repo_stub.py`'s
    `finalize`/`release` now enforce the same claimed-state/version/
    operation-id CAS as `core/turn_state_repository.py`'s `_owner_mutate()`,
    proven by a new standalone `test_tc8_repo_stub_fidelity.py` (6/6) without
    touching the 4 existing approval-callback consumer test files.
  - **Incidental, out-of-scope findings surfaced during regression** (not
    touched, not part of #9): `test_phase_4b_1b_durable_lifecycle.py` is
    written in `pytest` style but CI's "Run test_*.py scripts" step runs it
    as plain `python3 file.py`, which executes 0 tests silently (#8-adjacent
    CI-wiring concern); `test_bug153_create_task_reconfirmation_after_rejection.py`
    has 3 pre-existing failures, reproduced identically on a clean
    `origin/main` with none of this remediation's changes applied — unrelated
    to any of the 4 findings.

- **#11 Security Surface** — **CLOSED / STATIC VERIFIED + CI ENFORCED**
  (remediation 25/08/2026, Truth-Reset SHA `8c847ec24772850fba8a04031317295337a9ffeb`).
  All 3 findings from the Phase-1 read-only audit remediated; full record:
  `BUG_AUDIT_LOG.md` ("Audit #11 — Security Surface (Phase 1, Read-Only)" and
  its closure entry).
  - **#11-1 HIGH** — CLOSED / STATIC VERIFIED. All 9 unescaped interpolation
    sites (`inbound_handler.py`, `lead_capture.py`, `lead_memory.py`,
    `core/lead_buffer.py`, `ad_attribution.py`, `session_store.py`) now route
    the interpolated value through `escape_formula_value()`
    (`tools/airtable_gateway.py`) before it reaches the `filterByFormula`
    string. `core/noninteractive_lead_cutovers.py:22,38` reviewed and
    deliberately left unchanged — those lines build the `memory_key` field
    value itself (not a formula), and escaping there would corrupt the
    stored field content and break exact-match lookups elsewhere. **Production
    reachability of `EMAIL_INBOUND` remains UNVERIFIED from a read-only repo
    audit** — not a reason to keep the static finding open now the code gap
    is removed; only blocks a production-verified claim.
  - **#11-2 MEDIUM** — CLOSED / STATIC VERIFIED. `tma_api.py:95-100`'s
    `RuntimeError` handler now returns `{"error": "internal_error"}` only —
    no `str(e)` reaches the client; server-side `logger.error(...)` still
    retains full detail. Proven by
    `test_bug11_2_tma_runtime_error_no_detail_leak.py` (6/6 checks).
  - **#11-3 MEDIUM (coverage)** — CLOSED / CI ENFORCED. New blocking guard
    `tools/audit_formula_escaping_boundary.py` (AST-based, same pattern as
    `tools/audit_gateway_bypass.py`/`audit_dispatcher_bypass.py`/
    `audit_provider_boundary.py`) wired into `.github/workflows/ci.yml` as a
    blocking step — no `continue-on-error`/`|| true`. Repo-wide scan:
    `NEW (0)`, 5 pre-existing legacy-baseline sites carried forward
    unchanged (all previously documented as NOT COUNTED / out-of-scope).
    Proven by `test_audit_formula_escaping_boundary.py` (6/6 checks: unsafe
    interpolation rejected, both sanctioned escape patterns accepted,
    canonical query-renderer output accepted, static/constant formulas and
    log messages resembling the shape not incorrectly rejected).
  - **Routed input consumed (Phase 1, unaffected by this closure):**
    `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s "Future-audit cross-reference"
    §#11 row (J2 fail-open context, owner R-C06-8) — evaluated as ALREADY
    VERIFIED (deny-by-default `READONLY`/`LEAD` fallback, not a fail-open
    security gap); the underlying docs-or-code naming decision itself stays
    open under R-C06-8, not closed by this track.

- **#7 CLI / Admin Tools** — CLOSED (25/08/2026). Seven PRs (#936, #939, #940,
  #943, #944, #945, #946); no real CURRENT GAP remains under #7 ownership.
  Full record: `CHANGE_CONTROL_LOG.md` ("Track D-Structure Audit #7 — CLI /
  Admin Tools closure"). `diagnose_airtable.py` import safety is also CLOSED
  / VERIFIED (its `__main__` guard exists on current main — PR #930, merged
  before this track's work started).

- **#21 Orphan Artifact** — CLOSED for the identified orphan candidates.
  Evidence: `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md:42`.

- **#23 Cost Audit** — **CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION
  REMAINS** (26/08/2026, Truth-Reset SHA
  `dddacc4c00fdebec247dc54000fbfd74b263951e`). P23-M1 through P23-M8D
  verified the current reachable paid producers, durable attribution,
  truthful unknown-measurement handling, and aggregation/reporting semantics.
  I8 was reviewed as intentional separation / flag-authority clarity debt,
  not a current #23 runtime defect. `_AnthropicLLM` is not a current executed
  paid producer. Live deployment/runtime evidence remains unestablished.
  Full record: `BUG_AUDIT_LOG.md` (Audit #23 final closure capture).

- **#24 Architecture Drift** — **CLOSED / STATIC VERIFIED — RUNTIME
  VERIFICATION REMAINS** (26/08/2026, Truth-Reset SHA
  `e5033eeeee2e0b21383b269ac6b5759f36bba9d7`). Canonical capability and
  execution classification authority, immutable operation identity, shared
  execution context, and current producer authority boundaries are verified
  statically. Temporary `RouteDecision` authority is accepted; workflow
  correlation remains optional; `ExecutionKind` is observational/static only;
  no current competing legacy approval execution authority remains. Live
  deployment/runtime evidence is not established. Full record:
  `BUG_AUDIT_LOG.md` (Audit #24 final closure capture).

- **#18 SSOT** — **CLOSED / STATIC VERIFIED** (remediation 25/08/2026,
  Truth-Reset SHA `ef8363f830253c324b8da8f1b7026f29ff6faf0f`). All 3 findings
  from the Phase-1 read-only audit remediated; full record:
  `BUG_AUDIT_LOG.md` ("Audit #18 — SSOT (Phase 1, Read-Only)" and its
  closure entry).
  - **#18-1 HIGH** — CLOSED / VERIFIED. `CLAUDE.md:150` and
    `voice_adapter.py:3` now say `VOICE_IVR`, matching the registry
    (`feature_flags.py:71`) and every live call site (`app.py:6871`,
    `app.py:6887`, `voice_adapter.py:336`). Historical evidence
    (`docs/audit/M01_FEATURE_FLAG_CONSISTENCY_AUDIT.md:63`) left unchanged.
  - **#18-2 MEDIUM** — CLOSED / VERIFIED. `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s
    §F1 "Status" column for the #12 cluster rows (`worker.py`,
    `knowledge_engine.py`, `router.py`, `lead_qualifier.py`, `profile.py`,
    `creative_generator.py`) now carries an inline `RESOLVED / #12 CLOSED`
    resolution consistent with its own "Current disposition" column.
    `MAINTENANCE_DEFERRED_REGISTER.md`'s §E-F row already correctly read
    `RESOLVED / #12 CLOSED 25/08/2026` and was left unchanged. This file's
    own #12 entry below has been narrowed to remove the now-stale claim.
  - **#18-3 LOW / DOC DRIFT** — CLOSED / VERIFIED. `CLAUDE.md:159` now reads
    `worker.py: **REMOVED** (commit \`6b8573b\`)...` in place of the prior
    present-tense description.
  - Competing-authorities verdict: resolved on this branch for all 3 findings.

- **#12 File / Folder Ownership** — CLOSED. Evidence gathered and verified
  during this reconciliation pass (not previously written up anywhere): 7 of
  the 8 modules in `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s F1 cluster —
  `worker.py`, `knowledge_engine.py`, root `router.py`, `lead_qualifier.py`,
  `memory.py`, `profile.py`, `creative_generator.py` — have been removed from
  `origin/main` (PRs #909, #911, #915, #919, #922, #931, plus an earlier
  worker-module removal). The 8th, `tenant_provisioner.py`, remains by
  deliberate, already-documented owner-parked decision (test-only import,
  "needs to stay parked — business/model decision") — not a live gap.
  **Reconciled (Audit #18, 25/08/2026):** `MAINTENANCE_DEFERRED_REGISTER.md`'s
  §E-F row already read `RESOLVED / #12 CLOSED`; `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s
  §F1 table "Status" column for this cluster's removed rows now carries a
  matching inline `RESOLVED / #12 CLOSED` resolution — see #18 below.

## GOVERNANCE NOTES / ACTIVE ITEMS

- **No New Architectural Debt enforcement** — **ESTABLISHED (25/08/2026)**.
  PR #972 completed final noise verification and promoted A1–A5 to blocking.
  The merged verification recorded 49 focused guard tests passing, harmless
  changes passing, synthetic real violations failing, and no runtime or
  business-logic change. Canonical posture: `ESTABLISHED`; detail:
  `docs/governance/NO_NEW_ARCHITECTURAL_DEBT_POSTURE.md`.

- **Context Librarian provenance maintenance** — **CLOSED / COMPLETED
  (25/08/2026)**. PR #977 applied the approved mechanical reconciliation;
  `reconcile --check` is `CLEAN`, with no decision queue and no authority
  review required. The earlier provenance drift was a separate maintenance
  issue, not a #972 regression. Continue ordinary monitoring only.

**Program structure:** `#7 → #13`, `#22 → #23`. D-CORE is a separate,
independently verified track (see `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`
— `COMPLETE / READY TO FREEZE`, formal freeze an owner decision).

**Historical Track-A note:** #13 Naming Consistency is **CLOSED / CLEAN IN
OWNED SCOPE**. Its routed items remain recorded under #2, #3, and #20.

**Historical identity boundary:** #1 and #17 remain **UNKNOWN / UNASSIGNED**;
no primary source explicitly assigns their original identities. Later topic
ordering or reconstructed lists are not sufficient. Both are non-blocking
historical provenance gaps.

The complete historical identity and terminal-state ledger is
`docs/governance/MAINTENANCE_AUDIT_LEDGER.md`.

## CROSS-TRACK / HANDOFFS

From #7's triage of `audit_dispatcher_bypass.py`'s `WARN_NEW` findings —
routed to their owning tracks, not remediated by #7, not counted as #7 debt:

| Finding | Routed to |
|---|---|
| `core/google_drive_artifact_store.py:32` | Money Printer external-tools audit |
| `core/memory_retrieval.py:107` | Memory Retrieval / Episodic Memory (also relevant to Provider Portability / architecture conformance) |
| `core/runtime_schema_provider.py:204` | Airtable Schema Governance pipeline |
| `core/turn_coordinator_runtime.py:73` | Turn Coordinator architecture (also relevant to Provider Portability / architecture conformance) |

**Accepted / legitimate, no remediation required:** `scripts/verify_f15_staging.py:143`
— staging-only gated CLI (`F15_STAGING_NON_PRODUCTION`/`F15_STAGING_ENVIRONMENT`).
Continued visibility as `WARN_NEW` is intentional unless a later scanner-policy
decision changes that.

**Global hygiene, not track debt:** `origin/claude/epic-volta-wv446g` remains
unmerged and blocks `pre_session_gate.sh` for any new branch. Unrelated to
#7; recorded here only so it isn't mistaken for #7 follow-up.

## ARCHITECTURE GOVERNANCE

- **Legacy may remain temporarily. New code must converge.**
- **Approved future architecture creates a no-new-debt rule for new code,
  even before legacy migration is complete.**
- **Planning documents ≠ active execution/work documents.**

(Full Architecture Intent & Conformance Audit and the future
No-New-Architectural-Debt enforcement program are separate work — not
duplicated here. This is a management-level reference only.)
