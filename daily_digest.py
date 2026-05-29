# daily_digest.py
# דוח בוקר יומי — נשלח ב-08:00 לאליהו בטלגרם.
# scheduler-3.py מנסה לייבא send_daily_digest — חובה שיהיה קיים.
#
# מה שהדוח כולל:
# 1. תשלומים קרובים (7 ימים)
# 2. תשלומים באיחור
# 3. סיכום עסקאות פתוחות
# 4. תזכורת יומית קצרה

import logging
from datetime import date

logger = logging.getLogger(__name__)


def _safe_import_crm():
    """מחזיר פונקציות CRM, או None אם המודול לא קיים."""
    try:
        from crm import crm_upcoming_payments, crm_overdue_payments, crm_list_deals
        return crm_upcoming_payments, crm_overdue_payments, crm_list_deals
    except ImportError as e:
        logger.warning(f"daily_digest: crm not available — {e}")
        return None, None, None


def build_digest() -> str:
    """בונה את תוכן הדוח היומי כטקסט."""
    today = date.today().strftime("%d/%m/%Y")
    lines = [f"☀️ *בוקר טוב — דוח יומי {today}*\n"]

    crm_upcoming, crm_overdue, crm_deals = _safe_import_crm()

    # ── תשלומים קרובים ──────────────────────────
    if crm_upcoming:
        try:
            upcoming = crm_upcoming(days_ahead=7)
            lines.append("📅 *תשלומים קרובים (7 ימים):*")
            lines.append(upcoming)
        except Exception as e:
            logger.error(f"daily_digest upcoming: {e}")
            lines.append("📅 תשלומים קרובים: לא זמין כרגע")
    else:
        lines.append("📅 תשלומים: מודול CRM לא זמין")

    lines.append("")

    # ── תשלומים באיחור ───────────────────────────
    if crm_overdue:
        try:
            overdue = crm_overdue()
            if "🚨" in overdue or "₪" in overdue:
                lines.append("🚨 *תשלומים באיחור:*")
                lines.append(overdue)
                lines.append("")
        except Exception as e:
            logger.error(f"daily_digest overdue: {e}")

    # ── עסקאות פתוחות ────────────────────────────
    if crm_deals:
        try:
            deals = crm_deals(status="open")
            if deals and "אין" not in deals:
                lines.append("🤝 *עסקאות פתוחות:*")
                lines.append(deals)
                lines.append("")
        except Exception as e:
            logger.error(f"daily_digest deals: {e}")

    lines.append("_Boss HQ — יום מוצלח!_ 💪")
    return "\n".join(lines)


def send_daily_digest(bot, chat_id: str) -> None:
    """
    נקרא מ-scheduler.py בכל בוקר.
    bot = telebot.TeleBot instance
    chat_id = DIGEST_CHAT_ID מה-env
    """
    if not chat_id:
        logger.warning("send_daily_digest: chat_id ריק — מדלג")
        return

    try:
        text = build_digest()
        bot.send_message(chat_id, text, parse_mode="Markdown")
        logger.info(f"✅ Daily digest נשלח ל-{chat_id}")
    except Exception as e:
        logger.error(f"send_daily_digest failed: {e}")
