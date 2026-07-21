# core/emergency_stop_bootstrap.py — PATCH 3B Step 5
#
# The one explicit startup-path function app.py calls to construct the
# concrete AirtableEmergencyStopStore, wrap it in an EmergencyStopManager,
# inject it into feature_flags via configure_emergency_stop_manager(), and
# perform one synchronous hydration attempt so the manager's cache is warm
# (or its failure mode is known) before app.py's module load completes.
#
# No I/O at import time — the adapter/manager/feature_flags imports are all
# deferred inside bootstrap_emergency_stop(); importing this module does
# nothing but define the function and the result dataclass.
#
# Still dual-path after this step: no production caller (is_enabled(),
# set_flag(), tma_api, cost_monitor, scheduler) reads from the manager this
# bootstraps — they all still use the legacy feature_flags path unchanged.
# This step only makes the manager configured and hydrated; nothing
# consults it yet. Cutover is a later, separate, atomic step.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmergencyStopBootstrapResult:
    """What bootstrap_emergency_stop() actually did, for the caller (app.py
    startup logging) and for health_monitor.py to report accurately.

    configured:    True once a manager is (or already was) injected via
                   configure_emergency_stop_manager() — true even when the
                   durable store is unavailable/invalid; only a genuinely
                   unexpected bootstrap bug leaves this False.
    store_status:  "ok" / "unavailable" / "invalid" / None (no store
                   configured at all — should not happen once configured
                   is True, since the adapter is always constructed here).
    flags_loaded:  count of flags actually hydrated into the cache — only
                   nonzero when store_status == "ok".
    """
    configured: bool
    store_status: Optional[str]
    flags_loaded: int
    error: str = ""


def bootstrap_emergency_stop() -> EmergencyStopBootstrapResult:
    """
    Idempotent. Calling this more than once in the same process (e.g. a
    defensive double-call from app.py, mirroring the existing
    "scheduler thread already running -> skip" guard) detects an
    already-configured manager via feature_flags.get_emergency_stop_status()
    and returns its current status without constructing a second store/
    manager or re-triggering a fresh hydration attempt.

    Never raises. Any unexpected failure — including one from
    configure_emergency_stop_manager() itself — is caught and reported via
    the returned result's `error` field instead of propagating, so a bug
    here can never crash app.py's startup (see module docstring / Step 5
    boundary: "don't take down the whole app automatically").
    """
    try:
        import feature_flags

        existing = feature_flags.get_emergency_stop_status()
        if existing.configured:
            logger.info(
                "[EmergencyStop] bootstrap: manager already configured — skipping (idempotent)"
            )
            status = existing.manager_status
            return EmergencyStopBootstrapResult(
                configured=True,
                store_status=status.store_status if status else None,
                flags_loaded=(len(status.flags) if status and status.store_status == "ok" else 0),
                error=(status.error if status else ""),
            )

        from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
        from core.emergency_stop import EmergencyStopManager

        store = AirtableEmergencyStopStore()
        manager = EmergencyStopManager(store=store)

        try:
            feature_flags.configure_emergency_stop_manager(manager)
        except Exception as e:  # noqa: BLE001 — e.g. a genuine race hitting EmergencyStopManagerConflict
            logger.error(f"[EmergencyStop] bootstrap configure() failed: {type(e).__name__}: {e}")
            return EmergencyStopBootstrapResult(
                configured=False, store_status=None, flags_loaded=0, error=str(e)
            )

        status = manager.status()  # forces the first hydration attempt, synchronously

        if status.store_status == "ok":
            logger.info(
                "[EmergencyStop] bootstrap hydration OK — source=durable, %d flags loaded",
                len(status.flags),
            )
        elif status.store_status == "unavailable":
            logger.error(
                "[EmergencyStop] bootstrap hydration UNAVAILABLE (%s) — manager stays configured; "
                "evaluations fail closed per stale-cache/unknown policy",
                status.error,
            )
        elif status.store_status == "invalid":
            logger.error(
                "[EmergencyStop] bootstrap hydration INVALID (%s) — schema/data problem, "
                "durable state not trusted, evaluations fail closed",
                status.error,
            )
        else:
            logger.error(
                "[EmergencyStop] bootstrap hydration returned unexpected store_status=%r",
                status.store_status,
            )

        return EmergencyStopBootstrapResult(
            configured=True,
            store_status=status.store_status,
            flags_loaded=(len(status.flags) if status.store_status == "ok" else 0),
            error=status.error,
        )

    except Exception as e:  # noqa: BLE001 — must never crash app.py's startup
        logger.error(f"[EmergencyStop] bootstrap failed with unexpected {type(e).__name__}: {e}")
        return EmergencyStopBootstrapResult(configured=False, store_status=None, flags_loaded=0, error=str(e))
