import json, os, time, threading
from datetime import datetime
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = "הטוקן שלך"
ANTHROPIC_API_KEY = "המפתח שלך"

DATA_FILE = "data.json"
conversations = {}

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tasks": [], "expenses": [], "chat_id": None}

def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ask_claude(uid, msg, data):
    if uid not in conversations:
        conversations[uid] = []
    open_tasks = [t for t in data['tasks'] if not t.get('done')]
    monthly = sum(e['amount'] for e in data['expenses']
                  if e.get('month') == datetime.now().strftime('%m/%Y'))
    conversations[uid].append({"role": "user", "content":
        f"תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"משימות פתוחות: {len(open_tasks)}\n"
        f"הוצאות החודש: {monthly}₪\n\n{msg}"})
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
            "max_tokens": 800,
            "system": "אתה עוזר עסקי אישי בשם מנהל. עונה תמיד בעברית, קצר וממוקד.",
            "messages": conversations[uid]
        },
        timeout=30
    )
    reply = response.json()["content"][0]["text"]
    conversations[uid].append({"role": "assistant", "content": reply})
    return reply

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    data['chat_id'] = update.effective_chat.id
    save(data)
    await update.message.reply_text(
        "👋 שלום! אני המנהל שלך.\n\n"
        "📋 /tasks – משימות\n"
        "➕ /add [משימה] – הוסף\n"
        "✅ /done [מספר] – סיים\n"
        "💰 /expense [סכום] [תיאור]\n"
        "📊 /summary – סיכום\n\n"
        "או כתוב לי חופשי! 💬"
    )

async def tasks_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    open_t = [t for t in data['tasks'] if not t.get('done')]
    if not open_t:
        await update.message.reply_text("✅ אין משימות פתוחות!")
        return
    text = "📋 משימות:\n\n"
    for i, t in enumerate(open_t, 1):
        text += f"{i}. {t['text']}\n"
    await update.message.reply_text(text)

async def add_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("כתוב: /add [משימה]")
        return
    data = load()
    task = ' '.join(ctx.args)
    data['tasks'].append({"text": task, "done": False,
                          "date": datetime.now().strftime('%d/%m/%Y')})
    save(data)
    await update.message.reply_text(f"✅ נוסף: {task}")

async def done_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("כתוב: /done [מספר]")
        return
    data = load()
    open_t = [t for t in data['tasks'] if not t.get('done')]
    try:
        t = open_t[int(ctx.args[0]) - 1]
        t['done'] = True
        save(data)
        await update.message.reply_text(f"🎉 הושלם: {t['text']}")
    except:
        await update.message.reply_text("מספר לא תקין")

async def expense_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("כתוב: /expense [סכום] [תיאור]")
        return
    try:
        amount = float(ctx.args[0])
        desc = ' '.join(ctx.args[1:])
        data = load()
        data['expenses'].append({"amount": amount, "description": desc,
            "date": datetime.now().strftime('%d/%m/%Y'),
            "month": datetime.now().strftime('%m/%Y')})
        save(data)
        monthly = sum(e['amount'] for e in data['expenses']
                      if e.get('month') == datetime.now().strftime('%m/%Y'))
        await update.message.reply_text(
            f"💸 {desc} – {amount:,.0f}₪\nסה\"כ החודש: {monthly:,.0f}₪")
    except:
        await update.message.reply_text("שגיאה")

async def summary_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    open_t = [t for t in data['tasks'] if not t.get('done')]
    monthly = sum(e['amount'] for e in data['expenses']
                  if e.get('month') == datetime.now().strftime('%m/%Y'))
    days = ['שני','שלישי','רביעי','חמישי','שישי','שבת','ראשון']
    day = days[datetime.now().weekday()]
    text = f"☀️ יום {day}, {datetime.now().strftime('%d/%m/%Y')}\n\n"
    if open_t:
        text += f"📋 {len(open_t)} משימות:\n"
        for t in open_t[:7]:
            text += f"• {t['text']}\n"
    else:
        text += "✅ אין משימות!\n"
    if monthly:
        text += f"\n💰 הוצאות החודש: {monthly:,.0f}₪"
    await update.message.reply_text(text)

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    try:
        reply = ask_claude(uid, update.message.text, data)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {str(e)}")

def main():
    print("🚀 הבוט פועל!")
    app = (Application.builder()
           .token(TELEGRAM_TOKEN)
           .base_url("https://149.154.166.110/bot{token}")
           .base_file_url("https://149.154.166.110/file/bot{token}")
           .build())
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("expense", expense_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
