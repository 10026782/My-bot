# daily_digest.py
# דוח בוקר יומי — נשלח ב-08:00 לאליהו בטלגרם.
# scheduler.py מנסה לייבא send_daily_digest — חובה שיהיה קיים.

import logging
import os
import urllib.parse
from datetime import date, timedelta

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════

def _fetch(table_real: str, formula: str = "", max_rec: int = 20) -> list:
    """HTTP call ישיר ל-Airtable. מחזיר list[record] או []."""
    try:
        import httpx
        base = os.environ.get("AIRTABLE_BASE_ID", "")
        key  = os.environ.get("AIRTABLE_API_KEY", "")
        if not base or not key:
            return []
        params: dict = {}
        if formula:
            params["filterByFormula"] = formula
        if max_rec:
            params["maxRecords"] = max_rec
        encoded = urllib.parse.quote(table_real, safe="")
        r = httpx.get(
            f"https://api.airtable.com/v0/{base}/{encoded}",
            headers={"Authorization": f"Bearer {key}"},
            params=params,
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("records", [])
        logger.warning(f"_fetch({table_real}) → {r.status_code}: {r.text[:100]}")
    except Exception as e:
        logger.warning(f"_fetch({table_real}) error: {e}")
    return []


def _fmt(iso: str) -> str:
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso[:10]).strftime("%d/%m")
    except Exception:
        return iso[:5] if iso else "—"


# ══════════════════════════════════════════════════
# Sections
# ══════════════════════════════════════════════════

def _hot_leads(errors: list) -> str:
    """🔥 לידים חמים — score>=70 או tier=HOT / status=hot"""
    try:
        records = _fetch(
            "Leads",
            "OR({status}='hot',{status}='Hot',{status}='HOT')",
            max_rec=8,
        )
        if not records:
            return "🔥 *לידים חמים:* אין כרגע"
        lines = ["🔥 *לידים חמים:*"]
        for r in records:
            f         = r.get("fields", {})
            score     = f.get("score ציון", 0) or 0
            next_step = f.get("next_step", "—") or "—"
            lines.append(
                f"• {f.get('Name','?')} | {f.get('phone','—')} | ⭐{score} | {next_step}"
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


def _urgent_tasks(errors: list) -> str:
    """✅ משימות דחופות — due <= מחר ולא בוצע; deadlines גבוהה ולא הושלם"""
    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        task_recs = _fetch(
            "משימות (Tasks)",
            f"AND(IS_BEFORE({{תאריך יעד}}, '{tomorrow}'), {{סטטוס}} != 'בוצע')",
            max_rec=10,
        )
        dl_recs = _fetch(
            "משימות ודד ליינים",
            "AND({עדיפות}='גבוהה', {סטטוס}!='הושלם')",
            max_rec=5,
        )

        lines = ["✅ *משימות דחופות:*"]
        count = 0

        for r in task_recs:
            f = r.get("fields", {})
            lines.append(
                f"• {f.get('כותרת המשימה','?')} | {_fmt(f.get('תאריך יעד',''))} | {f.get('סטטוס','—')}"
            )
            count += 1

        for r in dl_recs:
            f = r.get("fields", {})
            lines.append(
                f"• ⚡ {f.get('שם המשימה','?')} | {_fmt(f.get('תאריך דדליין',''))} | {f.get('אחראי','—')}"
            )
            count += 1

        if not count:
            return "✅ *משימות דחופות:* אין"
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"משימות: {e}")
        return "✅ *משימות דחופות:* שגיאה"


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
            "תשלומים (Payments)",
            f"AND("
            f"{{סטטוס}} != 'התקבל', "
            f"IS_BEFORE({{תאריך}}, '{deadline.isoformat()}'), "
            f"IS_AFTER({{תאריך}}, '{today.isoformat()}')"
            f")",
            max_rec=10,
        )
        if not records:
            return "💰 *תשלומים קרובים:* אין"
        lines = ["💰 *תשלומים קרובים:*"]
        total = 0
        for r in records:
            f      = r.get("fields", {})
            amount = f.get("סכום", 0)
            total += amount if isinstance(amount, (int, float)) else 0
            amt    = f"₪{amount:,.0f}" if isinstance(amount, (int, float)) else "—"
            lines.append(
                f"• {f.get('אסמכתא','?')} | {amt} | {_fmt(f.get('תאריך',''))} | {f.get('סטטוס','—')}"
            )
        lines.append(f"💰 *סה\"כ: ₪{total:,.0f}*")
        return "\n".join(lines)
    except Exception as e:
        errors.append(f"תשלומים: {e}")
        return "💰 *תשלומים קרובים:* שגיאה"


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

    parts = [
        f"☀️ *דוח יומי — {today_str}*",
        shabbat,
        "",
        _hot_leads(errors),
        "",
        _followups_today(errors),
        "",
        _urgent_tasks(errors),
        "",
        _open_deals(errors),
        "",
        _upcoming_payments(errors),
        "",
    ]

    if errors:
        parts.append("⚠️ *בעיות מערכת:*")
        for e in errors:
            parts.append(f"• {e}")
        parts.append("")

    parts.append(_yesterday_changes(errors))
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
