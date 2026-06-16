# BOSS Bot — RUNBOOK
**תגובה לאירועים. עודכן: 16/06/2026**
לא לקרוא מקדימה — לפתוח כשיש בעיה.

---

## אבחון מהיר — 60 שניות

```bash
# 1. האם Render בכלל רץ?
curl https://my-bot-jqz2.onrender.com/health

# 2. מה ה-commit הפעיל?
# Render Dashboard → Events → ראה commit hash

# 3. בדוק Render logs
# Render Dashboard → Logs → סנן ל-"ERROR"
```

---

## תרחיש 1 — הבוט לא עונה בטלגרם

**בדיקה:**
```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
# בדוק: "url" מצביע ל-Render? "last_error_message" ריק?
```

**פתרונות לפי סדר:**

1. **Render ישן (sleep)** — שלח בקשה ל-`/health`, המתן 30 שניות, נסה שוב
2. **Webhook לא רשום** — הרץ `SETUP_WEBHOOK=1` מחדש
3. **Token שגוי** — בדוק `TELEGRAM_TOKEN` ב-Render Environment
4. **קוד קרס** — בדוק Render Logs, חפש `Exception` או `ImportError`

---

## תרחיש 2 — WhatsApp לא מקבל הודעות

**בדיקה:**
```bash
# בדוק Twilio Console → Monitor → Errors
# בדוק webhook URL ב-Twilio Console → WhatsApp Senders
```

**פתרונות:**

1. **Webhook URL שגוי** — עדכן ל-`https://my-bot-jqz2.onrender.com/whatsapp`
2. **HMAC validation נכשל** — בדוק `TWILIO_AUTH_TOKEN` ב-Render
3. **הודעה מספר לא מזוהה** — number לא ב-`IDENTITY_MAP` → מטופל כ-lead (תקין)
4. **Meta WhatsApp לא מחובר** — ראה F-items ב-ROADMAP (עדיין לא מומש)

---

## תרחיש 3 — שגיאות Airtable (422 / 403)

**422 — שלוש סיבות אפשריות:**

| קוד שגיאה | סיבה | פתרון |
|-----------|------|--------|
| INVALID_MULTIPLE_CHOICE_OPTIONS | ערך select עם רווח/גרשיים | בדוק `_clean_select_value()` ב-airtable_gateway.py |
| UNKNOWN_FIELD_NAME | שם עמודה לא תואם case-sensitive | בדוק שמות בדיוק ב-Airtable UI |
| Formula field in write | שדה `tier` או formula אחר ב-payload | הסר שדות formula מה-write payload |

**403:**
- לא תמיד permissions — בדוק גם: Base ID שגוי, שם טבלה שגוי (עברית עם סוגריים!)
- דוגמה נכונה: `"משימות (Tasks)"` לא `"משימות"`

```bash
# בדיקת connectivity
python diagnose_airtable.py
```

---

## תרחיש 4 — TMA לא נטען / שגיאות API

**בדיקה:**
```bash
# בדוק CORS
curl -H "Origin: https://[tma].vercel.app" \
     https://my-bot-jqz2.onrender.com/api/health

# צפוי: Access-Control-Allow-Origin header
```

**פתרונות:**
1. **CORS חסום** — הוסף את URL של Vercel ל-`TMA_ALLOWED_ORIGINS` ב-Render env
2. **401 Unauthorized** — Telegram initData לא תקין, בדוק TMA auth flow
3. **endpoint לא קיים** — בדוק `scan_ghost_buttons.py` — ייתכן endpoint שנמחק

---

## תרחיש 5 — Cost Watchdog התרעה

**מה זה אומר:** עלות AI עברה את הסף היומי.

**בדיקה:**
```bash
# בדוק AI_Usage_Daily ב-Airtable
# איזה מודול צורך הכי הרבה? (cost_watchdog.py → AI_Usage_Daily)
```

**פתרונות לפי סדר:**
1. בדוק אם יש loop — הודעה שמפעילה Sonnet במקום Haiku
2. בדוק `FEATURE_LEAD_SCORING` — אם פועל, יכול לירות הרבה calls
3. שינוי זמני: הורד מודל מ-Sonnet ל-Haiku ב-config.py

---

## תרחיש 6 — Render deploy תקוע / commit ישן

```bash
# בדוק מה בפועל פרוס
# Render Dashboard → Events → commit hash

# השווה ל-GitHub
git ls-remote origin main
# (לא git log origin/main — יכול להיות stale)

# אם שונה:
# Render Dashboard → Manual Deploy → Deploy latest commit
```

---

## Emergency Stop

אם הבוט שולח הודעות לא רצויות ללקוחות:

```bash
# 1. ב-Render: Suspend Service (Dashboard → Settings → Suspend)
# 2. ב-Twilio: Disable webhook (Console → WhatsApp → remove webhook URL)
# 3. ב-Telegram: getUpdates עדיין יעבוד אבל לא יהיה מענה

# לאחר תיקון: Resume Service + Restore webhooks
```

---

## לוגים שימושיים

```bash
# Render Logs — סינון שגיאות
# Dashboard → Logs → חפש: ERROR | Exception | 422 | 403 | Traceback

# בדיקת scheduler
# חפש: "digest" | "followup" | "flush"

# בדיקת cost
# חפש: "cost_watchdog" | "token_usage"
```

---

## אנשי קשר / שירותים

| שירות | קונסול | הערה |
|-------|--------|------|
| Render | dashboard.render.com | Backend hosting |
| Airtable | airtable.com/app4bcgoX7t0HUVnm | Base ID פרודקשן |
| Twilio | console.twilio.com | WhatsApp + Voice |
| Telegram | @BotFather | Token management |
| Vercel | vercel.com | TMA Frontend |
| Anthropic | console.anthropic.com | API usage + limits |
