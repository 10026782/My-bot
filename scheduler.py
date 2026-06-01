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
# N02 — Followup Scan
# ══════════════════════════════════════════════════

def _job_followup_scan():
    try:
        from feature_flags import is_enabled
        if not is_enabled("FOLLOWUP_AUTOMATION"):
            return

        from followup_engine import run_followup_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_followup_scan(owner_chat_id=owner_chat_id)

        if result.candidates:
            logger.info(
                f"[Followup] scanned={result.scanned} "
                f"candidates={len(result.candidates)} queued={result.approved}"
            )
        for err in result.errors:
            logger.error(f"[Followup] {err}")

    except ImportError as e:
        logger.warning(f"[Followup] not available: {e}")
    except Exception as e:
        logger.error(f"[Followup] job error: {e}")


# ══════════════════════════════════════════════════
# N04 — Payment Reminders
# ══════════════════════════════════════════════════

def _job_payment_reminders():
    try:
        from feature_flags import is_enabled
        if not is_enabled("PAYMENT_REMINDERS"):
            return

        from payment_reminder import run_payment_scan
        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[PaymentReminder] TELEGRAM_TOKEN / DIGEST_CHAT_ID חסרים")
            return

        bot    = telebot.TeleBot(token)
        result = run_payment_scan(bot=bot, chat_id=chat_id)

        if result.has_alerts:
            logger.info(
                f"[PaymentReminder] done | "
                f"upcoming={len(result.upcoming)} overdue={len(result.overdue)}"
            )
        for err in result.errors:
            logger.error(f"[PaymentReminder] {err}")

    except ImportError as e:
        logger.warning(f"[PaymentReminder] not available: {e}")
    except Exception as e:
        logger.error(f"[PaymentReminder] job error: {e}")


# ══════════════════════════════════════════════════
# F01 — Lead Recovery
# ══════════════════════════════════════════════════

def _job_lead_recovery():
    try:
        from feature_flags import is_enabled
        if not is_enabled("LEAD_RECOVERY"):
            return

        from core.lead_recovery import run_recovery_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_recovery_scan(owner_chat_id=owner_chat_id)

        if result.candidates:
            logger.info(
                f"[Recovery] scanned={result.scanned} "
                f"candidates={len(result.candidates)} queued={result.queued}"
            )
        for err in result.errors:
            logger.error(f"[Recovery] {err}")

    except ImportError as e:
        logger.warning(f"[Recovery] not available: {e}")
    except Exception as e:
        logger.error(f"[Recovery] job error: {e}")


# ══════════════════════════════════════════════════
# F02 — Learning Cycle
# ══════════════════════════════════════════════════

def _job_learning_cycle():
    try:
        from feature_flags import is_enabled
        if not is_enabled("LEARNING_ENGINE"):
            return

        from core.learning_engine import run_learning_cycle, get_domain_insights
        import telebot

        result = run_learning_cycle(["realestate", "import"])
        logger.info(f"[Learning] cycle done: {list(result.keys())}")

        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if token and chat_id and result:
            bot     = telebot.TeleBot(token)
            summary = get_domain_insights()
            if summary:
                bot.send_message(chat_id, summary, parse_mode="Markdown")
                logger.info("[Learning] ✅ Insights sent to owner")

    except ImportError as e:
        logger.warning(f"[Learning] not available: {e}")
    except Exception as e:
        logger.error(f"[Learning] job error: {e}")


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
# F06 — Email Inbound
# ══════════════════════════════════════════════════

def _job_email_inbound():
    try:
        from feature_flags import is_enabled
        if not is_enabled("EMAIL_INBOUND"):
            return

        from email_inbound import run_email_poll
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_email_poll(owner_chat_id=owner_chat_id)

        if result.routed:
            logger.info(
                f"[Email] scanned={result.scanned} "
                f"routed={result.routed} skipped={result.skipped}"
            )
        for err in result.errors:
            logger.error(f"[Email] {err}")

    except ImportError as e:
        logger.warning(f"[Email] not available: {e}")
    except Exception as e:
        logger.error(f"[Email] job error: {e}")


# ══════════════════════════════════════════════════
# D02 — Abandoned Lead Scan
# ══════════════════════════════════════════════════

def _job_abandoned_scan():
    """D02: סריקת לידים נטושים כל 15 דקות."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("ABANDONED_LEADS"):
            return
        from abandoned_lead_worker import run_abandoned_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_abandoned_scan(owner_chat_id)
        if result.abandoned:
            logger.info(
                f"[D02] abandoned={result.abandoned} "
                f"bounced={result.bounced} pipeline={result.human_pipeline}"
            )
    except ImportError as e:
        logger.warning(f"[D02] not available: {e}")
    except Exception as e:
        logger.error(f"[D02] {e}")


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
    from lead_memory import job_flush_lead_memory
    from shabbat_guard import shabbat_safe
    digest_time           = os.environ.get("DIGEST_TIME",               "07:30")
    collector_time        = os.environ.get("COLLECTOR_TIME",            "23:00")
    cleanup_interval      = int(os.environ.get("CLEANUP_INTERVAL_MIN",  "60"))
    followup_interval     = int(os.environ.get("FOLLOWUP_INTERVAL_MIN", "60"))
    payment_reminder_time = os.environ.get("PAYMENT_REMINDER_TIME",    "09:00")
    recovery_time         = os.environ.get("RECOVERY_TIME",            "10:00")
    learning_day          = os.environ.get("LEARNING_DAY",             "sunday")
    learning_time         = os.environ.get("LEARNING_TIME",            "06:00")
    email_interval        = int(os.environ.get("EMAIL_POLL_INTERVAL_MIN", "15"))
    security_day          = os.environ.get("SECURITY_REMINDER_DAY",    "sunday")
    security_time         = os.environ.get("SECURITY_REMINDER_TIME",   "09:00")
    abandoned_interval    = int(os.environ.get("ABANDONED_INTERVAL_MIN", "15"))

    schedule.every().day.at(digest_time).do(_job_daily_digest)
    schedule.every().day.at(collector_time).do(_job_daily_collector)
    schedule.every(cleanup_interval).minutes.do(_job_cleanup_pending)
    schedule.every().day.at("00:05").do(_job_overdue_payments)
    schedule.every(10).minutes.do(job_flush_lead_memory)                                          # N01
    schedule.every(followup_interval).minutes.do(shabbat_safe(_job_followup_scan))               # N02
    schedule.every().day.at(payment_reminder_time).do(shabbat_safe(_job_payment_reminders))      # N04
    schedule.every().day.at(recovery_time).do(shabbat_safe(_job_lead_recovery))                  # F01
    getattr(schedule.every(), learning_day).at(learning_time).do(_job_learning_cycle)            # F02
    schedule.every(email_interval).minutes.do(_job_email_inbound)                                # F06 (email always ok)
    schedule.every(abandoned_interval).minutes.do(shabbat_safe(_job_abandoned_scan))             # D02
    getattr(schedule.every(), security_day).at(security_time).do(_job_security_reminder)

    logger.info(
        f"📅 Scheduler | digest={digest_time} | collector={collector_time} | "
        f"cleanup=every {cleanup_interval}min | followup=every {followup_interval}min | "
        f"payment={payment_reminder_time} | recovery={recovery_time} | "
        f"learning={learning_day} {learning_time} | "
        f"email=every {email_interval}min | "
        f"abandoned=every {abandoned_interval}min | "
        f"security={security_day} {security_time}"
    )

    t = threading.Thread(target=_run_scheduler, daemon=True, name="scheduler")
    t.start()
    return t
