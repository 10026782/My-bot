# Phase 4B — Rollout & Cutover

> **Provenance of this document/tooling — read this first.** The Rollout & Cutover
> implementation (§1-11, all five tools in §2) is **PR #336**. **PR #335 is a
> verification-hardening layer merged on top of #336** (see the "Verification
> hardening" note below) — it is **not** an alternative, competing, or replacement
> Cutover layer. Every tool file, gate, and procedure below is #336's; #335 only
> adds the specific hardening checks called out explicitly by name.

> **Status of this document: first pass, report-only.** Nothing in this
> document has been executed against production. No Render env var, no
> Airtable record, no production PostgreSQL row has been changed as part of
> writing it. See `RELEASE_CHECKLIST.md` / `AGENTS.md` for the general
> merge/verification discipline this rollout must still satisfy on top of
> the gates below.

**Depends on:** PR #334 ("Phase 4B-2: Approvals becomes a non-authoritative
ActionContracts projection"), merged to `main` at `4d3787e`.

**⚠️ Known doc drift (do not use as ground truth):** `ROADMAP.md` and
`CHANGE_CONTROL_LOG.md`'s most recent entries (13/07/2026) describe PR #326
(C111, the `unhashable type: 'Identity'` fix) as the latest merged Phase 4B
work. Neither file has an entry for PR #334 yet. This rollout doc and the
tooling it describes were written by reading the code directly
(`core/action_gateway.py`, `core/action_contract_repository.py`,
`core/atomic_claim_repository.py`, `tma_api.py`,
`core/approvals_projection.py`) rather than trusting those two docs — treat
them as stale until a future change updates them with a `C11x` entry for
PR #334.

**Verification hardening — PR #335, merged on top of PR #336 (not a competing "Cutover" layer):**
An independent review of the initial (pre-rebase) version of PR #335 found six gaps where a GO/clean
report could be produced without actually proving what it claimed to prove. PR #335 was then rebased
onto #336 — dropping its own from-scratch tool reimplementations entirely in favor of #336's — and now
contributes only the six hardening checks below, added directly inside #336's own tool files:

- `tools/phase_4b_rollout_readiness.py`'s `--mode preflight` now has its own mandatory
  `B.preflight_not_already_cutover` check: both flags already being ON during a *preflight* (pre-rollout)
  run is a `FAIL`, not a silent pass — a preflight check finding the rollout already happened is not
  readiness. (`--mode active`'s existing `B.flags_both_on` requirement is unchanged.)
- A new mandatory `G_regression_suite` section: `G.regression_test_files_present` (file presence) and
  `G.regression_tests_pass` (actually executes the suite, only with `--run-regression-tests`; without
  that flag it reports `SKIP`, which — like any other mandatory `SKIP` in this tool — is already
  blocking, i.e. `NO-GO`, not a silent `GO`).
- `tools/phase_4b_reconciliation.py` has an 18th check, `R18_duplicate_contract_id`: two raw
  `ActionContracts` rows sharing one `contract_id` is a data-integrity anomaly (this file's own
  `contracts_by_id` dict would otherwise silently last-write-win between them), reported as its own
  blocking finding — independent of `R3`'s existing duplicate-*projection* check.
- `tools/phase_4b_mark_legacy_approvals.py` and `tools/phase_4b_repair_projections.py` now perform
  **read-back verification** after every successful `airtable_patch()`/`airtable_create()` call: the
  affected record is re-fetched and the intended field values are confirmed before counting the write as
  applied. A mismatch lands in a dedicated `*_verify_failed` list (distinct from `*_failed`, a rejected/
  errored API call) and fails the run's exit code — a `200`/`ok` response alone was never sufficient
  proof the write actually persisted.

None of the above changes this document's rollout sequence, gates, or the observational
`tools/phase_4b_canary_verify.py` — they make the existing gates strictly harder to pass on paper, never
easier.

**⚠️ Known limitation — BUG-109 (override vs. atomic claim collision), open, not fixed:** Under
`FEATURE_ATOMIC_CLAIMS=true`, an explicitly authorized override (`route_override_word()`, the "בצע שוב
<code>" flow) re-invokes `_execute_contract()` on a contract that already has a claim row —
`action_execution_claims.contract_id` is a single, non-composite `PRIMARY KEY`, so the override's second
claim attempt is rejected as `already_claimed` regardless of idempotency key, and the override silently
does not re-dispatch. `test_stage_b_full_suite.py`'s Req6 assertions ("correct override code dispatches
again" / "consumed override code cannot re-execute") fail under this flag (134/136 passing; both failures
here). **Owner decision (14/07/2026): do not fix and do not remove/weaken these assertions until the
side effects of a fix are reviewed** — see `BUG_AUDIT_LOG.md`'s `BUG-109` entry for the full trace, the
proposed (not-yet-approved) composite-key design, and the affected-files list. This gap is **not**
currently enforced by G1 — `test_stage_b_full_suite.py` is not in
`tools/phase_4b_rollout_readiness.py`'s `_REQUIRED_REGRESSION_TEST_FILES`, so `--run-regression-tests`
does not surface it. Treat this as an open item to resolve or explicitly accept before any production
environment with live traffic enables `FEATURE_ATOMIC_CLAIMS`.

---

## 1. Current production topology

| Component | Value | Source |
|---|---|---|
| Render backend service | `https://my-bot-jqz2.onrender.com` | `docs/operations/DEPLOYMENT.md` |
| Render frontend (TMA) | Vercel, `NEXT_PUBLIC_API_URL` → backend above | `docs/operations/DEPLOYMENT.md` |
| PostgreSQL service/database | Configured via `DATABASE_URL` (Render standard) or the legacy `DATABASE_HOST`/`DATABASE_PORT`/`DATABASE_NAME`/`DATABASE_USER`/`DATABASE_PASSWORD` env vars, read by `core/database.py::get_pool()`. No `render.yaml` exists in this repo — Render config is dashboard-managed, not IaC, so the concrete database identity is only visible in the Render dashboard, not in code. | `core/database.py` |
| Airtable base | `app4bcgoX7t0HUVnm` ("Base ID פרודקשן" per `docs/operations/RUNBOOK.md`), referenced in code only via the `AIRTABLE_BASE_ID` env var | `airtable_schema.py` comments, `docs/operations/RUNBOOK.md` |
| Pre-deploy command | `python -m core.predeploy` — runs `core/database_migrations.py::run_migrations()` (every `*.sql` file under `core/migrations/` in sorted order, `CREATE TABLE/INDEX IF NOT EXISTS` throughout → **idempotent, safe to re-run on every deploy**, no-ops if PostgreSQL isn't configured), then the Emergency Stop preflight. | `core/predeploy.py`, `core/database_migrations.py`, `docs/operations/DEPLOYMENT.md` |
| `FEATURE_ACTION_CONTRACT_PERSISTENCE` | Env-var only, **default OFF**, not in `feature_flags._DEFAULTS` or `_PERSISTENT_FLAG_NAMES` — a restart with the env var unset returns to OFF. Current Render value: **not verified by this document** — the readiness tool (§2 below) reports it live at run time; this doc must never hardcode a claimed value. | `feature_flags.py` |
| `FEATURE_ATOMIC_CLAIMS` | Same shape as above — env-var only, default OFF, non-persistent. Current Render value: **not verified by this document**, see readiness tool. | `feature_flags.py` |
| Separate staging service/database | **No `render.yaml` / IaC exists**, so there is no automatically-provisioned staging service. Two docs (`docs/PHASE_4B0_1B_STAGING_RUNBOOK.md`, `docs/PHASE_4B0_1C_STAGING_WIRING.md`) describe a "Render Staging PostgreSQL" that was used for the 4B0.1B/4B0.1C concurrency and wiring verification — but `docs/PHASE_4B0_1C_STAGING_WIRING.md` itself describes an executor call shape (`_executor(tool_name, tool_inputs, contract_id)`, a `create_atomic_aware_executor()` factory) that **predates** the current `core/action_gateway.py` (which now threads `identity=`/`claim_execution_id=` through `_make_dispatch_executor`, per the C110/C111 fixes). Treat those two docs as historical descriptions of an environment that may or may not still exist in its described shape — **do not assume a live, current staging service exists** without confirming it in the Render dashboard first. §8 below covers both cases. |

**Authority model reminder (do not re-derive — this is settled by PR #334):**

- `ActionContracts` (Airtable, `Tables.ACTION_CONTRACTS = "ActionContracts"`) — the canonical contract and lifecycle record. `core/action_contract_repository.py::ActionContractRepository` is its only writer; `ALLOWED_CONTRACT_TRANSITIONS` in that file is the legal state graph.
- PostgreSQL `action_execution_claims` (`core/atomic_claim_repository.py`, schema in `core/migrations/001_action_execution_claims.sql`) — the **sole execution-ownership primitive**. `contract_id` is `PRIMARY KEY`, `execution_id` and `idempotency_key` are both `UNIQUE`. Reachable only through `ActionGateway._execute_contract()` → `execute_with_atomic_claim()` (`core/action_gateway_atomic_executor.py`) when `FEATURE_ATOMIC_CLAIMS` is on; there is no other legitimate call path to `claim_contract_execution()`.
- `Approvals` (Airtable) — non-authoritative TMA **display projection only**. `ApprovalsFields.ACTION_CONTRACT_ID` / `LEGACY_READ_ONLY` / `PROJECTED_LIFECYCLE_STATUS` (added in PR #334) mirror the canonical contract; `core/approvals_projection.py` is the pure, side-effect-free mapping used to compute the display bucket. `Approvals.STATUS`/`CONTEXT_DATA` are never read to authorize execution — `tma_api.py`'s `_is_canonical_tma_contract()` (line ~1976) is the single shared gate every Approvals-backed action (single approve/reject, bulk approve, `actionable` flag) routes through, requiring `tool_name=="tma_write"`, `trusted_source=="tma_api"`, `origin_channel=="tma"`, `approval_policy=="approval"`, `tenant_id==identity.tenant_id`, `status=="pending"`.
- Provider write + receipt (the dispatcher's actual Airtable/Google/etc. call inside `_execute_contract()`, verified through `core.anti_hallucination.verify_execution`) is the only evidence that an action actually happened — never a claimed status alone.

**No fallback exists or may be reintroduced** to raw `Approvals.CONTEXT_DATA` execution, RAM-only ledger execution, direct dispatch bypassing `ActionGateway`, or the pre-4B-2 Airtable-status claim flow. `_queue_tma_write_approval()` in `tma_api.py` already hard-refuses (HTTP 503) unless **both** `FEATURE_ACTION_CONTRACT_PERSISTENCE` (with a live repository, `getattr(_gw._ledger, "_repository", None) is not None`) **and** `FEATURE_ATOMIC_CLAIMS` (with `core.database.get_pool()` reachable) are true — this rollout must never weaken that check.

---

## 2. Rollout gates

Every gate below is a **hard stop**, not a recommendation. All five tools referenced here are report-only / observational by default (see `tools/phase_4b_rollout_readiness.py`, `tools/phase_4b_reconciliation.py`, `tools/phase_4b_mark_legacy_approvals.py`, `tools/phase_4b_repair_projections.py`, `tools/phase_4b_canary_verify.py`). Every tool writes its JSON report under `reports/runtime/` (gitignored — see `reports/samples/*.sample.json` for deterministic fixture examples of the readiness, reconciliation, and canary-evidence shapes).

| Gate | Condition to pass | Tool |
|---|---|---|
| G1 — Code readiness | `python3 tools/phase_4b_rollout_readiness.py --mode preflight --run-regression-tests` exits 0 (GO or WARNING, not NO-GO) before cutover; `--mode active --run-regression-tests` exits 0 after both flags are enabled. Omitting `--run-regression-tests` reports `G.regression_tests_pass=SKIP`, which is already blocking (`NO-GO`) — a real GO requires it. | readiness |
| G2 — No orphaned/anomalous state | `python3 tools/phase_4b_reconciliation.py --tenant-id <tenant>` reports zero `blocking_findings` | reconciliation |
| G3 — Legacy rows marked | Every pre-4B-2 Approvals row (`action_contract_id` empty) has `legacy_read_only=true`, confirmed by re-running reconciliation after `phase_4b_mark_legacy_approvals.py --apply` | legacy marking + reconciliation |
| G4 — Both flags flip together | `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS` are set in the **same** Render configuration change — never one without the other | Render dashboard (manual) |
| G5 — Canary evidence | The 15-point canary checklist (§9) plus the 10 follow-up scenarios all pass, each verified with `tools/phase_4b_canary_verify.py` and assembled into `reports/runtime/phase_4b_canary_evidence.json` | manual + `phase_4b_canary_verify.py` + evidence file |
| G6 — Owner approval | Explicit sign-off recorded before each of: legacy-apply, flag-flip, and canary execution | manual |

No gate may be skipped because a later gate looks fine. Reconciliation must be re-run after legacy marking and again after the flags are enabled (§9).

---

## 3. Exact Render deployment order

1. Confirm PR #334 (and this rollout tooling PR) are merged to `main`; capture the exact commit SHA.
2. Confirm the Render **Pre-Deploy Command** is `python -m core.predeploy` (which runs `core/database_migrations.py` first, then the Emergency Stop preflight — this rollout does not add new migrations, `core/migrations/001_action_execution_claims.sql` already covers `action_execution_claims`).
3. Run `tools/phase_4b_rollout_readiness.py --mode preflight --run-regression-tests` against the target environment — both flags may still be off at this point (if they're already both ON, this is itself a blocking `B.preflight_not_already_cutover` finding).
4. Run `tools/phase_4b_reconciliation.py --tenant-id <tenant>` in report-only mode; review every blocking finding with the owner.
5. Run `tools/phase_4b_mark_legacy_approvals.py --report-only`; get explicit owner approval; only then run with `--apply --confirm APPLY_LEGACY_READ_ONLY`.
6. Re-run reconciliation — expect zero rows with `action_contract_id` empty and `legacy_read_only` false.
7. Deploy the exact reviewed `main` commit (this triggers the pre-deploy migration command automatically — idempotent, safe even though the claims table already exists).
8. Confirm the deploy succeeded and the app started (`/health`).
9. In **one** Render configuration change, set both `FEATURE_ACTION_CONTRACT_PERSISTENCE=true` and `FEATURE_ATOMIC_CLAIMS=true`.
10. Restart/redeploy once to apply the env change (Render env var changes require a restart to take effect for a running process; do not rely on a hot env reload).
11. Re-run `tools/phase_4b_rollout_readiness.py --mode preflight --run-regression-tests` — must be GO.
12. Run exactly one low-risk production canary (§9).
13. Only after the canary is fully verified, resume normal TMA approval traffic (§9 step 18-20).

---

## 4. Canary test procedure

See §9 (Required canary tests) for the full checklist. Summary: one harmless manager-initiated TMA write → verify contract creation → verify single projection → owner approves → verify claim → verify provider write happens exactly once → verify full lifecycle convergence (claim, contract, projection, legacy `STATUS` mirror) → verify a second approval attempt is a no-op (zero additional provider writes). Then one reject canary, one PATCH canary, and the 8 adversarial/edge scenarios listed in §9.

---

## 5. Reconciliation procedure

Run `python3 tools/phase_4b_reconciliation.py --tenant-id <tenant>` (report-only by default; it has no `--apply` mode at all — see tool file; `--tenant-id` is required, since R10 verifies every contract-linked Approvals row belongs to that one tenant — omitting it is itself a guaranteed blocking finding, never a silent pass). It cross-references:

- All `ActionContracts` rows (`tools/phase_4b_rollout_common.py::fetch_all_action_contracts()`)
- All `Approvals` rows (`fetch_all_approvals()`)
- All PostgreSQL `action_execution_claims` rows (`fetch_all_claims()`, skipped with a warning if PostgreSQL is unreachable)

against the 18 anomaly classes in `tools/phase_4b_reconciliation.py`'s module docstring, and separates its findings into `blocking_findings` / `warnings` / `informational`. The **mandatory rollout target** is stated in that file and repeated in the report's `rollout_target_met` field: zero orphaned contract-linked projections, zero cross-tenant mismatches, zero non-TMA contracts exposed as TMA approvals, zero executable legacy rows, zero contract-linked rows with non-empty `CONTEXT_DATA`, zero duplicate active projections, zero unresolved claim-ownership anomalies.

Run reconciliation: before legacy marking, after legacy marking, after the flags are enabled, and again after the canary. Never repair anything from this tool — that's `tools/phase_4b_repair_projections.py`'s job, and only for the safe display-repair subset it documents.

---

## 6. Rollback procedure

See §11 below (kept in one place, referenced from here) — summary: disable both flags together, never restore the legacy execution path, never delete contracts/claims, never retry `outcome_unknown` automatically, re-run readiness + reconciliation, investigate before any new GO decision.

---

## 7. Owner-approval checkpoints before every live mutation

No mutation happens without an explicit, recorded owner approval immediately before it:

1. **Before** `tools/phase_4b_mark_legacy_approvals.py --apply --confirm APPLY_LEGACY_READ_ONLY` — owner reviews the exact record-ID list the tool printed in `--report-only` mode first.
2. **Before** flipping `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` to `true` in Render — owner reviews the readiness + reconciliation reports.
3. **Before** running the production canary — owner is aware a real (harmless) TMA write will be proposed, approved, and executed against production Airtable.
4. **Before** resuming bulk TMA approval traffic — owner has seen at least one successful approve canary and one successful reject canary complete correctly end-to-end.
5. **Before** any `tools/phase_4b_repair_projections.py --apply --confirm APPLY_PROJECTION_REPAIRS` run, if that tool is ever needed — owner reviews the exact proposed repairs first.

If no isolated staging environment can be confirmed to exist (§1), step 2 above additionally requires an explicit owner sign-off that this is a **production canary**, not a staging dry run — see §8 below ("Staging / controlled test plan").

---

## 8. Staging / controlled test plan

**Preferred:** a separate Render staging service, separate PostgreSQL database, and separate Airtable base, so every gate in §2 (except the final canary) can be exercised without touching production.

**When no isolated staging environment can be confirmed to exist** (see §1's caveat about `docs/PHASE_4B0_1B_STAGING_RUNBOOK.md`/`docs/PHASE_4B0_1C_STAGING_WIRING.md` describing a possibly-stale staging setup): do not silently treat production as staging. Instead:

1. State explicitly, in the readiness report and to the owner, that no confirmed isolated staging environment exists for this rollout.
2. Produce a **production-canary plan** — this document's §9, run against production with the smallest possible blast radius (one manager-initiated write to a table already in `_TMA_WRITE_ALLOWED_TABLES`, reversible data, one record).
3. Stop and obtain explicit owner approval before touching Render env vars or any live data, exactly as in the general owner-approval checkpoints above.

Deploy the exact reviewed commit — never a locally-modified working tree, never a different branch than what was reviewed.

Verify after deployment (before flipping any flag):
- Application starts successfully (`/health` returns healthy).
- `core.database.get_pool()` succeeds (verified indirectly via the readiness tool, not by adding new production-only debug endpoints).
- `action_execution_claims` exists with the expected schema.
- `ActionContractRepository` is reachable (a real, harmless read, e.g. `find_pending_by_canonical_user()` on a probe ID that will never match).
- Readiness report is GO.
- Reconciliation report has zero blocking findings.

Then, and only then, proceed to §10 (flip both flags together, restart once).

---

## 9. Required canary tests

Do not start with bulk approval. Run **exactly one** controlled low-risk TMA canary first:

1. Manager requests one harmless test write (a table already in `_TMA_WRITE_ALLOWED_TABLES`, a field that's easy to revert).
2. Verify an `ActionContract` is created with `status="pending"` (read via the readiness/reconciliation tooling or a manual Airtable check — never by trusting the HTTP response alone).
3. Verify exactly one `Approvals` projection row is created for that `contract_id`.
4. Verify `Approvals.CONTEXT_DATA` is empty on that row (`_ensure_approval_projection`/`_repair_approval_projection` always blank it).
5. Verify the projection is actionable only for the correct tenant/owner (`_is_canonical_tma_contract` / `_projection_actionable`).
6. Owner approves via the TMA.
7. Verify exactly one PostgreSQL `action_execution_claims` row is created for that `contract_id` (`status="executing"` at claim time).
8. Verify the provider write (the actual Airtable `airtable_add`/`airtable_patch` the dispatcher performs) happens **exactly once** — check the target record's data/audit log, not just the HTTP response.
9. Verify the claim reaches `status="completed"`.
10. Verify the `ActionContract` reaches `status="completed"`.
11. Verify `Approvals.projected_lifecycle_status` reaches `"completed"` (`ProjectedLifecycleStatus.COMPLETED`).
12. Verify the legacy display `Approvals.STATUS` field is synchronized to a sensible terminal value (not left at "ממתין"/pending).
13. Verify the receipt/audit trail contains **distinct** `requested_by` and `approved_by` identities (not the same actor).
14. Verify the external record ID (the created/patched Airtable record's `id`) is present in the evidence.
15. Verify a **second** approval attempt on the same (now-completed) contract performs **zero** additional provider writes (idempotent no-op, not a duplicate write).

Then run, each as its own isolated canary with its own evidence entry:

- One reject canary (steps 1-6 analogous, ending in `status="rejected"`, no claim ever created, no provider write).
- One PATCH canary (op="patch" instead of "post", same lifecycle assertions).
- Two concurrent approval attempts against the same contract (expect exactly one `acquired` claim, one `already_claimed`/`contract_identity_conflict`, zero double-execution).
- An application restart between proposal and approval (contract must survive via the durable repository — `ExecutionLedger.find_by_id()`'s cache-miss recovery path).
- A projection-sync failure simulation (contract executes correctly even if the Approvals projection write fails — canonical state is never blocked on display-layer success, per `_ensure_approval_projection`'s "never rolls back the contract" contract).
- A direct-dispatch attempt with a forged `execution_context` dict (must be refused — `tools/approval_actions.py::tma_write()`'s `_verify_active_execution_claim()` against a live PostgreSQL claim, not a caller-constructed dict).
- A legacy-row approval attempt (an Approvals row with no `action_contract_id` — must be refused before any contract lookup).
- A projection pointing at a non-TMA contract (e.g. a `gmail_send_draft` contract's id planted into an Approvals row) — must be refused by `_is_canonical_tma_contract`.
- A cross-tenant projection attempt (contract's `tenant_id` differs from the approving identity's `tenant_id`) — must be refused.
- A flags-disabled request (temporarily simulate one flag off, or test this before §9's flip) — expect HTTP 503 and zero writes anywhere.

For any `outcome_unknown` result: do not retry automatically. Stop and require manual reconciliation (`tools/phase_4b_reconciliation.py` flags "Executing/outcome_unknown claims requiring manual attention" and "Claims whose canonical ActionContract cannot be found" explicitly).

Verify each scenario with `tools/phase_4b_canary_verify.py --contract-id <id> --expected-outcome {completed|rejected|outcome_unknown} [--approval-record-id <id>] [--provider-table <table> --provider-record-id <id>]` — `--expected-outcome` is required, and a pending/approved/executing contract can never be reported VERIFIED regardless of which value is passed. `completed` additionally requires supplied, existing provider evidence (`--provider-table`/`--provider-record-id` are not optional in that case); `outcome_unknown`, once confirmed, returns verdict=MANUAL_REVIEW — never VERIFIED, never a blunt FAILED. It is purely observational (never proposes, approves, rejects, dispatches, claims, retries, or writes) and cross-checks contract/projection/claim/provider IDs, lifecycle alignment, requester/approver separation (compared via stable IDs — actor_user_id/canonical_user_id vs approved_by, never actor_display_name), and duplicate-execution evidence. Save all of the above as structured evidence (IDs and statuses, no secrets, no full sensitive payloads) in `reports/runtime/phase_4b_canary_evidence.json` — see `reports/samples/phase_4b_canary_evidence.sample.json` for the expected shape.

---

## 10. Production cutover — exact sequence

1. Confirm PR #334 and this rollout tooling PR are both merged to `main`.
2. Confirm the current `main` SHA (`git rev-parse origin/main`).
3. Confirm the Render Pre-Deploy Command is `python -m core.predeploy` (which runs `core/database_migrations.py` first, then the Emergency Stop preflight).
4. Run `tools/phase_4b_rollout_readiness.py --mode preflight --run-regression-tests`.
5. Run `tools/phase_4b_reconciliation.py --tenant-id <tenant>` in report-only mode.
6. Review every blocking finding with the owner; do not proceed while any remain open.
7. Run `tools/phase_4b_mark_legacy_approvals.py --report-only`; review the exact record IDs proposed.
8. Obtain explicit owner approval for the legacy-apply step.
9. Apply legacy marking only: `tools/phase_4b_mark_legacy_approvals.py --apply --confirm APPLY_LEGACY_READ_ONLY`.
10. Re-run reconciliation — confirm zero legacy rows remain unmarked.
11. Deploy `main` at the confirmed SHA.
12. Confirm the pre-deploy migration succeeded (Render deploy log) and the app started.
13. In one Render configuration change, enable both `FEATURE_ACTION_CONTRACT_PERSISTENCE=true` and `FEATURE_ATOMIC_CLAIMS=true`.
14. Restart/deploy once to apply the change.
15. Run `tools/phase_4b_rollout_readiness.py --mode active --run-regression-tests` again — must be GO (both flags must now genuinely be on and wired).
16. Run exactly one low-risk production canary (§9, points 1-15).
17. Verify the `ActionContract`, PostgreSQL claim, `Approvals` projection, provider record, and audit/receipt all agree.
18. Only after the canary is fully verified may normal TMA approvals resume.
19. Do not enable bulk approval until at least one single approve **and** one reject have completed correctly.
20. Monitor logs and re-run reconciliation periodically for at least the initial rollout window (recommend: hourly for the first day, daily for the following week — adjust based on TMA write volume).

---

## 11. Rollback procedure

Rollback **never** restores the old direct-execution path. When a blocking problem appears:

1. Disable both flags together: `FEATURE_ACTION_CONTRACT_PERSISTENCE=false`, `FEATURE_ATOMIC_CLAIMS=false`.
2. Accept that new approval-required TMA writes will return HTTP 503 (`_queue_tma_write_approval`'s existing fail-closed behavior) until re-enabled.
3. Do not replay `Approvals.CONTEXT_DATA` for any row.
4. Do not delete any `ActionContracts` row.
5. Do not delete any PostgreSQL execution claim.
6. Do not retry any `outcome_unknown` claim automatically.
7. Run `tools/phase_4b_rollout_readiness.py --mode active` (to confirm the flags are indeed off again) and `tools/phase_4b_reconciliation.py --tenant-id <tenant>` to capture the exact state at the moment of rollback.
8. Preserve all provider records and receipts (do not delete/edit the underlying Airtable records the contract wrote to).
9. Investigate root cause before re-enabling anything.
10. Re-enable only after a new, explicit GO decision from a fresh readiness run — not by assuming the original GO still holds.

Disabling the flags is a traffic stop, not a data rollback — no data is undone by this step, only new execution is halted.
