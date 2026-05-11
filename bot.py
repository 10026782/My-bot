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

def ask_claude(uid, msg):
    if uid not in conversations:
        conversations[uid] = []
    
    try:
        data = load()
        open_tasks = len([t for t in data.get('tasks', []) if not t.get('done')])
        monthly = sum(e.get('amount', 0) for e in data.get('expenses', []) if e.get('month') == datetime.now().strftime('%m/%Y'))
    except Exception as e:
        print(f"Error loading data: {e}")
        open_tasks, monthly = 0, 0

    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
    user_content = f"תאריך: {timestamp}\nמשימות פתוחות: {open_tasks}\nהוצאות חודש: {monthly}\n\n{msg}"
    conversations[uid].append({"role": "user", "content": user_content})
    
    if len(conversations[uid]) > 20:
        conversations[uid] = conversations[uid][-20:]

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-sonnet-20240229",
                "max_tokens": 1024,
                "messages": conversations[uid]
            },
            timeout=30.0
        )
        result = response.json()
        if response.status_code != 200:
            print(f"Anthropic API Error: {result}")
            return f"שגיאת API: {result.get('error', {}).get('message', 'Unknown error')}"
        
        return result["content"][0]["text"]
    except Exception as e:
        print(f"System Error: {e}")
        return "חלה שגיאה פנימית בבוט."
def handle_command(text, uid):
    data = load()
    if text.startswith("/add "):
        task = text[5:]
        data['tasks'].append({"text": task, "done": False,
                               "date": datetime.now().strftime('%d/%m/%Y')})
        save(data)
        return f"✅ נוסף: {task}"
    elif text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        if not open_t:
            return "✅ אין משימות פתוחות!"
        return "📋 משימות:\n\n" + "".join(
            f"{i}. {t['text']}\n" for i, t in enumerate(open_t, 1))
    elif text.startswith("/done "):
        try:
            open_t = [t for t in data['tasks'] if not t.get('done')]
            t = open_t[int(text[6:]) - 1]
            t['done'] = True
            save(data)
            return f"🎉 הושלם: {t['text']}"
        except:
            return "מספר לא תקין"
    elif text.startswith("/expense "):
        parts = text[9:].split(" ", 1)
        try:
            amount = float(parts[0])
            desc = parts[1] if len(parts) > 1 else "הוצאה"
            data['expenses'].append({
                "amount": amount,
                "description": desc,
                "date": datetime.now().strftime('%d/%m/%Y'),
                "month": datetime.now().strftime('%m/%Y')
            })
            save(data)
            monthly = sum(e['amount'] for e in data['expenses']
                         if e.get('month') == datetime.now().strftime('%m/%Y'))
            return f"💸 {desc} - {amount:,.0f}₪\nסהכ החודש: {monthly:,.0f}₪"
        except:
            return "שגיאה. כתוב: /expense 500 תיאור"
    elif text == "/summary":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        monthly = sum(e['amount'] for e in data['expenses']
                     if e.get('month') == datetime.now().strftime('%m/%Y'))
        days = ['שני','שלישי','רביעי','חמישי','שישי','שבת','ראשון']
        day = days[datetime.now().weekday()]
        txt = f"☀️ יום {day}, {datetime.now().strftime('%d/%m/%Y')}\n\n"
        if open_t:
            txt += f"📋 {len(open_t)} משימות:\n"
            for t in open_t[:5]:
                txt += f"• {t['text']}\n"
        else:
            txt += "✅ אין משימות!\n"
        if monthly:
            txt += f"\n💰 הוצאות החודש: {monthly:,.0f}₪"
        return txt
    else:
        try:
            return ask_claude(uid, text)
        except Exception as e:
            return f"שגיאה: {str(e)}"

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
