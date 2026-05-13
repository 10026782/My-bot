import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import anthropic
from twilio.twiml.messaging_response import MessagingResponse

# --- הגדרות בסיס ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
app = Flask(__name__) # ה-'app' שגוניקורן מחפש

# משיכת מפתחות מה-Environment Variables ב-Render
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CLAUDE_KEY = os.environ.get('ANTHROPIC_API_KEY')
client = anthropic.Anthropic(api_key=CLAUDE_KEY)

# --- חלק 1: שרת Flask (עבור Render ו-WhatsApp) ---

@app.route('/')
def health_check():
    return "Bot is running", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    user_msg = request.values.get('Body', '')
    
    # שליחת הודעה ל-Claude
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": user_msg}]
    )
    
    msg = MessagingResponse()
    msg.message(response.content[0].text)
    return str(msg)

# --- חלק 2: לוגיקת טלגרם (הגרסה המקורית) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="שלום אלי! הסוכן העסקי שלך בטלגרם ובווטסאפ מוכן לפעולה."
    )

async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # שליחת הודעה ל-Claude
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": user_text}]
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response.content[0].text)

# הגדרת אפליקציית הטלגרם
telegram_app = ApplicationBuilder().token(TOKEN).build()
telegram_app.add_handler(CommandHandler('start', start))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_telegram_message))

# --- חלק 3: הרצה ---

if __name__ == '__main__':
    # הרצה מקומית (לצורך בדיקות)
    import threading
    
    # הפעלת הטלגרם בטרד נפרד
    threading.Thread(target=telegram_app.run_polling).start()
    
    # הפעלת ה-Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
