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
from tool_registry   import enforce, get as get_tool_meta, ToolDenied
from scheduler       import start_scheduler
from tools           import dispatch_tool
from tools.airtable_security import enforce_leads_write_gate, LeadsDirectWriteBlocked
from guards          import idempotency, rate_limiter, validate_tool_output
from config          import get_domain as _channel_domain
from core.router     import route_request, RouteDecision, Handler
from core.router.deterministic_denial import check_deterministic_denial
from core.anti_hallucination import (
    verify_execution, sanitize_agent_response,
    _SINGLE_SPEAKER_FALLBACK, _has_write_tool_evidence,
)
from core.turn_evidence import TurnEvidenceSummary, observe_shadow_finalizer
from health_monitor import get_health_status
from feature_flags import is_enabled as _flag_enabled, get_evidence_finalizer_state
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

# ─── PA-01 — Phantom Approval Prompt structural enforcement ─────────
# docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md (approved commit
# 81676ad). State-only: never read for text-detection purposes — these two
# constants are the only user-facing text the mechanism ever introduces, and
# _pa01_structured_terminal_outcome() only ever reads structured
# tool_results_log keys, never final_reply.
_PA01_PHANTOM_APPROVAL_FALLBACK = (
    "לא הצלחתי להכין את הפעולה לאישור, ולכן לא נוצרה כרגע פעולה שממתינה. "
    "אפשר לשלוח שוב את הבקשה."
)
_PA01_CAPABILITY_UNAVAILABLE_FALLBACK = (
    "לא ניתן לבצע את הפעולה הזו דרך החשבון הנוכחי. "
    "לביצוע, יש לפנות למנהל מורשה."
)


def _pa01_structured_terminal_outcome(
    tool_results_log: list, expected_tool: str | None,
) -> tuple | None:
    """
    Scoped lookup (PA-01_PLANNING_GATE.md §4.2f) — only a tool_results_log
    entry whose own tool identity matches expected_tool counts as a
    terminal outcome for this intent. A denial/preflight-block/queue-error
    for a different tool the agent also touched this turn is invisible
    here. Returns (outcome_kind, gate_authored_message) or None.
    """
    if expected_tool is None:
        return None
    for r in tool_results_log:
        outcome = r.get("terminal_outcome")
        if not outcome:
            continue
        # Queue/BUG-122 sentinels carry canonical identity in action_tool,
        # while "tool" is the fixed structural sentinel name.
        entry_tool = (
            r.get("action_tool")
            if r.get("tool") in (
                "__approval_queued__",
                "__approval_deferred_batch__",
                "__approval_blocked_pending__",
            )
            else r.get("tool")
        )
        if entry_tool == expected_tool:
            return outcome, r.get("content", "")
    return None


def _pa01_contract_created_for_expected_tool(
    tool_results_log: list, expected_tool: str | None,
) -> bool:
    """
    Row 2's own predicate, exact (PA-01_PLANNING_GATE.md §8, canonical-tool-
    wiring/created_this_turn follow-up): a __approval_queued__ sentinel only
    counts as "a contract was created for this intent this turn" when ALL
    five hold — a real sentinel, ok=True, no terminal_outcome, created_this_
    turn=True, and its action_tool matches expected_tool. A non-None
    contract_id alone is NOT sufficient: ActionGateway.propose_action() also
    returns a real, non-None contract_id for a rejected/duplicate/pre-
    existing contract it merely found (never created this turn) — see
    _queue_approval_detailed_impl()'s own docstring. Scans the full log
    (never stops at the first entry) — a matching sentinel anywhere in a
    multi-tool-call turn is found regardless of position.
    """
    if expected_tool is None:
        return False
    return any(
        r.get("tool") == "__approval_queued__"
        and r.get("ok") is True
        and r.get("terminal_outcome") is None
        and r.get("created_this_turn") is True
        and r.get("contract_id")
        and r.get("action_tool") == expected_tool
        for r in tool_results_log
    )

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

# Staging finding #4 (23/07/2026): natural-language "what's waiting for
# approval" questions (e.g. "לאשר את הפעולות שממתינות לאישור", "מה ממתין
# לאישור") don't match _CONFIRM_WORDS' exact-word grammar, so they used to
# fall straight through to the general agent — which has no ActionContracts
# tool and guessed at an ordinary Airtable table (observed: airtable_get
# table="Tasks") instead of ever finding the real pending contracts.
# Deliberately narrow/conservative (requires both a "pending" word and either
# an "approval" word or an interrogative nearby) so it only intercepts
# genuine pending-approval queries, not an unrelated free-text message that
# happens to contain one of the words alone.
#
# "ממתי\w*" (not "ממתינ\w*") — deliberate, mirrors PR #399/BUG-113's fix for
# the same class of bug: "ממתין" ends in final-form nun (ן, U+05DF), a
# different Unicode character from the regular nun (נ, U+05E0) inside
# "ממתינה"/"ממתינות" — a literal prefix ending in the regular nun never
# matches the bare "ממתין" form at all, regardless of a trailing \w*.
_PENDING_QUERY_RE = re.compile(
    r"(?:ממתי\w*|מחכ\w*).{0,20}(?:לאישור|אישור|לאשר)"
    r"|(?:לאישור|אישור|לאשר).{0,20}(?:ממתי\w*|מחכ\w*)"
    r"|(?:מה|אילו|איזה|רשימת).{0,15}(?:ממתי\w*|מחכ\w*)"
)

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

# Router-level (free-text "מאשר") pending approvals expire after this many
# seconds — matches the "פג תוקף בעוד 10 דקות" ("expires in 10 minutes")
# wording shown on the Telegram inline approval button (_queue_approval()).
#
# BUG-112: this constant alone did NOT protect the Telegram callback path.
# event_bus.py's PendingActionsStore has its OWN, separate, longer TTL
# (PENDING_TTL_MINUTES = 30 minutes) — a general cleanup horizon for the
# whole store, unrelated to what any specific approval message advertises.
# bus.pop(action_id) inside _handle_approval_callback_impl() only enforced
# THAT 30-minute window, so a button press between minute 10 and minute 30
# still executed the tool even though the user was told it would have
# expired by minute 10. _handle_approval_callback_impl() now enforces this
# SAME _PENDING_APPROVAL_TTL value independently, right after popping the
# bus item — see the "BUG-112" comment there.
_PENDING_APPROVAL_TTL = 600

# BUG-122: observational-only staleness threshold for live ActionContracts
# (core.action_gateway's ExecutionLedger — a "pending" contract has no TTL
# of its own; it stays live until explicitly approved/rejected/superseded).
# Used ONLY to log stale_contracts_count for visibility into queue
# pollution — never to auto-expire/auto-reject a contract. Mirrors C84's
# TMA Approvals TTL (24h — asynchronous review, not a push-notification
# button checked within minutes), the closest existing precedent for "how
# old is too old for a pending item nobody has acted on."
_LIVE_CONTRACT_STALE_SECONDS = 24 * 60 * 60

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
telebot.apihelper.ENABLE_MIDDLEWARE = True  # נדרש לפני TeleBot() — אחרת middleware_handler לא נרשם
bot    = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)  # webhook mode — handlers ירוצו סינכרונית, לפני שה-response חוזר


@bot.middleware_handler(update_types=['message'])
def log_all_exceptions(bot_instance, update):
    pass


class _TelebotExceptionHandler(telebot.ExceptionHandler):
    """telebot._handle_exception() calls self.exception_handler.handle(exception)
    — it requires an OBJECT with a .handle() method, not a bare function. A
    plain function here (the previous bug) makes that lookup itself raise
    AttributeError: 'function' object has no attribute 'handle', which then
    propagates in place of whatever the real original exception was —
    masking every command-handler error with the same useless message
    (see BUG_AUDIT_LOG.md's entry for this bug, found 20/07/2026)."""

    def handle(self, exception):
        logger.error(f"[Telebot] unhandled: {exception}", exc_info=True)
        return False  # not "handled" -> telebot re-raises the ORIGINAL exception,
        # so app.py's own try/except around process_new_updates() (the
        # /command dispatch path, report_error(context="command_dispatch"))
        # still sees and reports the real error.


bot.exception_handler = _TelebotExceptionHandler()

app = Flask(__name__)

# Phase 4B0.1A/B — Verify atomic claims health (migrations run via pre-deploy command)
# Migrations are executed as Render Pre-Deploy Command: python -m core.predeploy
# (runs database_migrations.run_migrations() then the Emergency Stop preflight —
# see core/predeploy.py). This checks health only; actual migration execution
# happens before app starts.
try:
    from feature_flags import is_enabled
    if is_enabled("FEATURE_ATOMIC_CLAIMS"):
        from core.atomic_claims_health import log_health_on_startup
        log_health_on_startup()
except ImportError:
    pass
except Exception as e:
    logging.error(f"Atomic claims health check failed: {e}")
    raise


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


# PR-0C Phase 3: send_followup.confirmed / send_recovery.confirmed subscribers
# removed — followup_engine.py/core/lead_recovery.py now queue tool_name=
# "send_followup"/"send_recovery" payloads, so this same logic runs via
# tools/approval_actions.py (through ActionGateway.approve() when
# FEATURE_ACTION_GATEWAY is on) from the tool_name branch below, not from a
# .confirmed event anymore.



@bot.message_handler(commands=["status"])
def cmd_status(msg):
    """Owner בלבד — מצב env vars."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    text = format_startup_message()
    try:
        bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException as e:
        # BUG-121: the message body includes raw env-var names (e.g.
        # GOOGLE_CLIENT_ID) — Telegram's legacy Markdown parser can choke on
        # their underscores ("Can't parse entities") and raise here. Retry
        # once as plain text so /status still gets through instead of
        # silently failing (previously masked entirely by BUG-120).
        logger.warning(f"[Command] /status Markdown send failed, retrying as plain text: {e}")
        bot.send_message(msg.chat.id, text)


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

_scheduler = None  # set inside run_startup_sequence(); globals().get("_scheduler") used by /health


def run_startup_sequence() -> None:
    """
    The explicit runtime startup entrypoint for this service — called once
    by gunicorn.conf.py's post_worker_init hook in production (Start
    Command stays `gunicorn app:app`; gunicorn auto-loads
    ./gunicorn.conf.py with no other change needed) and by
    `if __name__ == "__main__":` below for local/dev `python3 app.py` runs.

    Deliberately NOT invoked as a side effect of merely importing this
    module — `import app` (a test, a tool, or gunicorn loading the module
    to grab the WSGI `app` object) must never reach Airtable or start the
    scheduler on its own. Everything above this function definition (Flask
    routes, Telegram command handlers, tool/registry wiring) is plain
    Python object/decorator registration — no network I/O — and stays at
    module level exactly as before; only the two things that actually do
    I/O or spawn a background thread (the Emergency Stop bootstrap and the
    scheduler) live here now.

    Order is load-bearing (PATCH 3B Step 5): bootstrap_emergency_stop()
    (construct store + manager, configure, hydrate) always runs to
    completion — successfully or with a documented degraded outcome
    (Airtable unavailable / durable schema-data invalid, both reported via
    the returned result, never raised) — before start_scheduler() runs.
    An UNEXPECTED bootstrap failure (a construction/import/configure bug —
    not one of the two documented outcomes above) is deliberately NOT
    caught here or inside bootstrap_emergency_stop() itself: it propagates
    out of this function, so a real programming/configuration bug is
    exposed loudly and the scheduler is never started. See
    core/emergency_stop_bootstrap.py's module docstring for the exact
    documented-vs-unexpected distinction.

    Still dual-path after this step: nothing in production — no
    is_enabled()/set_flag() caller, no tma_api/cost_monitor/scheduler
    caller — reads from the manager bootstrap_emergency_stop() configures
    here. Cutover is a separate, later, atomic step.
    """
    from core.emergency_stop_bootstrap import bootstrap_emergency_stop
    result = bootstrap_emergency_stop()
    logger.info(
        "[EmergencyStop] bootstrap: configured=%s store_status=%s flags_loaded=%d",
        result.configured, result.store_status, result.flags_loaded,
    )

    global _scheduler
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


# BUG-123-FU (approval message rendering): shown when a business-readable
# description cannot be safely built from the tool's inputs — fail closed
# instead of leaking a raw "?" placeholder, tool_name, or internal dict
# repr into user-facing approval text.
_APPROVAL_DESCRIPTION_FALLBACK = "לא הצלחתי להכין תיאור ברור לבקשה הזו. נא לנסח את הבקשה שוב."


def _describe_tool_call(tool_name: str, inputs: dict) -> str:
    """תיאור קריא-לעסק של קריאת כלי, לכפתורי/הודעות אישור.

    BUG-123-FU: לעולם לא חושף tool_name/record_id/contract_id גולמיים
    בטקסט הפונה למשתמש (callback_data של הכפתור, לא הטקסט הגלוי, הוא
    המקום הנכון למזהים טכניים — ראה _queue_approval_detailed_impl()).
    אם אין מספיק מידע עסקי לבנות תיאור אמיתי (טבלה/fields חסרים או
    מעוותים) — נכשל-סגור עם _APPROVAL_DESCRIPTION_FALLBACK, לא עם placeholder
    ("?") שהמשתמש לא יכול להבין ממנו כלום.
    """
    if tool_name == "gmail_send_draft":
        return "📧 שלח מייל"
    if tool_name == "calendar_create_event":
        summary = inputs.get("summary")
        if not summary:
            return _APPROVAL_DESCRIPTION_FALLBACK
        start = str(inputs.get("start_time", "") or "")[:16]
        return f"📅 קבע: {summary}" + (f" ב-{start}" if start else "")
    if tool_name in ("airtable_add", "airtable_update"):
        table = inputs.get("table")
        fields = inputs.get("fields")
        if not table or not isinstance(fields, dict) or not fields:
            return _APPROVAL_DESCRIPTION_FALLBACK
        fields_preview = "\n".join(
            f"  • {k}: {_format_field_value(k, v)}" for k, v in fields.items()
        )
        if tool_name == "airtable_add":
            return f"➕ הוסף ל-{table}:\n{fields_preview}"
        # airtable_update: record_id is a raw Airtable identifier — never
        # shown in user-facing text (BUG-123-FU requirement 3). The fields
        # being changed are the meaningful business content here.
        return f"✏️ עדכן ב-{table}:\n{fields_preview}"
    if tool_name == "sheets_append":
        sheet = inputs.get("sheet_name")
        if not sheet:
            return _APPROVAL_DESCRIPTION_FALLBACK
        return f"📊 כתוב ל-{sheet}"
    # Unknown/uncovered tool — never leak the raw tool_name or an inputs
    # dict repr (could contain internal keys/ids) into user-facing text.
    return _APPROVAL_DESCRIPTION_FALLBACK


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


# PA-01 approval-queue failure recovery helpers were mechanically extracted
# to core/approval_queue_recovery.py (structural cleanup, no behavior change).
# Re-imported here so app.py's existing call sites — and the tests that
# reference app._revoke_and_verify_contract / app._orphan_cleanup_failure_
# response — keep resolving them unchanged.
from core.approval_queue_recovery import (  # noqa: E402
    _SAFE_CANCELLED_CONTRACT_STATUSES,
    _revoke_and_verify_contract,
    _cancel_and_verify_pending,
    _orphan_cleanup_failure_response,
)


def _queue_approval(tool_name: str, tool_inputs: dict,
                    user_chat_id: str, channel: str, user_text: str = "") -> str:
    """
    שומר פעולה ממתינה ושולח בקשת אישור לowner.
    מחזיר string לmodel: "⏳ ממתין לאישור..."
    Thin wrapper over _queue_approval_detailed() — kept string-returning for
    every existing caller/test that already depends on that contract; the
    raw Agent tool_use loop calls _queue_approval_detailed() directly since
    PA-01 needs the structured outcome, not just the message (see
    docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §4.2a —
    planning assumed the Gateway's own result object was already in scope
    at the tool-loop call site; in the real code it is local to this
    function, hence this split).
    """
    return _queue_approval_detailed(tool_name, tool_inputs, user_chat_id, channel, user_text)["message"]


def _queue_approval_detailed(tool_name: str, tool_inputs: dict,
                             user_chat_id: str, channel: str, user_text: str = "") -> dict:
    """
    Same behavior as _queue_approval() (see that docstring), but returns a
    structured outcome instead of just the model-facing message:
      {"message": str, "contract_id": str|None, "ok": bool,
       "terminal_outcome": str|None, "action_tool": str, "created_this_turn": bool}

    "created_this_turn" — PA-01 Main Integration Pass follow-up finding —
    is the single most load-bearing key here and is deliberately NOT
    inferred from contract_id truthiness: ActionGateway.propose_action()
    can return a non-None contract_id for a REJECTED/DUPLICATE/PRE-EXISTING
    contract too (existing.status == "pending"/"approved"/"executing"/
    "outcome_unknown" all return GatewayResult(ok=False, contract_id=
    existing.contract_id, ...) — core/action_gateway.py's own propose_action()
    body). A contract_id is therefore evidence a contract EXISTS, never proof
    it was created THIS turn. "created_this_turn" is set True on exactly one
    branch: the final success return below, and only when the underlying
    GatewayResult itself reports ok=True — which propose_action() only ever
    returns immediately after saving a brand-new ActionContract with a fresh
    uuid4() id (verified against that function's own body, not assumed).
    Every other branch — including shadow mode's own success-shaped return
    when the underlying proposal was itself a dedup/rejection that shadow
    mode doesn't block on — sets it False.

    "terminal_outcome" is None only for a genuine successful contract
    creation (created_this_turn=True). Every other branch sets one of two
    values, and the distinction is load-bearing (Codex re-audit of
    818c8a6):

      "APPROVAL_QUEUE_ERROR" — VERIFIED clean. Either provably no contract
      was ever attempted this call (duplicate fingerprint, cross-channel
      duplicate, propose_action()'s own pre-existing-contract dedup, or its
      failure_code="persistence_lookup_failed", which fails before any
      candidate contract is even constructed), or a contract this call
      proved it owns was revoked AND that revocation was independently
      re-verified by exact status (see _revoke_and_verify_contract()).
      contract_id=None here is a confirmed fact, not an assumption.

      "APPROVAL_QUEUE_ORPHANED" — unverified/unattributable. Used whenever
      ownership of any contract_id was never proven for this call (an
      exception from propose_action() itself, a
      failure_code="persistence_failed" acknowledgment-uncertain failure,
      or a canonicalization failure) OR a proven-owned contract's
      revoke/cancel could not be confirmed. contract_id here is either the
      real, proven-owned id (if cleanup on it failed verification) or None
      (if no id was ever attributable to this call at all) — see
      _orphan_cleanup_failure_response()'s own docstring for the exact
      distinction. This is a conservative "cannot verify, do not assume
      clean" state, never a claim that a contract definitely exists.

    ActionGateway's own rejection/dedup/pre-existing-contract paths return a
    real, non-None contract_id alongside APPROVAL_QUEUE_ERROR by design —
    that id points at an EXISTING contract this call did not create (kept
    for telemetry only), which is a different, already-understood situation
    from either of the two above.

    "action_tool" is the CANONICAL tool_name — after resolve_canonical_tool()
    below, the same name used for the fingerprint, the label, the EventBus
    payload, and the ActionGateway contract itself — on every branch,
    including the early-return ones (canonicalization happens once, before
    any of them). Never the pre-canonicalization tool_use block's own name.

    Exception safety: the caller-facing wrapper below this function's `_impl`
    catches any exception from ANY of this function's operations (EventBus,
    fingerprint/dedup lookups, cross-channel dedup, Gateway proposal, owner
    notification) and normalizes it to this exact same 6-key shape — no
    branch here, and no exception escaping this function, ever reaches the
    tool loop as anything other than this dict shape.

    PR #188: blocks re-queuing via executed_action_cache (raw chat_id fingerprint).
    Stage A: also dedupes cross-channel via canonical identity.memory_key.

    BUG-CANONICAL-TOOL-WIRING: resolved here, once, before anything else uses
    tool_name (dedup fingerprint, button label, legacy bus payload, and the
    ActionGateway contract all must agree) — resolving only inside
    propose_action() would leave the legacy bus item and button label
    pointing at the original (e.g. sheets_append) hint while the durable
    contract stores the resolved one (e.g. airtable_add), reintroducing the
    same fingerprint-mismatch class of bug fixed for the post-completion
    callback fallthrough (the button would fall through to a legacy dispatch
    of the wrong tool).
    """
    try:
        return _queue_approval_detailed_impl(tool_name, tool_inputs, user_chat_id, channel, user_text)
    except Exception as exc:
        # Fail-closed, uniform shape (decision 5 in this program's
        # fail-safe-degraded policy, extended here to _queue_approval_detailed
        # itself): any unexpected exception from EventBus/dedup/Gateway/owner-
        # notify is a queue-time failure, never a phantom success, and never
        # a raw exception reaching the tool loop for it to guess a shape from.
        logger.error(
            "[Approval] _queue_approval_detailed unexpected error: tool=%s error_type=%s",
            tool_name, type(exc).__name__, exc_info=True,
        )
        # action_tool must stay canonical in EVERY branch, including this
        # outermost catch-all: _impl's own canonicalized local `tool_name`
        # variable is lost when its frame unwinds on an exception — this
        # handler only ever sees ITS OWN parameter, the raw pre-
        # canonicalization name. resolve_canonical_tool() is pure/idempotent,
        # so recomputing it here (once) is safe and correct even when the
        # exception happened deep inside _impl, after it had already
        # canonicalized internally. Falls back to the raw name (telemetry
        # only) if canonicalization itself is what raised — the one case
        # where "canonical" is genuinely unknowable.
        try:
            from core.action_gateway import resolve_canonical_tool as _resolve_for_cleanup
            _canonical_tool_name = _resolve_for_cleanup(tool_name, tool_inputs, user_text)
        except Exception:
            _canonical_tool_name = tool_name

        # Codex re-audit of 818c8a6 — architectural ruling: this handler has
        # no contract_id proven to belong to THIS call (if it did, the
        # exception would have been handled locally in _impl by one of the
        # ownership-proven cleanup sites below, which never reach here).
        # A fingerprint match cannot substitute for that proof — it would
        # equally match a pre-existing contract from an earlier turn or a
        # concurrently-created one from a different turn, and mutating
        # either would silently interfere with a request this call has no
        # authority over. No lookup, no revoke — the conservative, honest
        # answer is "ownership not established," not "confirmed clean."
        return _orphan_cleanup_failure_response(_canonical_tool_name, None)


def _queue_approval_detailed_impl(tool_name: str, tool_inputs: dict,
                                  user_chat_id: str, channel: str, user_text: str = "") -> dict:
    from core.action_gateway import resolve_canonical_call
    tool_name, tool_inputs = resolve_canonical_call(
        tool_name, tool_inputs, user_text
    )

    from event_bus import bus, executed_action_cache, pending
    fp = executed_action_cache.compute(user_chat_id, tool_name, tool_inputs)
    if executed_action_cache.is_recently_executed(fp):
        logger.warning(
            f"[Approval] duplicate fingerprint blocked: {fp[:8]} | {tool_name} | user={_sanitize_id(user_chat_id)}"
        )
        return {
            "message": f"⚠️ פעולה זו כבר בוצעה לאחרונה ({tool_name}). כפילות נחסמה.",
            "contract_id": None, "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
            "action_tool": tool_name, "created_this_turn": False,
        }

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
        return {
            "message": f"⏳ הפעולה כבר ממתינה לאישור הבעלים{' (מ-' + origin + ')' if origin else ''}.",
            "contract_id": None, "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
            "action_tool": tool_name, "created_this_turn": False,
        }

    label     = _describe_tool_call(tool_name, tool_inputs)

    # Stage B (shadow mode): ActionGateway ב-FEATURE_ACTION_GATEWAY=false.
    # propose_action רושם contract ל-ledger ולמעקב — לא חוסם את המסלול הקיים.
    # כאשר הדגל פעיל: GatewayResult(ok=False) יחזיר כאן ויפסיק את הזרימה.
    from feature_flags import is_enabled as _flag
    _gw_result = None  # PA-01: keep defined even if the shadow-mode try/except below never assigns it
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
            trusted_source="agent",
            user_text=user_text,
        )
        if not _gw_result.ok:
            logger.info(
                "[ActionGateway] propose blocked: %s | contract=%s",
                _gw_result.reason, _gw_result.contract_id,
            )
            if _gw_result.failure_code == "persistence_failed":
                # Codex re-audit of 818c8a6, P1-3: self._ledger.save()
                # raising does not prove the durable write never landed —
                # ActionGateway gives no explicit "definitely not written"
                # signal for this failure_code (unlike persistence_lookup_
                # failed below, which fails BEFORE any candidate contract is
                # even constructed). No contract_id was returned either, so
                # ownership cannot be proven — no cleanup attempt is possible,
                # and this must not claim verified-clean.
                return {
                    "message": _gw_result.user_message or f"⏳ {_gw_result.reason}",
                    "contract_id": None, "ok": False,
                    "terminal_outcome": "APPROVAL_QUEUE_ORPHANED",
                    "action_tool": tool_name, "created_this_turn": False,
                }
            if _gw_result.failure_code == "existing_pending_blocks_agent":
                return {
                    "message": _gw_result.user_message or _gw_result.reason,
                    "contract_id": _gw_result.contract_id,
                    "ok": False,
                    "terminal_outcome": "APPROVAL_BLOCKED_PENDING",
                    "action_tool": tool_name,
                    "created_this_turn": False,
                }
            return {
                "message": _gw_result.user_message or f"⏳ {_gw_result.reason}",
                # contract_id, if present (dedup/pending/approved/executing
                # found, or persistence_lookup_failed which never attempts a
                # save at all), points at an EXISTING contract this call did
                # NOT create, or is None because nothing was ever attempted —
                # both are verified, not guessed. Kept here for telemetry
                # only; created_this_turn=False is what actually gates row 2.
                "contract_id": getattr(_gw_result, "contract_id", None),
                "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
                "action_tool": tool_name, "created_this_turn": False,
            }
    else:
        # Shadow mode records proposals without enforcement, except for the
        # canonical BUG-122 boundary shared by both gateway modes.
        try:
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
                trusted_source="agent",
                user_text=user_text,
            )
            if _gw_result.failure_code == "persistence_lookup_failed":
                # Structurally provable clean: this failure happens on the
                # very FIRST operation of propose_action(), before any
                # candidate contract is even constructed (core/action_
                # gateway.py's own propose_action() body) — genuinely
                # verified, not assumed.
                return {
                    "message": _gw_result.user_message or f"❌ {_gw_result.reason}",
                    "contract_id": None, "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
                    "action_tool": tool_name, "created_this_turn": False,
                }
            if _gw_result.failure_code == "existing_pending_blocks_agent":
                return {
                    "message": _gw_result.user_message or _gw_result.reason,
                    "contract_id": _gw_result.contract_id,
                    "ok": False,
                    "terminal_outcome": "APPROVAL_BLOCKED_PENDING",
                    "action_tool": tool_name,
                    "created_this_turn": False,
                }
            if _gw_result.failure_code == "persistence_failed":
                # Codex re-audit of 818c8a6, P1-3: acknowledgment-uncertain —
                # see the identical comment in the enforce-mode branch above.
                return {
                    "message": _gw_result.user_message or f"❌ {_gw_result.reason}",
                    "contract_id": None, "ok": False,
                    "terminal_outcome": "APPROVAL_QUEUE_ORPHANED",
                    "action_tool": tool_name, "created_this_turn": False,
                }
            # Shadow mode does not early-return on _gw_result.ok == False for
            # any other reason (dedup/pending/approved found) — by design, it
            # never blocks the legacy bus path. Falls through to bus.request_
            # approval() below regardless. _gw_result.ok is read again at the
            # success return to compute created_this_turn correctly for this
            # case (a shadow-mode dedup must not be reported as a fresh
            # creation just because the legacy path queued anyway).
        except Exception as _gw_exc:
            # P1-A re-audit: a real (non-GatewayResult) exception from
            # propose_action() is NOT the same as a structured failure_code —
            # the old code here logged at debug level and fell straight
            # through to bus.request_approval() below, producing a real
            # legacy EventBus pending item with NO canonical Gateway evidence
            # backing the "ממתין לאישור" message the user would then see.
            #
            # Codex re-audit of 818c8a6 — architectural ruling: propose_
            # action() can raise AFTER it has already durably saved a
            # contract but BEFORE returning a GatewayResult — _gw_result
            # stays None (its outer-scope init at the top of this function)
            # in exactly that case, so there is no contract_id PROVEN to
            # belong to this call. A fingerprint-based rediscovery was
            # previously attempted here (removed — see
            # _revoke_and_verify_contract()'s module comment) but fingerprint
            # match is not ownership proof: it could equally be a pre-
            # existing or concurrently-created contract from a different
            # call. Re-raises so _queue_approval_detailed()'s outer handler
            # returns the conservative, ownership-agnostic ORPHANED state —
            # never attempting a mutation this call cannot prove it owns.
            logger.error(
                "[ActionGateway] shadow propose raised unexpectedly (not a "
                "structured GatewayResult failure): %s", _gw_exc, exc_info=True,
            )
            raise

    try:
        action_id, _ = bus.request_approval(
            action  = tool_name,
            payload = {
                "tool_name":         tool_name,
                "tool_inputs":       tool_inputs,
                "contract_id":       _gw_result.contract_id if _gw_result else None,
                "origin_channel":    channel,
                "origin_chat_id":    user_chat_id,
                "canonical_user_id": identity.memory_key,
                "user_chat_id":      user_chat_id,
                "channel":           channel,
            },
            chat_id = user_chat_id,
            label   = label,
        )
    except Exception as _bus_exc:
        # P1-C re-audit: if propose_action() already durably saved a
        # brand-new ActionContract (_gw_result.ok=True) above, it must not be
        # left live+pending while this function returns contract_id=None —
        # revoke it before returning the structured failure.
        #
        # Codex re-audit of 8e05d67, P2: _gw_result.contract_id is known
        # precisely here (propose_action() already returned by this point),
        # so this uses it directly rather than a fingerprint rediscovery —
        # but the revoke itself is now VERIFIED (a fresh find_live_
        # contracts() re-query), never assumed just because reject() didn't
        # raise. If verification fails, the REAL contract_id is returned
        # with a distinct outcome rather than a false contract_id=None.
        logger.error(
            "[Approval] bus.request_approval failed after Gateway proposal: "
            "tool=%s error=%s", tool_name, _bus_exc, exc_info=True,
        )
        if _gw_result is not None and getattr(_gw_result, "ok", False) and getattr(_gw_result, "contract_id", None):
            if not _revoke_and_verify_contract(
                identity.memory_key, _gw_result.contract_id, "eventbus_publish_failed",
            ):
                return _orphan_cleanup_failure_response(tool_name, _gw_result.contract_id)
        return {
            "message": "❌ אירעה שגיאה בעת ניסיון להעביר את הפעולה לאישור. הפעולה לא בוצעה.",
            "contract_id": None, "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
            "action_tool": tool_name, "created_this_turn": False,
        }

    owner_chat_id = (
        os.environ.get("OWNER_TELEGRAM_ID", "") or
        os.environ.get("ELIYAHU_CHAT_ID", "") or
        os.environ.get("DIGEST_CHAT_ID", "")
    )
    # F52 PR6: proven (not assumed) — True only once bot.send_message() below
    # actually succeeds. Threaded into the return dict's "owner_notified" key
    # so the caller (the tool loop) can tell EvidenceFinalizerShadow a real
    # user/owner-visible message was sent this turn, even though A32's
    # Single-Speaker gate correctly returns "" for the agent's own text.
    _owner_notified = False
    if owner_chat_id:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(
            telebot.types.InlineKeyboardButton("✅ אשר", callback_data=f"approve:{action_id}"),
            telebot.types.InlineKeyboardButton("❌ בטל",  callback_data=f"reject:{action_id}"),
        )
        # BUG-123-FU: the raw action_id used to be shown directly in this
        # visible text ("ID: {action_id}") — a technical identifier with no
        # functional purpose here (routing is via the button's callback_data
        # above, or via display-index "1"/"2" for text-based disambiguation
        # elsewhere; nothing parses this ID back out of the message text).
        # Dropped from user-facing text entirely — the expiry countdown is
        # the only part of that line that's actually useful to the user.
        _legacy_pending_text = f"⏳ בקשת אישור\n\n{label}\n\nפג תוקף בעוד 10 דקות"
        # F52 PR6: shadow-only formatter pass — off (default) returns
        # _legacy_pending_text byte-identical; shadow computes+logs the
        # unified approval_pending text alongside it (never sent); on
        # returns the unified text instead. See
        # core.action_gateway.ActionGateway._render_pending_prompt().
        try:
            from core.action_gateway import action_gateway as _gw_render
            _pending_text = _gw_render._render_pending_prompt(
                tool_name, _gw_result.contract_id if _gw_result else None, _legacy_pending_text,
            )
        except Exception:
            logger.debug(
                "[F52 PR6] pending prompt formatter failed, using legacy text",
                exc_info=True,
            )
            _pending_text = _legacy_pending_text
        try:
            bot.send_message(
                owner_chat_id,
                _pending_text,
                reply_markup=kb,
            )
            _owner_notified = True
            logger.info(f"[Approval] ✅ sent to owner {_sanitize_id(owner_chat_id)} | {action_id}")
            # BUG-115: a bare "כן"/"מאשר" reply must resolve THIS contract,
            # not fall into ActionGateway's generic live-contract-count
            # disambiguation just because older unrelated contracts also
            # happen to still be pending. See
            # core.action_gateway.route_confirmation_word()'s bookmark check.
            if _gw_result is not None and getattr(_gw_result, "contract_id", None):
                try:
                    from session_store import lead_sessions as _ls_bm
                    _ls_bm.set_last_prompted_contract(
                        identity.memory_key, _gw_result.contract_id, kind="action_gateway",
                    )
                except Exception as exc:
                    logger.warning(f"[Approval] BUG-115 last-prompted-contract bookmark failed: {exc}")
        except Exception as e:
            logger.error(f"[Approval] ❌ failed to notify owner: {e}")
            # BOSS NEVER FAKES: לא מחזירים "ממתין לאישור" כשהשליחה נכשלה.
            # P1-C re-audit: by this point BOTH a live EventBus pending item
            # (created just above) and possibly a live ActionContract exist —
            # cancel/revoke both rather than silently returning
            # contract_id=None while they stay live and button-approvable
            # with no owner ever having seen the request.
            #
            # Codex re-audit of 8e05d67, P2/P3: both cleanups are now
            # VERIFIED (a fresh re-query after the attempt), never assumed
            # just because the cancel/revoke call itself didn't raise —
            # PendingActionsStore.cancel() and ActionGateway.reject() can
            # both complete "successfully" from this function's point of
            # view while the underlying item/contract remains live (reject()
            # in particular returns a message STRING on a durable-transition
            # failure, not an exception). If either cannot be confirmed
            # clear, the REAL contract_id is returned with a distinct
            # outcome instead of the false contract_id=None this re-audit
            # found.
            _pending_clear = _cancel_and_verify_pending(action_id, "owner_notify_failed")
            _contract_clear = True
            _live_contract_id = None
            if _gw_result is not None and getattr(_gw_result, "ok", False) and getattr(_gw_result, "contract_id", None):
                _live_contract_id = _gw_result.contract_id
                _contract_clear = _revoke_and_verify_contract(
                    identity.memory_key, _gw_result.contract_id, "owner_notify_failed",
                )
            if not _pending_clear or not _contract_clear:
                return _orphan_cleanup_failure_response(
                    tool_name, _live_contract_id if not _contract_clear else None,
                )
            return {
                "message": (
                    f"❌ לא הצלחתי לשלוח בקשת אישור לבעלים.\n"
                    f"הפעולה לא בוצעה: {label}"
                ),
                "contract_id": None, "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
                "action_tool": tool_name, "created_this_turn": False,
            }

    logger.info(f"[Approval] queued {action_id} | {tool_name} | user={_sanitize_id(user_chat_id)}")
    # created_this_turn tracks _gw_result.ok specifically, NOT contract_id
    # truthiness — propose_action() only ever returns ok=True immediately
    # after saving a brand-new ActionContract; ok=False with a populated
    # contract_id (dedup/pending/approved found) must never read as "created"
    # even though shadow mode falls through to this same success return.
    _created_this_turn = bool(_gw_result and getattr(_gw_result, "ok", False))
    _contract_id = _gw_result.contract_id if _gw_result else None
    return {
        "message": f"⏳ הפעולה ממתינה לאישור: {label}\nשלח *מאשר* כדי לאשר (בכל ערוץ).",
        "contract_id": _contract_id,
        "ok": _created_this_turn,
        "terminal_outcome": None if _created_this_turn else "APPROVAL_QUEUE_ERROR",
        "action_tool": tool_name,
        "created_this_turn": _created_this_turn,
        # F52 PR6: proven above, never assumed — see _owner_notified's own
        # comment at its assignment. Every other return branch in this
        # function implicitly omits this key; callers must read it via
        # .get("owner_notified", False), which is correctly False for all
        # of them (none actually sent the owner a message).
        "owner_notified": _owner_notified,
    }


def _promote_next_batch_item(canonical_user_id: str) -> None:
    """Discard legacy deferred items; automatic promotion is forbidden."""
    if not canonical_user_id:
        return
    try:
        from event_bus import batch_queue as _batch_queue
        queued = _batch_queue.count_pending(canonical_user_id)
        _batch_queue.clear(canonical_user_id)
        logger.info(
            "[BatchQueue] resolution_cleanup user=%s queue_count_before=%d "
            "queue_count_after=0 action=discard_no_promotion",
            _sanitize_id(canonical_user_id), queued,
        )
    except Exception as exc:
        logger.error(
            "[BatchQueue] resolution cleanup failed for user=%s: %s",
            _sanitize_id(canonical_user_id), exc, exc_info=True,
        )


def _gateway_reply_with_promotion(reply, canonical_user_id: str):
    """Compatibility wrapper: discard legacy deferred items after resolution."""
    _promote_next_batch_item(canonical_user_id)
    return reply


def _build_and_log_turn_envelope(
    identity, chat_id: str, session_snapshot: dict | None, entry_point: str = "run_agent",
    live_contracts_snapshot: list | None = None,
) -> None:
    """TurnCoordinator Phase 0 — observation only, log-only, no routing
    effect. See core/turn_envelope.py's module docstring for exact scope and
    docs/architecture/turn-coordinator/TURN_COORDINATOR_PROPOSAL_V2.md /
    docs/architecture/f52-unified-approval-runtime/audits/phase-4c/
    TURN_OWNERSHIP_EXTENSION.md for the design and call-site inventory.

    Reads already-live state (ActionGateway contracts, BatchQueueStore)
    purely for logging — never pops/mutates anything, never changes what
    run_agent() does next. Must never raise into the caller: this whole
    function is a best-effort side effect, called before any of this turn's
    own routing has run.

    session_snapshot: the SAME dict run_agent() already loaded via
    session_store.lead_sessions.get(chat_id) at "1.6 Session snapshot" —
    reused here instead of calling get_pending_lead_preview() (which does
    its own internal .get()), to preserve the single-Sessions-read-per-turn
    invariant test_session_snapshot.py (LL-11) guards. This inlines
    get_pending_lead_preview()'s own TTL check read-only — it deliberately
    does not replicate that method's expired-preview cleanup write, since
    Phase 0 must never mutate state.

    live_contracts_snapshot: the SAME list run_agent() already established at
    "1.65" — reused here instead of calling find_live_contracts() again
    (Case C read-amplification fix, TURN_OWNERSHIP_EXTENSION.md). Always
    provided by the one live caller (run_agent()); the None fallback below
    exists only for direct/standalone callers (tests) that construct their
    own envelope without going through run_agent()'s "1.65" step.

    Log content boundary: this runs unconditionally (no flag) on every turn,
    so identifiers embedded in queue_id (memory_key/chat_id — frequently a
    phone number for WhatsApp) are fingerprinted via _sanitize_id() before
    being placed anywhere a log line could reach, and lead-candidate
    PendingItem.id/label deliberately do NOT carry the raw phone/name — see
    inline notes below. No action payload, no user message text, and no
    business-record field values are ever passed to core/turn_envelope.py.

    entry_point: identifies which call site is calling, for the
    build_failed log below — lets a future second call site (TMA, the
    Telegram callback handler) be told apart from this one without adding a
    new mechanism.
    """
    try:
        from core.turn_envelope import (
            PendingItem, PendingQueueAwareness, build_turn_envelope, log_turn_envelope,
        )
        from core.action_gateway import action_gateway as _gw_te
        from event_bus import batch_queue as _bq_te

        live_contracts = (
            live_contracts_snapshot if live_contracts_snapshot is not None
            else _gw_te.find_live_contracts(identity.memory_key)
        )
        reconfirmation_required = any(
            getattr(c, "reconfirmation_required", False) for c in live_contracts
        )

        ac_queue = None
        if live_contracts:
            ac_queue = PendingQueueAwareness(
                queue_id=f"ac:{_sanitize_id(identity.memory_key)}",
                source="action_gateway",
                kind="action_contract",
                summary=f"{len(live_contracts)} live contract(s)",
                items=tuple(
                    # contract_id is an internal UUID, not PII — safe as-is.
                    PendingItem(
                        index=i + 1, id=getattr(c, "contract_id", "") or "",
                        kind="action_contract", label="",
                    )
                    for i, c in enumerate(live_contracts)
                ),
                approval_granularity="single_choice" if len(live_contracts) > 1 else "all_or_nothing",
                priority=3,
            )

        preview = None
        try:
            if session_snapshot:
                _candidate_preview = session_snapshot.get("pending_lead_preview")
                if _candidate_preview and (
                    time.time() - _candidate_preview.get("set_at", 0) <= 1800
                ):
                    preview = _candidate_preview
        except Exception:
            preview = None

        lead_queue = None
        if preview:
            candidates = preview.get("candidates") or []
            lead_queue = PendingQueueAwareness(
                queue_id=f"lead_preview:{_sanitize_id(chat_id)}",
                source="lead_capture",
                kind="lead_candidate",
                summary=f"{len(candidates)} candidate(s) pending",
                items=tuple(
                    # Deliberately NOT c["phone"]/c["name"] — Phase 0 has no
                    # consumer that needs the real value yet (to_log_dict()
                    # doesn't even serialize items today), so there is no
                    # reason to hold raw PII in this snapshot at all. A real
                    # label will be needed once Phase 2's
                    # resolve_numbered_reference() lands — that is an
                    # explicit future decision, not inherited silently here.
                    PendingItem(
                        index=i + 1, id=_sanitize_id(c.get("phone", "")),
                        kind="lead_candidate", label="",
                    )
                    for i, c in enumerate(candidates)
                ),
                # AP-12 / finding 1b: all-or-nothing only, no partial
                # selection exists today — see TURN_OWNERSHIP_EXTENSION.md.
                approval_granularity="all_or_nothing",
                priority=5,
            )

        other_queues = []
        try:
            batch_count = _bq_te.count_pending(identity.memory_key)
        except Exception:
            batch_count = 0
        if batch_count:
            other_queues.append(PendingQueueAwareness(
                queue_id=f"batch_queue:{_sanitize_id(identity.memory_key)}",
                source="action_gateway",
                kind="deferred_tool_call",
                summary=f"{batch_count} item(s) queued behind a live contract",
                priority=4,
            ))

        envelope = build_turn_envelope(
            live_contract_reply_owner="gateway" if live_contracts else None,
            reconfirmation_required=reconfirmation_required,
            action_gateway_queue=ac_queue,
            lead_capture_queue=lead_queue,
            other_queues=tuple(other_queues),
        )
        log_turn_envelope(envelope, canonical_user_id=identity.memory_key)

        # Case C1 signal (see docs/architecture/turn-coordinator/
        # CASE_C_CLARIFICATION_CONTINUITY.md) — more than one live
        # ActionContract simultaneously pending for this identity violates
        # BatchQueueStore's own single-live-contract invariant, regardless of
        # how it happened. Log-only: does not block or alter this turn.
        if len(live_contracts) > 1:
            from core.turn_envelope import log_case_c_signal
            log_case_c_signal(
                "C1", canonical_user_id=identity.memory_key,
                detail=f"live_contracts={len(live_contracts)}",
            )
    except Exception as exc:
        # Fail-open, not silent: a build failure must leave evidence, or the
        # one turn most likely to have unusual state (the one that broke
        # this) is exactly the one with no observation at all. error_type
        # only (never str(exc)) — an inner KeyError/AttributeError message
        # could echo back a dict key or attribute value that itself embeds
        # user content; type(exc).__name__ never can.
        logger.warning(
            "[TurnEnvelope] build_failed error_type=%s entry_point=%s user=%s",
            type(exc).__name__, entry_point, _sanitize_id(getattr(identity, "memory_key", "")),
        )
        logger.debug("[TurnEnvelope] build_failed detail", exc_info=True)


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


# BUG-124: core.ingress_classifier._TABLE_RE (Tier-4 gate) treats 2+ pipe
# characters — or even one Unicode box-drawing char — anywhere in a line as
# a pasted table/export, no matter where they came from. The substituted
# text below is a quoted business summary/filename, never meant to look
# tabular, but real tool summaries commonly use " | " as a field separator
# (e.g. "✅ בוצע: ... | מזהה: ..."). Left unsanitized, resolve_context_pronouns()
# could splice that "| ... | ..." straight into an otherwise ordinary
# message — so e.g. "כמה זה עולה" (a completely normal sentence, "זה" just
# meaning "this/it", nothing to do with a prior tool result) gets its "זה"
# replaced with a table-shaped chunk and the whole message is misclassified
# as tier=4/table_separator, blocked before it ever reaches the Router.
_TABLE_TRIGGER_CHARS = str.maketrans({"|": "·", "\t": " ", "│": "", "┃": ""})


def _sanitize_for_free_text(s: str) -> str:
    return s.translate(_TABLE_TRIGGER_CHARS)


# BUG-124 follow-up: a char-translate table only ever covers the ONE trigger
# class it was written for. core.ingress_classifier._is_tier4() has 7
# independent trigger classes (table separators, timestamps, WhatsApp export
# headers, Airtable record/field IDs, JSON blocks, CSV blocks, literal
# system-field markers/score-like numbers, table headers, fixed-width
# columns) — and real tool summaries defeat more than just the pipe one:
# airtable_add ("✅ רשומה נוספה | ID: recABC123XY"), airtable_update
# ("✅ רשומה recABC123XY עודכנה."), and tma_write ("✅ בוצע: ... | מזהה:
# recABC123XY") — 3 of the only 4 tools _MEMORABLE_TOOLS even persists —
# all embed the raw Airtable record_id verbatim, which still matches
# _AIRTABLE_ID_RE even after the pipe is translated away. A follow-up like
# "תעדכן גם את זה" right after any of these would still be silently blocked
# with the same "📄 נראה כמו טבלה" message — this bug's exact failure mode,
# just surfacing as a different _is_tier4() reason string.
#
# Fixed against the real classifier instead of another hand-picked char: the
# quoted snippet is checked with _is_tier4() before splicing, and only falls
# back to a plain unquoted reference if quoting would trip Tier-4 on its own.
# Nothing is lost by dropping the quote in that case — the LLM already gets
# the full record_id/url/tool name separately via _build_tool_context()'s
# system-prompt injection (below); this function's only job is giving the
# Router an explicit reference instead of a bare pronoun. Self-healing
# against any FUTURE trigger added to _is_tier4() too, not just today's list.
def _safe_context_quote(label: str, raw: str, fallback: str) -> str:
    quoted = f"{label} «{_sanitize_for_free_text(raw)}»"
    try:
        from core.ingress_classifier import _is_tier4
        if _is_tier4(quoted)[0]:
            return fallback
    except Exception:
        pass
    return quoted


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
                filename = luf.get("original_filename", "")
                replacement = _safe_context_quote("הקובץ", filename, "הקובץ האחרון שהעלית")
                resolved = resolved.replace(pronoun, replacement)
            elif ref_type == "last_tool_result" and ltr:
                summary = ltr.get("summary", "")
                replacement = _safe_context_quote("הפעולה", summary, "הפעולה האחרונה שביצעת")
                resolved = resolved.replace(pronoun, replacement)
    return resolved


def _handle_approval_callback(cq) -> None:
    """H3 top-level handler — דק, מעביר ל-impl ומדווח שגיאות לא-מטופלות."""
    try:
        _handle_approval_callback_impl(cq)
    except Exception as e:
        from core.error_reporter import report_error
        report_error(e, context="_handle_approval_callback")
        raise


def _notify_stale_or_resolved_callback(
    cq, *, notify_chat_id: str, label: str, state_text: str,
) -> None:
    """
    BUG-STALE-CALLBACK-UX: answer_callback_query()'s popup alone is a poor
    user-facing result for a completed/already-resolved/stale approval
    callback — small, disappears quickly, names no action, easy to miss.
    Sends a persistent chat message naming the action and confirming no
    duplicate execution occurred, and edits the original approval message
    to show its final state (removing the now-stale inline keyboard in the
    same call). Purely a notice about a callback that performed zero
    dispatcher calls, zero new Atomic Claims, and zero writes — never
    dispatches or claims anything itself.
    """
    if notify_chat_id:
        try:
            bot.send_message(notify_chat_id, f"ℹ️ {label}\n\n{state_text}, ולכן לא בוצעה שוב.")
        except Exception as e:
            logger.error(f"[Approval] stale-callback notice send failed: {e}")
    try:
        bot.edit_message_text(
            f"ℹ️ *{state_text}*\n{label}",
            cq.message.chat.id, cq.message.message_id,
            parse_mode="Markdown",
        )
    except Exception:
        try:
            bot.edit_message_reply_markup(
                cq.message.chat.id, cq.message.message_id, reply_markup=None)
        except Exception:
            pass


def _reject_stale_telegram_approval(
    cq, item: dict, action_id: str, approver_chat_id: str,
) -> None:
    """
    BUG-112: called once _handle_approval_callback_impl() has determined an
    "approve" callback arrived after _PENDING_APPROVAL_TTL (the SAME 600s
    window advertised to the user as "פג תוקף בעוד 10 דקות") — even though
    event_bus.py's own, separate 30-minute PendingActionsStore TTL had not
    yet elapsed, so bus.pop() still handed back a live item.

    The bus item is already popped/removed by the caller (this function does
    not touch event_bus state itself). This function's job is everything
    else "stale" must mean:
      - never dispatch/execute (caller returns immediately after this call —
        no fallthrough to any dispatch_tool()/ActionGateway.approve() path)
      - reject the matching live ActionGateway contract, if one exists and
        can be positively verified via business fingerprint (never a blind
        "assume it worked" — mirrors the verified-cleanup convention used
        elsewhere in this module, e.g. _revoke_and_verify_contract())
      - notify the approver with a PERSISTENT chat message (not only the
        transient answer_callback_query popup)
      - edit the original approval message so it no longer looks actionable
    """
    payload   = item.get("payload", {}) or {}
    tool_name = payload.get("tool_name")
    canonical_user_id = payload.get("canonical_user_id", "")
    tenant_id = payload.get("tenant_id", "boss_hq")

    if tool_name and canonical_user_id:
        try:
            from feature_flags import is_enabled as _flag_stale
            if _flag_stale("FEATURE_ACTION_GATEWAY"):
                from core.action_gateway import action_gateway as _gw_stale
                _fp_stale = _gw_stale.compute_business_fingerprint(
                    tenant_id, canonical_user_id, tool_name,
                    _gw_stale.normalize_payload(payload.get("tool_inputs", {})),
                )
                _contract_stale = _gw_stale._ledger.find_by_fingerprint(_fp_stale)
                if _contract_stale is not None and _contract_stale.status == "pending":
                    _gw_stale.reject(_contract_stale.contract_id, rejected_by="ttl_expired")
                    _verify_stale = _gw_stale._ledger.find_by_id(_contract_stale.contract_id)
                    if not (_verify_stale and _verify_stale.status == "rejected"):
                        logger.error(
                            "[Approval] TTL-expired callback: ActionContract=%s "
                            "reject() did not verify as rejected — status=%s",
                            _contract_stale.contract_id,
                            getattr(_verify_stale, "status", None),
                        )
        except Exception as _stale_exc:
            logger.warning(
                "[Approval] TTL-expired callback: contract cleanup failed "
                "(non-blocking, bus item already removed): %s", _stale_exc,
            )

    logger.info(
        "[Approval] TTL-expired Telegram callback: action_id=%s tool=%s — "
        "not executed", action_id, tool_name,
    )

    bot.answer_callback_query(cq.id, "⏰ פג תוקף — הפעולה לא בוצעה")
    if approver_chat_id:
        try:
            bot.send_message(approver_chat_id, "⏰ פג תוקף — הפעולה לא בוצעה")
        except Exception as e:
            logger.error(f"[Approval] TTL-expired notify failed: {e}")
    try:
        bot.edit_message_text(
            f"⏰ *פג תוקף*\n{item.get('label', '')}",
            cq.message.chat.id, cq.message.message_id,
            parse_mode="Markdown",
        )
    except Exception:
        try:
            bot.edit_message_reply_markup(
                cq.message.chat.id, cq.message.message_id, reply_markup=None)
        except Exception:
            pass


# BUG-112 production follow-up: bus.pop() found NOTHING at all for this
# action_id — event_bus.py's own 30-minute PendingActionsStore TTL already
# elapsed, or this exact callback was already consumed by an earlier press
# (Telegram can and does redeliver a callback more than once). This is a
# DIFFERENT path from _reject_stale_telegram_approval() above (BUG-112
# proper: a known, still-live pending item found, but past the 10-minute
# TTL advertised on the button) — here there is no item/payload at all, so
# there is no label, no contract fingerprint to look up, nothing to reject.
#
# Production evidence: a repeated/duplicate press on an already-TTL-expired
# button landed here right after _reject_stale_telegram_approval() had
# already fired for the first press — producing THREE overlapping-but-
# different "this didn't happen" phrasings for what a user reads as one
# event: the popup + persistent message here used to say "פג תוקף — הפעולה
# לא קיימת יותר" / "פגה או כבר לא קיימת, ולכן לא בוצעה שוב." (via the
# generic _notify_stale_or_resolved_callback() label/state_text template,
# built for "already executed"/"already rejected" — see the two call sites
# below this function that still legitimately use it), right after the
# first press had already shown "⏰ פג תוקף — הפעולה לא בוצעה". Safety was
# never in question (bus.pop() returning None already guarantees zero
# dispatch either way) — this is a wording-only fix. Normalized to ONE
# literal phrase, reused identically for the popup, the persistent chat
# message, and the edited original message — never templated/combined with
# a generic label placeholder (there is no real label to show here).
_MISSING_OR_EXPIRED_CALLBACK_TEXT = "ℹ️ הפעולה כבר פגה או אינה קיימת, ולכן לא בוצעה."


def _notify_missing_or_expired_callback(cq, approver_chat_id: str) -> None:
    """See the BUG-112 follow-up comment above this function."""
    bot.answer_callback_query(cq.id, _MISSING_OR_EXPIRED_CALLBACK_TEXT)
    if approver_chat_id:
        try:
            bot.send_message(approver_chat_id, _MISSING_OR_EXPIRED_CALLBACK_TEXT)
        except Exception as e:
            logger.error(f"[Approval] missing-callback notify failed: {e}")
    try:
        bot.edit_message_text(
            _MISSING_OR_EXPIRED_CALLBACK_TEXT,
            cq.message.chat.id, cq.message.message_id,
        )
    except Exception:
        try:
            bot.edit_message_reply_markup(
                cq.message.chat.id, cq.message.message_id, reply_markup=None)
        except Exception:
            pass


def _deliver_callback_final(
    cq,
    *,
    origin_channel: str,
    origin_chat_id: str,
    canonical_user_id: str,
    action_id: str,
    tool_name: str,
    text: str,
) -> None:
    """Deliver one persistent final response for a Telegram callback."""
    callback_message = getattr(cq, "message", None)
    callback_chat = getattr(callback_message, "chat", None)
    callback_chat_id = str(getattr(callback_chat, "id", "") or "")
    if origin_channel == "telegram":
        # The callback message owns the keyboard and must always be made
        # terminal, even when the original requester is a different chat.
        bot.edit_message_text(text, cq.message.chat.id, cq.message.message_id)
        if str(origin_chat_id) != callback_chat_id:
            bot.send_message(origin_chat_id, text)
        return

    _write_execution_receipt(
        canonical_user_id, origin_channel, origin_chat_id,
        action_id, tool_name, text,
    )
    bot.edit_message_text(text, cq.message.chat.id, cq.message.message_id)


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
        # BUG-POST-COMPLETION-FALLTHROUGH: this used to call bus.get(), which does
        # not exist on EventBus (only pop() is exposed there) — every invocation
        # raised AttributeError, silently swallowed below as "non-blocking", so
        # this entire pre-check never actually ran. bus.peek() is the real
        # non-destructive read (see event_bus.py).
        try:
            from feature_flags import is_enabled as _flag_sb02
            if _flag_sb02("FEATURE_ACTION_GATEWAY"):
                _peek_item = bus.peek(action_id)
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
                            _peek_label = _peek_item.get("label") or _describe_tool_call(_peek_tool, _peek_inputs)
                            if _contract_sb02.status in ("completed", "executed"):
                                bot.answer_callback_query(cq.id, "✅ פעולה זו כבר בוצעה")
                                _notify_stale_or_resolved_callback(
                                    cq, notify_chat_id=approver_chat_id,
                                    label=_peek_label, state_text="כבר בוצעה",
                                )
                                logger.info(
                                    "[ActionGateway] SB-02: blocked duplicate callback "
                                    "action_id=%s contract=%s tool=%s status=executed",
                                    action_id, _contract_sb02.contract_id, _peek_tool,
                                )
                                return
                            if _contract_sb02.status == "rejected":
                                bot.answer_callback_query(cq.id, "❌ פעולה זו בוטלה")
                                _notify_stale_or_resolved_callback(
                                    cq, notify_chat_id=approver_chat_id,
                                    label=_peek_label, state_text="כבר בוטלה",
                                )
                                return
        except Exception as _sb02_exc:
            logger.warning("[ActionGateway] SB-02 status pre-check failed (non-blocking): %s", _sb02_exc)

        # atomic pop — בדיקת TTL ומחיקה בצעד אחד
        item = bus.pop(action_id)
        if not item:
            # No payload was ever available (SB-02's own peek above would
            # have found the same nothing) — no specific action to name,
            # but still give a persistent result, not just the popup. See
            # _notify_missing_or_expired_callback()'s own comment for why
            # this is a dedicated single-phrase notice rather than the
            # generic _notify_stale_or_resolved_callback() template.
            _notify_missing_or_expired_callback(cq, approver_chat_id)
            return

        payload          = item["payload"]
        tool_name        = payload.get("tool_name")   # absent on non-tool approvals
        user_chat_id     = payload.get("user_chat_id", item.get("chat_id", ""))
        channel          = payload.get("channel", "telegram")
        # Stage A: route notify to the channel the user actually requested from
        origin_channel   = payload.get("origin_channel", channel)
        origin_chat_id   = payload.get("origin_chat_id", user_chat_id)
        canonical_user_id = payload.get("canonical_user_id", "")

        # BUG-112: bus.pop() above only enforced event_bus.py's OWN, separate
        # 30-minute PendingActionsStore TTL — not the 10-minute window
        # actually advertised to the user on the button ("פג תוקף בעוד 10
        # דקות"). Enforce that SAME _PENDING_APPROVAL_TTL independently here,
        # for every "approve" callback (tool AND non-tool), before any
        # dispatch/execute decision is made. The bus item is already gone
        # (popped above) regardless of this check's outcome — this only
        # decides whether execution may proceed.
        _item_created_raw = item.get("created")
        if _item_created_raw:
            try:
                from datetime import datetime as _dt_stale
                _age_seconds = (
                    _dt_stale.now() - _dt_stale.fromisoformat(_item_created_raw)
                ).total_seconds()
            except (ValueError, TypeError) as _ts_exc:
                logger.warning(
                    "[Approval] TTL check: malformed created timestamp %r "
                    "(%s) — not treated as stale", _item_created_raw, _ts_exc,
                )
                _age_seconds = 0.0
            if _age_seconds > _PENDING_APPROVAL_TTL:
                _reject_stale_telegram_approval(cq, item, action_id, approver_chat_id)
                return

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

            # TurnCoordinator Phase 0 — observation only (see
            # docs/architecture/turn-coordinator/). Extends coverage from
            # run_agent() (text turns) to the Telegram approval callback —
            # AP-02 in TURN_OWNERSHIP_EXTENSION.md, where the reply is
            # Gateway-authored, not agent-authored, and where a Case C1
            # multi-contract conflict is just as observable as at turn
            # start. No session_snapshot here (not a lead-preview context);
            # no pre-fetched live_contracts (this handler doesn't already
            # query it elsewhere, unlike run_agent()'s "1.65" — one read
            # here is the baseline, not an amplification of an existing one).
            _build_and_log_turn_envelope(
                identity, user_chat_id, None, entry_point="telegram_callback",
            )

            try:
                enforce(tool_name, identity)
            except ToolDenied as e:
                logger.warning(
                    f"[Approval] denied approved action {action_id} | "
                    f"{tool_name} | user={_sanitize_id(identity.user_id)} role={identity.role}: {e}"
                )
                bot.answer_callback_query(cq.id, "⛔ הפעולה כבר אינה מורשית")
                return

            # PR-0C: prefer executing through the frozen ActionGateway contract
            # (approve() = the single claim -> dispatch -> verify -> status
            # boundary) over re-implementing those same steps by hand here,
            # when a live contract exists for this fingerprint. Falls back to
            # the pre-migration direct dispatch_tool() call if no contract is
            # found (e.g. the shadow-mode propose_action() at _queue_approval
            # time failed silently, or FEATURE_ACTION_GATEWAY is off) — never
            # a new failure mode versus today. approver_role/approver here are
            # deliberately the button-clicking approver_identity (BUG-074: the
            # actual authenticated approver, never the original requester's
            # identity) — dispatch itself still executes scoped to the
            # requester, via contract.actor_role/actor_external_id already
            # captured by _queue_approval()'s propose_action(identity=...).
            _gw_contract_id = None
            _gw_terminal_reply = None
            _gw_terminal_contract_id = None
            _gw_terminal_status = None
            if _flag_enabled("FEATURE_ACTION_GATEWAY"):
                try:
                    from core.action_gateway import action_gateway as _gw_exec
                    _fp_exec = _gw_exec.compute_business_fingerprint(
                        getattr(identity, "tenant_id", "boss_hq"),
                        canonical_user_id or identity.memory_key, tool_name,
                        _gw_exec.normalize_payload(tool_inputs),
                    )
                    _contract_exec = _gw_exec._ledger.find_by_fingerprint(_fp_exec)
                    if _contract_exec:
                        if _contract_exec.status == "pending":
                            _gw_contract_id = _contract_exec.contract_id
                        elif _contract_exec.status in ("completed", "executed"):
                            _gw_terminal_reply = "✅ פעולה זו כבר בוצעה."
                            _gw_terminal_contract_id = _contract_exec.contract_id
                            _gw_terminal_status = _contract_exec.status
                        elif _contract_exec.status == "rejected":
                            _gw_terminal_reply = "❌ פעולה זו כבר בוטלה."
                            _gw_terminal_contract_id = _contract_exec.contract_id
                            _gw_terminal_status = _contract_exec.status
                except Exception as _gw_lookup_exc:
                    logger.warning(
                        "[ActionGateway] contract lookup failed for execution — "
                        "falling back to legacy dispatch: %s", _gw_lookup_exc,
                    )

            if _gw_terminal_reply:
                # BUG-POST-COMPLETION-FALLTHROUGH: the durable ActionContract for
                # this fingerprint already reached a terminal state (e.g. approved
                # via a text confirmation on this or another channel, while a
                # stale Telegram approval button for the same action was still
                # showing). Requirement: never fall through to the legacy
                # dispatch_tool() branch below on a terminal contract — Airtable-
                # level dedup detection is not a substitute for this authoritative
                # status check, and previously produced a misleading
                # "expected structured result dict; got plain string" failure.
                logger.info(
                    "[ActionGateway] blocked post-completion callback fallthrough: "
                    "action_id=%s contract=%s tool=%s status=%s",
                    action_id, _gw_terminal_contract_id, tool_name, _gw_terminal_status,
                )
                bot.answer_callback_query(cq.id, _gw_terminal_reply)
                _notify_stale_or_resolved_callback(
                    cq, notify_chat_id=approver_chat_id,
                    label=item.get("label") or _describe_tool_call(tool_name, tool_inputs),
                    state_text=(
                        "כבר בוצעה" if _gw_terminal_status in ("completed", "executed")
                        else "כבר בוטלה"
                    ),
                )
                return

            if _gw_contract_id:
                from core.action_gateway import action_gateway as _gw_exec
                result = _gw_exec.approve(
                    _gw_contract_id,
                    approver=approver_identity.memory_key or approver_identity.user_id,
                    approver_role=approver_identity.role,
                )
                _contract_after = _gw_exec._ledger.find_by_id(_gw_contract_id)
                exec_failed = not (
                    _contract_after and _contract_after.status in ("completed", "executed")
                )
                fail_text   = result
            elif _flag_enabled("FEATURE_ACTION_GATEWAY"):
                # BUG-STALE-CALLBACK-FALLTHROUGH: FEATURE_ACTION_GATEWAY is on
                # but no contract — pending or terminal — was found for this
                # exact fingerprint at all (a stale/replayed/unlinked
                # callback, or the shadow-mode propose_action() at
                # _queue_approval() time failed silently). Live incident:
                # such a callback reached direct dispatch_tool() with no
                # ActionGateway approval and no Atomic Claim behind it at
                # all. Once the Gateway is the authority, a callback must
                # never execute a real write without a contract to back it —
                # fail closed with a deterministic reply, zero dispatches.
                logger.warning(
                    "[ActionGateway] stale/unlinked callback: no contract found for "
                    "fingerprint — refusing legacy dispatch. action_id=%s tool=%s",
                    action_id, tool_name,
                )
                bot.answer_callback_query(cq.id, "⏰ הפעולה פגה או כבר טופלה.")
                _notify_stale_or_resolved_callback(
                    cq, notify_chat_id=approver_chat_id,
                    label=item.get("label") or _describe_tool_call(tool_name, tool_inputs),
                    state_text="כבר טופלה או שאין לה רישום אישור פעיל",
                )
                return
            else:
                # Legacy path — FEATURE_ACTION_GATEWAY entirely off, no
                # Gateway involvement in this mode at all; unchanged from
                # pre-migration behavior. BUG-091: this replays the payload
                # stored at _queue_approval() time (dict(tu.input) — Claude's
                # own tool_use JSON, verbatim). _queue_approval() is only
                # ever called from the raw Agent tool_use loop below —
                # hardcode "agent", never trust a "_source" key that might be
                # sitting inside tool_inputs.
                raw    = dispatch_tool(tool_name, tool_inputs, identity, trusted_source="agent")
                result = validate_tool_output(tool_name, raw)

                exec_check = verify_execution(tool_name, result)
                exec_failed = exec_check.status == "failed"
                fail_text   = f"❌ הפעולה לא הושלמה: {exec_check.reason}"
                if exec_check.status == "warn":
                    logger.warning(f"[Approval:A32] Execution warn: {tool_name} -- {exec_check.reason}")

            if exec_failed:
                logger.error(f"[Approval:A32] Execution failed: {tool_name} -- {fail_text}")
                try:
                    _deliver_callback_final(
                        cq, origin_channel=origin_channel,
                        origin_chat_id=origin_chat_id,
                        canonical_user_id=canonical_user_id,
                        action_id=action_id, tool_name=tool_name,
                        text=f"❌ אושר אך נכשל בביצוע\n{item['label']}\n\n{fail_text[:200]}",
                    )
                except Exception as e:
                    logger.error("[Approval] final callback delivery failed: %s", e)
                bot.answer_callback_query(cq.id, "❌ הביצוע נכשל")
                return

            # PR #188: raw chat_id fingerprint
            from event_bus import executed_action_cache as _eac
            _eac.mark_executed(_eac.compute(user_chat_id, tool_name, tool_inputs))
            # Stage A: also clear cross-channel duplicate pending
            if canonical_user_id:
                bus.mark_equivalent_pending_completed(canonical_user_id, tool_name, tool_inputs)
            # Stage B sync: mark the Gateway contract completed so a subsequent
            # free-text "מאשר" on another channel doesn't re-dispatch the same tool.
            _gw_lifecycle_failure = None
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
                        _success_status = (
                            "completed" if _gw_sync._ledger._repository else "executed"
                        )
                        if not _gw_sync._ledger.update_status(
                            _existing.contract_id, _success_status,
                            approved_by=canonical_user_id,
                            approved_at=__import__("time").time(),
                        ):
                            raise RuntimeError("contract missing during lifecycle update")
                        logger.info(
                            "[ActionGateway] Stage-A callback synced contract=%s tool=%s → %s",
                            _existing.contract_id, tool_name, _success_status,
                        )
            except Exception as _gw_sync_exc:
                _gw_lifecycle_failure = str(_gw_sync_exc)
                logger.critical(
                    "[ActionGateway] Stage-A provider succeeded but durable lifecycle sync failed: "
                    "action=%s tool=%s error=%s",
                    action_id, tool_name, _gw_sync_exc,
                )

            if _gw_lifecycle_failure:
                _lifecycle_message = (
                    "⚠️ הספק החזיר הצלחה, אך סטטוס ActionContract לא נשמר "
                    "באופן עמיד. אין לנסות שוב עד לבדיקת המערכת."
                )
                try:
                    _deliver_callback_final(
                        cq, origin_channel=origin_channel,
                        origin_chat_id=origin_chat_id,
                        canonical_user_id=canonical_user_id,
                        action_id=action_id, tool_name=tool_name,
                        text=f"{_lifecycle_message}\n{item['label']}",
                    )
                except Exception as _notify_exc:
                    logger.error("[Approval] lifecycle failure notify failed: %s", _notify_exc)
                bot.answer_callback_query(cq.id, "⚠️ סטטוס הביקורת לא נשמר")
                return

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
        try:
            _deliver_callback_final(
                cq, origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                canonical_user_id=canonical_user_id,
                action_id=action_id,
                tool_name=tool_name or item.get("action", ""),
                text=user_notify_text,
            )
        except Exception as e:
            logger.error("[Approval] final callback delivery failed: %s", e)
        bot.answer_callback_query(cq.id, "✅ בוצע!")
        # BUG-BATCH-DISCARD: this contract just resolved — promote the next
        # deferred batch item for this identity, if any and if none other is
        # still live.
        _promote_next_batch_item(canonical_user_id)

    elif action == "reject":
        item = bus.pop(action_id)
        if not item:
            _notify_missing_or_expired_callback(cq, approver_chat_id)
            return

        payload = item.get("payload", {})
        tool_name = payload.get("tool_name", "")
        tool_inputs = payload.get("tool_inputs", {})
        user_chat_id = payload.get("user_chat_id", item.get("chat_id", ""))
        channel = payload.get("channel", "telegram")
        origin_channel = payload.get("origin_channel", channel)
        origin_chat_id = payload.get("origin_chat_id", user_chat_id)
        canonical_user_id = payload.get("canonical_user_id", "")
        label = item.get("label") or _describe_tool_call(tool_name, tool_inputs)

        # BUG-144: the button and ActionContract are one lifecycle. Reject
        # the canonical contract before reporting cancellation.
        #
        # Preferred linkage is the exact contract_id proven at queue time.
        # Fingerprint rediscovery remains only as a backwards-compatible
        # fallback for older pending items that predate that payload field.
        _reject_contract_id = payload.get("contract_id", "") or ""
        if tool_name or _reject_contract_id:
            requester_identity = resolve_identity(channel, user_chat_id)
            from core.action_gateway import action_gateway as _gw_reject
            _reject_contract = None
            if _reject_contract_id:
                _reject_contract = _gw_reject._ledger.find_by_id(_reject_contract_id)
                if (
                    _reject_contract is not None
                    and canonical_user_id
                    and _reject_contract.canonical_user_id != canonical_user_id
                ):
                    logger.error(
                        "[ActionGateway] reject callback contract/canonical mismatch "
                        "action_id=%s contract=%s payload_user=%s contract_user=%s",
                        action_id, _reject_contract_id,
                        _sanitize_id(canonical_user_id),
                        _sanitize_id(_reject_contract.canonical_user_id),
                    )
                    _reject_contract = None
            elif tool_name and _flag_enabled("FEATURE_ACTION_GATEWAY"):
                _reject_fp = _gw_reject.compute_business_fingerprint(
                    getattr(requester_identity, "tenant_id", "boss_hq"),
                    canonical_user_id or requester_identity.memory_key,
                    tool_name, _gw_reject.normalize_payload(tool_inputs),
                )
                _reject_contract = _gw_reject._ledger.find_by_fingerprint(_reject_fp)
            if not _reject_contract:
                logger.warning(
                    "[ActionGateway] reject callback has no canonical contract "
                    "action_id=%s tool=%s contract_id=%s",
                    action_id, tool_name, _reject_contract_id or "none",
                )
                bot.answer_callback_query(cq.id, "⏰ הפעולה פגה או כבר טופלה.")
                _notify_stale_or_resolved_callback(
                    cq, notify_chat_id=approver_chat_id, label=label,
                    state_text="כבר טופלה או שאין לה רישום אישור פעיל",
                )
                return
            _reject_reply = _gw_reject.reject(
                _reject_contract.contract_id,
                rejected_by=approver_identity.memory_key or approver_identity.user_id,
            )
            _reject_after = _gw_reject._ledger.find_by_id(_reject_contract.contract_id)
            if not _reject_after or _reject_after.status != "rejected":
                logger.error(
                    "[ActionGateway] reject callback durable transition failed "
                    "action_id=%s contract=%s",
                    action_id, _reject_contract.contract_id,
                )
                try:
                    _deliver_callback_final(
                        cq, origin_channel=origin_channel,
                        origin_chat_id=origin_chat_id,
                        canonical_user_id=canonical_user_id,
                        action_id=action_id, tool_name=tool_name,
                        text=_reject_reply,
                    )
                except Exception:
                    pass
                bot.answer_callback_query(cq.id, "❌ הביטול לא נשמר")
                return

        logger.info(
            "🚫 Rejected: %s | %s | canonical_user=%s",
            action_id, label, _sanitize_id(canonical_user_id),
        )
        try:
            _deliver_callback_final(
                cq, origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                canonical_user_id=canonical_user_id,
                action_id=action_id, tool_name=tool_name,
                text=f"🚫 הפעולה בוטלה: {label}",
            )
        except Exception as e:
            logger.error("[Approval] final callback delivery failed: %s", e)
        bot.answer_callback_query(cq.id, "🚫 בוטל")
        _promote_next_batch_item(canonical_user_id)

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
    _live_contracts_snapshot: list | None = None,
) -> str:
    # _live_contracts_snapshot: Case C read-amplification fix (see
    # TURN_OWNERSHIP_EXTENSION.md) — an already-fetched find_live_contracts()
    # result for this identity from the caller's own ingress-gate query, so
    # this turn does not query again. None (default) is fully
    # backward-compatible: every caller that doesn't pass this (recursive
    # run_agent() calls, tests, any future caller) gets the exact original
    # behavior — this function fetches it once itself, the first time it's
    # needed, instead of not fetching at all. Either way, ONE fetch is
    # established below and reused for the rest of this turn — never
    # refetched, never cached across turns/calls.
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

    # ── 1.65. Establish the single per-turn live-contracts snapshot ──
    # Case C read-amplification fix. If the caller (webhook handler) already
    # fetched this for the ingress-gate check, reuse it (0 additional
    # queries). Otherwise fetch it exactly once, here, and reuse it for
    # everything below in this turn (Pending Approval Gate at 2.55,
    # build_turn_envelope() at 1.7, and the Case C2 signal after the tool
    # loop) — never refetched within this call, never cached across turns.
    if _live_contracts_snapshot is None:
        try:
            from core.action_gateway import action_gateway as _gw_snapshot
            _live_contracts_snapshot = _gw_snapshot.find_live_contracts(identity.memory_key)
        except Exception:
            _live_contracts_snapshot = []
    # Turn-start batch_queue count (RAM-only, not an Airtable read — no
    # amplification concern, captured here purely so the Case C2 check below
    # uses the same turn-start moment as build_turn_envelope() rather than a
    # separately-timed read).
    try:
        from event_bus import batch_queue as _bq_snapshot
        _batch_count_snapshot = _bq_snapshot.count_pending(identity.memory_key)
        logger.info(
            "[BatchQueue] turn_start user=%s queue_count=%d storage=memory",
            _sanitize_id(identity.memory_key), _batch_count_snapshot,
        )
        if _batch_count_snapshot:
            _bq_snapshot.clear(identity.memory_key)
            logger.warning(
                "[BatchQueue] turn_start_cleanup user=%s queue_count_before=%d "
                "queue_count_after=0 action=discard_no_promotion",
                _sanitize_id(identity.memory_key), _batch_count_snapshot,
            )
    except Exception:
        _batch_count_snapshot = 0

    # ── 1.7. TurnCoordinator Phase 0 (observation only) ──────────
    # Snapshot of turn-start pending state, logged only — see
    # _build_and_log_turn_envelope()'s docstring. Placed here, before the
    # Pending Approval Gate below pops anything, so it reflects what this
    # turn actually started with, not what's left after this turn's own
    # routing has already consumed it. Passes _session_snapshot through
    # (LL-11: single Sessions read per turn) instead of re-reading it, and
    # _live_contracts_snapshot through (Case C read-amplification fix)
    # instead of querying ActionGateway again.
    _build_and_log_turn_envelope(
        identity, chat_id, _session_snapshot, live_contracts_snapshot=_live_contracts_snapshot,
    )

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
            return _gateway_reply_with_promotion(
                _gw_ow.route_override_word(identity.memory_key, _override_code),
                identity.memory_key,
            )

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
            return _gateway_reply_with_promotion(_combined_reply, identity.memory_key)

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
                return _gateway_reply_with_promotion(_disambig_reply, identity.memory_key)

        # BUG-141 (AG-01) — natural-language pending-queue questions ("מה
        # ממתין כרגע לאישור?") must route to the deterministic
        # describe_pending_queue() regardless of a trailing "?". Checked
        # BEFORE the general "?" status-query branch below: that branch used
        # to unconditionally capture any "?"-containing text (its own
        # _STATUS_QUERY_PATTERNS only covers past-tense completion verbs,
        # not "ממתין"), so _PENDING_QUERY_RE never ran for such questions.
        # Not gated by FEATURE_ACTION_GATEWAY — matches the elif branch this
        # replaces, which also ran unconditionally. Read-only: never
        # approves/rejects anything, so a false-positive match here is
        # harmless (worst case: shows an accurate pending-list instead of
        # routing to the Agent).
        if _PENDING_QUERY_RE.search(_stripped):
            from core.action_gateway import action_gateway as _gw_pq
            _pq_pending_count = len(_gw_pq.find_live_contracts(identity.memory_key))
            _pq_reply = _gw_pq.describe_pending_queue(identity.memory_key)
            # Review pass (23/07/2026), sampling-hygiene finding: this log
            # line is raw material for RP5/TurnCoordinator-Shadow sampling —
            # it must never carry user free-text or reply content (names/
            # phones/business descriptions can appear in both). Structured,
            # PII-free fields only.
            logger.info(
                "[ActionGateway] describe_pending_queue: user=%s pending_count=%d scope=action_contracts result_code=%s",
                identity.memory_key, _pq_pending_count, "found" if _pq_pending_count else "empty",
            )
            if _out_meta is not None:
                _out_meta["source_module"] = "action_gateway"
            return _pq_reply

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
            # BUG-117: recency check BEFORE the unconditional Tier-1 gate
            # below. A fresh Tier-2 batch lead-preview ("📋 זיהיתי N לידים
            # אפשריים בקבוצה...", core/lead_candidate_handler.py's
            # _handle_clean_batch / session_store.py's pending_lead_preview,
            # BUG-058) was being hijacked into generic disambiguation of old,
            # unrelated Tier-1 ActionContracts — the same "stale contracts
            # never expire" failure mode BUG-115 already fixed within Tier-1
            # itself, but one level up (Tier-1-vs-Tier-2 precedence), never
            # touched by that fix. should_prefer_batch_preview() compares
            # this Tier-2 preview's timestamp against BUG-115's own Tier-1
            # bookmark and only short-circuits here when Tier-2 is genuinely
            # the more recently shown prompt; otherwise falls through
            # unchanged to the existing Tier-1-first logic below.
            from core.lead_candidate_handler import should_prefer_batch_preview as _prefer_t2
            if _prefer_t2(identity.memory_key, chat_id):
                from core.lead_candidate_handler import resolve_pending_lead_preview as _resolve_t2_early
                _t2_reply_early = _resolve_t2_early(identity, chat_id, is_confirm=True, is_cancel=False)
                if _t2_reply_early is not None:
                    logger.info(
                        "[LCH] resolve_pending_lead_preview(confirm, recency-preferred): user=%s reply=%.60s",
                        identity.memory_key, _t2_reply_early,
                    )
                    if _out_meta is not None:
                        _out_meta["source_module"] = "action_gateway"
                    return _t2_reply_early

            # BUG-056: check ActionGateway live contracts FIRST, regardless of
            # FEATURE_ACTION_GATEWAY — LCH's Tier-1 lead-preview confirmation
            # (core/lead_candidate_handler.py: _propose_lead_write) always
            # registers a real contract here, even when the flag is off (its
            # default). Only when Gateway has nothing pending do we fall back
            # to the flag-gated Stage A/B logic exactly as before.
            from core.action_gateway import action_gateway as _gw_cw
            # NOTE: deliberately NOT reusing _live_contracts_snapshot here —
            # left as its own fresh find_live_contracts() call. Not required
            # for the Case C read-amplification fix (this branch never
            # executes on a greeting turn, the reported regression's
            # scenario) and test_c89_preview_confirmation.py's
            # test_app_py_confirm_word_checks_gateway_before_flag_branch
            # statically asserts this exact call appears here, ahead of the
            # FEATURE_ACTION_GATEWAY flag branch — an intentional structural
            # invariant, not incidental text.
            if _gw_cw.find_live_contracts(identity.memory_key):
                _gw_reply = _gw_cw.route_confirmation_word(identity.memory_key, approver_role=identity.role)
                logger.info(
                    "[ActionGateway] route_confirmation_word: user=%s reply=%.60s",
                    identity.memory_key, _gw_reply,
                )
                if _out_meta is not None:
                    _out_meta["source_module"] = "action_gateway"
                return _gateway_reply_with_promotion(_gw_reply, identity.memory_key)

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
                return _gateway_reply_with_promotion(_gw_reply, identity.memory_key)
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
                    # BUG-PENDING-APPROVAL-B follow-up: this is the path
                    # actually hit by default (FEATURE_ACTION_GATEWAY off) —
                    # must also surface a specific "superseded" message
                    # instead of looking identical to "nothing ever happened".
                    return _gw_cw.describe_no_pending_reason(identity.memory_key)
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
                return _gateway_reply_with_promotion(_cancel_reply, identity.memory_key)

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

    # BUG-122: an unresolved canonical action owns the mutation slot.  A new
    # contract-required request must stop before LeadCandidate/approval/Agent
    # code can create another contract or retain deferred work.  Resolution
    # words and numbered selections have already been handled above.
    try:
        from core.router.risk_router import (
            intent_requires_contract_for_success as _requires_contract,
        )
    except Exception:
        _requires_contract = None
    if (
        _live_contracts_snapshot
        and _requires_contract is not None
        and _requires_contract(getattr(route, "intent", None))
    ):
        logger.warning(
            "[BUG-122] pending_gate_decision=block_new_action "
            "live_contracts_count=%d batch_queue_count=0 intent=%s user=%s",
            len(_live_contracts_snapshot), getattr(route, "intent", None),
            _sanitize_id(identity.memory_key),
        )
        return (
            f"יש לך כרגע {len(_live_contracts_snapshot)} בקשות הממתינות לאישור. "
            "שלח *מאשר* או *בטל* כדי לפתור את הפעולה הקיימת, ואז שלח מחדש "
            "את הבקשה החדשה."
        )

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
        turn_evidence = TurnEvidenceSummary()
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
            _lc_meta = get_tool_meta(_lc_a32["tool"])
            turn_evidence.record_verification(
                "ok" if _lc_a32["ok"] else "failed",
                read_only=bool(_lc_meta and _lc_meta.read_only),
            )

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
            # Cost Telemetry Reliability PR2 (shadow only): durable
            # provider/service/model-generic recording, in ADDITION to the
            # two calls above (unchanged) — does not feed AI_Usage_Daily or
            # EMERGENCY_STOP_AI yet. See core/usage_telemetry.py.
            try:
                from core.usage_telemetry import record_llm_usage
                record_llm_usage(
                    source     = "run_agent",
                    model      = ctx.model,
                    tokens_in  = getattr(response.usage, "input_tokens",  0),
                    tokens_out = getattr(response.usage, "output_tokens", 0),
                    caller     = ctx.memory_key,
                    request_id = getattr(response, "id", None),
                )
            except Exception as e:
                logger.error(f"[UsageTelemetry] run_agent recording failed (non-fatal): {e}", exc_info=True)

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
                    turn_evidence.record_verification("failed", read_only=False)
                    continue

                try:
                    meta = enforce(tu.name, identity)
                except ToolDenied as e:
                    logger.warning(f"[Tool] Denied: {tu.name} for {identity.role}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
                    })
                    # PA-01: gate-authored, non-agent text — see
                    # docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §4.2b.
                    tool_results_log.append({
                        "tool": tu.name, "content": str(e), "ok": False,
                        "terminal_outcome": "PERMISSION_DENIED",
                    })
                    turn_evidence.record_verification("failed", read_only=False)
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
                            # PA-01: gate-authored, non-agent text — see
                            # docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §4.2b.
                            tool_results_log.append({
                                "tool": tu.name, "content": str(e), "ok": False,
                                "terminal_outcome": "PREFLIGHT_BLOCKED",
                            })
                            turn_evidence.record_verification("failed", read_only=meta.read_only)
                            continue

                    # BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION originally
                    # blocked (discarded) any second mutating approval in the
                    # same turn outright. The payload-contamination it cited
                    # was never actually reproduced — dict(tu.input) already
                    # made an independent copy per call both before and after
                    # that fix, and each _queue_approval() call already
                    # creates its own independent EventBus item +
                    # ActionContract. The blanket block conflated "prevent a
                    # hypothetical shared-memory hazard" with "prohibit more
                    # than one pending action per turn", silently discarding
                    # every task beyond the first in a multi-task request.
                    #
                    # BUG-122: once this turn has created an unresolved
                    # contract, later mutations are neither contracted nor
                    # retained. The user must resolve the existing action and
                    # resend the remaining request.
                    if _mutating_approvals_this_turn >= 1:
                        logger.info(
                            "[BUG-122] same_turn_mutation_blocked tool=%s "
                            "user=%s batch_queue_count=0",
                            tu.name, _sanitize_id(chat_id),
                        )
                        _deferred_content = (
                            "⛔ הפעולה הנוספת לא נשמרה. יש לפתור את הפעולה "
                            "הממתינה ואז לשלוח את הבקשה מחדש."
                        )
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu.id,
                            "content": _deferred_content,
                        })
                        from core.action_gateway import resolve_canonical_tool as _resolve_deferred_tool
                        _deferred_action_tool = _resolve_deferred_tool(tu.name, dict(tu.input), user_text)
                        tool_results_log.append({
                            "tool": "__approval_blocked_pending__",
                            "content": _deferred_content,
                            "ok": False,
                            "contract_id": None,
                            "terminal_outcome": "APPROVAL_BLOCKED_PENDING",
                            "action_tool": _deferred_action_tool,
                            "created_this_turn": False,
                        })
                        continue
                    _approval_outcome = _queue_approval_detailed(
                        tu.name, dict(tu.input), chat_id, channel, user_text
                    )
                    result = _approval_outcome["message"]
                    _mutating_approvals_this_turn += 1
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": result
                    })
                    # BUG-V1-FAKE-APPROVAL-STATE: inject A32 sentinel so
                    # sanitize_agent_response can verify the "⏳ ממתינה לאישור"
                    # echo came from a real approval, not hallucinated text.
                    # PA-01 Main Integration Pass fix: "action_tool" MUST be
                    # the CANONICAL tool name _queue_approval_detailed()
                    # actually used to create the contract (resolve_canonical_
                    # tool() can rewrite it, e.g. sheets_append -> airtable_add
                    # — BUG-CANONICAL-TOOL-WIRING), never tu.name (the raw,
                    # pre-canonicalization tool the model happened to call) —
                    # using tu.name here would make a genuine contract
                    # invisible to PA-01's expected-tool scoping whenever
                    # canonicalization rewrote the tool.
                    # "created_this_turn" (follow-up fix): a non-None
                    # contract_id alone does NOT prove a contract was created
                    # THIS turn — ActionGateway.propose_action() also returns
                    # a real, non-None contract_id for a rejected/duplicate/
                    # pre-existing contract it merely found. See
                    # docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md
                    # §4.2a / §8.
                    tool_results_log.append({
                        "tool": "__approval_queued__",
                        "content": result,
                        "ok": _approval_outcome["ok"],
                        "contract_id": _approval_outcome["contract_id"],
                        "terminal_outcome": _approval_outcome["terminal_outcome"],
                        "action_tool": _approval_outcome["action_tool"],
                        "created_this_turn": _approval_outcome["created_this_turn"],
                        # F52 PR6: proven-sent flag (see _queue_approval_detailed_
                        # impl()'s own "owner_notified" comment) — .get() with a
                        # False default so pre-existing test mocks/older call
                        # shapes that don't set this key read as "not proven
                        # sent," never as a silent KeyError or a false True.
                        "owner_notified": _approval_outcome.get("owner_notified", False),
                    })
                    if _approval_outcome["created_this_turn"]:
                        turn_evidence.record_approval_pending()
                    elif _approval_outcome["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED":
                        turn_evidence.record_unverified_effect()
                    else:
                        turn_evidence.record_verification("failed", read_only=meta.read_only)
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
                turn_evidence.record_verification(exec_check.status, read_only=meta.read_only)

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

        # BUG-122: pending approval queue pollution suppressing explicit new
        # actions. Live incident: Router confidently recognized a contract-
        # requiring intent (create_task, conf=0.95) with 5 pre-existing live
        # ActionContracts for this identity; the agent emitted zero tool
        # calls and queued no new approval, but its own free text happened
        # to read as action/pending-status-shaped — Single-Speaker's blanket
        # rule above (_gateway_active + pattern match) then replaced it with
        # _SINGLE_SPEAKER_FALLBACK ("לא הצלחתי לבצע את הפעולה"), which is
        # misleading here: nothing was actually attempted, so "I failed" is
        # false, and the message gives the user no path forward. Only
        # intervenes on that exact combination — a confidently-recognized,
        # contract-requiring intent with zero turn activity — never touches
        # PA-01's own flag/state (intent_requires_contract_for_success() is
        # PA-01's existing single policy source, reused, not duplicated),
        # RP5/F52, or approval execution. Text-only improvement.
        try:
            from core.router.risk_router import intent_requires_contract_for_success as _b121_contract_required
        except Exception:
            _b121_contract_required = None
        _b121_intent = getattr(route, "intent", None)
        _b121_approval_queued_this_turn = any(
            r.get("tool") == "__approval_queued__" for r in tool_results_log
        )
        _b121_stale_count = sum(
            1 for c in (_live_contracts_snapshot or [])
            if time.time() - getattr(c, "created_at", time.time()) > _LIVE_CONTRACT_STALE_SECONDS
        )
        if (
            final_reply == _SINGLE_SPEAKER_FALLBACK
            and tool_calls_made == 0
            and not _b121_approval_queued_this_turn
            and _b121_contract_required is not None
            and _b121_contract_required(_b121_intent)
            and _live_contracts_snapshot
        ):
            logger.warning(
                "[BUG-122] pending_gate_decision=ask_queue_resolution live_contracts_count=%d "
                "stale_contracts_count=%d intent=%s user=%s",
                len(_live_contracts_snapshot), _b121_stale_count, _b121_intent,
                _sanitize_id(identity.memory_key),
            )
            final_reply = (
                f"יש לך כרגע {len(_live_contracts_snapshot)} בקשות הממתינות לאישור. "
                "כדי להמשיך, שלח *מאשר*/*בטל* לגבי הבקשות הקיימות, או נסח שוב את "
                "הבקשה החדשה שלך במפורש."
            )
        # Case C2 signal (see docs/architecture/turn-coordinator/
        # CASE_C_CLARIFICATION_CONTINUITY.md) — final_reply reads as a
        # pending-approval claim but this turn ends with nothing actually
        # pending and nothing newly queued.
        #
        # Read-amplification fix: this used to re-query find_live_contracts()
        # + batch_queue.count_pending() fresh here. Reuses the turn-start
        # _live_contracts_snapshot/_batch_count_snapshot (from "1.65")
        # instead — provably equivalent, not just cheaper: this code path is
        # only reached after falling through to the Agent tool loop (every
        # confirm/disambiguation/cancellation/override route returns early,
        # before this point), so the only way contract/batch-queue state can
        # have changed since turn start is a _queue_approval() call
        # succeeding this turn — which is exactly what
        # approval_queued_this_turn (tool_results_log's __approval_queued__
        # sentinel) already detects and short-circuits on inside
        # detect_case_c2_signal(). When approval_queued_this_turn is False,
        # nothing on this path could have touched either count, so the
        # turn-start values are still accurate; deliberately does not re-read
        # session_store either (LL-11 single-read invariant) — lead-preview
        # coverage remains intentionally out of scope for this signal, see
        # the doc. Log-only: never blocks/alters final_reply.
        try:
            from core.turn_envelope import detect_case_c2_signal, log_case_c_signal
            _turn_start_queue_count = len(_live_contracts_snapshot) + _batch_count_snapshot
            _approval_queued_this_turn = any(
                r.get("tool") == "__approval_queued__" for r in tool_results_log
            )
            if detect_case_c2_signal(
                final_reply,
                queue_count=_turn_start_queue_count,
                approval_queued_this_turn=_approval_queued_this_turn,
            ):
                log_case_c_signal("C2", canonical_user_id=identity.memory_key)
        except Exception:
            logger.debug("[TurnEnvelope] case_c2 detection skipped due to error", exc_info=True)

        # Ownership signal (routine, every agent-handled turn — not just
        # anomalies): recognized_intent/selected_handler/tool_use_emitted/
        # approval_queued/agent_claimed_approval/reply_owner. Requested to
        # prove precisely where the agent takes over reply ownership without
        # a backing action — a generalization of the Case C2 check above
        # with the routing context (which intent, which handler) attached,
        # logged for every turn so the population can be measured, not only
        # the already-suspected ones. Reuses route/tool_calls_made/
        # _approval_queued_this_turn already computed this turn — no new
        # reads. Log-only: never blocks/alters final_reply. Covers Telegram
        # and WhatsApp text turns identically, since both share this same
        # run_agent() code path.
        try:
            from core.turn_envelope import build_ownership_signal, log_ownership_signal
            _ownership_signal = build_ownership_signal(
                recognized_intent=getattr(route, "intent", "unknown"),
                selected_handler=getattr(route, "handler", "unknown"),
                tool_use_emitted=tool_calls_made > 0,
                approval_queued=_approval_queued_this_turn,
                final_reply=final_reply,
                # F52 PR6: build_ownership_signal()'s own reply_owner default
                # ("agent") was never overridden here, so a turn where a real
                # approval was queued this turn — and the agent's own text was
                # correctly suppressed by A32's Single-Speaker gate — still
                # logged reply_owner="agent", contradicting agent_claimed_
                # approval=False/tool_use_emitted=true right next to it in the
                # same record. "gateway" matches the label build_turn_envelope()
                # already uses for this exact situation (live_contract_reply_
                # owner="gateway") — no new vocabulary introduced.
                reply_owner="gateway" if _approval_queued_this_turn else "agent",
            )
            log_ownership_signal(_ownership_signal, canonical_user_id=identity.memory_key)
        except Exception:
            logger.debug("[TurnEnvelope] ownership signal skipped due to error", exc_info=True)

        # ── PA-01 — Phantom Approval Prompt structural enforcement ──────
        # docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md (approved
        # commit 81676ad). State-only: never inspects final_reply's text at
        # any point. is_hijack/detect_case_c2_signal() above are
        # observability/shadow-metrics/defense-in-depth only, not read here
        # (decision 8) — this block does not consume _ownership_signal.
        try:
            from core.router.risk_router import intent_requires_contract_for_success
            _pa01_contract_required = intent_requires_contract_for_success(getattr(route, "intent", None))
        except Exception:
            # Cannot classify -> treat as non-contract-required (matrix row 1),
            # per decision 5 — never fail an ordinary turn because PA-01's own
            # classifier broke. A PA-01 coverage gap if it ever fires,
            # accepted per fail-safe-degraded policy's own asymmetry.
            _pa01_contract_required = False

        if _pa01_contract_required:
            from feature_flags import get_pa01_enforcement_state
            _pa01_state = get_pa01_enforcement_state()
            if _pa01_state in ("shadow", "enforce"):
                try:
                    from core.router.risk_router import (
                        expected_tool_for_intent, contract_capable_this_turn,
                    )
                    _pa01_expected_tool = expected_tool_for_intent(getattr(route, "intent", None))
                    _pa01_contract_created = _pa01_contract_created_for_expected_tool(
                        tool_results_log, _pa01_expected_tool,
                    )
                    _pa01_outcome = None if _pa01_contract_created else _pa01_structured_terminal_outcome(
                        tool_results_log, _pa01_expected_tool,
                    )
                    _pa01_capable = (
                        _pa01_contract_created  # row 2 short-circuits capability entirely
                        or contract_capable_this_turn(route, identity, ctx)
                    )
                except Exception as exc:
                    # Fail-safe degraded (decision 5): cannot verify state ->
                    # block, forcing the Phantom row specifically, never the
                    # capability row (a broken check must not be misreported
                    # as "your role can't do this"). Distinct log marker.
                    logger.error(
                        "[PA-01] PA01_ENFORCEMENT_ERROR error_type=%s user=%s",
                        type(exc).__name__, _sanitize_id(identity.memory_key),
                    )
                    _pa01_contract_created, _pa01_outcome, _pa01_capable = False, None, True

                # Matrix row 2 — a contract for THIS intent's own expected
                # tool genuinely exists: nothing to do, Gateway's own message
                # already stands. A contract for a different tool does not
                # satisfy this row — it falls through exactly like no contract.
                if not _pa01_contract_created:
                    _pa01_response = None
                    if not _pa01_capable:
                        # Matrix row 5 — capability/permission gap.
                        _pa01_response = _PA01_CAPABILITY_UNAVAILABLE_FALLBACK
                        _pa01_row = "capability_unavailable"
                    elif _pa01_outcome is not None:
                        # Matrix row 3 — a real, gate-authored terminal outcome exists.
                        _outcome_kind, _outcome_message = _pa01_outcome
                        _pa01_response = _outcome_message  # the gate's own text, not agent text
                        _pa01_row = _outcome_kind.lower()
                    else:
                        # Matrix row 4 — the actual Phantom Approval Prompt case.
                        _pa01_response = _PA01_PHANTOM_APPROVAL_FALLBACK
                        _pa01_row = "phantom_approval_prompt"

                    if _pa01_response is not None:
                        logger.warning(
                            "[PA-01] %s state=%s user=%s intent=%s action=%s",
                            _pa01_row, _pa01_state, _sanitize_id(identity.memory_key),
                            getattr(route, "intent", "unknown"),
                            "blocked" if _pa01_state == "enforce" else "would_block",
                        )
                        if _pa01_state == "enforce":
                            final_reply = _pa01_response

        # PR-RP4 — compare the current response with structured turn evidence.
        # This observer always returns the exact input text; RP5 owns any future
        # enforcement/footer/fallback changes.
        #
        # F52 PR6: approval_prompt_sent is proven per-entry via the
        # __approval_queued__ sentinel's own "owner_notified" key (set only
        # when app.py's _queue_approval_detailed_impl() actually sent the
        # owner a message this turn — see that key's own comment), not
        # inferred from evidence.approvals_pending alone: a deferred batch
        # item (__approval_deferred_batch__) also counts as approval_pending
        # evidence but never sends the owner a direct notification.
        try:
            _approval_prompt_sent_this_turn = any(
                r.get("tool") == "__approval_queued__" and r.get("owner_notified")
                for r in tool_results_log
            )
            final_reply, _evidence_comparison = observe_shadow_finalizer(
                final_reply,
                turn_evidence,
                state=get_evidence_finalizer_state(),
                approval_prompt_sent=_approval_prompt_sent_this_turn,
            )
            if _out_meta is not None and _evidence_comparison is not None:
                _out_meta["evidence_finalizer_shadow"] = {
                    **_evidence_comparison.safe_record(),
                    "evidence": turn_evidence.safe_record(),
                }
        except Exception as _evidence_exc:
            logger.warning(
                "[EvidenceFinalizerShadow] observer_failed error_type=%s",
                type(_evidence_exc).__name__,
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


# ══════════════════════════════════════════════════
# BUG-PENDING-APPROVAL-B — global ingress context gate
#
# Single boundary, called once per inbound webhook event (Telegram +
# WhatsApp), after authentication + junk/idempotency/duplicate filtering +
# identity resolution, but before any callback/command/wizard/media/
# Decision Hub/Agent/early-return routing. Supersedes the earlier
# run_agent()-internal hook (PR #311) — that hook only ever saw events that
# already made it into the Agent message pipeline, missing every event
# handled by a separate code path (slash commands, wizard text/media
# capture, unrelated callbacks, general media, Decision Hub attachment
# references, WhatsApp media). This is the one place that sees all of them.
#
# Only a genuine attempt to resolve one of the identity's own live
# ActionGateway contracts (ActionGateway.is_own_resolution_event — confirm/
# cancel/disambiguation free text) is exempt. Everything else — including
# callbacks belonging to app.py's own separate _pending_approvals mechanism,
# which is not an ActionGateway resolution — marks live contracts
# interrupted. Duplicate/junk-filtered updates never reach this point at
# all (filtered earlier), so they cannot interrupt anything.
# ══════════════════════════════════════════════════

from dataclasses import dataclass as _dataclass


@_dataclass
class _IngressEvent:
    channel: str          # "telegram" | "whatsapp"
    kind: str             # "text" | "callback" | "media"
    text: str | None = None
    data: str | None = None  # raw callback_data, for kind="callback" only


def _apply_ingress_context_gate(
    identity, event: _IngressEvent, live_contracts: list | None = None,
) -> None:
    """See module note above. Fail-closed: if the primary mark cannot be
    recorded, an independent fallback path (find_live_contracts + the
    ledger's own update_status, not the same internal loop) forces the same
    result — a later bare confirm must never execute as though context
    integrity were known when it isn't.

    live_contracts: an already-fetched find_live_contracts() result for this
    identity, reused instead of querying again inside is_own_resolution_event.
    None (default, unchanged from before) means "fetch internally" — every
    caller that doesn't pass this keeps its exact original behavior. The
    three text-event webhook call sites pass this (see the Case C
    read-amplification fix — TURN_OWNERSHIP_EXTENSION.md); this makes it the
    SINGLE per-turn query, also threaded into run_agent() below.
    """
    if identity is None or not getattr(identity, "memory_key", None):
        # No action without identity (project-wide rule) — nothing pending
        # can be tied to an identity that never resolved in the first place.
        return
    user = identity.memory_key
    from core.action_gateway import action_gateway as _gw
    try:
        if event.kind == "text" and _gw.is_own_resolution_event(
            user, event.text or "", live=live_contracts,
        ):
            return  # genuine confirm/cancel/disambiguation — let normal routing resolve it
        # BUG-APPROVAL-CALLBACK-CONTEXT-INTERRUPT: an approve:/reject: button
        # press IS a genuine resolution event, exactly like a "מאשר"/"לא"
        # text confirm above — it is not some unrelated inbound message that
        # happened to arrive while a contract was pending. Marking
        # context_interrupted here previously forced an unnecessary
        # reconfirmation prompt on the very contract (or an unrelated
        # sibling) the button press was itself trying to resolve.
        if event.kind == "callback" and (event.data or "").startswith(("approve:", "reject:")):
            return
        _gw.mark_context_interrupted(user)
    except Exception:
        # Fail-closed, not fail-open: the primary mark couldn't be recorded,
        # so we cannot claim to know this contract's context is intact. The
        # incoming message still proceeds to normal routing below — only a
        # later bare confirm is affected — but the contract's integrity is
        # marked explicitly "unknown" (not silently left as "not interrupted"),
        # via an independently-written fallback method so a bug specific to
        # mark_context_interrupted() doesn't also break this path.
        logger.error(
            "[ActionGateway] ingress context gate primary mark failed for user=%s "
            "— marking context integrity unknown via independent fallback",
            user, exc_info=True,
        )
        try:
            _gw.mark_context_integrity_unknown(user)
        except Exception:
            logger.critical(
                "[ActionGateway] ingress context gate fallback ALSO failed for user=%s "
                "— pending contracts may be silently stale-approvable", user, exc_info=True,
            )


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
        # BUG-PENDING-APPROVAL-B: no junk/idempotency filter exists for
        # callbacks today — gate right after identity resolution. A
        # non-approval callback still always interrupts (BUG-APPROVAL-
        # CALLBACK-CONTEXT-INTERRUPT: approve:/reject: itself is exempted
        # inside _apply_ingress_context_gate, same principle as the text
        # confirm/cancel exemption above it — it IS the resolution event,
        # not an unrelated message that happened to arrive).
        try:
            _cb_identity = resolve_identity("telegram", str(call.from_user.id))
            _apply_ingress_context_gate(
                _cb_identity, _IngressEvent(channel="telegram", kind="callback", data=data),
            )
        except Exception as e:
            logger.error(f"[ActionGateway] ingress gate (callback) failed: {e}", exc_info=True)
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

        # ── junk/idempotency/duplicate filtering FIRST — moved ahead of
        # command/wizard dispatch so a duplicate slash-command or wizard
        # reply is discarded before it can reach the context gate at all
        # (BUG-PENDING-APPROVAL-B: duplicates must never interrupt anything).
        #
        # BUG-PENDING-APPROVAL-B follow-up: the dedup key must be the
        # provider's own event identity (update_id + message_id, chat-scoped
        # via sender_user_id), never the message text. Two DISTINCT Telegram
        # messages can legitimately carry identical text — e.g. the
        # reconfirmation flow's second "כן" after context_interrupted —
        # and keying on text falsely treated the second one as a duplicate
        # of the first, creating a dead end with no way to ever complete
        # the reconfirmation.
        _dedup_event_id = f"{update.update_id}:{update.message.message_id}"
        if idempotency.is_duplicate("telegram", sender_user_id, _dedup_event_id):
            try:
                bot.send_message(
                    reply_chat_id,
                    "♻️ ההודעה הזו כבר טופלה.\n"
                    "אם זו בקשה חדשה — נסח אותה אחרת."
                )
            except Exception as e:
                logger.debug(f"[Idempotency] notify failed: {e}")
            return "", 200

        # ── identity resolution + ingress context gate — before ANY
        # command/wizard/media/Decision Hub/Agent routing below.
        identity_for_gate = resolve_identity("telegram", sender_user_id)
        # Case C read-amplification fix (TURN_OWNERSHIP_EXTENSION.md): fetch
        # this identity's live contracts ONCE here — the single per-turn
        # source — and thread it into both the ingress gate (replacing its
        # own internal query) and run_agent() below (replacing its own
        # internal query at "1.65"), instead of three independent reads for
        # one incoming message. On failure, stays None: both downstream
        # callers already fall back to fetching internally on their own
        # (identical to this fetch never having existed), preserving the
        # ingress gate's original fail-open behavior — this new fetch must
        # not become a fail-closed point that wasn't one before.
        _live_contracts_for_turn = None
        try:
            from core.action_gateway import action_gateway as _gw_ingress
            _live_contracts_for_turn = _gw_ingress.find_live_contracts(identity_for_gate.memory_key)
        except Exception:
            logger.debug("[TurnEnvelope] turn-start live-contracts prefetch failed", exc_info=True)
        _apply_ingress_context_gate(
            identity_for_gate, _IngressEvent(channel="telegram", kind="text", text=text),
            live_contracts=_live_contracts_for_turn,
        )

        # Slash commands → registered @bot.message_handler(commands=[...]) handlers.
        # They authenticate via resolve_identity internally; we don't go through run_agent.
        if text.startswith("/"):
            try:
                bot.process_new_updates([update])
            except Exception as e:
                logger.error(f"[Command] dispatch error: {e} | cmd={text.split()[0]!r}", exc_info=True)
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

        # ── Decision Hub Stage 0.6 — "זה הנספח" attachment reference ──
        # SPEC_File_Context_Reference.md, Rule 10: max one linking question.
        # Telegram-specific (inline keyboards) — handled here, not in the
        # channel-agnostic run_agent. Flag-gated + additive.
        if _flag_enabled("FEATURE_DECISION_HUB"):
            try:
                from cmd_decision import is_attachment_reference, handle_attachment_reference
                if is_attachment_reference(text):
                    if handle_attachment_reference(bot, identity_for_gate, reply_chat_id, text):
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
            reply = run_agent(
                text, sender_user_id, channel="telegram", raw_event_id=str(update.update_id),
                _live_contracts_snapshot=_live_contracts_for_turn,
            )
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

        # BUG-SS-FALLBACK-CONTRADICTION: sanitize_agent_response() can return
        # "" to deliberately suppress a redundant/contradictory reply (e.g.
        # after a pending-approval message was already sent this turn) —
        # an empty reply must never be sent as a blank Telegram message.
        if reply:
            try:
                bot.send_message(reply_chat_id, reply)
            except Exception as e:
                logger.error(f"[Telegram] send error: {e}")
        return "", 200

    # F16 — Media Layer: voice notes / photo / document uploads
    if update.message and update.message.content_type in ("voice", "photo", "document"):
        # BUG-PENDING-APPROVAL-B: no junk/idempotency filter exists for
        # media today — gate right after identity resolution, before any
        # wizard-file-capture or generic media routing below.
        try:
            _media_identity_gate = resolve_identity("telegram", str(update.message.from_user.id))
            _apply_ingress_context_gate(
                _media_identity_gate, _IngressEvent(channel="telegram", kind="media"),
            )
        except Exception as e:
            logger.error(f"[ActionGateway] ingress gate (media) failed: {e}", exc_info=True)

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

    # BUG-PENDING-APPROVAL-B: identity resolution + ingress context gate —
    # after junk/idempotency filtering above, before media/furniture-funnel/
    # Agent routing below. WhatsApp text ("כן"/"לא"/etc.) still reaches
    # run_agent() unconditionally further down, so kind="text" here lets
    # is_own_resolution_event exempt a genuine resolution the same way.
    # Case C read-amplification fix (TURN_OWNERSHIP_EXTENSION.md): fetch
    # once, thread into both the ingress gate and run_agent() below — see
    # the Telegram handler's identical comment for the full rationale.
    _live_contracts_for_turn = None
    try:
        _wa_identity_gate = resolve_identity("whatsapp", sender)
        try:
            from core.action_gateway import action_gateway as _gw_ingress_wa
            _live_contracts_for_turn = _gw_ingress_wa.find_live_contracts(_wa_identity_gate.memory_key)
        except Exception:
            logger.debug("[TurnEnvelope] turn-start live-contracts prefetch failed (whatsapp)", exc_info=True)
        _apply_ingress_context_gate(
            _wa_identity_gate,
            _IngressEvent(channel="whatsapp", kind="text", text=incoming),
            live_contracts=_live_contracts_for_turn,
        )
    except Exception as e:
        logger.error(f"[ActionGateway] ingress gate (whatsapp) failed: {e}", exc_info=True)

    # ── BUG-071 FIX: WhatsApp Media Support ─────────────────────────────
    # Extract and process media (voice/file) from Twilio webhook.
    # Per F13 architecture: metadata extraction + byte download from signed URL,
    # routed through unified media_handler pipeline (same as Telegram C90).
    try:
        from whatsapp_media_adapter import (
            extract_whatsapp_media, download_whatsapp_media, infer_file_type, infer_filename
        )
        from media_handler import handle_voice_note, handle_file_upload

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
        _live_contracts_snapshot = _live_contracts_for_turn,
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
    # BUG-SS-FALLBACK-CONTRADICTION: agent_reply (and therefore gated_reply)
    # can be "" — a deliberate suppression signal from
    # sanitize_agent_response(), not just "no reply computed" (None). Treat
    # both as "send nothing" rather than sending a blank WhatsApp message.
    if gated_reply:
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

    # BUG-PENDING-APPROVAL-B: identity resolution + ingress context gate —
    # after junk/idempotency filtering above, before media/outbound-stub/
    # Agent routing below.
    # Case C read-amplification fix (TURN_OWNERSHIP_EXTENSION.md): fetch
    # once, thread into both the ingress gate and run_agent() below — see
    # the Telegram handler's identical comment for the full rationale.
    _live_contracts_for_turn = None
    try:
        _meta_identity_gate = resolve_identity("whatsapp", sender)
        try:
            from core.action_gateway import action_gateway as _gw_ingress_meta
            _live_contracts_for_turn = _gw_ingress_meta.find_live_contracts(_meta_identity_gate.memory_key)
        except Exception:
            logger.debug("[TurnEnvelope] turn-start live-contracts prefetch failed (meta whatsapp)", exc_info=True)
        _apply_ingress_context_gate(
            _meta_identity_gate,
            _IngressEvent(channel="whatsapp", kind="text", text=incoming),
            live_contracts=_live_contracts_for_turn,
        )
    except Exception as e:
        logger.error(f"[ActionGateway] ingress gate (meta whatsapp) failed: {e}", exc_info=True)

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
        _live_contracts_snapshot = _live_contracts_for_turn,
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
        if reply:
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
    run_startup_sequence()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
