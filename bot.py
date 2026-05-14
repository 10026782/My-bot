import os, json, threading, time
from datetime import datetime
from flask import Flask, request
import httpx
from twilio.twiml.messaging_response import MessagingResponse

# משיכת מפתחות ממשתני סביבה (ללא גרשיים בקוד!)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

DATA_FILE = "data.json"
conversations = {}
app = Flask(__name__)

def load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"tasks": [], "expenses": [], "chat_id": None}

def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ask_claude(uid, msg):
    if uid not in conversations:
        conversations[uid] = []
    data = load()
    open_tasks = [t for t in data['tasks'] if not t.get('done')]
    
    conversations[uid].append({
        "role": "user", 
        "content": f"תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')}\nמשימות פתוחות: {len(open_tasks)}\n\n{msg}"
    })
    
    if len(conversations[uid]) > 15: conversations[uid] = conversations[uid][-15:]

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 800,
                "system": "אתה עוזר עסקי אישי בשם מנהל. עונה בעברית ממוקדת. עוזר במשימות והוצאות.",
                "messages": conversations[uid]
            },
            timeout=30
        )
        return response.json()["content"][0]["text"]
    except Exception as e:
        return f"שגיאה: {e}"

def check_calendar():
    if not GOOGLE_REFRESH_TOKEN: return "יומן גוגל לא מוגדר."
    try:
        r = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        })
        access_token = r.json().get("access_token")
        cal_r = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": 3, "timeMin": datetime.utcnow().isoformat() + "Z"}
        )
        events = cal_r.json().get("items", [])
        if not events: return "אין אירועים קרובים."
        res = "📅 יומן:\n"
        for ev in events:
            res += f"• {ev.get('summary')} ({ev.get('start').get('dateTime', ev.get('start').get('date'))[:10]})\n"
        return res
    except: return "שגיאה בסנכרון היומן."

def handle_command(text, uid):
    data = load()
    text = text.strip()

    if text == "/start":
        return "👋 שלום אליהו! אני המנהל שלך.\nנסה את /tasks, /cal או /summary"
    
    if text == "/cal":
        return check_calendar()

    if text.startswith("/add "):
        task = text[5:]
        data['tasks'].append({"text": task, "done": False, "date": datetime.now().strftime('%d/%m/%Y')})
        save(data)
        return f"✅ נוסף: {task}"

    if text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        if not open_t: return "✅ אין משימות פתוחות!"
        return "📋 משימות:\n" + "\n".join(f"{i}. {t['text']}" for i, t in enumerate(open_t, 1))

    if text == "/summary":
        return f"☀️ סיכום:\n{check_calendar()}\n\nמשימות פתוחות: {len([t for t in data['tasks'] if not t.get('done')])}"

    return ask_claude(uid, text)

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    try:
        incoming = request.values.get("Body", "").strip()
        sender = request.values.get("From", "")
        reply = handle_command(incoming, sender)
        resp = MessagingResponse()
        resp.message(reply)
        return str(resp)
    except:
        return str(MessagingResponse().message("שגיאת תוכן בוואטסאפ."))

@app.route("/")
def home(): return "הבוט של אליהו חי ב-Render!"

def telegram_polling():
    offset = 0
    print("--- Polling טלגרם התחיל ---")
    while True:
        try:
            r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", 
                          params={"offset": offset, "timeout": 30}, timeout=35)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if msg.get("text"):
                    chat_id = msg["chat"]["id"]
                    reply = handle_command(msg["text"], str(chat_id))
                    httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                               json={"chat_id": chat_id, "text": reply})
        except: 
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
