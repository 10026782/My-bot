"""
worker.py — Background Worker פרואקטיבי ("הנודניק")
מופעל על ידי Cron Job ב-Render (08:00 ו-18:00) דרך POST /worker/trigger
"""

import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from threading import Thread
from time import sleep

logger = logging.getLogger(__name__)

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")  # same var as app.py
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DEADLINE_FIELD = "Deadline"
STATUS_FIELD = "Status"
NAME_FIELD = "Name"
TASKS_TABLE = os.environ.get("AIRTABLE_TASKS_TABLE", "Tasks")

NUDGE_AFTER_HOURS = 3  # שעות המתנה לפני "נודניק" חוזר


# ─── Main Proactive Check ─────────────────────────────────────────────────────
def run_proactive_check() -> str:
    """
    סורק את ה-CRM לאיתור דד-ליינים מתקרבים ושולח התראות לטלגרם.
    """
    logger.info("Proactive worker triggered.")
    try:
        urgent_tasks = _scan_airtable_deadlines(days_ahead=3)
        if not urgent_tasks:
            logger.info("No urgent tasks found.")
            return "אין משימות דחופות."

        for task in urgent_tasks:
            message = _build_urgency_message(task)
            _send_telegram(message)

        return f"נשלחו {len(urgent_tasks)} התראות."
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        return f"שגיאה ב-Worker: {e}"


# ─── Airtable Scan ────────────────────────────────────────────────────────────
def _scan_airtable_deadlines(days_ahead: int = 3) -> list:
    """
    שולף משימות שהדד-ליין שלהן בטווח הקרוב ושסטטוסן אינו 'Done'.
    מחזיר רשימה רזה — שם, דד-ליין, מספר ימים שנותרו.
    """
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    today = datetime.now(tz=timezone.utc)
    cutoff = today + timedelta(days=days_ahead)

    params = {
        "filterByFormula": f"AND({{Status}} != 'Done', IS_BEFORE({{{DEADLINE_FIELD}}}, '{cutoff.strftime('%Y-%m-%d')}'))",
        "fields[]": [NAME_FIELD, DEADLINE_FIELD, STATUS_FIELD],
        "maxRecords": 20,  # הגבלה קשיחה — לא סורקים הכל
    }

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TASKS_TABLE}"
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()

    records = r.json().get("records", [])
    urgent = []
    for rec in records:
        fields = rec.get("fields", {})
        deadline_str = fields.get(DEADLINE_FIELD, "")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=timezone.utc)
            days_left = (deadline - today).days
            urgent.append({
                "name": fields.get(NAME_FIELD, "ללא שם"),
                "deadline": deadline_str,
                "days_left": days_left,
                "status": fields.get(STATUS_FIELD, ""),
            })
        except ValueError:
            continue

    return urgent


# ─── Message Builder ──────────────────────────────────────────────────────────
def _build_urgency_message(task: dict) -> str:
    days = task["days_left"]
    name = task["name"]
    deadline = task["deadline"]
    status = task["status"]

    if days < 0:
        urgency = f"⚠️ *עבר הדד-ליין!* לפני {abs(days)} ימים"
    elif days == 0:
        urgency = "🔴 *היום הוא הדד-ליין!*"
    elif days == 1:
        urgency = "🟠 *מחר הוא הדד-ליין*"
    else:
        urgency = f"🟡 *{days} ימים לדד-ליין*"

    return (
        f"{urgency}\n"
        f"📋 משימה: *{name}*\n"
        f"📅 תאריך: {deadline}\n"
        f"סטטוס נוכחי: {status or 'לא הוגדר'}\n\n"
        f"אלייהו — טפל בזה. פספוס יגרור עלויות/נזק. האם לעדכן סטטוס?"
    )


# ─── Telegram Sender ──────────────────────────────────────────────────────────
def _send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing — skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    r = requests.post(url, json=payload, timeout=10)
    if not r.ok:
        logger.error(f"Telegram send failed: {r.text}")
    else:
        logger.info("Telegram notification sent.")


# ─── Nudge Loop (Reminder Thread) ────────────────────────────────────────────
def _nudge_loop():
    """
    מנגנון הנודניק: מחכה NUDGE_AFTER_HOURS שעות ושולח שוב אם יש משימות דחופות.
    רץ ב-Thread נפרד ברקע.
    """
    while True:
        sleep(NUDGE_AFTER_HOURS * 3600)
        logger.info("Nudge loop waking up — re-checking deadlines.")
        run_proactive_check()


def schedule_background_worker():
    """
    מפעיל את לולאת הנודניק ב-Thread דמון ברקע.
    הטריגר הראשי (08:00 / 18:00) מגיע מ-Render Cron Job → POST /worker/trigger.
    """
    thread = Thread(target=_nudge_loop, daemon=True, name="NudgeWorker")
    thread.start()
    logger.info("Background nudge worker started.")
