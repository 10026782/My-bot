# cmd_decision.py — Decision Hub (Stage 0) Telegram Commands
# /decision new|update|status + forward→Inbox
# Feature flag: FEATURE_DECISION_HUB (כבוי ברירת מחדל)
#
# BOSS never deletes signal. BOSS only down-ranks it.
# כל קלט נשמר גולמי לפני עיבוד — אף פעם לא נמחק.

import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from airtable_schema import (
    Tables,
    DecisionFields, DecisionDomain, DecisionStatus,
    DecisionEventFields, DecisionEventChannel, DecisionEventStatus,
    DecisionStakeholderFields, DecisionStakeholderRole, DecisionStakeholderPosition,
    DecisionInboxFields, DecisionInboxChannel, DecisionInboxStatus,
)
from decision_matching import find_matching_decision, list_open_decisions

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 30 * 60  # 30 דקות
_ALLOWED_ROLES = ("owner", "manager", "partner")

# ── State store — key: telegram user_id (str) ───────────────────
_pending: dict[str, dict] = {}


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
            _pending[uid] = {"command": "new", "step": "title", "identity": identity, "created_at": _now_ts()}
            bot.send_message(msg.chat.id, "📋 *החלטה חדשה*\n\nשם ההחלטה?", parse_mode="Markdown")

        elif sub == "update":
            if not arg:
                bot.send_message(msg.chat.id, "שימוש: `/decision update <decision_id>`", parse_mode="Markdown")
                return
            decision = _resolve_decision_ref(arg)
            if not decision:
                bot.send_message(msg.chat.id, f"❌ לא נמצאה החלטה תואמת ל-'{arg}'.")
                return
            _pending[uid] = {
                "command": "update", "step": "text",
                "decision": decision, "identity": identity, "created_at": _now_ts(),
            }
            title = decision["fields"].get(DecisionFields.TITLE, "")
            bot.send_message(msg.chat.id, f"📋 *{title}*\n\n✍️ מה קרה?", parse_mode="Markdown")

        elif sub == "status":
            if not arg:
                bot.send_message(msg.chat.id, "שימוש: `/decision status <decision_id>`", parse_mode="Markdown")
                return
            decision = _resolve_decision_ref(arg)
            if not decision:
                bot.send_message(msg.chat.id, f"❌ לא נמצאה החלטה תואמת ל-'{arg}'.")
                return
            bot.send_message(msg.chat.id, _format_decision_card(decision), parse_mode="Markdown")

        else:
            bot.send_message(
                msg.chat.id,
                "שימוש:\n`/decision new`\n`/decision update <id>`\n`/decision status <id>`",
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
        if not state or state.get("step") != "domain":
            bot.answer_callback_query(call.id, "פג תוקף — נסה /decision new מחדש.")
            return

        state["domain"] = call.data.split(":", 1)[1]
        state["step"] = "exposure"
        _pending[uid] = state

        bot.edit_message_text(
            f"✅ דומיין: *{state['domain']}*\n\n💰 חשיפה כספית משוערת? (מספר)",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown",
        )
        bot.answer_callback_query(call.id)

    # ── inline: forward→Inbox — שיוך מוצע / נבחר ────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_link:"))
    def cb_inbox_link(call):
        _, inbox_id, decision_id = call.data.split(":", 2)
        _link_inbox_to_decision(bot, call, inbox_id, decision_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_pick_choice:"))
    def cb_inbox_pick_choice(call):
        _, inbox_id, decision_id = call.data.split(":", 2)
        _link_inbox_to_decision(bot, call, inbox_id, decision_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dec_inbox_pick:"))
    def cb_inbox_pick(call):
        inbox_id = call.data.split(":", 1)[1]
        open_decisions = _list_open_decisions()
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
        inbox_id = call.data.split(":", 1)[1]
        from tools.airtable_gateway import airtable_patch
        airtable_patch(
            Tables.DECISION_INBOX, inbox_id,
            {DecisionInboxFields.STATUS: DecisionInboxStatus.REJECTED},
            source="cmd_decision:inbox_ignore",
        )
        bot.edit_message_text(
            "🗑 התעלמתי. נשאר ב-Decision Inbox לעיון מאוחר יותר.",
            call.message.chat.id, call.message.message_id,
        )
        bot.answer_callback_query(call.id)

    # ── לכידת טקסט חופשי (new/update flows) ──────────────────────
    @bot.message_handler(
        func=lambda m: (
            _pending.get(str(m.from_user.id), {}).get("step") in ("title", "exposure", "stakeholders", "text")
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

def _handle_new_step(bot, msg, state):
    if state["step"] == "title":
        state["title"] = msg.text.strip()
        state["step"] = "domain"
        _pending[str(msg.from_user.id)] = state
        bot.send_message(msg.chat.id, "דומיין?", reply_markup=_domain_keyboard())
        return

    if state["step"] == "exposure":
        state["exposure"] = _parse_number(msg.text)
        state["step"] = "stakeholders"
        _pending[str(msg.from_user.id)] = state
        bot.send_message(msg.chat.id, "👥 מי הצדדים? (שמות, מופרדים בפסיק)")
        return

    if state["step"] == "stakeholders":
        names = _parse_names(msg.text)
        _pending.pop(str(msg.from_user.id), None)
        identity = state["identity"]
        record = _create_decision(identity, state["title"], state.get("domain", DecisionDomain.GENERAL), state.get("exposure", 0), names)
        if record:
            bot.send_message(
                msg.chat.id,
                f"✅ *{state['title']}* נוצרה.\n🆔 `{record['id']}`",
                parse_mode="Markdown",
            )
        else:
            bot.send_message(msg.chat.id, "⚠️ ההחלטה לא נשמרה. בדוק logs.")
        return


def _create_decision(identity, title: str, domain: str, exposure: float, stakeholder_names: list[str]) -> dict | None:
    from tools.airtable_gateway import airtable_create

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    fields = {
        DecisionFields.TITLE: title,
        DecisionFields.DOMAIN: domain,
        DecisionFields.ESTIMATED_EXPOSURE: exposure,
        DecisionFields.STATUS: DecisionStatus.OPEN,
        DecisionFields.TENANT_ID: identity.tenant_id,
    }
    record = airtable_create(Tables.DECISIONS, fields, source=source_tag)
    if not record:
        logger.warning(f"[DecisionHub] _create_decision failed source={source_tag}")
        return None

    for name in stakeholder_names:
        _create_stakeholder(identity, record["id"], name)

    return record


def _create_stakeholder(identity, decision_id: str, name: str) -> None:
    from tools.airtable_gateway import airtable_create
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

    airtable_create(Tables.DECISION_STAKEHOLDERS, fields, source=source_tag)


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
        "_decision_id": decision["id"],
    }

    from decision_pipeline import run_pipeline
    outcome = run_pipeline(event, decision["fields"])

    event_id = _create_decision_event(identity, decision["id"], event)
    text = _format_pipeline_outcome(decision["fields"].get(DecisionFields.TITLE, ""), outcome, event)
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    if event_id:
        logger.info(f"[DecisionHub] event created id={event_id} halted_at={outcome['halted_at']}")


def _create_decision_event(identity, decision_id: str, event: dict) -> str | None:
    from tools.airtable_gateway import airtable_create

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    fields = {
        DecisionEventFields.DECISION: [decision_id],
        DecisionEventFields.EVENT_DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        DecisionEventFields.CHANNEL: event.get("Channel", DecisionEventChannel.TELEGRAM),
        DecisionEventFields.RAW_CONTENT: event.get("raw_content", ""),
        DecisionEventFields.DELTA_TYPE: event.get("Delta Type", ""),
        DecisionEventFields.STATUS: event.get("Status", DecisionEventStatus.LOGGED),
        DecisionEventFields.TENANT_ID: identity.tenant_id,
    }
    _add_trust_fields(fields, event)
    record = airtable_create(Tables.DECISION_EVENTS, fields, source=source_tag)
    return record.get("id") if record else None


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


def _format_pipeline_outcome(title: str, outcome: dict, event: dict) -> str:
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

def _format_decision_card(decision: dict) -> str:
    f = decision["fields"]
    title = f.get(DecisionFields.TITLE, "")
    draft = f.get(DecisionFields.CURRENT_DRAFT, "")
    exposure = f.get(DecisionFields.ESTIMATED_EXPOSURE, "")
    urgency = f.get(DecisionFields.URGENCY, "")
    risk_yes = f.get(DecisionFields.RISK_IF_YES, "")
    risk_no = f.get(DecisionFields.RISK_IF_NO, "")
    missing = f.get(DecisionFields.MISSING_INFO, "")

    stakeholders = _list_stakeholders(decision["id"])
    stakeholder_lines = "\n".join(
        f"  {_position_emoji(s['fields'].get(DecisionStakeholderFields.POSITION))} "
        f"{_linked_label(s['fields'].get(DecisionStakeholderFields.CONTACT))} — "
        f"{s['fields'].get(DecisionStakeholderFields.POSITION, '')}"
        for s in stakeholders
    ) or "  (אין)"

    events = _list_decision_events(decision["id"])
    latest = _latest_event(decision["id"], events)
    latest_summary = latest["fields"].get(DecisionEventFields.AI_SUMMARY, "") if latest else "(אין)"
    attention_summary = ""
    try:
        from decision_attention import build_attention_summary, calc_priority

        attention = calc_priority(decision, events)
        attention_summary = build_attention_summary(attention)
    except Exception as e:
        logger.warning(f"[DecisionHub] attention summary failed: {e}")

    attention_block = f"\n\nAttention:\n{attention_summary}" if attention_summary else ""

    confidence_block, confidence_result = _format_confidence_block(decision, events)
    readiness_block = _format_readiness_block(decision, events, confidence_result)

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
    )


def _format_confidence_block(decision: dict, events: list) -> tuple:
    """Stage 2 (F17) — Smart Trust Layer: confidence/evidence/missing-evidence
    על ההחלטה כולה, מחושב מ-Events מקושרים. AI Conflict Detection רץ כאן בלבד
    (פתיחת כרטיס /decision status) — lazy + cached, לעולם לא ב-ingest.
    מחזיר (טקסט_להצגה, ConfidenceResult) — ה-ConfidenceResult נדרש ל-Stage 3
    (decision_readiness.py) כדי שלא יחושב פעמיים (כולל AI Conflict Detection)."""
    from decision_confidence import calc_confidence, detect_missing_evidence, build_evidence_summary

    domain = decision["fields"].get(DecisionFields.DOMAIN, "")
    result = calc_confidence(events)
    missing_evidence = detect_missing_evidence(domain, events)
    evidence_summary = build_evidence_summary(events)

    _persist_confidence(decision["id"], result, missing_evidence, evidence_summary)

    pct = int(result.score * 100)
    lines = [f"📊 ביטחון בהחלטה: {pct}%", f"📎 ראיות: {evidence_summary}"]
    if result.conflicting:
        lines.append(f"⚡ קונפליקטים פתוחים: {len(result.conflicting)}")
    if missing_evidence:
        lines.append("⚠️ חסר לפני החלטה:\n" + "\n".join(f"  • {item}" for item in missing_evidence))
    return "\n".join(lines), result


def _format_readiness_block(decision: dict, events: list, confidence_result) -> str:
    """Stage 3 — Readiness Engine: האם ההחלטה מוכנה להכרעה אנושית. READY הוא
    איתות בלבד — לא מבצע שום פעולה."""
    from decision_readiness import calc_readiness, build_readiness_message

    result = calc_readiness(decision, events, confidence_result)
    _persist_readiness(decision["id"], result)
    return build_readiness_message(result)


def _persist_confidence(decision_id: str, result, missing_evidence: list, evidence_summary: str) -> None:
    """כתיבה best-effort — לא חוסם את הצגת הכרטיס. עד שהשדות נוצרים ידנית
    ב-Airtable (Stage 2 SPEC §Schema), airtable_patch ישמיט אותם בשקט."""
    import json
    from tools.airtable_gateway import airtable_patch

    fields = {
        DecisionFields.CONFIDENCE_SCORE: result.score,
        DecisionFields.EVIDENCE_SUMMARY: evidence_summary,
        DecisionFields.EVIDENCE_IDS: json.dumps(result.supporting + result.conflicting),
        DecisionFields.MISSING_EVIDENCE: json.dumps(missing_evidence),
    }
    try:
        airtable_patch(Tables.DECISIONS, decision_id, fields, source="decision_confidence:stage2")
    except Exception as e:
        logger.warning(f"[DecisionHub] _persist_confidence failed: {e}")


def _persist_readiness(decision_id: str, result) -> None:
    """כתיבה best-effort — לא חוסם את הצגת הכרטיס. כותב רק לשדה Readiness
    הקיים כבר ב-DecisionFields (Stage 3 SPEC: אין שינוי סכמה ל-MVP — Score/
    Message/Escalation מוצגים רק ב-Telegram, לא נשמרים, עד אישור נפרד)."""
    from tools.airtable_gateway import airtable_patch

    try:
        airtable_patch(
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
    from tools.airtable_gateway import airtable_create

    text = msg.text or getattr(msg, "caption", "") or ""
    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"

    inbox_fields = {
        DecisionInboxFields.RAW_INPUT: text,
        DecisionInboxFields.CHANNEL: DecisionInboxChannel.TELEGRAM,
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    inbox_record = airtable_create(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_record:
        bot.send_message(msg.chat.id, "⚠️ ההודעה המועברת לא נשמרה. בדוק logs.")
        return

    inbox_id = inbox_record["id"]
    _suggest_decision_link(bot, msg.chat.id, inbox_id, text)


def _suggest_decision_link(bot, chat_id, inbox_id: str, text: str) -> None:
    """התאמה + הצעת שיוך — tail משותף בין _handle_forward ו-route_file_to_decision_inbox."""
    match, score = _find_matching_decision(text)

    if match and score > 60:
        title = match["fields"].get(DecisionFields.TITLE, "")
        markup = _inbox_suggestion_keyboard(inbox_id, match["id"])
        bot.send_message(chat_id, f"נראה כמו «{title}» — לשייך?", reply_markup=markup)
        return

    open_decisions = _list_open_decisions()
    if not open_decisions:
        bot.send_message(chat_id, "📥 נשמר ב-Decision Inbox. אין החלטות פתוחות לשיוך כרגע.")
        return

    markup = _decision_pick_keyboard(inbox_id, open_decisions)
    bot.send_message(chat_id, "לאיזו החלטה זה שייך?", reply_markup=markup)


def _link_inbox_to_decision(bot, call, inbox_id: str, decision_id: str) -> None:
    from tools.airtable_gateway import airtable_patch, airtable_create
    from decision_pipeline import run_pipeline

    decision_record = _at_get_record(Tables.DECISIONS, decision_id)
    if not decision_record:
        bot.answer_callback_query(call.id, "❌ ההחלטה לא נמצאה.")
        return

    inbox_record = _at_get_record(Tables.DECISION_INBOX, inbox_id)
    raw_text = inbox_record["fields"].get(DecisionInboxFields.RAW_INPUT, "") if inbox_record else ""

    event = {
        "raw_content": raw_text,
        "attachment": False,
        "Channel": DecisionEventChannel.TELEGRAM,
        "_decision_id": decision_id,
    }
    outcome = run_pipeline(event, decision_record["fields"])

    event_fields = {
        DecisionEventFields.DECISION: [decision_id],
        DecisionEventFields.EVENT_DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        DecisionEventFields.CHANNEL: event.get("Channel", DecisionEventChannel.TELEGRAM),
        DecisionEventFields.RAW_CONTENT: raw_text,
        DecisionEventFields.DELTA_TYPE: event.get("Delta Type", ""),
        DecisionEventFields.STATUS: event.get("Status", DecisionEventStatus.LOGGED),
    }
    _add_trust_fields(event_fields, event)
    event_record = airtable_create(Tables.DECISION_EVENTS, event_fields, source="cmd_decision:inbox_link")
    event_id = event_record.get("id") if event_record else None

    patch_fields = {
        DecisionInboxFields.STATUS: DecisionInboxStatus.LINKED,
        DecisionInboxFields.SUGGESTED_DECISION: [decision_id],
    }
    if event_id:
        patch_fields[DecisionInboxFields.LINKED_EVENT] = [event_id]
    airtable_patch(Tables.DECISION_INBOX, inbox_id, patch_fields, source="cmd_decision:inbox_link")

    title = decision_record["fields"].get(DecisionFields.TITLE, "")
    text = _format_pipeline_outcome(title, outcome, event)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


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
    from tools.airtable_gateway import airtable_create

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
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    if attachment:
        inbox_fields[DecisionInboxFields.ATTACHMENT] = attachment

    inbox_record = airtable_create(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_record:
        bot.send_message(chat_id, "⚠️ הקובץ לא נשמר ב-Decision Inbox. בדוק logs.")
        return {"ok": False}

    inbox_id = inbox_record["id"]
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

    _suggest_decision_link(bot, chat_id, inbox_id, text)

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
        _suggest_decision_link(bot, chat_id, last_file["file_id"], text)
        return True

    from tools.airtable_gateway import airtable_create

    source_tag = f"cmd_decision:{identity.tenant_id}:{identity.user_id}"
    filename = last_file.get("original_filename", "")
    inbox_fields = {
        DecisionInboxFields.RAW_INPUT: filename,
        DecisionInboxFields.CHANNEL: DecisionInboxChannel.TELEGRAM,
        DecisionInboxFields.RECEIVED: datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: identity.tenant_id,
    }
    if last_file.get("url"):
        inbox_fields[DecisionInboxFields.ATTACHMENT] = [{"url": last_file["url"], "filename": filename}]

    inbox_record = airtable_create(Tables.DECISION_INBOX, inbox_fields, source=source_tag)
    if not inbox_record:
        bot.send_message(chat_id, "⚠️ לא הצלחתי לשמור את הקובץ ל-Decision Inbox.")
        return True

    inbox_id = inbox_record["id"]
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
    _suggest_decision_link(bot, chat_id, inbox_id, filename)
    return True


# ── Matching helpers ──────────────────────────────────────────

def _find_matching_decision(text: str) -> tuple[dict | None, float]:
    """Compatibility wrapper for existing command-layer callers."""
    return find_matching_decision(text)


# ── Airtable read helpers (cmd layer — direct, not through ports) ──

def _at_list(table: str, formula: str = "") -> list:
    try:
        import httpx
        from tools.airtable_gateway import _at_url, _at_headers

        params: dict = {}
        if formula:
            params["filterByFormula"] = formula
        r = httpx.get(_at_url(table), headers=_at_headers(), params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("records", [])
        logger.warning(f"[DecisionHub] _at_list({table}) -> {r.status_code}")
    except Exception as e:
        logger.warning(f"[DecisionHub] _at_list({table}) error: {e}")
    return []


def _at_get_record(table: str, record_id: str) -> dict | None:
    try:
        import httpx
        from tools.airtable_gateway import _at_url, _at_headers

        r = httpx.get(f"{_at_url(table)}/{record_id}", headers=_at_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"[DecisionHub] _at_get_record({table}/{record_id}) -> {r.status_code}")
    except Exception as e:
        logger.warning(f"[DecisionHub] _at_get_record({table}/{record_id}) error: {e}")
    return None


def _resolve_decision_ref(ref: str) -> dict | None:
    ref = ref.strip()
    if ref.startswith("rec"):
        record = _at_get_record(Tables.DECISIONS, ref)
        if record:
            return record

    formula = f"FIND('{ref}', {{{DecisionFields.TITLE}}})"
    matches = _at_list(Tables.DECISIONS, formula)
    return matches[0] if matches else None


def _list_open_decisions(limit: int = 5) -> list:
    """Compatibility wrapper for existing command-layer callers."""
    return list_open_decisions(limit)


def _list_stakeholders(decision_id: str) -> list:
    formula = f"FIND('{decision_id}', ARRAYJOIN({{{DecisionStakeholderFields.DECISION}}}))"
    return _at_list(Tables.DECISION_STAKEHOLDERS, formula)


def _latest_event(decision_id: str, events: list | None = None) -> dict | None:
    events = events if events is not None else _list_decision_events(decision_id)
    if not events:
        return None
    events.sort(key=lambda e: e["fields"].get(DecisionEventFields.EVENT_DATE, ""), reverse=True)
    return events[0]


def _list_decision_events(decision_id: str) -> list:
    formula = f"FIND('{decision_id}', ARRAYJOIN({{{DecisionEventFields.DECISION}}}))"
    return _at_list(Tables.DECISION_EVENTS, formula)


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
        title = d["fields"].get(DecisionFields.TITLE, "?")
        markup.add(InlineKeyboardButton(title, callback_data=f"dec_inbox_pick_choice:{inbox_id}:{d['id']}"))
    markup.add(InlineKeyboardButton("התעלם", callback_data=f"dec_inbox_ignore:{inbox_id}"))
    return markup
