import os, json, threading, time
from datetime import datetime
from flask import Flask, request, Response
import anthropic # שימוש בספריה הרשמית כפי שמופיע בקוד שלך
from twilio.twiml.messaging_response import MessagingResponse

# הגדרות מפתחות
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# יצירת קליינט של אנתרופיק
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DATA_FILE = "data.json"
app = Flask(__name__)

def load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"tasks": [], "expenses": []}

def save(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def ask_claude(msg):
    try:
        # המודל המדויק שביקשת לא לגעת בו לעולם
        response = client.messages.create(
            model="claude-sonnet-4-6", 
            max_tokens=1024,
            system="אתה עוזר עסקי אישי בשם מנהל. עונה בעברית.",
            messages=[{"role": "user", "content": msg}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"DEBUG Error: {e}")
        return "מצטער, יש לי עיכוב קטן בתשובה. נסה שוב בעוד רגע."

def handle_command(text, uid):
    data = load()
    text = text.strip()
    
    if text.startswith("/add "):
        task = text[5:]
        data['tasks'].append({"text": task, "done": False, "date": datetime.now().strftime('%d/%m/%Y')})
        save(data)
        return f"✅ נוסף למשימות: {task}"
    
    if text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        if not open_t: return "✅ אין משימות פתוחות!"
        return "📋 משימות פתוחות:\n" + "\n".join(f"{i}. {t['text']}" for i, t in enumerate(open_t, 1))

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
def home():
    return "The Boss is Live"

def telegram_polling():
    import httpx
    offset = 0
    print("--- Polling טלגרם התחיל (מודל 4-6) ---")
    while True:
        try:
            r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", 
                          params={"offset": offset, "timeout": 20}, timeout=25)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    reply = handle_command(text, str(chat_id))
                    httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                               json={"chat_id": chat_id, "text": reply})
        except:
            time.sleep(5)

# הפעלת טלגרם ברקע לפני הרצת השרת
t = threading.Thread(target=telegram_polling, daemon=True)
t.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
