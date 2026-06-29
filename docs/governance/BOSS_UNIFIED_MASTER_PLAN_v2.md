# BOSS Unified Master Plan v2
Date: 30/06/2026  
Owner: Eliyahu  
Status: Working Master Plan — vision + system map integrated

---

## 1. מטרת המסמך

לאחד את כל מסמכי התכנון למסלול ביצוע אחד ברור.

### חזון העל

BOSS היא מערכת הפעלה עסקית אחידה: שכבת עבודה אחת שמרכזת קלט, זיכרון, החלטות, ביצוע, מדידה ופלט.

המערכת נבנית כדי שכל תחום עסקי יוכל לעבוד על אותה ליבה: אותם כללי אמינות, אותם שערי אישור, אותו מודל נתונים, ואותם עקרונות הרחבה.

החזון אינו לבנות עוד אוסף פיצ'רים, אלא שדרה אחת: מידע נכנס דרך שער אחיד, נשמר כמקור אמת, מעובד לפי הקשר עסקי, עובר אישור כשצריך, נכתב עם ראיות, ונמדד לפי תוצאה.

לכן כל הרחבה עתידית — הכנסות, החלטות, מדיה, הפצה, ממשק, או ניהול עסקי מתקדם — חייבת להתחבר לאותה מערכת ולא ליצור מסלול מקביל.

המסמך הזה לא מחליף את `ROADMAP.md` כמקור אמת בריפו.  
הוא משמש כמפת־על: מה קודם, מה אחר כך, מה לא נוגעים בו כרגע, ואיך מונעים שוב ערבוב בין חזון, באגים, ספקס, שינויי UI, ושכבת הכנסות.

---

## 2. הכרעת יסוד

BOSS נבנית כ־Operating System עסקי אחד, אבל הביצוע חייב להישאר בשכבות:

1. Revenue loop — הכנסת כסף ומדידה.
2. Trust / Decision loop — קבלת החלטות אמינה, עם מקור, אמינות, קונפליקטים ומעקב.
3. Media / Context loop — קבצים, קול, נספחים וזיכרון כלים.
4. Distribution loop — הפצה מדודה ובטוחה.
5. Product UI loop — 8 עולמות עסקיים במקום מסכים מפוזרים.
6. Future business management — כדאיות, הון, חלוקת רווחים, SaaS.

הכל חזון אחד, אבל לא בונים הכל יחד.

---

## 3. כללי ברזל

### 3.1 Money-First Gate

כל משימה חדשה עוברת שאלה אחת:

> האם היא מכניסה כסף, משפרת מדידה, או פותחת ערוץ הפצה?

אם לא — היא נדחית, אלא אם היא מתקנת אמינות/אבטחה שחוסמת את שלושת הדברים האלה.

### 3.2 No Claim Without Verification

סטטוס `✅` מותר רק אחרי אימות פרודקשן אמיתי.

`merged`, `py_compile`, `smoke_tests`, או "הקוד קיים" אינם שווים "עובד בפרודקשן".

סטטוסים:
- ✅ Verified in production
- 🟡 Code exists / merged / flag off / needs live verification
- ❌ Not built
- 🧊 Archived / Future only

### 3.3 Feature Flag Default Off

כל פיצ'ר חדש או מסוכן:
- נבנה מאחורי flag
- כבוי כברירת מחדל
- נדלק רק אחרי בדיקת owner/live
- rollback = כיבוי flag או revert קטן

### 3.4 One Write Path

כל כתיבה ל־Airtable עוברת דרך gateway / approval / audit.

אין כתיבה ישירה, אין bypass, אין "זמני".

### 3.5 Broadcast Safety

אין broadcast אוטומטי לפני:
- COG / Messaging Gateway
- Approval hardening
- Emergency stop
- audit per send
- source/referral tracking

### 3.6 Core גנרי, Domain ספציפי

הליבה נשארת domain-agnostic.  
נדל"ן, ייבוא, SaaS, שירותים — כולם משתמשים באותו מנגנון core, עם התאמות schema/copy/domain config בלבד.

---

## 4. מקור אמת ותיעוד

### 4.1 מסמכי אמת פעילים

- `ROADMAP.md` — סדר עדיפויות, blockers, next actions.
- `BOSS_CURRENT_STATE.md` — מצב מודולים בפועל, ארכיטקטורה, סיכונים.
- `CHANGE_CONTROL_LOG.md` — ראיות שינוי ומיזוג.
- `BUG_AUDIT_LOG.md` — באגים עד אימות.
- `AI_CONTEXT.md` — תקציר עבודה לקודקס/קלוד, רק אחרי התאמה ל־ROADMAP/CURRENT_STATE.

### 4.2 מסמכים שאינם מקור אמת

כל מסמך חזון, spec ישן, audit היסטורי, patch report, generated summary, או master plan קודם — נשאר archive evidence בלבד, אלא אם תוכן מסוים קודם ידנית לתוך `ROADMAP.md` או `BOSS_CURRENT_STATE.md`.

### 4.3 כלל עדכון

אין ליצור עוד "מקור אמת מקביל".  
כל סשן שמסתיים בעבודה ממשית חייב לעדכן:
- ROADMAP אם השתנה סדר עדיפויות או סטטוס feature.
- CURRENT_STATE אם השתנה מצב מערכת בפועל.
- CHANGE_CONTROL אם היה commit/merge.
- BUG_AUDIT אם תוקן/נפתח באג.
- AI_CONTEXT רק כתקציר נגזר.

---

## 5. מפת המערכת המאוחדת

**מטרה:** להראות היכן כל רכיב יושב במערכת, מי מדבר עם מי, ומה אסור לעקוף.

הפרק הזה אינו מחליף Governance, Roadmap או Current State. הוא שכבת מיפוי בלבד.

### 5.1 כלל יסוד

לכל רכיב במערכת יש מקום אחד בלבד.

אם רכיב חדש אינו נכנס לאחת השכבות כאן, אין לבנות אותו לפני שמעדכנים את מפת המערכת.

### 5.2 Core Layer

שכבת הליבה של BOSS.

אחראית על זהות, הרשאות, דגלי הפעלה, רישום פעילות, ניטור שגיאות ותצורת מערכת.

רכיבים:
- Identity
- Tenant
- Permissions
- Feature Flags
- Audit Log
- Error Reporting
- System Config

כל מודול עסקי משתמש בליבה. אף מודול עסקי אינו מחזיק לוגיקת הרשאות עצמאית.

### 5.3 Data Layer

שכבת הנתונים והזיכרון.

אחראית על שמירת מידע, מבנה טבלאות, זיכרון עסקי, סשנים, קבצים ומעקב אחר עקיבות מידע.

רכיבים:
- Airtable Schema
- Schema Governance
- Business Memory
- Session Store
- Media / Files Records
- Lead Sessions
- Data Validation

כל כתיבה לנתונים חייבת לעבור דרך חוזה ברור. אין כתיבה ישירה ללא שכבת בקרה מתאימה.

### 5.4 Input Layer

שכבת הקלט האחידה.

אחראית על קבלת מידע מכל ערוץ, ניקוי ראשוני, זיהוי סוג הקלט והעברתו למסלול הנכון.

ערוצי קלט:
- Telegram
- WhatsApp
- Voice
- Files
- Manual Updates
- Forms / UI

הקלט אינו מחליט החלטות עסקיות. הוא מזהה, מסווג ומעביר לשכבת העיבוד.

### 5.5 Processing Layer

שכבת המוח והעיבוד.

אחראית על הבנת הקלט, בחירת מסלול, בניית הקשר, חישוב ניקוד, ניהול תהליך החלטה והפעלת כלים.

רכיבים:
- Agent
- Router
- Context Builder
- Decision Hub
- Lead Scoring
- Lead Memory
- Follow-up Logic
- Business Rules

זו השכבה שמחליטה מה צריך לקרות. היא אינה כותבת ישירות ואינה שולחת החוצה ללא Gateway מתאים.

### 5.6 Tool Layer

שכבת הכלים.

אחראית על חיבור לפעולות חיצוניות או פנימיות בצורה מבוקרת.

רכיבים:
- Tool Registry
- Tool Gateway
- Airtable Tools
- Provider Interfaces
- External Service Adapters
- Tool Result Contracts

כל כלי חייב להחזיר תוצאה מובנית. אין להסתמך על טקסט חופשי כהוכחת הצלחה.

### 5.7 Approval & Safety Layer

שכבת האישור והבטיחות.

אחראית על מניעת פעולות מסוכנות, אישורי בעלים, שערי סיכון, עצירת חירום ורישום ראיות.

רכיבים:
- Approval Bus
- Customer Output Gateway
- Financial Gate
- Emergency Window
- OTP
- Risk Policy
- Anti-Hallucination Gate

פעולה רגישה אינה מתבצעת רק כי המערכת חושבת שהיא נכונה. היא עוברת דרך שער מתאים.

### 5.8 Business Layer

שכבת הישויות העסקיות.

אחראית על שפת העבודה העסקית של BOSS: לידים, אנשי קשר, עסקאות, הזדמנויות, תשלומים, משימות, שותפים והחלטות.

ישויות מרכזיות:
- Leads
- Contacts
- Deals
- Ventures
- Payments
- Tasks
- Partners
- Traffic Sources
- Business Memory
- Decisions

זו השכבה שבה העסק מיוצג. היא אינה תשתית טכנית אלא מודל העבודה העסקי.

### 5.9 Output Layer

שכבת הפלט.

אחראית על שליחה החוצה, התראות, סיכומים, הודעות לבעלים והפצה מבוקרת.

ערוצי פלט:
- Telegram Alerts
- Owner Notifications
- Daily Digest
- WhatsApp Outbound
- Status Updates
- Reports

כל פלט ללקוח או לערוץ חיצוני חייב לעבור דרך Gateway מתאים. אין שליחה ישירה מתוך מודול עסקי.

### 5.10 UI Layer

שכבת הממשק.

אחראית על מסכים, צפייה, עריכה, אישור ובקרה אנושית.

רכיבים:
- TMA Screens
- Game Screen
- BossCheckin
- Ventures Screen
- Finance Pulse
- Lead Detail
- Approval UI

ה־UI מציג ומפעיל תהליכים. הוא אינו מחזיק מקור אמת עצמאי.

### 5.11 Revenue & Distribution Layer

שכבת ההכנסות וההפצה.

אחראית על מדידת מקורות, קמפיינים, שותפים, הכנסות והחזר השקעה.

רכיבים:
- Source Attribution
- Revenue Attribution
- Traffic Sources
- Partner Attribution
- Campaign Tracking
- Distribution Engine

שכבה זו קיימת כדי לענות על שאלה אחת: מה מכניס כסף, מאיפה, ובאיזו יעילות.

### 5.12 Future Layer

שכבת יכולות עתידיות.

רכיבים שלא נבנים כעת, אך יש להם מקום מוגדר במפה:
- Marketing Orchestrator
- Content Engine
- Asset Generation
- Advanced Revenue Intelligence
- Multi-Agent Workflows
- Advanced Decision Automation

רכיב עתידי לא מקבל קדימות רק כי הוא מעניין. הוא נכנס לביצוע רק אם הוא עובר את שער התכנון והעדיפות.

### 5.13 קשרי זרימה עיקריים

#### זרימת קלט רגילה

Input Layer → Processing Layer → Tool Layer / Business Layer → Approval & Safety Layer אם נדרש → Data Layer → Output Layer

#### זרימת ליד

WhatsApp / Telegram / Form → Input Layer → Lead Capture → Lead Scoring → Lead Memory → Leads → Owner Alert / Follow-up / Deal Conversion

#### זרימת החלטה

קלט / מסמך / שיחה → Decision Hub → Context Builder → Business Memory / Files / Sessions → הצגת מצב החלטה → אישור / השלמת מידע / פעולה

#### זרימת כתיבה

UI / Agent / Tool Request → Policy Check → Approval אם נדרש → Tool Gateway → Airtable / Data Layer → Audit Log → Receipt

#### זרימת פלט

Business Event → Output Gateway → Safety Gate → Channel Adapter → Telegram / WhatsApp / Report

### 5.14 כללי שילוב מודול חדש

כל מודול חדש חייב להצהיר:

1. באיזו שכבה הוא נמצא.
2. איזו ישות עסקית הוא משרת.
3. מאיפה הוא מקבל קלט.
4. לאן הוא כותב.
5. דרך איזה Gateway הוא פועל.
6. האם נדרש Approval.
7. איך מאמתים הצלחה.
8. איזה Feature Flag מפעיל אותו.
9. איך מבטלים אותו בלי לשבור את המערכת.

מודול שלא יודע לענות על תשע השאלות האלה — לא נכנס לפיתוח.

---

## 6. התכנית המאוחדת לפי אופקים

---

# Horizon 0 — Truth Reset & Production Verification

**מטרה:** לעצור בלבול בין "נבנה", "מוזג", "דגל כבוי", ו־"עובד".

## H0.1 מסמך תכנון אחד

ליצור בריפו מסמך קצר:
`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`

המסמך הזה צריך להיות שכבת־על בלבד, לא להחליף את ROADMAP.

## H0.2 לנקות סטטוסים

לעבור על כל הפריטים המסומנים ✅ ולשנמך ל־🟡 אם אין:
- commit hash
- deploy hash / Render hash
- בדיקת live מתועדת
- תוצאה אמיתית

## H0.3 לאמת Deployment

רשימת חובה:
- Render רץ על commit main הנכון.
- flags ידועים ומכוונים.
- אין claim "פעיל" על feature עם flag off.
- אין `FEATURE_DECISION_HUB`, `LEAD_CAPTURE`, `LEAD_SCORING`, `FEATURE_MEDIA_UPLOAD`, `FEATURE_VOICE_NOTES` דלוקים בטעות לפני בדיקה.

## H0.4 לסגור ענפים וקונפליקטים

חובה לפתור:
- C60 Tool Context Awareness — code done אבל לא ממוזג. להחליט: merge עכשיו או freeze.
- F12 מול F13 — לא לחבר provider layer לפני הכרעה.
- C59/C60 ID collision — לשמר mapping בתיעוד.
- F16 Media Files table — לא להדליק לפני שהטבלה קיימת ב־Airtable.
- Decision Trust Tags — לוודא אופציות multi-select חיות לפני כתיבה.

**Definition of Done:** אין מסמך שמציג מצב שאינו מגובה בראיה.

---

# Horizon 1 — Revenue Loop MVP

**מטרה:** להפעיל את הלולאה שמכניסה כסף ומודדת כסף.

זה קודם לכל UI יפה, content engine, video, orchestrator, SaaS, או refactor.

## H1.1 Lead Capture live

פעולות:
1. להדליק `LEAD_CAPTURE=true` בסביבה מבוקרת.
2. לשלוח הודעת WhatsApp אמיתית.
3. לוודא רשומת Lead ב־Airtable.
4. לוודא domain/source/channel.

## H1.2 Source Attribution

פעולות:
1. לאמת `_inject_utm`.
2. ליצור/להשלים טבלת `TRAFFIC_SOURCES`.
3. כל לינק/קמפיין/קבוצה/מודעה מקבלים `source_code`.
4. אין קמפיין בלי source.

## H1.3 Lead Scoring + Tier

פעולות:
1. להדליק `LEAD_SCORING=true` רק אחרי H1.1.
2. לוודא `score` נכתב.
3. לוודא `tier` נכתב לשדה חי נכון.
4. לבדוק HOT lead אמיתי.

## H1.4 Owner Alert

פעולות:
1. HOT lead אמיתי → Telegram alert ל־owner.
2. alert כולל source, tier, next action.
3. אין followup automation לפני שה-alert מוכח.

## H1.5 Daily Digest בסיסי

Digest לא חייב להיות מושלם.  
הוא חייב להראות:
- לידים חמים
- followups שדורשים אישור
- משימות היום
- anomalies / failures

**Definition of Done:** ליד אמיתי נכנס, מקבל source, score/tier, נשלח alert, ונמדד.

---

# Horizon 2 — Revenue Attribution & Partner Loop

**מטרה:** לדעת מאיפה הכסף בא.

## H2.1 Revenue Attribution

פעולות:
1. להשתמש ב־Origin Lead backlink הקיים.
2. ליצור aggregation לפי source.
3. לחבר Deals/Contacts/Payments לפי מקור.
4. דוח שבועי: source → leads → hot leads → deals → revenue.

## H2.2 Partner Attribution

פעולות:
1. טבלת Partners.
2. referral_code לכל שותף.
3. source_code לכל referral.
4. דוח ROI לפי partner.

## H2.3 Manual Distribution First

לפני אוטומציה:
- Telegram ערוץ עובד.
- WhatsApp Status/Groups ידני עם source codes.
- Posters/phone lines עם קודי מקור.
- Partnerships עם קודי referral.

**Definition of Done:** אפשר לדעת איזה מקור או שותף הביא כסף, לא רק לידים.

---

# Horizon 3 — Decision Hub Owner-Only

**מטרה:** להפוך החלטות עסקיות לנכס מובנה, בלי להכניס סיכון לפרודקשן.

## H3.1 מצב קיים

Stage 0 / 0.5 / 0.6:
- routing לקבצים/נספחים
- Decision Inbox
- session context
- last uploaded file
- merged to main
- flag off

Stage 1 Trust Layer:
- merged
- trust score
- claim topic
- supersede
- user flags
- לא verified production

Stage 2-4:
- conflict detection
- readiness engine
- attention engine
- לא התחילו

## H3.2 לפני הדלקה

חובה:
1. לוודא Airtable fields קיימים:
   - Claim Topic
   - Claim Topic Source
   - Claim Topic Confidence
   - Trust Level
   - Confidence
   - Tags
   - Supersedes
2. לוודא multi-select options קיימות.
3. להוסיף UI/flow ל־Source Reliability — אחרת default "ידני" יגרום trust לא מדויק.
4. לבצע test owner-only:
   - `/decision new`
   - העלאת קובץ
   - "זה הנספח"
   - link to decision
   - trust gate
   - user_flag
   - event write
5. לא לאפשר כתיבה רחבה לפני owner-only green.

## H3.3 C60 Tool Context Awareness

החלטה:
- אם Decision Hub נשען על "זה/הנספח/הקודם" — C60 צריך להיכנס לפני הפעלה אמיתית.
- אם לא, אפשר לדחות אותו, אבל אז מגבילים את Decision flow לטקסט מפורש בלבד.

**Definition of Done:** החלטה אמיתית אחת עוברת end-to-end עם קובץ, מקור, trust, ו־event כתוב.

---

# Horizon 4 — Media Layer Enablement

**מטרה:** קבצים וקול נכנסים למערכת בלי לשבור אמינות.

## H4.1 F16 מצב קיים

קיים:
- STT adapter
- Drive upload
- Media Gateway
- Media Handler
- Telegram hooks
- TMA upload endpoint
- MediaFileFields schema
- tests

חסר/דורש אימות:
- טבלת `Media Files` חיה ב־Airtable.
- flags כבויים כברירת מחדל.
- live upload מטלגרם.
- live upload מ־TMA.
- oversized file rejection.
- transcription path.

## H4.2 סדר הפעלה

1. ליצור/לאמת טבלת `Media Files`.
2. להדליק `FEATURE_MEDIA_UPLOAD=true` לסביבת owner.
3. להעלות קובץ קטן.
4. לבדוק Drive URL + Airtable metadata.
5. להדליק `FEATURE_VOICE_NOTES=true`.
6. לבדוק voice note קטן.
7. לבדוק קובץ גדול מדי.

**Definition of Done:** קובץ וקול נשמרים עם metadata, transcript אם יש, ובלי claim שקרי.

---

# Horizon 5 — Distribution Gateway

**מטרה:** הפצה בלי פגיעה באמון, בלי spam, ועם מדידה.

## H5.1 COG / Messaging Gateway

לפני כל broadcast:
- envelope אחיד
- recipient/audience
- channel
- source_code
- approval
- emergency stop
- audit
- rate limit

## H5.2 Meta WhatsApp

Inbound:
- F05a קיים test-only.
- לא להסתמך עליו כ-production lead flow לפני חיבור אמיתי.

Outbound:
- רק אחרי Meta approval / number / templates / 24h window.
- כל outbound חייב approval/audit/source.

## H5.3 Content

לא לבנות Content Engine חדש.

כרגע:
- להשתמש ב־`creative_generator.py` הקיים.
- תוכן ידני/חצי ידני.
- כל פוסט/מודעה עם source code.
- Content DNA / Video / Marketing Orchestrator = P3+ אחרי הכנסה מוכחת.

**Definition of Done:** ערוץ הפצה אחד עובד, מדיד, מאושר, וניתן לעצירה.

---

# Horizon 6 — Product UI / OS Refactor

**מטרה:** להפוך את המוצר לנוח בלי לשבור תשתיות קיימות.

המעבר:
- מ־11 מסכים מפוזרים
- ל־8 עולמות עסקיים
- עם BOSS Layer רוחבי

## 8 העולמות

1. Command Center — מה דורש אותי עכשיו?
2. Ventures — האם כדאי להיכנס?
3. Pipeline — האם הלקוח יקנה?
4. Operations — האם אנחנו מספקים?
5. Finance — האם אנחנו מרוויחים?
6. Knowledge — מי יודע מה ומה למדנו?
7. Insights — לאן העסק הולך?
8. System — איך המערכת עובדת?

BOSS Layer:
- רוחבי, לא מסך עצמאי מרכזי.
- BossBar בראש המסכים.
- GameScreen נשאר drill-down אופציונלי.

## סדר UI

1. Stage 0 bugs / schema field fixes.
2. Ventures screen.
3. Command Center.
4. BossBar.
5. Operations.
6. Knowledge.
7. Insights + System.

**Definition of Done:** כל שלב UI עצמאי, עובד, ולא שובר Approval/HMAC/Emergency Stop.

---

# Horizon 7 — Future Business Management

**מטרה:** אחרי שהתפעול מוכח, להרחיב לשכבת ניהול עסקית מלאה.

לא עכשיו:
- Deal Evaluation
- Demand Research
- Deal Structuring
- Profit Distribution
- Capital Management
- SaaS Multi-Tenant
- Provider abstraction
- Learning Engine
- KPI Engine מתקדם
- Video Engine
- Marketing Orchestrator

כן לשמור כ־Future:
- F01 Lead Recovery
- F02 Learning Engine
- F03 Revenue Attribution מתקדם
- F04 KPI Engine
- F05 WhatsApp Production
- F06 Email Inbound
- F07 Voice/IVR
- F08 SaaS Multi-Tenant
- F12/F13 Provider/Tenant decision
- F14 Contact Gate
- F15 crm.py gateway migration

---

## 7. Backlog מאוחד

| Priority | פריט | למה עכשיו | תנאי כניסה | DoD |
|---|---|---|---|---|
| P0 | Truth Reset | בלי אמת אין אמון | כל docs זמינים | ROADMAP/CURRENT_STATE מסונכרנים |
| P0 | Lead Capture live | כסף | flag controlled | Lead אמיתי ב־Airtable |
| P0 | Source Attribution | מדידה | Lead Capture עובד | source/channel נכתבים |
| P0 | Lead Scoring | תעדוף מכירות | source עובד | score/tier live |
| P0 | TRAFFIC_SOURCES | עמוד שדרה למדידה | source policy | כל source מקודד |
| P0 | Revenue Attribution MVP | לדעת מה מכניס | Origin Lead קיים | דוח מקור→הכנסה |
| P1 | Partner Attribution | ROI גבוה, low-tech | attribution בסיסי | partner→revenue |
| P1 | Decision Hub owner-only | החלטות קריטיות | Airtable fields verified | decision event trusted |
| P1 | Media Layer owner-only | נספחים/קול | Media Files table | file/voice live |
| P1 | C60 decision | context continuity | decide merge/freeze | no pronoun confusion |
| P1 | COG/Messaging Gateway | לפני הפצה | approval/audit | safe outbound envelope |
| P2 | Meta WhatsApp Production | ערוץ מרכזי | Meta approval | inbound/outbound audited |
| P2 | Command Center MVP | שימושיות | revenue loop stable | alerts/tasks/approvals |
| P2 | Ventures refinement | הזדמנויות | Decision flow stable | convert to Deal/Project |
| P3 | Knowledge Hub | בידול | Interaction Log stable | contacts+memory linked |
| P3 | Content DNA | שיווק מתקדם | revenue loop proven | no parallel system |
| P4 | Video Engine | חזון | content proven | measured output |
| P5 | Marketing Orchestrator | אוטונומיה | all gates stable | safe auto-publishing |

---

## 8. מה לא עושים עכשיו

1. לא בונים Orchestrator לפני שהלולאה מכניסה כסף.
2. לא בונים Video Engine לפני Content DNA מוכח.
3. לא מחברים F12/F13 לפני הכרעת provider architecture.
4. לא מפעילים WhatsApp outbound לפני Gateway + Meta + audit.
5. לא מחברים SaaS multi-tenant לפני שהמערכת עובדת אצלנו.
6. לא עושים UI refactor רחב לפני H0/H1.
7. לא מסמנים ✅ בלי production evidence.
8. לא יוצרים עוד "Master Plan" שמתחרה ב־ROADMAP.

---

## 9. סדר עבודה ל־Codex / Claude Code

### שלב A — Docs alignment בלבד

1. צור/עדכן `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` לפי מסמך זה.
2. עדכן `ROADMAP.md` כך שיכיל רק:
   - Active priorities
   - Blockers
   - Next actions
   - Status verified / partial / planned
3. עדכן `BOSS_CURRENT_STATE.md` כך שיכיל:
   - מצב production אמיתי
   - flags
   - modules
   - open risks
4. העבר כל מסמך כפול או היסטורי ל־archive disposition.
5. אל תשנה קוד בשלב זה.

### שלב B — Verification sweep

1. בדוק Render hash מול main.
2. בדוק flags.
3. בדוק Lead Capture/Scoring/Decision/Media flags כבויים או מופעלים במודע.
4. פתח רשימת manual verification לפי P0/P1.
5. עדכן BUG_AUDIT/CHANGE_CONTROL לפי ראיות בלבד.

### שלב C — Revenue activation

1. הפעל `LEAD_CAPTURE` owner-controlled.
2. אמת lead חי.
3. אמת source.
4. הפעל `LEAD_SCORING`.
5. אמת score/tier.
6. אמת alert.
7. רק אז עבור ל־TRAFFIC_SOURCES/Revenue Attribution.

### שלב D — Decision + Media owner-only

1. ודא Airtable schema.
2. החלט לגבי C60.
3. הפעל `FEATURE_DECISION_HUB` בסביבה מבוקרת.
4. בדוק החלטה אחת end-to-end.
5. הפעל `FEATURE_MEDIA_UPLOAD` / `FEATURE_VOICE_NOTES` רק אחרי טבלת Media Files.

---

## 10. משפט הסיכום

הדרך הנכונה היא לא "לבנות עוד הרבה", אלא להפעיל את מה שכבר נבנה, לאמת אותו, למדוד כסף, ואז לפתוח בזהירות את שכבת ההחלטות וההפצה.

החזון רחב.  
הכביש אחד.  
הצעד הראשון: אמת → כסף → מדידה → החלטות → הפצה → UI → אוטונומיה.
