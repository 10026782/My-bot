import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import anthropic

# הגדרת לוגים כדי לראות מה קורה ב-Render
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# משיכת המפתחות מה-Environment Variables ב-Render
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CLAUDE_KEY = os.environ.get('ANTHROPIC_API_KEY')

client = anthropic.Anthropic(api_key=CLAUDE_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="שלום אלי! הסוכן העסקי שלך מוכן לפעולה. איך אני יכול לעזור?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # שליחת ההודעה ל-Claude
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        messages=[{"role": "user", "content": user_text}]
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response.content[0].text)

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(msg_handler)
    
    # שימוש ב-Polling פשוט (מתאים לשרת ב-Render)
    application.run_polling()
