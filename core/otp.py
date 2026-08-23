# core/otp.py — One-Time Password issuance/verification
#
# שכבת אימות לפעולות Critical (תמיד) ו-High שמתבצעות דרך Emergency Window.
# הקוד נשלח לערוץ נפרד (Telegram DM לבעלים) — לא חוזר בתשובת ה-API בשום שלב.
# State פנימי בזיכרון בלבד (TTL קצר — 5 דקות, מספיק לסיכון restart). אין
# כתיבה ל-Airtable כאן; תיעוד הפעולה שאומתה הוא תפקיד שכבת הבדיקה שמשתמשת
# במודול הזה (_queue_tma_write_approval / emergency_window.record_action).
# See Approval_Policy_Spec.md.

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 5
MAX_ATTEMPTS = 5
_CODE_DIGITS = 6

# { request_id: {"code_hash", "purpose", "identity_ref", "expires", "attempts", "consumed"} }
_store: dict[str, dict] = {}
# LL-13-style lock (same pattern as event_bus.py's PendingActionsStore) — guards
# check-then-increment-then-consume in verify_otp() against concurrent callers
# racing the same request_id (e.g. double-submit / retry-storm on the OTP form).
_lock = threading.Lock()


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _send_code(code: str, purpose: str) -> bool:
    """שולח את הקוד ל-Telegram DM של הבעלים — ערוץ נפרד מהערוץ שמבצע את הפעולה."""
    owner = os.environ.get("OWNER_TELEGRAM_ID") or os.environ.get("ELIYAHU_CHAT_ID", "")
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not owner or not token:
        logger.error("[otp] OWNER_TELEGRAM_ID/ELIYAHU_CHAT_ID/TELEGRAM_TOKEN חסרים — קוד לא נשלח")
        return False
    try:
        import telebot  # type: ignore
        telebot.TeleBot(token).send_message(
            int(owner),
            f"🔐 קוד אימות לפעולה: *{purpose}*\n`{code}`\nתקף ל-{OTP_TTL_MINUTES} דקות.",
            parse_mode="Markdown",
        )
        return True
    except Exception as e:
        logger.error(f"[otp] send failed: {e}")
        return False


def request_otp(purpose: str, identity_ref: str) -> str | None:
    """
    מנפיק קוד חד-פעמי, שולח ל-Telegram DM, שומר state פנימי.
    מחזיר request_id (לעולם לא את הקוד עצמו) — None אם השליחה נכשלה.
    """
    code = "".join(secrets.choice("0123456789") for _ in range(_CODE_DIGITS))
    if not _send_code(code, purpose):
        return None

    request_id = str(uuid.uuid4())[:12]
    with _lock:
        _store[request_id] = {
            "code_hash": _hash_code(code),
            "purpose": purpose,
            "identity_ref": identity_ref,
            "expires": datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
            "attempts": 0,
            "consumed": False,
        }
    logger.warning(f"[otp] issued request_id={request_id} purpose={purpose!r} for={identity_ref}")
    return request_id


def verify_otp(request_id: str, code: str) -> bool:
    """
    מאמת קוד מול בקשה פתוחה. חד-פעמי: נצרך גם בהצלחה וגם כשנגמרים הניסיונות.
    True רק אם הקוד נכון, בתוקף, ולא כבר נוצל/נחסם.

    כל הבדיקה-ואז-עדכון (check-then-increment-then-consume) רצה תחת _lock —
    שתי קריאות מקבילות לאותו request_id (למשל retry כפול על אותה טופס) לא
    יכולות יותר לעקוף יחד את MAX_ATTEMPTS או לצרוך את אותו קוד פעמיים.
    """
    with _lock:
        entry = _store.get(request_id)
        if not entry or entry["consumed"]:
            return False
        if datetime.now(timezone.utc) > entry["expires"]:
            _store.pop(request_id, None)
            return False

        entry["attempts"] += 1
        if entry["attempts"] > MAX_ATTEMPTS:
            entry["consumed"] = True
            logger.warning(f"[otp] request_id={request_id} blocked — too many attempts")
            return False

        if hmac.compare_digest(entry["code_hash"], _hash_code(code.strip())):
            entry["consumed"] = True
            logger.warning(f"[otp] request_id={request_id} verified OK purpose={entry['purpose']!r}")
            return True

        return False


def get_purpose(request_id: str) -> str | None:
    """תכלית ה-OTP שהונפק — לתיעוד/הצגה ב-UI בלי לחשוף state פנימי נוסף."""
    entry = _store.get(request_id)
    return entry["purpose"] if entry else None


def cleanup_expired() -> int:
    """מנקה בקשות OTP שפגו — ניתן לקריאה מה-scheduler. מחזיר כמה נוקו."""
    now = datetime.now(timezone.utc)
    with _lock:
        expired = [rid for rid, e in _store.items() if now > e["expires"]]
        for rid in expired:
            _store.pop(rid, None)
    return len(expired)
