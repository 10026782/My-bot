import os, json, threading, time, httpx, telebot
from datetime import datetime
from flask import Flask, request, Response, abort
import anthropic
from twilio.twiml.messaging_response import MessagingResponse

# 1. הגדרות מפתחות וקליינטים
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DATA_FILE = "data.json"
KNOWLEDGE_FILE = "import_knowledge_base.json"

# 2. הגדרת ה-app של Flask
app = Flask(__name__)

# 3. הגדרת ה-Webhook של טלגרם - רץ אוטומטית כשהשרת עולה!
RENDER_APP_URL = "https://my-bot-jqz2.onrender.com"
try:
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_APP_URL}/{TELEGRAM_TOKEN}")
    print("✅ טלגרם עבר למצב Webhook חסכוני ומדויק!", flush=True)
except Exception as e:
    print(f"❌ שגיאה בהגדרת ה-Webhook: {e}", flush=True)

# 4. נקודת הקצה (Webhook) של טלגרם לקבלת הודעות
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        if update.message and update.message.text:
            chat_id = str(update.message.chat.id)
            text = update.message.text
            reply = handle_command(text, chat_id)
            bot.send_message(chat_id, reply)
        return '', 200
    else:
        abort(403)
def get_google_token():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id, 
        "client_secret": client_secret,
        "refresh_token": refresh_token, 
        "grant_type": "refresh_token"
    })
    data = r.json()
    print("Google token response:", data, flush=True)
    return data.get("access_token")

def search_drive(query):
    try:
        token = get_google_token()
        if not token:
            return "❌ לא הצלחתי לקבל טוקן מגוגל. בדוק את ה-env variables."
        r = httpx.get("https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": f"name contains '{query}' and trashed = false", "fields": "files(name, webViewLink)"})
        print("Drive response:", r.status_code, r.text[:300])
        files = r.json().get("files", [])
        if not files: return f"חיפשתי בדרייב, אבל אין כלום על '{query}'. בטוח שזה השם?"
        res = "מצאתי לך את זה בדרייב:\n"
        for f in files: res += f"• {f['name']}\n🔗 {f['webViewLink']}\n\n"
        return res
    except Exception as e:
        return f"❌ שגיאה: {str(e)}"

def load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"tasks": [], "expenses": [], "history": {}}

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
    data = load()
    try:
        with open('import_knowledge_base.json', 'r', encoding='utf-8') as f:
            kb = json.load(f)
            rules = "\n".join([f"{r['hebrew_name']}: {r['description']}" for r in kb['the_ten_commandments']])
    except:
        rules = "חוקי הייבוא של אליהו חזן."

    try:
        with open('config.json', 'r', encoding='utf-8') as f_config:
            config = json.load(f_config)
    except:
        config = {
            "bot_settings": {"model_name": "claude-sonnet-4-6", "memory_length": 5, "max_tokens_default": 50, "max_tokens_research": 1024},
            "system_prompt": "אתה עוזר אסטרטגי חד."
        }

    if uid not in data.get('history', {}):
        if 'history' not in data: data['history'] = {}
        data['history'][uid] = []

    history = data['history'][uid]

    memory_limit = config["bot_settings"]["memory_length"]
    if len(history) > (memory_limit * 2):
        history = history[-(memory_limit * 2):]

    if msg.startswith('#'):
        clean_msg = msg[1:].strip()
        max_tokens_to_send = config["bot_settings"]["max_tokens_research"]
        current_system = f"{config['system_prompt']}\n{rules}\nמצב מחקר פעיל: נתח לעומק וענה בהרחבה."
    else:
        clean_msg = msg
        max_tokens_to_send = config["bot_settings"]["max_tokens_default"]
        current_system = f"{config['system_prompt']}\n{rules}\nמצב שוטף: ענה בשורה אחת קצרה וממוקדת בלבד."

    response = client.messages.create(
        model=config["bot_settings"]["model_name"],
        max_tokens=max_tokens_to_send,
        system=current_system,
        messages=history + [{"role": "user", "content": clean_msg}]
    )

    answer = response.content[0].text

    data['history'][uid].append({"role": "user", "content": msg})
    data['history'][uid].append({"role": "assistant", "content": answer})
    save(data)

    return answer

def handle_command(text, uid):
    data = load()
    text = text.strip()
    
    if text.lower().startswith("/find ") or text.lower().startswith("find "):
        query = text[6:] if text.startswith("/") else text[5:]
        return search_drive(query)
    
    if text.startswith("/add "):
        task = text[5:]
        data['tasks'].append({"text": task, "done": False, "date": datetime.now().strftime('%d/%m/%Y')})
        save(data)
        return f"✅ נוסף למשימות: {task}"
    
    if text == "/tasks":
        open_t = [t for t in data['tasks'] if not t.get('done')]
        if not open_t: return "✅ אין משימות פתוחות!"
        return "📋 משימות פתוחות:\n" + "\n".join(f"{i}. {t['text']}" for i, t in enumerate(open_t, 1))

    return ask_claude(text, uid)

# 5. ראוטים נוספים ל-Flask
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

