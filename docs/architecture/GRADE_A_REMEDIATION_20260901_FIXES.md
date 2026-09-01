# Grade-A Remediation — PA-01 Visibility, Scheduler Diagnostic, Owner-Mapping Mechanism

**Date:** 01/09/2026. **Type:** three independent static/diagnostic fixes found during a read-only Grade-A runtime-verification pass (agent-verifiable without owner interaction — no flags changed, no Render config changed, no business writes, no canary). **PR:** #1159, branch `claude/pa01-scheduler-owner-mapping-fixes`. **Status at merge time: code-complete, CI-passing — not yet deployed/production-verified per CLAUDE.md's "כלל ברזל".**

> **HISTORICAL_NEXT — superseded:** the "not yet deployed" status above describes this document's state *at merge time only*. All three commits are now merged into `origin/main` and deployed to Render, and commits 1–2 additionally have runtime-verified evidence (PA-01 config corrected + restart-verified; scheduler diagnostic confirmed live `RUNNING_WITH_JOBS`). Current status: `BOSS_CURRENT_STATE.md` TR-24/TR-28/TR-29 — read those, not this paragraph, for current truth.

Full findings, business-impact framing, and cross-references live in `BOSS_CURRENT_STATE.md` TR-21–TR-27 (`docs: reconcile runtime truth after Grade-A env verification pass`, PR #1160) — this note exists only to satisfy this repo's status-sync gate (a material `.py` implementation change requires an accompanying current-state/architecture doc touch in the same PR) without duplicating that reconciliation's content here.

## Commit 1 — `5e7585c`: surface malformed PA-01 enforcement state

`feature_flags.py::get_pa01_enforcement_state()` previously fell back to `"off"` identically for both an unset env var and a malformed one (e.g. the live Render value `"shadow."`, a stray trailing character), with no log signal either way. Now: unset stays silent (expected default), a set-but-invalid value logs a WARNING naming the received value and the valid set. Return value/policy semantics are unchanged for every input — this makes the malformed case visible, it does not block or raise.

## Commit 2 — `4e594aa`: report real scheduler state in owner health

Two compounding diagnostic bugs in `/api/owner/health`: `tma_api.py` hardcoded `scheduler=None` instead of passing the real scheduler thread, and `health_monitor._check_scheduler()` assumed an APScheduler-shaped object (`.running`/`.get_jobs()`) that doesn't exist anywhere in this codebase — the actual scheduler is a `threading.Thread` (`scheduler.py::start_scheduler()`) plus the `schedule` library's module-level `schedule.jobs`. Fixed both: `tma_api.py` now passes `app._scheduler` via a deferred import (matching the circular-import-avoidance pattern already used elsewhere in that file), and `_check_scheduler()` now checks `Thread.is_alive()` + `schedule.jobs`, matching the pattern `boss_doctor.py::_check_scheduler()` already used correctly. Confirmed this diagnostic was never in `/health`'s public critical-status list — cosmetic/observability-only, never an operational outage signal.

## Commit 3 — `8b14600`: allow env-configured owner destination mappings

`config.py::OWNER_USER_ID_MAPPINGS` (WhatsApp/email/voice destination → canonical owner `user_id`, consumed by `core/source_owner_mapping.py`) was a hardcoded, always-empty Python dict — no way to populate it short of a code deploy. Added an env-JSON override (`OWNER_USER_ID_MAPPINGS`) mirroring `identity.py::_load_registry()`'s existing `IDENTITY_MAP` pattern exactly: env JSON parsed and validated per-source, malformed/wrong-shaped input logs an error and falls back to empty for that source only (never crashes, never invents a default owner), unset stays empty exactly as before. Registered in `startup_validator.py` (`warning`-level, matching `IDENTITY_MAP`'s own treatment) and documented in `.env.example` with a placeholder example. **This is the mechanism only** — the mapping itself remains empty until an owner supplies real values via Render env; every non-interactive canonical Lead writer (WhatsApp cutover, Voice, Email, Furniture) continues to fail closed until then.

## Test evidence

`test_pa01_state_malformed_value_visible.py` (3/3), `test_pa01_phantom_approval_enforcement.py` (108/108, unaffected), `test_health_monitor_airtable.py` (10/10, 4 new), `test_health_monitor_emergency_stop.py` (12/12, unaffected), `test_config_owner_mapping_env_override.py` (5/5), `test_phase3_source_owner_mapping.py` (3/3, unaffected), `test_noninteractive_lead_cutovers.py` (4/4, unaffected), `py_compile` clean, `smoke_tests.py` full pass, live call confirmed `resolve_owner_user_id()` still returns `None` with the env var unset.
