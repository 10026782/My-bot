# app.py — The Boss Bot v3.0
# Architecture: Identity → Router → Context → Agent
#
# כל בקשה עוברת:
#   resolve_identity → route_request → build_context → run_agent

import os
import re
import time
import uuid
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
from tools.airtable_security import enforce_leads_write_gate, LeadsDirectWriteBlocked
from guards          import idempotency, rate_limiter, validate_tool_output
from config          import get_domain as _channel_domain
from core.router     import route_request, RouteDecision, Handler
from core.router.deterministic_denial import check_deterministic_denial
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
# BUG-070 fix: value is now a dict of {approval_id: entry}, not a single
# entry — a chat_id can have multiple pending approvals queued at once.
# Each entry carries its own "display_index" (1, 2, 3...) so users can
# reply with a bare number ("1", "2") to disambiguate, matching the UX
# promise made elsewhere in the bot (e.g. daily_collector.py).
_pending_approvals: dict[str, dict[str, dict]] = {}
# LL-13: guards _pending_approvals against TOCTOU double-execution — two
# near-simultaneous requests for the same chat_id (duplicate webhook delivery,
# fast double "כן") must not both observe-then-act on the same pending entry.
_pending_approvals_lock = threading.Lock()
_CONFIRM_WORDS = frozenset({
    "כן", "אשר", "מאשר", "מאשרת", "✅", "yes", "y", "ok", "אוקי", "בצע", "קדימה",
})
_CANCEL_WORDS  = frozenset({"לא", "בטל", "❌", "no", "n", "ביטול", "עצור", "cancel"})

# ─── קליינטים ──────────────────────────────────────
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
telebot.apihelper.ENABLE_MIDDLEWARE = True  # נדרש לפני TeleBot() — אחרת middleware_handler לא נרשם
bot    = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)  # webhook mode — handlers ירוצו סינכרונית, לפני שה-response חוזר


@bot.middleware_handler(update_types=['message'])
def log_all_exceptions(bot_instance, update):
    pass


def handle_telebot_error(exception):
    logger.error(f"[Telebot] unhandled: {exception}", exc_info=True)


bot.exception_handler = handle_telebot_error

app = Flask(__name__)


def _empty_twiml() -> Response:
    return Response(str(MessagingResponse()), mimetype="application/xml")


def _gateway_whatsapp_reply(
    sender: str,
    body: str,
    domain: str,
    source_ref: str,
    source_module: str = "app.webhook_whatsapp",
) -> str | None:
    """
    מעביר את תשובת ה-WhatsApp ללקוח דרך C52 Customer Output Gateway לפני TwiML reply.
    Gateway קובע APPROVED/ESCALATED (Financial Gate) על הגוף בפועל; השליחה הסינכרונית
    עדיין נעשית ע"י Twilio מתוך ה-TwiML response (whatsapp_adapter הוא honest stub —
    ראה C38/C52). מחזיר את הגוף לשליחה, או None אם EMERGENCY_STOP (אין תשובה כלל).
    BUG-SB-01: source_module="action_gateway" מועבר כשהגוף הגיע מ-ActionGateway —
    מונע Single Speaker false-block על GatewayReply לגיטימי.
    """
    from core.output_gateway import send_outbound, OutboundEnvelope, AudienceClass, OutputChannel
    result = send_outbound(OutboundEnvelope(
        channel=OutputChannel.TWILIO_WHATSAPP,
        recipient=sender,
        body=body,
        audience=AudienceClass.CUSTOMER,
        source_module=source_module,
        source_ref=source_ref,
        domain=domain,
        meta={"source_type": "llm_response"},
    ))
    if result.status == "EMERGENCY_STOP":
        return None
    if result.status == "ESCALATED":
        return "אני מעביר את זה לבדיקה ידנית, ויחזרו אליך עם תשובה מדויקת."
    return body


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


def _sanitize_id(raw_id) -> str:
    """BUG-072: log a short, non-reversible fingerprint instead of a raw
    phone number / Telegram chat/user id. Same input always yields the same
    fingerprint, so repeated log lines for the same identity can still be
    correlated for debugging without exposing the identifier itself."""
    if not raw_id:
        return "?"
    return hashlib.sha256(str(raw_id).encode()).hexdigest()[:8]


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
    מחזיר dict עם: text, from, to, msg_id, media (optional).
    מחזיר None אם אין הודעה נכנסת (למשל קריאת status/read/delivery).

    BUG-071 FIX: Extracts media metadata (image/video/audio/document).
    Media handling is async — download URLs fetched on demand via Meta API.
    """
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return None
        msg = messages[0]

        result = {
            "text":   msg.get("text", {}).get("body", ""),
            "from":   msg.get("from", "unknown"),
            "to":     entry.get("metadata", {}).get("display_phone_number", "unknown"),
            "msg_id": msg.get("id", ""),
            "media":  None,  # populated if media present
        }

        # Extract media metadata (type + media_id for URL fetch)
        msg_type = msg.get("type", "text")
        if msg_type in ("image", "video", "audio", "document"):
            try:
                from meta_whatsapp_media_adapter import extract_meta_whatsapp_media
                media = extract_meta_whatsapp_media(msg)
                if media:
                    result["media"] = media
            except Exception as e:
                logger.warning(f"[Meta WhatsApp] media extraction failed: {e}")

        return result
    except (KeyError, IndexError, TypeError):
        return None


from tma_api import tma_api as _tma_blueprint
app.register_blueprint(_tma_blueprint)


# ── N05-B: send_followup.confirmed handler ────────────────────────────────────
# Sends the approved followup draft to the owner via Telegram for manual
# forwarding.9 Does NOT send outbound WhatsApp to lead (blocked on Meta, N05-C).
# C52: owner notification routed through core.output_gateway (TELEGRAM_OWNER is
# always INTERNAL — no Financial Gate, no behavior change vs. direct bot.send_message).

def _handle_send_followup_confirmed(payload: dict, chat_id: str) -> str:
    draft        = payload.get("draft", "")
    contact_name = payload.get("contact_name", "")
    channel      = payload.get("channel", "")
    memory_key   = payload.get("memory_key", "")

    msg = (f"📋 פולואפ מאושר — לשליחה ידנית ({channel}):\n"
           f"אל: {contact_name}\n\n{draft}")

    try:
        from core.output_gateway import send_outbound, OutboundEnvelope, AudienceClass, OutputChannel
        send_outbound(OutboundEnvelope(
            channel=OutputChannel.TELEGRAM_OWNER,
            recipient=chat_id,
            body=msg,
            audience=AudienceClass.INTERNAL,
            source_module="app.send_followup_confirmed",
            source_ref=memory_key,
            domain="followup",
        ))
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


# ── C53 FIX-1: send_recovery.confirmed handler ────────────────────────────
# lead_recovery.request_recovery_approval() שולח action="send_recovery" —
# ללא handler זה emit מחזיר None ומדפיס שגיאה שקטה. מבנה הפאיילוד
# תואם ל-core/lead_recovery.py:227-234.
# לא שולח WhatsApp ללקוח (Meta blocked, N05-C) — רק מעביר לבעלים.

def _handle_send_recovery_confirmed(payload: dict, chat_id: str) -> str:
    draft        = payload.get("draft", "")
    contact_name = payload.get("contact_name", "")
    channel      = payload.get("channel", "")
    memory_key   = payload.get("memory_key", "")
    tier         = payload.get("tier", "")

    msg = (f"♻️ Recovery מאושר — לשליחה ידנית ({channel}, {tier}):\n"
           f"אל: {contact_name}\n\n{draft}")

    try:
        from core.output_gateway import send_outbound, OutboundEnvelope, AudienceClass, OutputChannel
        result = send_outbound(OutboundEnvelope(
            channel=OutputChannel.TELEGRAM_OWNER,
            recipient=chat_id,
            body=msg,
            audience=AudienceClass.INTERNAL,
            source_module="app.send_recovery_confirmed",
            source_ref=memory_key,
            domain="recovery",
        ))
    except Exception as e:
        logger.error(f"[Recovery] notify owner failed: {e}")
        return f"⚠️ שגיאה בהצגת הטיוטה: {e}"

    owner_delivery = getattr(result, "action_result", None)
    if not owner_delivery or not owner_delivery.delivery_success:
        logger.error(
            "[Recovery] owner draft delivery not verified | memory_key=%s audit=%s",
            memory_key,
            getattr(result, "audit_id", ""),
        )
        return "⚠️ האישור נקלט, אך מסירת הטיוטה אליך לא אומתה. ה-recovery לא סומן כהושלם."

    # Delivery to TELEGRAM_OWNER is only a draft preview. It is not evidence
    # that the customer received the recovery message, so recovery_count must
    # remain unchanged until a customer-capable adapter confirms delivery.
    return "✅ הטיוטה נשלחה אליך להעברה ידנית"


_event_bus.subscribe("send_recovery.confirmed", _handle_send_recovery_confirmed)



@bot.message_handler(commands=["status"])
def cmd_status(msg):
    """Owner בלבד — מצב env vars."""
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
    """/done [n] — מסמן Quest מספר n כ-Done + כותב Coins_Log אוטומטית."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    try:
        from tma_api import _at_list, _at_patch, _at_post
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


# ── C20: /update command ─────────────────────────────────────────
try:
    from cmd_update import register_update_command
    result = register_update_command(bot, resolve_identity)
    logger.info("[C20] /update command registered")
    logger.info(f"[app] register_update_command returned: {result}")
except Exception as _e:
    logger.warning(f"[C20] /update registration failed: {_e}")

# ── Decision Hub (Stage 0): /decision command ────────────────────
try:
    from cmd_decision import register_decision_command
    result = register_decision_command(bot, resolve_identity)
    logger.info("[DecisionHub] /decision command registered")
    logger.info(f"[app] register_decision_command returned: {result}")
except Exception as _e:
    logger.warning(f"[DecisionHub] /decision registration failed: {_e}")

# ── C22: weekly summary callbacks ────────────────────────────────
try:
    from weekly_summary import register_weekly_callbacks
    register_weekly_callbacks(bot)
    logger.info("[C22] weekly summary callbacks registered")
except Exception as _e:
    logger.warning(f"[C22] weekly summary registration failed: {_e}")

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
        kwargs = {"url": f"{RENDER_APP_URL}/telegram"}
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


def _add_pending_approval(chat_id: str, entry: dict) -> str:
    """
    BUG-070: מוסיף approval חדש לרשימת הממתינים של chat_id בלי לדרוס
    approvals קיימים. מחזיר approval_id ייחודי. חייב להיקרא תחת
    _pending_approvals_lock (עקבי עם LL-13).
    """
    approval_id = uuid.uuid4().hex[:8]
    bucket = _pending_approvals.setdefault(chat_id, {})
    entry["display_index"] = len(bucket) + 1
    bucket[approval_id] = entry
    return approval_id


def _resolve_pending_reply(chat_id: str, user_text: str) -> tuple[str, dict] | None:
    """
    BUG-070: מפענח תשובת משתמש מול רשימת ה-approvals הממתינים של chat_id.
    - אם הטקסט מכיל מספר -> מחפש entry עם display_index תואם.
    - אם אין מספר וקיים ממתין יחיד -> מחזיר אותו (backward compatible
      עם ההתנהגות הקודמת, פשוט "כן"/"לא" בלי מספר).
    - אם אין מספר ויש כמה ממתינים -> מחזיר None (לא מנחשים).
    חייב להיקרא תחת _pending_approvals_lock.
    מחזיר (approval_id, entry) או None; לא מסיר מהמפה (caller אחראי לזה).
    """
    bucket = _pending_approvals.get(chat_id)
    if not bucket:
        return None

    match = re.search(r"\d+", user_text)
    if match:
        target_index = int(match.group())
        for approval_id, entry in bucket.items():
            if entry.get("display_index") == target_index:
                return approval_id, entry
        return None  # מספר לא תואם אף approval ממתין

    if len(bucket) == 1:
        approval_id, entry = next(iter(bucket.items()))
        return approval_id, entry

    return None  # כמה ממתינים, אין מספר -> דורשים הבהרה, לא מנחשים


def _pop_pending_approval(chat_id: str, approval_id: str) -> dict | None:
    """מסיר approval ספציפי בלי לגעת בשאר הממתינים לאותו chat_id."""
    bucket = _pending_approvals.get(chat_id)
    if not bucket:
        return None
    entry = bucket.pop(approval_id, None)
    if not bucket:
        _pending_approvals.pop(chat_id, None)
    return entry


def _pending_clarification_message(chat_id: str) -> str:
    """כשיש כמה approvals ממתינים ואין מספר בתשובה — מציג רשימה וממתין להבהרה."""
    bucket = _pending_approvals.get(chat_id, {})
    lines = ["⏳ יש כמה פעולות ממתינות לאישור. ענה במספר:"]
    for entry in sorted(bucket.values(), key=lambda e: e["display_index"]):
        preview = entry["text"][:80] + ("…" if len(entry["text"]) > 80 else "")
        lines.append(f"{entry['display_index']}. `{preview}`")
    return "\n".join(lines)


# SPEC Preview Content Fix (Site #4) — wording-only clarification that the
# preview text above is the user's raw request, not the actual action that
# will run; the real tool call is only decided when the Agent re-runs at
# confirm-time (see run_agent's recursive _skip_approval=True call). Does
# NOT change the "run again" architecture itself — that's a deliberate
# cost/latency + context-freshness trade-off, documented separately.
CONFIRMATION_SUFFIX = (
    "\n\nℹ️ הפרטים המדויקים ייקבעו כשאכין את הפעולה בפועל, "
    "ותוכל לבדוק ולאשר לפני שהיא מתבצעת."
)


def approval_response(route: RouteDecision, original_text: str, chat_id: str,
                       channel: str, domain: str) -> str:
    """Saves original action and asks owner to confirm with כן/לא."""
    logger.info(f"[APPROVAL] intent={route.intent} domain={route.domain} | saved for {_sanitize_id(chat_id)}")
    with _pending_approvals_lock:
        approval_id = _add_pending_approval(chat_id, {
            "text":       original_text,
            "channel":    channel,
            "domain":     domain,
            "created_at": time.time(),
        })
        pending_count = len(_pending_approvals.get(chat_id, {}))
    preview = original_text[:120] + ("…" if len(original_text) > 120 else "")
    if pending_count > 1:
        # BUG-070: כשיש כבר ממתין אחר, מציינים את המספר לתשובה חד-משמעית.
        display_index = _pending_approvals[chat_id][approval_id]["display_index"]
        return (
            f"⏳ *אישור נדרש* (#{display_index})\n\n"
            f"פעולה: `{preview}`\n\n"
            f"ענה *כן {display_index}* לביצוע או *לא {display_index}* לביטול."
            f"{CONFIRMATION_SUFFIX}"
        )
    return (
        f"⏳ *אישור נדרש*\n\n"
        f"פעולה: `{preview}`\n\n"
        f"ענה *כן* לביצוע או *לא* לביטול."
        f"{CONFIRMATION_SUFFIX}"
    )


# ══════════════════════════════════════════════════
# Approval Gate Helpers
# ══════════════════════════════════════════════════

# SPEC Preview Content Fix (Site #3) — Contract Chain (10/07/2026) grepped
# airtable_schema.py for every phone/email/internal-identifier-shaped field
# key across all table classes, not just LeadFields. Tables with Hebrew
# schemas (e.g. ContactFields in "אנשי קשר (Contacts)") use "טלפון"/"אימייל"
# as the literal field key Claude passes in tool inputs — the English-only
# set from the original spec draft would silently leave those unmasked.
# "email"/"אימייל" included alongside phone for the same PII reasoning even
# though it wasn't in the original 4; "external_id" added because it's the
# same class of internal dedup/routing key as sender_id/memory_key/tenant_id
# (LeadFields.EXTERNAL_ID — "gmail:<msg_id>", not shown to a human approver).
_SENSITIVE_FIELD_KEYS = {
    "phone", "sender_id", "memory_key", "tenant_id", "external_id",
    "email", "טלפון", "אימייל",
}


def _format_field_value(key: str, value) -> str:
    """מסך שדות רגישים, וחותך ערכים ארוכים בבטחה."""
    if key.lower() in _SENSITIVE_FIELD_KEYS:
        s = str(value)
        return s[:2] + "*" * max(len(s) - 4, 0) + s[-2:] if len(s) > 4 else "****"
    s = str(value)
    if len(s) > 80:
        return s[:80] + "..."
    return s


def _describe_tool_call(tool_name: str, inputs: dict) -> str:
    """תיאור קריא של קריאת כלי לכפתורי אישור."""
    if tool_name == "gmail_send_draft":
        return f"📧 שלח מייל (draft: {inputs.get('draft_id', '?')})"
    if tool_name == "calendar_create_event":
        start = str(inputs.get("start_time", "?"))[:16]
        return f"📅 קבע: {inputs.get('summary', '?')} ב-{start}"
    if tool_name == "airtable_add":
        fields = inputs.get("fields", {})
        if not isinstance(fields, dict):
            return f"➕ הוסף ל-{inputs.get('table', '?')}: [?]"
        fields_preview = "\n".join(
            f"  • {k}: {_format_field_value(k, v)}" for k, v in fields.items()
        )
        return f"➕ הוסף ל-{inputs.get('table', '?')}:\n{fields_preview}"
    if tool_name == "airtable_update":
        fields = inputs.get("fields", {})
        if not isinstance(fields, dict):
            return f"✏️ עדכן {inputs.get('record_id', '?')} ב-{inputs.get('table', '?')}"
        fields_preview = "\n".join(
            f"  • {k}: {_format_field_value(k, v)}" for k, v in fields.items()
        )
        return f"✏️ עדכן {inputs.get('record_id', '?')} ב-{inputs.get('table', '?')}:\n{fields_preview}"
    if tool_name == "sheets_append":
        return f"📊 כתוב ל-{inputs.get('sheet_name', '?')}"
    return f"⚡ {tool_name}: {str(inputs)[:60]}"


def _write_execution_receipt(
    canonical_user_id: str, origin_channel: str, origin_chat_id: str,
    action_id: str, tool_name: str, result: str,
) -> None:
    """
    Stage A: ל-origin_channel שאינו טלגרם — אין נתיב outbound בדוק.
    מתעד ביצוע ב-log בלבד, ללא ניסיון שליחה.
    """
    logger.info(
        "[Approval] origin_channel=%s no outbound (Stage A) | action_id=%s "
        "canonical=%s chat=%s tool=%s result=%.80s",
        origin_channel, action_id, canonical_user_id, origin_chat_id, tool_name, result,
    )


def _queue_approval(tool_name: str, tool_inputs: dict,
                    user_chat_id: str, channel: str) -> str:
    """
    שומר פעולה ממתינה ושולח בקשת אישור לowner.
    מחזיר string לmodel: "⏳ ממתין לאישור..."
    PR #188: blocks re-queuing via executed_action_cache (raw chat_id fingerprint).
    Stage A: also dedupes cross-channel via canonical identity.memory_key.
    """
    from event_bus import bus, executed_action_cache
    fp = executed_action_cache.compute(user_chat_id, tool_name, tool_inputs)
    if executed_action_cache.is_recently_executed(fp):
        logger.warning(
            f"[Approval] duplicate fingerprint blocked: {fp[:8]} | {tool_name} | user={_sanitize_id(user_chat_id)}"
        )
        return f"⚠️ פעולה זו כבר בוצעה לאחרונה ({tool_name}). כפילות נחסמה."

    # Stage A: canonical dedup — אותה זהות עסקית מ-channel שני
    identity = resolve_identity(channel, user_chat_id)
    existing = bus.find_pending_by_business_fingerprint(
        canonical_user_id=identity.memory_key,
        tool_name=tool_name,
        normalized_inputs=tool_inputs,
    )
    if existing:
        origin = existing.get("origin_channel") or existing.get("payload", {}).get("origin_channel", "")
        logger.info(
            f"[Approval] cross-channel duplicate suppressed | {existing['action_id']} "
            f"| canonical={identity.memory_key} | tool={tool_name}"
        )
        return f"⏳ הפעולה כבר ממתינה לאישור הבעלים{' (מ-' + origin + ')' if origin else ''}."

    label     = _describe_tool_call(tool_name, tool_inputs)

    # Stage B (shadow mode): ActionGateway ב-FEATURE_ACTION_GATEWAY=false.
    # propose_action רושם contract ל-ledger ולמעקב — לא חוסם את המסלול הקיים.
    # כאשר הדגל פעיל: GatewayResult(ok=False) יחזיר כאן ויפסיק את הזרימה.
    from feature_flags import is_enabled as _flag
    if _flag("FEATURE_ACTION_GATEWAY"):
        from core.action_gateway import action_gateway as _gw
        tenant_id = getattr(identity, "tenant_id", "boss_hq")
        _gw_result = _gw.propose_action(
            tenant_id=tenant_id,
            canonical_user_id=identity.memory_key,
            tool_name=tool_name,
            tool_inputs=tool_inputs,
            origin_channel=channel,
            origin_chat_id=user_chat_id,
            requires_approval=True,
            identity=identity,
        )
        if not _gw_result.ok:
            logger.info(
                "[ActionGateway] propose blocked: %s | contract=%s",
                _gw_result.reason, _gw_result.contract_id,
            )
            return _gw_result.user_message or f"⏳ {_gw_result.reason}"
    else:
        # shadow mode — log only, do not block
        try:
            from core.action_gateway import action_gateway as _gw
            tenant_id = getattr(identity, "tenant_id", "boss_hq")
            _gw.propose_action(
                tenant_id=tenant_id,
                canonical_user_id=identity.memory_key,
                tool_name=tool_name,
                tool_inputs=tool_inputs,
                origin_channel=channel,
                origin_chat_id=user_chat_id,
                requires_approval=True,
                identity=identity,
            )
        except Exception as _gw_exc:
            logger.debug("[ActionGateway] shadow propose failed (non-blocking): %s", _gw_exc)

    action_id, _ = bus.request_approval(
        action  = tool_name,
        payload = {
            "tool_name":         tool_name,
            "tool_inputs":       tool_inputs,
            "origin_channel":    channel,
            "origin_chat_id":    user_chat_id,
            "canonical_user_id": identity.memory_key,
            "user_chat_id":      user_chat_id,
            "channel":           channel,
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
                f"⏳ בקשת אישור\n\n{label}\n\nID: {action_id} | פג תוקף בעוד 10 דקות",
                reply_markup=kb,
            )
            logger.info(f"[Approval] ✅ sent to owner {_sanitize_id(owner_chat_id)} | {action_id}")
        except Exception as e:
            logger.error(f"[Approval] ❌ failed to notify owner: {e}")
            # BOSS NEVER FAKES: לא מחזירים "ממתין לאישור" כשהשליחה נכשלה
            return (
                f"❌ לא הצלחתי לשלוח בקשת אישור לבעלים.\n"
                f"הפעולה לא בוצעה: {label}"
            )

    logger.info(f"[Approval] queued {action_id} | {tool_name} | user={_sanitize_id(user_chat_id)}")
    return f"⏳ הפעולה ממתינה לאישור: {label}\nשלח *מאשר* כדי לאשר (בכל ערוץ)."


def _tool_user_message(result) -> str:
    """Extract display text from a C53-A structured tool result (dict) or pass through a plain string."""
    if isinstance(result, dict):
        msg = result.get("user_message")
        if isinstance(msg, str) and msg:
            return msg
        return str(result)
    return str(result or "")


# ══════════════════════════════════════════════════
# C60 — Tool Context Awareness (SPEC_C59_Tool_Context_Awareness.md;
# tracked as C60 in docs — "C59" collides with the already-merged
# Decision Hub Stage 1 Trust Layer).
# ══════════════════════════════════════════════════

def _capture_last_tool_result(chat_id: str, tool_name: str, result, tool_input: dict, ok: bool) -> None:
    """שומר את תוצאת הכלי האחרונה ב-session — תיקון 'עיוורון כלים' בין סבבי agent.
    result הוא חוזה C53-A {ok, tool, external_id, evidence, user_message} — לא
    {id/record_id/url/drive_url} כמו שהספק הניח; הותאם לחוזה האמיתי בקוד."""
    try:
        from session_store import lead_sessions
        from datetime import datetime, timezone

        evidence = result.get("evidence", {}) if isinstance(result, dict) else {}
        record_id = result.get("external_id", "") if isinstance(result, dict) else ""
        url = evidence.get("htmlLink") or evidence.get("url") or "" if isinstance(evidence, dict) else ""

        lead_sessions.set_last_tool_result(chat_id, {
            "tool":      tool_name,
            "status":    "success" if ok else "failed",
            "summary":   _tool_user_message(result)[:120],
            "record_id": record_id,
            "url":       url,
            "input":     str(tool_input)[:80],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # BUG-NEW-09: persist the real Lead record_id on the Session so
        # follow-up turns reference it instead of fabricating one.
        if ok and tool_name in ("airtable_add", "airtable_update") and tool_input.get("table") == "Leads":
            lead_sessions.set_current_lead_record_id(chat_id, record_id)
    except Exception as e:
        logger.warning(f"[C60] set_last_tool_result failed for {_sanitize_id(chat_id)}: {e}")


def _build_tool_context(chat_id: str, session: dict | None) -> str:
    """מזריק תקציר 'מה הכלים עשו לאחרונה' ל-system prompt (TTL 5 דקות).
    הספק קורא ל-_seconds_ago() ב-§5 בלי להגדיר אותה — ממומש כאן inline.

    `session`: snapshot שכבר נטען ע"י הקורא (run_agent) — חובה להעביר.
    אסור fallback-fetch כאן: זה נקרא פעם אחת לבקשה והקורא הוא היחיד
    שיודע אם session==None זה miss אמיתי או עדיין לא נטען (LL-11)."""
    from datetime import datetime, timezone

    if not session:
        return ""

    ltr = session.get("last_tool_result")
    luf = session.get("last_uploaded_file")
    parts = []

    if ltr and ltr.get("timestamp"):
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(ltr["timestamp"])).total_seconds()
        except Exception:
            age = None
        if age is not None and age < 300:
            status_emoji = "✅" if ltr.get("status") == "success" else "❌"
            line = (f"כלי אחרון שרץ ({int(age)}ש' לפני): {ltr.get('tool')} "
                    f"{status_emoji} {ltr.get('summary', '')}")
            if ltr.get("record_id"):
                line += f" | רשומה: {ltr['record_id']}"
            if ltr.get("url"):
                line += f" | קישור: {ltr['url']}"
            parts.append(line)

    if luf:
        parts.append(
            f"קובץ אחרון שהועלה: {luf.get('original_filename', '')} "
            f"({luf.get('type', '')}) | {luf.get('url', '')}"
        )

    if not parts:
        return ""
    return "\n🔧 הקשר כלים:\n" + "\n".join(f"• {p}" for p in parts)


CONTEXT_PRONOUNS = {
    "זה":          "last_tool_result",
    "הנספח":       "last_file",
    "הקובץ האחרון": "last_file",
    "הקובץ":       "last_file",
    "הקודם":       "last_tool_result",
    "ההוא":        "last_tool_result",
    "אותו":        "last_tool_result",
}


def resolve_context_pronouns(text: str, chat_id: str, session: dict | None) -> str:
    """מחליף כינויי הצבעה ('זה'/'הנספח'/'הקודם' וכו') בהקשר אמיתי מה-session,
    כדי שה-Router וה-LLM יראו התייחסות מפורשת במקום לנחש. נקרא לפני intent detection.

    `session`: snapshot שכבר נטען ע"י הקורא (run_agent) — חובה להעביר.
    אסור fallback-fetch כאן: זה נקרא פעם אחת לבקשה והקורא הוא היחיד
    שיודע אם session==None זה miss אמיתי או עדיין לא נטען (LL-11)."""
    if not session:
        return text

    ltr = session.get("last_tool_result")
    luf = session.get("last_uploaded_file")
    resolved = text

    for pronoun, ref_type in CONTEXT_PRONOUNS.items():
        if pronoun in resolved:
            if ref_type == "last_file" and luf:
                resolved = resolved.replace(pronoun, f"הקובץ «{luf.get('original_filename', '')}»")
            elif ref_type == "last_tool_result" and ltr:
                resolved = resolved.replace(pronoun, f"הפעולה «{ltr.get('summary', '')}»")
    return resolved


def _handle_approval_callback(cq) -> None:
    """H3 top-level handler — דק, מעביר ל-impl ומדווח שגיאות לא-מטופלות."""
    try:
        _handle_approval_callback_impl(cq)
    except Exception as e:
        from core.error_reporter import report_error
        report_error(e, context="_handle_approval_callback")
        raise


def _handle_approval_callback_impl(cq) -> None:
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
                f"by {_sanitize_id(approver_identity.user_id)} role={approver_identity.role}"
            )
            bot.answer_callback_query(cq.id, "⛔ אין לך הרשאה לאשר פעולה זו")
            return

    if action == "approve":
        # BUG-SB-02: peek the bus item (without consuming) to resolve fingerprint →
        # ActionContract.status. Block if already executed/rejected before dispatching.
        # action_id is an event_bus key, NOT a contract_id — must go via fingerprint.
        try:
            from feature_flags import is_enabled as _flag_sb02
            if _flag_sb02("FEATURE_ACTION_GATEWAY"):
                _peek_item = bus.get(action_id)
                if _peek_item:
                    _peek_payload = _peek_item.get("payload", {})
                    _peek_tool    = _peek_payload.get("tool_name", "")
                    _peek_inputs  = _peek_payload.get("tool_inputs", {})
                    _peek_uid     = _peek_payload.get("canonical_user_id", "")
                    _peek_tid     = _peek_payload.get("tenant_id", "boss_hq")
                    if _peek_tool and _peek_uid:
                        from core.action_gateway import action_gateway as _gw_sb02
                        _fp_sb02 = _gw_sb02.compute_business_fingerprint(
                            _peek_tid, _peek_uid, _peek_tool,
                            _gw_sb02.normalize_payload(_peek_inputs),
                        )
                        _contract_sb02 = _gw_sb02._ledger.find_by_fingerprint(_fp_sb02)
                        if _contract_sb02 is not None:
                            if _contract_sb02.status == "executed":
                                bot.answer_callback_query(cq.id, "✅ פעולה זו כבר בוצעה")
                                try:
                                    bot.edit_message_reply_markup(
                                        cq.message.chat.id, cq.message.message_id, reply_markup=None)
                                except Exception:
                                    pass
                                logger.info(
                                    "[ActionGateway] SB-02: blocked duplicate callback "
                                    "action_id=%s contract=%s tool=%s status=executed",
                                    action_id, _contract_sb02.contract_id, _peek_tool,
                                )
                                return
                            if _contract_sb02.status == "rejected":
                                bot.answer_callback_query(cq.id, "❌ פעולה זו בוטלה")
                                try:
                                    bot.edit_message_reply_markup(
                                        cq.message.chat.id, cq.message.message_id, reply_markup=None)
                                except Exception:
                                    pass
                                return
        except Exception as _sb02_exc:
            logger.warning("[ActionGateway] SB-02 status pre-check failed (non-blocking): %s", _sb02_exc)

        # atomic pop — בדיקת TTL ומחיקה בצעד אחד
        item = bus.pop(action_id)
        if not item:
            bot.answer_callback_query(cq.id, "⏰ פג תוקף — הפעולה לא קיימת יותר")
            try:
                bot.edit_message_reply_markup(cq.message.chat.id, cq.message.message_id,
                                              reply_markup=None)
            except Exception:
                pass
            return

        payload          = item["payload"]
        tool_name        = payload.get("tool_name")   # absent on non-tool approvals
        user_chat_id     = payload.get("user_chat_id", item.get("chat_id", ""))
        channel          = payload.get("channel", "telegram")
        # Stage A: route notify to the channel the user actually requested from
        origin_channel   = payload.get("origin_channel", channel)
        origin_chat_id   = payload.get("origin_chat_id", user_chat_id)
        canonical_user_id = payload.get("canonical_user_id", "")

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
                    f"{tool_name} | user={_sanitize_id(identity.user_id)} role={identity.role}: {e}"
                )
                bot.answer_callback_query(cq.id, "⛔ הפעולה כבר אינה מורשית")
                return

            # BUG-091: this replays the payload stored at _queue_approval()
            # time (dict(tu.input) — Claude's own tool_use JSON, verbatim).
            # _queue_approval() is only ever called from the raw Agent
            # tool_use loop below — hardcode "agent", never trust a
            # "_source" key that might be sitting inside tool_inputs.
            raw    = dispatch_tool(tool_name, tool_inputs, identity, trusted_source="agent")
            result = validate_tool_output(tool_name, raw)

            exec_check = verify_execution(tool_name, result)
            if exec_check.status == "failed":
                logger.error(f"[Approval:A32] Execution failed: {tool_name} -- {exec_check.reason}")
                fail_text = f"❌ הפעולה לא הושלמה: {exec_check.reason}"
                if origin_channel == "telegram":
                    try:
                        bot.send_message(origin_chat_id, fail_text)
                    except Exception as e:
                        logger.error(f"[Approval] notify user failed: {e}")
                else:
                    _write_execution_receipt(canonical_user_id, origin_channel, origin_chat_id,
                                             action_id, tool_name, fail_text)
                try:
                    bot.edit_message_text(
                        f"❌ *אושר אך נכשל בביצוע*\n{item['label']}\n\n`{fail_text[:200]}`",
                        cq.message.chat.id, cq.message.message_id,
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
                bot.answer_callback_query(cq.id, "❌ הביצוע נכשל")
                return
            if exec_check.status == "warn":
                logger.warning(f"[Approval:A32] Execution warn: {tool_name} -- {exec_check.reason}")

            # PR #188: raw chat_id fingerprint
            from event_bus import executed_action_cache as _eac
            _eac.mark_executed(_eac.compute(user_chat_id, tool_name, tool_inputs))
            # Stage A: also clear cross-channel duplicate pending
            if canonical_user_id:
                bus.mark_equivalent_pending_completed(canonical_user_id, tool_name, tool_inputs)
            # Stage B sync: mark the Gateway contract executed so a subsequent
            # free-text "מאשר" on another channel doesn't re-dispatch the same tool.
            try:
                from feature_flags import is_enabled as _flag_gw
                if _flag_gw("FEATURE_ACTION_GATEWAY"):
                    from core.action_gateway import action_gateway as _gw_sync
                    _fp = _gw_sync.compute_business_fingerprint(
                        getattr(identity, "tenant_id", "boss_hq"),
                        canonical_user_id, tool_name,
                        _gw_sync.normalize_payload(tool_inputs),
                    )
                    _existing = _gw_sync._ledger.find_by_fingerprint(_fp)
                    if _existing and _existing.status == "pending":
                        _gw_sync._ledger.update_status(
                            _existing.contract_id, "executed",
                            approved_by=canonical_user_id,
                            approved_at=__import__("time").time(),
                        )
                        logger.info(
                            "[ActionGateway] Stage-A callback synced contract=%s tool=%s → executed",
                            _existing.contract_id, tool_name,
                        )
            except Exception as _gw_sync_exc:
                logger.warning("[ActionGateway] Stage-A sync failed (non-blocking): %s", _gw_sync_exc)

            # BUG-SB-04: legacy approval path — wrap tool result via ActionFact + compose_status_reply
            # when FEATURE_ACTION_GATEWAY is enabled, so the reply text is gated by Single Speaker.
            try:
                from feature_flags import is_enabled as _flag_sb04
                if _flag_sb04("FEATURE_ACTION_GATEWAY") and isinstance(result, dict) and result.get("ok") is not None:
                    from core.action_gateway import ActionFact, action_gateway as _gw_sb04
                    _fact_sb04 = ActionFact(
                        tool_name=tool_name or "unknown",
                        contract_id=action_id or "legacy",
                        outcome="executed" if result.get("ok") else "failed",
                        record_id=result.get("external_id") or None,
                        error_code=None if result.get("ok") else "tool_failed",
                        raw_tool_response=result,
                    )
                    result = _gw_sb04.compose_status_reply(_fact_sb04)
                    # mark so _tool_user_message passthrough picks up .text
                    result = result.text
                else:
                    result = _tool_user_message(result)
            except Exception as _sb04_exc:
                logger.warning("[ActionGateway] SB-04 ActionFact wrap failed: %s", _sb04_exc)
                result = _tool_user_message(result)

        logger.info(f"[Approval] ✅ confirmed {action_id} | {tool_name or item.get('action')}")

        # Stage A/B: route success notify to origin_channel, not always telegram.
        # When flag=ON: SB-04 compose_status_reply produced the GatewayReply text — send as-is.
        # When flag=OFF: wrap with legacy "✅ הפעולה בוצעה:" prefix for consistent UX.
        _gw_on = _flag_enabled("FEATURE_ACTION_GATEWAY")
        user_notify_text = result if _gw_on else f"✅ הפעולה בוצעה:\n{result}"
        if origin_channel == "telegram":
            try:
                bot.send_message(origin_chat_id, user_notify_text)
            except Exception as e:
                logger.error(f"[Approval] notify user failed: {e}")
        else:
            _write_execution_receipt(canonical_user_id, origin_channel, origin_chat_id,
                                     action_id, tool_name or item.get("action", ""), user_notify_text)

        try:
            # Owner button: plain text only — no Markdown, no raw tool result
            bot.edit_message_text(
                f"✅ אושר ובוצע\n{item['label']}",
                cq.message.chat.id, cq.message.message_id,
            )
        except Exception:
            pass
        bot.answer_callback_query(cq.id, "✅ בוצע!")

    elif action == "reject":
        item = bus.pop(action_id)
        if item:
            logger.info("🚫 Rejected: %s | %s", action_id, item.get("label", item.get("action", "")))

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
            logger.debug(f"[Typing] failed for {_sanitize_id(chat_id)}: {e}")

    while not stop_event.wait(interval):
        if channel == "telegram":
            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception as e:
                logger.debug(f"[Typing] failed for {_sanitize_id(chat_id)}: {e}")
        else:
            # Future platforms can be added here if they support typing indicators.
            pass


def _safe_route(text: str, channel: str, identity, domain_from_channel: str = "", envelope_id: str = "") -> RouteDecision:
    """
    עוטף את route_request עם fallback.
    כלל ברזל #9: אם Router נכשל — ממשיכים עם intent=unknown, risk=review.
    לא נופלים.

    envelope_id: C94 Stage ג — forwarded to route_request()/capture_router;
    "" for any caller that didn't build an IngressEnvelope. This function's
    own blanket try/except below is UNCHANGED — it still catches every OTHER
    kind of router failure exactly as before (classify_ingress() failures
    specifically no longer reach here at all — capture_router.py degrades
    them to capture_ic=None internally; see C94 Stage ג).
    """
    try:
        return route_request(
            text                = text,
            channel_raw         = channel,
            identity            = identity,
            domain_from_channel = domain_from_channel,
            envelope_id         = envelope_id,
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


# ══════════════════════════════════════════════════
# run_agent — Identity + Router + Agent Loop
# ══════════════════════════════════════════════════

def _action_result_to_a32_entry(result) -> "dict | None":
    """
    ממיר ActionResult לרשומת A32 tool_results_log.
    ClaimType קובע את שם הכלי — FOUND לא יהיה evidence ל-CREATED.
    מוחזר None עבור failures טכניים (flag off, junk) שאין להם claim_type.
    """
    if result is None:
        return None
    try:
        from core.action_result import ClaimType
        from core.claim_gate import check_claim
    except Exception:
        return None
    claim_type = getattr(result, "claim_type", None)
    if claim_type is None:
        return None
    gate = check_claim(result)
    if claim_type == ClaimType.CREATED:
        tool_name = "airtable_add"
    elif claim_type == ClaimType.FOUND:
        tool_name = "airtable_get"
    elif claim_type == ClaimType.UPDATED:
        tool_name = "airtable_update"
    elif claim_type == ClaimType.SCHEDULED:
        tool_name = "airtable_add"
    else:
        tool_name = "lead_capture"
    record_id = getattr(result, "record_id", "") or "-"
    return {
        "tool":    tool_name,
        "content": f"lead_capture:{claim_type.value}:record_id={record_id}",
        "ok":      bool(gate.ok),
    }


def run_agent(
    user_text:           str,
    chat_id:             str,
    channel:             str = "telegram",
    domain_from_channel: str = "",
    _skip_approval:      bool = False,
    _resolved_domain:    dict | None = None,
    _out_meta:           dict | None = None,
    raw_event_id:        str = "",
) -> str:
    # raw_event_id: C94 Stage ג/ד — the channel's own raw event id (e.g.
    # Telegram update_id, Twilio MessageSid), if the caller has one. "" for
    # every existing caller (backward-compatible, zero behavior change) —
    # only the Telegram webhook and the Twilio WhatsApp webhook pass this
    # today. Used below to build an IngressEnvelope before routing. Meta
    # WhatsApp Cloud API deliberately does NOT pass this (see
    # core/whatsapp_ingress_adapter.py's module docstring) — it gets the
    # same classify_ingress() exception-safety fix (via capture_router.py,
    # channel-agnostic since Stage ג) but no envelope/Trace wiring yet.

    # ── 1. Identity ───────────────────────────────
    identity = resolve_identity(channel, chat_id)
    logger.info(f"[Identity] {identity}")
    if identity.role in (Role.READONLY, Role.GUEST):
        logger.warning(
            f"[Identity] LOW-PRIVILEGE request — "
            f"channel={channel} id={_sanitize_id(chat_id)} role={identity.role} "
            f"msg='{user_text[:60]}'"
        )

    # ── 1.5. WhatsApp Lead Capture (W0) ───────────
    # W0/N02: capture inbound WhatsApp leads and optionally score them.
    lead_capture_result = None   # CXX/A32: נשמר לשילוב ב-tool_results_log
    if identity.role == Role.LEAD:
        try:
            from lead_capture import capture_inbound_lead
            # BUG-NEW-13: domain תמיד "general" כאן — ה-Router עוד לא רץ
            # (רץ ב-3. Router למטה). write_event=False כדי שלא ייכתב Lead
            # Event עם domain שגוי לליד קיים; נכתוב אותו בנפרד אחרי הניתוב.
            lead_capture_result = capture_inbound_lead(identity, user_text, write_event=False)
            # BUG-NEW-09: this path bypasses the dispatcher tool loop, so
            # _capture_last_tool_result never sees it — persist here instead.
            if lead_capture_result is not None and getattr(lead_capture_result, "record_id", ""):
                try:
                    from core.claim_gate import check_claim
                    if check_claim(lead_capture_result).ok:
                        from session_store import lead_sessions as _ls_lc
                        _ls_lc.set_current_lead_record_id(chat_id, lead_capture_result.record_id)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[LeadCapture] failed for {identity.memory_key}: {e}")

    # ── 1.6. Session snapshot (request-scoped cache) ─────────────
    # נטען פעם אחת ומועבר ל-resolve_context_pronouns / _build_tool_context,
    # כדי שלא יקראו ל-lead_sessions בנפרד באותה בקשה (תיקון: Sessions נשאל
    # פעמים רבות לאותה הודעה). חובה לטעון *אחרי* capture_inbound_lead —
    # אם הוא יוצר/מעדכן session, snapshot שנטען לפניו יהיה ישן.
    try:
        from session_store import lead_sessions as _ls
        _session_snapshot = _ls.get(chat_id)
    except Exception:
        _session_snapshot = None


    # ── 2. Rate Limit ─────────────────────────────
    if not rate_limiter.is_allowed(identity.memory_key):
        return "⚠️ יותר מדי בקשות. המתן דקה ונסה שוב."

    # ── 2.5. Pending Approval Gate ────────────────
    # LL-13: decision (which entry, confirm/cancel) + pop happen inside the
    # same lock-guarded critical section — there is no separate "check" step,
    # so two concurrent calls for the same chat_id can never both act on the
    # same pending entry (TOCTOU fix preserved from before BUG-070).
    #
    # BUG-070: _pending_approvals[chat_id] is now a dict of possibly multiple
    # queued entries, keyed by approval_id. A user reply can:
    #   - "כן" / "לא"                -> resolves only if exactly 1 is queued
    #     (fully backward compatible with the pre-BUG-070 behavior)
    #   - "כן 2" / "לא 2" / bare "2" -> targets entry with display_index=2
    #   - anything else with 2+ queued and no matching number -> ambiguous;
    #     nothing is popped, and the user is shown the numbered list again.
    pending_action = None   # "confirm" | "cancel" | None
    pending_entry  = None
    pending_id     = None
    pending_ambiguous = False

    with _pending_approvals_lock:
        bucket = _pending_approvals.get(chat_id)
        if bucket:
            stripped = user_text.strip()
            lower = stripped.lower()
            first_token = lower.split()[0] if lower.split() else ""

            if first_token in _CONFIRM_WORDS:
                pending_action = "confirm"
            elif first_token in _CANCEL_WORDS:
                pending_action = "cancel"
            elif len(bucket) > 1 and re.fullmatch(r"\d+", stripped):
                # BUG-070 review fix: a bare digit only means "approve item N"
                # when disambiguation is actually needed (2+ queued). With a
                # single pending item, a bare "1" is indistinguishable from an
                # unrelated numeric reply (quantity, price, date-of-month...)
                # elsewhere in the conversation — treating it as silent confirm
                # would execute the pending action without real user intent.
                # The single-pending case is already fully covered by
                # _CONFIRM_WORDS ("כן"/"אשר"/...), so no bare-digit fallback
                # is needed there.
                pending_action = "confirm"  # bare number selects among multiple pending

            if pending_action:
                resolved = _resolve_pending_reply(chat_id, stripped)
                if resolved:
                    pending_id, pending_entry = resolved
                elif len(bucket) > 1:
                    pending_ambiguous = True
                # else: single pending but no number given -> _resolve_pending_reply
                # already returns it via the len(bucket)==1 branch, so resolved
                # would only be None here if a number was given but didn't match
                # any queued item — treat as unrelated (fall through).

            if pending_entry is not None:
                if time.time() - pending_entry.get("created_at", 0) > _PENDING_APPROVAL_TTL:
                    logger.info("[PendingApproval] expired (>%ss) for %s",
                                _PENDING_APPROVAL_TTL, chat_id)
                    _pop_pending_approval(chat_id, pending_id)
                    pending_entry = None
                    pending_action = None
                else:
                    _pop_pending_approval(chat_id, pending_id)

    if pending_ambiguous:
        return _pending_clarification_message(chat_id)

    if pending_entry is not None:
        if pending_action == "confirm":
            logger.info(
                f"[PendingApproval] ✅ confirmed by {_sanitize_id(chat_id)} → "
                f"executing: {pending_entry['text'][:60]}"
            )
            return run_agent(
                pending_entry["text"], chat_id, channel,
                domain_from_channel=pending_entry.get("domain", domain_from_channel),
                _skip_approval=True,
                _resolved_domain=_resolved_domain,
            )
        elif pending_action == "cancel":
            logger.info(f"[PendingApproval] 🚫 cancelled by {_sanitize_id(chat_id)}")
            return "🚫 הפעולה בוטלה."
        # else: new unrelated message — nothing was popped above, treat normally

    # ── 2.55. Confirm-word + canonical tool-approval intercept ───────
    # Stage A / SPEC section 3.3: "מאשר" חופשי לעולם לא מאשר tool רגיש.
    # Stage B: "בצע שוב <קוד>" מיורט לפני Agent עבור DuplicateOverrideApproval.
    # אם FEATURE_ACTION_GATEWAY פעיל → route_confirmation_word מ-Gateway.
    # אחרת → Stage A bus.find_pending_tool_approval (מסלול הקיים).
    if pending_entry is None:
        _stripped = user_text.strip()
        _lower = _stripped.lower()

        # §10 §17 — "בצע שוב <קוד>" מיורט לפני Agent, בכל מצב flag
        _override_match = re.match(r"^בצע\s+שוב\s+(\d{4,8})$", _stripped)
        if _override_match:
            _override_code = _override_match.group(1)
            from core.action_gateway import action_gateway as _gw_ow
            return _gw_ow.route_override_word(identity.memory_key, _override_code)

        # BUG-070 gap #1 — "כן 1"/"אשר 3"/"לא 2": אישור/דחייה ממוקדת בהודעה
        # אחת, בלי לדרוש קודם רשימה ממוספרת. חייב לרוץ *לפני* בדיקת
        # disambiguation הרגילה (§4 למטה) כדי שלא תנקה בטעות state תלוי,
        # ולפני _CONFIRM_WORDS/_CANCEL_WORDS כדי שלא ייפול ל-Agent.
        # פועל מול contracts חיים ישירות (כמו BUG-056) — לא תלוי בדגל.
        from core.action_gateway import action_gateway as _gw_combined
        _combined_reply = _gw_combined.route_combined_word(
            identity.memory_key, _stripped, approver_role=identity.role,
        )
        if _combined_reply is not None:
            logger.info(
                "[ActionGateway] route_combined_word: user=%s text=%.30r reply=%.60s",
                identity.memory_key, _stripped, _combined_reply,
            )
            if _out_meta is not None:
                _out_meta["source_module"] = "action_gateway"
            return _combined_reply

        # §4 disambiguation — "הראשונה"/"1"/etc. כשה-Gateway הציג רשימת בחירה.
        # חייב להיות לפני בדיקת "?" ולפני _CONFIRM_WORDS כדי שלא ייפול ל-Agent.
        from feature_flags import is_enabled as _flag_disambig
        if _flag_disambig("FEATURE_ACTION_GATEWAY"):
            from core.action_gateway import action_gateway as _gw_disambig
            _disambig_reply = _gw_disambig.route_disambiguation(
                identity.memory_key, _stripped, approver_role=identity.role,
            )
            if _disambig_reply is not None:
                logger.info(
                    "[ActionGateway] route_disambiguation: user=%s text=%.30r reply=%.60s",
                    identity.memory_key, _stripped, _disambig_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _disambig_reply

        # §8 — שאלות סטטוס ("?", "נכשל?", "אושר?") לא מהוות אישור לעולם.
        # §7 §20 — שאלות "נוספה?" / "הצליח?" נענות מה-ExecutionLedger בלבד, לא מטקסט Agent.
        if "?" in _stripped:
            from feature_flags import is_enabled as _flag_sq
            if _flag_sq("FEATURE_ACTION_GATEWAY"):
                _sq_lower = _stripped.lower().rstrip("?")
                _STATUS_QUERY_PATTERNS = (
                    "נוספה", "נוסף", "בוצע", "בוצעה", "עודכן", "עודכנה",
                    "הצליח", "הצליחה", "נשמר", "נשמרה", "נוצר", "נוצרה",
                    "הוספת", "הוספתי", "עדכנת", "נשלח", "נשלחה",
                )
                if any(_sq_lower.endswith(p) or p in _sq_lower for p in _STATUS_QUERY_PATTERNS):
                    from core.action_gateway import action_gateway as _gw_sq
                    _ledger_reply = _gw_sq.query_execution_status(identity.memory_key)
                    if _ledger_reply is not None:
                        logger.info(
                            "[ActionGateway] status_query: user=%s query=%.40r reply=%.60s",
                            identity.memory_key, _stripped, _ledger_reply,
                        )
                        if _out_meta is not None:
                            _out_meta["source_module"] = "action_gateway"
                        return _ledger_reply
            pass  # fall through — route to Agent as status query
        elif _lower in _CONFIRM_WORDS:
            # BUG-056: check ActionGateway live contracts FIRST, regardless of
            # FEATURE_ACTION_GATEWAY — LCH's Tier-1 lead-preview confirmation
            # (core/lead_candidate_handler.py: _propose_lead_write) always
            # registers a real contract here, even when the flag is off (its
            # default). Only when Gateway has nothing pending do we fall back
            # to the flag-gated Stage A/B logic exactly as before.
            from core.action_gateway import action_gateway as _gw_cw
            if _gw_cw.find_live_contracts(identity.memory_key):
                _gw_reply = _gw_cw.route_confirmation_word(identity.memory_key, approver_role=identity.role)
                logger.info(
                    "[ActionGateway] route_confirmation_word: user=%s reply=%.60s",
                    identity.memory_key, _gw_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _gw_reply

            # BUG-058: no live Tier-1 ActionGateway contract — check the
            # Tier-2 batch lead-preview next (core/lead_candidate_handler.py's
            # _handle_clean_batch). Tier-1 always wins when both exist
            # simultaneously for the same chat_id (BUG-056 precedent, same
            # ordering as above) — this check runs only after Tier-1 found
            # nothing. Not gated by FEATURE_ACTION_GATEWAY — separate mechanism.
            from core.lead_candidate_handler import resolve_pending_lead_preview as _resolve_t2
            _t2_reply = _resolve_t2(identity, chat_id, is_confirm=True, is_cancel=False)
            if _t2_reply is not None:
                logger.info(
                    "[LCH] resolve_pending_lead_preview(confirm): user=%s reply=%.60s",
                    identity.memory_key, _t2_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _t2_reply

            from feature_flags import is_enabled as _flag_cw
            if _flag_cw("FEATURE_ACTION_GATEWAY"):
                # Stage B: Gateway הוא מקור האמת לאישור (אין contract חי -> "אין פעולה...")
                _gw_reply = _gw_cw.route_confirmation_word(identity.memory_key, approver_role=identity.role)
                logger.info(
                    "[ActionGateway] route_confirmation_word: user=%s reply=%.60s",
                    identity.memory_key, _gw_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _gw_reply
            else:
                # Stage A fallback (flag כבוי)
                from event_bus import bus as _bus_cw
                _canonical_pending = _bus_cw.find_pending_tool_approval(identity.memory_key)
                if _canonical_pending:
                    logger.info(
                        f"[PendingApproval] free-text confirm intercepted — tool approval exists "
                        f"({_canonical_pending['action_id']}) for {identity.memory_key}"
                    )
                    return (
                        f"יש פעולה שממתינה לאישור: {_canonical_pending['label']}\n"
                        f"נא לאשר דרך כפתור ✅/❌ בהודעת האישור המקורית."
                    )
                else:
                    logger.info(
                        f"[PendingApproval] free-text confirm, no pending for {identity.memory_key}"
                    )
                    return "אין פעולה שממתינה לאישור. אם זו בקשה חדשה — שלח את הנתונים המדויקים."
        elif _lower in _CANCEL_WORDS:
            # BUG-056: same reasoning as _CONFIRM_WORDS above — LCH's Tier-1
            # preview may have a live ActionGateway contract regardless of
            # FEATURE_ACTION_GATEWAY. If none, fall through unchanged (existing
            # behavior: only the _pending_approvals dict block above handles
            # cancel words; this elif is a no-op passthrough to Agent otherwise).
            from core.action_gateway import action_gateway as _gw_cancel
            _cancel_reply = _gw_cancel.route_cancellation_word(identity.memory_key)
            if _cancel_reply is not None:
                logger.info(
                    "[ActionGateway] route_cancellation_word: user=%s reply=%.60s",
                    identity.memory_key, _cancel_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _cancel_reply

            # BUG-058: no live Tier-1 contract was cancelled (route_cancellation_word
            # returned None) — check the Tier-2 batch lead-preview next. Same
            # Tier-1-wins precedence as the _CONFIRM_WORDS branch above.
            from core.lead_candidate_handler import resolve_pending_lead_preview as _resolve_t2_cancel
            _t2_cancel_reply = _resolve_t2_cancel(identity, chat_id, is_confirm=False, is_cancel=True)
            if _t2_cancel_reply is not None:
                logger.info(
                    "[LCH] resolve_pending_lead_preview(cancel): user=%s reply=%.60s",
                    identity.memory_key, _t2_cancel_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _t2_cancel_reply

    # ── 2.6. Context Pronoun Resolution (C60) ────────
    # "תעלה לדסישנס"/"זה הנספח" וכד' — לפני intent detection, כדי שה-Router
    # וה-LLM יראו התייחסות מפורשת במקום לנחש מהקשר חלקי.
    user_text = resolve_context_pronouns(user_text, chat_id, session=_session_snapshot)

    # ── 2.7. C94 Stage ג/ד — IngressEnvelope (Telegram + WhatsApp/Twilio) ──
    # Built BEFORE routing/classification, per C94's validation gate. Only
    # wired for channel="telegram"/"whatsapp" with a real raw_event_id — Meta
    # WhatsApp Cloud API's webhook deliberately never passes raw_event_id
    # (see core/whatsapp_ingress_adapter.py's module docstring), so it never
    # reaches this block; it's still untouched/gated. A build/validate
    # failure here degrades to no envelope (envelope_id="") rather than
    # blocking the request — this is observability plumbing, not a new gate
    # on the agent pipeline.
    # FEATURE_INGRESS_ENVELOPE: kill-switch, default ON (see feature_flags.py
    # _DEFAULTS — C94 is already on main/likely in prod, so an unset flag must
    # behave as if true, or deploying this line would silently disable it).
    envelope_id = ""
    if _flag_enabled("FEATURE_INGRESS_ENVELOPE") and raw_event_id and channel in ("telegram", "whatsapp"):
        try:
            if channel == "telegram":
                from core.telegram_ingress_adapter import build_telegram_envelope
                envelope = build_telegram_envelope(identity=identity, raw_event_id=raw_event_id, text=user_text)
            else:
                from core.whatsapp_ingress_adapter import build_whatsapp_envelope
                envelope = build_whatsapp_envelope(identity=identity, raw_event_id=raw_event_id, text=user_text)
            envelope.validate()
            envelope_id = envelope.envelope_id
        except Exception as exc:
            logger.error(
                "[C94] %s envelope build/validate failed chat=%s error_type=%s",
                channel, chat_id, type(exc).__name__,
            )

    # ── 3. Router — CORE_02.6 Integration ────────
    route = _safe_route(user_text, channel, identity, domain_from_channel, envelope_id=envelope_id)
    logger.info(route.to_log())

    # BUG-NEW-13: כעת ש-domain אמיתי ידוע, כתוב Lead Event (אם דולג למעלה
    # כי מדובר בליד קיים) עם ה-domain הנכון מה-Router, לא "general".
    if lead_capture_result is not None and lead_capture_result.record_id:
        try:
            from core.action_result import ClaimType as _ClaimType
            if lead_capture_result.claim_type == _ClaimType.FOUND:
                from lead_capture import capture_lead_event
                capture_lead_event(identity, user_text, lead_capture_result.record_id, domain=route.domain)
        except Exception as e:
            logger.warning(f"[LeadCapture] deferred lead event failed for {identity.memory_key}: {e}")

    # ── 3.5. Resolved-domain — single source of truth ──────────────
    # תיקון: COG (_gateway_whatsapp_reply) ו-approval_response קיבלו את
    # domain_from_channel הישן (לפני Router) במקום הדומיין הסופי שה-Router
    # קבע. מחושב פעם אחת ומשמש גם ל-out-param וגם ל-approval flow.
    resolved_route_domain = getattr(route.domain, "value", str(route.domain))
    if _resolved_domain is not None:
        _resolved_domain["domain"] = resolved_route_domain

    # ── 3.6. LeadCandidate Handler (Section 4B / BUG-NEW-10) ──────
    # בעל הבית מכתיב ליד ("משה יצחקוב 050... תשמור") — short-circuit לפני agent.
    # sender_identity (אליהו) נשמר קבוע; subject (הליד) מטופל בנפרד.
    # SPEC 1 (Capture Policy Router-Integration): הועבר לכאן מ-שלב "1.45"
    # (היה *לפני* ה-Router — bypass מלא של Identity→Router→Context→Agent).
    # ה-Router רץ עכשיו תמיד קודם — LCH מקבל domain אמיתי מ-domain_router
    # (resolved_route_domain) במקום רק את ה-content-regex guess הפנימי שלו.
    # gate זהה לגמרי לישן (identity.is_internal) — לא route.capture_tier.
    # BUG-056: route.capture_ic (ה-IngressClassification המלא שה-Router כבר
    # חישב) מועבר ל-LCH במקום שLCH יריץ classify_ingress() שוב על אותו טקסט —
    # קריאה יחידה במקום שתיים (double-classification fix).
    if getattr(identity, "is_internal", False):
        try:
            from core.lead_candidate_handler import handle_lead_candidate
            _lch_reply = handle_lead_candidate(
                identity, user_text, chat_id, channel, domain=resolved_route_domain,
                ic=route.capture_ic, intent=route.intent, session=_session_snapshot,
            )
            if _lch_reply is not None:
                # BUG-SB-01: COG sees "lead_candidate_handler" as a different speaker.
                # LCH is a deterministic Gateway path — mark as "action_gateway"
                # so the Single Speaker guard passes, same as other GatewayReply paths.
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _lch_reply
        except Exception as _lch_exc:
            logger.warning("[LCH] handler failed (falling through to agent): %s", _lch_exc)

    # ── 4. Dispatch ───────────────────────────────
    if route.handler == Handler.ENGINEERING_NOTE:
        # SPEC-ROUTER-06: bug reports / debug instructions never reach the
        # Agent or tools — no business write, no self-reported-fix claim.
        return route.response_override or "קיבלתי דיווח באג. לא שיניתי את המערכת. צריך שינוי קוד, בדיקות ופריסה."

    if route.handler == Handler.CLARIFY:
        return clarify_response(route)

    if route.handler == Handler.APPROVAL and not _skip_approval:
        # שומרים את הדומיין שה-Router פתר בפועל, לא domain_from_channel הישן
        # — אחרת pending approval ישמור domain שגוי (למשל "general") ויחזיר
        # אותו ב-recursive call לאחר אישור.
        return approval_response(route, user_text, chat_id, channel, resolved_route_domain)

    # לא עושים BLOCK רגיל ללקוח — restricted ממשיך לסוכן
    if route.restricted:
        logger.warning(
            f"[Restricted] external request: "
            f"user={_sanitize_id(identity.user_id)} role={identity.role} "
            f"intent={route.intent} notify_owner=True tool_allowed=False"
        )

    # ── 5. Agent Loop ─────────────────────────────
    if _flag_enabled("EMERGENCY_STOP_AI"):
        logger.warning(
            f"[CostWatchdog] EMERGENCY_STOP_AI active — blocking agent for {_sanitize_id(identity.user_id)}"
        )
        return "⛔ מערכת ה-AI בעצירת חירום עקב עלות גבוהה. נסה שוב מאוחר יותר."

    # ── 5.1. Deterministic Denial Short-Circuit ────
    # כמה צירופי (intent, כלי משוער) ידועים כבר עכשיו ב-100% כך ששער מאוחר
    # יחסום אותם בכל מקרה, לא משנה מה Claude יעשה — מדלגים על סבב Claude
    # לגמרי, באותה קונבנציה כמו EMERGENCY_STOP_AI למעלה. שומרים על
    # tool_allowed (לא handler==AGENT): נתיבי RESTRICTED/blocked/clarify/
    # approval כבר חזרו למעלה או שיש להם מנגנון קיים משלהם בהמשך
    # (app.py, "הבקשה נרשמה במערכת.") — אסור להחליף אותם בהודעה הזו.
    if route.tool_allowed:
        denial = check_deterministic_denial(route.intent, identity)
        if denial is not None:
            logger.warning(
                f"[DeterministicDenial] {denial.reason} short-circuited before Agent | "
                f"intent={route.intent} tool={denial.tool_name} role={identity.role} "
                f"user={_sanitize_id(identity.user_id)}"
            )
            return denial.message

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
        # C60: הזרקת "הקשר כלים" — מה רץ בסבב הקודם — ל-system prompt
        ctx.system_prompt += _build_tool_context(chat_id, session=_session_snapshot)
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
        # LL-11: dedup repeated read-only lookups (e.g. Sessions/Leads GET)
        # within this turn — same (tool, inputs) reuses the cached result
        # instead of re-querying Airtable.
        _turn_read_cache: dict[tuple, dict] = {}
        # BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION: a single agent turn must
        # not queue more than one mutating (requires_approval) action.
        _mutating_approvals_this_turn = 0
        # CXX/A32: הוסף lead capture evidence — FOUND≠CREATED ב-A32
        _lc_a32 = _action_result_to_a32_entry(lead_capture_result)
        if _lc_a32:
            tool_results_log.append(_lc_a32)

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

            # C54: אם Claude ייצר text ו-tool_use באותה תשובה —
            # ה-text נוצר לפני שראה תוצאה. מבטלים אותו.
            # התשובה האמיתית תגיע ב-turn הבא עם ה-ToolResult.
            _c54_pending_text = False
            if tool_uses and text_blocks:
                _c54_pending_text = any(
                    any(w in b.text for w in ("ממתינ", "אישור", "pending", "⏳"))
                    for b in text_blocks
                )
                logger.info(f"[C54] Suppressed premature text_block alongside tool_use: "
                            f"{[b.text[:40] for b in text_blocks]}"
                            f"{' [approval-language detected]' if _c54_pending_text else ''}")
                # Stage B §5: record AgentObservation for C54 contradiction (approval text + tool_use)
                if _c54_pending_text:
                    try:
                        from core.action_gateway import action_gateway as _gw_c54
                        _gw_c54.record_agent_observation(
                            contract_id=None,
                            kind="contradiction",
                            text=f"C54: Agent produced approval-pending text alongside tool_use "
                                 f"({[tu.name for tu in tool_uses]}). "
                                 f"Suppressed text; approval gate will handle routing.",
                        )
                    except Exception:
                        pass
                text_blocks = []

            if not tool_uses:
                final_reply = text_blocks[0].text if text_blocks else "✅ פעולה הושלמה."
                break

            if tool_calls_made >= MAX_TOOL_TURNS:
                logger.warning(
                    f"[Agent] reached max tool turns ({tool_calls_made}/{MAX_TOOL_TURNS}) "
                    f"for user={_sanitize_id(identity.user_id)} role={identity.role} intent={route.intent}"
                )
                final_reply = (text_blocks[0].text if text_blocks
                               else "⚠️ הגעתי למגבלת הפעולות לריצה זו. נסה לפרק את הבקשה לשלבים.")
                break

            # ── Tool Loop ────────────────────────
            tool_results = []
            for tu in tool_uses:
                if not route.tool_allowed:
                    logger.info(f"[Tool] Silently blocked by route (restricted): {tu.name}")
                    # Was "הבקשה התקבלה ותועבר לטיפול." — no forwarding mechanism
                    # actually exists (route.notify_owner is set but never consumed
                    # anywhere; see backlog item for building real notification).
                    # Honest about current state: request was received and logged,
                    # nothing more.
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tu.id,
                        "content":     "הבקשה נרשמה במערכת.",
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
                    # BUG-091: preflight — a write enforce_leads_write_gate()
                    # provably blocks must never become a pending approval at
                    # all ("אושר אך נכשל בביצוע" is worse than never asking,
                    # and previously nothing stopped it from being queued).
                    # source is hardcoded "agent" — this branch IS the raw
                    # Agent tool_use loop, never a trusted internal call site;
                    # never read from tu.input, which Claude fully controls.
                    if tu.name in ("airtable_add", "airtable_update"):
                        try:
                            enforce_leads_write_gate(
                                tu.name, {"table": tu.input.get("table", "")}, source="agent",
                            )
                        except LeadsDirectWriteBlocked as e:
                            logger.warning(
                                f"[Approval] preflight blocked Leads write before queueing: {tu.name}"
                            )
                            tool_results.append({
                                "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
                            })
                            continue

                    # BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION: one mutating
                    # approval per agent turn; block the second unconditionally.
                    if _mutating_approvals_this_turn >= 1:
                        logger.warning(
                            f"[Approval] multi-pending blocked: {tu.name} | "
                            f"turn already has 1 approval queued | user={_sanitize_id(chat_id)}"
                        )
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id,
                            "content": (
                                "⚠️ לא ניתן לבצע מספר פעולות הדורשות אישור בו-זמנית. "
                                "אנא אשר את הפעולה הנוכחית קודם."
                            ),
                        })
                        continue
                    result = _queue_approval(
                        tu.name, dict(tu.input), chat_id, channel
                    )
                    _mutating_approvals_this_turn += 1
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": result
                    })
                    # BUG-V1-FAKE-APPROVAL-STATE: inject A32 sentinel so
                    # sanitize_agent_response can verify the "⏳ ממתינה לאישור"
                    # echo came from a real approval, not hallucinated text.
                    tool_results_log.append({
                        "tool": "__approval_queued__",
                        "content": result,
                        "ok": True,
                    })
                    continue

                dedup_key = (tu.name, tuple(sorted(tu.input.items(), key=lambda kv: kv[0])))
                if meta.read_only and dedup_key in _turn_read_cache:
                    logger.info(f"[Tool] {tu.name} | dedup hit (LL-11) — reusing this turn's result")
                    cached = _turn_read_cache[dedup_key]
                    raw, result, result_text = cached["raw"], cached["result"], cached["result_text"]
                else:
                    logger.info(f"[Tool] {tu.name} | {str(tu.input)[:80]}")
                    # BUG-091: raw Agent tool_use loop — always "agent",
                    # explicit for clarity/defense-in-depth even though
                    # airtable_add/update never reach this branch (both
                    # requires_approval=True, handled above).
                    raw    = dispatch_tool(tu.name, tu.input, identity, trusted_source="agent")
                    result = validate_tool_output(tu.name, raw)
                    result_text = _tool_user_message(result)
                    logger.info(f"[Tool] → {result_text[:80]}")
                    if meta.read_only:
                        _turn_read_cache[dedup_key] = {"raw": raw, "result": result, "result_text": result_text}

                # A32 — verify tool actually succeeded
                exec_check = verify_execution(tu.name, result)
                if exec_check.status == "failed":
                    logger.error(f"[A32] Execution failed: {tu.name} — {exec_check.reason}")
                    result_text = f"❌ הפעולה לא הושלמה: {exec_check.reason}"
                elif exec_check.status == "warn":
                    logger.warning(f"[A32] Execution warn: {tu.name} — {exec_check.reason}")

                # Fix 2: persist successful write results for next-turn memory
                if tu.name in _MEMORABLE_TOOLS and "❌" not in result_text:
                    memory.add(
                        ctx.memory_key,
                        "user",   # only "user"/"assistant" valid in Claude messages[]
                        f"[🔧 {tu.name}]: {str(tu.input)[:60]} → {result_text[:60]}"
                    )

                entry = {"type": "tool_result", "tool_use_id": tu.id, "content": result_text}
                tool_results.append(entry)
                # A32: separate record (not sent to the API) — carries the real
                # tool name + ok status so sanitize_agent_response can verify
                # claims by tool identity, not by guessing from response text.
                tool_results_log.append({
                    "tool":    tu.name,
                    "content": result_text,
                    "ok":      exec_check.status != "failed",
                })
                # C60: זיכרון בין סבבים — "תעלה לדסישנס" אחרי כלי קודם יזהה שהוא רץ
                _capture_last_tool_result(chat_id, tu.name, result, tu.input, exec_check.status != "failed")

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
        final_reply = sanitize_agent_response(
            final_reply, tool_results_log,
            _gateway_active=_flag_enabled("FEATURE_ACTION_GATEWAY"),
        )

        # ── שמירת זיכרון ─────────────────────────
        memory.add(ctx.memory_key, "user",      clean_msg)
        memory.add(ctx.memory_key, "assistant", final_reply)

        # Buffer recovery + cleanup:
        # 1. recover_blocked_lead_payload — צורך buffer ומעדכן ליד
        # 2. clear_buffer — finally, גם אם recovery נכשל
        #
        # סדר חשוב:
        #   capture_inbound_lead  ← buffer ריק (רץ לפני Agent)
        #   Agent                 ← נחסם, buffer מתמלא
        #   recover (כאן)         ← consume + patch
        #   clear (כאן)           ← finally
        try:
            if identity.role == Role.LEAD:
                from core.lead_buffer import recover_blocked_lead_payload, has_buffer
                if has_buffer():
                    # resolved_route_domain — מחושב למעלה (3.5), לא route.domain
                    # הגולמי (Enum) — אחרת memory_key ב-lead_buffer יקבל ערך שגוי.
                    recover_blocked_lead_payload(identity, domain=resolved_route_domain)
        except Exception as _rec_err:
            logger.debug(f"[LeadBuffer] recovery non-critical: {_rec_err}")
        finally:
            try:
                from core.lead_buffer import clear_buffer
                clear_buffer()
            except Exception:
                pass

        return final_reply

    except anthropic.APIStatusError as e:
        logger.error(f"[Agent] Anthropic {e.status_code}: {e.message}")
        _transient = e.status_code in (429, 529) or e.status_code >= 500
        if _transient and _flag_enabled("LLM_FALLBACK"):
            logger.warning(f"[Agent] Claude transient error {e.status_code} — OpenAI fallback for {_sanitize_id(chat_id)}")
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
        logger.error(f"[Agent] Timeout for {_sanitize_id(chat_id)}")
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


# ══════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════

# C90 — Structured File Capture: xlsx/csv detection (routing only, not a classifier)
_STRUCTURED_FILE_EXTENSIONS = (".xlsx", ".csv")
_STRUCTURED_FILE_MIME_TYPES = frozenset({
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})


def _is_structured_file(filename: str, mime_type: str) -> bool:
    if mime_type in _STRUCTURED_FILE_MIME_TYPES:
        return True
    return filename.lower().endswith(_STRUCTURED_FILE_EXTENSIONS)


# Operational safety cap only — parse_structured_file_rows() itself never
# drops rows. If a file exceeds this, only the first N are dispatched and
# the reply explicitly says so (never a silent truncation).
_MAX_FILE_ROWS_PROCESSED = 200


def _process_structured_file_upload(
    identity, chat_id: str, channel: str, domain: str,
    file_bytes: bytes, filename: str,
) -> str:
    """
    מפרסר קובץ xlsx/csv לשורות (core/file_ingress_adapter.py) ומעביר כל
    שורה, אחת בכל פעם, דרך אותו handle_lead_candidate()/classify_ingress()
    שהודעת טקסט הייתה עוברת — ללא special-casing. כל שורה יוצרת AgentObservation
    + raw_ref משלה (BUG-065). כל Tier 1-3 דורש אישור פרטני ("כן"/"לא"),
    בדיוק כמו הודעת טקסט בודדת — אין "אישור קבוצתי" (BUG-058 עדיין פתוח,
    לא נבנה resolver ל-batch כאן).

    C94 Stage ב: כל שורה עוברת קודם דרך build_file_row_envelope() ל-
    IngressEnvelope (validate() נכשל/עוצר את השורה הזו בלבד, לא את כל
    הקובץ) — ואז דרך אותו classify_ingress()/handle_lead_candidate() בדיוק
    כמו היום (ללא שינוי ב-C89/C90 עצמם). EvidenceTrace נבנה כתוצר לוואי
    אחרי classify_ingress() חוזר. classify_ingress() עצמו עטוף כעת ב-
    try/except: חריגה בשורה בודדת (למשל קלט לא צפוי) נלכדת, מתועדת כ-
    classification_error על ה-trace, וממשיכה לשורה הבאה — לפני התיקון הזה
    חריגה כזו הייתה מפילה את כל שאר שורות הקובץ בשקט.
    """
    from core.file_ingress_adapter import build_file_row_envelope, parse_structured_file_rows, FileParseError
    from core.ingress_classifier import classify_ingress
    from core.ingress_envelope import EvidenceTrace, EnvelopeValidationError
    import core.lead_candidate_handler as lch

    try:
        rows = parse_structured_file_rows(file_bytes, filename)
    except FileParseError as exc:
        logger.warning(f"[C90] file parse failed for {filename}: {exc}")
        return f"❌ לא הצלחתי לקרוא את הקובץ *{filename}*: {exc}"

    if not rows:
        return f"📊 הקובץ *{filename}* לא הכיל שורות נתונים — לא בוצעה שום פעולה."

    truncated = len(rows) > _MAX_FILE_ROWS_PROCESSED
    rows_to_process = rows[:_MAX_FILE_ROWS_PROCESSED]

    tier_counts: dict[int, int] = {}
    pending_count = 0
    written_count = 0
    failed_count = 0

    for row_index, row_text in enumerate(rows_to_process, start=1):
        envelope = build_file_row_envelope(
            identity=identity, channel=channel, filename=filename,
            row_index=row_index, row_text=row_text,
        )
        try:
            envelope.validate()
        except EnvelopeValidationError as exc:
            logger.error(f"[C94] invalid envelope for {filename} row {row_index}: {exc}")
            failed_count += 1
            continue

        trace = EvidenceTrace(envelope_id=envelope.envelope_id)
        try:
            ic = classify_ingress(envelope.normalized_text, source_type="file")
        except Exception as exc:
            # PII-safety: never log str(exc)/row text (may embed phone/name),
            # and never exc_info=True here either — a full traceback usually
            # embeds the same exception message/args in its last frame, which
            # would leak the same PII through the back door. Only safe,
            # structured metadata goes to the log; same discipline as the
            # Trace itself (classification_error = type(exc).__name__ only).
            logger.error(
                "[C94] classify_ingress error file_row envelope_id=%s row=%s error_type=%s",
                envelope.envelope_id, row_index, type(exc).__name__,
            )
            trace.record_classification(classification_error=type(exc).__name__)
            failed_count += 1
            continue
        trace.record_classification(
            classification_result={"tier": ic.tier, "confidence": ic.confidence, "reason": ic.reason},
            raw_ref=ic.raw_ref,
        )
        logger.debug(
            f"[C94] row trace: envelope_id={envelope.envelope_id} tier={ic.tier} raw_ref={trace.raw_ref}"
        )

        tier_counts[ic.tier] = tier_counts.get(ic.tier, 0) + 1
        try:
            reply = lch.handle_lead_candidate(identity, envelope.normalized_text, chat_id, channel, domain=domain, ic=ic)
        except Exception as exc:
            # Same PII-safety discipline as the classify_ingress except above —
            # no str(exc), no exc_info=True.
            logger.error(
                "[C90] row dispatch error envelope_id=%s row=%s error_type=%s",
                envelope.envelope_id, row_index, type(exc).__name__,
            )
            reply = None
        if reply is None:
            continue
        if reply.startswith("📋"):
            pending_count += 1
        elif reply.startswith("✅"):
            written_count += 1
        elif reply.startswith("❌"):
            failed_count += 1

    lines = [f"📊 עיבדתי את הקובץ *{filename}* — {len(rows_to_process)} שורות נתונים."]
    tier_summary = ", ".join(f"Tier {t}: {c}" for t, c in sorted(tier_counts.items()))
    lines.append(f"פילוח: {tier_summary}")
    if pending_count:
        lines.append(f"⏳ {pending_count} שורות ממתינות לאישור פרטני — ענה *כן*/*לא* לכל אחת בנפרד.")
    if written_count:
        lines.append(f"✅ {written_count} נכתבו (FEATURE_AUTO_CAPTURE פעיל).")
    if failed_count:
        lines.append(f"❌ {failed_count} שורות נכשלו בעיבוד (סיווג או כתיבה).")
    lines.append("לא בוצעה כתיבה אוטומטית קבוצתית — כל שורה דורשת אישור נפרד.")
    if truncated:
        lines.append(f"⚠️ הקובץ הכיל {len(rows)} שורות — עובדו רק {_MAX_FILE_ROWS_PROCESSED} הראשונות (מגבלת בטיחות תפעולית).")

    return "\n".join(lines)


# F16 — Media Layer: Telegram voice/photo/document intake
def _handle_telegram_media(message) -> None:
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    owner_chat_id = (
        os.environ.get("OWNER_TELEGRAM_ID", "") or
        os.environ.get("ELIYAHU_CHAT_ID", "") or
        os.environ.get("DIGEST_CHAT_ID", "")
    )

    try:
        identity = resolve_identity("telegram", user_id)
    except Exception as e:
        logger.error(f"[Media] identity resolution failed: {e}")
        return
    domain = identity.domain_id

    # ── Decision Hub Stage 0.5 — File/Voice Precedence Routing ───────
    # SPEC_File_Precedence_Fix.md, Rule 9 (MODULE_RULES.md): an active
    # Decision Inbox context wins over the default Drive/Voice flow below.
    # Flag-gated + fully additive — zero behavior change when off/inactive.
    try:
        from feature_flags import is_enabled
        if is_enabled("FEATURE_DECISION_HUB"):
            from cmd_decision import decision_context_active, route_file_to_decision_inbox
            if decision_context_active(message):
                text = message.caption or getattr(message, "text", None) or ""
                file_bytes, filename, mime_type = b"", "", ""
                try:
                    if message.content_type == "voice":
                        file_info = bot.get_file(message.voice.file_id)
                        file_bytes = bot.download_file(file_info.file_path)
                        filename = f"{message.voice.file_id}.ogg"
                        mime_type = message.voice.mime_type or "audio/ogg"
                    elif message.content_type == "photo":
                        photo = message.photo[-1]
                        file_info = bot.get_file(photo.file_id)
                        file_bytes = bot.download_file(file_info.file_path)
                        filename = f"{photo.file_id}.jpg"
                        mime_type = "image/jpeg"
                    elif message.content_type == "document":
                        doc = message.document
                        file_info = bot.get_file(doc.file_id)
                        file_bytes = bot.download_file(file_info.file_path)
                        filename = doc.file_name or f"{doc.file_id}"
                        mime_type = doc.mime_type or "application/octet-stream"

                    route_file_to_decision_inbox(
                        bot, identity, chat_id,
                        text=text, file_bytes=file_bytes, filename=filename, mime_type=mime_type,
                    )
                except Exception as e:
                    logger.error(f"[DecisionHub] precedence routing failed: {e}", exc_info=True)
                    try:
                        bot.send_message(chat_id, "❌ שגיאה בשמירה ל-Decision Inbox")
                    except Exception:
                        pass
                return
    except Exception as e:
        logger.error(f"[DecisionHub] precedence gate error: {e}", exc_info=True)
        # fall through to default Drive/Voice handling — fail-safe, not fail-closed

    # ── C90 — Structured File Capture (xlsx/csv) ──────────────────────
    # File upload is an ingress SOURCE ADAPTER only — not a new capture
    # pipeline, not a new classifier, not a new write path. Each row is
    # parsed (core/file_ingress_adapter.py) and dispatched, one at a time,
    # through the EXACT SAME classify_ingress()/handle_lead_candidate()
    # pipeline text messages use — no special-casing, no bulk auto-approve
    # (every Tier 1-3 row still requires individual "כן" approval, same as
    # FEATURE_AUTO_CAPTURE=false already enforces for text today).
    # Internal senders only, matching LCH's own is_internal gate.
    if (
        message.content_type == "document"
        and getattr(identity, "is_internal", False)
        and _flag_enabled("FEATURE_STRUCTURED_FILE_CAPTURE")
    ):
        doc = message.document
        filename = doc.file_name or ""
        mime_type = doc.mime_type or ""
        if _is_structured_file(filename, mime_type):
            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception:
                pass
            try:
                file_info = bot.get_file(doc.file_id)
                file_bytes = bot.download_file(file_info.file_path)
                reply = _process_structured_file_upload(
                    identity, chat_id, "telegram", domain, file_bytes, filename,
                )
                bot.send_message(chat_id, reply, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"[Media] structured file capture error: {e}", exc_info=True)
                try:
                    bot.send_message(chat_id, "❌ שגיאה בעיבוד הקובץ")
                except Exception:
                    pass
            return

    if message.content_type == "voice":
        if not _flag_enabled("FEATURE_VOICE_NOTES"):
            try:
                bot.send_message(chat_id, "🎤 בקרוב — תמלול הודעות קוליות")
            except Exception:
                pass
            return
        try:
            from media_handler import handle_voice_note, _format_media_result, _classify_size, MediaResult, MediaError

            voice_size = message.voice.file_size or 0
            if _classify_size(voice_size) == "oversized":
                logger.info(f"[Media] oversized voice note ({voice_size} bytes) from user={_sanitize_id(user_id)} — skipping download")
                bot.send_message(chat_id, _format_media_result(MediaResult(
                    ok=False, file_size_tier="oversized",
                    error=MediaError("FILE_TOO_LARGE", "הקובץ גדול מ-50MB. הגודל המרבי הוא 50MB.", False),
                )))
                return

            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception:
                pass

            file_info = bot.get_file(message.voice.file_id)
            audio_bytes = bot.download_file(file_info.file_path)
            result = handle_voice_note(
                audio_bytes=audio_bytes,
                mime_type=message.voice.mime_type or "audio/ogg",
                telegram_file_id=message.voice.file_id,
                user_id=user_id,
                domain=domain,
                owner_chat_id=owner_chat_id,
            )
            bot.send_message(chat_id, _format_media_result(result))
        except Exception as e:
            logger.error(f"[Media] voice handling error: {e}", exc_info=True)
            try:
                bot.send_message(chat_id, "❌ שגיאה בעיבוד ההודעה הקולית")
            except Exception:
                pass
        return

    # photo / document
    if not _flag_enabled("FEATURE_MEDIA_UPLOAD"):
        try:
            bot.send_message(chat_id, "📎 בקרוב — שמירת קבצים ל-Drive")
        except Exception:
            pass
        return

    try:
        from media_handler import handle_file_upload, _format_media_result, _classify_size, MediaResult, MediaError

        if message.content_type == "photo":
            photo = message.photo[-1]
            file_id = photo.file_id
            filename = f"{file_id}.jpg"
            mime_type = "image/jpeg"
            file_type = "image"
            file_size = photo.file_size or 0
        else:
            doc = message.document
            file_id = doc.file_id
            filename = doc.file_name or f"{file_id}"
            mime_type = doc.mime_type or "application/octet-stream"
            file_type = "document"
            file_size = doc.file_size or 0

        if _classify_size(file_size) == "oversized":
            logger.info(f"[Media] oversized {file_type} ({file_size} bytes) from user={_sanitize_id(user_id)} — skipping download")
            bot.send_message(chat_id, _format_media_result(MediaResult(
                ok=False, file_size_tier="oversized",
                error=MediaError("FILE_TOO_LARGE", "הקובץ גדול מ-50MB. הגודל המרבי הוא 50MB.", False),
            )))
            return

        try:
            bot.send_chat_action(chat_id, "upload_document")
        except Exception:
            pass

        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        result = handle_file_upload(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            file_type=file_type,
            file_id=file_id,
            user_id=user_id,
            domain=domain,
        )
        if result.ok:
            try:
                from datetime import datetime, timezone
                from session_store import lead_sessions, FileUploadResult
                lead_sessions.set_last_file(
                    user_id,
                    FileUploadResult(
                        type="drive_file",
                        url=result.drive_url,
                        file_id=result.asset_id,
                        original_filename=filename,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        conversation_id=chat_id,
                    ),
                    domain=domain,
                    channel="telegram",
                )
            except Exception as e:
                logger.warning(f"[Media] set_last_file failed: {e}")
        bot.send_message(chat_id, _format_media_result(result))
    except Exception as e:
        logger.error(f"[Media] file handling error: {e}", exc_info=True)
        try:
            bot.send_message(chat_id, "❌ שגיאה בשמירת הקובץ")
        except Exception:
            pass


@app.route("/health", methods=["GET"])
def health():
    health_status = get_health_status(globals().get("_scheduler"), memory)
    return jsonify({"status": health_status["status"]}), 200


@app.route("/telegram", methods=["POST"])
def webhook_telegram():
    """H1 top-level handler — דק, מעביר ל-impl ומדווח שגיאות לא-מטופלות."""
    try:
        return _webhook_telegram_impl()
    except Exception as e:
        from core.error_reporter import report_error
        report_error(e, context="webhook_telegram")
        raise


def _webhook_telegram_impl():
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
        call = update.callback_query
        data = call.data or ""
        try:
            if data.startswith(("approve:", "reject:")):
                _handle_approval_callback(call)
            else:
                # העבר ל-pyTeleBot handlers (upd_domain:, upd_type:, weekly summary וכו')
                bot.process_new_updates([update])
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
                logger.error(f"[Command] dispatch error: {e}", exc_info=True)
                from core.error_reporter import report_error
                report_error(e, context="command_dispatch")
            return "", 200

        # C20 — free text mid-/update never reaches capture_text (registered
        # via @bot.message_handler) because bot.process_new_updates() is only
        # called for slash commands above. Dispatch it ourselves so the
        # pending wizard claims its own text instead of falling through to
        # idempotency/run_agent. Fail-open: any error here just continues
        # to the normal flow below, it never blocks the message.
        try:
            from cmd_update import has_pending_text_capture
            if has_pending_text_capture(sender_user_id):
                bot.process_new_updates([update])
                return "", 200
        except Exception as e:
            logger.error(f"[/update] text capture routing failed: {e}", exc_info=True)

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

        # ── Decision Hub Stage 0.6 — "זה הנספח" attachment reference ──
        # SPEC_File_Context_Reference.md, Rule 10: max one linking question.
        # Telegram-specific (inline keyboards) — handled here, not in the
        # channel-agnostic run_agent. Flag-gated + additive.
        if _flag_enabled("FEATURE_DECISION_HUB"):
            try:
                from cmd_decision import is_attachment_reference, handle_attachment_reference
                if is_attachment_reference(text):
                    identity_for_ref = resolve_identity("telegram", sender_user_id)
                    if handle_attachment_reference(bot, identity_for_ref, reply_chat_id, text):
                        return "", 200
            except Exception as e:
                logger.error(f"[DecisionHub] attachment reference handling failed: {e}", exc_info=True)

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
            reply = run_agent(text, sender_user_id, channel="telegram", raw_event_id=str(update.update_id))
        except Exception as e:
            from core.error_reporter import report_error
            report_error(e, context="run_agent (telegram)")
            reply = "⚠️ קרתה שגיאה בעיבוד ההודעה. נסה שוב בעוד רגע."
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

    # F16 — Media Layer: voice notes / photo / document uploads
    if update.message and update.message.content_type in ("voice", "photo", "document"):
        # C20 — an /update session waiting on its free-text step must claim
        # the next photo/document itself; otherwise it silently falls
        # through to the generic Drive-upload flow below and the pending
        # state is orphaned until its TTL expires (see cmd_update.py).
        if update.message.content_type in ("photo", "document"):
            try:
                from cmd_update import has_pending_file_capture, capture_photo_or_document
                if has_pending_file_capture(str(update.message.from_user.id)):
                    capture_photo_or_document(bot, update.message, resolve_identity)
                    return "", 200
            except Exception as e:
                logger.error(f"[/update] file capture routing failed: {e}", exc_info=True)
        _handle_telegram_media(update.message)
        return "", 200

    return "", 200


@app.route("/whatsapp", methods=["POST"])
def webhook_whatsapp():
    """H2 top-level handler — דק, מעביר ל-impl ומדווח שגיאות לא-מטופלות."""
    try:
        return _webhook_whatsapp_impl()
    except Exception as e:
        from core.error_reporter import report_error
        report_error(e, context="webhook_whatsapp")
        raise


def _webhook_whatsapp_impl():
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

    # domain לפי מספר היעד — Layer 1 של domain_router
    domain_from_channel = _channel_domain(to_number)

    dedup_key = msg_sid if msg_sid else incoming
    if idempotency.is_duplicate("whatsapp", sender, dedup_key):
        return _empty_twiml()

    # ── BUG-071 FIX: WhatsApp Media Support ─────────────────────────────
    # Extract and process media (voice/file) from Twilio webhook.
    # Per F13 architecture: metadata extraction + byte download from signed URL,
    # routed through unified media_handler pipeline (same as Telegram C90).
    try:
        from whatsapp_media_adapter import (
            extract_whatsapp_media, download_whatsapp_media, infer_file_type, infer_filename
        )
        from media_handler import handle_voice_note, handle_file_upload
        from identity import resolve_identity

        media_meta = extract_whatsapp_media(request.values.to_dict())
        if media_meta:
            try:
                _media_identity = resolve_identity("whatsapp", sender)
                owner_chat_id = os.environ.get("OWNER_TELEGRAM_ID", "") or \
                                os.environ.get("ELIYAHU_CHAT_ID", "") or \
                                os.environ.get("DIGEST_CHAT_ID", "")

                file_bytes = download_whatsapp_media(media_meta["media_url"])
                if file_bytes:
                    mime_type = media_meta["mime_type"]
                    file_type = infer_file_type(mime_type)
                    filename = infer_filename(media_meta["media_url"], mime_type, media_meta["file_id"])

                    if file_type == "audio":
                        # Voice note → transcription pipeline
                        result = handle_voice_note(
                            file_bytes, mime_type, media_meta["file_id"],
                            sender, domain_from_channel, owner_chat_id, source="whatsapp"
                        )
                        logger.info(f"[WhatsApp] voice note processed: ok={result.ok}, has_transcript={bool(result.normalized_transcript)}")
                    else:
                        # File/image/video → Drive upload + Media Files record
                        result = handle_file_upload(
                            file_bytes, filename, mime_type, file_type,
                            media_meta["file_id"], sender, domain_from_channel,
                            source="whatsapp", linked_lead_id=""
                        )
                        logger.info(f"[WhatsApp] file uploaded: ok={result.ok}, file_size_tier={result.file_size_tier}")

                    if not result.ok and result.error and result.error.error_message:
                        logger.warning(f"[WhatsApp] media processing failed: {result.error.error_message}")
            except Exception as e:
                logger.warning(f"[WhatsApp] media handler error: {e}", exc_info=True)
    except ImportError:
        logger.debug("[WhatsApp] media adapter not available, skipping media handling")
    except Exception as e:
        logger.warning(f"[WhatsApp] media extraction error: {e}", exc_info=True)

    if _inject_utm and _flag_enabled("AD_ATTRIBUTION"):
        try:
            # תיקון: memory_key קנוני — boss_hq:+972... (כמו ש-identity.memory_key
            # מחזיר), לא whatsapp:+972... — אחרת _inject_utm מחפש/כותב ב-Airtable
            # עם key שלעולם לא תואם את הרשומה האמיתית שנוצרת ע"י lead_capture,
            # וגורם לחיפוש כפול (whatsapp:... נכשל, אח"כ boss_hq:... מצליח).
            _early_identity = resolve_identity("whatsapp", sender)
            _inject_utm(
                memory_key   = _early_identity.memory_key,
                request_args = request.values.to_dict(),
                channel      = "whatsapp",
            )
        except Exception as _utm_err:
            # BUG-057 FIX: היה logger.debug — הסתיר כשל שקט בכל הודעה
            # נכנסת (utm_source/medium/campaign/platform לא קיימים ב-schema_cache.json)
            logger.warning(f"[UTM] whatsapp inject failed: {_utm_err}")

    # furniture funnel pre-agent intercept — only when domain == "furniture_import"
    # if FURNITURE_TWILIO_WHATSAPP_NUMBER is unset, get_domain() returns "general" → skipped
    try:
        from furniture_lead_funnel import handle_furniture_lead_message
        funnel_reply = handle_furniture_lead_message(sender, incoming, domain_from_channel)
        if funnel_reply:
            gated_reply = _gateway_whatsapp_reply(sender, funnel_reply, domain_from_channel, msg_sid or sender)
            resp = MessagingResponse()
            if gated_reply is not None:
                resp.message(gated_reply)
            return Response(str(resp), mimetype="application/xml")
    except Exception as e:
        logger.warning("[FurnitureFunnel] fallback to agent: %s", e)

    _resolved = {}
    _run_meta = {}
    agent_reply = run_agent(
        incoming, sender,
        channel             = "whatsapp",
        domain_from_channel = domain_from_channel,
        _resolved_domain    = _resolved,
        _out_meta           = _run_meta,
        raw_event_id        = msg_sid,
    )
    # תיקון: COG מקבל את הדומיין הסופי (אחרי Router), לא domain_from_channel
    # הישן שנקבע לפני שה-Router רץ — אחרת domain=general נרשם ב-COG גם
    # כששה-Router/Context זיהו דומיין אחר (למשל real_estate).
    final_domain = _resolved.get("domain") or domain_from_channel
    # BUG-SB-01: propagate source_module from gateway replies to avoid Single Speaker false-block
    _reply_source = _run_meta.get("source_module", "app.webhook_whatsapp")
    gated_reply = _gateway_whatsapp_reply(sender, agent_reply, final_domain, msg_sid or sender,
                                          source_module=_reply_source)
    resp = MessagingResponse()
    if gated_reply is not None:
        resp.message(gated_reply)
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

    # ── BUG-071 FIX: Meta WhatsApp Media Support ───────────────────────────
    # Extract media (image/video/audio/document), fetch download URL from Meta API,
    # and route through unified media_handler pipeline.
    try:
        media_meta = normalized.get("media")
        if media_meta:
            try:
                from meta_whatsapp_media_adapter import (
                    get_meta_media_download_url, infer_mime_type_from_meta_type
                )
                from media_handler import handle_voice_note, handle_file_upload
                from identity import resolve_identity

                # Fetch download URL from Meta API
                access_token = os.environ.get("META_BUSINESS_TOKEN", "")
                if not access_token:
                    logger.warning("[Meta WhatsApp] no META_BUSINESS_TOKEN — skipping media download")
                else:
                    media_url = get_meta_media_download_url(media_meta["media_id"], access_token)
                    if media_url:
                        # Download bytes from Meta-signed URL
                        try:
                            import requests
                            resp = requests.get(media_url, timeout=30)
                            resp.raise_for_status()

                            file_bytes = resp.content
                            if len(file_bytes) > 50 * 1024 * 1024:  # 50MB limit
                                logger.warning("[Meta WhatsApp] media too large: %d bytes", len(file_bytes))
                            else:
                                _media_identity = resolve_identity("whatsapp", sender)
                                owner_chat_id = os.environ.get("OWNER_TELEGRAM_ID", "") or \
                                                os.environ.get("ELIYAHU_CHAT_ID", "") or \
                                                os.environ.get("DIGEST_CHAT_ID", "")

                                mime_type = infer_mime_type_from_meta_type(
                                    media_meta["media_type"], media_meta.get("filename", "")
                                )
                                filename = media_meta.get("filename") or f"meta_{media_meta['message_id']}"

                                if media_meta["media_type"] == "audio":
                                    result = handle_voice_note(
                                        file_bytes, mime_type, media_meta["message_id"],
                                        sender, domain_from_channel, owner_chat_id, source="whatsapp_meta"
                                    )
                                    logger.info(f"[Meta WhatsApp] voice note processed: ok={result.ok}")
                                else:
                                    result = handle_file_upload(
                                        file_bytes, filename, mime_type, media_meta["media_type"],
                                        media_meta["message_id"], sender, domain_from_channel,
                                        source="whatsapp_meta", linked_lead_id=""
                                    )
                                    logger.info(f"[Meta WhatsApp] file uploaded: ok={result.ok}")
                        except Exception as e:
                            logger.warning(f"[Meta WhatsApp] media download/process failed: {e}")
            except ImportError:
                logger.debug("[Meta WhatsApp] media adapter not available")
            except Exception as e:
                logger.warning(f"[Meta WhatsApp] media handler error: {e}", exc_info=True)
    except Exception as e:
        logger.warning(f"[Meta WhatsApp] media extraction error: {e}", exc_info=True)

    if not _flag_enabled("META_OUTBOUND_ENABLED"):
        logger.info(
            "[Meta WhatsApp] inbound received — outbound stub, skipping run_agent. "
            "Set META_OUTBOUND_ENABLED=true to activate."
        )
        return jsonify({"status": "received_no_outbound"}), 200

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
    return "The Boss is Live v3.0 — CORE_02.6 Router ✅"


# ══════════════════════════════════════════════════
# F07 — Voice IVR (Twilio)
# ══════════════════════════════════════════════════

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    if not _validate_twilio_signature():
        from_num = request.form.get("From", "unknown")
        logger.warning("[Voice] invalid Twilio signature from %s — possible spoofing", from_num)
        return Response("Forbidden", status=403)
    from feature_flags import is_enabled
    from voice_adapter import build_twiml, _say, _hangup, process_voice_step
    if not is_enabled("VOICE_IVR"):
        return Response(build_twiml(_say("השירות לא פעיל.") + _hangup()), mimetype="text/xml")
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
