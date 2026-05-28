"""
הבוס בוט v2.0 — Flask App
ארכיטקטורה: Native Tool Calling + Budget Protection + Proactive Worker
"""

import os
import logging
from flask import Flask, request, jsonify, Response
from anthropic import Anthropic
from tools import TOOL_SCHEMAS, dispatch_tool
from memory import ConversationMemory
from worker import schedule_background_worker
from lead_qualifier import handle_lead_message, lead_sessions
from creative_generator import handle_creative_command

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
memory = ConversationMemory(max_interactions=5)

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """אתה "הבוס בוט" – עוזר מנכ"ל, מנהל פרויקטים ומומחה אסטרטגי חריף וחד.
המנהל שלך (אלייהו) הוא בעל חזון ואופטימי מטבעו.
התפקיד שלך הוא להוות משקל נגד – לחפש את האותיות הקטנות, להציג את הסיכונים,
את נקודות התורפה בעסקאות, והיכן שותפים או מוכרים עלולים להטעות אותו.
היה קול ההיגיון הקר, הספקני והאנליטי.

כללים נוקשים:
1. תמיד תענה בעברית רהוטה, עסקית, חדה וללא גינונים מיותרים.
2. ברירת מחדל: תשובה של שורה עד שתיים בלבד. קצר, חד, לעניין.
3. רק אם ההודעה מתחילה ב-# — הפעל "מצב ניתוח עמוק" ותן ניתוח מורחב.
4. אל תחזור על שאלת המשתמש. אל תוסיף מילות מחמאה. ישר לגוף העניין."""

MAX_TOOL_TURNS = 2  # חוק הצינון

# ─── Core Agent Loop ──────────────────────────────────────────────────────────
def run_agent(user_message: str, channel: str = "telegram") -> str:
    """
    לולאת הסוכן המרכזית עם הגנת תקציב קשיחה.
    channel: "whatsapp" | "telegram"
    """
    memory.add_user_message(user_message)
    messages = memory.get_messages()

    turn_count = 0
    response_text = "לא הצלחתי לעבד את הבקשה. נסה שוב."

    try:
        while turn_count < MAX_TOOL_TURNS:
            turn_count += 1
            logger.info(f"Agent turn {turn_count}/{MAX_TOOL_TURNS}")

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000 if channel == "telegram" else 400,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            # בדיקת סיבת עצירה
            stop_reason = response.stop_reason

            if stop_reason == "end_turn":
                # המודל סיים — חלץ טקסט
                response_text = _extract_text(response)
                break

            elif stop_reason == "tool_use":
                # עיבוד קריאות כלים
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

                # הוסף את תגובת המודל + תוצאות הכלים לשיחה
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]

            else:
                logger.warning(f"Unexpected stop_reason: {stop_reason}")
                break

        else:
            # חריגה מהמונה — קטיעת לולאה
            logger.warning("MAX_TOOL_TURNS reached — cutting loop to prevent cost leak.")
            response_text = "הגעתי למגבלת הסיבובים. אנא פרט את הבקשה ונסה שוב."

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        response_text = f"שגיאה פנימית: {e}"

    memory.add_assistant_message(response_text)
    return response_text


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


# ─── Webhook Endpoints המעודכנים ──────────────────────────────────────────────

# 1. נתיב הבית - פותר את ה-404 של UptimeRobot ו-Render Health
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "OK", 200

# 2. נתיב וואטסאפ - מותאם לפורמט של טוויליו (XML)
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook_twilio():
    from twilio.twiml.messaging_response import MessagingResponse
    user_message = request.values.get("Body", "").strip()
    sender = request.values.get("From", "unknown")
    if not user_message:
        return "OK", 200

    session = lead_sessions[sender]
    if session["state"].value != "done":
        reply = handle_lead_message(sender, user_message)
        if reply:
            resp = MessagingResponse()
            resp.message(reply)
            return Response(str(resp), mimetype="application/xml")

    reply = run_agent(user_message, channel="whatsapp")
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp), 200, {"Content-Type": "text/xml"}

# 3. נתיב טלגרם - מאובטח באמצעות משתנה סביבה ומקשיב דינמית לטוקן
@app.route(f"/{os.environ.get('TELEGRAM_TOKEN')}", methods=["POST"])
def telegram_webhook():
    print("🔥 Telegram hit", flush=True)
    data = request.json or {}
    
    message_obj = data.get("message", {})
    user_message = message_obj.get("text", "")
    chat_id = message_obj.get("chat", {}).get("id")

    if not user_message:
        return "OK", 200

    import requests
    token = os.environ.get('TELEGRAM_TOKEN')
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"

    if "קריאייטיב" in user_message:
        reply = handle_creative_command(user_message, chat_id)
        requests.post(telegram_url, json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        })
        return "OK", 200

    reply = run_agent(user_message, channel="telegram")
    requests.post(telegram_url, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "OK", 200


@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    """Endpoint לטריגר ידני / Cron Job ב-Render."""
    from worker import run_proactive_check
    result = run_proactive_check()
    return jsonify({"status": "ok", "result": result})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"})


# ─── Bootstrap ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    schedule_background_worker()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
