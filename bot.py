import os
import logging
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import anthropic
from twilio.twiml.messaging_response import MessagingResponse
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- הגדרות בסיס ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
app = Flask(__name__)

# משיכת מפתחות (Environment Variables ב-Render)
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CLAUDE_KEY = os.environ.get('ANTHROPIC_API_KEY')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID') # מזהה תיקיית הנדל"ן
client = anthropic.Anthropic(api_key=CLAUDE_KEY)

# שם המודל היציב ביותר (פותר את שגיאת ה-404)
CLAUDE_MODEL = "claude-3-5-sonnet-20240620"

# --- פונקציות גוגל דרייב (נדל"ן) ---
def get_drive_context():
    """שולף טקסט מתוך קבצי הנדל"ן בדרייב כדי לתת ל-Claude הקשר"""
    try:
        # דורש משתנה סביבה GOOGLE_CREDENTIALS שמכיל את תוכן קובץ ה-JSON
        import json
        creds_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
        creds = service_account.Credentials.from_service_account_info(creds_json)
        service = build('drive', 'v3', credentials=creds)
        
        # חיפוש קבצי טקסט/PDF בתיקייה
        results = service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name)").execute()
        items = results.get('files', [])
        
        context_text = "מידע נדל"ן רלוונטי:\n"
        for item in items[:3]: # לוקח את 3 הקבצים הראשונים כדוגמה
            context_text += f"- קובץ: {item['name']}\n"
        return context_text
    except Exception as e:
        logging.error(f"Drive Error: {e}")
        return "לא ניתן היה לגשת לנתוני הנדל"ן כרגע."

# --- לוגיקת בינה מלאכותית משותפת ---
def ask_claude(user_input):
    real_estate_data = get_drive_context()
    
    system_prompt = f"אתה סוכן עסקי חכם. הנה מידע מהדרייב שלך: {real_estate_data}"
    
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}]
    )
    return message.content[0].text

# --- חלק 1: WhatsApp (Flask) ---
@app.route('/')
def health_check():
    return "The Agent is Live!", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    user_msg = request.values.get('Body', '')
    bot_response = ask_claude(user_msg)
    
    msg = MessagingResponse()
    msg.message(bot_response)
    return str(msg)

# --- חלק 2: Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="שלום אלי, הסוכן העסקי המלא שלך מוכן.")

async def handle_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    bot_response = ask_claude(user_text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_response)

# הגדרת אפליקציית הטלגרם
telegram_app = ApplicationBuilder().token(TOKEN).build()
telegram_app.add_handler(CommandHandler('start', start))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_telegram))

# --- חלק 3: הרצה משולבת ---
if __name__ == '__main__':
    # הפעלת טלגרם בטרד נפרד כדי שלא יחסום את Flask
    threading.Thread(target=telegram_app.run_polling, daemon=True).start()
    
    # הרצת השרת (Render משתמש בפורט שמוגדר במערכת)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
