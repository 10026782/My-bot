import os
from threading import Thread


def get_health_status(scheduler_thread: Thread | None = None) -> dict:
    checks = {
        "app": True,
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY", "")),
        "telegram_token": bool(os.environ.get("TELEGRAM_TOKEN", "")),
        "worker_secret": bool(os.environ.get("WORKER_SECRET", "")),
        "airtable_api_key": bool(os.environ.get("AIRTABLE_API_KEY", "")),
        "airtable_base_id": bool(os.environ.get("AIRTABLE_BASE_ID", "")),
        "scheduler_started": bool(
            scheduler_thread is not None and scheduler_thread.is_alive()
        ),
    }
    return {
        "status": "ok" if all(checks.values()) else "degraded",
        "checks": checks,
    }
