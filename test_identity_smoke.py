"""
Smoke test — Identity normalization (ARCHITECTURE_DRIFT_MAP.md #6)
Piggyback trigger: לפני חיבור Meta WhatsApp Cloud API.

4 מקרים:
  1. Telegram + owner chat_id  → Role.OWNER
  2. WhatsApp + owner phone    → Role.OWNER
  3. WhatsApp + unknown number → Role.LEAD
  4. Telegram + unknown id     → Role.READONLY

הטסט משתמש בערכים פיקטיביים כדי להיות deterministic בכל סביבה.
"""

import os
import sys
from unittest.mock import patch

_FAKE_TG_OWNER  = "100000001"
_FAKE_WA_PHONE  = "972501234567"
_UNKNOWN_WA     = "972509999999"
_UNKNOWN_TG     = "999888777"


def _load_with_env(**env_overrides):
    """Calls identity._load_registry() with custom env vars, returns registry dict."""
    with patch.dict(os.environ, env_overrides, clear=False):
        import identity as _id_mod
        return _id_mod._load_registry()


def run():
    import identity as _id_mod
    from identity import resolve_identity, Role

    # Build a test registry using fake env (no IDENTITY_MAP, use ELIYAHU_CHAT_ID + OWNER_PHONES)
    test_env = {
        "IDENTITY_MAP":    "",          # force Option 3 (default fallback)
        "ELIYAHU_CHAT_ID": _FAKE_TG_OWNER,
        "OWNER_PHONES":    _FAKE_WA_PHONE,
    }
    test_registry = _load_with_env(**test_env)

    # Temporarily replace the live registry so resolve_identity uses test data
    original = _id_mod._REGISTRY
    _id_mod._REGISTRY = test_registry

    cases = [
        ("1. Telegram owner",    "telegram",  _FAKE_TG_OWNER, Role.OWNER),
        ("2. WhatsApp owner",    "whatsapp",  _FAKE_WA_PHONE, Role.OWNER),
        ("3. Unknown WhatsApp",  "whatsapp",  _UNKNOWN_WA,    Role.LEAD),
        ("4. Unknown Telegram",  "telegram",  _UNKNOWN_TG,    Role.READONLY),
    ]

    results = []
    try:
        for name, channel, ext_id, expected in cases:
            idn = resolve_identity(channel, ext_id)
            passed = idn.role == expected
            results.append((name, expected, idn.role, passed))
    finally:
        _id_mod._REGISTRY = original

    print("\n=== Identity Smoke Test (ARCHITECTURE_DRIFT_MAP.md #6) ===")
    blockers = []
    for name, expected, actual, passed in results:
        status = "PASS" if passed else "FAIL ← BLOCKER"
        print(f"  [{status}] {name}: expected={expected!r}, got={actual!r}")
        if not passed:
            blockers.append(name)

    if blockers:
        print(f"\n❌ BLOCKER FOUND in: {', '.join(blockers)}")
        print("   אליהו לא יזוהה נכון — תיקון נדרש לפני חיבור Meta WhatsApp.")
    else:
        print("\n✅ כל 4 המקרים עברו — Identity מוכן לחיבור WhatsApp.")
    return len(blockers) == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
