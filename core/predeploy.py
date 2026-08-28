# core/predeploy.py — PATCH 3B Step 4
#
# Explicit predeploy wrapper: runs the existing database migrations first,
# and ONLY if they succeed, runs the Emergency Stop preflight
# (core/emergency_stop_preflight.py). A migrations failure prevents the
# preflight from running at all.
#
# WIRED as Render's live Pre-Deploy Command — confirmed 2026-08-28 via a
# read-only Render API query (GET /v1/services/srv-d80ehsf7f7vs73cq5rn0:
# serviceDetails.envSpecificDetails.preDeployCommand == "python -m
# core.predeploy"). This module's prior docstring claimed the opposite and
# referenced a render.yaml that has never existed in this repo — that was
# stale; Render's Pre-Deploy Command is dashboard-only config, not
# repo-tracked. See docs/operations/ORACLE_MIGRATION_M0.md for the full
# verification and the other dashboard-vs-docs discrepancies found the same
# way (autoDeploy, healthCheckPath).
#
# `python -m core.database_migrations` is untouched and keeps working
# completely independently, exactly as before — this module imports and
# calls the SAME run_migrations() function that CLI already uses, it does
# not replace, subclass, or wrap that CLI in any way.
#
# CLI usage:
#   python -m core.predeploy
#
# Exit codes:
#   0  both stages succeeded.
#   1  database migrations failed (or raised) — the preflight is never
#      invoked in this case.
#   otherwise, the emergency-stop preflight's own exit code when migrations
#   succeeded but the preflight did not (2=unavailable, 3=invalid,
#   1=internal_error — see core.emergency_stop_preflight) — preserved
#   rather than collapsed to a single generic code, so Render logs keep the
#   distinction.

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    from core.database_migrations import run_migrations
    from core.emergency_stop_preflight import EXIT_OK, run_preflight

    try:
        migrations_ok = run_migrations()
    except Exception as e:  # noqa: BLE001 — a bug/unavailable DB here must block the preflight, not skip past it
        logger.error(f"[predeploy] database migrations: FAILED — unexpected {type(e).__name__}: {e}")
        return 1

    if not migrations_ok:
        logger.error("[predeploy] database migrations: FAILED")
        return 1
    logger.info("[predeploy] database migrations: OK")

    try:
        preflight_exit_code = run_preflight()
    except Exception as e:  # noqa: BLE001 — defense-in-depth; run_preflight() already guards itself internally
        logger.error(f"[predeploy] emergency stop preflight: FAILED — unexpected {type(e).__name__}: {e}")
        return 1

    if preflight_exit_code != EXIT_OK:
        logger.error(f"[predeploy] emergency stop preflight: FAILED (exit {preflight_exit_code})")
        return preflight_exit_code
    logger.info("[predeploy] emergency stop preflight: OK")

    logger.info("[predeploy] all predeploy checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
