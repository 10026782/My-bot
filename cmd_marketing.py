# cmd_marketing.py — F23 BOSS Marketing Bridge (M1)
# /marketing_new — wizard: Domain -> Demand Type -> Target Audience -> Location
# -> Goal -> Constraints -> creates the Demand, composes a brief, makes one AI
# call for 3 ideas, then presents them as buttons to tap.
# Feature flag: FEATURE_MARKETING_BRIDGE (default OFF)
#
# No Airtable record ID is ever typed by the user or shown as visible text —
# this codebase has a locked UX principle for exactly this
# (decision.ux_no_internal_ids: "Technical identifiers remain in logs and
# audit evidence, never in user text", docs/architecture/f52-unified-approval-
# runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md). Record IDs travel only inside
# Telegram's invisible callback_data payloads.
#
# Per the M1 spec's Canonical Reuse Gate: this is a direct, human-triggered
# command handler (same shape as cmd_update.py/cmd_decision.py) — not an
# agent-invoked dispatcher tool, no tool_registry/ActionGateway involvement,
# because the human running the wizard IS the authorization. Listing/query
# commands (list demands, next action, etc.) remain M2 scope, not built here.

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_ALLOWED_ROLES = ("owner", "manager", "partner")
_STATE_TTL_SECONDS = 30 * 60  # 30 דקות, כמו cmd_update.py

DOMAINS = [
    ("נדל\"ן", "real_estate"),
    ("ייבוא",   "import"),
    ("מדיה",    "media"),
    ("SaaS",    "saas"),
    ("כספים",  "finance"),
    ("גיוס",    "recruitment"),
    ("כללי",   "general"),
]

DEMAND_TYPES = [
    ("גיוס / דרושים",          "recruitment"),
    ("ייבוא רהיטים",           "furniture_import"),
    ("ציוד סיבים אופטיים",     "fiber_equipment"),
    ("נדל\"ן — מודעת נכס",     "real_estate_listing"),
    ("עסק שירותים",            "service"),
]

# ── State store — key: telegram user_id (str) ───────────────────
_pending: dict[str, dict] = {}

_FREE_TEXT_STEPS = ("target_audience", "location", "goal", "constraints")


# ── Registration ─────────────────────────────────────────────────

def register_marketing_command(bot, get_identity):
    """נקרא מ-app.py פעם אחת ב-startup."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_MARKETING_BRIDGE"):
            logger.info("[F23] FEATURE_MARKETING_BRIDGE=off — /marketing_new not registered")
            return
    except ImportError as e:
        # dev mode — feature_flags module unavailable (e.g. isolated unit test),
        # not a real production path. Matches cmd_update.py's existing behavior.
        logger.warning("[F23] feature_flags unavailable, registering unconditionally: %s", e)

    @bot.message_handler(commands=["marketing_new"])
    def cmd_marketing_new(msg):
        identity = _authorized(bot, msg, get_identity)
        if not identity:
            return
        uid = str(msg.from_user.id)
        _pending[uid] = {"step": "domain", "created_at": _now_ts()}
        bot.send_message(
            msg.chat.id, "📣 דרישת שיווק חדשה\n\nבחר תחום:",
            reply_markup=_domain_keyboard(),
        )

    @bot.message_handler(commands=["cancel", "בטל"])
    def cmd_cancel(msg):
        uid = str(msg.from_user.id)
        if _pending.pop(uid, None):
            bot.send_message(msg.chat.id, "✅ בוטל.")
        else:
            bot.send_message(msg.chat.id, "אין תהליך פתוח לביטול.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mkt_domain:"))
    def cb_domain(call):
        uid = str(call.from_user.id)
        state = _get_valid_state(uid)
        if not state or state.get("step") != "domain":
            bot.answer_callback_query(call.id, "פג תוקף — נסה /marketing_new מחדש.")
            return
        state["domain"] = call.data.split(":", 1)[1]
        state["step"] = "demand_type"
        _pending[uid] = state
        bot.edit_message_text(
            f"✅ תחום: {_label(DOMAINS, state['domain'])}\n\nבחר סוג דרישה:",
            call.message.chat.id, call.message.message_id,
            reply_markup=_demand_type_keyboard(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mkt_type:"))
    def cb_type(call):
        uid = str(call.from_user.id)
        state = _get_valid_state(uid)
        if not state or state.get("step") != "demand_type":
            bot.answer_callback_query(call.id, "פג תוקף — נסה /marketing_new מחדש.")
            return
        state["demand_type"] = call.data.split(":", 1)[1]
        state["step"] = "target_audience"
        _pending[uid] = state
        bot.edit_message_text(
            f"✅ סוג: {_label(DEMAND_TYPES, state['demand_type'])}\n\n✍️ קהל יעד? (למשל: ניסיון 3+ שנים)",
            call.message.chat.id, call.message.message_id,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mkt_select:"))
    def cb_select(call):
        identity = _authorized_callback(bot, call, get_identity)
        if not identity:
            return
        _, creative_id, idea_num = call.data.split(":", 2)
        bot.answer_callback_query(call.id, "בוחר...")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        ok = _select_creative_and_generate_handoff(creative_id, idea_num)
        if not ok["ok"]:
            bot.send_message(call.message.chat.id, f"❌ {ok['error']}")
            return
        bot.send_message(
            call.message.chat.id,
            f"✅ נבחר רעיון {idea_num}\n\nProduction Handoff:\n\n{ok['handoff']}",
        )

    # ── לכידת טקסט חופשי לשלבי _FREE_TEXT_STEPS ──────────────────
    @bot.message_handler(
        func=lambda m: (
            _pending.get(str(m.from_user.id), {}).get("step")
            in _FREE_TEXT_STEPS
            and bool(getattr(m, "text", None))
            and not m.text.startswith("/")
        )
    )
    def capture_text(msg):
        uid = str(msg.from_user.id)
        state = _get_valid_state(uid)
        if not state:
            bot.send_message(msg.chat.id, "⏱ פג תוקף — נסה /marketing_new מחדש.")
            return

        step = state["step"]
        if step == "target_audience":
            state["target_audience"] = msg.text.strip()
            state["step"] = "location"
            _pending[uid] = state
            bot.send_message(msg.chat.id, "✍️ מיקום?")
            return

        if step == "location":
            state["location"] = msg.text.strip()
            state["step"] = "goal"
            _pending[uid] = state
            bot.send_message(msg.chat.id, "✍️ מה המטרה? (למשל: 10 מועמדים תוך שבוע)")
            return

        if step == "goal":
            state["goal"] = msg.text.strip()
            state["step"] = "constraints"
            _pending[uid] = state
            bot.send_message(
                msg.chat.id,
                "✍️ אילוצים ספציפיים לדרישה הזו? (למשל: לא להזכיר מחיר, קריאה "
                "לפעולה בטלפון בלבד — אם אין, כתוב \"אין\")",
            )
            return

        # step == "constraints" — השלב האחרון: יוצר Demand, מרכיב brief, קורא ל-AI
        identity = get_identity("telegram", uid)
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
            _pending.pop(uid, None)
            return

        state["constraints"] = msg.text.strip()
        _pending.pop(uid, None)
        bot.send_message(msg.chat.id, "⏳ יוצר דרישה ומרכיב 3 רעיונות...")

        result = _create_demand_and_generate_ideas(state, triggered_by=f"telegram:{identity.user_id}")
        if not result["ok"]:
            bot.send_message(msg.chat.id, f"❌ {result['error']}")
            return

        lines = ["✅ 3 רעיונות מוכנים — בחר אחד:", ""]
        for i, idea in enumerate(result["ideas"], start=1):
            lines.append(f"רעיון {i}:\n{idea}\n")
        bot.send_message(msg.chat.id, "\n".join(lines))
        bot.send_message(
            msg.chat.id, "בחר רעיון:",
            reply_markup=_idea_keyboard(result["creative_id"]),
        )

    logger.info("[F23] /marketing_new registered successfully")


def _authorized(bot, msg, get_identity):
    try:
        identity = get_identity("telegram", str(msg.from_user.id))
    except Exception as e:
        logger.error(f"[F23] identity error: {e}", exc_info=True)
        bot.send_message(msg.chat.id, "❌ שגיאה בזיהוי משתמש.")
        return None
    if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
        bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
        return None
    return identity


def _authorized_callback(bot, call, get_identity):
    try:
        identity = get_identity("telegram", str(call.from_user.id))
    except Exception as e:
        logger.error(f"[F23] identity error: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "שגיאה בזיהוי משתמש.")
        return None
    if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
        bot.answer_callback_query(call.id, "אין הרשאה.")
        return None
    return identity


def _now_ts() -> float:
    from datetime import timezone, datetime
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


def _label(pairs: list[tuple[str, str]], key: str) -> str:
    return next((label for label, k in pairs if k == key), key)


def _domain_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[
        InlineKeyboardButton(label, callback_data=f"mkt_domain:{key}")
        for label, key in DOMAINS
    ])
    return markup


def _demand_type_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(*[
        InlineKeyboardButton(label, callback_data=f"mkt_type:{key}")
        for label, key in DEMAND_TYPES
    ])
    return markup


def _idea_keyboard(creative_id: str):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[
        InlineKeyboardButton(f"רעיון {n}", callback_data=f"mkt_select:{creative_id}:{n}")
        for n in (1, 2, 3)
    ])
    return markup


# ── Core logic — importable/testable without a bot instance ─────────

def _parse_three_ideas(raw: str) -> list[str]:
    parts = re.split(r"רעיון\s*\d\s*:", raw)
    return [p.strip() for p in parts if p.strip()][:3]


def _create_demand_and_generate_ideas(state: dict, triggered_by: str = "unknown") -> dict:
    """
    Returns {"ok": True, "creative_id": ..., "ideas": [str, str, str]} or
    {"ok": False, "error": str}. Creates the Demand record, then makes one
    AI call for all 3 ideas (not the Agent tool-use loop — see the M1 spec's
    point on minimizing LLM calls).
    """
    import marketing_gateway
    from airtable_schema import MarketingDemandFields as MDF
    from llm_fallback import call_anthropic_text
    from marketing_brief_composer import compose_brief

    demand_record = marketing_gateway.DemandRecord(
        title=f"{_label(DEMAND_TYPES, state['demand_type'])} — {state.get('location', '')}".strip(" —"),
        domain=state["domain"],
        demand_type=state["demand_type"],
        target_audience=state.get("target_audience", ""),
        location=state.get("location", ""),
        goal=state.get("goal", ""),
        constraints=state.get("constraints", ""),
    )
    demand_id = marketing_gateway.create_demand(demand_record)
    if not demand_id:
        return {"ok": False, "error": "יצירת הדרישה נכשלה"}

    demand = marketing_gateway.get_demand(demand_id)
    if not demand:
        return {"ok": False, "error": f"הדרישה נוצרה (id={demand_id}) אך לא נמצאה בקריאה חוזרת"}

    domain_rules = marketing_gateway.get_marketing_rules(state["domain"])

    try:
        brief = compose_brief(demand=demand, task_type="creative_ideas", domain_rules=domain_rules)
    except Exception as e:
        return {"ok": False, "error": f"הרכבת ה-brief נכשלה: {e}"}

    instruction = (
        brief
        + "\n\nהחזר בדיוק בפורמט הבא, ללא טקסט נוסף:\n"
          "רעיון 1:\n<טקסט>\n\nרעיון 2:\n<טקסט>\n\nרעיון 3:\n<טקסט>"
    )

    try:
        raw = call_anthropic_text(
            source="cmd_marketing.create_demand_and_generate_ideas",
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system="אתה עוזר קריאייטיב שיווקי. החזר תשובה בפורמט המדויק המבוקש בלבד.",
            messages=[{"role": "user", "content": instruction}],
        )
    except Exception as e:
        return {"ok": False, "error": f"קריאת ה-AI נכשלה: {e}"}

    ideas = _parse_three_ideas(raw)
    if len(ideas) != 3:
        return {"ok": False, "error": f"לא הצלחתי לפרש 3 רעיונות מתשובת ה-AI (התקבלו {len(ideas)})"}

    creative_id = marketing_gateway.save_creative_ideas(
        demand_id=demand_id,
        title=f"{demand.get(MDF.NAME, demand_id)} — creatives",
        idea1=ideas[0], idea2=ideas[1], idea3=ideas[2],
        brief_used=brief,
    )
    if not creative_id:
        return {"ok": False, "error": "שמירת הרעיונות נכשלה"}

    logger.info("[F23] demand_id=%s creative_id=%s created by=%s", demand_id, creative_id, triggered_by)
    return {"ok": True, "creative_id": creative_id, "ideas": ideas}


def _select_creative_and_generate_handoff(creative_id: str, idea_num: str) -> dict:
    """Returns {"ok": True, "handoff": str} or {"ok": False, "error": str}."""
    import marketing_gateway
    from airtable_schema import MarketingCreativesFields as MCF, MarketingDemandFields as MDF, MarketingDemandStage
    from marketing_brief_composer import compose_production_handoff

    selected_idea = f"Idea {idea_num}"
    if not marketing_gateway.select_creative(creative_id, selected_idea):
        return {"ok": False, "error": "עדכון הבחירה נכשל"}

    creative = marketing_gateway.get_creative(creative_id)
    if not creative:
        return {"ok": False, "error": "הרעיון לא נמצא לאחר הבחירה"}

    idea_field = {"Idea 1": MCF.IDEA_1, "Idea 2": MCF.IDEA_2, "Idea 3": MCF.IDEA_3}[selected_idea]
    selected_text = creative.get(idea_field, "")
    if not selected_text:
        return {"ok": False, "error": "טקסט הרעיון שנבחר ריק"}

    demand_ids = creative.get(MCF.LINKED_DEMAND) or []
    if not demand_ids:
        return {"ok": False, "error": "לרעיון אין דרישה מקושרת"}

    demand = marketing_gateway.get_demand(demand_ids[0])
    if not demand:
        return {"ok": False, "error": "הדרישה המקושרת לא נמצאה"}

    domain_rules = marketing_gateway.get_marketing_rules(demand.get(MDF.DOMAIN, "general"))

    try:
        handoff = compose_production_handoff(
            demand=demand, selected_creative=selected_text, domain_rules=domain_rules,
        )
    except Exception as e:
        return {"ok": False, "error": f"הרכבת ה-Production Handoff נכשלה: {e}"}

    if not marketing_gateway.save_production_handoff(creative_id, handoff):
        return {"ok": False, "error": "שמירת ה-Production Handoff נכשלה"}

    if not marketing_gateway.update_demand_stage(demand_ids[0], MarketingDemandStage.HANDOFF_SENT):
        logger.warning(
            "[F23] handoff saved but demand_id=%s stage update to HANDOFF_SENT failed — "
            "Current Stage is now stale, fix manually in Airtable", demand_ids[0],
        )

    logger.info("[F23] handoff saved creative_id=%s demand_id=%s", creative_id, demand_ids[0])
    return {"ok": True, "handoff": handoff}


if __name__ == "__main__":
    sample = (
        "רעיון 1:\nמודעה קצרה וישירה.\n\n"
        "רעיון 2:\nמודעה עם דגש על תנאים.\n\n"
        "רעיון 3:\nמודעה עם קריאה לפעולה דחופה."
    )
    ideas = _parse_three_ideas(sample)
    assert len(ideas) == 3, f"expected 3 ideas, got {len(ideas)}"
    assert ideas[0] == "מודעה קצרה וישירה."
    assert ideas[2] == "מודעה עם קריאה לפעולה דחופה."

    malformed = _parse_three_ideas("אין כאן שום דבר בפורמט הנכון")
    assert len(malformed) != 3

    assert _label(DOMAINS, "recruitment") == "גיוס"
    assert _label(DEMAND_TYPES, "service") == "עסק שירותים"

    assert _FREE_TEXT_STEPS == ("target_audience", "location", "goal", "constraints")
    assert _FREE_TEXT_STEPS[-1] == "constraints", "constraints must be the terminal free-text step"

    # callback_data length sanity — Telegram caps at 64 bytes
    longest = f"mkt_select:recXXXXXXXXXXXXXXX:3"
    assert len(longest.encode()) <= 64, f"callback_data too long: {len(longest.encode())} bytes"

    print("cmd_marketing.py self-test OK")
