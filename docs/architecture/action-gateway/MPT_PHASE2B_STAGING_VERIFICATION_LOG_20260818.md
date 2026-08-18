# MPT Phase 2B — staging verification session log (18–19/08/2026)

**Status:** canonical execution path (`ActionContract → approval (ActionGateway) → dispatcher → ExternalExecutionBoundary → MoneyPrinterTurboAdapter`) is **proven correct and independently verified**, multiple times, directly against Airtable (not just terminal output). A real, provable defect in the verification harness itself was found and fixed (PR #740). No fresh `completed` MPT render was achieved *this session* — blocked by two infrastructure gaps documented in §3, neither of which is a defect in the tested code path. Two historically-completed runs (§2.4) already prove the path *can* reach `completed` under the right conditions.

**Source:** direct interactive work on `my-bot-approval-staging` (`srv-d99uq63eo5us73967cj0`), Airtable base `app4bcgoX7t0HUVnm`, plus independent cross-checks against that base via a separate Airtable connector (not the app's own code path) and read-only Render API calls. All record IDs, timestamps, and evidence below were read directly from Airtable, not inferred from pasted logs alone.

---

## 1. Bug found and fixed: harness never bootstrapped the Emergency Stop manager

`scripts/verify_mpt_phase2b_staging.py` (added in PR #736) did `import app` and then read `feature_flags.is_enabled("EMERGENCY_STOP_ALL")`. `app.py`'s own module docstring is explicit that `import app` alone **never** runs `run_startup_sequence()` / `bootstrap_emergency_stop()` — only gunicorn's `post_worker_init` hook or `python3 app.py`'s `__main__` block does. Without a configured manager, `is_enabled("EMERGENCY_STOP_ALL")` **fails closed to `True`** (`feature_flags.py`, `except EmergencyStopNotConfigured: return True`).

Net effect: every run of the harness, as originally merged, evaluated `EMERGENCY_STOP_ALL` as blocked regardless of the real durable value — including the harness's own preflight print. Confirmed directly: a bare `import app` followed by `feature_flags.clear_emergency_stop(...)` raised `EmergencyStopNotConfigured` on staging.

**Fix (PR #740, merged `da2c0f3`):** call `bootstrap_emergency_stop()` (store+manager construction and one synchronous hydration read only — no scheduler thread, no webhook re-registration) once at the top of `main()`, before `_preflight()`. CI green, `origin/main` now contains it at `db8e27d` and later.

---

## 2. Real staging runs this session (chronological, all cross-verified via direct Airtable reads)

### 2.1 Run 1 — pre-fix, EmergencyStop fail-closed default
Contract `f6831c0f-b04b-40a2-aa0a-9b6d110c5413`. Blocked at `tools/dispatcher.py`'s `EMERGENCY_STOP_ALL` check before reaching the boundary — **no `ExternalExecutionJob` record was created**. This was the fail-closed artifact from §1, not a real durable block (confirmed after the fact by independently reading the real durable value).

### 2.2 Run 2 — post-fix, real durable EmergencyStop block observed and cleared
- Confirmed real durable state via `bootstrap_emergency_stop()` + `get_emergency_stop_status()`: `EMERGENCY_STOP_ALL blocked=True, source=durable, operation_id=85b39d6a-...`.
- `clear_emergency_stop(...)` → `ok=True, verified=True` (op `mpt-phase2b-test-20260818`).
- Harness run → contract `0783d53a-f6ec-4034-8ddb-6daa1f6574f8`. Reached `ExternalExecutionBoundary` correctly this time — blocked instead by `MPT_CONCURRENCY_LIMIT` (a genuinely concurrent `submitted` job at that moment, contract `7120f948-...`, itself later resolved to `outcome_unknown`/`mpt_process_state_unknown`). Job left at `status=created`, `evidence={"capacity":"MPT_CONCURRENCY_LIMIT"}` — correct behavior per `core/mpt_runtime_policy.py`'s `active_count()`/`capacity_reason()`.
- `set_emergency_stop(..., True, ...)` → `ok=True, verified=True` (op `mpt-phase2b-restore-20260818-3`). Independently confirmed via direct Airtable read.
- Independently confirmed capacity was free afterward: 0 jobs at `status='submitted'`, `daily_count=1 < 3`.

### 2.3 Run 3 — real MPT subprocess reached, real content-validation rejection
Media fixture: a 3-second flat-color test clip (`ffmpeg -f lavfi color=...`). Clear → run → contract `dbbeaad2-7e4a-4384-bdff-d878bfd61c59`, `provider_job_id=e6576f1e-7d54-45b9-b2aa-13788e96d38f`. The real `cli.py` subprocess ran for **107.4s** on `runtime_profile=plan-srv-008` and exited code 1. `poll()` correctly classified it: `status=failed`, `failure_code=mpt_media_validation_failed`, `evidence.failure_classification=MEDIA_VALIDATION_FAILED`. Root cause: `.mpt-runtime/app/models/schema.py:81` — `video_clip_duration` defaults to **5 seconds**; `material.py` rejects any source clip shorter than that. No auto-retry occurred — correct, `MEDIA_VALIDATION_FAILED` is not in `RETRYABLE_FAILURES`. Restored (`mpt-phase2b-restore-20260819-000356`, `ok=True, verified=True`).

### 2.4 Run 4 attempt (fixture generation) — OOM crash before submit
Attempted a longer, richer fixture (`testsrc=1080x1920, 10s, 30fps`) directly on the interactive shell. This crashed the **entire Render instance** (`Ran out of memory (used over 512MB)`) during `ffmpeg` generation, before the flag was ever cleared. `EMERGENCY_STOP_ALL` was untouched (confirmed still `true` afterward) — nothing unsafe happened, but nothing progressed either.

### 2.5 Run 5 — real render reached, OOM mid-render, real durable-flag exposure window
Leaner fixture this time (`color=..., 480x854, 6s, 10fps` — succeeded, no OOM at generation). Clear (`mpt-phase2b-test-20260819-003605`, `ok=True, verified=True`) → harness run → contract `6e544a6a-4f98-4552-aa5b-8f1cf028c58d`, `provider_job_id=a1c2956a-5360-4d03-a47c-d101de2f9f5f`, real subprocess launched, `status=submitted`. **The instance OOM-crashed mid-render** (`Ran out of memory (used over 512MB)`). Because the restore command hadn't run yet, `EMERGENCY_STOP_ALL` was left durably `false` on the shared, production-adjacent base for longer than intended — caught and restored as soon as noticed (`mpt-phase2b-restore-20260819-004343`, `ok=True, verified=True`, independently confirmed). After the instance auto-restarted, the scheduler polled the orphaned job: process gone, no `exit_status` written → correctly classified `status=outcome_unknown`, `failure_code=mpt_process_state_unknown`. No auto-retry — correct, `OUTCOME_UNKNOWN` is in `NEVER_RETRY_FAILURES`.

**Operational note for next time:** the restore step must be treated as equally time-critical as the clear step. A crash between clear and restore is exactly the failure mode the original Decision's "restore immediately after" instruction was meant to prevent — worth having the restore auto-triggered (e.g., a `trap`) rather than a manually-run follow-up command, *if* that can be done without the added complexity itself becoming a new crash source (a combined trap+subshell block was tried once this session and its outcome couldn't be confirmed — kept as a possible improvement, not adopted here).

### 2.6 Historical completed runs (pre-dating this session, found via cross-check — not this session's evidence, but proof the path can reach `completed`)
- Contract `e2d9db58-e8a1-4b2e-953b-8d09b03480bc` (~17/08 05:39 UTC): `status=completed`, Google Drive artifact `drive_file_id=1GTpGV3uoWTzLOaa5-LGAo3nrhj-JyZHp`, `sha256=3f4787bd225fd84df3bc9641b200a4d86fe9747c787c893d70b2971cdabb8d5c`, `size=178203`, `mime_type=video/mp4`.
- Contract `f5c73380-40b5-4fda-a626-6049d69bf0b6` (~16/08 14:35 UTC): `status=completed`, local `result_ref`, `sha256=76771f08e7b51fc1747a4e73599799b6f7dac8ba795293844f97394ee9d58941`, `size=178500`.

Both are consistent with §3.2's finding: completion requires `submit()` and the polling scheduler to run in the *same* container — these were almost certainly both run directly from the persistent service's own process, not a separate one-off Job.

---

## 3. Infrastructure gaps found (not defects in the tested canonical path)

### 3.1 Gap A — Starter plan (512MB) insufficient for a real MPT render
`srv-d99uq63eo5us73967cj0`'s actual provisioned Render plan is `starter` (512MB RAM, confirmed via `GET /v1/services/{id}`). `core/mpt_runtime_policy.py`'s `MPTExecutionPolicy.runtime_supported()` already whitelists `MPT_RUNTIME_PROFILE=plan-srv-008` (this service's configured value) as a supported profile, alongside `"standard-2gb"` — i.e. the code already assumes a ~2GB-class runtime. The actual provisioned plan does not match that assumption. Two real OOM crashes this session (§2.4, §2.5) confirm 512MB is insufficient for MoneyPrinterTurbo's real render/TTS pipeline. **Not fixed this session** — this is a billing/infrastructure decision (upgrade the persistent service's Instance Type, temporarily or permanently), not a code change.

### 3.2 Gap B — Render One-Off Jobs cannot be polled to completion by the live service
`MoneyPrinterTurboAdapter.poll()` (`core/moneyprinterturbo_adapter.py`) detects completion by reading **local files** (`$MPT_JOBS_ROOT/<provider_job_id>/manifest.json`, `exit_status`) and checking a **local OS PID** (`_pid_alive(pid)`). The actual polling loop (`scheduler.py`'s `_job_external_execution_poll()` → `get_default_boundary().poll_due()`) only ever runs inside the **persistent service's own container**. A Render One-Off Job runs in a **separate, freshly-created container** — confirmed directly this session: fixture files created in the interactive shell (`/tmp/mpt-approved-media/clip1.mp4`, `/tmp/mpt_approved_script.txt`) were absent (`No such file or directory`) inside a fresh one-off Job's container.

Consequence, reasoned through but **not attempted** (correctly avoided, not just theorized): submitting via a one-off Job — even a well-resourced one (`--plan-id plan-srv-008`, i.e. Standard/2GB) — would let the render actually complete, but the live scheduler would never find `manifest.json`/`exit_status` in *its own* container's `/tmp/mpt-jobs/`, and would eventually mark the job `outcome_unknown` via the same exception path as any missing-file case. Because the Google Drive upload only happens inside `poll()`'s success branch, a genuinely-finished render would never be uploaded — real render cost spent, artifact unrecoverable. Worse, until that first failed poll attempt, the job sits at `status='submitted'`, which `active_count()` counts toward the concurrency ceiling — a **permanently stuck active slot**, strictly worse than the clean `outcome_unknown` outcomes actually observed in §2.2/§2.5.

**Not fixed this session** — needs a real design decision: either (a) a Render persistent Disk shared between the service and its one-off Jobs, plus rethinking the PID-liveness half of `poll()` (file-based exit-status detection could work across a shared disk; OS PID checks fundamentally cannot), or (b) restructure so a single one-off Job's own process does `submit()` + polls itself internally to a terminal state, without depending on the separate scheduler, or (c) keep running actual completions only from the persistent service's own container and accept its RAM ceiling (i.e., resolve only Gap A).

---

## 4. Current safe state (as of session end)

- `EMERGENCY_STOP_ALL`: durably `true` (blocked), independently verified via direct Airtable read, `operation_id=mpt-phase2b-restore-20260819-004343`.
- `EXTERNAL_EXECUTION_ENABLED`: `true` — unchanged all session, a pre-existing service-level env var, not something this session toggled.
- No `ExternalExecutionJob` is at `status='submitted'` (verified) — no lingering active-capacity consumption from this session's runs.
- Two orphaned-but-correctly-classified jobs from this session (`dbbeaad2` → `failed`/`MEDIA_VALIDATION_FAILED`, `6e544a6a` → `outcome_unknown`/`mpt_process_state_unknown`) remain as durable records, matching existing precedent (e.g. `2f86bff8` from 16/08) — not cleaned up, per the harness's own design (cleanup only ever removes the disposable `ActionContract`, never the `ExternalExecutionJob`, since that row is the actual Phase 2B evidence).

## 5. Open items for next session

1. Owner decision on Gap A: bump `srv-d99uq63eo5us73967cj0` to Standard (2GB) permanently, or only for bounded verification windows (manual toggle, like the Emergency Stop flag).
2. Design decision on Gap B before ever attempting a One-Off Job submit for real (see §3.2 options).
3. Once either gap is resolved: re-run the exact sequence in §2.5 with a ≥5s media fixture — this is expected to reach `completed` based on the historical precedent in §2.6.
4. Consider whether the harness (or an operator runbook) should make the clear→run→restore sequence crash-safe (see §2.5's operational note) before it's used again outside a closely-watched session.

---

**Related:** PR #736 (harness), PR #740 (bootstrap fix), `docs/MPT_PHASE_2B_RUNTIME_POLICY.md` (policy design intent), `core/mpt_runtime_policy.py`, `core/moneyprinterturbo_adapter.py`, `core/external_execution_boundary.py`.
