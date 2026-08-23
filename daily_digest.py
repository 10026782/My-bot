# דוח בוקר יומי — נשלח ב-08:00 לאליהו בטלגרם.
# scheduler.py מנסה לייבא send_daily_digest — חובה שיהיה קיים.

import logging
import os
from datetime import date, timedelta

from airtable_schema import LeadFields, Tables, PaymentFields, PaymentStatus
from tools.airtable_read_adapter import list_records

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════

def _fetch(table_real: str, formula: str = "", max_rec: int = 20) -> list:
    """Return Airtable records or raise RuntimeError, preserving the old contract."""
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        raise RuntimeError("Airtable credentials missing (AIRTABLE_BASE_ID / AIRTABLE_API_KEY)")
    try:
        return list_records(table_real, formula, max_records=max_rec)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def _fmt(iso: str) -> str:
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso[:10]).strftime("%d/%m")
    except Exception:
        return iso[:5] if iso else "—"


# ══════════════════════════════════════════════════
# Sections
# ══════════════════════════════════════════════════

def _tier_label(score: int) -> str:
    """
    Score → tier label, באותם ספים כמו lead_capture._score_inbound_message.
    אין שדה tier ב-Airtable (ROADMAP Known Issues: LeadFields.TIER לא קיים
    בסכמה) — ה-tier מחושב כאן בזיכרון מתוך Score בלבד, לא נקרא משדה.
    """
    if score >= 70:
        return "🔥 רותח"
    if score >= 50:
        return "🌶️ לוהט"
    if score >= 25:
        return "🌤️ חם"
    return "❄️ קר"


def _hot_leads(errors: list) -> str:
    """🔥 לידים חמים — Score>=50 (סף HOT/ULTRA_HOT) או status legacy='hot'"""
    try:
        records = _fetch(
            "Leads",
            "OR({Score}>=50, {status}='hot', {status}='Hot', {status}='HOT')",
            max_rec=8,
        )
        if not records:
            return "🔥 *לידים חמים:* אין כרגע"
        lines = ["🔥 *לידים חמים:*"]
        for r in records:
            f         = r.get("fields", {})
            score     = int(f.get(LeadFields.SCORE, 0) or 0)
            tier      = _tier_label(score)
            next_step = f.get("next_step", "—") or "—"
            lines.append(
                f"• {f.get('Name','?')} | {f.get('phone','—')} | ⭐{score} {tier} | {next_step}"
            )
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"לידים חמים: {e}")
        return "🔥 *לידים חמים:* שגיאה"


def _followups_today(errors: list) -> str:
    """📞 מעקבים להיום — contacts עם תאריך פולו אפ = היום"""
    try:
        records = _fetch(
            "אנשי קשר (Contacts)",
            "IS_SAME({תאריך פולו אפ}, TODAY(), 'day')",
            max_rec=15,
        )
        if not records:
            return "📞 *מעקבים להיום:* אין"
        lines = ["📞 *מעקבים להיום:*"]
        for r in records:
            f      = r.get("fields", {})
            status = f.get("סטטוס", "—")
            due    = _fmt(f.get("תאריך פולו אפ", ""))
            lines.append(
                f"• {f.get('שם','?')} | {f.get('טלפון','—')} | {status} | {due}"
            )
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"מעקבים: {e}")
        return "📞 *מעקבים להיום:* שגיאה"


def _roadmap_tasks_today(errors: list) -> str:
    """📅 משימות היום — Roadmap_Tasks של אליהו, Due_Date <= היום, לא Done, ממוין P0→P3"""
    try:
        today_str = date.today().isoformat()
        records   = _fetch(
            "Roadmap_Tasks",
            f"AND("
            f"{{Owner}}='אליהו', "
            f"{{Status}}!='Done', "
            f"IS_BEFORE({{Due_Date}}, DATEADD('{today_str}', 1, 'days'))"
            f")",
            max_rec=30,
        )

        if not records:
            return "📅 *משימות היום:* אין"

        # Sort by priority order
        _PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 4}
        records.sort(key=lambda r: _PRIO_ORDER.get(
            r.get("fields", {}).get("Priority", ""), 4
        ))

        buckets: dict[str, list[str]] = {"P0": [], "P1": [], "P2": [], "P3": []}
        for r in records:
            f       = r.get("fields", {})
            task    = f.get("Task", "?")
            prio    = f.get("Priority", "P3")
            status  = f.get("Status", "")
            blocker = " 🚧" if f.get("Blocker") else ""
            due     = _fmt(f.get("Due_Date", ""))
            status_icon = "🔄" if status == "In Progress" else "☐"
            line    = f"{status_icon} {task} | {due}{blocker}"
            buckets.setdefault(prio, []).append(line)

        lines = ["📅 *משימות היום*"]
        if buckets.get("P0"):
            lines.append("🔥 *P0 — חובה:*")
            lines.extend(f"  • {t}" for t in buckets["P0"])
        if buckets.get("P1"):
            lines.append("🟡 *P1 — חשוב:*")
            lines.extend(f"  • {t}" for t in buckets["P1"])
        if buckets.get("P2"):
            lines.append("🟢 *P2 — אם נשאר זמן:*")
            lines.extend(f"  • {t}" for t in buckets["P2"])
        if buckets.get("P3"):
            lines.append("⚪ *P3:*")
            lines.extend(f"  • {t}" for t in buckets["P3"])

        return "\n".join(lines)
    except Exception as e:
        errors.append(f"Roadmap Tasks: {e}")
        return "📅 *משימות היום:* שגיאה"


def _open_deals(errors: list) -> str:
    """🤝 עסקאות פתוחות"""
    try:
        records = _fetch(
            "עסקאות (Deals)",
            "NOT(OR({שלב}='סגור-ניצחון', {שלב}='סגור-הפסד'))",
            max_rec=10,
        )
        if not records:
            return "🤝 *עסקאות פתוחות:* אין"
        lines = ["🤝 *עסקאות פתוחות:*"]
        for r in records:
            f      = r.get("fields", {})
            amount = f.get("סכום", 0)
            amt    = f"₪{amount:,.0f}" if isinstance(amount, (int, float)) else "—"
            lines.append(
                f"• {f.get('שם העסקה','?')} | {f.get('שלב','—')} | {amt}"
            )
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"עסקאות: {e}")
        return "🤝 *עסקאות פתוחות:* שגיאה"


def _upcoming_payments(errors: list) -> str:
    """💰 תשלומים קרובים — 7 ימים, לא שולמו"""
    try:
        today    = date.today()
        deadline = today + timedelta(days=7)
        records  = _fetch(
            Tables.PAYMENTS,
            f"AND("
            f"{{{PaymentFields.STATUS}}} != '{PaymentStatus.RECEIVED}', "
            f"IS_BEFORE({{{PaymentFields.DATE}}}, '{deadline.isoformat()}'), "
            f"IS_AFTER({{{PaymentFields.DATE}}}, '{today.isoformat()}')"
            f")",
            max_rec=10,
        )
        if not records:
            return "💰 *תשלומים קרובים:* אין"
        lines = ["💰 *תשלומים קרובים:*"]
        total = 0
        for r in records:
            f      = r.get("fields", {})
            amount = f.get(PaymentFields.AMOUNT, 0)
            total += amount if isinstance(amount, (int, float)) else 0
            amt    = f"₪{amount:,.0f}" if isinstance(amount, (int, float)) else "—"
            lines.append(
                f"• {f.get(PaymentFields.REF,'?')} | {amt} | {_fmt(f.get(PaymentFields.DATE,''))} | {f.get(PaymentFields.STATUS,'—')}"
            )
        lines.append(f"💰 *סה\"כ: ₪{total:,.0f}*")
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"תשלומים: {e}")
        return "💰 *תשלומים קרובים:* שגיאה"


def _lead_temperature_counts(records: list) -> tuple[int, int, int]:
    """מחזיר ספירות HOT/WARM/COLD לפי טווחי ציון הלידים הקנוניים."""
    hot = warm = cold = 0
    for record in records:
        raw_score = record.get("fields", {}).get(LeadFields.SCORE, 0)
        try:
            score = int(raw_score or 0)
        except (TypeError, ValueError):
            score = 0
        if score >= 50:  # HOT ו-ULTRA_HOT נכללים באותה קטגוריית סיכום.
            hot += 1
        elif score >= 25:
            warm += 1
        else:
            cold += 1
    return hot, warm, cold


def _leads_scoring_summary(errors: list) -> str:
    """מסכם את כל הלידים לפי קבוצת טמפרטורה HOT/WARM/COLD."""
    try:
        hot, warm, cold = _lead_temperature_counts(_fetch("Leads", "", max_rec=0))
        total = hot + warm + cold
        return (
            f"📊 *לידים:* 🔥 {hot} HOT | 🌤️ {warm} WARM | "
            f"❄️ {cold} COLD | סה\"כ {total}"
        )
    except Exception as e:
        errors.append(f"סיכום לידים: {e}")
        return "📊 *לידים:* שגיאה"


def _yesterday_changes(errors: list) -> str:
    """🧠 מה השתנה אתמול — לידים חדשים, עסקאות חדשות, משימות שהושלמו"""
    try:
        yesterday = date.today() - timedelta(days=1)
        yday_str  = yesterday.isoformat()
        today_str = date.today().isoformat()

        lead_recs = _fetch(
            "Leads",
            f"AND("
            f"IS_AFTER({{created_at}}, '{yday_str}T00:00:00.000Z'), "
            f"IS_BEFORE({{created_at}}, '{today_str}T00:00:00.000Z')"
            f")",
            max_rec=10,
        )
        deal_recs = _fetch(
            "עסקאות (Deals)",
            "IS_SAME(CREATED_TIME(), DATEADD(TODAY(), -1, 'days'), 'day')",
            max_rec=5,
        )
        done_recs = _fetch(
            "משימות (Tasks)",
            "{סטטוס} = 'בוצע'",
            max_rec=5,
        )

        lines = ["🧠 *מה השתנה אתמול:*"]
        any_data = False

        if lead_recs:
            lines.append(f"• *לידים חדשים ({len(lead_recs)}):*")
            for r in lead_recs:
                f   = r.get("fields", {})
                src = f.get("source") or f.get("channel") or "—"
                lines.append(f"  – {f.get('Name','?')} | {f.get('phone','—')} | {src}")
            any_data = True

        if deal_recs:
            lines.append(f"• *עסקאות חדשות ({len(deal_recs)}):*")
            for r in deal_recs:
                f = r.get("fields", {})
                lines.append(f"  – {f.get('שם העסקה','?')} | {f.get('שלב','—')}")
            any_data = True

        if done_recs:
            lines.append(f"• *משימות שהושלמו ({len(done_recs)}):*")
            for r in done_recs:
                f = r.get("fields", {})
                lines.append(f"  – {f.get('כותרת המשימה','?')}")
            any_data = True

        if not any_data:
            lines.append("• אין שינויים מדווחים")

        return "\n".join(lines)
    except Exception as e:
        errors.append(f"שינויים אתמול: {e}")
        return "🧠 *מה השתנה אתמול:* שגיאה"


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════

def build_digest() -> str:
    today_str = date.today().strftime("%d/%m/%Y")
    errors: list = []

    shabbat = ""
    try:
        from shabbat_guard import shabbat_status_message  # type: ignore
        shabbat = shabbat_status_message() or ""
    except ImportError:
        pass

    sections = [
        _leads_scoring_summary(errors),
        _hot_leads(errors),
        _followups_today(errors),
        _roadmap_tasks_today(errors),
        _open_deals(errors),
        _upcoming_payments(errors),
        _yesterday_changes(errors),
    ]

    # log every section error so it reaches the server logs
    for err in errors:
        logger.warning(f"[Digest] section error: {err}")

    header = [f"☀️ *דוח יומי — {today_str}*"]
    if shabbat:
        header.append(shabbat)
    if errors:
        header.append(f"🔴 *יש {len(errors)} שגיאות בדוח — בדוק פרטים בתחתית*")

    parts = header + [""]
    for section in sections:
        parts.append(section)
        parts.append("")

    if errors:
        parts.append("⚠️ *בעיות מערכת:*")
        for e in errors:
            parts.append(f"• {e}")
        parts.append("")

    parts.append("_Boss HQ — יום מוצלח!_ 💪")

    return "\n".join(p for p in parts if p is not None)


def send_daily_digest(bot, chat_id: str) -> None:
    """נקרא מ-scheduler.py בכל בוקר."""
    if not chat_id:
        logger.warning("send_daily_digest: chat_id ריק — מדלג")
        return
    try:
        text = build_digest()
        bot.send_message(chat_id, text, parse_mode="Markdown")
        logger.info(f"✅ Daily digest נשלח ל-{chat_id}")
    except Exception as e:
        logger.error(f"send_daily_digest failed: {e}")
