# BOSS OS — תוכנית Refactor v1.0
**תאריך:** 17/06/2026
**מטרה:** מעבר מ-11 מסכים מפוזרים ל-8 עולמות עסקיים + BOSS Layer רוחבי, תוך תיקון כל הבאגים הידועים. **בלי לשבור את ה-Approval Gate.**

---

## עקרון מנחה
> כל מסך עונה על שאלה עסקית אחת. BOSS (גיים) הוא שכבה רוחבית, לא מסך. הידע והזיכרון הם הייחודיות — מקבלים מסך מלא.

---

## מפת המעבר: 11 מסכים → 8 עולמות

| עולם חדש | שאלה | מסכים קיימים שמרכיבים אותו | סוג פעולה |
|----------|------|---------------------------|-----------|
| 🏠 Command Center | מה דורש אותי עכשיו? | OCC + Hub KPIs + Daily Digest | **מיזוג** (OCC = בסיס) |
| 🔭 Ventures | האם כדאי להיכנס? | Strategic Pipeline (קבור ב-OCC) | **חילוץ** |
| 🎯 Pipeline | האם הלקוח יקנה? | LeadPipeline + LeadDetail | נשאר |
| 🏗️ Operations | האם אנחנו מספקים? | Projects Hub + Personal Mode | **מיזוג + תיקון שדות** |
| 💰 Finance | האם אנחנו מרוויחים? | FinancePulse | נשאר |
| 🧠 Knowledge | מי יודע מה ומה למדנו? | ActivityFeed + Interaction Log | **שדרוג ל-Relationship Hub** |
| 📊 Insights | לאן העסק הולך? | BossDigest + AI Usage | **מיזוג** |
| ⚙️ System | איך המערכת עובדת? | SystemHealth + Approvals | **מיזוג** |
| ⚔️ BOSS Layer | (רוחבי) | GameScreen + BossCheckin | **הופך לשכבה** |

---

## שלב 0 — תיקוני באגים קריטיים (לפני כל refactor)

יש לטפל בכל אלה תחילה כי הם תשתית:

| # | מסך | באג | תיקון |
|---|-----|-----|--------|
| 1 | PersonalMode | שמות שדות לא תואמים ל-live Airtable | מפה לשמות אמיתיים: `Mortgage Balance` (לא `Mortgage`). הסר התייחסויות ל-`Purchase Cost` ו-`Documents` שלא קיימים. |
| 2 | BossCheckin + GameScreen | `/api/game/today` משותף — שינוי שובר שניים | פצל ל-`/api/game/checkin` ו-`/api/game/world` עם service layer משותף מתחת |
| 3 | GameScreen | אין constraint על Worlds פעילים | הוסף ולידציה: רק World אחד `Active` בכל רגע |
| 4 | BossCheckin | tasks ללא persisted flag לא נכתבים — UX לא ברור | החלט: או לכתוב מיד, או להציג מצב "לא נשמר" ברור |
| 5 | Telegram | `/status` handler חסר decorator | תיקון שורה אחת |
| 6 | Hub | debug info (platform/initData) בתצוגת שגיאה | הסר מפרודקשן |

**שדות אמיתיים ב-Units (לתיקון PersonalMode):**
`Unit Number, Project, Type, Size (sqft), Price, Status, Sale Price (NIS), Current Value, Mortgage Balance, Monthly Income, Ownership %, Equity, My Equity`

---

## שלב 1 — חילוץ Ventures (הניצחון הראשון)

**למה ראשון:** מאמץ קטן, ערך עצום. ה-Strategic Pipeline כבר קיים בתוך `OwnerControlCenter.tsx` — רק צריך לחלץ אותו למסך עצמאי.

### ⚠️ החלטה ארכיטקטונית (סופית): טבלה נפרדת
**Ventures = טבלה חדשה ונפרדת. לא חלק מ-Deals.**
- **Venture** = האם בכלל כדאי לפתוח שולחן (לפני ליד, לפני עסקה)
- **Deal** = כסף שכבר על השולחן (הזדמנות מסחרית מוגדרת)
- ערבוב ביניהם הורס את הניקיון הארכיטקטוני. Deals נשאר רק לעסקאות מכירה.

### יצירת טבלת Ventures (Claude Code — לא ניתן דרך MCP API)
> הערה: יצירת טבלה חדשה לא נתמכת ב-Airtable MCP. יש ליצור אותה דרך Claude Code (Airtable Web API / Meta API) או ידנית.

**סכמת טבלת `Ventures`:**

| שדה | סוג | ערכים / הערות |
|-----|-----|----------------|
| `Venture Name` | singleLineText | שדה ראשי |
| `Domain` | singleSelect | נדל"ן / ייבוא / SaaS / שירותים / אחר |
| `Stage` | singleSelect | Research / Supplier-Source / Due Diligence / Smoke Test / GO / NO-GO |
| `Description` | multilineText | במה מדובר |
| `Decision Log` | multilineText | מה נבדק, מה הוחלט, למה |
| `Estimated Decision Date` | date | מתי GO/NO-GO צפוי |
| `Confidence` | singleSelect | נמוך / בינוני / גבוה |
| `Linked Contacts` | multipleRecordLinks → אנשי קשר (Contacts) | ספקים, עו"ד, עמיל מכס |
| `Linked Interactions` | multipleRecordLinks → Interaction Log | פגישות, הצעות, מו"מ |
| `Linked Memory` | multipleRecordLinks → Business Memory | אירועים והחלטות |
| `Converted To` | singleSelect | — / Deal / Project / Campaign |
| `Owner` | multipleRecordLinks → Profile | |
| `Created At` | createdTime | |

**שלבי ה-Venture (דומיין-אגנוסטי — זהה לנדל"ן/ייבוא/SaaS):**
```
Research → Supplier/Source → Due Diligence → Smoke Test → GO/NO-GO → [Convert]
```

### משימות שלב 1
1. צור טבלת `Ventures` עם הסכמה לעיל
2. צור קומפוננטה `Ventures.tsx`
3. העבר את לוגיקת ה-Strategic Pipeline מ-OCC לקומפוננטה החדשה (קורא מ-Ventures, לא מ-Deals)
4. הוסף פעולה **Convert Venture → Deal / Project / Campaign** (דרך Approval Gate)
   - בהמרה: צור רשומה ב-Deals/Projects, סמן Venture כ-`Converted To`, שמור קישור
5. ה-OCC ימשיך להציג סיכום (count by stage), אבל המסך המלא הוא Ventures
6. הוסף `Ventures` ל-`_TMA_WRITE_ALLOWED_TABLES` (כדי שכתיבה תעבור דרך ה-Gate)

---

## שלב 2 — Command Center (מיזוג OCC + Hub + Digest)

**בסיס:** `OwnerControlCenter.tsx` (הכי עשיר).

**מה ממזגים פנימה:**
- KPIs גלובליים מ-Hub (`income_this_month, pending_payments, overdue_tasks, hot_leads`)
- סיכום יומי מ-BossDigest

**מבנה v1 (מינימלי — לפי החלטת MVP):**
```
┌─────────────────────────────┐
│ BOSS BAR (World + Streak)   │  ← שכבה רוחבית
├─────────────────────────────┤
│ 🚨 ALERTS — דחוף עכשיו     │
├─────────────────────────────┤
│ ✅ APPROVALS — ממתינים     │
├─────────────────────────────┤
│ 📋 TODAY — משימות היום      │
├─────────────────────────────┤
│ 📊 3 מספרים בלבד            │
└─────────────────────────────┘
```

**לא בגרסה 1 (יגיע כשנבין מה שימושי):** Value Meter, Ventures Pulse, Pipeline Pulse, KPI מורחב.

---

## שלב 3 — BOSS הופך לשכבה רוחבית

**הבעיה הנוכחית:** שני מסכים (GameScreen + BossCheckin) חולקים endpoint ושוברים זה את זה.

**הפתרון:** רכיב יחיד `<BossBar />` שמופיע בראש כל מסך:
```
[⚔️ World 3]  ████░░ 67 XP   🔥 Streak: 5   Quest: "סגור 2 עסקאות"
```

**מאפיינים:**
- קורא מ-Worlds + Coins_Log (סכום)
- ניתן להסתרה ב-System settings (משתמש שלא רוצה גיים)
- הנתונים העסקיים זהים בין אם הוא מוצג או לא
- מסך GameScreen המלא נשאר זמין כ-drill-down אופציונלי, אבל לא בניווט הראשי

---

## שלב 4 — Operations (מיזוג Hub + Personal Mode)

- Projects Hub = מבט-על על פרויקטים
- Personal Mode = נכסים בתוך הפרויקטים
- **תנאי:** באג שמות השדות (שלב 0 #1) תוקן קודם

---

## שלב 5 — Knowledge (שדרוג ActivityFeed)

**מ-feed פסיבי ל-Relationship Hub:**
- אנשי קשר לפי תפקיד: ספקים, עו"ד, רו"ח, משקיעים, מתווכים
- היסטוריית אינטראקציות לכל קשר (Interaction Log)
- Business Memory + Learnings & Insights מקושרים
- זה הנכס שמבדל את BOSS מכל CRM סטנדרטי

---

## שלב 6 — Insights + System (מיזוגים אחרונים)

- **Insights:** BossDigest + AI_Usage_Daily → דשבורד למידה
- **System:** SystemHealth + Approvals → מסך תשתית אחד

---

## מה אסור לגעת בו (שכבת בטיחות)

1. **Approval Gate** — כל כתיבה עוברת דרכו
2. `_TMA_WRITE_ALLOWED_TABLES` — רשימת ההיתרים
3. HMAC validation (`_validate_initdata`)
4. Emergency Stop mechanism

אלה נשארים רוחביים ותחתיים מתחת לכל המסכים החדשים.

---

## סדר ביצוע מומלץ

```
שלב 0 (באגים)  →  שלב 1 (Ventures)  →  שלב 2 (Command Center)
     →  שלב 3 (BOSS Layer)  →  שלב 4 (Operations)
     →  שלב 5 (Knowledge)  →  שלב 6 (Insights+System)
```

**עיקרון:** כל שלב עצמאי, עובד, ונבדק לפני המעבר לבא. MVP קודם, הרחבה אחר כך.

---

## טבלאות Airtable — Reference (Base: app4bcgoX7t0HUVnm "בסיס עיקרי")

| תפקיד | טבלה |
|-------|------|
| לידים | Leads |
| עסקאות/Ventures | עסקאות (Deals) |
| אנשי קשר | אנשי קשר (Contacts) |
| משימות | משימות (Tasks) + משימות ודד ליינים |
| תשלומים | תשלומים (Payments) |
| הוצאות | הוצאות (Expenses) |
| נכסים | Units + Assets |
| פרויקטים | Projects + ProjectsHub |
| זיכרון | Business Memory + Interaction Log + Learnings & Insights |
| גיים | Worlds + Quests + Roadmap_Tasks + Coins_Log + Boss_Battles + Weekly_Goals |
| בקרה | AI_Usage_Daily |
