# app.py ג€” The Boss Bot v3.0
# Architecture: Identity ג†’ Router ג†’ Context ג†’ Agent
#
# ׳›׳ ׳‘׳§׳©׳” ׳¢׳•׳‘׳¨׳×:
#   resolve_identity ג†’ route_request ג†’ build_context ג†’ run_agent

import os
import time
import hmac
import hashlib
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

# Step 5 — gateway alias consistency check (WARN only, does not block startup)
try:
    from tools.airtable_gateway import check_alias_consistency as _gw_check
    _gw_mismatches = _gw_check()
    if _gw_mismatches:
        import os as _os
        _owner = _os.environ.get("ELIYAHU_CHAT_ID", "")
        _token = _os.environ.get("TELEGRAM_TOKEN", "")
        if _owner and _token:
            import httpx as _httpx
            _httpx.post(
                f"https://api.telegram.org/bot{_token}/sendMessage",
                json={"chat_id": _owner, "text": "⚠️ Gateway alias mismatch:\n" + "\n".join(_gw_mismatches)},
                timeout=5,
            )
except Exception as _gw_e:
    logging.warning("gateway startup check failed: %s", _gw_e)

import anthropic
import telebot
from twilio.request_validator import RequestValidator
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
from feature_flags import is_enabled as _flag_enabled
import cost_monitor
import llm_fallback
try:
    from ad_attribution import inject_source_to_incoming_lead as _inject_utm
except ImportError:
    _inject_utm = None

logger = logging.getLogger(__name__)

# ג”€ג”€ג”€ ׳§׳‘׳•׳¢׳™׳ ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
MAX_TOOL_TURNS = 3

# ׳›׳׳™׳ ׳©׳×׳•׳¦׳׳×׳ ׳ ׳©׳׳¨׳× ׳‘׳–׳™׳›׳¨׳•׳ ׳׳¨׳¦׳™׳₪׳•׳× ׳‘׳™׳ ׳×׳•׳¨׳•׳×
_MEMORABLE_TOOLS = frozenset({
    "airtable_add", "airtable_update",
    "calendar_create_event", "gmail_send_draft",
})
AGENT_TIMEOUT  = 25

# ג”€ג”€ג”€ Pending Approvals (router-level) ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
# Saves messages routed to Handler.APPROVAL until the user confirms.
# key: chat_id (telegram user_id / whatsapp number)
_pending_approvals: dict[str, dict] = {}
_CONFIRM_WORDS = frozenset({"׳›׳", "׳׳©׳¨", "ג…", "yes", "y", "ok", "׳׳•׳§׳™", "׳‘׳¦׳¢", "׳§׳“׳™׳׳”"})
_CANCEL_WORDS  = frozenset({"׳׳", "׳‘׳˜׳", "ג", "no", "n", "׳‘׳™׳˜׳•׳", "׳¢׳¦׳•׳¨", "cancel"})

# ג”€ג”€ג”€ ׳§׳׳™׳™׳ ׳˜׳™׳ ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_APP_URL     = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")
WEBHOOK_SECRET     = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

if not WEBHOOK_SECRET:
    logging.getLogger(__name__).warning(
        "[Security] TELEGRAM_WEBHOOK_SECRET not set -- webhook URL is the only "
        "protection. Set this env var to enable header-based secret validation."
    )

# Router-level pending approvals expire after this many seconds.
_PENDING_APPROVAL_TTL = 600

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
bot    = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask(__name__)


def _empty_twiml() -> Response:
    return Response(str(MessagingResponse()), mimetype="application/xml")


def _is_junk_inbound_text(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    meaningful = [ch for ch in stripped if ch.isalnum()]
    if not meaningful:
        return True
    if len(meaningful) < 2:
        return True
    return False


def _public_request_url() -> str:
    # Prefer configured public URL to avoid trusting attacker-supplied X-Forwarded-Host.
    base = os.environ.get("RENDER_APP_URL", "").rstrip("/")
    if base:
        return f"{base}{request.full_path}".rstrip("?")
    proto = request.headers.get("X-Forwarded-Proto")
    if proto:
        return request.url.replace("http://", f"{proto}://", 1)
    return request.url


def _validate_twilio_signature() -> bool:
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    signature = request.headers.get("X-Twilio-Signature", "")
    if not token or not signature:
        logger.warning("[WhatsApp] missing Twilio auth token or signature")
        return False

    return RequestValidator(token).validate(
        _public_request_url(),
        request.form.to_dict(flat=True),
        signature,
    )

def _validate_meta_signature() -> bool:
    """X-Hub-Signature-256 מול META_APP_SECRET (HMAC-SHA256)."""
    app_secret = os.environ.get("META_APP_SECRET", "")
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not app_secret or not sig_header:
        logger.warning("[Meta WhatsApp] חסר app secret או חתימה")
        return False
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        request.get_data(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _normalize_meta_payload(payload: dict) -> dict | None:
    """
    מחזיר dict עם: text, from, to, msg_id.
    מחזיר None אם אין הודעה נכנסת (למשל קריאת status/read/delivery).
    """
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return None
        msg = messages[0]
        return {
            "text":   msg.get("text", {}).get("body", ""),
            "from":   msg.get("from", "unknown"),
            "to":     entry.get("metadata", {}).get("display_phone_number", "unknown"),
            "msg_id": msg.get("id", ""),
        }
    except (KeyError, IndexError, TypeError):
        return None


from tma_api import tma_api as _tma_blueprint
app.register_blueprint(_tma_blueprint)


# ── N05-B: send_followup.confirmed handler ────────────────────────────────────
# Sends the approved followup draft to the owner via Telegram for manual
# forwarding.9 Does NOT send outbound WhatsApp to lead (blocked on Meta, N05-C).

def _handle_send_followup_confirmed(payload: dict, chat_id: str) -> str:
    draft        = payload.get("draft", "")
    contact_name = payload.get("contact_name", "")
    channel      = payload.get("channel", "")
    memory_key   = payload.get("memory_key", "")

    msg = (f"📋 פולואפ מאושר — לשליחה ידנית ({channel}):\n"
           f"אל: {contact_name}\n\n{draft}")

    try:
        bot.send_message(chat_id, msg)
    except Exception as e:
        logger.error(f"[Followup] notify owner failed: {e}")
        return f"⚠️ שגיאה בהצגת הטיוטה: {e}"

    if memory_key:
        try:
            from lead_memory import lead_memory
            state = lead_memory.get(memory_key)
            lead_memory.update(memory_key, followup_count=state.followup_count + 1)
        except Exception as e:
            logger.warning(f"[Followup] followup_count update failed: {e}")

    return "✅ הטיוטה נשלחה אליך להעברה ידנית"


from event_bus import bus as _event_bus
_event_bus.subscribe("send_followup.confirmed", _handle_send_followup_confirmed)



def cmd_status(msg):
    """Owner ׳‘׳׳‘׳“ ג€” ׳׳¦׳‘ env vars."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    bot.send_message(msg.chat.id, format_startup_message(), parse_mode="Markdown")


@bot.message_handler(commands=["schema"])
def cmd_schema(msg):
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role != "owner":
        bot.send_message(msg.chat.id, "פקודה זו זמינה לבעלים בלבד.")
        return
    try:
        from schema_intelligence import handle_schema_command
        args = msg.text.replace("/schema", "", 1).replace(f"@{bot.get_me().username}", "").strip()
        reply = handle_schema_command(args)
        bot.send_message(msg.chat.id, reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_schema error: {e}")
        bot.send_message(msg.chat.id, f"שגיאה בטעינת סכמה: {e}")

@bot.message_handler(commands=["done"])
def cmd_done(msg):
    """/done [n] ג€” ׳׳¡׳׳ Quest ׳׳¡׳₪׳¨ n ׳›-Done + ׳›׳•׳×׳‘ Coins_Log ׳׳•׳˜׳•׳׳˜׳™׳×."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from tma_api import _at_list, _at_patch, _at_post, _coins_running_total
        from datetime import date, timedelta
        from airtable_schema import Tables, QuestsFields, CoinsLogFields, QuestStatus

        args = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split()) > 1 else ""
        if not args.isdigit():
            bot.send_message(msg.chat.id, "׳©׳™׳׳•׳©: /done [׳׳¡׳₪׳¨]  ג€”  ׳׳“׳•׳’׳׳”: /done 2")
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
            bot.send_message(msg.chat.id, f"׳׳¡׳₪׳¨ ׳׳ ׳×׳§׳™׳. ׳™׳© {len(week_quests)} Quests ׳”׳©׳‘׳•׳¢.")
            return

        quest      = week_quests[quest_num - 1]
        qf         = quest.get("fields", {})
        old_status = qf.get(QuestsFields.STATUS, "")
        name       = qf.get(QuestsFields.NAME, "?")

        if old_status == QuestStatus.DONE:
            bot.send_message(msg.chat.id, f"ג… {name} ׳›׳‘׳¨ ׳׳¡׳•׳׳ ׳›׳”׳•׳©׳׳.")
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
            f"ג… *{name}* ג€” ׳”׳•׳©׳׳\\!\n\\+{coins}נ×™",
            parse_mode="MarkdownV2",
        )
        logger.info(f"[Game] /done {quest_num} ג†’ {name} +{coins}נ×™ by {identity.display_name}")
    except Exception as e:
        logger.error(f"cmd_done error: {e}")
        bot.send_message(msg.chat.id, f"ג ׳©׳’׳™׳׳”: {e}")


@bot.message_handler(commands=["convert"])
def cmd_convert(msg):
    """/convert [׳©׳/׳˜׳׳₪׳•׳] ג€” ׳”׳•׳₪׳ ׳׳™׳“ ׳׳׳™׳© ׳§׳©׳¨ ׳‘-CRM (owner ׳‘׳׳‘׳“, ׳“׳•׳¨׳© LEAD_AUTO_CONVERT)."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from lead_conversion import convert_lead_to_contact
        query = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split()) > 1 else ""
        if not query:
            bot.send_message(msg.chat.id, "׳©׳™׳׳•׳©: /convert [׳©׳ ׳׳• ׳˜׳׳₪׳•׳ ׳©׳ ׳׳™׳“]")
            return

        ok, reply = convert_lead_to_contact(query)
        bot.send_message(msg.chat.id, reply, parse_mode="Markdown")
        logger.info(f"[LeadConvert] /convert '{query}' ג†’ {'OK' if ok else 'skip'} by {identity.display_name}")
    except Exception as e:
        logger.error(f"cmd_convert error: {e}")
        bot.send_message(msg.chat.id, f"ג ׳©׳’׳™׳׳”: {e}")


@bot.message_handler(commands=["quest"])
def cmd_quest(msg):
    """/quest ג€” Quest Log ׳”׳©׳‘׳•׳¢."""
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
            bot.send_message(msg.chat.id, "נ® ׳׳™׳ Quests ׳”׳©׳‘׳•׳¢.")
            return

        icons = {QuestStatus.DONE: "ג…", QuestStatus.IN_PROGRESS: "נ”„", QuestStatus.TODO: "ג¬", QuestStatus.SKIPPED: "ג­ן¸"}
        lines = [f"נ® *Quest Log ג€” {week_str}*\n"]
        total_possible = 0
        total_earned   = 0
        for r in quests:
            f       = r.get("fields", {})
            status  = f.get(QuestsFields.STATUS, "")
            coins   = int(f.get(QuestsFields.COINS, 0) or 0)
            impact  = " ג¡" if f.get(QuestsFields.IMPACT) else ""
            total_possible += coins
            if status == QuestStatus.DONE:
                total_earned += coins
            lines.append(f"{icons.get(status, 'ג“')} {f.get(QuestsFields.NAME, '?')} ג€” {coins}נ×™{impact}")

        lines.append(f"\nנ’° {total_earned}/{total_possible}נ×™ ׳”׳•׳©׳׳")
        bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_quest error: {e}")
        bot.send_message(msg.chat.id, f"ג ׳©׳’׳™׳׳”: {e}")


@bot.message_handler(commands=["coins"])
def cmd_coins(msg):
    """/coins ג€” ׳¡׳”׳´׳› ׳׳˜׳‘׳¢׳•׳× + World progress."""
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
            bar    = "ג–ˆ" * filled + "ג–‘" * (10 - filled)
            world_section = (
                f"\n\nנ *{wf.get(WorldsFields.NAME, 'World')}*\n"
                f"`{bar}` {pct}%\n"
                f"{earned}/{target}נ×™ | ׳₪׳¨׳¡: {wf.get(WorldsFields.PRIZE, '?')}"
            )

        bot.send_message(msg.chat.id, f"נ×™ *׳¡׳”׳´׳› ׳׳˜׳‘׳¢׳•׳×: {total_coins}*{world_section}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_coins error: {e}")
        bot.send_message(msg.chat.id, f"ג ׳©׳’׳™׳׳”: {e}")


_scheduler_thread = next(
    (t for t in threading.enumerate() if t.name == "scheduler" and t.is_alive()),
    None,
)
if _scheduler_thread:
    logger.info("[Scheduler] Already running ג€” skipping init")
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
        kwargs = {"url": f"{RENDER_APP_URL}/telegram"}
        if WEBHOOK_SECRET:
            kwargs["secret_token"] = WEBHOOK_SECRET
        bot.set_webhook(**kwargs)
        logger.info(f"Telegram Webhook set (secret={'yes' if WEBHOOK_SECRET else 'no'})")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# Integration Layer ג€” CORE_02.6
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•

def clarify_response(route: RouteDecision) -> str:
    logger.info(f"[CLARIFY] intent={route.intent} conf={route.confidence:.2f}")
    return route.response_override or "׳׳ ׳”׳¦׳׳—׳×׳™ ׳׳”׳‘׳™׳ ג€” ׳×׳•׳›׳ ׳׳ ׳¡׳— ׳׳—׳¨׳×?"


def approval_response(route: RouteDecision, original_text: str, chat_id: str,
                       channel: str, domain: str) -> str:
    """Saves original action and asks owner to confirm with ׳›׳/׳׳."""
    logger.info(f"[APPROVAL] intent={route.intent} domain={route.domain} | saved for {chat_id}")
    _pending_approvals[chat_id] = {
        "text":       original_text,
        "channel":    channel,
        "domain":     domain,
        "created_at": time.time(),
    }
    preview = original_text[:120] + ("ג€¦" if len(original_text) > 120 else "")
    return (
        f"ג³ *׳׳™׳©׳•׳¨ ׳ ׳“׳¨׳©*\n\n"
        f"׳₪׳¢׳•׳׳”: `{preview}`\n\n"
        f"׳¢׳ ׳” *׳›׳* ׳׳‘׳™׳¦׳•׳¢ ׳׳• *׳׳* ׳׳‘׳™׳˜׳•׳."
    )


# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# Approval Gate Helpers
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•

def _describe_tool_call(tool_name: str, inputs: dict) -> str:
    """׳×׳™׳׳•׳¨ ׳§׳¨׳™׳ ׳©׳ ׳§׳¨׳™׳׳× ׳›׳׳™ ׳׳›׳₪׳×׳•׳¨׳™ ׳׳™׳©׳•׳¨."""
    if tool_name == "gmail_send_draft":
        return f"נ“§ ׳©׳׳— ׳׳™׳™׳ (draft: {inputs.get('draft_id', '?')})"
    if tool_name == "calendar_create_event":
        start = str(inputs.get("start_time", "?"))[:16]
        return f"נ“… ׳§׳‘׳¢: {inputs.get('summary', '?')} ׳‘-{start}"
    if tool_name == "airtable_add":
        fields_str = str(inputs.get("fields", {}))[:50]
        return f"ג• ׳”׳•׳¡׳£ ׳-{inputs.get('table', '?')}: {fields_str}"
    if tool_name == "airtable_update":
        return f"גן¸ ׳¢׳“׳›׳ {inputs.get('record_id', '?')} ׳‘-{inputs.get('table', '?')}"
    if tool_name == "sheets_append":
        return f"נ“ ׳›׳×׳•׳‘ ׳-{inputs.get('sheet_name', '?')}"
    return f"ג¡ {tool_name}: {str(inputs)[:60]}"


def _queue_approval(tool_name: str, tool_inputs: dict,
                    user_chat_id: str, channel: str) -> str:
    """
    ׳©׳•׳׳¨ ׳₪׳¢׳•׳׳” ׳׳׳×׳™׳ ׳” ׳•׳©׳•׳׳— ׳‘׳§׳©׳× ׳׳™׳©׳•׳¨ ׳owner.
    ׳׳—׳–׳™׳¨ string ׳model: "ג³ ׳׳׳×׳™׳ ׳׳׳™׳©׳•׳¨..."
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
            telebot.types.InlineKeyboardButton("ג… ׳׳©׳¨", callback_data=f"approve:{action_id}"),
            telebot.types.InlineKeyboardButton("ג ׳‘׳˜׳",  callback_data=f"reject:{action_id}"),
        )
        try:
            bot.send_message(
                owner_chat_id,
                f"ג³ *׳‘׳§׳©׳× ׳׳™׳©׳•׳¨*\n\n{label}\n\n_ID: {action_id} | ׳₪׳’ ׳×׳•׳§׳£ ׳‘׳¢׳•׳“ 10 ׳“׳§׳•׳×_",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            logger.info(f"[Approval] ג… sent to owner {owner_chat_id} | {action_id}")
        except Exception as e:
            logger.error(f"[Approval] ג failed to notify owner: {e}")
            # BOSS NEVER FAKES: ׳׳ ׳׳—׳–׳™׳¨׳™׳ "׳׳׳×׳™׳ ׳׳׳™׳©׳•׳¨" ׳›׳©׳”׳©׳׳™׳—׳” ׳ ׳›׳©׳׳”
            return (
                f"ג ׳׳ ׳”׳¦׳׳—׳×׳™ ׳׳©׳׳•׳— ׳‘׳§׳©׳× ׳׳™׳©׳•׳¨ ׳׳‘׳¢׳׳™׳.\n"
                f"׳”׳₪׳¢׳•׳׳” ׳׳ ׳‘׳•׳¦׳¢׳”: {label}"
            )

    logger.info(f"[Approval] queued {action_id} | {tool_name} | user={user_chat_id}")
    return f"ג³ ׳”׳₪׳¢׳•׳׳” ׳׳׳×׳™׳ ׳” ׳׳׳™׳©׳•׳¨ ׳”׳‘׳¢׳׳™׳: {label}"


def _handle_approval_callback(cq) -> None:
    """׳׳˜׳₪׳ ׳‘׳׳—׳™׳¦׳” ׳¢׳ ג…/ג ׳©׳ ׳‘׳§׳©׳× ׳׳™׳©׳•׳¨."""
    from event_bus import bus

    data = cq.data or ""
    if ":" not in data:
        bot.answer_callback_query(cq.id, "ג ן¸ ׳ ׳×׳•׳ ׳™ callback ׳׳ ׳×׳§׳™׳ ׳™׳")
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
            bot.answer_callback_query(cq.id, "ג›” ׳׳™׳ ׳׳ ׳”׳¨׳©׳׳” ׳׳׳©׳¨ ׳₪׳¢׳•׳׳” ׳–׳•")
            return

    if action == "approve":
        # atomic pop ג€” ׳‘׳“׳™׳§׳× TTL ׳•׳׳—׳™׳§׳” ׳‘׳¦׳¢׳“ ׳׳—׳“
        item = bus.pop(action_id)
        if not item:
            bot.answer_callback_query(cq.id, "ג° ׳₪׳’ ׳×׳•׳§׳£ ג€” ׳”׳₪׳¢׳•׳׳” ׳׳ ׳§׳™׳™׳׳× ׳™׳•׳×׳¨")
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
            # Non-tool approval ג€” emit {action}.confirmed event
            bus_action = item.get("action", "")
            logger.info(f"[Approval] non-tool confirm {action_id} | action={bus_action}")
            from event_bus import bus as _bus
            result = _bus.emit(f"{bus_action}.confirmed", payload, user_chat_id)
            if result is None:
                result = f"ג ן¸ ׳׳™׳ handler ׳-{bus_action} ג€” ׳”׳₪׳¢׳•׳׳” ׳׳ ׳‘׳•׳¦׳¢׳”."
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
                bot.answer_callback_query(cq.id, "ג›” ׳”׳₪׳¢׳•׳׳” ׳›׳‘׳¨ ׳׳™׳ ׳” ׳׳•׳¨׳©׳™׳×")
                return

            raw    = dispatch_tool(tool_name, tool_inputs, identity)
            result = validate_tool_output(tool_name, raw)

        logger.info(f"[Approval] ג… confirmed {action_id} | {tool_name or item.get('action')}")

        try:
            bot.send_message(user_chat_id, f"ג… ׳”׳₪׳¢׳•׳׳” ׳‘׳•׳¦׳¢׳”:\n{result}")
        except Exception as e:
            logger.error(f"[Approval] notify user failed: {e}")

        try:
            bot.edit_message_text(
                f"ג… *׳׳•׳©׳¨ ׳•׳‘׳•׳¦׳¢*\n{item['label']}\n\n`{result[:200]}`",
                cq.message.chat.id, cq.message.message_id,
                parse_mode="Markdown",
            )
        except Exception:
            pass
        bot.answer_callback_query(cq.id, "ג… ׳‘׳•׳¦׳¢!")

    elif action == "reject":
        item = bus.pop(action_id)
        item = bus._pending.pop(action_id, None)  # atomic: remove + return in one step
        if item:
            logger.info("🚫 Rejected: %s | %s", action_id, item.get("label", item.get("action", "")))

        if item:
            user_chat_id = item["payload"].get("user_chat_id", "")
            if user_chat_id:
                try:
                    bot.send_message(user_chat_id, f"נ« ׳”׳₪׳¢׳•׳׳” ׳‘׳•׳˜׳׳”: {item['label']}")
                except Exception:
                    pass

        try:
            bot.edit_message_text(
                "נ« *׳‘׳•׳˜׳*",
                cq.message.chat.id, cq.message.message_id,
                parse_mode="Markdown",
            )
        except Exception:
            pass
        bot.answer_callback_query(cq.id, "נ« ׳‘׳•׳˜׳")

    else:
        bot.answer_callback_query(cq.id, "ג ן¸ ׳₪׳¢׳•׳׳” ׳׳ ׳׳•׳›׳¨׳×")


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
    ׳¢׳•׳˜׳£ ׳׳× route_request ׳¢׳ fallback.
    ׳›׳׳ ׳‘׳¨׳–׳ #9: ׳׳ Router ׳ ׳›׳©׳ ג€” ׳׳׳©׳™׳›׳™׳ ׳¢׳ intent=unknown, risk=review.
    ׳׳ ׳ ׳•׳₪׳׳™׳.
    """
    try:
        return route_request(
            text                = text,
            channel_raw         = channel,
            identity            = identity,
            domain_from_channel = domain_from_channel,
        )
    except Exception as e:
        logger.error(f"[Router] FAILED — fallback fail-closed: {e}", exc_info=True)
        from core.router.route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler
        return RouteDecision(
            channel           = channel,
            intent            = Intent.UNKNOWN,
            domain            = RouterDomain.GENERAL,
            risk              = Risk.NEEDS_APPROVAL,  # fail-closed: router error → require approval
            handler           = Handler.APPROVAL,
            needs_approval    = True,
            confidence        = 0.0,
            matched_rule      = "fallback",
            response_override = "",
        )


# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# run_agent ג€” Identity + Router + Agent Loop
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•

def run_agent(
    user_text:           str,
    chat_id:             str,
    channel:             str = "telegram",
    domain_from_channel: str = "",
    _skip_approval:      bool = False,
) -> str:

    # ג”€ג”€ 1. Identity ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    identity = resolve_identity(channel, chat_id)
    logger.info(f"[Identity] {identity}")
    if identity.role in (Role.READONLY, Role.GUEST):
        logger.warning(
            f"[Identity] LOW-PRIVILEGE request ג€” "
            f"channel={channel} id={chat_id} role={identity.role} "
            f"msg='{user_text[:60]}'"
        )

    # ג”€ג”€ 1.5. WhatsApp Lead Capture (W0) ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    # W0/N02: capture inbound WhatsApp leads and optionally score them.
    if identity.role == Role.LEAD:
        try:
            from lead_capture import capture_inbound_lead
            capture_inbound_lead(identity, user_text)
        except Exception as e:
            logger.error(f"[LeadCapture] failed for {identity.memory_key}: {e}")


    # ג”€ג”€ 2. Rate Limit ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    if not rate_limiter.is_allowed(identity.memory_key):
        return "ג ן¸ ׳™׳•׳×׳¨ ׳׳“׳™ ׳‘׳§׳©׳•׳×. ׳”׳׳×׳ ׳“׳§׳” ׳•׳ ׳¡׳” ׳©׳•׳‘."

    # ג”€ג”€ 2.5. Pending Approval Gate ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    pending = _pending_approvals.get(chat_id)
    if pending:
        if time.time() - pending.get("created_at", 0) > _PENDING_APPROVAL_TTL:
            _pending_approvals.pop(chat_id, None)
            logger.info("[PendingApproval] expired (>%ss) for %s",
                        _PENDING_APPROVAL_TTL, chat_id)
            pending = None
    if pending:
        lower = user_text.strip().lower()
        if lower in _CONFIRM_WORDS:
            _pending_approvals.pop(chat_id, None)
            logger.info(
                f"[PendingApproval] ג… confirmed by {chat_id} ג†’ "
                f"executing: {pending['text'][:60]}"
            )
            return run_agent(
                pending["text"], chat_id, channel,
                domain_from_channel=pending.get("domain", domain_from_channel),
                _skip_approval=True,
            )
        elif lower in _CANCEL_WORDS:
            _pending_approvals.pop(chat_id, None)
            logger.info(f"[PendingApproval] נ« cancelled by {chat_id}")
            return "נ« ׳”׳₪׳¢׳•׳׳” ׳‘׳•׳˜׳׳”."
        else:
            # New unrelated message ג€” clear stale pending, treat normally
            _pending_approvals.pop(chat_id, None)

    # ג”€ג”€ 3. Router ג€” CORE_02.6 Integration ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    route = _safe_route(user_text, channel, identity, domain_from_channel)
    logger.info(route.to_log())

    # ג”€ג”€ 4. Dispatch ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    if route.handler == Handler.CLARIFY:
        return clarify_response(route)

    if route.handler == Handler.APPROVAL and not _skip_approval:
        return approval_response(route, user_text, chat_id, channel, domain_from_channel)

    # ׳׳ ׳¢׳•׳©׳™׳ BLOCK ׳¨׳’׳™׳ ׳׳׳§׳•׳— ג€” restricted ׳׳׳©׳™׳ ׳׳¡׳•׳›׳
    if route.restricted:
        logger.warning(
            f"[Restricted] external request: "
            f"user={identity.user_id} role={identity.role} "
            f"intent={route.intent} notify_owner=True tool_allowed=False"
        )

    # ג”€ג”€ 5. Agent Loop ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
    if _flag_enabled("EMERGENCY_STOP_AI"):
        logger.warning(
            f"[CostWatchdog] EMERGENCY_STOP_AI active ג€” blocking agent for {identity.user_id}"
        )
        return "ג›” ׳׳¢׳¨׳›׳× ׳”-AI ׳‘׳¢׳¦׳™׳¨׳× ׳—׳™׳¨׳•׳ ׳¢׳§׳‘ ׳¢׳׳•׳× ׳’׳‘׳•׳”׳”. ׳ ׳¡׳” ׳©׳•׳‘ ׳׳׳•׳—׳¨ ׳™׳•׳×׳¨."

    try:
        research_mode = user_text.startswith("#") and identity.is_owner
        clean_msg     = user_text[1:].strip() if research_mode else user_text

        # Context ׳׳§׳‘׳ domain + handler ׳׳”׳¨׳׳•׳˜׳¨
        ctx = build_context(
            identity,
            user_text,
            domain  = route.domain,
            handler = route.handler,
            intent  = route.intent,
        )
        history = memory.get_for_claude(ctx.memory_key)

        # C4.1: trim history if too large ג€” prevents silent context overflow
        MAX_HISTORY_CHARS = 60_000
        if len(str(history)) > MAX_HISTORY_CHARS:
            logger.warning(
                f"[Agent] history too large ({len(str(history))} chars) "
                f"for {ctx.memory_key} ג€” trimming to last 6 messages"
            )
            history = history[-6:]

        messages = history + [{"role": "user", "content": clean_msg}]

        logger.info(
            f"[Agent] {ctx.identity_label} | "
            f"intent={route.intent} domain={route.domain} | "
            f"model={ctx.model} tools={len(ctx.allowed_tools)}"
        )

        final_reply     = "ג ן¸ ׳׳ ׳”׳×׳§׳‘׳׳” ׳×׳©׳•׳‘׳”."
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

            cost_monitor.record_call(
                model      = ctx.model,
                tokens_in  = getattr(response.usage, "input_tokens",  0),
                tokens_out = getattr(response.usage, "output_tokens", 0),
                caller     = ctx.memory_key,
            )
            try:
                from core.cost_watchdog import log_usage as _cw_log
                _src_type = "claude_sonnet" if "sonnet" in ctx.model else "claude_haiku"
                _cw_log(_src_type,
                        getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0),
                        {"caller": ctx.memory_key})
            except Exception:
                pass

            tool_uses   = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_uses:
                final_reply = text_blocks[0].text if text_blocks else "ג… ׳₪׳¢׳•׳׳” ׳”׳•׳©׳׳׳”."
                break

            if tool_calls_made >= MAX_TOOL_TURNS:
                logger.warning(
                    f"[Agent] reached max tool turns ({tool_calls_made}/{MAX_TOOL_TURNS}) "
                    f"for user={identity.user_id} role={identity.role} intent={route.intent}"
                )
                final_reply = (text_blocks[0].text if text_blocks
                               else "ג ן¸ ׳”׳’׳¢׳×׳™ ׳׳׳’׳‘׳׳× ׳”׳₪׳¢׳•׳׳•׳× ׳׳¨׳™׳¦׳” ׳–׳•. ׳ ׳¡׳” ׳׳₪׳¨׳§ ׳׳× ׳”׳‘׳§׳©׳” ׳׳©׳׳‘׳™׳.")
                break

            # ג”€ג”€ Tool Loop ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
            tool_results = []
            for tu in tool_uses:
                if not route.tool_allowed:
                    logger.info(f"[Tool] Silently blocked by route (restricted): {tu.name}")
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tu.id,
                        "content":     "׳”׳‘׳§׳©׳” ׳”׳×׳§׳‘׳׳” ׳•׳×׳•׳¢׳‘׳¨ ׳׳˜׳™׳₪׳•׳.",
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

                # ג”€ג”€ Approval Gate ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
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
                logger.info(f"[Tool] ג†’ {result[:80]}")

                # A32 ג€” verify tool actually succeeded
                exec_check = verify_execution(tu.name, result)
                if exec_check.status == "failed":
                    logger.error(f"[A32] Execution failed: {tu.name} ג€” {exec_check.reason}")
                    result = f"ג ׳”׳₪׳¢׳•׳׳” ׳׳ ׳”׳•׳©׳׳׳”: {exec_check.reason}"
                elif exec_check.status == "warn":
                    logger.warning(f"[A32] Execution warn: {tu.name} ג€” {exec_check.reason}")

                # Fix 2: persist successful write results for next-turn memory
                if tu.name in _MEMORABLE_TOOLS and "ג" not in result:
                    memory.add(
                        ctx.memory_key,
                        "user",   # only "user"/"assistant" valid in Claude messages[]
                        f"[נ”§ {tu.name}]: {str(tu.input)[:60]} ג†’ {result[:60]}"
                    )

                entry = {"type": "tool_result", "tool_use_id": tu.id, "content": result}
                tool_results.append(entry)
                tool_results_log.append(entry)   # A32: accumulate for final check

            tool_calls_made += 1

            # ג³ keep typing indicator alive between tool calls
            if channel == "telegram":
                try:
                    bot.send_chat_action(chat_id, "typing")
                except Exception:
                    pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

        # A32 ג€” final hallucination check before reply reaches user
        final_reply = sanitize_agent_response(final_reply, tool_results_log)

        # ג”€ג”€ ׳©׳׳™׳¨׳× ׳–׳™׳›׳¨׳•׳ ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
        memory.add(ctx.memory_key, "user",      clean_msg)
        memory.add(ctx.memory_key, "assistant", final_reply)

        return final_reply

    except anthropic.APIStatusError as e:
        logger.error(f"[Agent] Anthropic {e.status_code}: {e.message}")
        _transient = e.status_code in (429, 529) or e.status_code >= 500
        if _transient and _flag_enabled("LLM_FALLBACK"):
            logger.warning(f"[Agent] Claude transient error {e.status_code} — OpenAI fallback for {chat_id}")
            try:
                fallback = llm_fallback.call_openai_text(
                    source="run_agent.status_error",
                    messages=[{"role": "user", "content": clean_msg}],
                    system=ctx.system_prompt,
                    max_tokens=ctx.max_tokens,
                )
                return sanitize_agent_response(fallback, [])
            except Exception as fe:
                logger.error(f"[Agent] OpenAI fallback failed: {fe}")
        if e.status_code == 413:
            return "❗ ההודעה ארוכה מדי. נסה לשלוח קצר יותר."
        return f"מצטערים, יש תקלה זמנית ({e.status_code}). ננסה שוב בקרוב."
    except anthropic.APITimeoutError:
        logger.error(f"[Agent] Timeout for {chat_id}")
        if _flag_enabled("LLM_FALLBACK"):
            try:
                fallback = llm_fallback.call_openai_text(
                    source="run_agent.timeout",
                    messages=[{"role": "user", "content": clean_msg}],
                    system=ctx.system_prompt,
                    max_tokens=ctx.max_tokens,
                )
                return sanitize_agent_response(fallback, [])
            except Exception as fe:
                logger.error(f"[Agent] OpenAI fallback also failed: {fe}")
        return "מצטערים, יש תקלה זמנית. ננסה שוב בקרוב."
    except Exception as e:
        logger.error(f"[Agent] error: {e}", exc_info=True)
        return "משהו השתבש. נסה שוב."


# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# Endpoints
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•

@app.route("/health", methods=["GET"])
def health():
    health_status = get_health_status(globals().get("_scheduler"), memory)
    return jsonify({"status": health_status["status"]}), 200


@app.route("/telegram", methods=["POST"])
def webhook_telegram():
    if request.headers.get("content-type") != "application/json":
        abort(403)
    if not WEBHOOK_SECRET:
        logger.error("[Webhook] TELEGRAM_WEBHOOK_SECRET not set — rejecting (fail-closed)")
        logger.error("[Webhook] WEBHOOK_SECRET not set — rejecting request (fail-closed)")
        abort(403)
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
        reply_chat_id  = str(update.message.chat.id)       # ׳׳׳ ׳׳©׳׳•׳— (group ׳׳• private)
        sender_user_id = str(update.message.from_user.id)  # ׳׳™ ׳©׳׳— (׳×׳׳™׳“ USER_ID)
        text           = update.message.text

        # Slash commands ג†’ registered @bot.message_handler(commands=[...]) handlers.
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
                    "ג™»ן¸ ׳”׳”׳•׳“׳¢׳” ׳”׳–׳• ׳›׳‘׳¨ ׳˜׳•׳₪׳׳”.\n"
                    "׳׳ ׳–׳• ׳‘׳§׳©׳” ׳—׳“׳©׳” ג€” ׳ ׳¡׳— ׳׳•׳×׳” ׳׳—׳¨׳×."
                )
            except Exception as e:
                logger.debug(f"[Idempotency] notify failed: {e}")
            return "", 200

        # ג”€ג”€ Thinking Indicator ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€ג”€
        thinking_msg_id = None
        try:
            thinking_msg    = bot.send_message(reply_chat_id, "ג³")
            thinking_msg_id = thinking_msg.message_id
        except Exception:
            pass

        # typing thread ׳›׳’׳™׳‘׳•׳™ (׳׳׳§׳¨׳” ׳©-ג³ ׳׳ ׳ ׳©׳׳—)
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
    if not _validate_twilio_signature():
        return Response("Forbidden", status=403)

    incoming  = request.values.get("Body", "").strip()
    sender_raw = request.values.get("From", "whatsapp:unknown")
    sender     = sender_raw.removeprefix("whatsapp:")   # "+972XXXXXXXXX"
    to_number  = request.values.get("To",   "whatsapp:unknown")
    msg_sid   = request.values.get("MessageSid", "")

    if _is_junk_inbound_text(incoming):
        logger.info("[WhatsApp] junk inbound ignored before LLM")
        return _empty_twiml()

    # domain ׳׳₪׳™ ׳׳¡׳₪׳¨ ׳”׳™׳¢׳“ ג€” Layer 1 ׳©׳ domain_router
    domain_from_channel = _channel_domain(to_number)

    dedup_key = msg_sid if msg_sid else incoming
    if idempotency.is_duplicate("whatsapp", sender, dedup_key):
        return _empty_twiml()

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


# ════════════════════════════════════════════════════════════════
# F05a — Meta WhatsApp Cloud API (Phase 1 — inbound only)
# ════════════════════════════════════════════════════════════════

@app.route("/webhooks/meta/whatsapp", methods=["GET", "POST"])
def webhook_meta_whatsapp():
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge", "")
        expected_token = os.environ.get("META_VERIFY_TOKEN", "")
        if mode == "subscribe" and expected_token and token == expected_token:
            return challenge, 200
        logger.warning("[Meta WhatsApp] אימות GET נכשל")
        return "Forbidden", 403

    # ── POST ──────────────────────────────────────────────────────
    if _flag_enabled("EMERGENCY_STOP_WHATSAPP"):
        logger.warning("[Meta WhatsApp] EMERGENCY_STOP_WHATSAPP פעיל — מתעלם")
        return jsonify({"status": "stopped"}), 200

    if not _validate_meta_signature():
        return Response("Forbidden", status=403)

    payload    = request.get_json(silent=True) or {}
    normalized = _normalize_meta_payload(payload)
    if normalized is None:
        return jsonify({"status": "ignored"}), 200

    incoming      = normalized["text"]
    sender        = normalized["from"]
    to_number     = normalized["to"]
    msg_id        = normalized["msg_id"]

    if _is_junk_inbound_text(incoming):
        logger.info("[Meta WhatsApp] junk inbound — מתעלם לפני LLM")
        return jsonify({"status": "ignored"}), 200

    if idempotency.is_duplicate("whatsapp_meta", sender, msg_id):
        return jsonify({"status": "duplicate"}), 200

    domain_from_channel = _channel_domain(to_number)

    reply = run_agent(
        incoming, sender,
        channel             = "whatsapp",
        domain_from_channel = domain_from_channel,
    )

    # Outbound — stub כנה: מחשב תשובה, לא שולח (Phase 1)
    logger.info("[Meta WhatsApp] תשובה נוצרה (stub — לא נשלחה): %s", reply[:100])
    return jsonify({"status": "received"}), 200


WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    auth_header = request.headers.get("Authorization", "")
    if not WORKER_SECRET or auth_header != f"Bearer {WORKER_SECRET}":
        logger.warning(f"[Worker] unauthorized attempt from {request.remote_addr}")
        return jsonify({"error": "unauthorized"}), 401
    try:
        # chat_id is never accepted from the caller — always derived from server config
        # to prevent impersonation even if WORKER_SECRET leaks.
        owner_chat_id = os.environ.get("ELIYAHU_CHAT_ID", "").strip()
        if not owner_chat_id:
            logger.error("[Worker] ELIYAHU_CHAT_ID not configured")
            return jsonify({"error": "server misconfiguration"}), 503
        payload = request.get_json(force=True) or {}
        event   = payload.get("event", "")
        if not event:
            return jsonify({"error": "event required"}), 400
        reply = run_agent(f"[system event]: {event}", owner_chat_id)
        try:
            bot.send_message(owner_chat_id, reply)
        except Exception as e:
            logger.error(f"[Worker] telegram: {e}")
        return jsonify({"status": "ok", "reply": reply[:200]}), 200
    except Exception as e:
        logger.error(f"[Worker] trigger error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "The Boss is Live v3.0 ג€” CORE_02.6 Router ג…"


# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•
# F07 ג€” Voice IVR (Twilio)
# ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•ג•

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    if not _validate_twilio_signature():
        from_num = request.form.get("From", "unknown")
        logger.warning("[Voice] invalid Twilio signature from %s — possible spoofing", from_num)
        return Response("Forbidden", status=403)
    from feature_flags import is_enabled
    from voice_adapter import build_twiml, _say, _hangup, process_voice_step
    if not is_enabled("VOICE_IVR"):
        return Response(build_twiml(_say("׳”׳©׳™׳¨׳•׳× ׳׳ ׳₪׳¢׳™׳.") + _hangup()), mimetype="text/xml")
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    return Response(process_voice_step(call_sid, from_num), mimetype="text/xml")


@app.route("/voice/step", methods=["POST"])
def voice_step():
    if not _validate_twilio_signature():
        from_num = request.form.get("From", "unknown")
        logger.warning("[Voice] invalid Twilio signature from %s — possible spoofing", from_num)
        return Response("Forbidden", status=403)
    from voice_adapter import process_voice_step
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    digits   = request.form.get("Digits", "")
    return Response(process_voice_step(call_sid, from_num, digits), mimetype="text/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
