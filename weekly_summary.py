# weekly_summary.py — C22 Weekly Business Summary
# רץ כל ראשון 08:30 דרך scheduler.
# שולף Business Memory — 7 ימים אחרונים, מקבץ לפי Domain,
# שולח סיכום לטלגרם + כפתור העברה ל-ROADMAP לרעיונות.
# Feature flag: FEATURE_WEEKLY_SUMMARY (כבוי ברירת מחדל)
# Read-only לחלוטין — לא כותב לשום מקום.

import logging
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

_IL_TZ = ZoneInfo("Asia/Jerusalem")

# תיוג ידידותי לפי domain — תואם ל-Domain.ALL / cmd_update.py's DOMAINS
_DOMAIN_LABELS = {
    "real_estate": "🏠 נדל\"ן",
    "import":      "📦 ייבוא",
    "media":       "📺 מדיה",
    "saas":        "💻 SaaS",
    "finance":     "💰 כספים",
    "general":     "🗂 כללי",
}

# Event Type שנחשב "רעיון" — יוצג עם כפתור ROADMAP.
# הערך האמיתי היחיד ב-Airtable עבור "רעיון" הוא Learning (ראו cmd_update.py ENTRY_TYPES).
_IDEA_TYPES = {"Learning"}


def send_weekly_summary(bot, chat_id: str) -> None:
    """
    נקרא מ-scheduler._job_weekly_summary.
    לעולם לא זורק — כשל לא יפגע ב-scheduler.
    """
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_WEEKLY_SUMMARY"):
            logger.info("[C22] FEATURE_WEEKLY_SUMMARY=off — דולג")
            return
    except ImportError:
        pass  # dev mode

    try:
        entries = _fetch_last_7_days()

        if not entries:
            bot.send_message(
                chat_id,
                "📋 *סיכום שבועי — BOSS*\n\nלא נמצאו עדכונים השבוע.\nהשתמש ב-/update כדי להכניס.",
                parse_mode="Markdown",
            )
            return

        grouped  = _group_by_domain(entries)
        ideas    = _collect_ideas(entries)
        msg      = _build_message(grouped, ideas)

        if ideas:
            markup = _ideas_keyboard()
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode="Markdown")

        logger.info(f"[C22] weekly summary sent — {len(entries)} entries, {len(ideas)} ideas")

    except Exception as e:
        logger.error(f"[C22] send_weekly_summary failed: {e}")
        try:
            bot.send_message(chat_id, "⚠️ הסיכום השבועי נכשל. בדוק logs.")
        except Exception:
            pass


# ── שליפה ───────────────────────────────────────────────────────

def _fetch_last_7_days() -> list[dict]:
    """
    שולף רשומות מ-Business Memory — 7 ימים אחרונים.
    קריאה בלבד, לא דרך gateway. מחזיר list של fields dicts. ריק אם כשל.
    """
    try:
        from airtable_schema import BusinessMemoryFields as BMF

        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        formula = f"IS_AFTER({{{BMF.DATE}}}, '{since}')"
        return _fetch_records_direct(formula)

    except Exception as e:
        logger.error(f"[C22] _fetch_last_7_days failed: {e}")
        return []


def _fetch_records_direct(formula: str) -> list[dict]:
    """שליפת records גולמיים מ-Airtable — לסיכום בלבד."""
    from airtable_schema import Tables

    api_key = os.environ.get("AIRTABLE_API_KEY", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    if not api_key or not base_id:
        return []

    encoded = urllib.parse.quote(Tables.BUSINESS_MEMORY, safe="")
    r = httpx.get(
        f"https://api.airtable.com/v0/{base_id}/{encoded}",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"filterByFormula": formula, "maxRecords": "50"},
        timeout=10,
    )
    if r.status_code != 200:
        logger.warning(f"[C22] Airtable {r.status_code}: {r.text[:100]}")
        return []

    return [rec.get("fields", {}) for rec in r.json().get("records", [])]


# ── עיבוד ────────────────────────────────────────────────────────

def _group_by_domain(entries: list[dict]) -> dict[str, list[dict]]:
    """מקבץ לפי domain (Tags[0])."""
    from airtable_schema import BusinessMemoryFields as BMF

    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        tags   = entry.get(BMF.TAGS, []) or []
        domain = tags[0] if tags else "general"
        grouped.setdefault(domain, []).append(entry)
    return grouped


def _collect_ideas(entries: list[dict]) -> list[dict]:
    """מחזיר רשומות מסוג Learning (=\"רעיון\") בלבד."""
    from airtable_schema import BusinessMemoryFields as BMF
    return [e for e in entries if e.get(BMF.EVENT_TYPE, "") in _IDEA_TYPES]


# ── בניית הודעה ──────────────────────────────────────────────────

def _build_message(grouped: dict[str, list[dict]], ideas: list[dict]) -> str:
    from airtable_schema import BusinessMemoryFields as BMF

    now_str = datetime.now(_IL_TZ).strftime("%d/%m/%Y")
    lines   = [f"📋 *סיכום שבועי — BOSS*\n_{now_str}_\n"]

    for domain, entries in grouped.items():
        label = _DOMAIN_LABELS.get(domain, f"📌 {domain}")
        lines.append(f"\n{label} *({len(entries)} עדכונים):*")
        for e in entries[:5]:   # מקסימום 5 לכל domain — לא להציף
            title = e.get(BMF.TITLE, "ללא כותרת")
            etype = e.get(BMF.EVENT_TYPE, "")
            lines.append(f"  • [{etype}] {title[:70]}")
        if len(entries) > 5:
            lines.append(f"  _...ועוד {len(entries)-5} עדכונים_")

    if ideas:
        lines.append(f"\n💡 *{len(ideas)} רעיונות לדיון — להעביר ל-ROADMAP?*")

    return "\n".join(lines)


# ── כפתורי רעיונות ───────────────────────────────────────────────

def _ideas_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ כן, העבר ל-ROADMAP", callback_data="weekly_ideas:approve"),
        InlineKeyboardButton("⏭ לא עכשיו",           callback_data="weekly_ideas:skip"),
    )
    return markup


def register_weekly_callbacks(bot) -> None:
    """
    מרשם callback handlers לכפתורי הסיכום השבועי.
    נקרא מ-app.py פעם אחת ב-startup.
    """
    @bot.callback_query_handler(func=lambda c: c.data.startswith("weekly_ideas:"))
    def cb_weekly_ideas(call):
        action = call.data.split(":")[1]

        if action == "approve":
            bot.edit_message_text(
                "✅ הרעיונות סומנו — העבר אותם ל-ROADMAP.md בסשן הבא עם Claude Code.",
                call.message.chat.id,
                call.message.message_id,
            )
            logger.info("[C22] user approved ideas → ROADMAP transfer")

        elif action == "skip":
            bot.edit_message_text(
                "⏭ דולג — הרעיונות נשארים ב-Business Memory.",
                call.message.chat.id,
                call.message.message_id,
            )
            logger.info("[C22] user skipped ideas transfer")

        bot.answer_callback_query(call.id)
