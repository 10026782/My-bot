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
def read_drive_file(file_name):
    """קריאת תוכן של קובץ טקסט או גוגל דוקס מתוך הדרייב והמרתו לטקסט נקי"""
    try:
        token = get_google_token()
        if not token:
            print("❌ חסר טוקן לקריאת קובץ", flush=True)
            return None
            
        headers = {"Authorization": f"Bearer {token}"}
        search_params = {"q": f"name contains '{file_name}' and trashed = false", "fields": "files(id, name, mimeType)"}
        r = httpx.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=search_params)
        files = r.json().get("files", [])
        
        if not files:
            return None
            
        file_id = files[0]['id']
        mime_type = files[0].get('mimeType', '')
        
        if "apps.document" in mime_type:  # Google Doc
            export_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            r_content = httpx.get(export_url, headers=headers, params={"mimeType": "text/plain"})
            return r_content.text
        else:  # קובץ טקסט רגיל
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            r_content = httpx.get(download_url, headers=headers, params={"alt": "media"})
            return r_content.text
    except Exception as e:
        print(f"❌ שגיאה בקריאת קובץ: {e}", flush=True)
        return None

def create_calendar_event(summary, start_time, duration_minutes=60):
    """קביעת פגישה חדשה ביומן גוגל (Google Calendar)"""
    try:
        token = get_google_token()
        if not token: 
            return "❌ חסר טוקן לחיבור ליומן. אנא בצע חיבור מחדש."
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        from datetime import datetime, timedelta
        
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        event_data = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Jerusalem"}
        }
        
        r = httpx.post("https://www.googleapis.com/calendar/v3/calendars/primary/events", headers=headers, json=event_data)
        if r.status_code in [200, 201]:
            return f"✅ הפגישה '{summary}' נקבעה בהצלחה ביומן!"
        return f"❌ שגיאה מקלנדר: {r.text}"
    except Exception as e:
        return f"❌ שגיאה בקביעת פגישה: {str(e)}"

def send_gmail(to_email, subject, body_text):
    """שליחת אימייל מהיר דרך חשבון ה-Gmail שלך"""
    try:
        token = get_google_token()
        if not token: 
            return "❌ חסר טוקן לשליחת מייל."
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body_text)
        message['to'] = to_email
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        r = httpx.post("https://www.googleapis.com/gmail/v1/users/me/messages/send", headers=headers, json={"raw": raw_message})
        if r.status_code == 200:
            return f"📧 המייל ל-{to_email} נשלח בהצלחה!"
        return f"❌ שגיאה בשליחת מייל: {r.text}"
    except Exception as e:
        return f"❌ שגיאה במערכת המייל: {str(e)}"

def read_latest_emails(max_results=5):
    """קריאת תקצירי האימיילים האחרונים מתיבת ה-Gmail שלך"""
    try:
        token = get_google_token()
        if not token: 
            return "❌ חסר טוקן לקריאת מיילים."
        
        headers = {"Authorization": f"Bearer {token}"}
        r = httpx.get("https://www.googleapis.com/gmail/v1/users/me/messages", headers=headers, params={"maxResults": max_results})
        messages = r.json().get("messages", [])
        
        if not messages: 
            return "📬 אין מיילים חדשים בתיבה."
        
        summary = "📬 המיילים האחרונים שקיבלת:\n"
        for msg in messages:
            msg_info = httpx.get(f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}", headers=headers).json()
            snippet = msg_info.get("snippet", "")
            summary += f"- {snippet}\n"
        return summary
    except Exception as e:
        return f"❌ שגיאה בקריאת מיילים: {str(e)}"

def append_to_sheet(spreadsheet_name, row_data_list):
    """הוספת שורת נתונים (הערות, משקל, מדדי בריאות) לקובץ גוגל שיטס קיים"""
    try:
        token = get_google_token()
        if not token: 
            return "❌ חסר טוקן לחיבור לגוגל שיטס."
        
        headers = {"Authorization": f"Bearer {token}"}
        search_params = {"q": f"name = '{spreadsheet_name}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"}
        r_search = httpx.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=search_params)
        files = r_search.json().get("files", [])
        
        if not files: 
            return f"❌ לא מצאתי בדרייב קובץ גוגל שיטס בשם '{spreadsheet_name}'."
        spreadsheet_id = files[0]['id']
        
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/A1:append"
        body = {"range": "A1", "majorDimension": "ROWS", "values": [row_data_list]}
        r_append = httpx.post(url, headers=headers, params={"valueInputOption": "USER_ENTERED"}, json=body)
        
        if r_append.status_code == 200:
            return f"📊 הנתונים נרשמו בהצלחה בטבלה '{spreadsheet_name}'!"
        return f"❌ שגיאה ברישום לשיטס: {r_append.text}"
    except Exception as e:
        return f"❌ שגיאה במערכת גוגל שיטס: {str(e)}"
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
def handle_command(user_text, chat_id):
    """המוח המרכזי של הבוט - מנתח את כוונת המשתמש, מפעיל כלים, ומשמש כשותף המזהיר"""
    try:
        # 1. הגדרת האישיות של הבוט כשותף המזהיר והשקול (האיפכא מסתברא)
        system_instruction = (
            "You are 'The Boss Bot' - an elite business strategist, real estate expert, and international trade advisor. "
            "Your absolute primary mandate is to act as the 'Devil's Advocate' (איפכא מסתברא) and the cautious, protective partner. "
            "The user and his business partner are naturally optimistic and visionary; they see the upside. Your job is to look for "
            "the downside, the risks, what can go wrong, where they might be naive, and where the seller or partner might be misleading them. "
            "Be the voice of reason, cold logic, and critical thinking. Stand at the gate and protect their capital. "
            "Always respond in fluent, professional, and sharp Hebrew.\n\n"
            "If the user asks to perform an action (like searching/reading Google Drive, checking Gmail, updating Google Sheets, "
            "creating calendar events, or managing Airtable), reply by starting your message with a special JSON command block "
            "wrapped in [TOOL_CALL] ... [/TOOL_CALL] so the system can execute it, then provide your critical business feedback below it."
        )

        # 2. שליחת ההודעה לקלוד לקבלת ניתוח והחלטה על כלים
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            temperature=0.5,
            system=system_instruction,
            messages=[{"role": "user", "content": user_text}]
        )
        
        reply = message.content[0].text
        context_data = ""

        # 3. מנגנון זיהוי והפעלת כלים אוטומטי (Intent Detection)
        if "[TOOL_CALL]" in reply:
            try:
                # חילוץ הפקודה מתוך תגובות ה-JSON של קלוד
                start_idx = reply.find("[TOOL_CALL]") + len("[TOOL_CALL]")
                end_idx = reply.find("[/TOOL_CALL]")
                import json
                tool_json = json.loads(reply[start_idx:end_idx].strip())
                clean_reply = reply[end_idx + len("[/TOOL_CALL]"):].strip()
                
                action = tool_json.get("action")
                
                # הפעלת הכלי הנכון לפי החלטת קלוד (בלי שהמשתמש יצטרך פקודה מפורשת)
                if action == "search_drive":
                    context_data = search_drive(tool_json.get("query"))
                elif action == "read_file":
                    file_content = read_drive_file(tool_json.get("file_name"))
                    context_data = f"\n[תוכן הקובץ שנשלף מהדרייב]:\n{file_content}" if file_content else "❌ הקובץ לא נמצא או ריק."
                elif action == "create_calendar":
                    context_data = create_calendar_event(tool_json.get("summary"), tool_json.get("start_time"))
                elif action == "send_email":
                    context_data = send_gmail(tool_json.get("to"), tool_json.get("subject"), tool_json.get("body"))
                elif action == "read_emails":
                    context_data = read_latest_emails()
                elif action == "append_sheet":
                    context_data = append_to_sheet(tool_json.get("sheet_name"), tool_json.get("row_data"))
                elif action == "airtable_update":
                    # כאן נחבר את פונקציית האיירטאבל שנוסיף מיד
                    context_data = "📊 פקודת איירטאבל התקבלה במערכת!"
                
                # אם נשלף מידע מהכלים, קלוד מעבד אותו ומנסח את התשובה הסופית והמזהירה
                if context_data:
                    final_message = client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1500,
                        system=system_instruction,
                        messages=[
                            {"role": "user", "content": user_text},
                            {"role": "assistant", "content": reply},
                            {"role": "user", "content": f"[תוצאת המערכת]: {context_data}\nכעת ענה למשתמש על בסיס נתונים אלו כשותף המזהיר שלו."}
                        ]
                    )
                    return final_message.content[0].text
                return clean_reply
                
            except Exception as tool_err:
                print(f"Error executing tool: {tool_err}", flush=True)

        return reply
    except Exception as e:
        return f"❌ שגיאה בעיבוד ההודעה: {str(e)}"
def home():
    return "The Boss is Live"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

