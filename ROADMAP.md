# BOSS Bot — ROADMAP
**מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE.**
עודכן: 07/06/2026

---

## עיקרון ניהול
- **C** = Completed — הושלם ובפרודקשן
- **N** = Next — הבא בתור, מסודר לפי תלויות
- **F** = Future — מתוכנן, אין תאריך

כל פיצ'ר חדש נרשם כאן לפני שנוגעים בקוד.
כל batch מתחיל מקריאת ROADMAP — לא מזיכרון.

---

## C — הושלם

### CORE — תשתית
| ID | שם | קבצים |
|----|----|--------|
| C01 | Identity + Roles | identity.py, tool_registry.py, context.py |
| C02 | Router — Intent / Domain / Risk | core/router/ (7 קבצים) |
| C03 | Anti-Hallucination | core/anti_hallucination.py |
| C04 | Feature Flags | feature_flags.py |
| C05 | Action Validator | action_validator.py |
| C06 | Event Bus + Approval Flow | event_bus.py |
| C07 | Domain Prompts (לפי דומיין) | domain_prompts.py |
| C08 | Memory Store (שיחה קצרת-טווח, TTL) | memory_store.py |
| C09 | Circuit Breaker + Rate Limiter | circuit_breaker.py, rate_limiter.py |

### Lead System
| ID | שם | קבצים |
|----|----|--------|
| C10 | Lead Qualifier (State Machine) | lead_qualifier.py |
| C11 | Lead Memory (ארוך-טווח) | core/lead_memory.py |
| C12 | Lead Events (audit log) | core/lead_events.py |
| C13 | Shared Memory (תובנות עסקיות לפי דומיין) | core/shared_memory.py |
| C14 | Lead Scoring (rule-based, זמן אמת) | core/lead_scoring.py |
| C15 | Followup Engine (תשתית, כבוי) | core/followup_engine.py |

### CRM + Storage
| ID | שם | קבצים |
|----|----|--------|
| C16 | CRM Repository (get_lead / save_lead) | crm.py |
| C17 | Airtable Search + Schema Self-Sync | airtable_tools.py |
| C18 | Store Protocol (LeadStore / EventStore) | core/stores/base.py |

### App Layer
| ID | שם | קבצים |
|----|----|--------|
| C19 | app.py — 4 Hooks (H1–H4) | app.py |
| C20 | Scheduler (jobs קיימים) | scheduler.py |
| C21 | Daily Digest | daily_digest.py |

### חוזה (Contract Fix)
| ID | שם | מה תוקן |
|----|----|---------|
| C22 | feature_flags — is_enabled() alias | 3 קבצים שיובאו בשם לא קיים |
| C23 | config — תיעוד input provider בלבד | מנע מקור אמת כפול עם domain_router |
| C24 | lead_qualifier — detect_domain() | get_domain(channel,sender) לא קיים |

### Stabilization Sprint — 07/06/2026
| ID | שם | מה תוקן | קבצים |
|----|----|---------| ------|
| C25 | Google Tools merge conflict | SyntaxError שורה 21 — נפתר | tools/google_tools.py |
| C26 | lead_qualifier TypeError | get_domain signature mismatch — תוקן | lead_qualifier.py |
| C27 | Event Bus fail-closed | confirm() מחזיר הצלחה רק אם handler רץ בפועל | event_bus.py |
| C28 | email_inbound honest stub | ImportError → mock הוסר; stub כנה | email_inbound.py |
| C29 | TMA approval stubs | TODO הוחלף ב-coming_soon / רשימה ריקה | tma_api.py |
| C30 | tool_registry sync | כלים מיושרים: schemas / validator / registry / dispatcher | tool_registry.py, schemas.py |
| C31 | Airtable shim | תיקון imports עקביים לכל מודולי עזר | airtable_tools.py |
| C32 | Twilio signature validation | WhatsApp webhook מאמת חתימה | app.py |
| C33 | Emergency Stop persistence | flag נשמר ב-restart | feature_flags.py |
| C34 | Mock data removed | דוחות מציגים כשלים אמיתיים | daily_digest.py, workers |
| C35 | Approval subscribers x4 | send_email_reply, send_followup, send_recovery, send_bounce | event_bus.py |
| C36 | Approval UX honest | הצלחה מוצגת רק אחרי פעולה אמיתית | app.py |
| C37 | Payment Reminder fix | self-test עובר (commit 0744ce9) | payment_reminder.py |
| C38 | WhatsApp outbound honest stub | לא מעמיד פנים — מחזיר stub כנה | app.py / whatsapp tools |
| C39 | TMA CORS + auth 401 | CORS origin נוסף ל-Render env; 401 נפתר | tma_api.py, Render env |

---

## N — הבא בתור

**סדר ביצוע קשיח — כל N תלוי ב-N שלפניו.**

### N01 — Airtable Schema Formula Mismatch
**למה קודם:** field name mismatch גורם לקריאות שבורות ב-Lead Pipeline ו-Lead Card.
**מה:** יישור שמות שדות בין airtable_schema.py לטבלאות האמיתיות.
**קבצים:** airtable_schema.py + tma_api.py.
**flag:** אין flag — תיקון schema בלבד.

### N02 — Airtable Save Debounce
**למה קודם:** scoring רץ על כל הודעה → כותב ל-Airtable על כל הודעה → rate-limit.
**מה:** counter per memory_key ב-LeadMemory. שמירה רק כל N=3 הודעות, או כש-tier השתנה.
**קבצים:** core/lead_memory.py בלבד.
**flag:** קיים (LEAD_MEMORY). אין flag חדש.

### N03 — Followup Activation
**תלוי ב:** N02 (אחרת scan → update → rate-limit מיד).
**מה:**
- scan אמיתי בscheduler: טוען לידים פעילים, מריץ determine_followup_needed
- יוצר טיוטה / תזכורת
- שולח לאישור owner דרך event_bus הקיים
- לא שולח ללקוח בלי אישור
**קבצים:** core/followup_engine.py, scheduler.py (job קיים ← מחבר).
**flag:** FOLLOWUP_AUTOMATION (קיים, כבוי).

### N04 — Contact Resolver
**תלוי ב:** ללא תלות, עצמאי.
**מה:** "שלח מייל לדניאל" → חיפוש fuzzy ב-Contacts → אם יש כפילות, מבקש אישור → מבצע.
**קבצים:** כלי חדש contact_resolver.py + רישום ב-tool_registry + schemas.
**flag:** חדש — CONTACT_RESOLVER (כבוי ברירת מחדל).

### N05 — Daily Digest שדרוג
**תלוי ב:** N03 (כדי שלידים חדשים + scoring יופיעו בדוח).
**מה:** חיבור scoring + לידים חדשים לדוח הבוקר הקיים.
**קבצים:** daily_digest.py בלבד.

---

## F — עתיד (אין תאריך, יש spec)

### F01 — Lead Recovery
מה: לידים שדעכו → זיהוי אוטומטי → הצעת פנייה מחדש לowner.
תלוי ב: N03 Followup.
Spec מפורט: ראה ARCHIVE_additions_log.md → A14.

### F02 — Learning Engine
מה: מעל lead_events (כבר נצבר מ-C12). לומד מדפוסים, התנגדויות, מה סגר עסקאות.
תלוי ב: N03, כמה חודשי דאטה.
Spec: ARCHIVE_additions_log.md → A33.

### F03 — Revenue Attribution
מה: קמפיין → ליד → עסקה → כסף. מאיזה פרסום הגיע הכסף.
תלוי ב: F02.
Spec: ARCHIVE_additions_log.md → A10.

### F04 — KPI Engine
מה: מצב עסק בזמן אמת — המרות, תזרים, לידים פעילים, חובות.
תלוי ב: C21 Daily Digest + F03.
Spec: ARCHIVE_additions_log.md → A26.

### F05 — WhatsApp Production (Meta Cloud API)
מה: WhatsApp outbound אמיתי. כרגע honest stub — תלוי Meta Cloud API.
חסם: אישור Meta Cloud API + מספרים ייעודיים.
Spec: ARCHIVE_additions_log.md → A17.

### F06 — Email Channel (Inbound)
מה: לקוח שולח מייל → gmail_read → Router → Agent → draft → אישור → שליחה.
תלוי ב: Google Tools הפשרה (מוקפאים כרגע).
Spec: ARCHIVE_additions_log.md → A42.

### F07 — Voice / IVR (מגזר חרדי)
מה: STT → Router → Agent → TTS. ימות המשיח / Twilio Voice.
מודל עסקי: White-Glove, ריטיינר גבוה.
Spec מפורט: ARCHIVE_additions_log.md → A41.

### F08 — SaaS Multi-Tenant
מה: BOSS כמוצר לעסקים אחרים. tenant_id כבר קיים (C01).
תלוי ב: הכל לפניו.
Spec: ARCHIVE_additions_log.md → A20.

---

## כללי ברזל — לא לגעת בלי אישור

1. **Feature flag = כבוי ברירת מחדל.** מדליקים במודע.
2. **app.py — 4 hooks בלבד (H1–H4).** לא נוגעים שוב בלי סיבה ארכיטקטונית.
3. **Agent לא נוגע ב-Airtable ישירות.** תמיד דרך crm.py.
4. **זיכרון ליד = identity.memory_key בלבד.** לא phone, לא email.
5. **מקור אמת לדומיין = detect_domain() בלבד.** config.py = input provider.
6. **לא בונים batch לפי פיצ'ר — בונים לפי קובץ.**

---

## ארכיב מסמכים

| קובץ | תפקיד |
|------|--------|
| ROADMAP.md | **זה. מקור האמת היחיד.** |
| ARCHIVE_additions_log.md | specs מפורטים A01–A43, היסטוריה |
| SETUP.md | env vars, טבלאות Airtable, הפעלה ראשונה |
