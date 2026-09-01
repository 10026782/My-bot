import os
import logging
from threading import Thread

logger = logging.getLogger(__name__)

_AIRTABLE_TIMEOUT = 3  # seconds per real check


def _check_airtable() -> tuple[bool, str]:
    """Attempt a real Airtable read. Returns (ok, detail)."""
    try:
        base = os.environ.get("AIRTABLE_BASE_ID", "")
        key  = os.environ.get("AIRTABLE_API_KEY", "")
        if not base or not key:
            return False, "missing credentials"
        from tools.airtable_gateway import AirtableLookupError, get_base_metadata

        get_base_metadata(timeout=_AIRTABLE_TIMEOUT)
        return True, "ok"
    except AirtableLookupError as e:
        if e.status_code is not None:
            return False, f"HTTP {e.status_code}"
        cause = e.cause
        return False, f"error: {type(cause or e).__name__}"
    except Exception as e:
        return False, f"error: {type(e).__name__}"


def _check_scheduler(scheduler) -> tuple[bool, str]:
    """Check the background scheduler thread is alive and jobs are registered.

    This codebase runs the `schedule` library's jobs on one background
    `threading.Thread` (scheduler.py::start_scheduler()) — there is no
    APScheduler instance anywhere in the repo. `scheduler` here is that
    Thread; job count comes from the `schedule` library's own module-level
    `schedule.jobs`, not from the thread object.
    """
    try:
        if scheduler is None:
            return False, "not started"
        if hasattr(scheduler, "is_alive") and not scheduler.is_alive():
            return False, "stopped"
        import schedule as _schedule_lib
        jobs = _schedule_lib.jobs
        if not jobs:
            return False, "no jobs registered"
        return True, f"{len(jobs)} jobs"
    except Exception as e:
        return False, f"error: {type(e).__name__}"


def _check_emergency() -> tuple[bool, str]:
    """Return whether EMERGENCY_STOP_ALL is active."""
    try:
        from feature_flags import is_enabled
        if is_enabled("EMERGENCY_STOP_ALL"):
            return False, "EMERGENCY_STOP_ALL is active"
        return True, "clear"
    except Exception as e:
        return True, f"flag check error: {e}"


def _check_emergency_stop_manager() -> tuple[bool, str]:
    """
    Reflects the PATCH 3B Step 5 durable-store-backed EmergencyStopManager
    (core/emergency_stop_bootstrap.py) — separate from, and does not
    replace, _check_emergency()'s legacy is_enabled("EMERGENCY_STOP_ALL")
    check above, which is unchanged and still the one that actually governs
    production behavior (dual-path — see Step 5 boundaries). This check is
    observability only: it must show degraded/invalid accurately even
    though nothing is gated by the manager yet.
    """
    try:
        from feature_flags import get_emergency_stop_status
        result = get_emergency_stop_status()
        if not result.configured:
            return False, "not configured"

        store_status = result.manager_status.store_status if result.manager_status else None
        if store_status == "ok":
            n = len(result.manager_status.flags)
            return True, f"durable, {n} flags"
        if store_status == "unavailable":
            return False, "unavailable — stale-cache/unknown fail-closed"
        if store_status == "invalid":
            return False, "invalid schema/data"
        return False, "unknown (never hydrated)"
    except Exception as e:
        return False, f"error: {type(e).__name__}"


def get_health_status(scheduler=None, memory=None) -> dict:
    at_ok, at_detail       = _check_airtable()
    sched_ok, sched_detail = _check_scheduler(scheduler)
    emerg_ok, emerg_detail = _check_emergency()
    es_mgr_ok, es_mgr_detail = _check_emergency_stop_manager()

    checks = {
        "app":             True,
        "anthropic_key":   bool(os.environ.get("ANTHROPIC_API_KEY", "")),
        "telegram_token":  bool(os.environ.get("TELEGRAM_TOKEN", "")),
        "airtable_live":   at_ok,
        "airtable_detail": at_detail,
        "scheduler":       sched_ok,
        "scheduler_detail": sched_detail,
        "emergency_clear": emerg_ok,
        "emergency_detail": emerg_detail,
        "emergency_stop_manager_ok":     es_mgr_ok,
        "emergency_stop_manager_detail": es_mgr_detail,
        "memory_entries":  len(memory._store) if memory and hasattr(memory, "_store") else 0,
    }

    critical = [
        checks["anthropic_key"],
        checks["telegram_token"],
        checks["airtable_live"],
        checks["emergency_clear"],
        checks["emergency_stop_manager_ok"],
    ]
    status = "ok" if all(critical) else "degraded"

    if not at_ok:
        logger.warning(f"[Health] Airtable degraded: {at_detail}")
    if not sched_ok:
        logger.warning(f"[Health] Scheduler: {sched_detail}")
    if not emerg_ok:
        logger.warning(f"[Health] Emergency stop active: {emerg_detail}")
    if not es_mgr_ok:
        logger.warning(f"[Health] EmergencyStopManager degraded: {es_mgr_detail}")

    return {"status": status, "checks": checks}
