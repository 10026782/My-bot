# app.py — The Boss Bot v3.4
# Multi-Tenant Architecture: Identity → Context → Agent
# v3.4: dispatch_tool(name, input, identity), WORKER_SECRET, identity None guard,
#        action_validator, check_tool_results, tool memory, "typing..." UX

import os
import logging
from flask import Flask, request, Response, abort, jsonify

import anthropic
import telebot
from twilio.twiml.messaging_response import MessagingResponse

from memory_store        import memory
from identity            import resolve_identity, Role
from context             import build_context, check_tool_results
from action_validator    import validate_action, ActionBlocked
from tool_registry       import enforce, ToolDenied
from scheduler           import start_scheduler
from tools               import dispatch_tool
from guards              import idempotency, rate_limiter, validate_tool_output

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── קבועים ────────────────────────────────────────
MAX_TOOL_TURNS = 4
AGENT_TIMEOUT  = 25

# ─── env vars ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_APP_URL    = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")
WORKER_SECRET     = os.environ.get("WORKER_SECRET", "")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN לא מוגדר — הוסף env var ב-Render")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY לא מוגדר — הוסף env var ב-Render")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=AGENT_TIMEOUT)
bot    = telebot.TeleBot(TELEGRAM_TOKEN)
app    = Flask(__name__)

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
# Tool memory — תמצות context כלים בין תורות
# ══════════════════════════════════════════════════

def _summarize_tool_context(tool_results: list[dict], max_chars: int = 800) -> str:
    """מקצר את תוצאות הכלים להקשר בין iterations."""
    lines = []
    for r in tool_results:
        content = r.get("content", "")
        if isinstance(content, str) and content:
            lines.append(content[:200])
    summary = "\n".join(lines)
    return summary[:max_chars] if len(summary) > max_chars else summary


# ══════════════════════════════════════════════════
# run_agent — Identity-Aware Agent Loop v3.4
# ══════════════════════════════════════════════════

def run_agent(user_text: str, chat_id: str, channel: str = "telegram") -> str:

    # ─── Identity ──────────────────────────────────
    identity = resolve_identity(channel, chat_id)

    # ─── Identity None guard ───────────────────────
    if identity is None:
        logger.error(f"resolve_identity returned None for {channel}:{chat_id}")
        return "❌ שגיאת זיהוי פנימית."

    # ─── Rate Limit ────────────────────────────────
    if not rate_limiter.is_allowed(identity.memory_key):
        return "⚠️ יותר מדי בקשות. המתן דקה ונסה שוב."

    # ─── Readonly block ────────────────────────────
    if identity.role == Role.READONLY:
        return "⚠️ אין לך גישה למערכת. פנה למנהל."

    try:
        research_mode = user_text.startswith("#") and identity.is_owner
        clean_msg     = user_text[1:].strip() if research_mode else user_text

        # ─── typing... UX ──────────────────────────
        if channel == "telegram":
            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception:
                pass

        # ─── Context Builder ───────────────────────
        ctx      = build_context(identity, user_text)
        history  = memory.get_for_claude(ctx.memory_key)
        messages = history + [{"role": "user", "content":
                                f"{ctx.user_context_hint}\n{clean_msg}" if ctx.user_context_hint
                                else clean_msg}]

        logger.info(f"run_agent | {ctx.identity_label} | {ctx.model} | {ctx.max_tokens}tok")

        final_reply     = "⚠️ לא התקבלה תשובה."
        tool_calls_made = 0
        tool_context    = ""   # זיכרון תוצאות כלים בין iterations

        while True:
            # הוסף tool context אם יש
            sys_prompt = ctx.system_prompt
            if tool_context:
                sys_prompt += f"\n\n[תוצאות כלים קודמות]\n{tool_context}"

            response = client.messages.create(
                model       = ctx.model,
                max_tokens  = ctx.max_tokens,
                temperature = 0.2,
                system      = sys_prompt,
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

            # ─── Tool Loop ─────────────────────────
            tool_results = []
            for tu in tool_uses:

                # 1. Registry permission check
                try:
                    enforce(tu.name, identity)
                except ToolDenied as e:
                    logger.warning(f"Tool denied: {tu.name} for {identity.role}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id,
                        "content": str(e)
                    })
                    continue

                # 2. action_validator — presence + structure + חוק 9%
                validation = validate_action(tu.name, dict(tu.input))
                if isinstance(validation, ActionBlocked):
                    logger.info(f"ActionBlocked: {tu.name} — {validation.reason[:60]}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu.id,
                        "content": f"⛔ {validation.reason}"
                    })
                    continue

                # 3. Dispatch
                logger.info(f"Tool: {tu.name} | {str(tu.input)[:80]}")
                raw    = dispatch_tool(tu.name, tu.input, identity=identity)
                result = validate_tool_output(tu.name, raw)
                logger.info(f"  -> {result[:80]}")

                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": result
                })

            # 4. Grounding check
            grounded, err = check_tool_results(tool_results)
            if not grounded:
                logger.warning(f"Grounding failed: {err}")

            # 5. עדכון tool context לאיטרציה הבאה
            tool_context = _summarize_tool_context(tool_results)

            tool_calls_made += 1
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

        # ─── שמור זיכרון ───────────────────────────
        memory.add(ctx.memory_key, "user",      clean_msg)
        memory.add(ctx.memory_key, "assistant", final_reply)

        return final_reply

    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic {e.status_code}: {e.message}")
        return f"❌ שגיאת API ({e.status_code}). נסה שוב."
    except Exception as e:
        logger.error(f"run_agent error: {e}", exc_info=True)
        return f"❌ שגיאה פנימית: {e}"


# ══════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":         "ok",
        "version":        "3.4",
        "max_tool_turns": MAX_TOOL_TURNS,
        "security":       "tenant-enforced",
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
            bot.send_message(chat_id, reply, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            try:
                bot.send_message(chat_id, reply)   # fallback ללא Markdown
            except Exception:
                pass
    return "", 200


@app.route("/webhook/whatsapp", methods=["POST"])
def webhook_whatsapp():
    incoming = request.values.get("Body", "").strip()
    sender   = request.values.get("From", "whatsapp:unknown")
    msg_sid  = request.values.get("MessageSid", "")
    if not incoming:
        return Response(str(MessagingResponse()), mimetype="application/xml")
    dedup_key = msg_sid if msg_sid else incoming
    if idempotency.is_duplicate("whatsapp", sender, dedup_key):
        return Response(str(MessagingResponse()), mimetype="application/xml")
    resp = MessagingResponse()
    resp.message(run_agent(incoming, sender, channel="whatsapp"))
    return Response(str(resp), mimetype="application/xml")


@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    # ─── WORKER_SECRET auth ────────────────────────
    if WORKER_SECRET:
        auth = request.headers.get("X-Worker-Secret", "")
        if auth != WORKER_SECRET:
            logger.warning("worker_trigger: unauthorized attempt")
            abort(403)

    try:
        payload = request.get_json(force=True) or {}
        chat_id = payload.get("chat_id", "")
        event   = payload.get("event", "")
        if not chat_id or not event:
            return jsonify({"error": "chat_id and event required"}), 400
        reply = run_agent(f"[אירוע מערכת]: {event}", chat_id)
        try:
            bot.send_message(chat_id, reply, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"worker telegram: {e}")
        return jsonify({"status": "ok", "reply": reply[:200]}), 200
    except Exception as e:
        logger.error(f"worker_trigger: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "The Boss is Live v3.4 — Multi-Tenant ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
