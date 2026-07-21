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
# here), an import failure, configure_emergency_stop_manager() itself
# raising (e.g. EmergencyStopManagerConflict from a genuine race), or
# ManagerStatus.store_status coming back as anything other than the three
# documented values (Step 5.1 hardening — see _require_valid_store_status
# below) — is UNEXPECTED, not a documented operational state, and is
# deliberately NOT caught anywhere in this module. It propagates straight
# out of bootstrap_emergency_stop() to the caller, which does not catch it
# either — an unexpected bootstrap bug must be exposed loudly and prevent
# the scheduler from starting, not be silently treated as "just another
# degraded state."

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_VALID_STORE_STATUSES = frozenset({"ok", "unavailable", "invalid"})


def _require_valid_store_status(store_status: object) -> None:
    """
    Step 5.1 hardening: ManagerStatus.store_status is contractually one of
    "ok"/"unavailable"/"invalid" (core.emergency_stop's own StoreStatus
    Literal) — anything else, INCLUDING None, means that contract broke
    somewhere below this function (a real bug, not an operational state we
    know how to handle). Raises RuntimeError rather than logging and
    treating it as just another degraded case — an unknown status must
    stop startup, not be quietly downgraded to "probably fine."
    """
    if store_status not in _VALID_STORE_STATUSES:
        raise RuntimeError(
            f"internal contract violation: store_status={store_status!r} is not one of "
            f"{sorted(_VALID_STORE_STATUSES)} — EmergencyStopManager.status() is contractually "
            "supposed to never produce this; treating it as a startup failure rather than "
            "silently continuing."
        )


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
        if status is None:
            # configured=True with no manager_status is itself a contract
            # violation (feature_flags.get_emergency_stop_status() always
            # calls manager.status() when configured) — not a state we
            # know how to report as "just degraded."
            raise RuntimeError(
                "internal contract violation: get_emergency_stop_status() reported "
                "configured=True but manager_status is None"
            )
        _require_valid_store_status(status.store_status)
        return EmergencyStopBootstrapResult(
            configured=True,
            store_status=status.store_status,
            flags_loaded=(len(status.flags) if status.store_status == "ok" else 0),
            error=status.error,
        )

    from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore
    from core.emergency_stop import EmergencyStopManager

    store = AirtableEmergencyStopStore()
    manager = EmergencyStopManager(store=store)
    feature_flags.configure_emergency_stop_manager(manager)

    status = manager.status()  # forces the first hydration attempt, synchronously
    _require_valid_store_status(status.store_status)

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
    else:  # status.store_status == "invalid" — the only remaining case _require_valid_store_status allows
        logger.error(
            "[EmergencyStop] bootstrap hydration INVALID (%s) — schema/data problem, "
            "durable state not trusted, evaluations fail closed",
            status.error,
        )

    return EmergencyStopBootstrapResult(
        configured=True,
        store_status=status.store_status,
        flags_loaded=(len(status.flags) if status.store_status == "ok" else 0),
        error=status.error,
    )
