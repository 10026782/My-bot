# cmd_decision.py — Decision Hub (Stage 0) Telegram Commands
# /decision new|update|status + forward→Inbox
# Feature flag: FEATURE_DECISION_HUB (כבוי ברירת מחדל)
#
# BOSS never deletes signal. BOSS only down-ranks it.
# כל קלט נשמר גולמי לפני עיבוד — אף פעם לא נמחק.

import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from airtable_schema import (
    Tables,
    DecisionFields, DecisionDomain, DecisionStatus,
    DecisionEventFields, DecisionEventChannel, DecisionEventStatus,
    DecisionStakeholderFields, DecisionStakeholderRole, DecisionStakeholderPosition,
    DecisionInboxFields, DecisionInboxChannel, DecisionInboxStatus,
)
from decision_matching import (
    DECISION_ALLOWED_ROLES, decision_in_scope, find_matching_decision,
    has_decision_capability, list_open_decisions,
)
from core.query_contract import all_of, any_of, array_contains, contains, equals
from decision_insight_source import (
    HOME_TENANT_ID, SOURCE_LABEL, build_insight_view, canonical_record,
    compose_event_content, excerpt, insight_marker, list_insights, read_insight,
    search_query_for_marker,
)
from core.draft_flow import DraftSpec, resolve_draft_reply
from tma_api import record_fields as _record_fields, record_id as _record_id
from tools.airtable_read_adapter import AirtableReadError, get_record, list_records

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 30 * 60  # 30 דקות
_ALLOWED_ROLES = DECISION_ALLOWED_ROLES


@dataclass(frozen=True)
class DecisionPersistenceResult:
    """Structured write outcome; side-effect failures must not look successful."""

    status: str
    record_id: str | None = None
    record: dict | None = None
    failed_steps: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"

# ── State store — key: telegram user_id (str) ───────────────────
_pending: dict[str, dict] = {}

_CONFIRM_WORDS = frozenset({"כן", "אשר", "מאשר", "מאשרת", "✅", "yes", "ok"})
_CANCEL_WORDS = frozenset({"לא", "בטל", "ביטול", "cancel", "no", "↩️"})
_EDIT_WORDS = frozenset({"ערוך", "עריכה", "edit"})
_NEW_EDIT_FIELDS = {
    "title": "שם ההחלטה",
    "domain": "דומיין",
    "exposure": "חשיפה כספית",
    "stakeholders": "צדדים",
}
_DECISION_DOMAIN_LABELS = {
    DecisionDomain.REAL_ESTATE: "נדל\"ן",
    DecisionDomain.IMPORT: "ייבוא",
    DecisionDomain.RECRUITMENT: "גיוס",
    DecisionDomain.PARTNERSHIP: "שותפות",
    DecisionDomain.GENERAL: "כללי",
    "real_estate": "נדל\"ן",
    "import": "ייבוא",
    "recruitment": "גיוס",
    "partnership": "שותפות",
    "general": "כללי",
}


def _decision_storage():
    """Canonical Decision domain storage boundary for Telegram writes."""
    from decision_ports import build_default_ports
    return build_default_ports().storage


def _callback_identity(get_identity, call):
    try:
        identity = get_identity("telegram", str(call.from_user.id))
    except Exception as exc:
        logger.warning("[DecisionHub] callback identity error: %s", exc)
        return None
    return identity if has_decision_capability(identity) else None


def _reject_callback(bot, call) -> None:
    bot.answer_callback_query(call.id, "לא ניתן לבצע פעולה זו.")


def _inbox_in_scope(inbox: dict | None, identity) -> bool:
    return bool(
        inbox and has_decision_capability(identity)
        and _record_fields(inbox).get(DecisionInboxFields.TENANT_ID) == getattr(identity, "tenant_id", None)
    )


def _inbox_callback_valid(inbox: dict | None) -> bool:
    return bool(inbox and _record_fields(inbox).get(DecisionInboxFields.STATUS) == DecisionInboxStatus.PENDING)


# ── Registration ─────────────────────────────────────────────────

def register_decision_command(bot, get_identity):
    """נקרא מ-app.py פעם אחת ב-startup."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_DECISION_HUB"):
            logger.info("[DecisionHub] FEATURE_DECISION_HUB=off — /decision not registered")
            return
    except ImportError:
        pass  # dev mode

    # ── /decision new|update|status ────────────────────────────
    @bot.message_handler(commands=["decision"])
    def cmd_decision(msg):
        try:
            identity = get_identity("telegram", str(msg.from_user.id))
        except Exception as e:
            logger.error(f"[/decision] identity error: {e}", exc_info=True)
            bot.send_message(msg.chat.id, "❌ שגיאה בזיהוי משתמש.")
            return
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
            return

        parts = msg.text.split(maxsplit=2)
        sub = parts[1].lower() if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""
        uid = str(msg.from_user.id)

        if sub == "new":
            _pending[uid] = _new_decision_state(identity)
            bot.send_message(msg.chat.id, "📋 *החלטה חדשה*\n\nשם ההחלטה?", parse_mode="Markdown")

        elif sub == "update":
            if not arg:
                bot.send_message(msg.chat.id, "שימוש: `/decision update <decision_id>`", parse_mode="Markdown")
                return
            decision = _resolve_decision_ref(arg, identity)
            if not decision:
                bot.send_message(msg.chat.id, f"❌ לא נמצאה החלטה תואמת ל-'{arg}'.")
                return
            _pending[uid] = {
                "command": "update", "step": "text",
                "decision": decision, "identity": identity, "created_at": _now_ts(),
            }
            title = _record_fields(decision).get(DecisionFields.TITLE, "")
            bot.send_message(msg.chat.id, f"📋 *{title}*\n\n✍️ מה קרה?", parse_mode="Markdown")

        elif sub == "status":
            if not arg:
                bot.send_message(msg.chat.id, "שימוש: `/decision status <decision_id>`", parse_mode="Markdown")
                return
            decision = _resolve_decision_ref(arg, identity)
            if not decision:
                bot.send_message(msg.chat.id, f"❌ לא נמצאה החלטה תואמת ל-'{arg}'.")
                return
            bot.send_message(msg.chat.id, _format_decision_card(decision, identity), parse_mode="Markdown")

        elif sub == "from-insight":
            _start_insight_flow(bot, msg, identity, arg.strip(), uid)

        else:
            bot.send_message(
                msg.chat.id,
                "שימוש:\n`/decision new`\n`/decision update <id>`\n`/decision status <id>`\n`/decision from-insight [חיפוש]`",
                parse_mode="Markdown",
            )

    # ── /cancel (משותף עם cmd_update — בדיקה דו-שלבית) ──────────
    @bot.message_handler(commands=["cancel", "בטל"])
    def cmd_cancel(msg):
        uid = str(msg.from_user.id)
        if _pending.pop(uid, None):
            bot.send_message(msg.chat.id, "✅ הפעולה בוטלה.")

    # ── inline: בחירת דומיין ב-/decision new ────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_domain:"))
    def cb_domain(call):
        uid = str(call.from_user.id)
        state = _get_valid_state(uid)
        if not state or state.get("command") != "new" or state.get("step") not in {"domain", "edit_choice"}:
            bot.answer_callback_query(call.id, "פג תוקף — נסה /decision new מחדש.")
            return

        state["domain"] = call.data.split(":", 1)[1]
        editing = state.get("step") == "edit_choice"
        state["step"] = "review" if editing else "exposure"
        state["mode"] = "review" if editing else "filling"
        state["awaiting_field"] = None if editing else "exposure"
        _pending[uid] = state

        bot.edit_message_text(
            _decision_new_review(state) if editing else
            f"✅ דומיין: *{state['domain']}*\n\n💰 חשיפה כספית משוערת? (מספר)",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown",
            reply_markup=_decision_new_review_keyboard(state["token"]) if editing else None,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_new_confirm:"))
    def cb_new_confirm(call):
        _resolve_new_terminal_callback(bot, call, "confirm")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_new_cancel:"))
    def cb_new_cancel(call):
        _resolve_new_terminal_callback(bot, call, "cancel")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_new_edit:"))
    def cb_new_edit(call):
        uid = str(call.from_user.id)
        state = _get_valid_state(uid)
        parts = (call.data or "").split(":", 2)
        token = parts[1] if len(parts) > 1 else ""
        field = parts[2] if len(parts) > 2 else ""
        if not state or state.get("command") != "new" or state.get("token") != token:
            bot.answer_callback_query(call.id, "ℹ️ התהליך כבר אינו זמין.")
            return
        if field == "menu":
            bot.edit_message_text(
                "איזה שדה לערוך?", call.message.chat.id, call.message.message_id,
                reply_markup=_decision_new_edit_keyboard(token),
            )
            bot.answer_callback_query(call.id, "✏️ עריכה")
            return
        if field not in _NEW_EDIT_FIELDS:
            bot.answer_callback_query(call.id, "שדה לא מוכר.")
            return
        if field == "domain":
            state["step"] = "edit_choice"
            _pending[uid] = state
            bot.edit_message_text("בחר דומיין חדש:", call.message.chat.id, call.message.message_id, reply_markup=_domain_keyboard())
        else:
            state["step"] = "edit_value"
            state["edit_field"] = field
            _pending[uid] = state
            bot.edit_message_text(f"{_NEW_EDIT_FIELDS[field]} — הזן ערך חדש:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "✏️ עריכה")

    # ── inline: forward→Inbox — שיוך מוצע / נבחר ────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_link:"))
    def cb_inbox_link(call):
        parts = (call.data or "").split(":", 2)
        identity = _callback_identity(get_identity, call)
        if len(parts) != 3 or not identity:
            _reject_callback(bot, call)
            return
        _link_inbox_to_decision(bot, call, parts[1], parts[2], identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_pick_choice:"))
    def cb_inbox_pick_choice(call):
        parts = (call.data or "").split(":", 2)
        identity = _callback_identity(get_identity, call)
        if len(parts) != 3 or not identity:
            _reject_callback(bot, call)
            return
        _link_inbox_to_decision(bot, call, parts[1], parts[2], identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_pick:"))
    def cb_inbox_pick(call):
        parts = (call.data or "").split(":", 1)
        identity = _callback_identity(get_identity, call)
        if len(parts) != 2 or not identity:
            _reject_callback(bot, call)
            return
        inbox_id = parts[1]
        inbox_record = _at_get_record(Tables.DECISION_INBOX, inbox_id)
        if not _inbox_in_scope(inbox_record, identity) or not _inbox_callback_valid(inbox_record):
            _reject_callback(bot, call)
            return
        open_decisions = _list_open_decisions(identity=identity)
        if not open_decisions:
            bot.answer_callback_query(call.id, "אין החלטות פתוחות.")
            return

        markup = _decision_pick_keyboard(inbox_id, open_decisions)
        bot.edit_message_text(
            "לאיזו החלטה זה שייך?",
            call.message.chat.id, call.message.message_id, reply_markup=markup,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_ignore:"))
    def cb_inbox_ignore(call):
        parts = (call.data or "").split(":", 1)
        identity = _callback_identity(get_identity, call)
        if len(parts) != 2 or not identity:
            _reject_callback(bot, call)
            return
        inbox_id = parts[1]
        inbox_record = _at_get_record(Tables.DECISION_INBOX, inbox_id)
        if not _inbox_in_scope(inbox_record, identity) or not _inbox_callback_valid(inbox_record):
            _reject_callback(bot, call)
            return
        _decision_storage().update(
            Tables.DECISION_INBOX, inbox_id,
            {DecisionInboxFields.STATUS: DecisionInboxStatus.REJECTED},
            source="cmd_decision:inbox_ignore",
        )
        bot.edit_message_text(
            "🗑 התעלמתי. נשאר ב-Decision Inbox לעיון מאוחר יותר.",
            call.message.chat.id, call.message.message_id,
        )
        bot.answer_callback_query(call.id)

    # ── inline: /decision from-insight — תובנה → החלטה ──────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_ins_pick:"))
    def cb_insight_pick(call):
        _insight_cb_pick(bot, call, get_identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_ins_target:"))
    def cb_insight_target(call):
        _insight_cb_target(bot, call, get_identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_ins_retarget:"))
    def cb_insight_retarget(call):
        _insight_cb_retarget(bot, call, get_identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_ins_confirm:"))
    def cb_insight_confirm(call):
        _insight_cb_confirm(bot, call, get_identity)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_ins_cancel:"))
    def cb_insight_cancel(call):
        _insight_cb_cancel(bot, call, get_identity)

    # ── לכידת טקסט חופשי (new/update flows) ──────────────────────
    @bot.message_handler(
        func=lambda m: (
            _pending.get(str(m.from_user.id), {}).get("step") in ("title", "exposure", "stakeholders", "edit_choice", "edit_value", "review", "text")
            and bool(getattr(m, "text", None))
            and not m.text.startswith("/")
        )
    )
    def capture_text(msg):
        uid = str(msg.from_user.id)
        state = _pending.get(uid)
        if not state or _is_expired(state):
            _pending.pop(uid, None)
            bot.send_message(msg.chat.id, "⏱ פג תוקף — נסה /decision מחדש.")
            return

        if state["command"] == "new":
            _handle_new_step(bot, msg, state)
        elif state["command"] == "update":
            _handle_update_step(bot, msg, state, get_identity)

    # ── forward → Inbox (דלת הכניסה האמיתית) ─────────────────────
    @bot.message_handler(
        func=lambda m: (
            getattr(m, "forward_date", None) is not None
            and str(m.from_user.id) not in _pending
        )
    )
    def capture_forward(msg):
        try:
            identity = get_identity("telegram", str(msg.from_user.id))
        except Exception as e:
            logger.error(f"[/decision forward] identity error: {e}", exc_info=True)
            return
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            return

        _handle_forward(bot, msg, identity)

    logger.info("[/decision] handler registered successfully")


# ── /decision new — דיאלוג רב-שלבי ──────────────────────────────

def _decision_domains() -> tuple[str, ...]:
    return (
        DecisionDomain.REAL_ESTATE, DecisionDomain.IMPORT,
        DecisionDomain.RECRUITMENT, DecisionDomain.PARTNERSHIP,
        DecisionDomain.GENERAL,
    )


def _new_decision_state(identity) -> dict:
    return {
        "command": "new", "step": "title", "mode": "filling", "awaiting_field": "title", "identity": identity,
        "created_at": _now_ts(), "token": uuid.uuid4().hex,
        "title": "", "domain": "", "exposure": 0.0,
        "stakeholder_names": [],
    }


def _validate_new_field(field: str, raw: str):
    text = (raw or "").strip()
    if field == "title":
        return (text, "") if text else (None, "שם ההחלטה לא יכול להיות ריק.")
    if field == "exposure":
        if not re.fullmatch(r"\d+(?:\.\d+)?", text):
            return None, "החשיפה חייבת להיות מספר לא שלילי."
        return float(text), ""
    if field == "stakeholders":
        names = _parse_names(text)
        return (names, "") if names else (None, "נדרש לפחות צד אחד.")
    return text, ""


def _set_new_draft_field(draft: dict, field: str, raw: str) -> tuple[bool, str]:
    validation_field = "stakeholders" if field in {"stakeholders", "stakeholder_names"} else field
    value, error = _validate_new_field(validation_field, raw)
    if error:
        return False, error
    draft["stakeholder_names" if field in {"stakeholders", "stakeholder_names"} else field] = value
    return True, ""


def _render_new_draft(draft: dict) -> str:
    return _decision_new_review(draft)


_DECISION_NEW_DRAFT_SPEC = DraftSpec(
    required_fields=("title", "domain", "exposure", "stakeholder_names"),
    field_prompts={
        "title": "שם ההחלטה?",
        "domain": "דומיין?",
        "exposure": "💰 חשיפה כספית משוערת? (מספר)",
        "stakeholder_names": "👥 מי הצדדים? (שמות, מופרדים בפסיק)",
    },
    edit_labels={
        "שם": "title", "דומיין": "domain", "חשיפה": "exposure", "צדדים": "stakeholder_names",
    },
    set_field=_set_new_draft_field,
    render=_render_new_draft,
    unknown_field_message="שדה לא מוכר. בחר/י: שם / דומיין / חשיפה / צדדים.",
    edit_choice_prompt="איזה שדה לערוך? שם / דומיין / חשיפה / צדדים.",
)


def _decision_new_review(state: dict) -> str:
    names = ", ".join(state.get("stakeholder_names", [])) or "—"
    domain = _DECISION_DOMAIN_LABELS.get(state.get("domain"), "כללי")
    return (
        "📋 *החלטה חדשה — לבדיקה*\n\n"
        f"שם: {state.get('title', '')}\n"
        f"דומיין: {domain}\n"
        f"חשיפה: {state.get('exposure', 0):g}\n"
        f"צדדים: {names}\n\n"
        "בחר/י ✅ אישור, ✏️ עריכה או ↩️ ביטול."
    )


def _decision_new_review_keyboard(token: str):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("✅ אישור", callback_data=f"dec_new_confirm:{token}"),
        InlineKeyboardButton("✏️ עריכה", callback_data=f"dec_new_edit:{token}:menu"),
        InlineKeyboardButton("↩️ ביטול", callback_data=f"dec_new_cancel:{token}"),
    )
    return markup


def _decision_new_edit_keyboard(token: str):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(*[
        InlineKeyboardButton(label, callback_data=f"dec_new_edit:{token}:{field}")
        for field, label in _NEW_EDIT_FIELDS.items()
    ])
    return markup


def _decision_new_receipt(result: DecisionPersistenceResult | dict | None, title: str = "") -> str:
    if isinstance(result, DecisionPersistenceResult):
        if result.status == "PARTIAL":
            return "⚠️ ההחלטה נשמרה חלקית; חלק מפרטי הצדדים לא נשמרו. בדוק לפני המשך."
        record = result.record
    else:
        record = result
    if not record:
        return "⚠️ ההחלטה לא נשמרה."
    return f"✅ ההחלטה נשמרה: {title}" if title else "✅ ההחלטה נשמרה."


def _resolve_new_terminal_callback(bot, call, action: str) -> None:
    uid = str(call.from_user.id)
    state = _get_valid_state(uid)
    token = (call.data or "").split(":", 1)[1]
    if not state or state.get("command") != "new" or state.get("step") != "review" or state.get("token") != token:
        bot.answer_callback_query(call.id, "ℹ️ התהליך כבר אינו זמין.")
        return
    _pending.pop(uid, None)
    if action == "cancel":
        bot.answer_callback_query(call.id, "✅ התקבל")
        bot.edit_message_text("↩️ ההחלטה בוטלה.", call.message.chat.id, call.message.message_id)
        return
    record = _create_decision(
        state["identity"], state["title"], state["domain"],
        state["exposure"], state["stakeholder_names"],
    )
    bot.answer_callback_query(call.id, "✅ התקבל")
    bot.edit_message_text(_decision_new_receipt(record, state["title"]), call.message.chat.id, call.message.message_id)


def _handle_new_step(bot, msg, state):
    if state["step"] == "review":
        state["mode"] = "review"
    elif state["step"] in {"title", "exposure", "stakeholders"}:
        state["mode"] = "filling"
        state["awaiting_field"] = {"stakeholders": "stakeholder_names"}.get(state["step"], state["step"])
    if state["step"] == "domain":
        state["mode"] = "filling"
        state["awaiting_field"] = "domain"
        bot.send_message(msg.chat.id, "בחר דומיין חדש:", reply_markup=_domain_keyboard())
        return
    was_edit_choice = state["step"] == "edit_choice"
    if state["step"] == "edit_choice":
        state["mode"] = "edit_choice"
    elif state["step"] == "edit_value":
        state["mode"] = "filling"
        state["awaiting_field"] = state.pop("edit_field")

    outcome = resolve_draft_reply(msg.text, state, _DECISION_NEW_DRAFT_SPEC)
    if outcome.kind == "confirm":
        _pending.pop(str(msg.from_user.id), None)
        record = _create_decision(
            state["identity"], state["title"], state["domain"],
            state["exposure"], state["stakeholder_names"],
        )
        bot.send_message(msg.chat.id, _decision_new_receipt(record, state["title"]))
    elif outcome.kind == "cancel":
        _pending.pop(str(msg.from_user.id), None)
        bot.send_message(msg.chat.id, "↩️ ההחלטה בוטלה.")
    elif outcome.kind == "reply":
        if state.get("awaiting_field") == "domain":
            state["step"] = "domain"
            bot.send_message(msg.chat.id, "דומיין?", reply_markup=_domain_keyboard())
        elif state.get("mode") == "review":
            state["step"] = "review"
            bot.send_message(msg.chat.id, outcome.message, reply_markup=_decision_new_review_keyboard(state["token"]))
        elif state.get("mode") == "edit_choice":
            state["step"] = "edit_choice"
            bot.send_message(msg.chat.id, outcome.message)
        elif was_edit_choice:
            state["step"] = "edit_value"
            state["edit_field"] = state.get("awaiting_field")
            bot.send_message(msg.chat.id, outcome.message)
        else:
            state["step"] = {"stakeholder_names": "stakeholders"}.get(
                state.get("awaiting_field"), state.get("awaiting_field", "title")
            )
            _pending[str(msg.from_user.id)] = state
            bot.send_message(msg.chat.id, outcome.message)


def _create_decision(
    identity, title: str, domain: str, exposure: float, stakeholder_names: list[str]
) -> DecisionPersistenceResult:
    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    fields = {
        DecisionFields.TITLE: title,
        DecisionFields.DOMAIN: domain,
        DecisionFields.ESTIMATED_EXPOSURE: exposure,
        DecisionFields.STATUS: DecisionStatus.OPEN,
        DecisionFields.TENANT_ID: identity.tenant_id,
    }
    record_id = _decision_storage().add(Tables.DECISIONS, fields, source=source_tag)
    if not record_id:
        logger.warning(f"[DecisionHub] _create_decision failed source={source_tag}")
        return DecisionPersistenceResult(status="FAILED", failed_steps=("decision",))
    record = {"id": record_id, "fields": fields}

    failed_steps = []
    for name in stakeholder_names:
        stakeholder_result = _create_stakeholder(identity, _record_id(record, required=True), name)
        if not stakeholder_result.ok:
            failed_steps.append("stakeholder")

    return DecisionPersistenceResult(
        status="PARTIAL" if failed_steps else "SUCCESS",
        record_id=record_id,
        record=record,
        failed_steps=tuple(failed_steps),
    )


def _create_stakeholder(identity, decision_id: str, name: str) -> DecisionPersistenceResult:
    from tools.contact_resolver import resolve, ResolveStatus

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    result = resolve(name)
    contact_id = result.matches[0].record_id if result.status == ResolveStatus.FOUND_ONE and result.matches else None

    fields = {
        DecisionStakeholderFields.DECISION: [decision_id],
        DecisionStakeholderFields.ROLE: DecisionStakeholderRole.PENDING,
        DecisionStakeholderFields.POSITION: DecisionStakeholderPosition.PENDING,
        DecisionStakeholderFields.POSITION_DETAILS: "" if contact_id else f"לא זוהה איש קשר: {name}",
        DecisionStakeholderFields.TENANT_ID: identity.tenant_id,
    }
    if contact_id:
        fields[DecisionStakeholderFields.CONTACT] = [contact_id]

    try:
        record_id = _decision_storage().add(
            Tables.DECISION_STAKEHOLDERS, fields, source=source_tag
        )
    except Exception:
        logger.exception("[DecisionHub] stakeholder persistence failed")
        return DecisionPersistenceResult(status="FAILED", failed_steps=("stakeholder",))
    if not record_id:
        logger.warning("[DecisionHub] stakeholder persistence returned no record id")
        return DecisionPersistenceResult(status="FAILED", failed_steps=("stakeholder",))
    return DecisionPersistenceResult(status="SUCCESS", record_id=record_id)


# ── /decision update — Event + run_pipeline ─────────────────────

def _handle_update_step(bot, msg, state, get_identity):
    uid = str(msg.from_user.id)
    _pending.pop(uid, None)

    # re-check הרשאה לפני כתיבה בפועל — לעולם לא לסמוך על state ישן בלבד
    identity = get_identity("telegram", uid)
    if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
        bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
        return

    decision = state["decision"]
    has_attachment = bool(getattr(msg, "photo", None) or getattr(msg, "document", None))

    event = {
        "raw_content": msg.text or "",
        "attachment": has_attachment,
        "Channel": DecisionEventChannel.TELEGRAM,
        "_decision_id": _record_id(decision, required=True),
    }

    from decision_pipeline import run_pipeline
    outcome = run_pipeline(event, _record_fields(decision))

    event_result = _create_decision_event(identity, _record_id(decision, required=True), event)
    text = _format_pipeline_outcome(
        _record_fields(decision).get(DecisionFields.TITLE, ""), outcome, event, event_result
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    if event_result.ok:
        logger.info(f"[DecisionHub] event created id={event_result.record_id} halted_at={outcome['halted_at']}")


def _create_decision_event(identity, decision_id: str, event: dict) -> DecisionPersistenceResult:
    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    fields = {
        DecisionEventFields.DECISION: [decision_id],
        DecisionEventFields.EVENT_DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        DecisionEventFields.CHANNEL: event.get("Channel", DecisionEventChannel.TELEGRAM),
        DecisionEventFields.RAW_CONTENT: event.get("raw_content", ""),
        DecisionEventFields.DELTA_TYPE: event.get("Delta Type", ""),
        DecisionEventFields.STATUS: event.get("Status", DecisionEventStatus.LOGGED),
        DecisionEventFields.TENANT_ID: identity.tenant_id,
    }
    _add_trust_fields(fields, event)
    try:
        record_id = _decision_storage().add(
            Tables.DECISION_EVENTS, fields, source=source_tag
        )
    except Exception:
        logger.exception("[DecisionHub] event persistence failed")
        return DecisionPersistenceResult(status="FAILED", failed_steps=("event",))
    if not record_id:
        logger.warning("[DecisionHub] event persistence returned no record id")
        return DecisionPersistenceResult(status="FAILED", failed_steps=("event",))
    return DecisionPersistenceResult(status="SUCCESS", record_id=record_id)


def _add_trust_fields(fields: dict, event: dict) -> None:
    """Stage 1 — מעביר את פלט gate_trust מ-event ל-fields שנכתבים ל-Airtable."""
    if "Trust Level" in event:
        fields[DecisionEventFields.TRUST_LEVEL] = event["Trust Level"]
    if "Confidence" in event:
        fields[DecisionEventFields.CONFIDENCE] = event["Confidence"]
    if event.get("Tags"):
        fields[DecisionEventFields.TAGS] = event["Tags"]
    if event.get("Claim Topic"):
        fields[DecisionEventFields.CLAIM_TOPIC] = event["Claim Topic"]
    if event.get("Claim Topic Source"):
        fields[DecisionEventFields.CLAIM_TOPIC_SOURCE] = event["Claim Topic Source"]
    if "Claim Topic Confidence" in event:
        fields[DecisionEventFields.CLAIM_TOPIC_CONFIDENCE] = event["Claim Topic Confidence"]
    if event.get("Source Reliability"):
        fields[DecisionEventFields.SOURCE_RELIABILITY] = event["Source Reliability"]
    if event.get("Supersedes"):
        fields[DecisionEventFields.SUPERSEDES] = event["Supersedes"]


def _format_pipeline_outcome(
    title: str,
    outcome: dict,
    event: dict,
    persistence: DecisionPersistenceResult | None = None,
) -> str:
    if persistence and not persistence.ok:
        if persistence.record_id:
            return f"⚠️ «{title}» — העדכון נשמר חלקית; היסטוריית האירוע לא נשמרה. אין זו הצלחה מלאה."
        return f"⚠️ «{title}» — העדכון לא הושלם; היסטוריית האירוע לא נשמרה."
    halted_at = outcome["halted_at"]
    result = outcome["result"]
    delta_type = event.get("Delta Type", "")

    if halted_at == "delta" and delta_type == "לחץ":
        return f"📋 «{title}» — עדכון נשמר\n✗ אין עובדה חדשה — לחץ טקטי בלבד.\nנרשם בהיסטוריה, לא דורש פעולה."
    if halted_at == "delta":
        return f"📋 «{title}» — אותו מידע, ניסוח אחר. נרשם בלבד."
    if halted_at == "entity":
        return f"⚠️ «{title}» — {result.user_flag or result.reason}"
    if halted_at == "trust":
        return f"⚠️ «{title}» — {result.user_flag or result.reason}"
    base = f"✅ «{title}» — Event חדש נשמר ({delta_type})."
    if result.user_flag:
        base += f"\n{result.user_flag}"
    return base


# ── /decision status — כרטיס מלא ────────────────────────────────

def _format_decision_card(decision: dict, identity=None) -> str:
    f = _record_fields(decision)
    title = f.get(DecisionFields.TITLE, "")
    draft = f.get(DecisionFields.CURRENT_DRAFT, "")
    exposure = f.get(DecisionFields.ESTIMATED_EXPOSURE, "")
    urgency = f.get(DecisionFields.URGENCY, "")
    risk_yes = f.get(DecisionFields.RISK_IF_YES, "")
    risk_no = f.get(DecisionFields.RISK_IF_NO, "")
    missing = f.get(DecisionFields.MISSING_INFO, "")

    stakeholders = _list_stakeholders(_record_id(decision, required=True), identity)
    stakeholder_lines = "\n".join(
        f"  {_position_emoji(_record_fields(s).get(DecisionStakeholderFields.POSITION))} "
        f"{_linked_label(_record_fields(s).get(DecisionStakeholderFields.CONTACT))} — "
        f"{_record_fields(s).get(DecisionStakeholderFields.POSITION, '')}"
        for s in stakeholders
    ) or "  (אין)"

    events = _list_decision_events(_record_id(decision, required=True), identity)
    latest = _latest_event(_record_id(decision, required=True), events)
    latest_summary = _record_fields(latest).get(DecisionEventFields.AI_SUMMARY, "") if latest else "(אין)"
    attention_summary = ""
    try:
        from decision_attention import build_attention_summary, calc_priority

        attention = calc_priority(decision, events)
        attention_summary = build_attention_summary(attention)
    except Exception as e:
        logger.warning(f"[DecisionHub] attention summary failed: {e}")

    attention_block = f"\n\nAttention:\n{attention_summary}" if attention_summary else ""

    confidence_block, confidence_result = _format_confidence_block(decision, events)
    readiness_block, readiness_result = _format_readiness_block(
        decision,
        events,
        confidence_result,
    )

    # Airtable persistence is best-effort, so the fetched record may still
    # contain the previous readiness. Route on a shallow snapshot containing
    # the value calculated for this card without mutating the source record.
    orchestrator_decision = {
        **decision,
        "fields": {
            **_record_fields(decision),
            DecisionFields.READINESS: readiness_result.status,
        },
    }
    try:
        from decision_orchestrator import append_orchestrator_to_card

        orchestrator_block = append_orchestrator_to_card(
            orchestrator_decision,
            events,
            stakeholders,
            precomputed_confidence=confidence_result,
        )
    except Exception as e:
        logger.warning(f"[DecisionHub] orchestrator block failed: {e}")
        orchestrator_block = ""

    # Stage 6 — Core Reasoning Layer (core/adapters/decision_adapter.py).
    # orchestrator_block ו-reasoning_block מציגים את אותו מידע בעיקרו
    # (state, confidence, צעד הבא) — לא מציגים את שניהם יחד. reasoning_block
    # רץ רק כשFEATURE_DECISION_HUB כבוי, כ-fallback ל-Orchestrator המבוטל.
    reasoning_block = ""
    try:
        from feature_flags import is_enabled
        from decision_orchestrator import FEATURE_FLAG as _ORCHESTRATOR_FLAG

        if not is_enabled(_ORCHESTRATOR_FLAG):
            from core.adapters.decision_adapter import append_reasoning_block

            reasoning_block = append_reasoning_block(
                orchestrator_decision,
                events,
                stakeholders,
                precomputed_confidence=confidence_result,
            )
    except Exception as e:
        logger.warning(f"[DecisionHub] reasoning block failed: {e}")

    return (
        f"📋 {title} | טיוטה {draft}\n"
        f"────────────────────\n"
        f"💰 חשיפה: {exposure}\n"
        f"⏰ דחיפות: {urgency}\n\n"
        f"👥 עמדות:\n{stakeholder_lines}\n\n"
        f"⚠️ בחתימה: {risk_yes}\n"
        f"⚠️ באי-חתימה: {risk_no}\n\n"
        f"❓ חסר: {missing}\n\n"
        f"{confidence_block}\n\n"
        f"{readiness_block}\n"
        f"🔄 אחרון: {latest_summary}"
        f"{attention_block}"
        f"{orchestrator_block}"
    )


def _format_confidence_block(decision: dict, events: list) -> tuple:
    """Stage 2 (F17) — Smart Trust Layer: confidence/evidence/missing-evidence
    על ההחלטה כולה, מחושב מ-Events מקושרים. AI Conflict Detection רץ כאן בלבד
    (פתיחת כרטיס /decision status) — lazy + cached, לעולם לא ב-ingest.
    מחזיר (טקסט_להצגה, ConfidenceResult) — ה-ConfidenceResult נדרש ל-Stage 3
    (decision_readiness.py) כדי שלא יחושב פעמיים (כולל AI Conflict Detection)."""
    from decision_confidence import calc_confidence, build_evidence_summary

    domain = _record_fields(decision).get(DecisionFields.DOMAIN, "")
    result = calc_confidence(events, domain=domain)
    missing_evidence = result.missing
    evidence_summary = build_evidence_summary(events)

    _persist_confidence(_record_id(decision, required=True), result, missing_evidence, evidence_summary)

    pct = int(result.score * 100)
    lines = [f"📊 ביטחון בהחלטה: {pct}%", f"📎 ראיות: {evidence_summary}"]
    if result.conflicting:
        lines.append(f"⚡ קונפליקטים פתוחים: {len(result.conflicting)}")
    if missing_evidence:
        lines.append("⚠️ חסר לפני החלטה:\n" + "\n".join(f"  • {item}" for item in missing_evidence))
    return "\n".join(lines), result


def _format_readiness_block(decision: dict, events: list, confidence_result) -> tuple:
    """Stage 3 — Readiness Engine: האם ההחלטה מוכנה להכרעה אנושית. READY הוא
    איתות בלבד — לא מבצע שום פעולה."""
    from decision_readiness import calc_readiness, build_readiness_message

    result = calc_readiness(decision, events, confidence_result)
    _persist_readiness(_record_id(decision, required=True), result)
    return build_readiness_message(result), result


def _persist_confidence(decision_id: str, result, missing_evidence: list, evidence_summary: str) -> None:
    """כתיבה best-effort — לא חוסם את הצגת הכרטיס. עד שהשדות נוצרים ידנית
    ב-Airtable (Stage 2 SPEC §Schema), airtable_patch ישמיט אותם בשקט."""
    import json
    fields = {
        DecisionFields.CONFIDENCE_SCORE: result.score,
        DecisionFields.EVIDENCE_SUMMARY: evidence_summary,
        DecisionFields.EVIDENCE_IDS: json.dumps(result.supporting + result.conflicting),
        DecisionFields.MISSING_EVIDENCE: json.dumps(missing_evidence),
    }
    try:
        _decision_storage().update(Tables.DECISIONS, decision_id, fields, source="decision_confidence:stage2")
    except Exception as e:
        logger.warning(f"[DecisionHub] _persist_confidence failed: {e}")


def _persist_readiness(decision_id: str, result) -> None:
    """כתיבה best-effort — לא חוסם את הצגת הכרטיס. כותב רק לשדה Readiness
    הקיים כבר ב-DecisionFields (Stage 3 SPEC: אין שינוי סכמה ל-MVP — Score/
    Message/Escalation מוצגים רק ב-Telegram, לא נשמרים, עד אישור נפרד)."""
    try:
        _decision_storage().update(
            Tables.DECISIONS, decision_id,
            {DecisionFields.READINESS: result.status},
            source="decision_readiness:stage3",
        )
    except Exception as e:
        logger.warning(f"[DecisionHub] _persist_readiness failed: {e}")


def _position_emoji(position: str) -> str:
    return {"בעד": "🟢", "נגד": "🟡"}.get(position, "⚪")


def _linked_label(value) -> str:
    if isinstance(value, list) and value:
        return value[0]
    return "?"


# ── forward → Inbox ───────────────────────────────────────────

def _handle_forward(bot, msg, identity) -> None:
    text = msg.text or getattr(msg, "caption", "") or ""
    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"

    inbox_fields = {
        DecisionInboxFields.RAW_INPUT: text,
        DecisionInboxFields.CHANNEL: DecisionInboxChannel.TELEGRAM,
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    inbox_id = _decision_storage().add(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_id:
        bot.send_message(msg.chat.id, "⚠️ ההודעה המועברת לא נשמרה. בדוק logs.")
        return

    _suggest_decision_link(bot, msg.chat.id, inbox_id, text, identity)


def _suggest_decision_link(bot, chat_id, inbox_id: str, text: str, identity) -> None:
    """התאמה + הצעת שיוך — tail משותף בין _handle_forward ו-route_file_to_decision_inbox."""
    match, score = _find_matching_decision(text, identity)

    if match and score > 60:
        title = _record_fields(match).get(DecisionFields.TITLE, "")
        markup = _inbox_suggestion_keyboard(inbox_id, _record_id(match, required=True))
        bot.send_message(chat_id, f"נראה כמו «{title}» — לשייך?", reply_markup=markup)
        return

    open_decisions = _list_open_decisions(identity=identity)
    if not open_decisions:
        bot.send_message(chat_id, "📥 נשמר ב-Decision Inbox. אין החלטות פתוחות לשיוך כרגע.")
        return

    markup = _decision_pick_keyboard(inbox_id, open_decisions)
    bot.send_message(chat_id, "לאיזו החלטה זה שייך?", reply_markup=markup)


def _link_inbox_to_decision(bot, call, inbox_id: str, decision_id: str, identity) -> None:
    from decision_pipeline import run_pipeline

    decision_record = _at_get_record(Tables.DECISIONS, decision_id)
    inbox_record = _at_get_record(Tables.DECISION_INBOX, inbox_id)
    if (
        not decision_in_scope(decision_record, identity)
        or not _inbox_in_scope(inbox_record, identity)
        or not _inbox_callback_valid(inbox_record)
        or _record_fields(decision_record).get(DecisionFields.TENANT_ID)
        != _record_fields(inbox_record).get(DecisionInboxFields.TENANT_ID)
    ):
        _reject_callback(bot, call)
        return

    raw_text = _record_fields(inbox_record).get(DecisionInboxFields.RAW_INPUT, "") if inbox_record else ""

    event = {
        "raw_content": raw_text,
        "attachment": False,
        "Channel": DecisionEventChannel.TELEGRAM,
        "_decision_id": decision_id,
    }
    outcome = run_pipeline(event, _record_fields(decision_record))

    event_result = _create_decision_event(identity, decision_id, event)
    if not event_result.ok:
        bot.edit_message_text(
            "⚠️ השיוך לא הושלם במלואו; אירוע ההחלטה לא נשמר. אין זו הצלחה מלאה.",
            call.message.chat.id,
            call.message.message_id,
        )
        bot.answer_callback_query(call.id)
        return
    event_id = event_result.record_id

    patch_fields = {
        DecisionInboxFields.STATUS: DecisionInboxStatus.LINKED,
        DecisionInboxFields.SUGGESTED_DECISION: [decision_id],
    }
    patch_fields[DecisionInboxFields.LINKED_EVENT] = [event_id]
    _decision_storage().update(Tables.DECISION_INBOX, inbox_id, patch_fields, source="cmd_decision:inbox_link")

    title = _record_fields(decision_record).get(DecisionFields.TITLE, "")
    text = _format_pipeline_outcome(title, outcome, event)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ── /decision from-insight — תובנה (Learnings) → החלטה ───────────
# SPEC_Insight_to_Decision_to_Task.md §5 (PR1). אין כתיבה לפני ✅ על כרטיס אחד
# שמציג את השיוך המדויק; כתיבות דרך DecisionPorts בלבד; אידמפוטנטיות לפי סמן
# טקסטואלי קבוע ב-Airtable (לא לפי זיכרון תהליך). לא טוענים אידמפוטנטיות מלאה:
# ל-Airtable אין אילוץ ייחודיות, ולכן ההתכנסות היא דטרמיניסטית (canonical_record),
# לא מניעה מוחלטת של כפילות בין תהליכים.

_INSIGHT_STATE_LOCK = threading.Lock()   # claim אטומי של state לפני כתיבה
_INSIGHT_WRITE_LOCK = threading.Lock()   # gunicorn: workers=1, gthread → נעילה בתהליך אפקטיבית
_INSIGHT_PICK_LIMIT = 5
_INSIGHT_OPTION_LIMIT = 4

_STEP_LABELS = {
    "inbox": "Decision Inbox",
    "decision": "החלטה",
    "event": "אירוע ראיה",
    "link": "קישור Inbox↔החלטה↔אירוע",
}
_STEP_ICONS = {"ok": "✅", "reused": "♻️", "failed": "❌", "skipped": "⏳"}


@dataclass(frozen=True)
class InsightLinkResult:
    """תוצאת שיוך: צעד→(status, detail). complete רק אם כל ארבעת הצעדים ok/reused."""

    steps: tuple = ()
    decision_id: str | None = None
    inbox_id: str | None = None
    event_id: str | None = None

    @property
    def complete(self) -> bool:
        return len(self.steps) == len(_STEP_LABELS) and all(s[1] in ("ok", "reused") for s in self.steps)


def _insight_identity_ok(identity) -> bool:
    return bool(has_decision_capability(identity) and getattr(identity, "tenant_id", None) == HOME_TENANT_ID)


def _insight_plain_edit(bot, call, text: str, markup=None) -> None:
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as exc:  # הודעה שלא נערכה לעולם לא מסתירה תוצאת כתיבה
        logger.warning("[DecisionHub] from-insight edit_message failed (%s); sending a new message", exc)
        bot.send_message(call.message.chat.id, text, reply_markup=markup)


def _last_line_is_marker(text, marker: str) -> bool:
    """הסמן נכתב תמיד כשורה אחרונה; טקסט תובנה חופשי שמכיל סמן של תובנה אחרת אינו נחשב."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    return bool(lines) and lines[-1] == marker


def _insight_new_state(identity, candidates: list) -> dict:
    return {
        "command": "insight", "step": "insight_pick", "token": uuid.uuid4().hex[:12],
        "identity": identity, "created_at": _now_ts(), "candidates": candidates,
    }


def _claim_insight_state(uid: str, token: str, step: str, *, consume: bool) -> dict | None:
    """מחזיר state רק אם הטוקן והשלב תואמים; consume=True מוחק אטומית (claim יחיד)."""
    with _INSIGHT_STATE_LOCK:
        state = _get_valid_state(uid)
        if not state or state.get("command") != "insight" or state.get("token") != token or state.get("step") != step:
            return None
        if consume:
            _pending.pop(uid, None)
        return state


def _start_insight_flow(bot, msg, identity, hint: str, uid: str) -> None:
    if not _insight_identity_ok(identity):
        bot.send_message(msg.chat.id, "תובנות אינן זמינות עבור המשתמש/ה הזה.")
        return
    try:
        records = list_insights(identity, hint, limit=_INSIGHT_PICK_LIMIT)
    except AirtableReadError as exc:
        logger.warning("[DecisionHub] from-insight list failed: %s", exc.cause or exc)
        bot.send_message(msg.chat.id, "⚠️ לא ניתן לקרוא תובנות כרגע. לא נכתב דבר.")
        return
    views = [v for v in (build_insight_view(r) for r in records) if v]
    if not views:
        bot.send_message(msg.chat.id, "לא נמצאו תובנות מתאימות.")
        return
    state = _insight_new_state(identity, views)
    _pending[uid] = state
    bot.send_message(
        msg.chat.id,
        "📚 בחר תובנה לשיוך להחלטה (לא נכתב דבר עד אישור):",
        reply_markup=_insight_pick_keyboard(state["token"], views),
    )


def _insight_pick_keyboard(token: str, views: list):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    for i, view in enumerate(views):
        markup.add(InlineKeyboardButton(view.title[:48], callback_data=f"dec_ins_pick:{token}:{i}"))
    markup.add(InlineKeyboardButton("↩️ ביטול", callback_data=f"dec_ins_cancel:{token}"))
    return markup


def _insight_target_keyboard(token: str, options: list):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    for i, decision in enumerate(options):
        title = _record_fields(decision).get(DecisionFields.TITLE, "?")
        markup.add(InlineKeyboardButton(f"🔗 {title}"[:48], callback_data=f"dec_ins_target:{token}:{i}"))
    markup.add(InlineKeyboardButton("➕ החלטה חדשה", callback_data=f"dec_ins_target:{token}:new"))
    markup.add(InlineKeyboardButton("↩️ ביטול", callback_data=f"dec_ins_cancel:{token}"))
    return markup


def _insight_review_keyboard(token: str):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("✅ אשר שיוך", callback_data=f"dec_ins_confirm:{token}"),
        InlineKeyboardButton("✏️ שנה יעד", callback_data=f"dec_ins_retarget:{token}"),
        InlineKeyboardButton("↩️ ביטול", callback_data=f"dec_ins_cancel:{token}"),
    )
    return markup


def _find_insight_inboxes(insight_id: str, tenant_id: str) -> list:
    """חיפוש לפי סמן. מעלה AirtableReadError — כשל קריאה אינו 'לא נמצא' (מונע כפילות)."""
    marker = insight_marker(insight_id)
    rows = list_records(
        Tables.DECISION_INBOX,
        search_query_for_marker(DecisionInboxFields.RAW_INPUT, marker, tenant_id),
        limit=10, paginate=False, timeout=10,
    )
    return [r for r in rows if _last_line_is_marker(_record_fields(r).get(DecisionInboxFields.RAW_INPUT), marker)]


def _find_insight_events(insight_id: str, decision_id: str, tenant_id: str) -> list:
    marker = insight_marker(insight_id)
    rows = list_records(
        Tables.DECISION_EVENTS,
        search_query_for_marker(DecisionEventFields.RAW_CONTENT, marker, tenant_id),
        limit=10, paginate=False, timeout=10,
    )
    return [
        r for r in rows
        if decision_id in (_record_fields(r).get(DecisionEventFields.DECISION) or [])
        and _last_line_is_marker(_record_fields(r).get(DecisionEventFields.RAW_CONTENT), marker)
    ]


def _insight_target_options(identity, view, inbox: dict | None) -> list:
    """מועמדי יעד: שיוך חלקי קודם (אם יש) → התאמת כותרת → פתוחות. הכל בסקופ."""
    options: list = []
    seen: set = set()

    def add(decision):
        if decision and _decision_in_scope(decision, identity):
            did = _record_id(decision)
            if did and did not in seen and len(options) < _INSIGHT_OPTION_LIMIT:
                seen.add(did)
                options.append(decision)

    if inbox:
        for did in _record_fields(inbox).get(DecisionInboxFields.SUGGESTED_DECISION) or []:
            add(_at_get_record(Tables.DECISIONS, did))
    open_decisions = _list_open_decisions(limit=_INSIGHT_OPTION_LIMIT + 1, identity=identity)
    match, score = find_matching_decision(view.match_text, open_decisions, identity)
    if match and score > 60:
        add(match)
    for decision in open_decisions:
        add(decision)
    return options


def _insight_card(view, target_label: str) -> str:
    lines = ["🔗 שיוך תובנה להחלטה", "", f"תובנה: {view.title}"]
    if view.description:
        lines.append(excerpt(view))
    if view.next_action:
        lines.append(f"פעולה הבאה (מהתובנה): {view.next_action}")
    lines += ["", f"⟶ {target_label}", "", SOURCE_LABEL, "לא נכתב דבר עד אישור."]
    return "\n".join(lines)


def _insight_cb_common(bot, call, get_identity):
    """(identity, uid, token, parts) או None אחרי דחייה. אין כתיבה בנתיב זה."""
    identity = _callback_identity(get_identity, call)
    if not identity or not _insight_identity_ok(identity):
        _reject_callback(bot, call)
        return None
    parts = (call.data or "").split(":")
    if len(parts) < 2:
        _reject_callback(bot, call)
        return None
    return identity, str(call.from_user.id), parts[1], parts


def _insight_stale(bot, call) -> None:
    bot.answer_callback_query(call.id, "ℹ️ התהליך כבר אינו זמין.")


def _insight_cb_cancel(bot, call, get_identity) -> None:
    common = _insight_cb_common(bot, call, get_identity)
    if not common:
        return
    _, uid, token, _ = common
    with _INSIGHT_STATE_LOCK:
        state = _get_valid_state(uid)
        if not state or state.get("command") != "insight" or state.get("token") != token:
            _insight_stale(bot, call)
            return
        _pending.pop(uid, None)
    bot.answer_callback_query(call.id, "✅ התקבל")
    _insight_plain_edit(bot, call, "↩️ בוטל. לא נכתב דבר.")


def _insight_cb_pick(bot, call, get_identity) -> None:
    common = _insight_cb_common(bot, call, get_identity)
    if not common:
        return
    identity, uid, token, parts = common
    state = _claim_insight_state(uid, token, "insight_pick", consume=False)
    if not state or len(parts) != 3 or not parts[2].isdigit() or int(parts[2]) >= len(state["candidates"]):
        _insight_stale(bot, call)
        return
    chosen = state["candidates"][int(parts[2])]
    try:
        _, view = read_insight(chosen.record_id, identity)
        if view is None:
            _reject_callback(bot, call)
            return
        inboxes = _find_insight_inboxes(view.record_id, identity.tenant_id)
    except AirtableReadError as exc:
        logger.warning("[DecisionHub] from-insight pick read failed: %s", exc.cause or exc)
        _insight_plain_edit(bot, call, "⚠️ לא ניתן לאמת את התובנה/הכפילויות כרגע. לא נכתב דבר.")
        bot.answer_callback_query(call.id)
        return
    inbox = canonical_record(inboxes)
    if inbox:
        status = _record_fields(inbox).get(DecisionInboxFields.STATUS)
        linked = _record_fields(inbox).get(DecisionInboxFields.SUGGESTED_DECISION) or []
        if status == DecisionInboxStatus.REJECTED:
            _pending.pop(uid, None)
            _insight_plain_edit(bot, call, "התובנה סומנה בעבר כנדחית ב-Decision Inbox. לא נכתב דבר.")
            bot.answer_callback_query(call.id)
            return
        if status == DecisionInboxStatus.LINKED and linked:
            decision = _at_get_record(Tables.DECISIONS, linked[0])
            title = _record_fields(decision).get(DecisionFields.TITLE, linked[0]) if decision and _decision_in_scope(decision, identity) else linked[0]
            _pending.pop(uid, None)
            _insight_plain_edit(bot, call, f"התובנה כבר משויכת להחלטה: {title}\nלא נכתב דבר.")
            bot.answer_callback_query(call.id)
            return
    state.update({
        "step": "insight_target", "view": view, "partial_inbox": inbox,
        "options": _insight_target_options(identity, view, inbox),
    })
    state["token"] = uuid.uuid4().hex[:12]
    _pending[uid] = state
    note = "\n\n⚠️ נמצא שיוך חלקי קודם לתובנה זו — האישור ישלים את החסר." if inbox else ""
    _insight_plain_edit(
        bot, call, f"תובנה: {view.title}\n\nלאיזו החלטה לשייך?{note}",
        _insight_target_keyboard(state["token"], state["options"]),
    )
    bot.answer_callback_query(call.id)


def _insight_render_target(state) -> tuple[str, str]:
    view = state["view"]
    target = state["target"]
    if target["kind"] == "new":
        label = f"החלטה חדשה: «{view.title[:120]}» (דומיין: {view.decision_domain})"
    else:
        label = f"החלטה: «{_record_fields(target['decision']).get(DecisionFields.TITLE, '?')}»"
    return _insight_card(view, label), label


def _insight_cb_target(bot, call, get_identity) -> None:
    common = _insight_cb_common(bot, call, get_identity)
    if not common:
        return
    identity, uid, token, parts = common
    state = _claim_insight_state(uid, token, "insight_target", consume=False)
    if not state or len(parts) != 3:
        _insight_stale(bot, call)
        return
    choice = parts[2]
    if choice == "new":
        state["target"] = {"kind": "new"}
    elif choice.isdigit() and int(choice) < len(state["options"]):
        state["target"] = {"kind": "existing", "decision": state["options"][int(choice)]}
    else:
        _insight_stale(bot, call)
        return
    state["step"] = "insight_review"
    state["token"] = uuid.uuid4().hex[:12]
    _pending[uid] = state
    text, _ = _insight_render_target(state)
    _insight_plain_edit(bot, call, text, _insight_review_keyboard(state["token"]))
    bot.answer_callback_query(call.id)


def _insight_cb_retarget(bot, call, get_identity) -> None:
    common = _insight_cb_common(bot, call, get_identity)
    if not common:
        return
    identity, uid, token, _ = common
    state = _claim_insight_state(uid, token, "insight_review", consume=False)
    if not state:
        _insight_stale(bot, call)
        return
    state["step"] = "insight_target"
    state["token"] = uuid.uuid4().hex[:12]   # הטוקן הישן (כפתור ✅ קודם) מתבטל
    state.pop("target", None)
    _pending[uid] = state
    _insight_plain_edit(
        bot, call, f"תובנה: {state['view'].title}\n\nלאיזו החלטה לשייך?",
        _insight_target_keyboard(state["token"], state["options"]),
    )
    bot.answer_callback_query(call.id)


def _insight_cb_confirm(bot, call, get_identity) -> None:
    common = _insight_cb_common(bot, call, get_identity)
    if not common:
        return
    identity, uid, token, _ = common
    # claim אטומי: לחיצה שנייה/מקבילה מקבלת "אינו זמין" ולא כותבת
    state = _claim_insight_state(uid, token, "insight_review", consume=True)
    if not state:
        _insight_stale(bot, call)
        return
    view = state["view"]
    target = state["target"]
    try:
        _, fresh = read_insight(view.record_id, identity)
        if fresh is None:
            _insight_plain_edit(bot, call, "התובנה אינה נגישה עוד. לא נכתב דבר.")
            bot.answer_callback_query(call.id)
            return
        if fresh.fingerprint != view.fingerprint:
            _insight_plain_edit(bot, call, "התובנה שונתה מאז שהוצגה — האישור אינו תקף. הרץ שוב /decision from-insight. לא נכתב דבר.")
            bot.answer_callback_query(call.id)
            return
        if target["kind"] == "existing":
            decision = _at_get_record(Tables.DECISIONS, _record_id(target["decision"], required=True))
            open_ok = decision and _record_fields(decision).get(DecisionFields.STATUS) in (DecisionStatus.OPEN, DecisionStatus.PENDING_INPUT)
            if not decision or not _decision_in_scope(decision, identity) or not open_ok:
                _insight_plain_edit(bot, call, "ההחלטה אינה זמינה לשיוך (נעלמה/נסגרה/מחוץ להרשאה). לא נכתב דבר.")
                bot.answer_callback_query(call.id)
                return
            target = {"kind": "existing", "decision": decision}
    except AirtableReadError as exc:
        logger.warning("[DecisionHub] from-insight confirm re-read failed: %s", exc.cause or exc)
        _insight_plain_edit(bot, call, "⚠️ לא ניתן לאמת את הנתונים לפני כתיבה. לא נכתב דבר.")
        bot.answer_callback_query(call.id)
        return
    bot.answer_callback_query(call.id, "✅ התקבל")
    try:
        with _INSIGHT_WRITE_LOCK:
            result = _execute_insight_link(identity, fresh, target)
    except Exception:
        logger.exception("[DecisionHub] from-insight unexpected failure insight=%s", fresh.record_id)
        _insight_plain_edit(
            bot, call,
            "⚠️ אירעה שגיאה בלתי צפויה במהלך השיוך — ייתכן שנשמר חלק מהרשומות. "
            "הרץ שוב /decision from-insight ובחר את אותה תובנה (ימשיך מהחסר). לא נטען שהשיוך הושלם.",
        )
        return
    _insight_plain_edit(bot, call, _format_insight_result(fresh, result))


def _storage_add_outcome(storage, table: str, fields: dict, source: str):
    """(status, record_id|None). created | failed | outcome_unknown."""
    adder = getattr(storage, "add_with_outcome", None)
    if adder is None:
        record_id = storage.add(table, fields, source=source)
        return ("created", record_id) if record_id else ("failed", None)
    outcome = adder(table, fields, source=source)
    record = getattr(outcome, "record", None) or {}
    return getattr(outcome, "status", "failed"), record.get("id")


def _execute_insight_link(identity, view, target: dict) -> InsightLinkResult:
    """W1 Inbox → W2 החלטה → W3 אירוע → W4 קישור. כל צעד בודק קיום לפי סמן לפני כתיבה;
    כשל = עצירה עם דיווח מדויק; מה שנכתב נשאר (אין מחיקה). הרצה חוזרת ממשיכה מהחסר."""
    storage = _decision_storage()
    tenant = identity.tenant_id
    source_tag = f"cmd_decision:insight:{tenant}:{identity.user_id}"
    steps: list = []
    ids: dict = {"decision_id": None, "inbox_id": None, "event_id": None}

    def stop(name: str, detail: str) -> InsightLinkResult:
        steps.append((name, "failed", detail))
        for later in list(_STEP_LABELS)[len(steps):]:
            steps.append((later, "skipped", ""))
        return InsightLinkResult(tuple(steps), **ids)

    content = compose_event_content(view)

    # ── W1: Decision Inbox ─────────────────────────────────────
    try:
        inbox = canonical_record(_find_insight_inboxes(view.record_id, tenant))
    except AirtableReadError:
        return stop("inbox", "לא ניתן לבדוק כפילות לפני כתיבה")
    if inbox and _record_fields(inbox).get(DecisionInboxFields.STATUS) == DecisionInboxStatus.REJECTED:
        return stop("inbox", "התובנה סומנה בעבר כנדחית")
    if inbox:
        ids["inbox_id"] = _record_id(inbox)
        steps.append(("inbox", "reused", ""))
    else:
        fields = {
            DecisionInboxFields.RAW_INPUT: content,
            DecisionInboxFields.CHANNEL: DecisionInboxChannel.MANUAL,
            DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
            DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
            DecisionInboxFields.TENANT_ID: tenant,
        }
        status, record_id = _storage_add_outcome(storage, Tables.DECISION_INBOX, fields, source_tag)
        if status == "outcome_unknown":
            # אין retry עיוור: קודם בודקים אם הרשומה בכל זאת נכתבה
            try:
                found = canonical_record(_find_insight_inboxes(view.record_id, tenant))
            except AirtableReadError:
                found = None
            if found:
                status, record_id = "created", _record_id(found)
            else:
                status, record_id = _storage_add_outcome(storage, Tables.DECISION_INBOX, fields, source_tag)
        if status != "created" or not record_id:
            detail = "תוצאת הכתיבה לא ידועה — בדוק Decision Inbox לפני ניסיון נוסף" if status == "outcome_unknown" else "הכתיבה נכשלה"
            return stop("inbox", detail)
        ids["inbox_id"] = record_id
        steps.append(("inbox", "ok", ""))
        try:  # התכנסות: אם נוצרה כפילות במקביל — כולם בוחרים את אותה רשומה
            winner = canonical_record(_find_insight_inboxes(view.record_id, tenant))
            if winner and _record_id(winner) != record_id:
                logger.warning("[DecisionHub] from-insight duplicate Inbox detected; converging on %s", _record_id(winner))
                ids["inbox_id"] = _record_id(winner)
                inbox = winner
        except AirtableReadError:
            pass
    inbox_suggested = list(_record_fields(inbox).get(DecisionInboxFields.SUGGESTED_DECISION) or []) if inbox else []

    # ── W2: החלטה ──────────────────────────────────────────────
    if target["kind"] == "existing":
        decision_id = _record_id(target["decision"], required=True)
        if inbox_suggested and decision_id not in inbox_suggested:
            return stop("decision", "קיים שיוך חלקי קודם להחלטה אחרת — בחר בה או טפל ידנית")
        ids["decision_id"] = decision_id
        steps.append(("decision", "reused", ""))
    else:
        decision_id = None
        if inbox_suggested:
            prior = _at_get_record(Tables.DECISIONS, inbox_suggested[0])
            if not prior or not _decision_in_scope(prior, identity):
                return stop("decision", "לא ניתן לאמת את ההחלטה מהשיוך החלקי הקודם")
            decision_id = inbox_suggested[0]
            steps.append(("decision", "reused", ""))
        else:
            title = view.title[:120]
            try:
                same = list_records(
                    Tables.DECISIONS,
                    all_of(
                        equals(DecisionFields.TITLE, title), equals(DecisionFields.TENANT_ID, tenant),
                        any_of(equals(DecisionFields.STATUS, DecisionStatus.OPEN), equals(DecisionFields.STATUS, DecisionStatus.PENDING_INPUT)),
                    ),
                    limit=5, paginate=False, timeout=10,
                )
            except AirtableReadError:
                return stop("decision", "לא ניתן לבדוק החלטה קיימת בשם זהה")
            if any(_decision_in_scope(d, identity) for d in same):
                return stop("decision", "כבר קיימת החלטה פתוחה בשם זהה — בחר אותה כיעד במקום ליצור חדשה")
            created = _create_decision(identity, title, view.decision_domain, 0.0, [])
            if not created.ok or not created.record_id:
                return stop("decision", "יצירת ההחלטה נכשלה")
            decision_id = created.record_id
            steps.append(("decision", "ok", ""))
            if not storage.update(
                Tables.DECISION_INBOX, ids["inbox_id"],
                {DecisionInboxFields.SUGGESTED_DECISION: [decision_id]}, source=f"{source_tag}:pre_link",
            ):
                logger.warning("[DecisionHub] from-insight pre-link failed inbox=%s decision=%s", ids["inbox_id"], decision_id)
        ids["decision_id"] = decision_id

    # ── W3: Decision Event (ללא Trust Level — לא נספר כראיה מהותית ב-Readiness) ──
    try:
        event = canonical_record(_find_insight_events(view.record_id, decision_id, tenant))
    except AirtableReadError:
        return stop("event", "לא ניתן לבדוק כפילות אירוע לפני כתיבה")
    if event:
        ids["event_id"] = _record_id(event)
        steps.append(("event", "reused", ""))
    else:
        fields = {
            DecisionEventFields.DECISION: [decision_id],
            DecisionEventFields.EVENT_DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
            DecisionEventFields.CHANNEL: DecisionEventChannel.MANUAL,
            DecisionEventFields.RAW_CONTENT: content,
            DecisionEventFields.STATUS: DecisionEventStatus.LOGGED,
            DecisionEventFields.TENANT_ID: tenant,
        }
        status, record_id = _storage_add_outcome(storage, Tables.DECISION_EVENTS, fields, source_tag)
        if status == "outcome_unknown":
            try:
                found = canonical_record(_find_insight_events(view.record_id, decision_id, tenant))
            except AirtableReadError:
                found = None
            if found:
                status, record_id = "created", _record_id(found)
            else:
                status, record_id = _storage_add_outcome(storage, Tables.DECISION_EVENTS, fields, source_tag)
        if status != "created" or not record_id:
            detail = "תוצאת הכתיבה לא ידועה — בדוק Decision Events לפני ניסיון נוסף" if status == "outcome_unknown" else "הכתיבה נכשלה"
            return stop("event", detail)
        steps.append(("event", "ok", ""))
        ids["event_id"] = record_id
        try:
            winner = canonical_record(_find_insight_events(view.record_id, decision_id, tenant))
            if winner and _record_id(winner) != record_id:
                logger.warning("[DecisionHub] from-insight duplicate Event detected; converging on %s", _record_id(winner))
                ids["event_id"] = _record_id(winner)
        except AirtableReadError:
            pass

    # ── W4: קישור Inbox ↔ החלטה ↔ אירוע + אימות בקריאה חוזרת ──────
    patch = {
        DecisionInboxFields.STATUS: DecisionInboxStatus.LINKED,
        DecisionInboxFields.SUGGESTED_DECISION: [decision_id],
        DecisionInboxFields.LINKED_EVENT: [ids["event_id"]],
    }
    if not storage.update(Tables.DECISION_INBOX, ids["inbox_id"], patch, source=f"{source_tag}:link"):
        return stop("link", "עדכון ה-Inbox נכשל")
    verify = _at_get_record(Tables.DECISION_INBOX, ids["inbox_id"])
    vf = _record_fields(verify) if verify else {}
    if not (
        vf.get(DecisionInboxFields.STATUS) == DecisionInboxStatus.LINKED
        and decision_id in (vf.get(DecisionInboxFields.SUGGESTED_DECISION) or [])
        and ids["event_id"] in (vf.get(DecisionInboxFields.LINKED_EVENT) or [])
    ):
        return stop("link", "הקישור לא אומת בקריאה חוזרת")
    steps.append(("link", "ok", ""))
    return InsightLinkResult(tuple(steps), **ids)


def _format_insight_result(view, result: InsightLinkResult) -> str:
    lines = []
    for name, status, detail in result.steps:
        line = f"{_STEP_ICONS.get(status, '•')} {_STEP_LABELS[name]}"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    if result.complete:
        head = f"✅ התובנה «{view.title}» שויכה להחלטה.\n{SOURCE_LABEL}"
    else:
        head = (
            f"⚠️ השיוך של «{view.title}» לא הושלם. מה שנשמר נשאר.\n"
            "להשלמה: הרץ שוב /decision from-insight ובחר את אותה תובנה (ימשיך מהחסר)."
        )
    return head + "\n\n" + "\n".join(lines)


# ── Stage 0.5 — File/Voice Precedence Routing ──────────────────
# SPEC_File_Precedence_Fix.md — תיקון Drive↔Decision Inbox collision.
# Rule 9 (MODULE_RULES.md, Input Precedence): context ייעודי פעיל מנצח דיפולט;
# handler דיפולטי (Drive/Voice) ממשיך כרגיל כשאין context.

_DECISION_PREFIXES = ("החלטה:", "decision:")
_DECISION_KEYWORDS = ("inbox", "decision inbox", "אינבוקס", "decision table", "טבלת החלטות")


def session_has_active_decision(user_id: str) -> bool:
    """True אם למשתמש יש /decision session פעיל (לא expired)."""
    return _get_valid_state(str(user_id)) is not None


def decision_context_active(msg) -> bool:
    """
    קובע אם קובץ/הודעה שייכים ל-Decision Inbox ולא לזרימת ה-Drive/Voice
    הדיפולטית. 3 טריגרים (OR), לפי SPEC_File_Precedence_Fix.md:
      1. prefix מפורש: "החלטה:" / "decision:"
      2. /decision session פעיל למשתמש
      3. אזכור מפורש של inbox/decision table במילות מפתח
    """
    text = (getattr(msg, "text", None) or getattr(msg, "caption", None) or "").strip()
    text_lower = text.lower()

    if text_lower.startswith(tuple(p.lower() for p in _DECISION_PREFIXES)):
        return True

    user = getattr(msg, "from_user", None)
    user_id = str(getattr(user, "id", "")) if user else ""
    if user_id and session_has_active_decision(user_id):
        return True

    if any(kw in text_lower for kw in _DECISION_KEYWORDS):
        return True

    return False


def route_file_to_decision_inbox(
    bot, identity, chat_id,
    *,
    text: str = "",
    file_bytes: bytes | None = None,
    filename: str = "",
    mime_type: str = "",
    channel: str = DecisionInboxChannel.TELEGRAM,
) -> dict:
    """
    נקודת כניסה חדשה ל-Decision Inbox — קבצים/הודעות שנתפסו ע"י
    decision_context_active() לפני שהגיעו ל-Drive/Voice handler (Rule 9/10).
    Raw-first: שומר מיד, מאשר, רק אז מציע שיוך (_suggest_decision_link).
    Drive משמש כאן רק כ-URL backend — לא נכתב Media Files/AssetRecord.
    """
    attachment = []
    if file_bytes:
        try:
            from drive_adapter import upload_file, _get_upload_folder
            folder_id = _get_upload_folder(identity.domain_id)
            drive_file = upload_file(file_bytes, filename, mime_type, folder_id)
            if drive_file.ok:
                attachment = [{"url": drive_file.web_url, "filename": filename}]
        except Exception as e:
            logger.warning(f"[DecisionHub] route_file_to_decision_inbox drive upload failed: {e}")

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    inbox_fields = {
        DecisionInboxFields.RAW_INPUT: text,
        DecisionInboxFields.CHANNEL: channel,
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    if attachment:
        inbox_fields[DecisionInboxFields.ATTACHMENT] = attachment

    inbox_id = _decision_storage().add(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_id:
        bot.send_message(chat_id, "⚠️ הקובץ לא נשמר ב-Decision Inbox. בדוק logs.")
        return {"ok": False}

    bot.send_message(chat_id, "📥 נשמר ב-Decision Inbox.")

    if attachment:
        try:
            from session_store import lead_sessions, FileUploadResult
            lead_sessions.set_last_file(
                identity.user_id,
                FileUploadResult(
                    type="inbox_file",
                    url=attachment[0]["url"],
                    file_id=inbox_id,
                    original_filename=filename,
                    timestamp=datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
                    conversation_id=str(chat_id),
                ),
                domain=identity.domain_id,
                channel="telegram",
            )
        except Exception as e:
            logger.warning(f"[DecisionHub] set_last_file failed: {e}")

    _suggest_decision_link(bot, chat_id, inbox_id, text, identity)

    return {
        "ok": True,
        "inbox_id": inbox_id,
        "attachment_url": attachment[0]["url"] if attachment else "",
    }


# ── Stage 0.6 — "זה הנספח" attachment reference ────────────────
# SPEC_File_Context_Reference.md — מקשר את הקובץ האחרון שהועלה
# (FileUploadResult, session_store.lead_sessions) להחלטה.
# Rule 10 (MODULE_RULES.md): שאלת שיוך אחת בלבד, לא חקירה.

_ATTACHMENT_REFERENCE_PHRASES = ("זה הנספח", "זה הקובץ", "this is the attachment", "this is the file")


def is_attachment_reference(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(p.lower() in t for p in _ATTACHMENT_REFERENCE_PHRASES)


def handle_attachment_reference(bot, identity, chat_id, text: str) -> bool:
    """
    מטפל ב"זה הנספח" — שולף את FileUploadResult האחרון (set_last_file)
    ומציע שיוך להחלטה. אם הקובץ עדיין לא ב-Decision Inbox (העלה ל-Drive
    ישירות) — נוצרת רשומה raw-first מה-URL הקיים, בלי להעלות שוב.
    מחזיר True אם הטופל (כולל "לא נמצא קובץ"), False אם לא רלוונטי.
    """
    from session_store import lead_sessions, FileUploadResult

    last_file = lead_sessions.get_last_file(identity.user_id)
    if not last_file:
        bot.send_message(chat_id, "לא מצאתי קובץ שהועלה לאחרונה.")
        return True

    if last_file.get("type") == "inbox_file" and last_file.get("file_id"):
        _suggest_decision_link(bot, chat_id, last_file["file_id"], text, identity)
        return True

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    filename = last_file.get("original_filename", "")
    inbox_fields = {
        DecisionInboxFields.RAW_INPUT: filename,
        DecisionInboxFields.CHANNEL: DecisionInboxChannel.TELEGRAM,
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    if last_file.get("url"):
        inbox_fields[DecisionInboxFields.ATTACHMENT] = [{"url": last_file["url"], "filename": filename}]

    inbox_id = _decision_storage().add(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_id:
        bot.send_message(chat_id, "⚠️ לא הצלחתי לשמור את הקובץ ל-Decision Inbox.")
        return True

    lead_sessions.set_last_file(
        identity.user_id,
        FileUploadResult(
            type="inbox_file",
            url=last_file.get("url", ""),
            file_id=inbox_id,
            original_filename=filename,
            timestamp=datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
            conversation_id=str(chat_id),
        ),
        domain=identity.domain_id,
        channel="telegram",
    )
    _suggest_decision_link(bot, chat_id, inbox_id, filename, identity)
    return True


# ── Matching helpers ──────────────────────────────────────────

def _find_matching_decision(text: str, identity=None) -> tuple[dict | None, float]:
    """Compatibility wrapper for existing command-layer callers."""
    return find_matching_decision(text, identity=identity)


# ── Airtable read helpers (cmd layer — direct, not through ports) ──

def _at_list(table: str, formula: str = "") -> list:
    try:
        return list_records(table, formula, max_records=None, paginate=False, timeout=10)
    except AirtableReadError as exc:
        if exc.status_code is not None:
            logger.warning(f"[DecisionHub] _at_list({table}) -> {exc.status_code}")
        else:
            logger.warning(f"[DecisionHub] _at_list({table}) error: {exc.cause or exc}")
    except Exception as e:
        logger.warning(f"[DecisionHub] _at_list({table}) error: {e}")
    return []


def _at_get_record(table: str, record_id: str) -> dict | None:
    try:
        return get_record(table, record_id, timeout=10)
    except AirtableReadError as exc:
        if exc.status_code is not None:
            logger.warning(f"[DecisionHub] _at_get_record({table}/{record_id}) -> {exc.status_code}")
        else:
            logger.warning(f"[DecisionHub] _at_get_record({table}/{record_id}) error: {exc.cause or exc}")
    except Exception as e:
        logger.warning(f"[DecisionHub] _at_get_record({table}/{record_id}) error: {e}")
    return None


def _decision_in_scope(decision: dict, identity) -> bool:
    """Enforce tenant and record/domain scope after capability authorization."""
    return decision_in_scope(decision, identity)


def _resolve_decision_ref(ref: str, identity=None) -> dict | None:
    ref = ref.strip()
    if ref.startswith("rec"):
        record = _at_get_record(Tables.DECISIONS, ref)
        if record and (identity is None or _decision_in_scope(record, identity)):
            return record

    query = contains(DecisionFields.TITLE, ref, case_sensitive=True)
    if identity is not None:
        query = all_of(query, equals(DecisionFields.TENANT_ID, identity.tenant_id))
    matches = _at_list(Tables.DECISIONS, query)
    for match in matches:
        if identity is None or _decision_in_scope(match, identity):
            return match
    return None


def _list_open_decisions(limit: int = 5, identity=None) -> list:
    """Compatibility wrapper for existing command-layer callers."""
    return list_open_decisions(limit, identity=identity)


def _list_stakeholders(decision_id: str, identity=None) -> list:
    parent = _at_get_record(Tables.DECISIONS, decision_id) if identity is not None else None
    if not decision_in_scope(parent, identity):
        return []
    return _at_list(
        Tables.DECISION_STAKEHOLDERS,
        all_of(array_contains(DecisionStakeholderFields.DECISION, decision_id), equals(DecisionStakeholderFields.TENANT_ID, identity.tenant_id)),
    )


def _latest_event(decision_id: str, events: list | None = None) -> dict | None:
    events = events if events is not None else _list_decision_events(decision_id)
    if not events:
        return None
    events.sort(key=lambda e: _record_fields(e).get(DecisionEventFields.EVENT_DATE, ""), reverse=True)
    return events[0]


def _list_decision_events(decision_id: str, identity=None) -> list:
    parent = _at_get_record(Tables.DECISIONS, decision_id) if identity is not None else None
    if not decision_in_scope(parent, identity):
        return []
    return _at_list(
        Tables.DECISION_EVENTS,
        all_of(array_contains(DecisionEventFields.DECISION, decision_id), equals(DecisionEventFields.TENANT_ID, identity.tenant_id)),
    )


# ── פונקציות עזר כלליות ──────────────────────────────────────────

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


def _parse_number(text: str) -> float:
    digits = re.sub(r"[^\d.]", "", text or "")
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def _parse_names(text: str) -> list[str]:
    parts = re.split(r",|\sו\s", text or "")
    return [p.strip() for p in parts if p.strip()]


def _domain_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    domains = [DecisionDomain.REAL_ESTATE, DecisionDomain.IMPORT, DecisionDomain.RECRUITMENT,
               DecisionDomain.PARTNERSHIP, DecisionDomain.GENERAL]
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[InlineKeyboardButton(d, callback_data=f"dec_domain:{d}") for d in domains])
    return markup


def _inbox_suggestion_keyboard(inbox_id: str, decision_id: str):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("✓ שייך", callback_data=f"dec_inbox_link:{inbox_id}:{decision_id}"),
        InlineKeyboardButton("בחר אחר", callback_data=f"dec_inbox_pick:{inbox_id}"),
        InlineKeyboardButton("התעלם", callback_data=f"dec_inbox_ignore:{inbox_id}"),
    )
    return markup


def _decision_pick_keyboard(inbox_id: str, decisions: list):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    for d in decisions:
        title = _record_fields(d).get(DecisionFields.TITLE, "?")
        markup.add(InlineKeyboardButton(title, callback_data=f"dec_inbox_pick_choice:{inbox_id}:{_record_id(d, required=True)}"))
    markup.add(InlineKeyboardButton("התעלם", callback_data=f"dec_inbox_ignore:{inbox_id}"))
    return markup
