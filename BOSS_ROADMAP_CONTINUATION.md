# BOSS — המשך תוכנית העבודה
**מסמך זה הוא המשך ישיר של ROADMAP.md — לא מחליף אותו.**
**Owner:** אליהו | **עודכן:** יוני 2026
**מקור אמת לצד:** ROADMAP.md · BOSS_CURRENT_STATE.md

---

## למה המסמך הזה קיים

ROADMAP.md מתמקד בנבנה ובנמצא. כאן יושב **מה שמגיע אחר כך** —
Core Validation Phase שמאמת את המנוע לפני שמוסיפים עליו,
המודולים העסקיים שנשענים על הליבה,
והשלבים הרחוקים שצורתם כבר ברורה.

---

## עיקרון מנחה — One Road, Many Exits

```
              ┌─────────────────────────────────────┐
              │           הכביש (CORE)              │
              │  Input → Memory → Understanding →   │
              │  5 Gates → Decision / Action        │
              └─────────────────────────────────────┘
                 │         │         │         │
            ┌────┘    ┌────┘    ┌────┘    └────┐
         דומיינים    כלים     ייעודים      ערוצים
         (יציאות)  (יציאות)  (יציאות)    (יציאות)
```

כביש אחד — ליבה חזקה ואחידה. כל השאר — התאמות יפות.

תהליך קבלת ההחלטה זהה בכל מקום: עסקה, גיוס עובד, קניית דירה.
אותם שלבים, אותם שערים, אותה ליבה. ה-vocabulary בלבד משתנה.

**הסכנה היחידה:** לבנות MedicalDecision / LeadDecision / VentureDecision בנפרד.
התוצאה — 3 מערכות. השמירה — ישות אחת. דומיין = שדה. תמיד.

---

## מפת השלבים — מבט-על

```
Stage 0  ✅  Core הקיים (Input / Routing / Memory / Output / Approval)
             ↓
Stage 0-V    Core Validation — אימות המנוע לפני שמוסיפים עליו
             ↓
Stage 1      5 Gates — Delta / Entity / Trust / Readiness / Risk
             ↓
Stage 2  ✅  Decision Hub — Stages 0-6 מוזגו
             ↓
Stage 3      Lead Management — Lead, Scoring, Attribution, Followup
             ↓
Stage 4      Revenue — Attribution, Partner, Digest מלא
             ↓
Stage 5      UI — Command Center, Knowledge Hub, Ventures
             ↓
Stage 6      Future — SaaS, Learning, Multi-Tenant, WhatsApp Production
```

**ההיגיון:** Decision Hub, Leads, Ventures — כולם *משתמשים* באותו מנוע.
אף אחד מהם לא *בונה* מנוע נפרד. לכן המנוע חייב לעמוד לפני שהם נבנים.

---

## חוקי המבנה (MODULE_RULES 1–11)

```
1   גידור פיצ'ר — כל פיצ'ר חדש מאחורי flag, כבוי ברירת מחדל
2   רזון app.py — 4 hooks בלבד (H1–H4), לא לוגיקה עסקית
3   כיוון תלויות — Business → Core, לא הפוך
4   כלים בלי state — כל tool stateless, state ב-session_store בלבד
5   מקור אמת יחיד — ROADMAP.md ראשון, BOSS_CURRENT_STATE.md שני
6   memory לא מפעיל LLM — lead_memory/session_store ל-state בלבד
7   הפרדת ליבה↔פלאגאין — DecisionPorts (decision_ports.py)
8   הפרדת כלי↔גייט — _GATE_REGISTRY, לא import ישיר
9   Input Precedence — context מנצח default (קובץ > session > ברירת מחדל)
10  Raw-First, Never Interrogate — קולטים קלט גולמי לפני עיבוד
11  Domain-Agnostic Core — כביש אחד, יציאות רבות
```

**5 שערי תכנון (PLANNING_GATE) — לפני כל קוד:**
```
1. האם הרכיב שייך לליבה או לפלאגאין?
2. האם הכלי נרשם ב-registry ועובר דרך gateway?
3. האם precedence מוגדר? (מה מנצח מה?)
4. האם Raw-First? (לא מנתחים לפני שקולטים)
5. מבחן הכביש האחד — עובד לרופא ולחתונה?
```

---

# STAGE 0-V — Core Validation Phase

> **לפני כל קוד חדש — המנוע הקיים עובר אימות.**
> Stage זה אינו בנייה. הוא הוכחה שמה שנבנה אכן עובד.
> Definition of Done לכל סעיף: evidence מפרודקשן, לא py_compile.

---

## V0 — Validate Processing (Input → Router → Response)

**מה בודקים:** שליחת הודעה אמיתית → הסוכן מנתב נכון → תשובה נשלחת.

**בדיקות:**
1. Telegram: שלח "שלום" → BOSS עונה בעברית, ללא timeout, ללא שגיאה
2. WhatsApp (Twilio): שלח הודעה → webhook מתעורר → run_agent רץ → תשובה
3. כשל מכוון: הפסק ANTHROPIC_API_KEY → BOSS מחזיר הודעת fallback בעברית (BUG-011)
4. Render hash מסונכרן ל-main — לא commit קודם

**קבצים:** `app.py`, `core/router/`
**Evidence נדרש:** לוג Render + screenshot הודעה נשלחת + תשובה

---

## V1 — Validate Understanding (Domain / Intent / Context)

**מה בודקים:** שהסוכן מזהה נושא, כוונה, ומי מדבר.

**בדיקות:**
1. שלח "אני מעוניין לקנות דירה ב-3 חדרים" → domain=real_estate, intent=lead
2. שלח "/decision חדש" → domain=decision, routing לcmd_decision
3. שלח "#מחקר: מה מחיר ממוצע לדירה?" → model=Sonnet (research mode)
4. ליד לא מזוהה (unknown number) → role=LEAD, לא OWNER

**קבצים:** `core/router/`, `identity.py`, `context.py`
**Evidence נדרש:** לוג עם domain/intent/role לכל הודעה

---

## V2 — Validate Memory (Session + Business Memory)

**מה בודקים:** שהמערכת זוכרת בין הודעות ובין sessions.

**בדיקות:**
1. שלח הודעה א' → שלח הודעה ב' שמתייחסת לא' → BOSS מבין את הקשר
2. שלח "זה הנספח" אחרי העלאת קובץ → BOSS מקשר נכון (C60 context pronouns)
3. Render restart → שלח הודעה → session_store קורא מ-Airtable Sessions (C58) ולא מ-RAM
4. /update "פגישה עם ספק ריהוט" → Business Memory נכתב ב-Airtable

**קבצים:** `session_store.py`, `cmd_update.py`, `memory_store.py`
**Evidence נדרש:** רשומה ב-Sessions table + Business Memory table לאחר בדיקה 3/4

---

## V3 — Validate Conversation (Multi-turn / Followup / Approval)

**מה בודקים:** שהמערכת מנהלת שיחה רציפה, לא רק הודעות בודדות.

**בדיקות:**
1. שיחת ליד 3 סיבובים: שאלה → תגובה → הבהרה → BOSS מבין את ההקשר המלא
2. פעולה שדורשת אישור: owner מבקש פעולה → alert נשלח → owner מאשר → פעולה מתבצעת
3. reject: owner דוחה → פעולה לא מתבצעת (לא רק "rejected" בלוג — לא נכתב ל-Airtable)
4. /cancel באמצע זרימה → state מתנקה נכון

**קבצים:** `app.py`, `event_bus.py`, `session_store.py`
**Evidence נדרש:** Airtable audit log לפעולה שאושרה + אימות שreject לא כותב

---

## V4 — Validate Output (Consistency / Safety / Formatting)

**מה בודקים:** שכל פלט עובר דרך הגייטים הנכונים ומגיע נקי.

**בדיקות:**
1. Anti-hallucination: BOSS לא יאמר "מצאתי קובץ ב-Drive" בלי search_drive בפועל (A32/BUG-014)
2. COG: שליחה ללקוח עוברת דרך output_gateway.py — לא ישירה מה-business logic
3. Mojibake: כל הודעות עברית מגיעות תקינות (BUG-018 תוקן — לאמת בפועל)
4. Emergency Stop: הפעל EMERGENCY_STOP → אפס הודעות יוצאות

**קבצים:** `core/output_gateway.py`, `core/anti_hallucination.py`, `app.py`
**Evidence נדרש:** screenshot הודעות עברית תקינות + לוג COG לכל שליחה

---

## V5 — Validate Five Gates (Trust / Risk / Approval)

**מה בודקים:** שהשערים הקיימים עובדים end-to-end לפני שמוסיפים שערים חדשים.

**בדיקות:**
1. Gate Trust (שער 3): `/decision חדש` עם מסמך → trust score נכתב ל-Airtable
2. Gate Risk (שער 5 — Approval): PATCH ל-Airtable דרך TMA → עובר approval, לא ישיר
3. Emergency Window: `EMERGENCY_WINDOW=true` → High-risk action מהטלפון מחכה ל-OTP
4. Feature Flag: כבה flag פעיל → התנהגות חוזרת ל-baseline, אפס שבירה

**קבצים:** `decision_pipeline.py`, `tma_api.py`, `core/emergency_window.py`, `feature_flags.py`
**Evidence נדרש:** decision event ב-Airtable עם trust_level + approval receipt

---

> **Stage 0-V Complete** כאשר כל 5 הסעיפים מתועדים עם evidence בפרודקשן.
> רק אז פותחים Stage 1.

---

# CORE — חיזוק הליבה

> רכיבים שמשפרים את המנוע עצמו. לא מודולים עסקיים.

---

## C-CORE-01 — lead_memory Persistence 🔲 PLANNED
**בעיה:** lead_memory הוא RAM בלבד. כל Render restart — context לידים פעילים נמחק.
**פתרון:** lead_memory.flush() → Sessions table (C58 קיים). חיווט קצר.
**תנאי כניסה:** V2 מאומת (Sessions עובד).
**קבצים:** `core/lead_memory.py`, `session_store.py`

---

## C-CORE-02 — Airtable Write Queue 🔲 PLANNED
**בעיה:** rate limit של 5 req/sec. עם followup automation — 429 errors בוא יבואו.
**פתרון:** queue פשוט ב-memory עם background thread, retry אוטומטי על 429, backoff.
**תנאי כניסה:** V3 מאומת (approval flow עובד) + לפני הפעלת FOLLOWUP_AUTOMATION.
**קבצים:** `tools/airtable_gateway.py` (הוספת queue), `scheduler.py`

---

## C-CORE-03 — F12/F13 Architecture Decision 🔲 DECISION REQUIRED
**בעיה:** שני spec-ים סותרים ב-`providers/`. כל sprint שנוגע ב-LLM נתקל בשאלה ועוקף.
**ההכרעה הנדרשת:**
- F13 = SaaS infrastructure בלבד (Storage/Channel adapters)
- F12 = LLM abstraction בלבד (`LLMProvider.generate`)
- הם שכבות שונות — לא סותרים, משלימים
**פעולה:** לרשום החלטה ב-ROADMAP ולסגור. לא לבנות כלום — רק לתעד.
**קבצים:** `ROADMAP.md` (הוספת החלטה), `providers/` (אם נמחק F13)

---

## C-CORE-04 — N10: Rollback אוטומטי 🔲 PLANNED
**תלוי ב:** N08 CI/CD (הושלם).
**מה:** rollback אוטומטי ל-commit יציב כש-health check כושל אחרי deploy.
**עד שמיושם:** manual gate בלבד (RELEASE_CHECKLIST.md).
**קבצים:** `scheduler.py`, `.github/workflows/ci.yml`

---

# BUSINESS MODULES — מודולים עסקיים

> כל מודול עסקי *משתמש* בליבה. אף אחד לא *בונה* לוגיקה מקבילה.
> סדר: 5 Gates → Decision Hub → Leads → Revenue.

---

## BM-01 — 5 Gates: Delta (שער 1) 🔲 PLANNED
**מה:** "מה השתנה מהידוע?" — זיהוי אוטומטי של מידע חדש שמשנה תמונה קיימת.
**בניה מעל:** Entity (שער 2, קיים) + Trust (שער 3, מוזג).
**פלט:** `delta_detected: bool`, `changed_fields: list`, `impact_level`.
**קבצים:** `decision_delta.py` (חדש), `decision_pipeline.py`
**Feature Flag:** `FEATURE_DECISION_HUB`

---

## BM-02 — 5 Gates: Readiness Engine (שער 4) 🔲 PLANNED
**מה:** "האם יש מספיק מידע להחליט?"
מחשב לפי `REQUIRED_EVIDENCE` (מ-F17 Stage 2) כמה ראיות חסרות ומה הסוג שחסר.
**פלט:** `ReadinessScore` (0–1), `missing_by_type`, `recommended_next_step`.
**אינטגרציה:** `_format_decision_card()` — "מה צריך לפני שמחליטים".
**קבצים:** `decision_readiness.py` (חדש), `decision_pipeline.py`, `cmd_decision.py`
**Feature Flag:** `FEATURE_DECISION_HUB`

---

## BM-03 — Decision Hub: Attention Engine (Stage 4) 🔲 PLANNED
**תלוי ב:** BM-02 (Readiness Engine).
**מה:** job יומי שסורק החלטות פתוחות ומדרג לפי דחיפות:
- Deadline < 7 ימים → alert
- ReadinessScore > 0.8 → "מוכן להחלטה"
- קונפליקט לא פתור → "דורש בירור"
**פלט:** 3 החלטות הדחופות ביותר — daily push לowner.
**קבצים:** `decision_attention.py` (חדש), `scheduler.py`
**Feature Flag:** `FEATURE_DECISION_ATTENTION` (חדש)

---

## BM-04 — Lead Source Attribution End-to-End 🔲 PLANNED
**תלוי ב:** V0 (Processing מאומת) + LEAD_CAPTURE=true בפרודקשן.
**מה:**
1. `TRAFFIC_SOURCES` — טבלת Airtable: `Source Code`, `Channel`, `Campaign`, `Partner`
2. כל ליד מקבל `source_code` (UTM / referral / ידני)
3. Revenue Attribution: Deal/Payment → Origin Lead (C55 קיים) → source_code
4. דוח שבועי: source → leads → hot → deals → revenue
**קבצים:** `lead_capture.py`, `airtable_schema.py`, `daily_digest.py`

---

## BM-05 — Partner Attribution 🔲 PLANNED
**תלוי ב:** BM-04.
**מה:** ROI לשותפים — referral_code, source_code ייחודי לכל שותף, דוח partner → revenue.
**tech effort:** נמוך — Airtable + ידני בעיקר.
**קבצים:** `airtable_schema.py` (Tables.PARTNERS), `crm.py`, `daily_digest.py`

---

## BM-06 — Followup Engine Full Activation 🔲 PLANNED
**מצב:** תשתית קיימת (F11 — `followup_engine.py`, scheduler job כבוי).
**תלוי ב:** C-CORE-01 (lead_memory persistence) + C-CORE-02 (write queue).
**מה:** גרסה מלאה — טיוטות, זיכרון, הצעות לowner.
**קבצים:** `followup_engine.py`, `scheduler.py`
**Feature Flag:** `FOLLOWUP_AUTOMATION`

---

## BM-07 — Ventures: Convert + Notifications 🔲 PLANNED
**הערה:** N06 (Ventures screen) מוזג. זה מה שנותר.
**מה:**
- Convert Venture → Deal / Project / Campaign (דרך Approval Gate)
- Owner notification כשVenture עובר Stage
**קבצים:** `Ventures.tsx`, `tma_api.py`, `scheduler.py`
**Feature Flag:** `FEATURE_VENTURES_NOTIFICATIONS` (חדש)

---

## BM-08 — F14: Contact Gate 🔲 PLANNED
**מה:** `find_or_create_contact(phone, name, **fields) → (record_id, created: bool)`.
**Piggyback Trigger:** בפגישה עם המרת ליד → contact.
**קבצים:** `crm.py`

---

## BM-09 — F15: crm.py Write Path Migration 🔲 PLANNED
**מה:** החלפת `_post`/`_patch` ישירים ב-`crm.py` בקריאות ל-`airtable_gateway`.
**Piggyback Trigger:** בפגישה עם BM-08.
**קבצים:** `crm.py`, `airtable_gateway.py`

---

## BM-10 — F52: Tool Architecture Refactor 🔲 PLANNED
**מצב:** 4 מסמכי audit מוזגים (docs/f52/). אפס שינוי קוד.
**תנאי כניסה:** Stage Revenue יציב (BM-04/05).
**מה שיבוא:** סגירת high-risk bypasses לפי F52_BYPASS_MAP.md.
**קבצים:** `crm.py` (→BM-09), `lead_conversion.py`, dispatcher

---

# REVENUE — לולאת הכסף

> כאן מודדים. כל מה שלפני — מאפשר מדידה. זה מה שמצדיק את הכל.

---

## RV-01 — Command Center MVP 🔲 PLANNED
**תלוי ב:** BM-04 (Attribution), BM-07 (Ventures), C56 מאומת.
**מה:** מיזוג OCC + Hub + Daily Digest → מסך אחד.

```
┌─────────────────────────────┐
│ BOSS BAR (World + Streak)   │
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

**מה לא ב-v1:** Value Meter, KPI מורחב, Ventures Pulse.
**קבצים:** `OwnerControlCenter.tsx`, `tma_api.py`

---

## RV-02 — Knowledge Hub 🔲 PLANNED
**תלוי ב:** RV-01.
**מה:** שדרוג ActivityFeed → Relationship Hub:
- אנשי קשר לפי תפקיד (ספקים / עו"ד / משקיעים)
- היסטוריית אינטראקציות לכל קשר
- Business Memory + Learnings מקושרים
**קבצים:** `ActivityFeed.tsx` → `KnowledgeHub.tsx`, `tma_api.py`

---

## RV-03 — Lead Recovery 🔲 PLANNED
**תלוי ב:** N04 Followup (מוזג).
**מה:** לידים שדעכו → זיהוי → הצעת פנייה מחדש.
**קבצים:** `lead_recovery.py` (חדש), `scheduler.py`

---

# FUTURE — שלבים רחוקים

> לא בונים עד שהתפעול מבוסס לחלוטין.
> תיעוד כאן = שמירת הכיוון, לא התחייבות לזמן.

---

## F-01 — Learning Engine
**תלוי ב:** כמה חודשי דאטה אמיתי + N04.
**מה:** לומד מ-lead_events — מה סגר עסקאות, מה לא, דפוסי התנגדויות.

## F-02 — Revenue Attribution מתקדם
**תלוי ב:** BM-05, F-01.
**מה:** multi-touch attribution, cohort analysis, LTV.

## F-03 — KPI Engine
**תלוי ב:** C21 Digest, F-02.
**מה:** conversion rates, CAC, עסקאות חזויות.

## F-04 — WhatsApp Production (Meta Cloud API)
**חסם:** אישור Meta Cloud API.
**תנאים לפני הפעלה:** COG (C52) + C56 פעילים + audit per send + source tracking.

## F-05 — Email Channel (Inbound)
**תלוי ב:** Google Tools + LEAD_CAPTURE=true. שני דגלים חייבים יחד.

## F-06 — Voice / IVR
**תלוי ב:** F-04. מודל עסקי: White-Glove.

## F-07 — SaaS Multi-Tenant
**תלוי ב:** הכל לפניו + C-CORE-03 (F12/F13 הכרעה).
**מה:** Tenant isolation, TenantConfig loader, Airtable per-tenant.

## F-08 — Lead Qualifier Wire-up
**מצב:** `lead_qualifier.py` בנוי. לא מחובר.
**תלוי ב:** N04. אחר כך: לחבר או להחליף ב-Claude-native scoring — להחליט.

---

## Business Management Layer — מה מגיע הרבה אחר כך

המערכת היום = **Operating Layer** (שלב 5–6 מתוך 8).

| שלב | תיאור | מצב |
|-----|--------|------|
| 1. Opportunity Pipeline | Ventures | ✅ N06 מוזג |
| 2. Deal Evaluation | שמאי / עו"ד / מיסוי | ❌ לא מתועדף |
| 3. Demand Research | שוק / מתחרים / תמחור | ❌ לא מתועדף |
| 4. Deal Structuring | מימון / שותפים / מבנה רווחים | ❌ לא מתועדף |
| 5. Marketing & Sales | לידים / פולואפים / קמפיינים | ✅ הליבה הקיימת |
| 6. Execution | חוזים / גבייה / תשלומים | 🟡 חלקי |
| 7. Profit Distribution | חלוקת רווחים | ❌ לא מתועדף |
| 8. Capital Management | מעקב הון | ❌ לא מתועדף |

**החלטה מ-13/06/2026 — נשמרת:** שלבים 2–4, 7–8 לא נוגעים עד שהתפעול מבוסס.

---

## מה לא עושים עכשיו

1. לא פותחים Business Module לפני Stage 0-V Complete.
2. לא בונים Multi-Tenant לפני שהמערכת עובדת בשוכר יחיד.
3. לא בונים Learning Engine לפני כמה חודשי דאטה אמיתי.
4. לא מחברים F12/F13 לפני C-CORE-03 (הכרעה).
5. לא מפעילים WhatsApp outbound לפני Gateway + Meta + audit.
6. לא מסמנים ✅ בלי production evidence.

---

## סדר ביצוע — הכביש המלא

```
Stage 0-V  ←  עכשיו
           V0 Processing → V1 Understanding → V2 Memory
           → V3 Conversation → V4 Output → V5 Gates

Core       ←  במקביל ל-Stage 0-V
           C-CORE-01 Memory Persistence
           C-CORE-02 Write Queue
           C-CORE-03 F12/F13 Decision

Business   ←  אחרי Stage 0-V Complete
Modules       BM-01/02 Delta + Readiness Gates
              BM-03 Attention Engine
              BM-04/05 Lead Attribution + Partners
              BM-06 Followup Full
              BM-07/08/09 Ventures + Contacts + CRM

Revenue    ←  אחרי Business Modules יציבים
              RV-01 Command Center
              RV-02 Knowledge Hub
              RV-03 Lead Recovery

Future     ←  אחרי revenue loop מוכח
              Learning → KPI → WhatsApp → SaaS
```

---

## ארכיב מסמכים

| קובץ | תפקיד |
|------|--------|
| `ROADMAP.md` | **מקור האמת היחיד** — C/N/F הנוכחיים |
| `BOSS_ROADMAP_CONTINUATION.md` | **זה** — Core Validation + Business Modules + Future |
| `BOSS_CURRENT_STATE.md` | מצב מודולים בפועל |
| `CLAUDE.md` | הוראות לקלוד קוד — קרא ראשון |
| `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md` | שכבת-על: חזון, ממשל, 9 שאלות לכל מודול |
| `archive/BOSS_MASTER_PLAN_One_Road.md` | ARCHIVE — עקרון One Road (גוף הועתק לכאן) |
