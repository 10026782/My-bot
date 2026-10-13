# SPEC — Insight → Decision → Task (השלמת Decision Hub, שני צעדים)

**סטטוס:** DRAFT — ממתין לאישור בעלים. לא מומש. אין קוד, אין שינוי Airtable, אין PR.
**בסיס:** `origin/main` @ `5e20e60` (אודיט 13/10/2026).
**מסמך אב:** `docs/specs/DECISION_HUB_MASTER_SPEC.md` — ספק זה הוא **חלוקת משנה ל-Stage 6 (Closure)** ולהרחבת Stage 0 (Inbox), לא ספק מתחרה. אם יש סתירה — המסמך האב קובע, ויש לעדכנו.
**החלטת בעלים שהתקבלה:** כיוון מינימלי; בלי טבלת מחקר חדשה; בלי מנוע החלטות חדש; `Learnings & Insights` = מקור התובנות; `Tasks` = מעקב ביצוע; בלי כתיבה אוטומטית ובלי החלטות השקעה ללא אישור.

---

## 0. עקרונות מחייבים

1. **Reuse before build.** כל שדה/טבלה/פונקציה קיימים נמחזרים. מתווספים לכל היותר 2–3 שדות Airtable (ראו §4).
2. **מקור אמת יחיד.** תובנה חיה ב-Learnings. החלטה ב-Decisions. ביצוע ב-Tasks. אין שכפול סטטוסים: סטטוס המשימה נקרא מ-Tasks בזמן תצוגה, לא מועתק להחלטה.
3. **אין כתיבה בלי אישור מפורש** של משתמש מורשה (כפתור אישור קשור לטוקן, כמו `dec_new_confirm`). אין אוטומציה שיוצרת החלטה, סוגרת החלטה או יוצרת משימה.
4. **המערכת לא מחליטה.** היא מרכזת ראיות, מראה מה חסר, ומתעדת מי אישר. אין המלצת קנייה/מכירה ואין ביצוע עסקאות.
5. **כל כתיבה דרך המנגנונים הקיימים:** `DecisionPorts` → `tools/airtable_gateway.py` להחלטות; Action Gateway / Golden Writer למשימות. אין import ישיר של שכבת הכתיבה.
6. **Flag כבוי כברירת מחדל.** צעד 1 תחת `FEATURE_DECISION_HUB` הקיים. צעד 2 תחת flag חדש אחד, `FEATURE_DECISION_CLOSE` (כבוי).

## 1. מצב נוכחי (ראיות מהאודיט)

| יכולת | מצב | ראיה |
|---|---|---|
| קלט טקסט → Inbox → Event | `CODE_EXISTS` | `cmd_decision.py::_handle_forward`, `_link_inbox_to_decision` |
| קישור תובנה ↔ החלטה | `NOT_IMPLEMENTED` | אין קוד שקורא `Tables.LEARNINGS`; אין שדה קישור |
| עמדת מייעץ אחרי יצירה | `NOT_IMPLEMENTED` | `_create_stakeholder` יוצר `ממתין/ממתין` ולא מתעדכן |
| סגירת החלטה (`Decided Yes/No`, `Final Decision`, מי אישר) | `NOT_IMPLEMENTED` | אין כתיבה ל-`DecisionStatus.DECIDED_*` מחוץ ל-`core/adapters/leads_adapter.py` |
| החלטה → משימה | `NOT_IMPLEMENTED` | אין שימוש ב-`DecisionFields.LINKED_TASKS`; ב-`TaskFields` אין קבוע ל-`Decisions` |
| כתיבת Tasks מאומתת (כותרת, dedup, Cadence) | `CODE_EXISTS` | `core/task_writer.py`, `core/action_gateway.py::complete_task_proposal`, `tools/dispatcher.py::_DEDUP_FIELDS` |

סכמה חיה (Airtable MCP, קריאה בלבד, 13/10/2026): ל-Learnings יש `Business Memory` (קישור), `Outcome`, `Next Action`, `domain`, `source`; **אין** `tenant_id` ואין קישור ל-Decisions. ל-Tasks יש כבר `Decisions` (קישור), `Owner`, `תאריך יעד`. ל-Decisions יש `Linked Tasks`, `Linked Memory`, `Final Decision`, `Lessons Learned`.

---

## 2. צעד 1 — תובנה → החלטה (Intake + Provenance)

### 2.1 מטרה
אפשר להפוך תובנה קיימת מ-Learnings לנושא החלטה, עם קישור חזרה למקור, בלי להעתיק ידנית טקסט ובלי ליצור החלטה כפולה.

### 2.2 זרימה
```
/decision from-insight [רמז חיפוש]
  → זיהוי + הרשאה + scope        (כמו /decision הקיים)
  → בחירת תובנה (קריאה מ-Learnings, מסוננת לפי tenant)
  → [בדיקת כפילות — §2.4]
  → כרטיס סקירה: כותרת, תיאור, Next Action, "מה חסר"   [✅ אישור | ↩️ ביטול]
  → אישור:
       a. יצירת פריט Decision Inbox   (Channel=Manual, Raw Input עם סמן מקור)
       b. התאמה להחלטה פתוחה (decision_matching) → "לשייך ל-X?" / "החלטה חדשה"
       c. שיוך → Decision Event (Raw Content כולל "מקור: תובנה <rec id>")
       d. כתיבת קישור Learnings.Linked Decisions
```
החלטה חדשה נוצרת רק דרך `_create_decision` הקיים, עם כותרת מוצעת מהתובנה, אחרי עריכה/אישור של המשתמש (אותו מסך review של `/decision new`).

### 2.3 מקורות ואימות
- ראיות נשמרות כ-Decision Events (טקסט + קישור מקור). אין מחקר חדש ואין חישוב אוטומטי בצעד זה.
- **אזהרה מחייבת:** `_AntiHallucinationVerifierAdapter` הוא stub (`decision_ports.py:112`) ולכן "מאומת" ב-Hub פירושו Authority×Medium בלבד, לא בדיקת תוכן. בכרטיס יוצג תווית **"מחקר פנימי — לא אומת מול מקור חיצוני"** לאירוע שמקורו תובנה. אין לטעון אימות שלא בוצע.

### 2.4 מניעת כפילויות (מתמשך, לא בזיכרון)
- אם ל-`Learnings.Linked Decisions` יש כבר החלטה → מציגים אותה ("כבר קיימת החלטה: X") ולא יוצרים חדשה, אלא אם המשתמש בוחר במפורש "החלטה נוספת".
- סמן מקור ב-Raw Input: `[insight:<recId>]`. לפני יצירת Inbox בודקים (קריאה דרך `list_records`) אם כבר קיים פריט Inbox עם הסמן במצב `Pending`/`Linked`. זה מחליף את `_IDEMPOTENCY_CACHE` בזיכרון רק במסלול הזה; המטמון הקיים לא משתנה.

### 2.5 הרשאות
- אותה בדיקה כמו `/decision`: `identity.is_owner` או `identity.role in DECISION_ALLOWED_ROLES` (`owner|manager|partner`), עם re-check לפני כל כתיבה (כמו `_handle_update_step`).
- scope: תובנה נקראת רק אם `tenant_id` שלה = tenant של ה-identity. **תובנה ללא `tenant_id` נחשבת לא-נגישה (fail closed)** עד שיושלם backfill בידי הבעלים (§4).

### 2.6 שינויי קוד (צפויים)
| קובץ | שינוי |
|---|---|
| `airtable_schema.py` | `LearningFields`: הוספת `LINKED_DECISIONS`, `TENANT_ID` (+ אופציונלית שדות קיימים: `NEXT_ACTION="Next Action"`, `OUTCOME="Outcome"`) |
| `cmd_decision.py` | תת-פקודה `from-insight` + callbacks (`dec_ins_pick`, `dec_ins_confirm`, `dec_ins_cancel`) |
| `decision_insight_source.py` (חדש, קטן, קריאה בלבד) | קריאה/סינון Learnings לפי tenant דרך `tools/airtable_read_adapter` — **לא** מנוע, לא כותב |
| `tests` | ראו §6 |

---

## 3. צעד 2 — סגירת החלטה → משימת ביצוע → תוצאה

### 3.1 מטרה
החלטה מאושרת נסגרת עם תיעוד מי אישר ולמה, ויוצרת (באישור) משימת המשך אחת מקושרת; תוצאת הביצוע נראית בכרטיס ההחלטה.

### 3.2 זרימה
```
/decision close <ref>        (FEATURE_DECISION_CLOSE)
  → הרשאה: owner בלבד לפעולת סגירה   (ראו O1)
  → תנאי קדם: Status ∈ {Open, Pending Input}; קיים ≥1 Event;
      Readiness=READY, או override מפורש עם סיבה שנרשמת
  → בחירת תוצאה: ✅ אשר | ❌ דחה | ⏸ דחה להמשך (נשאר Pending Input, לא נסגר) | 🚫 בטל
  → Final Decision (טקסט חופשי) + Lessons Learned (אופציונלי)
  → משימת המשך (אופציונלית, רק אם התוצאה "אשר"): כותרת, Owner, תאריך יעד, "פעולה הבאה"
  → כרטיס סיכום  [✅ אישור סגירה | ✏️ עריכה | ↩️ ביטול]
  → אישור:
       1. patch Decision: Status, Final Decision, Lessons Learned
       2. Decision Event (Event Type=החלטה): "אושרה ע״י <שם> <חותמת זמן>" — תיעוד המאשר
       3. Business Memory (Event Type=Decision) וקישור ל-Linked Memory   (כמוגדר ב-Stage 6)
       4. אם נבחרה משימה: הצעת משימה ל-Action Gateway (§3.3)
```
אין "מאשר" חדש כשדה: התיעוד הוא Event בציר הזמן (מקור אמת יחיד) + audit log של ה-gateway.

### 3.3 משימה — מסלול מחייב
- נבנית **הצעה קנונית** דרך `core/router/task_builders` ונשלחת ל-`ActionGateway.propose_action` (`tool_name=airtable_add`, טבלת Tasks). עוברת `complete_task_proposal` (Golden Writer: כותרת תקינה, Cadence, אימות קישורים), `tool_registry.enforce`, `action_validator`, ו-approval רגיל. **אין עקיפה, אין יצירת Task ישירה מה-Hub.**
- הקישור להחלטה נקבע **ביצירה**: ההצעה נושאת `Decisions=[<decisionId>]` ולכן payload שאושר = payload שבוצע. הקישור ההפוך (`Decisions.Linked Tasks`) נוצר ע"י Airtable עצמו, בתנאי שזוג השדות אכן מקושר (§4, בדיקה ידנית).
- מחייב שינוי קטן: `TaskFields.DECISIONS_LINK = "Decisions"`, הוספה ל-`_TASK_WRITE_FIELDS`, ואימות מזהה ההחלטה (קיים + באותו tenant) לפני הצעה.
- Owner: רשומת Profile (כמו `TaskFields.OWNER`); תאריך יעד ISO; "פעולה הבאה" נכנסת ל-`תיאור` בשורה ראשונה `פעולה הבאה: …`. שדה חדש אינו נדרש.
- **ללא כפילות:** (א) אם ל-Decision כבר יש `Linked Tasks` פתוחים → מציגים אותם ולא מציעים חדשה בלי "משימה נוספת" מפורשת; (ב) `_DEDUP_FIELDS` לפי כותרת נשאר פעיל; (ג) כותרת כוללת סמן `[decision:<recId>]` בתיאור, כך שאפשר לאתר יתומות.
- אישור הסגירה ואישור המשימה הם שני אישורים נפרדים (הסגירה מתועדת גם אם המשימה נדחתה; הכרטיס מציג "משימת המשך: ממתינה/נדחתה"). ראו O2.

### 3.4 תוצאה חוזרת ל-Decision Hub
- **ללא סינכרון סטטוסים.** `/decision status` מוסיף בלוק "ביצוע": קורא את המשימות המקושרות מ-Tasks (קריאה בלבד) ומציג סטטוס/יעד/Owner בפועל מול מה שתוכנן (`Final Decision` + כותרת/יעד המשימה).
- סימון משימה כ"בוצע" נשאר ב-flow הקיים (`tma_api.py:3272`, Golden Writer). רישום "מה קרה בפועל" = הערת תוצאה שהמשתמש מזין ב-`/decision update` כ-Event רגיל, או `Lessons Learned`.
- סגירת הלולאה בחזרה ל-Learnings: אופציונלי — כתיבת `Outcome` בתובנה המקורית רק אחרי אישור נפרד (O3).

### 3.5 שינויי קוד (צפויים)
| קובץ | שינוי |
|---|---|
| `cmd_decision.py` | `/decision close`, callbacks `dec_close_*`, בלוק "ביצוע" ב-`_format_decision_card` |
| `decision_closure.py` (חדש, קטן) | פונקציות טהורות: בדיקת תנאי קדם, בניית payloads לסגירה/Event/Memory/הצעת משימה. ללא I/O ישיר |
| `airtable_schema.py` | `TaskFields.DECISIONS_LINK` |
| `core/router/task_builders.py` | הרשאת השדה `Decisions` |
| `feature_flags.py` | רישום `FEATURE_DECISION_CLOSE` (default off) בדוקסטרינג ובקוד |

---

## 4. שינויי Airtable (ידניים, בידי הבעלים, additive בלבד)

| טבלה | שדה | חובה | הערה |
|---|---|---|---|
| Learnings & Insights | `Linked Decisions` (קישור → Decisions) | כן | שדה הפוך יווצר ב-Decisions אוטומטית |
| Learnings & Insights | `tenant_id` (טקסט) | כן | נדרש לבידוד; backfill לרשומות קיימות |
| Learnings & Insights | `Research Status` | **לא** — ראו O4 | קודם לבדוק אם `Outcome` הקיים מספיק |

בדיקות ידניות לפני מימוש (ללא כתיבה): (1) ש-`Decisions.Linked Tasks` ו-`Tasks.Decisions` הם אותו זוג קישור; (2) אפשרויות `Learnings.Outcome`; (3) לאחר הוספת שדות — הרצת `schema_audit.py` לרענון `schema_cache.json`.

> **סיכון ידוע:** `airtable_patch` **משמיט בשקט** שדות שאינם ב-`schema_cache.json`. לכן כל כתיבה בצעדים אלה חייבת לבדוק שהשדה נכתב בפועל (קריאה חוזרת) ולהחזיר כישלון גלוי — לא "הצלחה". זה תנאי קבלה (§6).

## 5. Governance

- **Cross-Layer Planning Gate:** סיווג מוצע `FULL` (כתיבה, approval, lifecycle). יש להשלים הערכה לפי `docs/governance/CROSS_LAYER_GOVERNANCE_REVISED_PLANNING_GATE.md` לפני מימוש.
- **Security review** נדרש (`docs/governance/SECURITY_CHECKLIST.md`): נוגע ב-dispatcher/gateway flow ומוסיף כתיבה חדשה ל-Tasks. כולל בדיקות שלילית: cross-tenant, role לא מורשה, callback ישן/מושמט.
- **ROADMAP:** יש להוסיף מזהה ולעדכן את `עודכן:`; לא נבדק במסגרת ספק זה.
- **Rule 15:** אין לדווח "הושלם/פרוס" ללא merge + deploy + אימות בפרודקשן.
- **מחוץ לתחום:** Portfolio Lab (לא קיים בקוד), הרצת חישובי מס, המלצות השקעה, ביצוע עסקאות, כתיבה אוטומטית מכל ערוץ.

## 6. בדיקות וקריטריוני קבלה

בדיקות סקריפט עצמאיות (תבנית `test_*.py` של הריפו, ללא Flask/Anthropic/Airtable אמיתיים):

**צעד 1:** תובנה מ-tenant אחר → נדחית; תובנה בלי `tenant_id` → נדחית; role לא מורשה → נדחה; תובנה עם `Linked Decisions` קיים → מוצגת ההחלטה ולא נוצרת חדשה; הרצה כפולה (כולל אחרי "ריסטארט" — מטמון ריק) → פריט Inbox אחד; כתיבת הקישור נכשלה/הושמטה → דיווח כישלון, לא הצלחה; אין כתיבה כלשהי לפני לחיצת אישור.

**צעד 2:** סגירה ללא Readiness/Events ללא override → נחסמת; לא-owner → נדחה; callback ישן/טוקן שגוי → "התהליך אינו זמין"; סגירה לא יוצרת משימה בלי אישור נפרד של ה-Gateway; ביטול/דחיית משימה משאירה החלטה סגורה ומתועדת; "משימה נוספת" נדרשת במפורש כשיש כבר Linked Task; payload שאושר = payload שנכתב; החלטה שנסגרה פעם לא נסגרת שוב (idempotent).

**תרחיש בדיקה תיאורטי (קרן ההון, מבלי ליצור רשומות):** תובנה "מימוש הפסדי הון לקיזוז מס" → Inbox → החלטה → מייעץ "רו״ח" כ-Stakeholder (נוצר בתור ממתין) → Events עם חוות דעת → סגירה "אשר בדיקה מוגדרת בלבד" → משימה "לקבל חוות דעת רו״ח על …" עם Owner ויעד → הכרטיס מציג ביצוע בפועל.
**פער שנשאר בכוונה:** עדכון Role/Position של מייעץ אחרי יצירה (נשאר ידני ב-Airtable, או חלק מהרחבה עתידית) — ראו O5.

Definition of Done: `CODE_EXISTS` מחייב בדיקות ירוקות + `python3 smoke_tests.py` + CI. `RUNTIME_VERIFIED` מחייב הרצה בסביבה אמיתית אחרי הפעלת flag בידי הבעלים. עד אז: 🟡 CODE DONE, NOT VERIFIED.

## 7. החלטות פתוחות לבעלים

| # | שאלה | המלצה |
|---|---|---|
| O1 | מי רשאי לסגור החלטה? | owner בלבד (פעולה קריטית); הצגה/עדכון נשארים `owner|manager|partner` |
| O2 | שני אישורים (סגירה + משימה) או אישור אחד? | שניים — שומר על "בלי עקיפת Gateway"; אישור אחד דורש החלטת ארכיטקטורה |
| O3 | לכתוב `Outcome` חזרה ל-Learnings? | כן, אחרי אישור נפרד, ורק בסגירה |
| O4 | האם `Learnings.Outcome` מספיק כסטטוס מחקר? | לבדוק אפשרויות; אם לא — שדה select אחד בלבד |
| O5 | לתעד עמדות מייעצים מתוך הבוט? | לא בגרסה זו (נשאר ידני); להוסיף רק אם יתברר צורך |
| O6 | `FEATURE_DECISION_HUB` בפרודקשן | לאמת מצב ב-Render לפני כל תכנון הפעלה (לא אומת באודיט) |

## 8. סדר עבודה מוצע
1. הבעלים: הוספת שדות (§4) + בדיקות ידניות + `schema_audit`.
2. צעד 1 (PR נפרד): `from-insight` + בדיקות.
3. צעד 2 (PR נפרד): `close` + `DECISIONS_LINK` + בדיקות; flag כבוי.
4. הפעלה מבוקרת בידי הבעלים, ורק אז אימות בפרודקשן.
