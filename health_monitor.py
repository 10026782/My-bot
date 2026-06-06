import os
import logging
from threading import Thread

logger = logging.getLogger(__name__)

_AIRTABLE_TIMEOUT = 3  # seconds per real check


def _check_airtable() -> tuple[bool, str]:
    """Attempt a real Airtable read. Returns (ok, detail)."""
    try:
        import httpx
        base = os.environ.get("AIRTABLE_BASE_ID", "")
        key  = os.environ.get("AIRTABLE_API_KEY", "")
        if not base or not key:
            return False, "missing credentials"
        r = httpx.get(
            f"https://api.airtable.com/v0/meta/bases/{base}/tables",
            headers={"Authorization": f"Bearer {key}"},
            timeout=_AIRTABLE_TIMEOUT,
        )
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"error: {type(e).__name__}"


def _check_scheduler(scheduler) -> tuple[bool, str]:
    """Check that the APScheduler instance has running jobs."""
    try:
        if scheduler is None:
            return False, "not started"
        if hasattr(scheduler, "running") and not scheduler.running:
            return False, "stopped"
        jobs = scheduler.get_jobs() if hasattr(scheduler, "get_jobs") else []
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


def get_health_status(scheduler=None, memory=None) -> dict:
    at_ok, at_detail       = _check_airtable()
    sched_ok, sched_detail = _check_scheduler(scheduler)
    emerg_ok, emerg_detail = _check_emergency()

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
        "memory_entries":  len(memory._store) if memory and hasattr(memory, "_store") else 0,
    }

    critical = [
        checks["anthropic_key"],
        checks["telegram_token"],
        checks["airtable_live"],
        checks["emergency_clear"],
    ]
    status = "ok" if all(critical) else "degraded"

    if not at_ok:
        logger.warning(f"[Health] Airtable degraded: {at_detail}")
    if not sched_ok:
        logger.warning(f"[Health] Scheduler: {sched_detail}")
    if not emerg_ok:
        logger.warning(f"[Health] Emergency stop active: {emerg_detail}")

    return {"status": status, "checks": checks}
