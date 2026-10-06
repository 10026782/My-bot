"""FCC rollout gate shared by TMA and chat: flag AND canary allowlist (fail closed)."""

from __future__ import annotations

import os


def enabled_for(identity) -> bool:
    """``FEATURE_FINANCIAL_CONTROL_CENTER`` AND ``FCC_CANARY_USER_IDS`` names the caller's ``user_id``.
    Empty/unset allowlist = nobody, so turning the flag on alone exposes nothing."""
    import feature_flags
    if not feature_flags.is_enabled("FEATURE_FINANCIAL_CONTROL_CENTER"):
        return False
    allowed = {u.strip().casefold() for u in os.environ.get("FCC_CANARY_USER_IDS", "").split(",") if u.strip()}
    uid = str(getattr(identity, "user_id", "") or "").casefold()
    return bool(uid) and uid in allowed
