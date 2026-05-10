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
    data = load()
    open_tasks = len([t for t in data['tasks'] if not t.get('done')])
    monthly = sum(e['amount'] for e in data['expenses']
                  if e.get('month') == datetime.now().strftime('%m/%Y'))
    conversations[uid].append({
        "role": "user",
        "content": f"תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')}\nמשימות: {open_tasks}\nהוצאות: {monthly}\n\n{msg}"
    })
    if len(conversations[uid]) > 20:
        conversations[uid] = conversations[uid][-20:]
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "system": SYSTEM_PROMPT,
            "messages": conversations[uid]
        },
        timeout=30
    )
    reply = response.json()["content"][0]["text"]
    conversations[uid].append({"role": "assistant", "content": reply})
    return reply

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
            for t in ope
