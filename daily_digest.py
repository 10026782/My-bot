# daily_digest.py
# דוח בוקר יומי — נשלח ב-08:00 לאליהו בטלגרם.
# scheduler.py מנסה לייבא send_daily_digest — חובה שיהיה קיים.
#
# מה שהדוח כולל:
# 1. תשלומים קרובים (7 ימים)
# 2. תשלומים באיחור
# 3. סיכום עסקאות פתוחות
# 4. לוח זמנים פרויקט (ProjectTimeline)
# 5. תזכורת יומית קצרה

import logging
from datetime import date

logger = logging.getLogger(__name__)


def _get_leads_summary() -> str:
    """שולף את כל הלידים מ-Airtable ומחזיר תצוגה עם score_display."""
    try:
        from airtable_tools import airtable_get  # type: ignore
        from airtable_schema import Tables       # type: ignore
        from score_display import format_leads_summary  # type: ignore

        records = airtable_get(Tables.LEADS, "")
        if not records or not isinstance(records, list):
            return ""

        leads = [
            {
                "name":      r.get("fields", {}).get("Name", "ליד"),
                "score":     int(r.get("fields", {}).get("score", 0) or 0),
                "tier":      r.get("fields", {}).get("tier", "COLD"),
                "next_step": r.get("fields", {}).get("next_step", ""),
            }
            for r in records if isinstance(r, dict)
        ]
        return format_leads_summary(leads)

    except ImportError:
        logger.debug("daily_digest: score_display/airtable not available — skip leads")
        return ""
    except Exception as e:
        logger.warning(f"daily_digest _get_leads_summary: {e}")
        return ""


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

    # שבת/חג — הודעה בראש הדוח
    try:
        from shabbat_guard import shabbat_status_message  # type: ignore
        shabbat_msg = shabbat_status_message()
        if shabbat_msg:
            lines.append(shabbat_msg)
            lines.append("")
    except ImportError:
        pass

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
            deals = crm_deals(status="Active")   # DealStatus.ACTIVE — סטטוס תקין
            if deals and "אין" not in deals:
                lines.append("🤝 *עסקאות פתוחות:*")
                lines.append(deals)
                lines.append("")
        except Exception as e:
            logger.error(f"daily_digest deals: {e}")

    # ── N05: לידים — score_display v2 ───────────────
    try:
        leads_block = _get_leads_summary()
        if leads_block:
            lines.append(leads_block)
            lines.append("")
    except Exception as e:
        logger.warning(f"daily_digest leads: {e}")

    # ── D04: Churn Risk ───────────────────────────
    try:
        from feature_flags import is_enabled  # type: ignore
        if is_enabled("AUDIENCE_INTELLIGENCE"):
            from audience_intelligence import detect_churn_risk, load_all_leads  # type: ignore
            churn = detect_churn_risk(load_all_leads())
            if churn:
                lines.append("🚨 *Churn Risk — פנה מהר:*")
                for l in churn[:3]:
                    lines.append(f"  • *{l.name}* score={l.score} | {l.days_silent}d שתיקה")
                lines.append("")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"daily_digest churn: {e}")

    # ── ProjectTimeline ───────────────────────────
    try:
        from project_timeline import get_timeline_summary, format_timeline_digest_block
        timeline_block = format_timeline_digest_block(get_timeline_summary())
        if timeline_block:
            lines.append(timeline_block)
            lines.append("")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"daily_digest timeline: {e}")

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
