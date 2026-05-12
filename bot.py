import os, json, threading, time
from datetime import datetime
from flask import Flask, request
import httpx

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")

DATA_FILE = "data.json"
conversations = {}
app = Flask(__name__)

SYSTEM_PROMPT = """אתה עוזר עסקי אישי בשם מנהל.
עונה תמיד בעברית, קצר וממוקד.
עוזר בניהול משימות, הוצאות, קשרי לקוחות, ניסוח מודעות פרסום ותגובות ראשוניות ללקוחות."""

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tasks": [], "expenses": [], "chat_id": None}

def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def handle_command(text, uid):
    # פונקציה לניהול משימות והוצאות - רצה מקומית בשרת
    try:
        data = load()
        if "משימה" in text:
            task = text.replace("משימה", "").strip()
            if 'tasks' not in data: data['tasks'] = []
            data['tasks'].append({"text": task, "done": False, "date": datetime.now().strftime("%d/%m/%Y")})
            save(data)
            return f"רשמתי לעצמי: {task}"
        
        if "הוצאה" in text:
            import re
            amount = re.findall(r'\d+', text)
            if amount:
                amt = int(amount[0])
                desc = text.replace("הוצאה", "").replace(str(amt), "").strip()
                if 'expenses' not in data: data['expenses'] = []
                data['expenses'].append({
                    "amount": amt, 
                    "desc": desc, 
                    "month": datetime.now().strftime("%m/%Y"),
                    "date": datetime.now().strftime("%d/%m/%Y")
                })
                save(data)
                return f"רשמתי הוצאה: {amt} ש\"ח על {desc}"
    except Exception as e:
        print(f"Error in handle_command: {e}")
    return None

def ask_claude(uid, msg):
    # המספר האישי שלך לזיהוי "מנהל"
    MASTER_NUMBER = "972548347342"
    
    # 1. אם זה אתה - בודקים אם שלחת פקודת רישום (משימה/הוצאה)
    if uid == MASTER_NUMBER:
        cmd_response = handle_command(msg, uid)
        if cmd_response:
            return cmd_response

    # 2. ניהול זיכרון השיחה לכל משתמש
    if uid not in conversations:
        conversations[uid] = []
    
    # 3. שליפת נתונים עדכניים עבור המוח של הבוט
    try:
        data = load()
        open_tasks = len([t for t in data.get('tasks', []) if not t.get('done')])
        monthly = sum(e.get('amount', 0) for e in data.get('expenses', []) if e.get('month') == datetime.now().strftime('%m/%Y'))
    except:
        open_tasks, monthly = 0, 0

    # 4. הגדרת האישיות לפי מי ששולח את ההודעה
    if uid == MASTER_NUMBER:
        system_prompt = (
            "אתה 'הסוכן של אליהו'. עוזר אישי חכם שלומד מהנחיותיו של אליהו בזמן אמת. "
            "אליהו עוסק בנדל\"ן, ייבוא רהיטים ותשתיות תקשורת. "
            f"סטטוס: {open_tasks} משימות פתוחות, {monthly} ש\"ח הוצאות החודש."
        )
    else:
        system_prompt = (
            "אתה נציג המכירות המקצועי של אליהו חזן. ענה באדיבות ובאופן מכירתי. "
            "אל תחשוף נתונים פנימיים. פתח בברכת שלום בשם המשרד."
        )

    # 5. שליחת השאלה לקלוד (Sonnet 4.6)
    user_content = f"תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nהודעה: {msg}"
    messages_to_send = conversations[uid] + [{"role": "user", "content": user_content}]

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": messages_to_send
            },
            timeout=30.0
        )
        result = response.json()
        bot_response = result["content"][0]["text"]
        
        # שמירת השיחה בזיכרון (עד 15 הודעות)
        conversations[uid].append({"role": "user", "content": msg})
        conversations[uid].append({"role": "assistant", "content": bot_response})
        if len(conversations[uid]) > 15:
            conversations[uid] = conversations[uid][-15:]
            
        return bot_response
        
    except Exception as e:
        return f"שגיאה בתקשורת: {str(e)}"
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    from twilio.twiml.messaging_response import MessagingResponse
    incoming = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    
    reply = handle_command(incoming, sender)
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

@app.route("/")
def home():
    return "הבוט פועל!"

def send_telegram(chat_id, text):
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except:
        pass

def telegram_polling():
    offset = 0
    while True:
        try:
            r = httpx.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if chat_id and text:
                    data = load()
                    data['chat_id'] = chat_id
                    save(data)
                    reply = handle_command(text, str(chat_id))
                    send_telegram(chat_id, reply)
        except Exception as e:
            print(f"שגיאת טלגרם: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=telegram_polling, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
