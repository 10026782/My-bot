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

**Last updated:** 25/08/2026
**Truth Reset SHA at last update:** `9399979cd6decc5d8418ed607c9abb364364bb88`

---

## OPEN

- **#9 Mock Fidelity** — 🔴 **OPEN — CURRENT MOCK FIDELITY GAPS**
  (Phase 1 read-only audit, documentation capture 25/08/2026, Truth-Reset SHA
  `9399979cd6decc5d8418ed607c9abb364364bb88`). Full record: `BUG_AUDIT_LOG.md`
  ("Audit #9 — Mock Fidelity (Phase 1, Read-Only)"). No remediation performed
  in this pass — documentation only.
  - **#9-1 HIGH** — TMA approval tenant-isolation check
    (`tma_api.py:2344` `_is_canonical_tma_contract`) is exercised only on its
    all-conditions-pass branch across every test that touches it
    (`test_approval_concurrency.py:90-140`, `test_phase_4b2_wiring.py:106-149`,
    `test_pr0c0_tma_approval_truthfulness.py`) — no test asserts a tenant
    mismatch is rejected. A regression weakening the tenant guard would pass
    the suite undetected. CROSS-TRACK → #8 for the broader negative-path
    Test Gap.
  - **#9-2 MEDIUM (latent)** — 5 test files hardcode
    `MockIdentity.is_internal = True` unconditionally instead of deriving it
    from `role` like `identity.py:151` and 3 other correct test copies do.
    Not currently exploited (all 5 use `role="owner"` today) — dormant risk
    if a future test in those files uses a non-internal role.
  - **#9-3 LOW** — `LifecycleRepository` test fake
    (`test_phase_4b_1b_durable_lifecycle.py:56-74`) omits the transition-legality
    check that `core/action_contract_repository.py:241-245` enforces in
    production. Not currently reachable via user input.
  - **#9-4 LOW** — `tc8_test_repo_stub.py:52-67`'s `finalize`/`release` drop the
    CAS/ownership check `core/turn_state_repository.py:272-329` enforces in
    production. Mitigated — the consuming path is non-fatal cleanup, and TC8's
    real CAS semantics are separately covered with high fidelity elsewhere.
  - CROSS-TRACK → #2/#3 (`providers/airtable_shim.py` stale docstring) and
    → #11 (`test_bugdh03_04_formula_injection.py`, already-closed territory,
    no new gap) also recorded — not pursued under #9.

## CLOSED

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

## ACTIVE

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

**Next Track-A item: #13 Naming Consistency.** Not started, not active — do
not mark it complete or in-progress beyond this. Known routed input for #13
(from `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s cross-reference table): I1–I3,
I5, I7–I10, K10.

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
