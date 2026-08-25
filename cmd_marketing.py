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

import json
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
    from tma_api import record_fields, record_id
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(*[
        InlineKeyboardButton(
            f"{_label(DOMAINS, record_fields(r).get(MDF.DOMAIN, ''))} · "
            f"{record_fields(r).get(MDF.NAME, record_id(r, required=True))}"[:60],
            callback_data=f"mkt_status:{record_id(r, required=True)}",
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
    from tma_api import record_fields

    records = marketing_gateway.list_demands(limit=10)
    return [
        r for r in records
        if identity.can_access_domain(record_fields(r).get(MDF.DOMAIN, ""))
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


# ── BUG-164 PR2: bounded creative authority for creative_ideas ─────
#
# The old free-text "רעיון 1:/2:/3:" instruction + regex parse let raw
# AI-authored prose reach save_creative_ideas() unchecked (BUG-164: a
# canonical Demand.Goal was silently rewritten into an unsupported claim).
# This section replaces that path. It reuses BUG-164 PR1's authority modules
# (marketing_fact_authority.py, marketing_creative_templates.py,
# marketing_creative_renderer.py) EXACTLY AS MERGED — no PR1 file is
# modified by this change.
#
# The AI is now asked to choose only from a closed menu (never free text):
# an (angle_id, opening_style, cta_style) combination from
# marketing_creative_templates.allowed_combinations(), and a fact_order
# drawn only from ProtectedDemandFacts.renderable(). Its JSON response is
# parsed with marketing_creative_renderer.parse_creative_proposal() and
# rendered with authority_filter_and_render() -- the SAME functions PR1
# shipped and tested, unmodified. The prompt below is advisory only; it is
# NOT the authority boundary -- an AI response that ignores it entirely
# still cannot produce persisted copy, because parse_creative_proposal()/
# authority_filter_and_render() reject anything that doesn't pass. See
# _parse_and_render_creative_proposals()'s fail-closed contract: on ANY
# rejection this function returns ok=False and nothing is ever passed to
# marketing_gateway.save_creative_ideas() -- there is no legacy raw-text
# fallback path left in this file.

def _build_creative_proposal_instruction(demand: dict, facts, domain_rules: str = "") -> str:
    """
    Pure. Builds the AI-facing prompt: persona/global-rules/domain-rules/
    business-rules context (same content compose_brief() would include for
    this Demand -- not reusing that function itself, to avoid touching
    marketing_brief_composer.py for this PR2 cutover) + a closed menu
    derived directly from marketing_creative_templates.allowed_combinations()
    and facts.renderable() -- never a second, hand-maintained list that
    could drift from what authority_filter_and_render() actually accepts.

    Raises ValueError if this demand_type has no registered template
    combinations -- fail closed, nothing valid to offer the AI.
    """
    from airtable_schema import MarketingDemandFields as MDF
    from marketing_creative_templates import allowed_combinations
    from marketing_domain_profiles import GLOBAL_RULES, get_profile

    demand_type = demand.get(MDF.DEMAND_TYPE, "")
    combos = allowed_combinations(demand_type)
    if not combos:
        raise ValueError(f"no template combinations registered for demand_type={demand_type!r}")

    profile = get_profile(demand_type)
    parts = [
        f"[persona] {profile.persona}",
        f"[חוקים כלליים] {GLOBAL_RULES}",
    ]
    if domain_rules:
        parts.append(f"[חוקי תחום] {domain_rules}")
    parts.append(f"[חוקי עסק] {profile.business_rules}")

    parts.append(
        "[משימה] בחר 3 הצעות קריאייטיב שונות באופן מהותי זו מזו (זווית/מסר "
        "שונה בכל הצעה, לא 3 ניסוחים לאותו רעיון). אתה בוחר אך ורק מתוך "
        "האפשרויות הסגורות למטה — אינך כותב טקסט חופשי, אינך מנסח בעצמך, "
        "ואינך ממציא עובדות שאינן ברשימת [עובדות זמינות]. ניתן לבחור באותה "
        "קומבינציה יותר מפעם אחת בין ההצעות, אך עדיף גיוון."
    )

    combo_lines = [
        f"{i}. angle_id={angle.value}, opening_style={opening.value}, cta_style={cta.value}"
        for i, (angle, opening, cta) in enumerate(combos, start=1)
    ]
    parts.append("[אפשרויות מותרות: angle_id / opening_style / cta_style]\n" + "\n".join(combo_lines))

    renderable = facts.renderable()
    fact_lines = [f'- "{key}": {fact.value!r}' for key, fact in sorted(renderable.items())]
    parts.append("[עובדות זמינות (fact_order יכול להשתמש רק במפתחות אלו)]\n" + "\n".join(fact_lines))

    parts.append(
        "[פורמט תשובה מחייב]\n"
        "החזר אך ורק JSON תקין: מערך של בדיוק 3 אובייקטים, ללא טקסט נוסף "
        "לפני או אחרי ה-JSON, ללא markdown code fence.\n"
        "כל אובייקט חייב להכיל בדיוק את 4 המפתחות הבאים, ושום מפתח נוסף:\n"
        '  "angle_id": ערך יחיד מהעמודה הראשונה למעלה (למשל "benefit_first") — '
        'לא מספר השורה.\n'
        '  "opening_style": ערך יחיד מהעמודה השנייה.\n'
        '  "cta_style": ערך יחיד מהעמודה השלישית.\n'
        '  "fact_order": רשימת מפתחות מתוך [עובדות זמינות] בלבד, בסדר שבו '
        'יופיעו בטקסט. "goal" חובה להיכלל בכל הצעה.'
    )
    return "\n\n".join(parts)


def _parse_and_render_creative_proposals(raw: str, facts, expected_count: int = 3) -> tuple[bool, list[str], str]:
    """
    Fail-closed batch gate. Returns (ok, rendered_ideas, reason).

    ok=False -> rendered_ideas is [] and reason explains why (invalid_json /
    not_a_json_array / wrong_count:N / item_i:<parse_creative_proposal or
    authority_filter_and_render rejection reason>). Caller MUST NOT persist
    anything and MUST NOT fall back to the raw AI text on ok=False.

    ok=True -> rendered_ideas contains exactly expected_count strings, each
    produced ONLY by marketing_creative_renderer.authority_filter_and_render()
    -- system-rendered output built from the fixed Hebrew template fragments
    and whole ProtectedFact.value strings, never raw AI prose. A single
    invalid proposal fails the entire batch (no partial save of 2 good +
    1 rejected idea).
    """
    from marketing_creative_renderer import ProposalRejected, authority_filter_and_render, parse_creative_proposal

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return False, [], f"invalid_json:{e}"

    if not isinstance(parsed, list):
        return False, [], "not_a_json_array"
    if len(parsed) != expected_count:
        return False, [], f"wrong_count:{len(parsed)}"

    rendered: list[str] = []
    for i, item in enumerate(parsed):
        try:
            proposal = parse_creative_proposal(item)
        except ProposalRejected as e:
            return False, [], f"item_{i}:{e}"
        result = authority_filter_and_render(proposal, facts)
        if result.status != "ok":
            return False, [], f"item_{i}:{result.reason}"
        rendered.append(result.rendered)

    return True, rendered, ""


def _create_demand_and_generate_ideas(state: dict, triggered_by: str = "unknown") -> dict:
    """
    Returns {"ok": True, "creative_id": ..., "ideas": [str, str, str]} or
    {"ok": False, "error": str}. Creates the Demand record, then makes one
    AI call for all 3 ideas (not the Agent tool-use loop — see the M1 spec's
    point on minimizing LLM calls).

    BUG-164 PR2: the persisted idea text is always system-rendered output
    that passed authority_filter_and_render() -- see
    _build_creative_proposal_instruction / _parse_and_render_creative_
    proposals above. On any validation failure this returns {"ok": False,
    ...} and marketing_gateway.save_creative_ideas() is never called with
    anything -- no raw-AI-text fallback exists in this function.
    """
    import marketing_gateway
    from airtable_schema import MarketingDemandFields as MDF
    from llm_fallback import call_anthropic_text
    from marketing_fact_authority import extract_protected_facts

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
    facts = extract_protected_facts(demand_id, demand)

    try:
        instruction = _build_creative_proposal_instruction(demand, facts, domain_rules=domain_rules)
    except ValueError as e:
        return {"ok": False, "error": f"הרכבת הבקשה ל-AI נכשלה: {e}"}

    try:
        raw = call_anthropic_text(
            source="cmd_marketing.create_demand_and_generate_ideas",
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=(
                "אתה בוחר הצעות קריאייטיב מתוך אפשרויות סגורות בלבד. "
                "החזר אך ורק JSON תקין בפורמט המבוקש, ללא טקסט נוסף."
            ),
            messages=[{"role": "user", "content": instruction}],
        )
    except Exception as e:
        return {"ok": False, "error": f"קריאת ה-AI נכשלה: {e}"}

    ok, ideas, reason = _parse_and_render_creative_proposals(raw, facts)
    if not ok:
        logger.warning(
            "[F23][BUG-164] creative proposal batch rejected demand_id=%s reason=%s raw=%.500s",
            demand_id, reason, raw,
        )
        return {
            "ok": False,
            "error": "ה-AI החזיר הצעה לא תקינה — לא נשמר תוכן לא-מאומת. נסה /marketing_new מחדש.",
        }

    creative_id = marketing_gateway.save_creative_ideas(
        demand_id=demand_id,
        title=f"{demand.get(MDF.NAME, demand_id)} — creatives",
        idea1=ideas[0], idea2=ideas[1], idea3=ideas[2],
        brief_used=instruction,
    )
    if not creative_id:
        return {"ok": False, "error": "שמירת הרעיונות נכשלה"}

    logger.info("[F23] demand_id=%s creative_id=%s created by=%s", demand_id, creative_id, triggered_by)
    return {"ok": True, "creative_id": creative_id, "ideas": ideas}


def _select_creative_and_generate_handoff(creative_id: str, idea_num: str) -> dict:
    """Select a Creative, then stop until an Approved Script exists."""
    import marketing_gateway
    from airtable_schema import MarketingCreativesFields as MCF, MarketingDemandStage

    selected_idea = f"Idea {idea_num}"
    if not marketing_gateway.select_creative(creative_id, selected_idea):
        return {"ok": False, "error": "עדכון הבחירה נכשל"}

    creative = marketing_gateway.get_creative(creative_id)
    if not creative:
        return {"ok": False, "error": "הרעיון לא נמצא לאחר הבחירה"}

    demand_ids = creative.get(MCF.LINKED_DEMAND) or []
    if not demand_ids:
        return {"ok": False, "error": "לרעיון אין דרישה מקושרת"}

    if not marketing_gateway.update_demand_stage(demand_ids[0], MarketingDemandStage.SELECTED):
        logger.warning(
            "[F23] creative selected but demand_id=%s stage update to SELECTED failed — "
            "Current Stage is now stale, fix manually in Airtable", demand_ids[0],
        )

    logger.info(
        "[F23] creative selected; script approval required creative_id=%s demand_id=%s",
        creative_id, demand_ids[0],
    )
    return {"ok": False, "error": "נבחר Creative. נדרש Script Draft ואישור לפני Production Handoff."}


if __name__ == "__main__":
    # BUG-164 PR2: no legacy raw-text parser exists in this module anymore —
    # structural proof there is no dormant fallback path left to reach for.
    assert "_parse_three_ideas" not in dir(), "legacy free-text idea parser must not exist"

    from airtable_schema import MarketingDemandFields as MDF
    from marketing_fact_authority import extract_protected_facts

    _demand = {
        MDF.DOMAIN: "general", MDF.DEMAND_TYPE: "recruitment", MDF.NAME: "דרישה למתקינים",
        MDF.TARGET_AUDIENCE: "ניסיון 3+ שנים", MDF.LOCATION: "בית שמש",
        MDF.GOAL: "10 מועמדים תוך שבוע", MDF.CONSTRAINTS: "מיקום נגיש לנכים",
    }
    _facts = extract_protected_facts("recDemo1", _demand)

    _instruction = _build_creative_proposal_instruction(_demand, _facts, domain_rules="תמיד לציין שכר.")
    assert _instruction == _build_creative_proposal_instruction(_demand, _facts, domain_rules="תמיד לציין שכר."), \
        "_build_creative_proposal_instruction must be deterministic"
    assert "angle_id=benefit_first" in _instruction
    assert '"goal"' in _instruction and "10 מועמדים תוך שבוע" in _instruction
    assert '"constraints"' not in _instruction and '"domain"' not in _instruction and '"topic"' not in _instruction
    assert "אינך כותב טקסט חופשי" in _instruction

    _valid_json = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal", "location", "audience"]},
        {"angle_id": "urgency", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal"]},
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal", "audience"]},
    ])
    ok, ideas, reason = _parse_and_render_creative_proposals(_valid_json, _facts)
    assert ok and len(ideas) == 3 and reason == "", (ok, ideas, reason)
    assert all("10 מועמדים תוך שבוע" in idea for idea in ideas)

    # fenced code block wrapper (common LLM habit despite instructions) is
    # stripped as transport framing, not treated as invalid
    ok_fenced, ideas_fenced, _ = _parse_and_render_creative_proposals(f"```json\n{_valid_json}\n```", _facts)
    assert ok_fenced and ideas_fenced == ideas

    # malformed JSON -> fail closed, nothing rendered
    ok_bad, ideas_bad, reason_bad = _parse_and_render_creative_proposals("not json at all", _facts)
    assert not ok_bad and ideas_bad == [] and reason_bad.startswith("invalid_json")

    # AI trying to smuggle free text via an extra field -> fail closed
    smuggled = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal"], "framing_text": "10 משרות פתוחות"},
    ] * 3)
    ok_smuggled, ideas_smuggled, reason_smuggled = _parse_and_render_creative_proposals(smuggled, _facts)
    assert not ok_smuggled and ideas_smuggled == [] and "unknown_fields" in reason_smuggled

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
