# app.py — The Boss Bot v3.0
# Architecture: Identity → Router → Context → Agent
#
# כל בקשה עוברת:
#   resolve_identity → route_request → build_context → run_agent

import os
import logging

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)

from startup_validator import validate_startup, format_startup_message
validate_startup()   # Fail Fast — SystemExit if CRITICAL env var missing

from flask import Flask, request, Response, abort, jsonify

import anthropic
import telebot
from twilio.twiml.messaging_response import MessagingResponse

from memory_store    import memory
from identity        import resolve_identity
from context         import build_context
from tool_registry   import enforce, ToolDenied
from scheduler       import start_scheduler
from tools           import dispatch_tool
from guards          import idempotency, rate_limiter, validate_tool_output
from config          import get_domain as _channel_domain
from core.router     import route_request, RouteDecision, Handler
from core.anti_hallucination import verify_execution, sanitize_agent_response

logger = logging.getLogger(__name__)

# ─── קבועים ────────────────────────────────────────
MAX_TOOL_TURNS = 2
AGENT_TIMEOUT  = 25

# ─── קליינטים ──────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_APP_URL     = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")
WEBHOOK_SECRET     = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
bot    = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask(__name__)


@bot.message_handler(commands=["status"])
def cmd_status(msg):
    """Owner בלבד — מצב env vars."""
    identity = resolve_identity("telegram", str(msg.from_user.id))
    if not identity or identity.role not in ("owner", "admin"):
        return
    bot.send_message(msg.chat.id, format_startup_message(), parse_mode="Markdown")

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


def approval_response(route: RouteDecision) -> str:
    logger.info(f"[APPROVAL] intent={route.intent} domain={route.domain}")
    return (
        route.response_override or
        f"הפעולה '{route.intent}' דורשת אישור לפני ביצוע.\n"
        f"אשר עם: ✅ כן / ❌ לא"
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

    owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
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
        except Exception as e:
            logger.error(f"[Approval] notify owner failed: {e}")

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

    if action == "approve":
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
        tool_name     = payload["tool_name"]
        tool_inputs   = payload["tool_inputs"]
        user_chat_id  = payload["user_chat_id"]
        channel       = payload.get("channel", "telegram")

        identity = resolve_identity(channel, user_chat_id)
        raw      = dispatch_tool(tool_name, tool_inputs, identity)
        result   = validate_tool_output(tool_name, raw)
        logger.info(f"[Approval] ✅ confirmed {action_id} | {tool_name}")

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
    user_text:          str,
    chat_id:            str,
    channel:            str = "telegram",
    domain_from_channel: str = "",
) -> str:

    # ── 1. Identity ───────────────────────────────
    identity = resolve_identity(channel, chat_id)
    logger.info(f"[Identity] {identity}")

    # ── 2. Rate Limit ─────────────────────────────
    if not rate_limiter.is_allowed(identity.memory_key):
        return "⚠️ יותר מדי בקשות. המתן דקה ונסה שוב."

    # ── 3. Router — CORE_02.6 Integration ────────
    route = _safe_route(user_text, channel, identity, domain_from_channel)
    logger.info(route.to_log())

    # ── 4. Dispatch ───────────────────────────────
    if route.handler == Handler.CLARIFY:
        return clarify_response(route)

    if route.handler == Handler.APPROVAL:
        return approval_response(route)

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
        history  = memory.get_for_claude(ctx.memory_key)
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
                final_reply = (text_blocks[0].text if text_blocks
                               else "⚠️ הגעתי לגבול הכלים. נסה לפרק לשלבים.")
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

                entry = {"type": "tool_result", "tool_use_id": tu.id, "content": result}
                tool_results.append(entry)
                tool_results_log.append(entry)   # A32: accumulate for final check

            tool_calls_made += 1
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
        return f"❌ שגיאת API ({e.status_code}). נסה שוב."
    except Exception as e:
        logger.error(f"[Agent] error: {e}", exc_info=True)
        return f"❌ שגיאה פנימית: {e}"


# ══════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":         "ok",
        "version":        "3.0",
        "max_tool_turns": MAX_TOOL_TURNS,
        "router":         "CORE_02.6",
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
        chat_id = str(update.message.chat.id)
        text    = update.message.text
        if idempotency.is_duplicate("telegram", chat_id, text):
            return "", 200
        reply = run_agent(text, chat_id, channel="telegram")
        try:
            bot.send_message(chat_id, reply)
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
