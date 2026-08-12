# cmd_marketing.py — F23 BOSS Marketing Bridge (M1)
# /marketing_new — wizard: Domain -> Demand Type -> per-type intake questions
# -> Constraints -> creates the Demand, composes a brief, makes one AI call
# for 3 ideas, then presents them as buttons to tap.
#
# Ownership: while a MarketingCaptureState is pending for a user (any step),
# app.py's webhook must route that user's next text to this module — see
# has_pending_capture() below and its call site in app.py's
# _webhook_telegram_impl (mirrors cmd_update.has_pending_text_capture(),
# which is the reason free text mid-/update doesn't leak to run_agent()).
# Before this was added, every free-text reply to /marketing_new fell
# straight through to run_agent() (the general Agent), because
# bot.process_new_updates() — the only thing that ever fires this module's
# @bot.message_handler-registered functions — was only called for slash
# commands or for cmd_update's own pending state.
#
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
# because the human running the wizard IS the authorization.
#
# M2 (Telegram slice — list + Next Action query, TMA screen tracked
# separately): /marketing_status lists Demands the caller is authorized to
# see (identity.can_access_domain(), re-checked again on the callback — never
# rely on the record id being merely hidden inside callback_data), then
# renders a status card via marketing_orchestrator.compute_next_action()
# (pure, pull-only, mirrors decision_orchestrator.py — never writes canonical
# state). When exactly one Creative is pending review, the card reuses the
# *existing* mkt_select:/_idea_keyboard() write path below as-is — M2 adds no
# new write implementation, only a new authorized entry point into the M1
# selection/handoff flow that was already live.

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
# MarketingCaptureState shape (plain dict, matches cmd_update.py/
# cmd_decision.py convention — no new state engine):
#   step: "domain" | "demand_type" | "intake" | "constraints"
#   domain, demand_type: str
#   q_index: int                 — position in INTAKE_QUESTIONS[demand_type]
#   answers: dict[str, str]      — semantic_key -> free-text answer
#   created_at: float
_pending: dict[str, dict] = {}

_CONSTRAINTS_PROMPT = (
    "✍️ אילוצים ספציפיים לדרישה הזו? (למשל: לא להזכיר מחיר, קריאה לפעולה "
    "בטלפון בלבד — אם אין, כתוב \"אין\")"
)

# Per Demand Type: a short, relevant question list — (semantic_key, prompt).
# Keys are named for what they actually ask, not for the existing Demand
# field they'll eventually compose into (see _materialize_demand_fields) —
# forcing e.g. "מחיר ומטרת הפרסום" into a key literally called
# "target_audience" would be a silent semantic mismatch just to avoid a
# schema change. Constraints is a universal trailing question, appended by
# the walker below, not authored per type.
INTAKE_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "recruitment": [
        ("role_experience", "✍️ איזה תפקיד/ניסיון אתה מחפש? (למשל: מתקין סיבים, ניסיון 3+ שנים)"),
        ("area", "✍️ אזור עבודה?"),
        ("quantity_deadline", "✍️ כמה מועמדים צריך ועד מתי?"),
    ],
    "furniture_import": [
        ("product_category", "✍️ אילו רהיטים/קטגוריה?"),
        ("sales_area", "✍️ איזור מכירה/משלוח?"),
        ("objective", "✍️ מה המטרה? (למשל: X יחידות תוך חודש)"),
    ],
    "fiber_equipment": [
        ("equipment_project", "✍️ איזה ציוד/פרויקט?"),
        ("project_area", "✍️ איזור הפרויקט?"),
        ("objective", "✍️ מה המטרה? (למשל: איתור קבלן, X יחידות ציוד)"),
    ],
    "real_estate_listing": [
        ("property_type_rooms", "✍️ סוג נכס וחדרים?"),
        ("property_location", "✍️ מיקום הנכס?"),
        ("price_purpose", "✍️ מחיר ומטרת הפרסום?"),
    ],
    "service": [
        ("service_type", "✍️ איזה שירות?"),
        ("service_area", "✍️ איזור שירות?"),
        ("objective", "✍️ מה המטרה? (למשל: X פניות תוך שבוע)"),
    ],
}


def _materialize_demand_fields(demand_type: str, answers: dict) -> dict:
    """
    Composes the semantic intake answers into DemandRecord's existing
    target_audience/location/goal fields (no schema change available).
    Explicit per-type mapping, not a generic rename — where a semantic key's
    meaning doesn't natively match the field it must land in (e.g. a
    property's type/rooms is not really a "target audience"), the composed
    text is labeled inline so the brief/summary downstream stays accurate
    instead of silently misrepresenting the content under the field's
    literal name.
    """
    a = answers
    if demand_type == "recruitment":
        return {
            "target_audience": a.get("role_experience", ""),
            "location": a.get("area", ""),
            "goal": a.get("quantity_deadline", ""),
        }
    if demand_type == "furniture_import":
        return {
            "target_audience": a.get("product_category", ""),
            "location": a.get("sales_area", ""),
            "goal": a.get("objective", ""),
        }
    if demand_type == "fiber_equipment":
        return {
            "target_audience": a.get("equipment_project", ""),
            "location": a.get("project_area", ""),
            "goal": a.get("objective", ""),
        }
    if demand_type == "real_estate_listing":
        return {
            "target_audience": f"פרטי הנכס: {a.get('property_type_rooms', '')}",
            "location": a.get("property_location", ""),
            "goal": a.get("price_purpose", ""),
        }
    if demand_type == "service":
        return {
            "target_audience": a.get("service_type", ""),
            "location": a.get("service_area", ""),
            "goal": a.get("objective", ""),
        }
    raise KeyError(f"no field mapping for demand_type={demand_type!r}")


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

    @bot.message_handler(commands=["marketing_status", "מצב_שיווק"])
    def cmd_marketing_status(msg):
        identity = _authorized(bot, msg, get_identity)
        if not identity:
            return
        records = _authorized_demand_list(identity)
        if not records:
            bot.send_message(msg.chat.id, "אין דרישות שיווק פעילות שאתה מורשה לראות כרגע.")
            return
        bot.send_message(
            msg.chat.id, f"📋 דרישות שיווק פעילות ({len(records)}):",
            reply_markup=_demand_list_keyboard(records),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mkt_status:"))
    def cb_status(call):
        identity = _authorized_callback(bot, call, get_identity)
        if not identity:
            return
        demand_id = call.data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        result = _get_next_action_card(demand_id, identity)
        if not result["ok"]:
            bot.send_message(call.message.chat.id, f"❌ {result['error']}")
            return
        bot.send_message(call.message.chat.id, result["text"], reply_markup=result.get("keyboard"))

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
        demand_type = call.data.split(":", 1)[1]
        state["demand_type"] = demand_type
        state["step"] = "intake"
        state["q_index"] = 0
        state["answers"] = {}
        _pending[uid] = state
        first_prompt = INTAKE_QUESTIONS[demand_type][0][1]
        bot.edit_message_text(
            f"✅ סוג: {_label(DEMAND_TYPES, demand_type)}\n\n{first_prompt}",
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

    # ── לכידת טקסט חופשי — כל עוד יש MarketingCaptureState פעיל, שום דבר
    # אחר (Agent, מילות אישור, וכו') לא נוגע בהודעה הבאה של המשתמש. תופס
    # לפי has_pending_capture() בלבד (לא לפי step ספציפי) כדי שגם טקסט תועה
    # בשלבי domain/demand_type (שאמורים להיענות בכפתורים) יטופל כאן ולא
    # יזלוג ל-Agent — ראה has_pending_capture() למטה ואת ה-call site שלה
    # ב-app.py.
    @bot.message_handler(
        func=lambda m: (
            has_pending_capture(str(m.from_user.id))
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

        if step in ("domain", "demand_type"):
            bot.send_message(msg.chat.id, "בחר אחת מהאפשרויות בכפתורים למעלה 👆")
            return

        if step == "intake":
            questions = INTAKE_QUESTIONS[state["demand_type"]]
            key, _ = questions[state["q_index"]]
            state["answers"][key] = msg.text.strip()
            state["q_index"] += 1
            if state["q_index"] < len(questions):
                _pending[uid] = state
                bot.send_message(msg.chat.id, questions[state["q_index"]][1])
            else:
                state["step"] = "constraints"
                _pending[uid] = state
                bot.send_message(msg.chat.id, _CONSTRAINTS_PROMPT)
            return

        # step == "constraints" — השלב האחרון: יוצר Demand, מרכיב brief, קורא ל-AI
        identity = get_identity("telegram", uid)
        if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
            bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
            _pending.pop(uid, None)
            return

        state["answers"]["constraints"] = msg.text.strip()
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


def has_pending_capture(user_id: str) -> bool:
    """
    app.py's webhook only calls bot.process_new_updates() (the only thing
    that fires this module's @bot.message_handler-registered functions) for
    slash-command text — free text never reaches it otherwise, so this must
    be checked in app.py's ingress and, if True, bot.process_new_updates()
    called explicitly. Mirrors cmd_update.has_pending_text_capture() exactly.

    True for ANY pending step (not just intake/constraints) — a stray text
    reply while the domain/demand_type keyboards are showing must also be
    claimed here (capture_text redirects the user to the buttons) rather
    than falling through to run_agent().
    """
    return _get_valid_state(user_id) is not None


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


def _demand_list_keyboard(records: list[dict]):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    from airtable_schema import MarketingDemandFields as MDF
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(*[
        InlineKeyboardButton(
            f"{_label(DOMAINS, r.get('fields', {}).get(MDF.DOMAIN, ''))} · "
            f"{r.get('fields', {}).get(MDF.NAME, r['id'])}"[:60],
            callback_data=f"mkt_status:{r['id']}",
        )
        for r in records
    ])
    return markup


# ── Core logic — importable/testable without a bot instance ─────────

def _authorized_demand_list(identity) -> list[dict]:
    """
    Read-only. Demands the caller is authorized to see, filtered by
    identity.can_access_domain() (owner: all, partner: only
    identity.allowed_domains, other internal roles: unrestricted today — see
    identity.py). limit=10 bounds the Telegram inline keyboard size.
    """
    import marketing_gateway
    from airtable_schema import MarketingDemandFields as MDF

    records = marketing_gateway.list_demands(limit=10)
    return [
        r for r in records
        if identity.can_access_domain(r.get("fields", {}).get(MDF.DOMAIN, ""))
    ]


def _truncate_for_telegram(text: str, limit: int = 3500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…\n(קוצר — הטקסט המלא שמור ב-Airtable, Marketing Creatives → Production Handoff)"


def _get_next_action_card(demand_id: str, identity) -> dict:
    """
    Returns {"ok": True, "text": str, "keyboard": InlineKeyboardMarkup|None}
    or {"ok": False, "error": str}. Re-checks identity.can_access_domain()
    against the fetched Demand independently of the list-time filter — a
    stale/replayed callback_data for a demand the caller has since lost
    access to must still fail closed, and a missing vs. unauthorized demand
    return the exact same generic error so neither leaks which case it was.
    """
    import marketing_gateway
    import marketing_orchestrator
    from airtable_schema import MarketingDemandFields as MDF

    demand = marketing_gateway.get_demand(demand_id)
    if not demand or not identity.can_access_domain(demand.get(MDF.DOMAIN, "")):
        return {"ok": False, "error": "הדרישה לא נמצאה"}

    creative_ids = demand.get(MDF.CREATIVES) or []
    creatives = {}
    for cid in creative_ids:
        fields = marketing_gateway.get_creative(cid)
        if fields:
            creatives[cid] = fields

    result = marketing_orchestrator.compute_next_action(demand_id, demand, creatives)
    text = _truncate_for_telegram(marketing_orchestrator.format_status_card(result))
    keyboard = _idea_keyboard(result.creative_id) if result.show_ideas and result.creative_id else None
    return {"ok": True, "text": text, "keyboard": keyboard}


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

    fields = _materialize_demand_fields(state["demand_type"], state["answers"])
    demand_record = marketing_gateway.DemandRecord(
        title=f"{_label(DEMAND_TYPES, state['demand_type'])} — {fields['location']}".strip(" —"),
        domain=state["domain"],
        demand_type=state["demand_type"],
        target_audience=fields["target_audience"],
        location=fields["location"],
        goal=fields["goal"],
        constraints=state["answers"].get("constraints", ""),
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

    # every Demand Type has its own 3-question intake list
    assert set(INTAKE_QUESTIONS.keys()) == {k for _, k in DEMAND_TYPES}
    for dt, questions in INTAKE_QUESTIONS.items():
        assert len(questions) == 3, f"{dt} should have exactly 3 intake questions"
        keys = [k for k, _ in questions]
        assert len(set(keys)) == 3, f"{dt} has duplicate semantic keys"

    # _materialize_demand_fields: every type maps to the 3 existing Demand
    # fields, and real_estate_listing's non-audience answer is labeled, not
    # silently renamed
    for dt in INTAKE_QUESTIONS:
        answers = {key: f"<{key}>" for key, _ in INTAKE_QUESTIONS[dt]}
        fields = _materialize_demand_fields(dt, answers)
        assert set(fields.keys()) == {"target_audience", "location", "goal"}
        assert all(fields.values()), f"{dt} produced an empty composed field"
    re_fields = _materialize_demand_fields(
        "real_estate_listing", {"property_type_rooms": "3 חדרים", "property_location": "x", "price_purpose": "y"},
    )
    assert "פרטי הנכס" in re_fields["target_audience"], "real_estate_listing content must stay labeled, not silently pass as literal target_audience"

    try:
        _materialize_demand_fields("not_a_real_type", {})
        raise AssertionError("expected KeyError")
    except KeyError:
        pass

    # has_pending_capture: True for ANY step while state is live, False once
    # popped/expired — this is what app.py's ingress checks before letting
    # run_agent() see the message
    _pending["_selftest_uid"] = {"step": "domain", "created_at": _now_ts()}
    assert has_pending_capture("_selftest_uid") is True
    _pending["_selftest_uid"]["step"] = "intake"
    assert has_pending_capture("_selftest_uid") is True
    _pending.pop("_selftest_uid")
    assert has_pending_capture("_selftest_uid") is False
    _pending["_selftest_uid"] = {"step": "constraints", "created_at": 0.0}  # expired
    assert has_pending_capture("_selftest_uid") is False
    _pending.pop("_selftest_uid", None)

    # callback_data length sanity — Telegram caps at 64 bytes
    longest = f"mkt_select:recXXXXXXXXXXXXXXX:3"
    assert len(longest.encode()) <= 64, f"callback_data too long: {len(longest.encode())} bytes"
    longest_status = "mkt_status:recXXXXXXXXXXXXXXX"
    assert len(longest_status.encode()) <= 64, f"callback_data too long: {len(longest_status.encode())} bytes"

    # _truncate_for_telegram: short text passes through, long text is cut with a note
    assert _truncate_for_telegram("short") == "short"
    long_text = "x" * 4000
    truncated = _truncate_for_telegram(long_text, limit=100)
    assert len(truncated) < len(long_text)
    assert "קוצר" in truncated

    print("cmd_marketing.py self-test OK")
