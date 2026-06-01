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


def _get_hot_leads_today() -> str:
    """שולף לידים HOT מ-Airtable שטרם טופלו היום. מחזיר string מפורמט, או "" אם אין."""
    try:
        from airtable_tools import airtable_get  # type: ignore
        from airtable_schema import Tables       # type: ignore

        records = airtable_get(Tables.LEADS, "{Tier}='HOT'")
        if not records or not isinstance(records, list):
            return ""

        lines = []
        for r in records[:5]:
            f    = r.get("fields", {}) if isinstance(r, dict) else {}
            name = f.get("Name") or f.get("contact_name") or "ליד"
            last = f.get("last_message") or f.get("Last Message") or ""
            if last:
                last = f' | "{last[:40]}"'
            lines.append(f"• *{name}* | HOT{last}")

        if not lines:
            return ""

        suffix = f"\n  _(ועוד {len(records)-5} נוספים)_" if len(records) > 5 else ""
        return "\n".join(lines) + suffix

    except ImportError:
        logger.debug("daily_digest: airtable_tools not available — skip hot leads")
        return ""
    except Exception as e:
        logger.warning(f"daily_digest _get_hot_leads_today: {e}")
        return ""


def _get_leads_scoring_summary() -> str:
    """סיכום HOT/WARM/COLD counts מ-Airtable Leads. מחזיר string קצר, או "" אם אין."""
    try:
        from airtable_tools import airtable_get  # type: ignore
        from airtable_schema import Tables       # type: ignore

        records = airtable_get(Tables.LEADS, "")
        if not records or not isinstance(records, list):
            return ""

        hot = warm = cold = 0
        for r in records:
            tier = ""
            if isinstance(r, dict):
                tier = r.get("fields", {}).get("Tier") or r.get("fields", {}).get("tier") or ""
            tier = tier.upper()
            if tier == "HOT":    hot  += 1
            elif tier == "WARM": warm += 1
            elif tier == "COLD": cold += 1

        total = hot + warm + cold
        if not total:
            return ""

        parts = []
        if hot:  parts.append(f"🔥 {hot} HOT")
        if warm: parts.append(f"🟡 {warm} WARM")
        if cold: parts.append(f"🧊 {cold} COLD")
        parts.append(f"סה\"כ {total}")
        return " | ".join(parts)

    except ImportError:
        logger.debug("daily_digest: airtable_tools not available — skip scoring")
        return ""
    except Exception as e:
        logger.warning(f"daily_digest _get_leads_scoring_summary: {e}")
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

    # ── N05: לידים חמים היום ─────────────────────
    try:
        hot_leads = _get_hot_leads_today()
        if hot_leads:
            lines.append("🔥 *לידים חמים — מחייבים מעקב היום:*")
            lines.append(hot_leads)
            lines.append("")
    except Exception as e:
        logger.warning(f"daily_digest hot_leads: {e}")

    # ── N05: סיכום scoring ───────────────────────
    try:
        scoring = _get_leads_scoring_summary()
        if scoring:
            lines.append(f"📊 *מצב לידים:* {scoring}")
            lines.append("")
    except Exception as e:
        logger.warning(f"daily_digest scoring: {e}")

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
