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

## חוק 10 — Raw-First, Never Interrogate

```
כל קלט נשמר גולמי מיד, לפני פרסור.
ניחוש קורה אחרי — על רשומה קיימת.
המערכת: מנחשת + יוצרת טיוטה + נותנת לתקן. לא חוקרת.
מקסימום שאלה אחת, ורק אחרי שהגולמי נשמר.
```
עיקרון-על: BOSS never deletes signal — only down-ranks. גולמי תמיד נשמר.
