# app.py — The Boss Bot v3.0
# Architecture: Identity → Router → Context → Agent
#
# כל בקשה עוברת:
#   resolve_identity → route_request → build_context → run_agent

import os
import logging
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

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── קבועים ────────────────────────────────────────
MAX_TOOL_TURNS = 2
AGENT_TIMEOUT  = 25

# ─── קליינטים ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_APP_URL    = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
bot    = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask(__name__)

try:
    _scheduler = start_scheduler()
    logger.info("Scheduler OK")
except Exception as e:
    logger.error(f"Scheduler failed: {e}")

if os.environ.get("SETUP_WEBHOOK") == "1":
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_APP_URL}/{TELEGRAM_TOKEN}")
        logger.info("Telegram Webhook set")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


# ══════════════════════════════════════════════════
# Integration Layer — CORE_02.6
# ══════════════════════════════════════════════════

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

    # ── 4. Route Decision ─────────────────────────
    if route.handler == Handler.BLOCK:
        logger.warning(f"[Router] BLOCKED: {identity} intent={route.intent}")
        return route.response_override or "⛔ אין לך הרשאה לבצע פעולה זו."

    if route.handler == Handler.CLARIFY:
        logger.info(f"[Router] CLARIFY: intent={route.intent} confidence={route.confidence:.2f}")
        return route.response_override or "לא הצלחתי להבין — תוכל לנסח אחרת?"

    if route.handler == Handler.APPROVAL:
        logger.info(f"[Router] APPROVAL NEEDED: intent={route.intent} domain={route.domain}")
        return (
            route.response_override or
            f"⏳ הפעולה *{route.intent}* דורשת אישור לפני ביצוע.\n"
            f"אשר עם: ✅ כן / ❌ לא"
        )

    # ── 5. Agent Loop ─────────────────────────────
    try:
        research_mode = user_text.startswith("#") and identity.is_owner
        clean_msg     = user_text[1:].strip() if research_mode else user_text

        # Context מקבל את ה-domain מה-RouteDecision
        ctx      = build_context(identity, user_text, domain=route.domain)
        history  = memory.get_for_claude(ctx.memory_key)
        messages = history + [{"role": "user", "content": clean_msg}]

        logger.info(
            f"[Agent] {ctx.identity_label} | "
            f"intent={route.intent} domain={route.domain} | "
            f"model={ctx.model} tools={len(ctx.allowed_tools)}"
        )

        final_reply     = "⚠️ לא התקבלה תשובה."
        tool_calls_made = 0

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
                try:
                    enforce(tu.name, identity)
                except ToolDenied as e:
                    logger.warning(f"[Tool] Denied: {tu.name} for {identity.role}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
                    })
                    continue

                logger.info(f"[Tool] {tu.name} | {str(tu.input)[:80]}")
                raw    = dispatch_tool(tu.name, tu.input, identity)
                result = validate_tool_output(tu.name, raw)
                logger.info(f"[Tool] → {result[:80]}")

                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id, "content": result
                })

            tool_calls_made += 1
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

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
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
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


@app.route("/webhook/whatsapp", methods=["POST"])
def webhook_whatsapp():
    incoming  = request.values.get("Body", "").strip()
    sender    = request.values.get("From", "whatsapp:unknown")
    to_number = request.values.get("To",   "whatsapp:unknown")
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


@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
