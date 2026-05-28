# scheduler.py
import logging
import os
import threading
import time

import schedule

logger = logging.getLogger(__name__)

_started = False


def _send_digest_message(text: str) -> None:
    import telebot

    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("DIGEST_CHAT_ID", "")
    if not token or not chat_id:
        return
    bot = telebot.TeleBot(token)
    bot.send_message(chat_id, text, parse_mode="Markdown")


def _job_daily_digest():
    """Morning digest with reminders and pending surveys."""
    try:
        report = (
            "🌅 *דוח בוקר*\n\n"
            "• בדוק משימות פתוחות\n"
            "• אשר פגישות ותשלומים\n"
            "• זהה פעולה אחת שמקדמת הכנסה\n"
        )

        from feature_flags import is_enabled

        if is_enabled("SUPABASE"):
            try:
                import httpx

                url = os.environ.get("SUPABASE_URL", "")
                key = os.environ.get("SUPABASE_KEY", "")
                r = httpx.get(
                    f"{url}/rest/v1/pending_surveys",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                    params={"answered_at": "is.null", "limit": "5"},
                    timeout=5,
                )
                surveys = r.json() if r.status_code == 200 else []
                if surveys:
                    report += "\n\n📝 *סקרים ממתינים:*\n"
                    for s in surveys:
                        outcome = "🎉" if s.get("outcome") == "won" else "📋"
                        report += f"  {outcome} {s.get('contact_name','?')} — {s.get('outcome','')}\n"
                    report += "_שלח 'ענה לסקרים' לפתיחה_"
            except Exception:
                pass

        _send_digest_message(report)
    except Exception as e:
        logger.error(f"Daily digest: {e}")


def _job_weekly_debrief():
    """Friday 17:00 — weekly debrief."""
    try:
        _send_digest_message(
            "📊 *סיכום שבועי — מה למדת?*\n\n"
            "כתוב בחופשיות:\n"
            "• עסקאות שסגרת / נפלו\n"
            "• בעיות שנתקלת\n"
            "• מה עבד טוב\n"
            "• תובנות לזכור\n\n"
            "_המערכת תזקק ותשמור._"
        )
    except Exception as e:
        logger.error(f"Weekly debrief: {e}")


def _run_loop():
    while True:
        schedule.run_pending()
        time.sleep(30)


def start_scheduler():
    global _started
    if _started:
        return
    schedule.every().day.at("08:00").do(_job_daily_digest)
    schedule.every().friday.at("17:00").do(_job_weekly_debrief)
    threading.Thread(target=_run_loop, daemon=True).start()
    _started = True
