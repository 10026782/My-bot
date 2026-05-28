"""
הבוס בוט v2.1 — Flask App
ארכיטקטורה: Native Tool Calling + Budget Protection + Proactive Worker + Identity Layer
"""

import os
import logging
import requests as http_requests
from flask import Flask, request, jsonify, Response
from anthropic import Anthropic
from tools import TOOL_SCHEMAS, dispatch_tool
from memory import ConversationMemory
from worker import schedule_background_worker
from lead_qualifier import handle_lead_message, lead_sessions
from creative_generator import handle_creative_command
from identity import resolve_identity

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Env Vars ─────────────────────────────────────────────────────────────────
_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _api_key:
    logger.critical("ANTHROPIC_API_KEY is not set — API calls will fail")
client = Anthropic(api_key=_api_key)

_telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
if not _telegram_token:
    logger.critical("TELEGRAM_TOKEN is not set — Telegram webhook will not work")

# ─── Per-User Memory (max 500 users) ──────────────────────────────────────────
_user_memories: dict = {}
_MAX_MEMORY_USERS = 500


def _get_memory(user_id: str) -> ConversationMemory:
    if user_id not in _user_memories:
        if len(_user_memories) >= _MAX_MEMORY_USERS:
            oldest = next(iter(_user_memories))
            del _user_memories[oldest]
        _user_memories[user_id] = ConversationMemory(max_interactions=5)
    return _user_memories[user_id]


# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """אתה "הבוס בוט" – עוזר מנכ"ל, מנהל פרויקטים ומומחה אסטרטגי חריף וחד.
המנהל שלך (אלייהו) הוא בעל חזון ואופטימי מטבעו.
התפקיד שלך הוא להוות משקל נגד – לחפש את האותיות הקטנות, להציג את הסיכונים,
את נקודות התורפה בעסקאות, והיכן שותפים או מוכרים עלולים להטעות אותו.
היה קול ההיגיון הקר, הספקני והאנליטי.

כלים זמינים — השתמש בהם לפני שאתה מנחש:
- airtable_get_records: שליפת משימות, עסקאות, לידים, מלאי מ-Airtable
- airtable_create_record: יצירת רשומה חדשה (משימה, ליד, עסקה)
- airtable_update_record: עדכון רשומה קיימת לפי ID
- add_knowledge: שמירת עובדה לזיכרון הבוט

כללים נוקשים:
1. תמיד תענה בעברית רהוטה, עסקית, חדה וללא גינונים מיותרים.
2. ברירת מחדל: תשובה של שורה עד שתיים בלבד. קצר, חד, לעניין.
3. רק אם ההודעה מתחילה ב-# — הפעל "מצב ניתוח עמוק" ותן ניתוח מורחב.
4. אל תחזור על שאלת המשתמש. אל תוסיף מילות מחמאה. ישר לגוף העניין.
5. כשנשאלים על נתונים (משימות/עסקאות/לידים) — קרא לכלי Airtable, אל תאמר שאין לך גישה."""

MAX_TOOL_TURNS = 2

# ─── Core Agent Loop ──────────────────────────────────────────────────────────
def run_agent(user_message: str, channel: str = "telegram", user_id: str = "default") -> str:
    """
    לולאת הסוכן המרכזית עם הגנת תקציב קשיחה.
    channel: "whatsapp" | "telegram"
    """
    mem = _get_memory(user_id)
    mem.add_user_message(user_message)
    messages = mem.get_messages()

    turn_count = 0
    response_text = "לא הצלחתי לעבד את הבקשה. נסה שוב."

    try:
        while turn_count < MAX_TOOL_TURNS:
            turn_count += 1
            logger.info(f"Agent turn {turn_count}/{MAX_TOOL_TURNS} | user={user_id}")

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000 if channel == "telegram" else 400,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            stop_reason = response.stop_reason

            if stop_reason == "end_turn":
                response_text = _extract_text(response)
                break

            elif stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Calling tool: {block.name} | input: {block.input}")
                        result = dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]

            else:
                logger.warning(f"Unexpected stop_reason: {stop_reason}")
                break

        else:
            logger.warning("MAX_TOOL_TURNS reached — cutting loop to prevent cost leak.")
            response_text = "הגעתי למגבלת הסיבובים. אנא פרט את הבקשה ונסה שוב."

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        response_text = f"שגיאה פנימית: {e}"

    mem.add_assistant_message(response_text)
    return response_text


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "לא הצלחתי לייצר תשובה. נסה שוב."


# ─── Webhook Endpoints ────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "OK", 200


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook_twilio():
    from twilio.twiml.messaging_response import MessagingResponse
    user_message = request.values.get("Body", "").strip()
    sender = request.values.get("From", "unknown")
    if not user_message:
        return "OK", 200

    # ─── זיהוי תפקיד ───────────────────────────────────────────────────────────
    phone = sender.replace("whatsapp:", "")
    identity = resolve_identity("whatsapp", phone)
    logger.info(f"WhatsApp message | sender={phone} | role={identity.role}")

    # בעל בית / צוות → ישר ל-agent, בלי שאלות ליד
    if identity.is_internal:
        reply = run_agent(user_message, channel="whatsapp", user_id=identity.sender)
        resp = MessagingResponse()
        resp.message(reply)
        return Response(str(resp), mimetype="application/xml")

    # לקוח חיצוני → State Machine כרגיל
    session = lead_sessions.get(sender)
    if session is None or not session["done"]:
        reply = handle_lead_message(sender, user_message)
        if reply:
            resp = MessagingResponse()
            resp.message(reply)
            return Response(str(resp), mimetype="application/xml")

    reply = run_agent(user_message, channel="whatsapp", user_id=sender)
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp), 200, {"Content-Type": "text/xml"}


@app.route(f"/{_telegram_token}", methods=["POST"])
def telegram_webhook():
    logger.info("Telegram webhook hit")
    data = request.json or {}

    message_obj = data.get("message", {})
    user_message = message_obj.get("text", "")
    chat_id = message_obj.get("chat", {}).get("id")

    if not user_message:
        return "OK", 200

    telegram_url = f"https://api.telegram.org/bot{_telegram_token}/sendMessage"

    if "קריאייטיב" in user_message:
        reply = handle_creative_command(user_message, chat_id)
        try:
            http_requests.post(telegram_url, json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown"
            }, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Telegram creative reply: {e}")
        return "OK", 200

    reply = run_agent(user_message, channel="telegram", user_id=str(chat_id))
    try:
        http_requests.post(telegram_url, json={
            "chat_id": chat_id,
            "text": reply
        }, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Telegram reply: {e}")

    return "OK", 200


@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    from worker import run_proactive_check
    result = run_proactive_check()
    return jsonify({"status": "ok", "result": result})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"})


# ─── Bootstrap — רץ גם תחת gunicorn ──────────────────────────────────────────
schedule_background_worker()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
