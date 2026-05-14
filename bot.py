import os, json, threading, time
from datetime import datetime
from flask import Flask, request, Response
import httpx
from twilio.twiml.messaging_response import MessagingResponse

# משיכת מפתחות (לוודא שקיימים ב-Render!)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

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

def ask_claude(msg):
    try:
        print(f"DEBUG: פונה לקלוד...")
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-haiku-20240307", # מודל מהיר וזול יותר שמונע טיימאאוט
                "max_tokens": 400,
                "system": "אתה עוזר עסקי אישי בשם מנהל. עונה בעברית קצרה.",
                "messages": [{"role": "user", "content": msg}]
            },
            timeout=15.0
        )
        
        res_json = response.json()
        
        # בדיקה אם יש תוכן לפני שמנסים לקרוא אותו
        if "content" in res_json and len(res_json["content"]) > 0:
            return res_json["content"][0]["text"]
        else:
            print(f"שגיאת מבנה מקלוד: {res_json}")
            return "קיבלתי את ההודעה, אבל יש לי תקלה טכנית קלה בתשובה."
            
    except Exception as e:
        print(f"ERROR Claude: {str(e)}")
        return "מצטער, אני זמין רק לפקודות כמו /tasks כרגע."
def handle_command(text, uid):
    data = load()
    text = text.strip()
    
    if text.startswith("/add "):
        task = text[5:]
        data['tasks'].append({"text": task, "done": False, "date": datetime.now().strftime('%d/%m/%Y')})
        save(data)
        return f"✅ נוסף: {task}"
    
    if text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        if not open_t: return "✅ אין משימות פתוחות!"
        return "📋 משימות:\n" + "\n".join(f"{i}. {t['text']}" for i, t in enumerate(open_t, 1))

    # אם זו לא פקודה, שלח לקלוד
    return ask_claude(text)

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    print(f"DEBUG: הודעה מוואטסאפ ({sender}): {incoming}")
    
    reply = handle_command(incoming, sender)
    
    # תיקון שגיאת ה-Content: יצירת תגובה עם Content-Type נכון
    resp = MessagingResponse()
    resp.message(reply)
    return Response(str(resp), mimetype='application/xml')

@app.route("/")
def home():
    return "Bot is Live"

def telegram_polling():
    offset = 0
    print("--- Polling טלגרם התחיל ---")
    while True:
        try:
            # הוספת טיימאאוט קצר כדי לא לתקוע את ה-Thread
            r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", 
                          params={"offset": offset, "timeout": 20}, timeout=25)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    print(f"DEBUG: הודעה מטלגרם: {text}")
                    reply = handle_command(text, str(chat_id))
                    httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                               json={"chat_id": chat_id, "text": reply})
        except Exception as e:
            # מניעת קריסה של הלולאה
            time.sleep(5)

if __name__ == "__main__":
    # הרצת טלגרם ב-Thread נפרד
    threading.Thread(target=telegram_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
