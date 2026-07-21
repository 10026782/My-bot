# core/emergency_stop_bootstrap.py — PATCH 3B Step 5
#
# The one explicit startup-path function app.run_startup_sequence() calls
# to construct the concrete AirtableEmergencyStopStore, wrap it in an
# EmergencyStopManager, inject it into feature_flags via
# configure_emergency_stop_manager(), and perform one synchronous
# hydration attempt so the manager's cache is warm (or its failure mode is
# known) before the caller starts the scheduler.
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
#
# ══════════════════════════════════════════════════════════════════
# Exception policy — documented outcome vs. unexpected failure
# ══════════════════════════════════════════════════════════════════
# Two DOCUMENTED, EXPECTED outcomes are reported as data, never as a raised
# exception, because the adapter (Step 2/2.5) and the manager (Step 1) are
# both already internally defensive about them:
#   - Airtable unavailable (network/HTTP/timeout)  -> ManagerStatus.store_status="unavailable"
#   - durable schema/data invalid                  -> ManagerStatus.store_status="invalid"
# Both leave the manager configured and fail-closed on affected flags —
# this function returns a result describing that, and the caller
# (app.run_startup_sequence()) proceeds to start the scheduler regardless.
#
# Everything else — a bug in construction (e.g. AirtableEmergencyStopStore
# or EmergencyStopManager raising ValueError on malformed
# known_flag_names, which should never happen with the defaults used
# here), an import failure, or configure_emergency_stop_manager() itself
# raising (e.g. EmergencyStopManagerConflict from a genuine race) — is
# UNEXPECTED, not a documented operational state, and is deliberately NOT
# caught anywhere in this module. It propagates straight out of
# bootstrap_emergency_stop() to the caller, which does not catch it
# either — an unexpected bootstrap bug must be exposed loudly and prevent
# the scheduler from starting, not be silently treated as "just another
# degraded state."

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
                   configure_emergency_stop_manager(). Always True when
                   this function returns normally — an unexpected failure
                   during construction/configuration propagates instead of
                   producing a configured=False result (see module
                   docstring's exception policy).
    store_status:  "ok" / "unavailable" / "invalid" — the two failure
                   values are documented, expected operational states, not
                   exceptions.
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
    defensive double-call, mirroring the existing "scheduler thread already
    running -> skip" guard in app.py) detects an already-configured manager
    via feature_flags.get_emergency_stop_status() and returns its current
    status without constructing a second store/manager or re-triggering a
    fresh hydration attempt.

    Raises on an unexpected construction/configuration failure — see the
    module docstring's exception policy. Never raises for Airtable being
    unavailable or the durable schema/data being invalid; both come back as
    a normal EmergencyStopBootstrapResult.
    """
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
    feature_flags.configure_emergency_stop_manager(manager)

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
        # Not a documented outcome (see exception policy above) — surfaced
        # as data here rather than raised because it comes from
        # ManagerStatus, itself produced by the manager's own internally-
        # defensive status() call, which by contract never raises. If this
        # branch is ever hit it means that contract broke somewhere below
        # us; logging loudly is the right response, not crashing the whole
        # startup over an observability-shaped surprise.
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
