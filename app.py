# app.py — The Boss Bot v3.0
# Architecture: Identity → Router → Context → Agent
#
# כל בקשה עוברת:
#   resolve_identity → route_request → build_context → run_agent

import os
import logging
import threading
from flask import Flask, request, Response, abort, jsonify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from startup_validator import validate_startup, format_startup_message
validate_startup()

import anthropic
import telebot
from twilio.twiml.messaging_response import MessagingResponse

from memory_store    import memory
from identity        import resolve_identity, Role
from context         import build_context
from tool_registry   import enforce, ToolDenied
from scheduler       import start_scheduler
from tools           import dispatch_tool
from guards          import idempotency, rate_limiter, validate_tool_output
from config          import get_domain as _channel_domain
from core.router     import route_request, RouteDecision, Handler
from core.anti_hallucination import verify_execution, sanitize_agent_response
from health_monitor import get_health_status
try:
    from ad_attribution import inject_source_to_incoming_lead as _inject_utm
except ImportError:
    _inject_utm = None

logger = logging.getLogger(__name__)

# ─── קבועים ────────────────────────────────────────
MAX_TOOL_TURNS = 3

# כלים שתוצאתם נשמרת בזיכרון לרציפות בין תורות
_MEMORABLE_TOOLS = frozenset({
    "airtable_add", "airtable_update",
    "calendar_create_event", "gmail_send_draft",
})
AGENT_TIMEOUT  = 25

# ─── Pending Approvals (router-level) ──────────────────────────
# Saves messages routed to Handler.APPROVAL until the user confirms.
# key: chat_id (telegram user_id / whatsapp number)
_pending_approvals: dict[str, dict] = {}
_CONFIRM_WORDS = frozenset({"כן", "אשר", "✅", "yes", "y", "ok", "אוקי", "בצע", "קדימה"})
_CANCEL_WORDS  = frozenset({"לא", "בטל", "❌", "no", "n", "ביטול", "עצור", "cancel"})

# ─── קליינטים ──────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_APP_URL     = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")
WEBHOOK_SECRET     = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
bot    = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask(__name__)

from tma_api import tma_api as _tma_blueprint
app.register_blueprint(_tma_blueprint)


@bot.message_handler(commands=["status"])
def cmd_status(msg):
    """Owner בלבד — מצב env vars."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    bot.send_message(msg.chat.id, format_startup_message(), parse_mode="Markdown")


@bot.message_handler(commands=["schema"])
def cmd_schema(msg):
    """/schema [טבלה] — הצג סכמה. ללא טבלה = כל הטבלאות."""
    try:
        from schema_intelligence import handle_schema_command
        args = msg.text.replace("/schema", "", 1).replace(f"@{bot.get_me().username}", "").strip()
        reply = handle_schema_command(args)
        bot.send_message(msg.chat.id, reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_schema error: {e}")
        bot.send_message(msg.chat.id, f"❌ שגיאה בטעינת סכמה: {e}")

@bot.message_handler(commands=["done"])
def cmd_done(msg):
    """/done [n] — מסמן Quest מספר n כ-Done + כותב Coins_Log אוטומטית."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from tma_api import _at_list, _at_patch, _at_post, _coins_running_total
        from datetime import date, timedelta
        from airtable_schema import Tables, QuestsFields, CoinsLogFields, QuestStatus

        args = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split()) > 1 else ""
        if not args.isdigit():
            bot.send_message(msg.chat.id, "שימוש: /done [מספר]  —  לדוגמה: /done 2")
            return

        quest_num = int(args)
        today     = date.today()
        week_str  = (today - timedelta(days=today.weekday())).isoformat()

        all_quests  = _at_list(Tables.QUESTS, "", max_records=200)
        week_quests = [
            r for r in all_quests
            if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == week_str
        ] or [
            r for r in all_quests
            if r.get("fields", {}).get(QuestsFields.STATUS, "") != QuestStatus.SKIPPED
        ]

        if quest_num < 1 or quest_num > len(week_quests):
            bot.send_message(msg.chat.id, f"מספר לא תקין. יש {len(week_quests)} Quests השבוע.")
            return

        quest      = week_quests[quest_num - 1]
        qf         = quest.get("fields", {})
        old_status = qf.get(QuestsFields.STATUS, "")
        name       = qf.get(QuestsFields.NAME, "?")

        if old_status == QuestStatus.DONE:
            bot.send_message(msg.chat.id, f"✅ {name} כבר מסומן כהושלם.")
            return

        _at_patch(Tables.QUESTS, quest["id"], {
            QuestsFields.STATUS:  QuestStatus.DONE,
            QuestsFields.DONE_BY: identity.display_name or identity.user_id,
        })

        coins = int(qf.get(QuestsFields.COINS, 0) or 0)
        if coins > 0:
            _at_post(Tables.COINS_LOG, {
                CoinsLogFields.ACTION:        name,
                CoinsLogFields.COINS:         coins,
                CoinsLogFields.DATE:          today.isoformat(),
                CoinsLogFields.QUEST:         [quest["id"]],
                CoinsLogFields.NOTE:          "Quest completed via /done",
                CoinsLogFields.TOTAL_RUNNING: _coins_running_total(coins),
            })

        bot.send_message(
            msg.chat.id,
            f"✅ *{name}* — הושלם\\!\n\\+{coins}🪙",
            parse_mode="MarkdownV2",
        )
        logger.info(f"[Game] /done {quest_num} → {name} +{coins}🪙 by {identity.display_name}")
    except Exception as e:
        logger.error(f"cmd_done error: {e}")
        bot.send_message(msg.chat.id, f"❌ שגיאה: {e}")


@bot.message_handler(commands=["convert"])
def cmd_convert(msg):
    """/convert [שם/טלפון] — הופך ליד לאיש קשר ב-CRM (owner בלבד, דורש LEAD_AUTO_CONVERT)."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from lead_conversion import convert_lead_to_contact
        query = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split()) > 1 else ""
        if not query:
            bot.send_message(msg.chat.id, "שימוש: /convert [שם או טלפון של ליד]")
            return

        ok, reply = convert_lead_to_contact(query)
        bot.send_message(msg.chat.id, reply, parse_mode="Markdown")
        logger.info(f"[LeadConvert] /convert '{query}' → {'OK' if ok else 'skip'} by {identity.display_name}")
    except Exception as e:
        logger.error(f"cmd_convert error: {e}")
        bot.send_message(msg.chat.id, f"❌ שגיאה: {e}")


@bot.message_handler(commands=["quest"])
def cmd_quest(msg):
    """/quest — Quest Log השבוע."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from tma_api import _at_list
        from datetime import date, timedelta
        from airtable_schema import Tables, QuestsFields, QuestStatus
        today  = date.today()
        monday = today - timedelta(days=today.weekday())
        week_str = monday.isoformat()

        all_q = _at_list(Tables.QUESTS, "", max_records=200)
        quests = [r for r in all_q if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == week_str]
        if not quests:
            quests = [r for r in all_q if r.get("fields", {}).get(QuestsFields.STATUS, "") in {QuestStatus.TODO, QuestStatus.IN_PROGRESS}]
        if not quests:
            bot.send_message(msg.chat.id, "🎮 אין Quests השבוע.")
            return

        icons = {QuestStatus.DONE: "✅", QuestStatus.IN_PROGRESS: "🔄", QuestStatus.TODO: "⬜", QuestStatus.SKIPPED: "⏭️"}
        lines = [f"🎮 *Quest Log — {week_str}*\n"]
        total_possible = 0
        total_earned   = 0
        for r in quests:
            f       = r.get("fields", {})
            status  = f.get(QuestsFields.STATUS, "")
            coins   = int(f.get(QuestsFields.COINS, 0) or 0)
            impact  = " ⚡" if f.get(QuestsFields.IMPACT) else ""
            total_possible += coins
            if status == QuestStatus.DONE:
                total_earned += coins
            lines.append(f"{icons.get(status, '❓')} {f.get(QuestsFields.NAME, '?')} — {coins}🪙{impact}")

        lines.append(f"\n💰 {total_earned}/{total_possible}🪙 הושלם")
        bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_quest error: {e}")
        bot.send_message(msg.chat.id, f"❌ שגיאה: {e}")


@bot.message_handler(commands=["coins"])
def cmd_coins(msg):
    """/coins — סה״כ מטבעות + World progress."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from tma_api import _at_list
        from airtable_schema import Tables, CoinsLogFields, WorldsFields, WorldStatus

        log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
        total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

        worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
        world_section = ""
        if worlds:
            wf     = worlds[0].get("fields", {})
            target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)
            earned = int(wf.get(WorldsFields.COINS_EARNED, 0) or 0)
            pct    = round(100 * earned / target, 1) if target > 0 else 0.0
            filled = int(pct / 10)
            bar    = "█" * filled + "░" * (10 - filled)
            world_section = (
                f"\n\n🌍 *{wf.get(WorldsFields.NAME, 'World')}*\n"
                f"`{bar}` {pct}%\n"
                f"{earned}/{target}🪙 | פרס: {wf.get(WorldsFields.PRIZE, '?')}"
            )

        bot.send_message(msg.chat.id, f"🪙 *סה״כ מטבעות: {total_coins}*{world_section}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_coins error: {e}")
        bot.send_message(msg.chat.id, f"❌ שגיאה: {e}")


_scheduler_thread = next(
    (t for t in threading.enumerate() if t.name == "scheduler" and t.is_alive()),
    None,
)
if _scheduler_thread:
    logger.info("[Scheduler] Already running — skipping init")
    _scheduler = _scheduler_thread
else:
    try:
        _scheduler = start_scheduler()
        logger.info("Scheduler OK")
    except Exception as e:
        logger.error(f"Scheduler failed: {e}")

if os.environ.get("SETUP_WEBHOOK") == "1":
    try:
        bot.remove_webhook()
        kwargs = {"url": f"{RENDER_APP_URL}/{TELEGRAM_TOKEN}"}
        if WEBHOOK_SECRET:
            kwargs["secret_token"] = WEBHOOK_SECRET
        bot.set_webhook(**kwargs)
        logger.info(f"Telegram Webhook set (secret={'yes' if WEBHOOK_SECRET else 'no'})")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


# ══════════════════════════════════════════════════
# Integration Layer — CORE_02.6
# ══════════════════════════════════════════════════

def clarify_response(route: RouteDecision) -> str:
    logger.info(f"[CLARIFY] intent={route.intent} conf={route.confidence:.2f}")
    return route.response_override or "לא הצלחתי להבין — תוכל לנסח אחרת?"


def approval_response(route: RouteDecision, original_text: str, chat_id: str,
                       channel: str, domain: str) -> str:
    """Saves original action and asks owner to confirm with כן/לא."""
    logger.info(f"[APPROVAL] intent={route.intent} domain={route.domain} | saved for {chat_id}")
    _pending_approvals[chat_id] = {
        "text":    original_text,
        "channel": channel,
        "domain":  domain,
    }
    preview = original_text[:120] + ("…" if len(original_text) > 120 else "")
    return (
        f"⏳ *אישור נדרש*\n\n"
        f"פעולה: `{preview}`\n\n"
        f"ענה *כן* לביצוע או *לא* לביטול."
    )


# ══════════════════════════════════════════════════
# Approval Gate Helpers
# ══════════════════════════════════════════════════

def _describe_tool_call(tool_name: str, inputs: dict) -> str:
    """תיאור קריא של קריאת כלי לכפתורי אישור."""
    if tool_name == "gmail_send_draft":
        return f"📧 שלח מייל (draft: {inputs.get('draft_id', '?')})"
    if tool_name == "calendar_create_event":
        start = str(inputs.get("start_time", "?"))[:16]
        return f"📅 קבע: {inputs.get('summary', '?')} ב-{start}"
    if tool_name == "airtable_add":
        fields_str = str(inputs.get("fields", {}))[:50]
        return f"➕ הוסף ל-{inputs.get('table', '?')}: {fields_str}"
    if tool_name == "airtable_update":
        return f"✏️ עדכן {inputs.get('record_id', '?')} ב-{inputs.get('table', '?')}"
    if tool_name == "sheets_append":
        return f"📊 כתוב ל-{inputs.get('sheet_name', '?')}"
    return f"⚡ {tool_name}: {str(inputs)[:60]}"


def _queue_approval(tool_name: str, tool_inputs: dict,
                    user_chat_id: str, channel: str) -> str:
    """
    שומר פעולה ממתינה ושולח בקשת אישור לowner.
    מחזיר string לmodel: "⏳ ממתין לאישור..."
    """
    from event_bus import bus
    label     = _describe_tool_call(tool_name, tool_inputs)
    action_id, _ = bus.request_approval(
        action  = tool_name,
        payload = {
            "tool_name":    tool_name,
            "tool_inputs":  tool_inputs,
            "user_chat_id": user_chat_id,
            "channel":      channel,
        },
        chat_id = user_chat_id,
        label   = label,
    )

    owner_chat_id = (
        os.environ.get("OWNER_TELEGRAM_ID", "") or
        os.environ.get("ELIYAHU_CHAT_ID", "") or
        os.environ.get("DIGEST_CHAT_ID", "")
    )
    if owner_chat_id:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(
            telebot.types.InlineKeyboardButton("✅ אשר", callback_data=f"approve:{action_id}"),
            telebot.types.InlineKeyboardButton("❌ בטל",  callback_data=f"reject:{action_id}"),
        )
        try:
            bot.send_message(
                owner_chat_id,
                f"⏳ *בקשת אישור*\n\n{label}\n\n_ID: {action_id} | פג תוקף בעוד 10 דקות_",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            logger.info(f"[Approval] ✅ sent to owner {owner_chat_id} | {action_id}")
        except Exception as e:
            logger.error(f"[Approval] ❌ failed to notify owner: {e}")
            # BOSS NEVER FAKES: לא מחזירים "ממתין לאישור" כשהשליחה נכשלה
            return (
                f"❌ לא הצלחתי לשלוח בקשת אישור לבעלים.\n"
                f"הפעולה לא בוצעה: {label}"
            )

    logger.info(f"[Approval] queued {action_id} | {tool_name} | user={user_chat_id}")
    return f"⏳ הפעולה ממתינה לאישור הבעלים: {label}"


def _handle_approval_callback(cq) -> None:
    """מטפל בלחיצה על ✅/❌ של בקשת אישור."""
    from event_bus import bus

    data = cq.data or ""
    if ":" not in data:
        bot.answer_callback_query(cq.id, "⚠️ נתוני callback לא תקינים")
        return

    action, action_id = data.split(":", 1)

    if action in ("approve", "reject"):
        approver_chat_id = str(getattr(cq.from_user, "id", "") or "")
        approver_identity = resolve_identity("telegram", approver_chat_id)
        if not (approver_identity.is_owner or approver_identity.can("actions.approve")):
            logger.warning(
                f"[Approval] unauthorized {action} attempt {action_id} "
                f"by {approver_identity.user_id} role={approver_identity.role}"
            )
            bot.answer_callback_query(cq.id, "⛔ אין לך הרשאה לאשר פעולה זו")
            return

    if action == "approve":
        # atomic pop — בדיקת TTL ומחיקה בצעד אחד
        item = bus._pending.pop(action_id)
        if not item:
            bot.answer_callback_query(cq.id, "⏰ פג תוקף — הפעולה לא קיימת יותר")
            try:
                bot.edit_message_reply_markup(cq.message.chat.id, cq.message.message_id,
                                              reply_markup=None)
            except Exception:
                pass
            return

        payload       = item["payload"]
        tool_name     = payload.get("tool_name")   # absent on non-tool approvals
        user_chat_id  = payload.get("user_chat_id", item.get("chat_id", ""))
        channel       = payload.get("channel", "telegram")

        if not tool_name:
            # Non-tool approval — emit {action}.confirmed event
            bus_action = item.get("action", "")
            logger.info(f"[Approval] non-tool confirm {action_id} | action={bus_action}")
            from event_bus import bus as _bus
            result = _bus.emit(f"{bus_action}.confirmed", payload, user_chat_id)
            if result is None:
                result = f"⚠️ אין handler ל-{bus_action} — הפעולה לא בוצעה."
                logger.error(f"[Approval] no handler for {bus_action}.confirmed")
        else:
            tool_inputs = payload.get("tool_inputs", {})
            identity    = resolve_identity(channel, user_chat_id)

            try:
                enforce(tool_name, identity)
            except ToolDenied as e:
                logger.warning(
                    f"[Approval] denied approved action {action_id} | "
                    f"{tool_name} | user={identity.user_id} role={identity.role}: {e}"
                )
                bot.answer_callback_query(cq.id, "⛔ הפעולה כבר אינה מורשית")
                return

            raw    = dispatch_tool(tool_name, tool_inputs, identity)
            result = validate_tool_output(tool_name, raw)

        logger.info(f"[Approval] ✅ confirmed {action_id} | {tool_name or item.get('action')}")

        try:
            bot.send_message(user_chat_id, f"✅ הפעולה בוצעה:\n{result}")
        except Exception as e:
            logger.error(f"[Approval] notify user failed: {e}")

        try:
            bot.edit_message_text(
                f"✅ *אושר ובוצע*\n{item['label']}\n\n`{result[:200]}`",
                cq.message.chat.id, cq.message.message_id,
                parse_mode="Markdown",
            )
        except Exception:
            pass
        bot.answer_callback_query(cq.id, "✅ בוצע!")

    elif action == "reject":
        item = bus._pending.get(action_id)
        bus.reject(action_id)

        if item:
            user_chat_id = item["payload"].get("user_chat_id", "")
            if user_chat_id:
                try:
                    bot.send_message(user_chat_id, f"🚫 הפעולה בוטלה: {item['label']}")
                except Exception:
                    pass

        try:
            bot.edit_message_text(
                "🚫 *בוטל*",
                cq.message.chat.id, cq.message.message_id,
                parse_mode="Markdown",
            )
        except Exception:
            pass
        bot.answer_callback_query(cq.id, "🚫 בוטל")

    else:
        bot.answer_callback_query(cq.id, "⚠️ פעולה לא מוכרת")


def _typing_indicator(chat_id: str, channel: str, stop_event: threading.Event, interval: float = 2.5) -> None:
    """Send a periodic typing indicator while the Agent processes the request."""
    if channel == "telegram":
        try:
            bot.send_chat_action(chat_id, "typing")
        except Exception as e:
            logger.debug(f"[Typing] failed for {chat_id}: {e}")

    while not stop_event.wait(interval):
        if channel == "telegram":
            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception as e:
                logger.debug(f"[Typing] failed for {chat_id}: {e}")
        else:
            # Future platforms can be added here if they support typing indicators.
            pass


def _safe_route(text: str, channel: str, identity, domain_from_channel: str = "") -> RouteDecision:
    """
    עוטף את route_request עם fallback.
    כלל ברזל #9: אם Router נכשל — ממשיכים עם intent=unknown, risk=review.
    לא נופלים.
    """
    try:
        return route_request(
            text                = text,
            channel_raw         = channel,
            identity            = identity,
            domain_from_channel = domain_from_channel,
        )
    except Exception as e:
        logger.error(f"[Router] FAILED — fallback to safe defaults: {e}", exc_info=True)
        from core.router.route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler
        return RouteDecision(
            channel           = channel,
            intent            = Intent.UNKNOWN,
            domain            = RouterDomain.GENERAL,
            risk              = Risk.NORMAL,
            handler           = Handler.AGENT,   # ממשיכים — Agent יטפל
            needs_approval    = False,
            confidence        = 0.0,
            matched_rule      = "fallback",
            response_override = "",
        )


# ══════════════════════════════════════════════════
# run_agent — Identity + Router + Agent Loop
# ══════════════════════════════════════════════════

def run_agent(
    user_text:           str,
    chat_id:             str,
    channel:             str = "telegram",
    domain_from_channel: str = "",
    _skip_approval:      bool = False,
) -> str:

    # ── 1. Identity ───────────────────────────────
    identity = resolve_identity(channel, chat_id)
    logger.info(f"[Identity] {identity}")
    if identity.role in (Role.READONLY, Role.GUEST):
        logger.warning(
            f"[Identity] LOW-PRIVILEGE request — "
            f"channel={channel} id={chat_id} role={identity.role} "
            f"msg='{user_text[:60]}'"
        )

    # ── 1.5. WhatsApp Lead Capture (W0) ───────────
    if identity.role == Role.LEAD:
        try:
            from lead_capture import capture_inbound_lead
            capture_inbound_lead(identity, user_text)
        except Exception as e:
            logger.error(f"[LeadCapture] failed for {identity.memory_key}: {e}")

    # ── 2. Rate Limit ─────────────────────────────
    if not rate_limiter.is_allowed(identity.memory_key):
        return "⚠️ יותר מדי בקשות. המתן דקה ונסה שוב."

    # ── 2.5. Pending Approval Gate ────────────────
    pending = _pending_approvals.get(chat_id)
    if pending:
        lower = user_text.strip().lower()
        if lower in _CONFIRM_WORDS:
            _pending_approvals.pop(chat_id, None)
            logger.info(
                f"[PendingApproval] ✅ confirmed by {chat_id} → "
                f"executing: {pending['text'][:60]}"
            )
            return run_agent(
                pending["text"], chat_id, channel,
                domain_from_channel=pending.get("domain", domain_from_channel),
                _skip_approval=True,
            )
        elif lower in _CANCEL_WORDS:
            _pending_approvals.pop(chat_id, None)
            logger.info(f"[PendingApproval] 🚫 cancelled by {chat_id}")
            return "🚫 הפעולה בוטלה."
        else:
            # New unrelated message — clear stale pending, treat normally
            _pending_approvals.pop(chat_id, None)

    # ── 3. Router — CORE_02.6 Integration ────────
    route = _safe_route(user_text, channel, identity, domain_from_channel)
    logger.info(route.to_log())

    # ── 4. Dispatch ───────────────────────────────
    if route.handler == Handler.CLARIFY:
        return clarify_response(route)

    if route.handler == Handler.APPROVAL and not _skip_approval:
        return approval_response(route, user_text, chat_id, channel, domain_from_channel)

    # לא עושים BLOCK רגיל ללקוח — restricted ממשיך לסוכן
    if route.restricted:
        logger.warning(
            f"[Restricted] external request: "
            f"user={identity.user_id} role={identity.role} "
            f"intent={route.intent} notify_owner=True tool_allowed=False"
        )

    # ── 5. Agent Loop ─────────────────────────────
    try:
        research_mode = user_text.startswith("#") and identity.is_owner
        clean_msg     = user_text[1:].strip() if research_mode else user_text

        # Context מקבל domain + handler מהראוטר
        ctx = build_context(
            identity,
            user_text,
            domain  = route.domain,
            handler = route.handler,
            intent  = route.intent,
        )
        history = memory.get_for_claude(ctx.memory_key)

        # C4.1: trim history if too large — prevents silent context overflow
        MAX_HISTORY_CHARS = 60_000
        if len(str(history)) > MAX_HISTORY_CHARS:
            logger.warning(
                f"[Agent] history too large ({len(str(history))} chars) "
                f"for {ctx.memory_key} — trimming to last 6 messages"
            )
            history = history[-6:]

        messages = history + [{"role": "user", "content": clean_msg}]

        logger.info(
            f"[Agent] {ctx.identity_label} | "
            f"intent={route.intent} domain={route.domain} | "
            f"model={ctx.model} tools={len(ctx.allowed_tools)}"
        )

        final_reply     = "⚠️ לא התקבלה תשובה."
        tool_calls_made = 0
        tool_results_log: list[dict] = []   # A32: accumulates all tool results

        while True:
            response = client.messages.create(
                model       = ctx.model,
                max_tokens  = ctx.max_tokens,
                temperature = 0.2,
                system      = ctx.system_prompt,
                tools       = ctx.allowed_tools,
                messages    = messages,
            )

            tool_uses   = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_uses:
                final_reply = text_blocks[0].text if text_blocks else "✅ פעולה הושלמה."
                break

            if tool_calls_made >= MAX_TOOL_TURNS:
                logger.warning(
                    f"[Agent] reached max tool turns ({tool_calls_made}/{MAX_TOOL_TURNS}) "
                    f"for user={identity.user_id} role={identity.role} intent={route.intent}"
                )
                final_reply = (text_blocks[0].text if text_blocks
                               else "⚠️ הגעתי למגבלת הפעולות לריצה זו. נסה לפרק את הבקשה לשלבים.")
                break

            # ── Tool Loop ────────────────────────
            tool_results = []
            for tu in tool_uses:
                if not route.tool_allowed:
                    logger.info(f"[Tool] Silently blocked by route (restricted): {tu.name}")
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tu.id,
                        "content":     "הבקשה התקבלה ותועבר לטיפול.",
                    })
                    continue

                try:
                    meta = enforce(tu.name, identity)
                except ToolDenied as e:
                    logger.warning(f"[Tool] Denied: {tu.name} for {identity.role}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
                    })
                    continue

                # ── Approval Gate ─────────────────────
                if meta.requires_approval:
                    result = _queue_approval(
                        tu.name, dict(tu.input), chat_id, channel
                    )
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": result
                    })
                    continue

                logger.info(f"[Tool] {tu.name} | {str(tu.input)[:80]}")
                raw    = dispatch_tool(tu.name, tu.input, identity)
                result = validate_tool_output(tu.name, raw)
                logger.info(f"[Tool] → {result[:80]}")

                # A32 — verify tool actually succeeded
                exec_check = verify_execution(tu.name, result)
                if exec_check.status == "failed":
                    logger.error(f"[A32] Execution failed: {tu.name} — {exec_check.reason}")
                    result = f"❌ הפעולה לא הושלמה: {exec_check.reason}"
                elif exec_check.status == "warn":
                    logger.warning(f"[A32] Execution warn: {tu.name} — {exec_check.reason}")

                # Fix 2: persist successful write results for next-turn memory
                if tu.name in _MEMORABLE_TOOLS and "❌" not in result:
                    memory.add(
                        ctx.memory_key,
                        "user",   # only "user"/"assistant" valid in Claude messages[]
                        f"[🔧 {tu.name}]: {str(tu.input)[:60]} → {result[:60]}"
                    )

                entry = {"type": "tool_result", "tool_use_id": tu.id, "content": result}
                tool_results.append(entry)
                tool_results_log.append(entry)   # A32: accumulate for final check

            tool_calls_made += 1

            # ⏳ keep typing indicator alive between tool calls
            if channel == "telegram":
                try:
                    bot.send_chat_action(chat_id, "typing")
                except Exception:
                    pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

        # A32 — final hallucination check before reply reaches user
        final_reply = sanitize_agent_response(final_reply, tool_results_log)

        # ── שמירת זיכרון ─────────────────────────
        memory.add(ctx.memory_key, "user",      clean_msg)
        memory.add(ctx.memory_key, "assistant", final_reply)

        return final_reply

    except anthropic.APIStatusError as e:
        logger.error(f"[Agent] Anthropic {e.status_code}: {e.message}")
        if e.status_code == 529:
            return "⚠️ השרת עמוס כרגע. נסה שוב בעוד דקה."
        if e.status_code == 413:
            return "⚠️ ההודעה ארוכה מדי. נסה לשלח קצר יותר."
        return f"❌ שגיאת API ({e.status_code}). נסה שוב."
    except anthropic.APITimeoutError:
        logger.error(f"[Agent] Timeout for {chat_id}")
        return "⚠️ הבקשה לקחה יותר מדי זמן. נסה שוב או שלח הודעה קצרה יותר."
    except Exception as e:
        logger.error(f"[Agent] error: {e}", exc_info=True)
        return "⚠️ משהו השתבש. נסה שוב."


# ══════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    health_status = get_health_status(globals().get("_scheduler"), memory)
    return jsonify({
        "status":         health_status["status"],
        "version":        "3.0",
        "max_tool_turns": MAX_TOOL_TURNS,
        "router":         "CORE_02.6",
        "checks":         health_status["checks"],
        "digest_chat_id": bool(os.environ.get("DIGEST_CHAT_ID")),
        "airtable":       bool(os.environ.get("AIRTABLE_API_KEY")),
        "memory_entries": len(memory._store),
    }), 200


@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook_telegram():
    if request.headers.get("content-type") != "application/json":
        abort(403)
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != WEBHOOK_SECRET:
            logger.warning(f"[Webhook] bad secret from {request.remote_addr}")
            abort(403)
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))

    if update.callback_query:
        try:
            _handle_approval_callback(update.callback_query)
        except Exception as e:
            logger.error(f"[Telegram] callback error: {e}", exc_info=True)
        return "", 200

    if update.message and update.message.text:
        reply_chat_id  = str(update.message.chat.id)       # לאן לשלוח (group או private)
        sender_user_id = str(update.message.from_user.id)  # מי שלח (תמיד USER_ID)
        text           = update.message.text

        # Slash commands → registered @bot.message_handler(commands=[...]) handlers.
        # They authenticate via resolve_identity internally; we don't go through run_agent.
        if text.startswith("/"):
            try:
                bot.process_new_updates([update])
            except Exception as e:
                logger.error(f"[Telegram] command dispatch error: {e}", exc_info=True)
            return "", 200

        if idempotency.is_duplicate("telegram", sender_user_id, text):
            try:
                bot.send_message(
                    reply_chat_id,
                    "♻️ ההודעה הזו כבר טופלה.\n"
                    "אם זו בקשה חדשה — נסח אותה אחרת."
                )
            except Exception as e:
                logger.debug(f"[Idempotency] notify failed: {e}")
            return "", 200

        # ── Thinking Indicator ────────────────────────────────────
        thinking_msg_id = None
        try:
            thinking_msg    = bot.send_message(reply_chat_id, "⏳")
            thinking_msg_id = thinking_msg.message_id
        except Exception:
            pass

        # typing thread כגיבוי (למקרה ש-⏳ לא נשלח)
        typing_stop   = threading.Event()
        typing_thread = threading.Thread(
            target=_typing_indicator,
            args=(reply_chat_id, "telegram", typing_stop),
            daemon=True,
        )
        typing_thread.start()

        try:
            reply = run_agent(text, sender_user_id, channel="telegram")
        finally:
            typing_stop.set()
            typing_thread.join(timeout=1.0)
            if thinking_msg_id:
                try:
                    bot.delete_message(reply_chat_id, thinking_msg_id)
                except Exception:
                    pass

        try:
            bot.send_message(reply_chat_id, reply)
        except Exception as e:
            logger.error(f"[Telegram] send error: {e}")
    return "", 200


@app.route("/whatsapp", methods=["POST"])
def webhook_whatsapp():
    incoming  = request.values.get("Body", "").strip()
    sender_raw = request.values.get("From", "whatsapp:unknown")
    sender     = sender_raw.removeprefix("whatsapp:")   # "+972XXXXXXXXX"
    to_number  = request.values.get("To",   "whatsapp:unknown")
    msg_sid   = request.values.get("MessageSid", "")

    if not incoming:
        return Response(str(MessagingResponse()), mimetype="application/xml")

    # domain לפי מספר היעד — Layer 1 של domain_router
    domain_from_channel = _channel_domain(to_number)

    dedup_key = msg_sid if msg_sid else incoming
    if idempotency.is_duplicate("whatsapp", sender, dedup_key):
        return Response(str(MessagingResponse()), mimetype="application/xml")

    if _inject_utm:
        try:
            _inject_utm(
                memory_key   = f"whatsapp:{sender}",
                request_args = request.values.to_dict(),
                channel      = "whatsapp",
            )
        except Exception as _utm_err:
            logger.debug(f"[UTM] whatsapp inject skipped: {_utm_err}")

    resp = MessagingResponse()
    resp.message(run_agent(
        incoming, sender,
        channel             = "whatsapp",
        domain_from_channel = domain_from_channel,
    ))
    return Response(str(resp), mimetype="application/xml")


WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    auth_header = request.headers.get("Authorization", "")
    if not WORKER_SECRET or auth_header != f"Bearer {WORKER_SECRET}":
        logger.warning(f"[Worker] unauthorized attempt from {request.remote_addr}")
        return jsonify({"error": "unauthorized"}), 401
    try:
        payload = request.get_json(force=True) or {}
        chat_id = payload.get("chat_id", "")
        event   = payload.get("event", "")
        if not chat_id or not event:
            return jsonify({"error": "chat_id and event required"}), 400
        reply = run_agent(f"[אירוע מערכת]: {event}", chat_id)
        try:
            bot.send_message(chat_id, reply)
        except Exception as e:
            logger.error(f"[Worker] telegram: {e}")
        return jsonify({"status": "ok", "reply": reply[:200]}), 200
    except Exception as e:
        logger.error(f"[Worker] trigger error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "The Boss is Live v3.0 — CORE_02.6 Router ✅"


# ══════════════════════════════════════════════════
# F07 — Voice IVR (Twilio)
# ══════════════════════════════════════════════════

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    from feature_flags import is_enabled
    from voice_adapter import build_twiml, _say, _hangup, process_voice_step
    if not is_enabled("VOICE_IVR"):
        return Response(build_twiml(_say("השירות לא פעיל.") + _hangup()), mimetype="text/xml")
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    return Response(process_voice_step(call_sid, from_num), mimetype="text/xml")


@app.route("/voice/step", methods=["POST"])
def voice_step():
    from voice_adapter import process_voice_step
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    digits   = request.form.get("Digits", "")
    return Response(process_voice_step(call_sid, from_num, digits), mimetype="text/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
