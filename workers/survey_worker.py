# workers/survey_worker.py
import os, logging
from datetime import datetime
import telebot

logger = logging.getLogger(__name__)


def _bot():
    return telebot.TeleBot(os.environ.get("TELEGRAM_TOKEN",""))


def send_won_survey(tenant_id: str, chat_id: str, deal_id: str, contact_name: str):
    try:
        msg = (
            f"🎉 *עסקה עם {contact_name} נסגרה!*\n\n"
            f"מה הכי השפיע?\n"
            f"[ מחיר ] [ תזמון ] [ אמון ] [ פולואפ ] [ המוצר ] [ אחר ]\n\n"
            f"מה היה ה-turning point?\n"
            f"_(ענה כשנוח — תזכורת בדוח הבוקר)_"
        )
        _bot().send_message(chat_id, msg, parse_mode="Markdown")
        _save_survey(tenant_id, chat_id, deal_id, contact_name, "won")
        logger.info(f"Won survey → {contact_name}")
    except Exception as e:
        logger.error(f"Won survey: {e}")


def send_lost_survey(tenant_id: str, chat_id: str, deal_id: str, contact_name: str):
    try:
        msg = (
            f"📋 *עסקה עם {contact_name} נסגרה ללא הצלחה.*\n\n"
            f"מה הסיבה?\n"
            f"[ מחיר ] [ תזמון ] [ מתחרה ] [ לא מוכן ] [ תהליך ] [ אחר ]\n\n"
            f"מה אפשר היה לעשות אחרת?\n"
            f"_(ענה כשנוח — תזכורת בדוח הבוקר)_"
        )
        _bot().send_message(chat_id, msg, parse_mode="Markdown")
        _save_survey(tenant_id, chat_id, deal_id, contact_name, "lost")
        logger.info(f"Lost survey → {contact_name}")
    except Exception as e:
        logger.error(f"Lost survey: {e}")


def _save_survey(tenant_id, chat_id, deal_id, contact_name, outcome):
    from feature_flags import is_enabled
    if not is_enabled("SUPABASE"):
        logger.info(f"Survey pending (no supabase): {contact_name} {outcome}")
        return
    try:
        import httpx
        url = os.environ.get("SUPABASE_URL","")
        key = os.environ.get("SUPABASE_KEY","")
        httpx.post(f"{url}/rest/v1/pending_surveys",
            headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"tenant_id":tenant_id,"chat_id":chat_id,"deal_id":deal_id,
                  "contact_name":contact_name,"outcome":outcome,"sent_at":datetime.now().isoformat()},
            timeout=5)
    except Exception as e:
        logger.error(f"Save survey: {e}")
