# BOSS Bot — ROADMAP
**מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE.**
עודכן: 12/06/2026

---

## עיקרון ניהול
- **C** = Completed — הושלם ובפרודקשן
- **W** = Completed (World 2 sprint) — נוסף במהלך Lead Flow Audit
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
| ID | שם | קבצים | הערה |
|----|----|----|------|
| C12 | Lead Events (audit log) | core/lead_events.py | |
| C13 | Shared Memory (תובנות עסקיות לפי דומיין) | core/shared_memory.py | |
| ~~C14~~ | ~~Lead Scoring~~ | ~~core/lead_scoring.py~~ | **קובץ לא קיים — הוסר מ-Completed** |

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
| C40 | Golden Path Approval Gate | TMA write endpoints now require approval before Airtable writes: POST /api/projects, PATCH /api/leads/<lead_id>/status, POST /api/followup. Writes execute only after approve; reject does not write; receipt returned after execution; audit runs only after successful execution. | tma_api.py (commit 4e5d00d on origin/approval-gate; supersedes local f3172ba) |

### World 2 — Lead Flow Sprint (08/06/2026)
| ID | שם | מה נעשה | קבצים | commit |
|----|----|---------|--------|--------|
| W0 | WhatsApp Lead Capture | ליד נכנס ← נוצר/מתעדכן Leads ב-Airtable | lead_capture.py, app.py | 2b861bd |
| W1 | Airtable Schema Fix (N01) | LeadFields.SCORE/TIER + schema_intelligence sync | airtable_schema.py, schema_intelligence.py, tma_api.py, daily_digest.py | f095036 |
| W1b | W1 Completion — Score/Next Followup case fix | LeadFields.SCORE "score"→"Score"; FIELD_ALIASES aligned; schema_cache.json updated | airtable_schema.py, schema_cache.json, schema_intelligence.py, lead_memory.py, tools/airtable_tools.py | a6b471c |
| W2 | Airtable Gateway — single write path | tools/airtable_gateway.py: normalize→validate→audit→httpx; tma/agent/lead_capture migrated; 22-test regression suite | tools/airtable_gateway.py, tma_api.py, airtable_tools.py, lead_capture.py, app.py | b43357e |

---

## N — הבא בתור

**סדר ביצוע קשיח — כל N תלוי ב-N שלפניו.**

### N01 — ✅ הושלם (W1 לעיל)

### N02 — Live Lead Scoring
**למה עכשיו:** W0 יוצר ליד ב-Airtable. עכשיו צריך לתת לו ציון בזמן יצירה.
**מה:** scoring בסיסי בתוך lead_capture.py — לא מודול נפרד.
- ציין פרויקט ספציפי? +20
- שאל על מחיר? +15
- ציין תקציב? +25
- כותב score + tier לאותה שורת Airtable של W0
**קבצים:** lead_capture.py בלבד.
**flag:** LEAD_SCORING (כבוי ברירת מחדל).

### N03 — Lead Memory Wire-up
**תלוי ב:** N02 (צריך score אמיתי לפני זיכרון).
**מה:** חיבור lead_memory.update() לתוך lead_capture — אחרי create/score.
**קבצים:** lead_capture.py + core/lead_memory.py.
**flag:** LEAD_MEMORY (קיים, כבוי).

### N04 — Followup Activation
**תלוי ב:** N03.
**מה:** scheduler scan → לידים עם tier=HOT ללא מגע 24 שעות → שולח לאישור owner.
**קבצים:** core/followup_engine.py, scheduler.py.
**flag:** FOLLOWUP_AUTOMATION (קיים, כבוי).

### N05 — Daily Digest שדרוג
**תלוי ב:** N02 (כדי שציונים אמיתיים יופיעו בדוח).
**מה:** חיבור score + tier לדוח הבוקר.
**קבצים:** daily_digest.py בלבד.

### F05a — Meta WhatsApp Phase 1 (Inbound, ללא תעבורת פרודקשן)
**מה:** `/webhooks/meta/whatsapp` (GET verify + POST inbound) — נתיב נפרד מ-Twilio.
מנרמל payload → אותו pipeline של `run_agent()` כמו Twilio. Outbound נשאר stub כנה.
**קבצים:** `app.py` (2 helpers + 1 route, additive בלבד).
**guard:** `EMERGENCY_STOP_WHATSAPP` נבדק לפני כל processing.
**env:** `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`.
**סטטוס:** test-only — אין תעבורת לידים אמיתית עד F05 (חיבור Meta מלא).

---

## 📌 Business Lifecycle Gap Analysis (נוסף 2026-06-13)

ה-CRM/Workflow הקיים מכסה כ-20-25% ממחזור החיים העסקי המלא.
מיפוי 8 השלבים:

| שלב | תיאור | סטטוס |
|---|---|---|
| 1. Opportunity Pipeline | איתור הזדמנויות (מתווך/שמאי/ספק/שותף/משקיע) | ❌ לא קיים → **Future** |
| 2. Deal Evaluation | בדיקת כדאיות (שמאי/עו"ד/רו"ח/מיסוי/סיכונים) | ❌ לא קיים → **Future** |
| 3. Demand Research | מחקר שוק (לקוחות/מתחרים/תמחור) | ❌ לא קיים → **Future** |
| 4. Deal Structuring | בניית עסקה (מימון/שותפים/מבנה רווחים) | ❌ לא קיים → **Future** |
| 5. Marketing & Sales | קמפיינים/לידים/פולואפים | ✅ הכי מפותח - הליבה הקיימת |
| 6. Execution | חוזים/גבייה/תשלומים/מסירה | 🟡 חלקי (Payments table קיים) |
| 7. Profit Distribution | חלוקת רווחים לשותפים/משקיעים | ❌ לא קיים → **Future** |
| 8. Capital Management | מעקב הון - כמה נשאר/מושקע/חוזר/יוצא | ❌ לא קיים → **Future** |

**החלטה (2026-06-13)**: לא בונים שלבים חדשים כרגע. ממשיכים ברודמאפ הקיים
(Cost Watchdog → Meta WhatsApp → N04/N05 → Digest). שלבים 1-4, 7-8
מתועדים כ-Future items, יישקלו לאחר השלמת השכבה התפעולית.

**עקרון מנחה**: המערכת היום היא "Operating Layer" (תפעול). שכבת
"Business Management" (ניהול העסק - הזדמנויות, כדאיות, הון) היא
השכבה הבאה, אחרי שהתפעול מבוסס לחלוטין.

---

## 📌 Strategic Layer — Minimal Adaptation (2026-06-13)

**עקרון**: לא Opportunities table נפרדת. הרחבת `Deals.Status` כך שה-Deal
"נולד" משלב הרעיון, לפני שיווק. Dashboard/Cards הם views על הסטטוסים
החדשים — לא טבלאות חדשות.

### ✅ שלב 1-2 — Schema (מיושם)
- `DealStatus` ב-`airtable_schema.py` — 4 ערכים חדשים לפני ה-execution stages:
  `"Idea" → "Feasibility Check" → "Legal/Tax Review" → "Pending Decision"`
  + `"Rejected"` (שונה מ-Cancelled — נדחה לפני שהיה Active)
- `ContactFields.ROLE_CATEGORY = "Role Category"` (single-select) + `ContactFields.SPECIALTY = "Specialty"` (text)
- `ContactRoleCategory`: `lead / broker / expert / supplier / operator / partner / investor / client / other`
- **לא נגענו** ב-Lead Capture / Scoring / Approval Gate / Routing

### 🔲 שלב 3 — OCC Endpoint Extension (ממתין לאישור)
הרחבת OCC endpoint קיים עם 3 ספירות חדשות (לא endpoint חדש — תוספת ל-response):
```
New Opportunities  = COUNT(Deals WHERE Status = "Idea")
In Evaluation      = COUNT(Deals WHERE Status IN ("Feasibility Check", "Legal/Tax Review"))
Pending Decision   = COUNT(Deals WHERE Status = "Pending Decision")
```

### 🔲 שלב 4 — TMA Strategic Card (ממתין לאישור)
כרטיס "Strategic" נוסף ב-Owner Control Center, נשען על endpoint המורחב.

**מה לא משתנה לעולם בשלבים 3-4**: Lead Capture, Scoring, Approval Gate, Routing, Activity Feed.

---

## 📌 CORE_05 Cost Watchdog — Spec v2 (גנרי, multi-source)

### תיקון תיעוד חשוב
`interaction_engine.py` (שהוזכר כקורא Sonnet כל 15 דקות) **לא קיים בקודבייס**.
הארכיטקטורה התפתחה ל-`context.py` שכולל `_select_model()` חכם:
- Owner + הודעה מתחילה ב-`#` → Sonnet (מצב מחקר)
- כל שאר המקרים → Haiku

**נקודת הדליפה האמיתית**: `creative_generator.py` קרא ל-Sonnet תמיד — **תוקן** (Haiku עכשיו).

### מרכיבי הפתרון (מיושם 2026-06-13)
- `core/cost_watchdog.py` (חדש) — `log_usage(source_type, units, meta, user_id)` → `logs/usage.jsonl`
- `creative_generator.py` — עבר ל-Haiku + log_usage אחרי כל קריאה
- `app.py` — `log_usage()` אחרי כל `client.messages.create` (source_type לפי model name)
- `scheduler.py` — `_job_daily_usage_report` כל יום 08:00 → aggregation + Airtable + alert
- `airtable_schema.py` → `Tables.AI_USAGE_DAILY = "AI_Usage_Daily"` (טבלה חדשה, 1 שורה/יום)
- Feature flag: `COST_WATCHDOG_ENABLED=true` (default on)
- ספים: `SONNET_DAILY_LIMIT=50` (configurable), `WHATSAPP_CONV_DAILY_LIMIT` (להגדיר עם Meta)

### עלויות נסתרות (לא בקוד — מעקב ידני)
- Meta WhatsApp Cloud API: per-conversation pricing (utility/marketing/auth) — לבדוק לפני חיבור
- Render: per-plan-tier (compute/RAM), לא per-call — רלוונטי לסקלביליות 1000 משתמשים
- Airtable: rate limit 5 req/sec/base — סיכון 429 errors בעומס גבוה

---

## F — עתיד (אין תאריך, יש spec)

### F01 — Lead Recovery
מה: לידים שדעכו → זיהוי אוטומטי → הצעת פנייה מחדש לowner.
תלוי ב: N04 Followup.

### F02 — Learning Engine
מה: מעל lead_events (C12). לומד מדפוסים, התנגדויות, מה סגר עסקאות.
תלוי ב: N04, כמה חודשי דאטה.

### F03 — Revenue Attribution
תלוי ב: F02.

### F04 — KPI Engine
תלוי ב: C21 Daily Digest + F03.

### F05 — WhatsApp Production (Meta Cloud API)
חסם: אישור Meta Cloud API. כרגע honest stub.

### F06 — Email Channel (Inbound)
תלוי ב: Google Tools הפשרה.

### F07 — Voice / IVR
מודל עסקי: White-Glove.

### F08 — SaaS Multi-Tenant
תלוי ב: הכל לפניו.

### F09 — Lead Qualifier Wire-up
מה: חיבור lead_qualifier.handle_lead_message() לתוך run_agent — state machine שאלון לכל ליד WhatsApp.
מצב: **בנוי ובדוק** — lead_qualifier.py קיים ומלא. לא מחובר לפרודקשן.
תלוי ב: N04 (קודם צריך scoring + followup פשוטים). אחר כך להחליט: לחבר או להחליף ב-Claude-native scoring.
קבצים: lead_qualifier.py (קיים), app.py (hook).

### F10 — Lead Memory Wire-up
מה: חיבור lead_memory.update() לתוך lead_capture — זיכרון ארוך-טווח per lead.
מצב: **בנוי ובדוק** — core/lead_memory.py קיים כולל debounce, flush, TTL, feature flag.
תלוי ב: N02 (scoring קודם — אין טעם לזכור ליד ללא ציון).
קבצים: core/lead_memory.py (קיים), lead_capture.py.

### F11 — Followup Engine Full Activation
מה: הפעלת core/followup_engine.py המלא — determine_followup_needed, יצירת טיוטות, שליחה לאישור.
מצב: **תשתית קיימת** — followup_engine.py בנוי. scheduler job קיים (כבוי).
תלוי ב: N04 (N04 הוא גרסת MVP — F11 הוא הגרסה המלאה עם טיוטות וזיכרון).
קבצים: core/followup_engine.py (קיים), scheduler.py.

---

## פערים ידועים (לא באגים — החלטות מודעות)

| פער | סיבה | מתי נטפל |
|-----|-------|----------|
| F09 lead_qualifier — לא מחובר | state machine בנוי, מחכה ל-N04 | F09 |
| F10 lead_memory — לא מחובר | debounce בנוי, מחכה ל-N02 | F10 |
| F11 followup_engine — חלקי | תשתית בנויה, מחכה ל-N04 MVP | F11 |
| core_knowledge.py smoke test false positive | _NEVER_FAKE_CONTROL מכיל פראזה שהtest מזהה בטעות | לתעד כ-known false positive |
| Voice/IVR Twilio signature validation | לא קריטי עד שF07 פעיל | לפני F07 |

---

## כללי ברזל — לא לגעת בלי אישור

1. **Feature flag = כבוי ברירת מחדל.**
2. **app.py — 4 hooks בלבד (H1–H4).**
3. **Agent לא נוגע ב-Airtable ישירות.** תמיד דרך crm.py.
4. **זיכרון ליד = identity.memory_key בלבד.**
5. **מקור אמת לדומיין = detect_domain() בלבד.**
6. **לא בונים batch לפי פיצ'ר — בונים לפי קובץ.**
7. **schema_intelligence.SCHEMA["Leads"] חייב להיות מסונכרן לפני כל כתיבה.**

---

## ארכיב מסמכים

| קובץ | תפקיד |
|------|--------|
| ROADMAP.md | **זה. מקור האמת היחיד.** |
| BOSS_CURRENT_STATE.md | מצב מודולים בפועל |
| CLAUDE.md | הוראות לקלוד קוד — קרא ראשון |
| ARCHIVE_additions_log.md | specs מפורטים A01–A43, היסטוריה |
| SETUP.md | env vars, טבלאות Airtable, הפעלה ראשונה |
