# BOSS Bot — DEPLOYMENT
**מדריך פריסה מעשי. עודכן: 16/06/2026**
תלוי ב-SETUP.md לפרטי env vars ו-Airtable schema.

---

## ארכיטקטורת הפריסה

```
GitHub (main)
    │
    ▼
Render (Backend — Python/Flask)        Vercel (Frontend — TMA)
https://my-bot-jqz2.onrender.com       https://[tma].vercel.app
    │
    ├── /telegram  ← Telegram webhook
    ├── /whatsapp  ← Twilio WhatsApp webhook
    ├── /voice     ← Twilio Voice webhook
    ├── /api/*     ← TMA API endpoints
    └── /health    ← בדיקת חיות (public endpoint, returns limited status)
```

---

## פריסה רגילה — Render

### 1. Push ל-main
```bash
git push origin main
```

### 2. אמת deploy בפועל
```bash
# בדוק commit hash ב-Render Dashboard → Events
# השווה ל:
git ls-remote origin main
# אם שונה — Render עדיין על commit ישן, המתן או trigger manual deploy
```

### 3. בדוק חיות
```bash
curl https://my-bot-jqz2.onrender.com/health
# צפוי: {"status": "ok", "version": "..."}
```

### 4. שלח בדיקת smoke מטלגרם
```
שלום          ← בדיקת router
דוח בוקר     ← בדיקת Airtable + Digest
```

---

## פריסה ראשונה / סביבה חדשה

```bash
# 1. Clone
git clone https://github.com/10026782/My-bot.git
cd My-bot

# 2. Dependencies
pip install -r requirements.txt

# 3. ENV
cp env_example.txt .env
# מלא את כל הערכים (ראה SETUP.md)

# 4. רישום Telegram Webhook — פעם אחת בלבד
SETUP_WEBHOOK=1 python app.py
# לאחר רישום, הסר SETUP_WEBHOOK מה-env

# 5. רישום Twilio Webhooks — ידני
# Render URL → Twilio Console:
# WhatsApp: https://my-bot-jqz2.onrender.com/whatsapp
# Voice:    https://my-bot-jqz2.onrender.com/voice/incoming
```

---

## Render — הגדרות נדרשות

| הגדרה | ערך |
|-------|-----|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Python Version | 3.11 |
| Auto-Deploy | Yes (main branch) |
| Health Check Path | `/health` |

**Environment Variables:** הוסף את כל המשתנים מ-SETUP.md ב-Render Dashboard → Environment.

---

## Vercel (TMA Frontend)

```bash
# פריסה ידנית
cd tma/
vercel --prod

# או: Auto-deploy מ-GitHub (מומלץ)
# Vercel Dashboard → Git Integration → main branch
```

**Environment Variables ב-Vercel:**
```
NEXT_PUBLIC_API_URL=https://my-bot-jqz2.onrender.com
NEXT_PUBLIC_BOT_USERNAME=@YourBotUsername
```

---

## Feature Flags — מה פועל בפרודקשן

ברירת מחדל: **כבוי** לכולם חוץ מאלה:

```bash
FEATURE_DOMAIN_PROMPTS=true
FEATURE_DOMAIN_ROUTING=true
FEATURE_ANTI_HALLUCINATION=true
FEATURE_ACTION_VALIDATOR=true
FEATURE_LEAD_CAPTURE=true       # W0 — WhatsApp lead capture
```

**לא להדליק בלי בדיקה מפורשת:**
```bash
FEATURE_LEAD_SCORING=false
FEATURE_LEAD_MEMORY=false
FEATURE_FOLLOWUP_AUTOMATION=false
FEATURE_AUTO_REPLY=false
```

---

## בדיקת בריאות מלאה לאחר פריסה

```bash
# 1. HTTP health
curl https://my-bot-jqz2.onrender.com/health

# 2. Python imports
python -c "from feature_flags import is_enabled; print('flags OK')"
python -c "from airtable_tools import airtable_schema_diff; print('airtable OK')"

# 3. Airtable connectivity (מטלגרם)
# שלח: "בדיקת מערכת"

# 4. Cost Watchdog
# בדוק AI_Usage_Daily ב-Airtable — שורה של היום קיימת
```

---

## Rollback

```bash
# זיהוי commit תקין אחרון
git log --oneline -10

# Revert
git revert HEAD
git push origin main

# או: Render Dashboard → Events → בחר deploy קודם → "Redeploy"
```

---

## בעיות ידועות בפריסה

| בעיה | סיבה | פתרון |
|------|------|--------|
| Render על commit ישן | `git log origin/main` מהקאש המקומי | השווה ל-`git ls-remote origin main` |
| 403 מ-Airtable | Base ID שגוי או שם טבלה לא מדויק | בדוק `AIRTABLE_BASE_ID` ושמות טבלאות עם עברית מלאה |
| Webhook לא מגיע | Twilio URL לא מעודכן | עדכן ב-Twilio Console ידנית |
| TMA לא טוען | CORS או NEXT_PUBLIC_API_URL שגוי | בדוק TMA_ALLOWED_ORIGINS ב-Render env |
