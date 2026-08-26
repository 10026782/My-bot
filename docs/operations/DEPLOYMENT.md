# BOSS Bot — DEPLOYMENT
**מדריך פריסה מעשי. עודכן: 26/08/2026**
פרטי הסביבה והדגלים נמצאים ב-`.env.example`; בדיקת schema ידנית מתועדת
ב-`tools/check_airtable_schema_runtime.py`.

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
python3 -m pip install -r requirements.txt

# 3. ENV
cp .env.example .env
# מלא את הערכים הנדרשים לפי ההערות ב-.env.example

# 4. רישום Telegram Webhook — פעם אחת בלבד
SETUP_WEBHOOK=1 python3 app.py
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
| Pre-Deploy Command | `python3 -m core.predeploy` |
| Python Version | 3.11 |
| Auto-Deploy | Yes (main branch) |
| Health Check Path | `/health` |

**Pre-Deploy Command:** `core/predeploy.py` runs PostgreSQL migrations (`core/database_migrations.py::run_migrations()`, Phase 4B0.1A atomic coordination if `FEATURE_ATOMIC_CLAIMS=true`) and, only if those succeed, the Emergency Stop preflight (`core/emergency_stop_preflight.py`). Blocks deploy if either stage fails. Idempotent — safe to run repeatedly on each deploy. See `docs/PHASE_4B0_1C_STAGING_WIRING.md` for more details.

**Environment Variables:** הוסף את המשתנים מ-`.env.example` ב-Render Dashboard → Environment. For atomic claims (staging only), also set:
```
FEATURE_ATOMIC_CLAIMS=true
DATABASE_URL=postgresql://...  # Or individual DATABASE_HOST, DATABASE_PORT, etc.
```

---

## Vercel (TMA Frontend)

```bash
# פריסה ידנית
cd tma-frontend/
vercel --prod

# או: Auto-deploy מ-GitHub (מומלץ)
# Vercel Dashboard → Git Integration → main branch
```

**Environment Variables ב-Vercel:**
```
VITE_API_URL=https://my-bot-jqz2.onrender.com
VITE_DEV_TELEGRAM_ID=7228089151  # local development only; do not use as production auth
```

---

## Feature Flags — מה פועל בפרודקשן

ברירת מחדל: **כבוי** לכולם, אלא אם צוין אחרת ב-`feature_flags.py`.
השתמש בשמות הדגלים המדויקים הבאים; אין שמות חלופיים לדגלי domain או lead:

```bash
LEAD_CAPTURE=true               # WhatsApp lead capture
```

**לא להדליק בלי בדיקה מפורשת:**
```bash
LEAD_SCORING=false
LEAD_MEMORY=false
FOLLOWUP_AUTOMATION=false
```

---

## בדיקת בריאות מלאה לאחר פריסה

```bash
# 1. HTTP health
curl https://my-bot-jqz2.onrender.com/health

# 2. Python syntax and on-demand Airtable schema diagnostic
python3 -m py_compile app.py
python3 tools/check_airtable_schema_runtime.py --dry-run

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
| TMA לא טוען | CORS או VITE_API_URL שגוי | בדוק `VITE_API_URL` ב-Vercel ואת `TMA_ALLOWED_ORIGINS` ב-Render env |
