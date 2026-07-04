# Module Rules

## כלל כתיבה לפני הוספת writer/sender/notifier חדש

לפני הוספת writer/sender/notifier חדש — בדוק `ARCHITECTURE_DRIFT_MAP.md` אם הקובץ הזה כבר מסומן לdrift.

---

## Single Source of Authority (SoA)

Every persistent fact, state, calculation, memory, approval, message, or external action must have exactly one declared owner module — its Source of Authority.

Other modules may request, read, or display this data — but must not independently decide, mutate, recompute, send, or execute it unless they are the declared SoA for that item.

**Practical test before writing new code**: "Am I the SoA for this? If not — call the SoA, don't duplicate its logic."

**כלל מעשי לקוד חדש**: לפני שמודול כותב/שולח/מחשב משהו — לבדוק: יש לזה כבר בעל-בית מוצהר? אם כן — לקרוא לו, לא לשכפל את הלוגיקה שלו. אם לא קיים בעל-בית — לתעד את הקובץ הזה כ-SoA זמני ב-`FILE_OWNERSHIP.md`, ולא להניח שזה בסדר שכל מודול יחזיק עותק.

**איתור הפרות (לאודיטים עתידיים)**: כל פעם ש-grep מוצא 2+ קבצים שכותבים/שולחים את אותו דבר (Airtable table, Telegram message, approval state) — זו לא "כפילות נוחה", זו הפרת SoA וצריכה שורה ב-`ARCHITECTURE_DRIFT_MAP.md`.

---

## חוק 11 — כתיב שמות שדות ב-airtable_schema.py

**העיקרון:** הקוד מחקה את Airtable. לא ההיפך.
מה שרשום ב-Airtable — זה המחרוזת בקוד. בלי יצירתיות.

| סוג | פורמט | דוגמה |
|---|---|---|
| שם שדה עסקי (אנגלית) | Title Case | `"Project Name"`, `"Status"`, `"Notes"` |
| שם שדה עברי | כפי שב-Airtable | `"שם העסקה"`, `"סטטוס"` |
| ערך Single Select | Title Case | `"Active"`, `"In Progress"` |
| שם טבלה | כפי שב-Airtable | `"משימות (Tasks)"`, `"Projects"` |
| שדה טכני/פנימי | lowercase | `"tenant_id"`, `"slug"`, `"mode"` |
| טבלת Leads (חריג) | כפי שנוצר — לא נוגעים | `"phone"`, `"Score"`, `"status"` |

**כללי עבודה:**
- ספק לגבי כתיב? → פתח את Airtable ובדוק. אסור לנחש.
- שדה חדש נוצר ב-Airtable → אחר כך מגדירים ב-schema. לא הפוך.
- אין "נרמול" של שמות ישנים בלי PR מפורש שמתקן גם את Airtable וגם את הקוד באותו commit.

---

## חוק 7 — הפרדת ליבה↔פלאגאין (Ports)

פיצ'ר חדש לא מייבא תשתית ישירות.
```
❌ אסור:  import airtable_gateway / memory / llm  בתוך לוגיקת הפיצ'ר.
✅ נכון:  הפיצ'ר מדבר דרך Port/Interface. נקודת הזרקה אחת
          (build_*_ports) היא היחידה שמכירה את התשתית הקונקרטית.
```
זה מרחיב את חוק 3 (כיוון תלויות): לא רק "עסקי→טכני", אלא "דרך interface".
תואם F08/F13. הפרה = חוב טכני ש-V4 ידרוש לפרק.
בדיקה: `grep -c "import <infra>" <feature>.py` = 0 בליבה.

**מקור:** התגלה תוך כדי בניית Decision Hub (יוני 2026) — היה משתמע, עכשיו מפורש.
**דוגמה קיימת:** `decision_ports.py` (`DecisionPorts`, `build_default_ports`).

## חוק 8 — הפרדת כלי↔גייט

שער (gate) ≠ כלי (tool).
```
כלי:   מקבל קלט, מבצע פעולה, מחזיר פלט. (חוק 4)
שער:   מחליט אם להמשיך. מחזיר חוזה אחיד (GateResult/VerifyResult).
       שערים מאחורי registry דקלרטיבי (_GATE_REGISTRY / register_gate),
       מראה את _REGISTRY ב-tool_registry.
```
פונקציה אחת לא גם מחליטה וגם מבצעת. ב-multi-tenant, שערים = plugins.

**מקור:** התגלה תוך כדי בניית Decision Hub (יוני 2026).
**דוגמה קיימת:** `decision_pipeline.py` (`GateResult`, `_GATE_REGISTRY`, `register_gate`).

## חוק 9 — Input Precedence

כל ערוץ קלט (קובץ/הודעה/קולי/אימייל) יש לו handler דיפולטי.
```
לפני הוספת יעד שני לקלט → מפה את ה-handler הקיים.
הגדר precedence מפורש: context ייעודי פעיל מנצח את הדיפולט.
handler דיפולטי ממשיך כרגיל כשאין context.
```
מקור: התנגשות Drive↔Decision Inbox — קובץ נחטף ל-Drive לפני שה-Inbox ראה.

**תוספת (03/07/2026) — UTM Attribution Injection:**
`inject_source_to_incoming_lead` (`ad_attribution.py`, קריאה יחידה מ-`app.py:2162`)
פועל **לפני** `route_request()` בכוונה — זה לא bypass שדורש תיקון. מאומת:
1. עדכון-בלבד על ליד קיים (`airtable_update`) — לעולם לא יוצר Lead.
2. נוגע רק בשדות `utm_source`/`utm_medium`/`utm_campaign`/`platform`.
3. 0 חפיפת שדות עם Router / `capture_router.py` / `lead_candidate_handler.py`.
4. מאחורי `AD_ATTRIBUTION` (נבדק דרך `_flag_enabled("AD_ATTRIBUTION")`, כבוי כברירת
   מחדל — לא רשום ב-`_DEFAULTS` ב-`feature_flags.py`).

אם קוד עתידי יגע באותם שדות דרך Router/LCH — grep מחדש נדרש לפני merge, כדי לוודא
שהיעדר-החפיפה עדיין נכון. ראה `BUG_AUDIT_LOG.md` → BUG-060.

## חוק 10 — Raw-First, Never Interrogate

```
כל קלט נשמר גולמי מיד, לפני פרסור.
ניחוש קורה אחרי — על רשומה קיימת.
המערכת: מנחשת + יוצרת טיוטה + נותנת לתקן. לא חוקרת.
מקסימום שאלה אחת, ורק אחרי שהגולמי נשמר.
```
עיקרון-על: BOSS never deletes signal — only down-ranks. גולמי תמיד נשמר.

## חוק 12 — Domain-Agnostic Core (כביש אחד, יציאות רבות)

> **הערת מספור:** במקור הוצע מסמך חוץ (`MODULE_RULES_additions.md`, יוני 2026) כ"חוק 11" —
> מתנגש עם חוק 11 הקיים מעלה (כתיב שמות שדות ב-airtable_schema.py, e06dc3d). מוספר כאן
> מחדש כחוק 12 כדי לשמר רצף יחיד בקובץ זה.

ישות הליבה זהה לכל דומיין וכל ייעוד.
```
כביש אחד:   Input → Memory → Understanding → 5 שערים → Decision/Action
יציאות:     דומיין (נדל"ן/רפואה/נישואין) = שדה + vocabulary.
            כלי (Drive/voice/email)       = port adapter.
            ייעוד (עו"ד/רופא/יזם/זוג)     = tenant config.
❌ אסור:  ישות חדשה לדומיין (MedicalDecision/MarriageDecision).
✅ נכון:  Decision אחד. domain = ערך ב-select. אפס קוד חדש לדומיין.
```
מבחן: "האם זה עובד גם לרופא וגם לחתונה?" — אם לא, בנית feature במקום core.
זה שאלה 2 ("נפתר במקום אחר?") בקנה מידה של דומיינים שלמים.
תואם V4: אותו קוד לכל tenant. ה-tenant בוחר vocabulary + providers בלבד.

**מקור:** התגלה תוך כדי בניית Decision Hub (יוני 2026) — היה משתמע, עכשיו מפורש.
**דוגמה קיימת:** `Decision` (decision_pipeline.py) — ישות אחת, ללא תת-מחלקות לדומיין.

## חוק 13 — קריאות AI הן Lazy + Cached, לעולם לא Eager על ingest

```
❌ אסור:  קריאת LLM שרצה אוטומטית בכל כתיבת/קליטת רשומה (event/lead/message).
✅ נכון:  קריאת LLM רצה רק בפעולת קריאה/refresh מפורשת, מוגבלת בסקופ
          (אותו topic/cluster, סף trust/quality), deduped לפי hash של הזוג/הקלט,
          ומוגבלת במספר קריאות לריצה (cap).
```
קליטת מידע (ingest) לא תלויה אף פעם בזמינות/תקציב/latency של ה-LLM — רשומה חדשה
נכתבת תמיד, גם אם ה-AI איטי/נכשל/חסום. ה-AI הוא שכבת אינטליגנציה *מעל* הדאטה
הקיים, לא שער שהדאטה צריך לעבור כדי להיכתב.

מבחן: "אם Claude למטה לגמרי, האם ingest עדיין עובד?" — אם לא, יש הפרה של החוק.

**מקור:** תנאי האישור המפורש של הבעלים ל-Decision Hub Stage 2 / F17 (Smart Trust
Layer, יוני 2026) — "AI Conflict Detection יהיה Lazy + Cached, לא Eager. קליטת
Event לא תלויה ב-Claude." הועלה לחוק כללי כי העיקרון רלוונטי לכל מודול שמשלב LLM
על דאטה שכבר נכתב (לא רק Decision Hub).
**דוגמה קיימת:** `detect_conflicts_ai_lazy()` (`decision_confidence.py`) — רץ רק
מ-`/decision status`, מסונן ל-Claim Topic זהה + Trust>=T1, cache לפי
`event_pair_hash`, מוגבל ל-5 קריאות Claude חדשות לריצה.
