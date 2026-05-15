import os, json, threading, time, httpx
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
KNOWLEDGE_FILE = "import_knowledge_base.json"
app = Flask(__name__)
def get_google_token():
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"), 
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN"), 
        "grant_type": "refresh_token"
    })
    return r.json().get("access_token")

def search_drive(query):
    try:
        token = get_google_token()
        r = httpx.get("https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": f"name contains '{query}' and trashed = false", "fields": "files(name, webViewLink)"})
        files = r.json().get("files", [])
        if not files: return f"חיפשתי בדרייב, אבל אין כלום על '{query}'. בטוח שזה השם?"
        res = f"מצאתי לך את זה בדרייב:\n"
        for f in files: res += f"• {f['name']}\n🔗 {f['webViewLink']}\n\n"
        return res
    except: return "משהו נתקע בחיבור לדרייב. תבדוק את ההרשאות."
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
def load_knowledge():
    """טוענת את לוחות הברית של העסק"""
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
                kb = json.load(f)
                rules = "\n".join([f"- {r['hebrew_name']}: {r['description']}" for r in kb.get('the_ten_commandments', [])])
                return rules
        except: pass
    return "אין לוחות ברית זמינים כרגע."
def ask_claude(msg, uid):
    data = load() # טעינת הנתונים והזיכרון
    
    # טעינת לוחות הברית מהקובץ שהעלינו לגיטהאב
    try:
        with open('import_knowledge_base.json', 'r', encoding='utf-8') as f:
            kb = json.load(f)
            rules = "\n".join([f"{r['hebrew_name']}: {r['description']}" for r in kb['the_ten_commandments']])
    except:
        rules = "חוקי הייבוא של אליהו חזן."

    if uid not in data.get('history', {}):
        if 'history' not in data: data['history'] = {}
        data['history'][uid] = []

    history = data['history'][uid]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=f"""אתה 'מנהל', העוזר האסטרטגי והחד של אליהו חזן. 
        האישיות שלך: יזם נדל"ן ממולח, חד, עם חוש הומור ענייני.
        עליך לפעול תמיד לפי 'לוחות הברית' האלו:
        {rules}
        
        יש לך גישה לדרייב (/find) וליומן (/cal). 
        אל תגיד שאתה לא זוכר! תשתמש בהיסטוריית השיחה המצורפת.""",
        messages=history + [{"role": "user", "content": msg}]
    )
    
    answer = response.content[0].text
    # שמירת הזיכרון
    data['history'][uid].append({"role": "user", "content": msg})
    data['history'][uid].append({"role": "assistant", "content": answer})
    data['history'][uid] = data['history'][uid][-10:] # זוכר 10 הודעות אחרונות
    save(data)
    return answer
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
