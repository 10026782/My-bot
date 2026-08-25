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
**Truth Reset SHA at last update:** `ef8363f830253c324b8da8f1b7026f29ff6faf0f`

---

## CLOSED

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
