# scheduler.py — v3.3
# משימות רקע: דוח בוקר + מאסף יומי + ניקוי + תשלומים

import os
import logging
import threading
import schedule
import time

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
    """
    המאסף היומי — רץ ב-23:00.
    עובר על שיחות היום, מזהה נתונים שאולי לא נשמרו,
    ושולח לאליהו סיכום בטלגרם.
    """
    try:
        from daily_collector import send_daily_collector
        import telebot

        token      = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id    = os.environ.get("DIGEST_CHAT_ID", "")
        owner_key  = os.environ.get("OWNER_MEMORY_KEY", "boss_hq:eliyahu")

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
    digest_time      = os.environ.get("DIGEST_TIME",           "07:30")
    collector_time   = os.environ.get("COLLECTOR_TIME",        "23:00")
    cleanup_interval = int(os.environ.get("CLEANUP_INTERVAL_MIN", "60"))

    schedule.every().day.at(digest_time).do(_job_daily_digest)
    schedule.every().day.at(collector_time).do(_job_daily_collector)
    schedule.every(cleanup_interval).minutes.do(_job_cleanup_pending)
    schedule.every().day.at("00:05").do(_job_overdue_payments)

    logger.info(
        f"📅 Scheduler | digest={digest_time} | "
        f"collector={collector_time} | cleanup=every {cleanup_interval}min"
    )

    t = threading.Thread(target=_run_scheduler, daemon=True, name="scheduler")
    t.start()
    return t
