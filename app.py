# app.py — The Boss Bot v3.3
# Multi-Tenant Architecture: Identity → Context → Agent
#
# תיקונים v3.3 (על גבי v3.2):
# • action_validator: gate לפני dispatch_tool — בדיקת פרמטרים rule-based
# • hybrid prompt: Layer 7+8 עוברים ל-user message (חיסכון ~100 טוקן/בקשה)
# • grounding: בודק last_turn_results בלבד (לא all) — מאפשר retry
# • UX: typing indicator לפני כל תשובה

import os
import logging
from flask import Flask, request, Response, abort, jsonify

import anthropic
import telebot
from twilio.twiml.messaging_response import MessagingResponse

from memory_store import memory
from identity import resolve_identity, Role
from context import build_context, check_tool_results
from action_validator import validate_action, ActionBlocked
from tool_registry import enforce, ToolDenied
from scheduler import start_scheduler
from tools import dispatch_tool
from guards import idempotency, rate_limiter, validate_tool_output

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── קבועים ────────────────────────────────────────
MAX_TOOL_TURNS = 4       # היה 2 — מאפשר שרשרת כלים מלאה
AGENT_TIMEOUT  = 25      # שניות

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
# _summarize_tool_context
# ══════════════════════════════════════════════════

def _summarize_tool_context(tool_results: list[dict]) -> str:
    """
    בונה סיכום קצר של תוצאות הכלים לשמירה בזיכרון.
    כך בהודעה הבאה Claude יודע "מה שלפתי בשיחה הקודמת"
    מבלי לשמור את מבנה ה-tool_result הטכני (שאינו valid כהיסטוריה).
    """
    if not tool_results:
        return ""
    parts = []
    for r in tool_results:
        content = r.get("content", "")
        if isinstance(content, str) and content and not content.startswith("❌"):
            # קח רק 80 תווים ראשונים — מספיק להקשר, לא מציף
            parts.append(content[:80].replace("\n", " "))
    if not parts:
        return ""
    joined = " | ".join(parts)
    return f"[הקשר כלים מהשיחה הקודמת: {joined}]"


# ══════════════════════════════════════════════════
# run_agent — Identity-Aware Agent Loop
# ══════════════════════════════════════════════════

def run_agent(user_text: str, chat_id: str, channel: str = "telegram") -> str:
    # ─── Identity ──────────────────────────────────
    identity = resolve_identity(channel, chat_id)

    # ─── Rate Limit ────────────────────────────────
    if not rate_limiter.is_allowed(identity.memory_key):
        return "⚠️ יותר מדי בקשות. המתן דקה ונסה שוב."

    # ─── Readonly block ────────────────────────────
    if identity.role == Role.READONLY:
        return "⚠️ אין לך גישה למערכת. פנה למנהל."

    try:
        research_mode = user_text.startswith("#") and identity.is_owner
        clean_msg     = user_text[1:].strip() if research_mode else user_text

        # ─── Context + History ─────────────────────
        ctx      = build_context(identity, user_text)
        history  = memory.get_for_claude(ctx.memory_key)

        # Layer 7+8 נכנסים ל-user message (לא system) — חוסך ~100 טוקן/בקשה
        from core_knowledge import build_context_layer, dynamic_context
        ctx_line  = build_context_layer()
        data_line = dynamic_context.get()
        user_content = clean_msg
        if ctx_line or data_line:
            suffix = "\n".join(filter(None, [ctx_line, data_line]))
            user_content = f"{clean_msg}\n{suffix}"

        messages = history + [{"role": "user", "content": user_content}]

        logger.info(f"run_agent | {ctx.identity_label} | {ctx.model} | {ctx.max_tokens}tok")

        final_reply     = "⚠️ לא התקבלה תשובה."
        tool_calls_made = 0
        all_tool_results: list[dict] = []   # לסיכום זיכרון בלבד
        last_turn_results: list[dict] = []  # ל-grounding (הסיבוב האחרון בלבד)

        # ══════════════════════════════════════════
        # Agent Loop
        # ══════════════════════════════════════════
        while True:
            response = client.messages.create(
                model=ctx.model,
                max_tokens=ctx.max_tokens,
                temperature=0.2,
                system=ctx.system_prompt,
                tools=ctx.allowed_tools,
                messages=messages
            )

            tool_uses   = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            # ─── תשובה סופית — אין כלים נוספים ────
            if not tool_uses:
                candidate = text_blocks[0].text if text_blocks else "✅ פעולה הושלמה."

                # Grounding: בדוק רק את הכלים של הסיבוב האחרון.
                # אם Claude ניסה כלי חלופי והצליח — לא חוסמים בגלל כשל ישן.
                if last_turn_results:
                    grounded, err_msg = check_tool_results(last_turn_results)
                    if not grounded:
                        logger.warning("Grounding: last-turn tool failure — blocking answer")
                        final_reply = err_msg
                        break

                final_reply = candidate
                break

            # ─── MAX_TOOL_TURNS הגיע לסוף ──────────
            if tool_calls_made >= MAX_TOOL_TURNS:
                final_reply = (
                    text_blocks[0].text if text_blocks
                    else (
                        "⚠️ לא הגעתי לתוצאה אחרי מספר ניסיונות. "
                        "בדוק חיבור Airtable/Drive ונסה שוב, "
                        "או פרק לשלבים."
                    )
                )
                break

            # ─── Tool Loop ──────────────────────────
            # tool_results הוא list[dict] — תקני ל-Anthropic API
            # (role=user, content=list) — לא שומרים מבנה זה בזיכרון
            tool_results: list[dict] = []

            for tu in tool_uses:
                try:
                    enforce(tu.name, identity)
                except ToolDenied as e:
                    logger.warning(f"Tool denied: {tu.name} for {identity.role}")
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tu.id,
                        "content":     str(e),
                    })
                    continue

                # ACTION VALIDATOR — gate לפני dispatch
                av = validate_action(tu.name, tu.input)
                if isinstance(av, ActionBlocked):
                    logger.info(f"ActionBlocked: {tu.name} — {av.reason}")
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tu.id,
                        "content":     f"BLOCKED: {av.reason}",
                    })
                    continue

                logger.info(f"Tool: {tu.name} | {str(tu.input)[:80]}")
                raw    = dispatch_tool(tu.name, tu.input)
                result = validate_tool_output(tu.name, raw)
                logger.info(f"  -> {result[:80]}")

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tu.id,
                    "content":     result,   # תמיד string — תקני ל-API
                })

            # last_turn = סיבוב נוכחי בלבד (ל-grounding)
            # all = מצטבר (לסיכום זיכרון)
            last_turn_results = tool_results
            all_tool_results.extend(tool_results)

            tool_calls_made += 1

            # ── הזן לאנתרופיק: assistant (כולל tool_use) + user (tool_result list) ──
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})
            # ↑ content=list תקני לאנתרופיק בלולאה הפנימית.
            # לא נשמר ב-memory_store (ראה למטה).

        # ══════════════════════════════════════════
        # שמירת זיכרון ארוך-טווח
        # שומרים גם סיכום הקשר כלים
        # ══════════════════════════════════════════
        tool_ctx = _summarize_tool_context(all_tool_results)

        # user: ההודעה + הקשר כלים (אם יש) — מאפשר ל-Claude לדעת "מה שלפתי"
        user_memory = clean_msg
        if tool_ctx:
            user_memory = f"{clean_msg}\n{tool_ctx}"

        memory.add(ctx.memory_key, "user",      user_memory)
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
        "version":        "3.3",
        "max_tool_turns": MAX_TOOL_TURNS,
        "grounding":      "enabled",
        "layers":         8,
        "ttl_hours":      4,
        "tool_memory":    "enabled",
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
        # UX: הצג "מקליד..." כדי שהמשתמש ידע שהבוט עובד (לא תקוע)
        try:
            bot.send_chat_action(chat_id, "typing")
        except Exception:
            pass
        reply = run_agent(text, chat_id, channel="telegram")
        try:
            bot.send_message(chat_id, reply)
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
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
            logger.error(f"worker telegram: {e}")
        return jsonify({"status": "ok", "reply": reply[:200]}), 200
    except Exception as e:
        logger.error(f"worker_trigger: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "The Boss is Live v3.3 — Hybrid Prompt + Action Validator ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
