# scheduler.py — v3.4
# משימות רקע: דוח בוקר + מאסף יומי + ניקוי + תשלומים + תזכורת אבטחה

import os
import logging
import threading
import schedule
import time
from datetime import date

logger = logging.getLogger(__name__)


def _job_cleanup_pending():
    try:
        from event_bus import pending
        pending.cleanup()
    except Exception as e:
        logger.error(f"cleanup_pending error: {e}")


def _job_daily_digest():
    try:
        from daily_digest import send_daily_digest
        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("DIGEST_CHAT_ID לא מוגדר — דוח בוקר דולג")
            return
        bot = telebot.TeleBot(token)
        send_daily_digest(bot=bot, chat_id=chat_id)
        logger.info(f"✅ Daily digest נשלח ל-{chat_id}")
    except ImportError:
        logger.info("daily_digest לא קיים — דולג")
    except Exception as e:
        logger.error(f"daily_digest error: {e}")


def _job_overdue_payments():
    try:
        from crm import crm_overdue_payments
        result = crm_overdue_payments()
        if "🚨" in result:
            logger.info(f"Overdue payments: {result[:100]}")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"overdue_payments error: {e}")


def _job_daily_collector():
    try:
        from daily_collector import send_daily_collector
        import telebot
        token     = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id   = os.environ.get("DIGEST_CHAT_ID", "")
        owner_key = os.environ.get("OWNER_MEMORY_KEY", "boss_hq:eliyahu")
        if not token or not chat_id:
            logger.warning("DIGEST_CHAT_ID לא מוגדר — מאסף דולג")
            return
        bot = telebot.TeleBot(token)
        send_daily_collector(bot=bot, chat_id=chat_id, memory_key=owner_key)
    except ImportError:
        logger.info("daily_collector לא קיים — דולג")
    except Exception as e:
        logger.error(f"daily_collector error: {e}")


# ══════════════════════════════════════════════════
# Security Review Reminder
# ══════════════════════════════════════════════════

def _get_last_review_date() -> date | None:
    """קורא תאריך review אחרון מenv var."""
    raw = os.environ.get("LAST_SECURITY_REVIEW", "")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _days_since_review() -> int:
    last = _get_last_review_date()
    if not last:
        return 999
    return (date.today() - last).days


def _build_security_reminder(days: int) -> str:
    """בונה הודעת תזכורת לפי כמה ימים עברו."""
    if days >= 90:
        urgency = "🔴 *review מלא נדרש*"
        detail  = "עברו 3 חודשים. זמן לסריקה מקיפה של כל שכבות האבטחה."
    elif days >= 28:
        urgency = "🟠 *סריקה מהירה — 4 שבועות*"
        detail  = "grep על dispatcher / crm / identity. 15 דקות מספיקות."
    else:
        return ""

    last_str = _get_last_review_date()
    last_str = last_str.strftime("%d/%m/%Y") if last_str else "לא ידוע"

    return (
        f"🔐 *תזכורת אבטחה — Boss Bot*\n\n"
        f"{urgency}\n"
        f"Review אחרון: {last_str} ({days} ימים)\n\n"
        f"{detail}\n\n"
        f"*צ'קליסט מהיר:*\n"
        f"• dispatch_tool מקבל identity בכל קריאה?\n"
        f"• כלים חדשים עברו דרך registry?\n"
        f"• endpoint חדש — יש auth?\n"
        f"• crm._get מסנן לפי tenant?\n\n"
        f"לאחר הבדיקה: עדכן `LAST_SECURITY_REVIEW={date.today().isoformat()}` ב-Render."
    )


def _job_security_reminder():
    """
    רץ פעם בשבוע (ראשון בבוקר).
    שולח תזכורת רק אם עברו 28+ ימים מהreview האחרון.
    """
    try:
        days = _days_since_review()
        msg  = _build_security_reminder(days)
        if not msg:
            logger.info(f"Security reminder: {days} ימים — עדיין מוקדם")
            return

        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("Security reminder: DIGEST_CHAT_ID לא מוגדר")
            return

        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        logger.info(f"✅ Security reminder נשלח ({days} ימים מהreview)")

    except Exception as e:
        logger.error(f"security_reminder error: {e}")


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def _run_scheduler():
    logger.info("🕐 Scheduler thread started")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"Scheduler run error: {e}")
        time.sleep(30)


def start_scheduler() -> threading.Thread:
    digest_time      = os.environ.get("DIGEST_TIME",             "07:30")
    collector_time   = os.environ.get("COLLECTOR_TIME",          "23:00")
    cleanup_interval = int(os.environ.get("CLEANUP_INTERVAL_MIN", "60"))
    security_day     = os.environ.get("SECURITY_REMINDER_DAY",   "sunday")
    security_time    = os.environ.get("SECURITY_REMINDER_TIME",  "09:00")

    schedule.every().day.at(digest_time).do(_job_daily_digest)
    schedule.every().day.at(collector_time).do(_job_daily_collector)
    schedule.every(cleanup_interval).minutes.do(_job_cleanup_pending)
    schedule.every().day.at("00:05").do(_job_overdue_payments)

    # תזכורת אבטחה — פעם בשבוע, שולחת רק אם עברו 28+ ימים
    getattr(schedule.every(), security_day).at(security_time).do(_job_security_reminder)

    logger.info(
        f"📅 Scheduler | digest={digest_time} | collector={collector_time} | "
        f"cleanup=every {cleanup_interval}min | "
        f"security-check=every {security_day} {security_time}"
    )

    t = threading.Thread(target=_run_scheduler, daemon=True, name="scheduler")
    t.start()
    return t
