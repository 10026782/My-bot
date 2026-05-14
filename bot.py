import os, json, threading, time
from datetime import datetime
from flask import Flask, request, Response
import httpx
import anthropic
from twilio.twiml.messaging_response import MessagingResponse

# מפתחות מ-Render Environment
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
DATA_FILE = "data.json"
app = Flask(__name__)

def load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"tasks": [], "expenses": [], "chat_id": None}

def save(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def check_calendar():
    if not GOOGLE_REFRESH_TOKEN: return "⚠️ יומן גוגל לא מוגדר."
    try:
        r = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN, "grant_type": "refresh_token"
        })
        access_token = r.json().get("access_token")
        cal_r = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": 3, "timeMin": datetime.utcnow().isoformat() + "Z"}
        )
        events = cal_r.json().get("items", [])
        res = "📅 אירועים קרובים:\n"
        for ev in events: res += f"• {ev.get('summary')}\n"
        return res if events else "📅 אין אירועים קרובים."
    except: return "❌ שגיאה ביומן."

def ask_claude(msg):
    try:
        # מעדכן לשם המודל המדויק מהצילום מסך שלך
        response = client.messages.create(
            model="claude-sonnet-4-6", 
            max_tokens=1024,
            system="אתה עוזר עסקי אישי בשם מנהל. עונה בעברית.",
            messages=[{"role": "user", "content": msg}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude Error: {e}")
        return f"שגיאה: {str(e)}"

def handle_command(text, uid):
    data = load()
    text = text.strip()
    if text == "/start": return "👋 שלום אליהו! המערכת מחוברת."
    if text == "/cal": return check_calendar()
    if text.startswith("/add "):
        task = text[5:]; data['tasks'].append({"text": task, "done": False}); save(data)
        return f"✅ נוסף: {task}"
    if text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        return "📋 משימות:\n" + "\n".join(f"- {t['text']}" for t in open_t) if open_t else "✅ אין משימות."
    return ask_claude(text)

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    reply = handle_command(incoming, sender)
    resp = MessagingResponse()
    resp.message(reply)
    return Response(str(resp), mimetype='application/xml')

@app.route("/")
def home(): return "Bot is Live with Sonnet 4-6"

def telegram_polling():
    offset = 0
    while True:
        try:
            r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", 
                          params={"offset": offset, "timeout": 20}, timeout=25)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    reply = handle_command(update["message"]["text"], str(chat_id))
                    httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                               json={"chat_id": chat_id, "text": reply})
        except: time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
