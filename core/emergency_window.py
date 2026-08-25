# core/emergency_window.py — Emergency Window: controlled mobile exception
#
# לא Emergency Stop (שם דומה, תפקיד הפוך — ראה Approval_Policy_Spec.md).
# Stop = נועל את כל המערכת. Window = פותח חריג זמני ומתועד: Owner יכול
# לאשר פעולות High-risk מהטלפון לחלון זמן מוגדר (24/48/72 שעות), כל פעולה
# דרך החלון מתועדת. Critical לעולם לא עובר דרך כאן — אין דרך להרים את
# התקרה מעל High.
#
# כתיבה: רק דרך tools/airtable_gateway.py (כלל ברזל #2 בספק).
# קריאה: דרך ה-read adapter הקנוני.

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone

import feature_flags
from airtable_schema import (
    Tables,
    EmergencyWindowFields as F,
    EmergencyWindowStatus as Status,
    EmergencyWindowMaxRisk,
)
from tools.airtable_gateway import airtable_create, airtable_patch
from core.query_contract import equals
from tools.airtable_read_adapter import AirtableReadError, list_records

logger = logging.getLogger(__name__)

_SOURCE = "emergency_window"
ALLOWED_DURATIONS_HOURS = (24, 48, 72)

# C05-C07 audit Finding #7: activate_window()'s "no stacking" invariant was
# enforced via a bare check-then-write (is_active() then airtable_create())
# with no serialization — two concurrent callers could both observe "no
# active window" and both create one. This lock closes that race the same
# way event_bus.py's threading.Lock() closes its analogous pop/confirm race.
# It only serializes calls within this one process — it is not a
# cross-process/multi-worker guarantee (Airtable itself offers no atomic
# compare-and-create), which matches this codebase's existing precedent.
_activate_lock = threading.Lock()


def _at_key() -> str:
    return os.environ.get("AIRTABLE_API_KEY", "")


def _at_base() -> str:
    return os.environ.get("AIRTABLE_BASE_ID", "")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_active_record() -> dict | None:
    """GET the most recent record with Status=Active. None on any failure."""
    key, base = _at_key(), _at_base()
    if not key or not base:
        logger.warning("[emergency_window] Airtable env vars not set")
        return None

    try:
        records = list_records(
            Tables.EMERGENCY_WINDOW,
            equals(F.STATUS, Status.ACTIVE),
            limit=1,
            sort=[{"field": F.ACTIVATED_AT, "direction": "desc"}],
            paginate=False,
            timeout=10,
        )
        return records[0] if records else None
    except AirtableReadError as e:
        if e.status_code is not None:
            logger.warning(
                f"[emergency_window] fetch failed {e.status_code}: {e.response_text[:200]}"
            )
        else:
            logger.error(f"[emergency_window] fetch error: {e.cause or e}")
        return None
    except Exception as e:
        logger.error(f"[emergency_window] fetch error: {e}")
        return None


def _auto_expire(record: dict) -> bool:
    """If a record's Expires At has passed, flip it to Expired. Returns True if expired."""
    from tma_api import record_fields, record_id

    expires_raw = record_fields(record).get(F.EXPIRES_AT)
    if not expires_raw:
        return False
    try:
        expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires_at > _now():
        return False

    # C05-C07 audit Finding #7: this write's success/failure used to be
    # discarded outright. We still fail closed (an expired window is treated
    # as inactive locally either way — never let a stale mobile exception
    # keep granting High-risk access), but a failed patch now leaves a
    # distinguishable Airtable record (Status=Active past Expires At) that
    # this ERROR log surfaces instead of hiding behind the same message as
    # a genuine success.
    ok = airtable_patch(
        Tables.EMERGENCY_WINDOW,
        record_id(record, required=True),
        {F.STATUS: Status.EXPIRED},
        source=_SOURCE,
    )
    if ok:
        logger.warning(f"[emergency_window] window {record_id(record, required=True)} auto-expired")
    else:
        logger.error(
            f"[emergency_window] window {record_id(record, required=True)} expiry PATCH FAILED — "
            f"Airtable record still shows Status=Active past its Expires At; "
            f"treating it as expired locally regardless, but the record is "
            f"now inconsistent until a later write succeeds"
        )
    return True


def get_active_window() -> dict | None:
    """
    Returns the live Airtable record dict for the currently active window,
    or None if the feature is off / there is none / it just auto-expired.
    """
    if not feature_flags.is_enabled("EMERGENCY_WINDOW"):
        return None

    record = _fetch_active_record()
    if not record:
        return None
    if _auto_expire(record):
        return None
    return record


def is_active() -> bool:
    return get_active_window() is not None


def max_risk_allowed() -> str:
    """The risk ceiling an active window permits. Always High — never Critical."""
    return EmergencyWindowMaxRisk.HIGH


def activate_window(activated_by: str, reason: str, duration_hours: int) -> dict:
    """
    Opens a new Emergency Window. Raises ValueError on bad input or if one is
    already active (must be revoked or left to expire first — no stacking).
    """
    if not feature_flags.is_enabled("EMERGENCY_WINDOW"):
        raise RuntimeError("emergency_window_disabled")
    if duration_hours not in ALLOWED_DURATIONS_HOURS:
        raise ValueError(f"duration_hours must be one of {ALLOWED_DURATIONS_HOURS}")
    if not reason or not reason.strip():
        raise ValueError("reason is required")

    with _activate_lock:
        if is_active():
            raise ValueError("an emergency window is already active")

        now = _now()
        window_id = f"EW-{now:%Y%m%d%H%M%S}"
        rec = airtable_create(
            Tables.EMERGENCY_WINDOW,
            {
                F.WINDOW_ID: window_id,
                F.ACTIVATED_BY: activated_by,
                F.ACTIVATED_AT: now.isoformat(),
                F.EXPIRES_AT: (now + timedelta(hours=duration_hours)).isoformat(),
                F.REASON: reason.strip(),
                F.STATUS: Status.ACTIVE,
                F.MAX_RISK_ALLOWED: EmergencyWindowMaxRisk.HIGH,
                F.ACTIONS_APPROVED: "",
            },
            source=_SOURCE,
        )
        if not rec:
            raise RuntimeError("emergency_window_create_failed")
        logger.warning(f"[emergency_window] ACTIVATED by={activated_by} duration={duration_hours}h reason={reason!r}")
        return rec


def revoke_window(revoked_by: str) -> bool:
    """Manually closes the active window before its natural expiry."""
    record = _fetch_active_record()
    if not record:
        return False

    from tma_api import record_id

    ok = airtable_patch(
        Tables.EMERGENCY_WINDOW,
        record_id(record, required=True),
        {F.STATUS: Status.REVOKED, F.REVOKED_AT: _now().isoformat()},
        source=_SOURCE,
    )
    if ok:
        logger.warning(f"[emergency_window] REVOKED window={record_id(record, required=True)} by={revoked_by}")
    return ok


def record_action(description: str) -> None:
    """Appends one line to Actions Approved on the active window. Best-effort — never raises."""
    record = get_active_window()
    if not record:
        logger.warning(f"[emergency_window] record_action with no active window: {description!r}")
        return

    from tma_api import record_fields, record_id

    existing = record_fields(record).get(F.ACTIONS_APPROVED, "") or ""
    line = f"[{_now().isoformat()}] {description}"
    updated = f"{existing}\n{line}".strip()

    ok = airtable_patch(
        Tables.EMERGENCY_WINDOW,
        record_id(record, required=True),
        {F.ACTIONS_APPROVED: updated},
        source=_SOURCE,
    )
    if not ok:
        logger.warning(f"[emergency_window] failed to log action on window={record_id(record, required=True)}: {description!r}")
