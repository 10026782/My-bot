# cmd_update.py — C20 Business Context Command
# /update | /עדכון  — שמירת הקשר עסקי ידני ל-Business Memory
# Feature flag: FEATURE_BUSINESS_UPDATE (כבוי ברירת מחדל)

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ── קבועים ──────────────────────────────────────────────────────
# מפתחות domain תואמים ל-Domain.ALL ב-identity.py — כדי שתגי
# Business Memory יתאמו בפועל ל-identity.domain_id בעת context injection.

DOMAINS = [
    ("נדל\"ן", "real_estate"),
    ("ייבוא",   "import"),
    ("מדיה",    "media"),
    ("SaaS",    "saas"),
    ("כספים",  "finance"),
    ("כללי",   "general"),
]

# ממופה לערכים חוקיים ב-Airtable EVENT_TYPE
ENTRY_TYPES = [
    ("פגישה",      "Milestone"),
    ("שיחה",       "Other"),
    ("החלטה",      "Decision"),
    ("סיכון",      "Crisis"),
    ("הצעת מחיר", "Other"),
    ("רעיון",      "Learning"),
    ("אחר",        "Other"),
]

_STATE_TTL_SECONDS = 30 * 60  # 30 דקות
_ALLOWED_ROLES = ("owner", "manager", "partner")

# ── State store — key: telegram user_id (str) ───────────────────
# האובייקט identity המלא נשמר בתוך state["identity"] (נקבע פעם אחת ב-/update).
_pending: dict[str, dict] = {}


# ── Registration ─────────────────────────────────────────────────

def register_update_command(bot, get_identity):
    """נקרא מ-app.py פעם אחת ב-startup."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_BUSINESS_UPDATE"):
            logger.info("[C20] FEATURE_BUSINESS_UPDATE=off — /update not registered")
            return
    except ImportError:
        pass  # dev mode

    # ── /update ─────────────────────────────────────────────────
    @bot.message_handler(commands=["update", "עדכון"])
    def cmd_update(msg):
        logger.info(f"[/update] handler fired for user {msg.from_user.id}")
        try:
            identity = get_identity("telegram", str(msg.from_user.id))
        except Exception as e:
            logger.error(f"[/update] identity error: {e}", exc_info=True)
            bot.send_message(msg.chat.id, "❌ שגיאה בזיהוי משתמש.")
            return
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
            return

        uid = str(msg.from_user.id)
        _pending[uid] = {
            "step":       "domain",
            "identity":   identity,
            "created_at": _now_ts(),
        }

        bot.send_message(
            msg.chat.id,
            "📋 *עדכון עסקי חדש*\n\nבחר תחום:",
            reply_markup=_domain_keyboard(),
            parse_mode="Markdown",
        )

    # ── /cancel ──────────────────────────────────────────────────
    @bot.message_handler(commands=["cancel", "בטל"])
    def cmd_cancel(msg):
        uid = str(msg.from_user.id)
        if _pending.pop(uid, None):
            bot.send_message(msg.chat.id, "✅ העדכון בוטל.")
        else:
            bot.send_message(msg.chat.id, "אין עדכון פתוח לביטול.")

    # ── inline: בחירת תחום ───────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("upd_domain:"))
    def cb_domain(call):
        uid   = str(call.from_user.id)
        state = _get_valid_state(uid)

        if not state or state.get("step") != "domain":
            bot.answer_callback_query(call.id, "פג תוקף — נסה /update מחדש.")
            return

        state["domain"] = call.data.split(":")[1]
        state["step"]   = "type"
        _pending[uid]   = state

        bot.edit_message_text(
            f"✅ תחום: *{_domain_label(state['domain'])}*\n\nסוג עדכון:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=_type_keyboard(),
            parse_mode="Markdown",
        )
        bot.answer_callback_query(call.id)

    # ── inline: בחירת סוג ───────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("upd_type:"))
    def cb_type(call):
        uid   = str(call.from_user.id)
        state = _get_valid_state(uid)

        if not state or state.get("step") != "type":
            bot.answer_callback_query(call.id, "פג תוקף — נסה /update מחדש.")
            return

        state["entry_type"] = call.data.split(":")[1]
        state["step"]       = "text"
        _pending[uid]       = state

        bot.edit_message_text(
            f"✅ {_domain_label(state['domain'])} → {state['entry_type']}\n\n"
            "✍️ מה קרה? כתוב בחופשיות:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        bot.answer_callback_query(call.id)

    # ── לכידת טקסט חופשי ────────────────────────────────────────
    # סינון כפול: step==text AND לא פקודה.
    # הסינון נשען רק על ה-dict המקומי — אסור לקרוא resolve_identity כאן.
    @bot.message_handler(
        func=lambda m: (
            _pending.get(str(m.from_user.id), {}).get("step") == "text"
            and bool(getattr(m, "text", None))
            and not m.text.startswith("/")
        )
    )
    def capture_text(msg):
        uid   = str(msg.from_user.id)
        state = _pending.pop(uid, None)

        if not state:
            return

        # TTL check פעם נוספת — הגנה כפולה
        if _is_expired(state):
            bot.send_message(msg.chat.id, "⏱ פג תוקף — נסה /update מחדש.")
            return

        # re-check הרשאה לפני כתיבה בפועל — לעולם לא לסמוך על state ישן בלבד
        identity = get_identity("telegram", uid)
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
            return

        record = _save_to_business_memory(
            identity   = identity,
            title      = f"{state['entry_type']}: {msg.text[:60]}",
            raw_text   = msg.text,
            domain     = state.get("domain", "general"),
            entry_type = state.get("entry_type", "Other"),
        )

        if record:
            bot.send_message(
                msg.chat.id,
                f"✅ *נשמר בזיכרון עסקי*\n\n"
                f"📌 {state['entry_type']} | {_domain_label(state['domain'])}\n"
                f"_{msg.text[:80]}{'...' if len(msg.text) > 80 else ''}_",
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                msg.chat.id,
                "⚠️ הטקסט התקבל אבל לא נשמר. בדוק logs.",
            )

    logger.info("[/update] handler registered successfully")


# ── תפיסת קובץ (photo/document) בשלב 'text' ──────────────────────
# app.py's webhook routes photo/document updates straight to the F16
# media handler (_handle_telegram_media) before ever calling
# bot.process_new_updates — so capture_text above, which only matches
# messages with .text, never sees them. Without this, an attachment sent
# mid-/update would silently fall through to the generic Drive-upload
# flow and orphan the pending state until its TTL expires. app.py must
# check has_pending_file_capture() and call capture_photo_or_document()
# *before* _handle_telegram_media for photo/document content types.

def has_pending_file_capture(user_id: str) -> bool:
    state = _get_valid_state(user_id)
    return bool(state and state.get("step") == "text")


# ── תפיסת טקסט חופשי בשלב 'text' ─────────────────────────────────
# app.py's webhook only calls bot.process_new_updates() for slash-command
# text (see the `if text.startswith("/")` branch) — free text never goes
# through it, so capture_text above (registered via @bot.message_handler)
# never fires for it either. Free text sent mid-/update instead falls all
# the way through to idempotency.is_duplicate() and then run_agent(),
# silently abandoning the pending state until its TTL expires. app.py must
# check has_pending_text_capture() *before* the idempotency check and, if
# True, call bot.process_new_updates([update]) itself so capture_text runs.

def has_pending_text_capture(user_id: str) -> bool:
    state = _get_valid_state(user_id)
    return bool(state and state.get("step") == "text")


def capture_photo_or_document(bot, message, get_identity) -> None:
    uid     = str(message.from_user.id)
    chat_id = message.chat.id
    state   = _pending.pop(uid, None)

    if not state:
        return

    if _is_expired(state):
        bot.send_message(chat_id, "⏱ פג תוקף — נסה /update מחדש.")
        return

    # re-check הרשאה לפני כתיבה בפועל — לעולם לא לסמוך על state ישן בלבד
    identity = get_identity("telegram", uid)
    if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
        bot.send_message(chat_id, "אין הרשאה לפקודה זו.")
        return

    caption = (getattr(message, "caption", None) or "").strip()
    drive_url = _upload_attachment(bot, message, uid, state.get("domain", "general"))
    extracted_text = _extract_document_text(bot, message)

    raw_text = caption or "קובץ מצורף"
    if extracted_text:
        raw_text = f"{raw_text}\n\n{extracted_text}"
    if drive_url:
        raw_text = f"{raw_text}\n📎 {drive_url}"

    record = _save_to_business_memory(
        identity   = identity,
        title      = f"{state['entry_type']}: {(caption or 'קובץ מצורף')[:60]}",
        raw_text   = raw_text,
        domain     = state.get("domain", "general"),
        entry_type = state.get("entry_type", "Other"),
    )

    if record:
        lines = [
            "✅ *נשמר בזיכרון עסקי*",
            "",
            f"📌 {state['entry_type']} | {_domain_label(state['domain'])}",
        ]
        if drive_url:
            lines.append(f"🔗 {drive_url}")
        if caption:
            lines.append(f"_{caption[:80]}{'...' if len(caption) > 80 else ''}_")
        bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "⚠️ הקובץ התקבל אבל לא נשמר. בדוק logs.")


def _upload_attachment(bot, message, uid: str, domain: str) -> str:
    """מעלה photo/document ל-Drive דרך media_handler הקיים. לא חוסם — כשל מחזיר ''."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_MEDIA_UPLOAD"):
            return ""
    except ImportError:
        return ""

    try:
        from media_handler import handle_file_upload

        if message.content_type == "photo":
            photo     = message.photo[-1]
            file_id   = photo.file_id
            filename  = f"{file_id}.jpg"
            mime_type = "image/jpeg"
            file_type = "image"
        else:
            doc       = message.document
            file_id   = doc.file_id
            filename  = doc.file_name or f"{file_id}"
            mime_type = doc.mime_type or "application/octet-stream"
            file_type = "document"

        file_info  = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        result = handle_file_upload(
            file_bytes = file_bytes,
            filename   = filename,
            mime_type  = mime_type,
            file_type  = file_type,
            file_id    = file_id,
            user_id    = uid,
            domain     = domain,
            source     = "telegram",
        )
        return result.drive_url if result.ok else ""
    except Exception as e:
        logger.error(f"[C20] attachment upload failed: {e}", exc_info=True)
        return ""


def _extract_document_text(bot, message) -> str | None:
    """מוריד document (לא photo) ומעביר ל-media_handler.extract_text_if_document.
    לא חוסם — כל כשל/פורמט לא נתמך מחזיר None והרשומה נשמרת רק עם caption+drive_url."""
    if message.content_type != "document":
        return None

    try:
        from media_handler import extract_text_if_document

        doc = message.document
        mime_type = doc.mime_type or "application/octet-stream"
        file_info  = bot.get_file(doc.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        return extract_text_if_document(file_bytes, mime_type)
    except Exception as e:
        logger.error(f"[C20] document text extraction failed: {e}", exc_info=True)
        return None


# ── נרמול שדות לפני כתיבה ל-Business Memory ──────────────────────
# Airtable מחזיר 422 על ערך שאינו option קיים בשדה singleSelect/
# multipleSelects (אין typecast=true בשכבת ה-gateway). BusinessMemoryFields
# עד כה לא היה לה שדה Domain ייעודי — ה-domain key הגולמי (למשל "media")
# נכתב ישירות לתוך Tags הכללי, שם אין לו שום ערבות שהוא option קיים.
# Root cause (מאושר מול production logs): domain לעולם לא אמור להיכתב
# ל-Tags בכלל — Tags הוא לנושאים אמיתיים ממקור נפרד, לא ל-domain. הכתיבה
# ל-Tags הוסרה לגמרי ב-_save_to_business_memory; domain נכתב רק לשדה
# Domain הייעודי (ממופה לערך Airtable חוקי). הסינון כאן נשאר כ-defense-in-
# depth בלבד, למקרה שמקור עתידי כן ימלא Tags עם נושאים אמיתיים.

_VALID_EVENT_TYPES = {"Milestone", "Decision", "Crisis", "Announcement", "Learning", "Other"}

_VALID_TAGS = {
    "Strategy", "Operations", "Finance", "HR", "Sales", "Customer", "Product",
    "Legal", "Risk", "Other", "Real Estate", "blue_view", "negotiation",
    "lessons", "gross_profit", "profit_distribution", "contracts", "numbers",
    "fatigue", "pressure", "option_agreement", "partners", "bargaining_power",
    "principle",
}

# מיפוי domain-key (מה-DOMAINS tuple הפנימי) → ערך Airtable חוקי
_DOMAIN_TO_AIRTABLE = {
    "real_estate": "Real Estate",   # Title Case הוא היחיד שנשאר ב-Airtable
    "import":      "Import",
    "media":       "Media",         # תוקן — Title Case, לא lowercase
    "saas":        "SaaS",
    "finance":     "General",       # אין option ייעודי — נופל ל-General, עם warning
    "general":     "General",
}


def normalize_business_memory_fields(fields: dict, raw_domain_key: str) -> dict:
    from airtable_schema import BusinessMemoryFields as BMF

    result = dict(fields)

    # Event Date
    if not result.get(BMF.DATE):
        result[BMF.DATE] = datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()

    # Event Type
    et = result.get(BMF.EVENT_TYPE)
    if et not in _VALID_EVENT_TYPES:
        logger.info(f"[BMF] normalized Event Type: {et!r} → Other")
        result[BMF.EVENT_TYPE] = "Other"

    # Tags — לא domain, רק נושאים אמיתיים (ממקור נפרד, אם וכשיהיה)
    if BMF.TAGS in result:
        raw_tags = result[BMF.TAGS]
        filtered = [t for t in raw_tags if t in _VALID_TAGS]
        dropped = set(raw_tags) - set(filtered)
        for d in dropped:
            logger.info(f"[BMF] dropped invalid tag: {d}")
        if filtered:
            result[BMF.TAGS] = filtered
        else:
            result.pop(BMF.TAGS, None)
            logger.info("[BMF] removed empty Tags after filtering")

    # Domain — כתיבה לשדה הייעודי, לא ל-Tags
    airtable_domain = _DOMAIN_TO_AIRTABLE.get(raw_domain_key)
    if airtable_domain:
        if airtable_domain != raw_domain_key:
            logger.info(f"[BMF] normalized Domain: {raw_domain_key} → {airtable_domain}")
        result[BMF.DOMAIN] = airtable_domain
    else:
        logger.warning(f"[BMF] no domain mapping for '{raw_domain_key}' — defaulting to General")
        result[BMF.DOMAIN] = "General"

    return result


# ── שמירה — דרך gateway בלבד ────────────────────────────────────

def _save_to_business_memory(
    identity,
    title: str,
    raw_text: str,
    domain: str,
    entry_type: str,
) -> dict | None:
    source_tag = f"cmd_update:{identity.tenant_id}:{identity.user_id}"
    try:
        from tools.airtable_gateway import airtable_create
        from airtable_schema import Tables, BusinessMemoryFields as BMF

        fields = {
            BMF.TITLE:       title,
            BMF.DESCRIPTION: raw_text,
            BMF.DATE:        datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
            BMF.EVENT_TYPE:  entry_type,   # ערך חוקי: Decision|Milestone|Crisis|Announcement|Learning|Other
            BMF.IMPACT:      "Manual Entry",
        }
        fields = normalize_business_memory_fields(fields, domain)

        record = airtable_create(
            Tables.BUSINESS_MEMORY,
            fields,
            source=source_tag,
        )

        if record:
            logger.info(f"[C20] saved id={record.get('id','?')} domain={domain} type={entry_type}")
            try:
                from tools.airtable_security import audit_log_airtable
                audit_log_airtable(
                    "cmd_update",
                    identity,
                    {"table": Tables.BUSINESS_MEMORY, "domain": domain, "entry_type": entry_type},
                    f"created id={record.get('id', '?')}",
                )
            except Exception:
                pass  # audit לעולם לא שובר את ה-flow
        else:
            logger.warning(f"[C20] airtable_create returned None source={source_tag}")

        return record

    except Exception as e:
        logger.error(f"[C20] _save_to_business_memory failed: {e}")
        return None


# ── Context injection — נקרא מ-context.py ───────────────────────

def get_recent_business_context(domain: str = "general", limit: int = 5) -> str:
    """
    קריאה בלבד — לא דרך gateway.
    מחזיר מחרוזת ריקה אם אין נתונים או כשל — לא חוסם.
    מוגבל ל-600 תווים כדי לא להכביד על prompt.
    """
    try:
        from tools.airtable_tools import airtable_get
        from airtable_schema import Tables, BusinessMemoryFields as BMF

        if domain and domain != "general":
            airtable_domain = _DOMAIN_TO_AIRTABLE.get(domain, "General")
            formula = (
                f"OR("
                f"{{{BMF.DOMAIN}}}='{airtable_domain}',"
                f"{{{BMF.DOMAIN}}}='General',"
                # legacy fallback: records written before BUG-081 (Domain field
                # didn't exist yet) have the raw domain key baked into Tags instead
                f"FIND('{domain}',ARRAYJOIN({{{BMF.TAGS}}}))"
                f")"
            )
        else:
            formula = ""

        raw = airtable_get(Tables.BUSINESS_MEMORY, formula)

        if not raw or "אין רשומות" in raw or "❌" in raw:
            return ""

        text = f"[זיכרון עסקי]\n{raw}"
        return text[:600]   # תקרה קשיחה

    except Exception as e:
        logger.debug(f"[C20] get_recent_business_context failed (non-blocking): {e}")
        return ""


# ── פונקציות עזר ────────────────────────────────────────────────

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

def _is_expired(state: dict) -> bool:
    return (_now_ts() - state.get("created_at", 0)) > _STATE_TTL_SECONDS

def _get_valid_state(uid: str) -> dict | None:
    state = _pending.get(uid)
    if not state:
        return None
    if _is_expired(state):
        _pending.pop(uid, None)
        return None
    return state

def _domain_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[
        InlineKeyboardButton(label, callback_data=f"upd_domain:{key}")
        for label, key in DOMAINS
    ])
    return markup

def _type_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[
        InlineKeyboardButton(label, callback_data=f"upd_type:{val}")
        for label, val in ENTRY_TYPES
    ])
    return markup

def _domain_label(key: str) -> str:
    return next((l for l, k in DOMAINS if k == key), key)
