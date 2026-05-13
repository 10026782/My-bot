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
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"




    
# --- לוגיקת בינה מלאכותית משותפת ---
def ask_claude(user_input):
    # מחק או שים # בתחילת השורה הזו:
    # real_estate_data = get_drive_context() 

    # שנה את בניית ההודעה כך שלא תכלול את הנתונים מהדרייב:
    full_prompt = f"הודעת משתמש: {user_input}"
    
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": full_prompt}]
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
