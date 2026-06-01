# shabbat_guard.py — Shabbat & Holiday Guard
# קובץ: shabbat_guard.py (flat, root)
# אין flag — תמיד פעיל (לא שולח בשבת זה ברירת מחדל הגיונית לכולם)
#
# מה זה עושה:
#   is_shabbat_now()    — האם עכשיו שבת? (שישי אחה"צ → מוצ"ש)
#   is_holiday_now()    — האם עכשיו חג? (לפי רשימה ב-env)
#   should_send_now()   — האם מותר לשלוח הודעות עכשיו?
#   next_allowed_time() — מתי מותר לשלח הבא?
#
# שימוש ב-scheduler.py:
#   לפני כל job שליחה: if not should_send_now(): return
#
# שימוש ב-voice_adapter.py:
#   לפני step_welcome(): if not should_send_now(): TwiML סגור
#
# הגדרות ב-env:
#   SHABBAT_CITY=jerusalem   (ברירת מחדל: tel_aviv)
#   HOLIDAY_DATES=2026-09-22,2026-09-23,2026-10-02  (יום כיפור, ר"ה וכו')
#   SHABBAT_BUFFER_MINUTES=30  (מוסיף 30 דקות לפני/אחרי — ברירת מחדל: 20)

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone, time as dtime
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# זמני כניסת שבת לפי עיר (UTC offset + דקות לפני שקיעה)
# ══════════════════════════════════════════════════

# כניסת שבת = 18 דקות לפני שקיעה. שקיעה ממוצעת לפי עיר + חודש.
# כאן: קירוב פשוט לפי שעה קבועה — מדויק מספיק לrun-guard.
# לחישוב מדויק: ניתן להוסיף chaqira/hebcal API בעתיד.

_SHABBAT_START_HOUR: dict[str, dict] = {
    "jerusalem": {"summer": 18, "winter": 16, "buffer_min": 30},
    "tel_aviv":  {"summer": 19, "winter": 17, "buffer_min": 20},
    "haifa":     {"summer": 19, "winter": 17, "buffer_min": 20},
    "bnei_brak": {"summer": 19, "winter": 16, "buffer_min": 25},
}

_ISRAEL_TZ_OFFSET = 2   # UTC+2 (חורף). UTC+3 בקיץ — מפשט לUTC+2


def _israel_now() -> datetime:
    """שעה נוכחית בישראל (UTC+2 בסיסי)."""
    utc_now = datetime.now(tz=timezone.utc)
    return utc_now + timedelta(hours=_ISRAEL_TZ_OFFSET)


def _is_summer(dt: datetime) -> bool:
    """חודשי קיץ = אפריל-אוקטובר (קירוב לשעון קיץ ישראל)."""
    return 4 <= dt.month <= 10


def _shabbat_start_hour(city: str, dt: datetime) -> int:
    """שעת כניסת שבת לפי עיר + עונה."""
    city_data = _SHABBAT_START_HOUR.get(city, _SHABBAT_START_HOUR["tel_aviv"])
    return city_data["summer"] if _is_summer(dt) else city_data["winter"]


def _shabbat_buffer(city: str) -> int:
    city_data = _SHABBAT_START_HOUR.get(city, _SHABBAT_START_HOUR["tel_aviv"])
    env_buf   = int(os.environ.get("SHABBAT_BUFFER_MINUTES", "0"))
    return city_data["buffer_min"] + env_buf


# ══════════════════════════════════════════════════
# Core Functions
# ══════════════════════════════════════════════════

def is_shabbat_now(city: Optional[str] = None) -> bool:
    """
    האם עכשיו שבת?
    שישי מ-SHABBAT_START עד מוצ"ש (כוכבים = ~50 דקות אחרי שקיעה).
    """
    city = city or os.environ.get("SHABBAT_CITY", "tel_aviv")
    now  = _israel_now()

    start_hour   = _shabbat_start_hour(city, now)
    buffer_min   = _shabbat_buffer(city)
    shabbat_in   = now.replace(hour=start_hour, minute=0, second=0) - timedelta(minutes=buffer_min)
    # מוצ"ש = שבת בשעה ~20:00-21:00 (50 דקות אחרי שקיעה + buffer)
    havdala_hour = start_hour + 2   # קירוב — מוצ"ש בערך 2 שעות אחרי כניסה

    # שישי לפני כניסה → כניסה
    if now.weekday() == 4 and now >= shabbat_in:
        return True

    # כל השבת
    if now.weekday() == 5:
        if now.hour < havdala_hour:
            return True

    return False


def is_holiday_now() -> bool:
    """
    האם עכשיו חג?
    נקרא מ-HOLIDAY_DATES בenv (ISO dates, comma-separated).
    """
    raw = os.environ.get("HOLIDAY_DATES", "")
    if not raw.strip():
        return False

    today_str = _israel_now().strftime("%Y-%m-%d")
    holiday_dates = [d.strip() for d in raw.split(",") if d.strip()]
    return today_str in holiday_dates


def should_send_now(channel: str = "default") -> bool:
    """
    האם מותר לשלוח עכשיו?
    False בשבת וחג.
    True בכל שאר הזמן.

    channel: "voice" / "whatsapp" / "email" / "default"
    הערה: email מותר תמיד (נפתח אחרי שבת). voice לא בשבת בשום אופן.
    """
    if channel == "email":
        return True   # מייל = async, תמיד מותר לשלוח (נפתח אחרי שבת)

    if is_shabbat_now() or is_holiday_now():
        logger.info(f"[ShabbatGuard] BLOCKED — channel={channel}")
        return False

    return True


def next_allowed_time() -> str:
    """
    מתי מותר לשלוח הבא (למוצ"ש / אחרי חג).
    מחזיר string ידידותי להצגה.
    """
    city       = os.environ.get("SHABBAT_CITY", "tel_aviv")
    now        = _israel_now()
    start_hour = _shabbat_start_hour(city, now)
    havdala    = start_hour + 2

    if now.weekday() == 5 and now.hour < havdala:
        return f"מוצ\"ש בשעה {havdala}:00 בערך"
    if now.weekday() == 4:
        return f"מוצ\"ש בשעה {havdala}:00 בערך"

    # חג
    raw = os.environ.get("HOLIDAY_DATES", "")
    if raw:
        return "לאחר צאת החג"

    return "עכשיו מותר"


def shabbat_status_message() -> str:
    """הודעה קצרה לowner על מצב שבת/חג — לdaily digest."""
    if is_holiday_now():
        return "🕯️ *חג* — הודעות אוטומטיות מושהות עד צאת החג."
    if is_shabbat_now():
        next_t = next_allowed_time()
        return f"🕯️ *שבת* — הודעות אוטומטיות מושהות עד {next_t}."
    return ""


# ══════════════════════════════════════════════════
# Scheduler Decorator
# ══════════════════════════════════════════════════

def shabbat_safe(job_fn):
    """
    Decorator לjobs בscheduler.py.
    שימוש:
        @shabbat_safe
        def _job_followup_scan(): ...
    """
    def wrapper(*args, **kwargs):
        channel = kwargs.get("channel", "default")
        if not should_send_now(channel):
            logger.info(f"[ShabbatGuard] Job '{job_fn.__name__}' skipped — Shabbat/Holiday")
            return
        return job_fn(*args, **kwargs)
    wrapper.__name__ = job_fn.__name__
    return wrapper


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # ── _is_summer ────────────────────────────────
    import datetime as dt
    july    = dt.datetime(2026, 7, 1)
    january = dt.datetime(2026, 1, 1)
    chk("July = summer",    _is_summer(july))
    chk("January = winter", not _is_summer(january))

    # ── _shabbat_start_hour ───────────────────────
    chk("Jerusalem summer start = 18", _shabbat_start_hour("jerusalem", july)    == 18)
    chk("Jerusalem winter start = 16", _shabbat_start_hour("jerusalem", january) == 16)
    chk("Tel Aviv summer start = 19",  _shabbat_start_hour("tel_aviv",  july)    == 19)

    # ── is_holiday_now ────────────────────────────
    import os
    today_str = _israel_now().strftime("%Y-%m-%d")
    os.environ["HOLIDAY_DATES"] = today_str
    chk("today is holiday",      is_holiday_now() is True)

    os.environ["HOLIDAY_DATES"] = "2099-01-01"
    chk("far future not holiday", is_holiday_now() is False)

    os.environ.pop("HOLIDAY_DATES", None)
    chk("no env → not holiday",   is_holiday_now() is False)

    # ── should_send_now ───────────────────────────
    chk("email always ok",        should_send_now("email") is True)

    os.environ["HOLIDAY_DATES"] = today_str
    chk("holiday blocks voice",   should_send_now("voice")   is False)
    chk("holiday blocks default", should_send_now("default") is False)
    chk("holiday email ok",       should_send_now("email")   is True)
    os.environ.pop("HOLIDAY_DATES", None)

    # ── next_allowed_time ─────────────────────────
    msg = next_allowed_time()
    chk("next_allowed_time string", isinstance(msg, str) and len(msg) > 0)

    # ── shabbat_status_message ────────────────────
    os.environ["HOLIDAY_DATES"] = today_str
    status = shabbat_status_message()
    chk("holiday status message",   "חג" in status)
    os.environ.pop("HOLIDAY_DATES", None)

    normal = shabbat_status_message()
    chk("normal day = empty string", normal == "" or "שבת" not in normal)

    # ── decorator ─────────────────────────────────
    results = []

    @shabbat_safe
    def mock_job():
        results.append("ran")

    os.environ["HOLIDAY_DATES"] = today_str
    mock_job()
    chk("decorator blocks on holiday", len(results) == 0)
    os.environ.pop("HOLIDAY_DATES", None)

    mock_job()
    chk("decorator runs on normal day", len(results) == 1)

    print(f"\n{'='*40}")
    print(f"ShabbatGuard Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
