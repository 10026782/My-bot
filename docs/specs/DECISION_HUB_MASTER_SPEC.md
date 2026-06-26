# DECISION HUB MASTER SPEC

## Source of Truth — BOSS Decision Layer

סטטוס: Draft Architecture
מטרה: מקור אמת אחד לכל פיתוח Decision Hub
עיקרון על: לא בונים עוד מערכת צדדית. בונים שכבת Decision בתוך BOSS, על בסיס התשתיות הקיימות.

---

# 1. Vision

Decision Hub נועד לפתור בעיה אחת מרכזית:

כאשר יש החלטות עסקיות מורכבות, עם הרבה הודעות, מסמכים, בעלי עניין, לחצים, גרסאות, טיוטות וסיכונים — אין היום ישות אחת שמחזיקה את תהליך קבלת ההחלטה.

יש Tasks.
יש Deals.
יש Contacts.
יש Business Memory.
אבל אין Decision.

Decision Hub מוסיף ישות חדשה: החלטה מנוהלת.

המטרה אינה “שהמערכת תחליט במקום המשתמש”, אלא:

* לרכז את כל החומר סביב החלטה אחת.
* להפריד בין עובדה חדשה לבין לחץ בלבד.
* לזהות מה חסר כדי להחליט.
* למנוע שכחת פרטים.
* לזהות דפוסי לחץ.
* לתעד למה הוחלט.
* לסגור החלטה לתוך Business Memory.
* לאפשר בהמשך אוטומציה מבוקרת.

---

# 2. Core Principle

## דלת אחת, ערוצים רבים

כל קלט, מכל ערוץ, נכנס קודם ל־Decision Inbox.

```text
מסמך / הודעה / אימייל / וואטסאפ / קולי / ידני
        ↓
Decision Inbox
        ↓
Decision Pipeline
        ↓
Canonical Decision State
        ↓
Business Memory
```

המשתמש לא צריך בזמן לחץ למלא טופס.
הוא צריך לזרוק חומר פנימה — והמערכת תסדר.

---

# 3. Architecture Rule

Decision Hub הוא Pipeline אחד, לא אוסף מנועים מנותקים.

הזרימה הקיימת ב־BOSS:

```text
Input → AI → anti_hallucination → Approval Gate → Write
```

הזרימה החדשה:

```text
Input
  → Decision Inbox
  → Delta Gate
  → Entity Gate
  → Trust Gate
  → Readiness Gate
  → Risk Gate
  → Write
```

כל השערים עובדים לפי אותו חוזה.

---

# 4. Design Principles

## 4.1 Never Delete Signal

BOSS לעולם לא מוחק signal.
הוא רק מוריד דירוג, מסמן, או משאיר ללא השפעה על ה־Canonical State.

דוגמה:

אם שלומי שלח הודעת לחץ בלי עובדה חדשה:

* ההודעה נשמרת כ־Decision Event.
* Delta Type = לחץ.
* Status = Logged.
* אין שינוי בהחלטה.
* אין התראה מיותרת.
* אבל הדפוס נשמר.

מחר ניתן לזהות:
“שלומי לחץ 5 פעמים השבוע בלי להביא עובדה חדשה.”

---

## 4.2 Manual First, Automation Later

Stage 0 מתחיל ידני:

* Forward לבוט.
* נוחת ב־Inbox.
* המשתמש מאשר שיוך.
* רק אחר כך נוצרים Events.

אוטומציה מלאה של WhatsApp/Email מגיעה רק אחרי שהסיווג הידני מוכיח את עצמו.

---

## 4.3 Additive Architecture Only

אין לשבור routes קיימים.
אין להחליף Approval Gate.
אין לבנות Entity Resolution חדש.
אין לשכתב anti_hallucination.

Decision Hub מתחבר לתשתיות קיימות.

---

## 4.4 Reuse Existing Infrastructure

| צורך             | רכיב קיים              |
| ---------------- | ---------------------- |
| Trust            | anti_hallucination.py  |
| Risk / Approval  | Approval Gate          |
| Contact matching | find_or_create_contact |
| Lessons          | Business Memory        |
| בעלי עניין       | Contacts               |
| עסקאות קשורות    | Deals                  |
| משימות המשך      | Tasks                  |
| איסוף יומי       | Collector / Daily Jobs |
| ממשק עתידי       | TMA                    |

---

## 4.5 Multi Tenant First

כל טבלה וכל רשומה חייבת לתמוך ב־tenant_id / Owner.

אסור לבנות משהו שמתאים רק למשתמש יחיד.

---

# 5. Airtable Schema

## 5.1 Table: Decisions

ישות ההחלטה המרכזית.

```text
Title                 Text
tenant_id             Text
Owner                 Link/User/Text
Domain                Select: נדל"ן / ייבוא / גיוס / שותפות / כללי
Estimated Exposure    Currency
Exposure Type         Select: כספי / משפטי / תפעולי / מוניטין
Status                Select: Open / Pending Input / Decided Yes / Decided No / Cancelled
Readiness             Select: READY / NOT_READY
Urgency               Select: אין / שבוע / 48ש / עכשיו
Current Draft #       Number
Risk If Yes           Long Text
Risk If No            Long Text
Missing Info          Long Text
Final Decision        Long Text
Lessons Learned       Long Text
Linked Contacts       Link → Contacts
Linked Deal           Link → Deals
Linked Tasks          Link → Tasks
Linked Memory         Link → Business Memory
Parent Decision       Link → Decisions
Created               Created Time
Updated               Last Modified Time
```

הערה:
Parent Decision לא חובה ב־Stage 0, אבל צריך להופיע בבקלוג/Schema כדי לתמוך בהחלטות שמתפצלות.

---

## 5.2 Table: Decision Events

Timeline + Evidence.

```text
Decision              Link → Decisions
tenant_id             Text
Event Date            DateTime
Event Type            Select: הודעה / מסמך / פגישה / טיוטה / לחץ / עמדה / החלטה
Channel               Select: וואטסאפ / טלגרם / אימייל / מסמך / קולי / ידני
Stakeholder           Link → Contacts
Raw Content           Long Text
Attachment            Attachment
Trust Level           Select: T0 / T1 / T2 / T3
Source Reliability    Select: חוזה / עו"ד / רו"ח / לקוח / שותף / שמועה
Confidence            Number 0-100
Tags                  Multi Select: תמלול_חלקי / עמום / קונפליקט / לחץ_בלבד / חסר_הקשר
Delta Type            Select: עובדה / מסמך / שינוי_עמדה / לחץ / ללא_שינוי
Status                Select: Logged / Draft / Review / Applied / Superseded
Supersedes            Link → Decision Events
AI Summary            Long Text
Created               Created Time
```

הסבר Supersedes:

אם נכנס Event חדש וברור שמחליף Event קודם, לדוגמה:

* אתמול מסמך מטושטש T1
* היום אותו מסמך ברור T2

אז ה־Event החדש מסמן Supersedes → הישן.
לא מוחקים את הישן, רק יודעים שהוא הוחלף.

---

## 5.3 Table: Decision Stakeholders

מפת בעלי עניין לפי החלטה.

```text
Decision              Link → Decisions
tenant_id             Text
Contact               Link → Contacts
Role                  Select: מחליט / מייעץ / מושפע / מתנגד / ממתין
Position              Select: בעד / נגד / ממתין / לא_ידוע
Position Details      Long Text
Last Updated          DateTime
```

---

## 5.4 Table: Decision Inbox

דלת הכניסה.

```text
Raw Input             Long Text
tenant_id             Text
Channel               Select: וואטסאפ / אימייל / מסמך / קולי / ידני / טלגרם
Received              DateTime
Attachment            Attachment
Suggested Decision    Link → Decisions
Match Confidence      Number 0-100
Status                Select: ממתין / שויך / נדחה
Linked Event          Link → Decision Events
Created               Created Time
```

---

# 6. Decision Pipeline

הסדר המחייב:

```text
1. Input
2. Inbox
3. Delta Gate
4. Entity Gate
5. Trust Gate
6. Readiness Gate
7. Risk Gate
8. Canonical Decision State
```

---

# 7. GateResult Contract

כל שער חייב להחזיר אותו מבנה:

```python
class GateResult:
    passed: bool
    reason: str
    next_gate: str | None
    user_flag: str | None
    halt_status: str | None
```

אסור שכל שער יחזיר פורמט אחר.
זה תנאי לתחזוקה פשוטה.

---

# 8. Gate Details

## 8.1 Delta Gate — ראשון

מטרתו: להבין האם הקלט משנה משהו.

סוגי Delta:

```text
עובדה
מסמך
שינוי_עמדה
לחץ
ללא_שינוי
```

כלל חשוב:

Delta בא לפני Entity.

הסיבה:

אם ההודעה היא לחץ בלבד, אין צורך לזהות “איזה שלומי” או לפתור כפילויות אנשי קשר.
שומרים את ההודעה כ־Logged Event, ולא מטרידים את המשתמש.

Stage 0:

* keyword based
* ללא AI classifier
* החלטות פשוטות בלבד

Stage 2:

* AI Delta Classifier

---

## 8.2 Entity Gate

מטרתו: לשייך לגורם הנכון.

משתמש ב־find_or_create_contact הקיים.

אם יש כפילות:

* לא מנחשים.
* שולחים ל־Review Queue.
* המשתמש בוחר.

---

## 8.3 Trust Gate

מטרתו: להעריך אמינות.

משתמש ב־anti_hallucination.py הקיים.

רמות:

```text
T0 — לא אמין / לא ברור / דורש בדיקה
T1 — חלש / חלקי / Draft
T2 — סביר / פנימי / ניתן לשמור
T3 — חזק / ראיה טובה / ניתן לקדם
```

Stage 0:
Trust Gate הוא stub:

```text
passed=True
```

Stage 1:
Trust Gate עוטף anti_hallucination.

---

## 8.4 Readiness Gate

מטרתו: לומר האם אפשר להחליט.

פלט:

```text
READY
NOT_READY
```

אם NOT_READY:

* Missing Info מתעדכן.
* Escalation נרשם.
* לא דוחפים החלטה.

דוגמה:

```text
חסר:
- תגובת עו"ד
- מסמך חתום
- חישוב חשיפה
```

---

## 8.5 Risk Gate

מטרתו: להחליט אם צריך Approval.

משתמש ב־Approval Gate הקיים.

כללי בסיס:

```text
Low Risk → write
Medium Risk → preview
High Risk → confirm required
Critical Risk → owner only
```

אין כתיבה חיצונית או פעולה מסוכנת בלי Approval.

---

# 9. Stage Roadmap

## Stage 0 — Inbox + Schema + Manual Flow

מטרה:
לבנות שלד Decision Hub עובד ידנית.

כולל:

* יצירת 4 טבלאות.
* `/decision new`
* `/decision update`
* `/decision status`
* Forward → Decision Inbox
* שיוך ידני ל־Decision
* יצירת Decision Event
* Delta Gate בסיסי
* Entity Gate בסיסי
* Trust/Readiness/Risk כ־stubs

Definition of Done:

* ניתן ליצור Decision.
* ניתן לשלוח הודעה לבוט והיא נוחתת ב־Decision Inbox.
* ניתן לשייך אותה להחלטה.
* נוצר Event.
* לחץ בלבד נשמר אך לא משנה Canonical State.
* אין מחיקה של signal.
* אין עקיפה של Approval Gate.
* אין Logic כפול מול Contacts.

---

## Stage 1 — Trust Layer

מטרה:
לחבר Trust Gate אמיתי.

כולל:

* wrapper ל־anti_hallucination.py
* Trust Level T0-T3
* Tags
* Confidence
* Review Queue ל־T0
* Draft ל־T1

Definition of Done:

* Event מקבל Trust Level.
* T0 לא נכנס Canonical.
* T1 נשמר כ־Draft.
* T2/T3 ממשיכים לפי כללים.
* אין החלפה של anti_hallucination.

---

## Stage 2 — Delta Classifier

מטרה:
להחליף Delta keyword פשוט ב־AI Classifier מבוקר.

כולל:

* עובדה חדשה
* לחץ בלבד
* שינוי עמדה
* מסמך
* ללא שינוי
* הסבר קצר למשתמש

Definition of Done:

* רוב הודעות הלחץ לא מטרידות.
* עובדות חדשות כן עולות.
* כל Delta נשמר כ־Event.
* אין signal שנמחק.

---

## Stage 3 — Readiness Engine

מטרה:
להבין האם אפשר להחליט.

כולל:

* READY / NOT_READY
* Missing Info
* Escalation
* “מה חסר כדי להחליט”
* המלצה לפנייה לעו"ד/רו"ח/שותף במידת הצורך

Definition of Done:

* כל Decision פתוח יודע מה חסר.
* Daily יכול להציג החלטות תקועות.
* אין דחיפה להחלטה כשחסר מידע מהותי.

---

## Stage 4 — Attention Engine

מטרה:
לזהות תקיעות ודדליינים.

כולל:

* Job יומי
* החלטות תקועות
* גורם ממתין
* Deadline מתקרב
* לחץ חוזר
* דפוסי שינוי עמדה

Definition of Done:

* Daily Digest מציג החלטות שדורשות תשומת לב.
* אין הצפה על אירועים לא חשובים.
* לחץ חוזר מזוהה כדפוס.

---

## Stage 5 — Auto Ingestion

מטרה:
לחבר ערוצים אוטומטיים אחרי שהידני יציב.

כולל:

* WhatsApp listener
* Email ingestion
* Document ingestion
* Voice transcription
* Channel tagging

Definition of Done:

* קלט אוטומטי נוחת ב־Decision Inbox.
* לא נכתב Canonical בלי Pipeline.
* ניתן לכבות Auto-Ingestion ב־feature flag.

---

## Stage 6 — Closure + TMA Screen

מטרה:
לסגור החלטות ולבנות מסך ויזואלי.

כולל:

* Final Decision
* Lessons Learned
* Business Memory write
* Decision Timeline
* Stakeholder Map
* Missing/Risk display
* TMA Decision Screen

Definition of Done:

* החלטה נסגרת עם תיעוד.
* נוצר Business Memory.
* ניתן לראות Timeline.
* ניתן להבין למה הוחלט.

---

# 10. Commands

## `/decision new`

יוצר Decision חדש.

דוגמה:

```text
/decision new
Title: הסכם Blue View
Domain: נדל"ן
Exposure: 500000
Urgency: 48ש
```

---

## `/decision update`

מכניס קלט ידני או משייך Inbox item.

דוגמה:

```text
/decision update
שלומי שוב לוחץ על 50%, בלי מסמך חדש.
```

---

## `/decision status`

מחזיר מצב החלטה.

פלט רצוי:

```text
Decision: הסכם Blue View
Status: Pending Input
Readiness: NOT_READY
Missing:
- תגובת עו"ד
- נוסח סופי
Recent Events:
- לחץ בלבד משלומי
- אין עובדה חדשה
Recommendation:
לא לשנות עמדה כרגע.
```

---

# 11. Forward Flow

זרימה בסיסית:

```text
1. המשתמש מעביר הודעה לבוט
2. ההודעה נשמרת ב־Decision Inbox
3. מנוע 0 מציע Decision
4. המשתמש מאשר שיוך
5. נוצר Decision Event
6. Delta Gate רץ
7. Entity Gate רץ אם צריך
8. Event נשמר
9. Canonical מתעדכן רק אם מותר
```

---

# 12. Example Flow

```text
שלומי שלח:
"אם אתה לא חותם היום אין עסקה."

Pipeline:

Inbox:
Raw Input נשמר.

Delta:
לחץ בלבד.

Entity:
לא נדרש אם אין עובדה חדשה.

Trust:
Stub ב־Stage 0.

Event:
נוצר Event עם Delta=לחץ, Status=Logged.

Canonical:
לא משתנה.

Response:
"העדכון נשמר תחת הסכם Blue View.
סיווג: לחץ בלבד.
אין עובדה חדשה.
לא שיניתי את מצב ההחלטה."
```

---

# 13. Governance Rules

כל פיתוח Decision Hub חייב לעמוד בכללים הבאים:

1. אין מחיקת signal.
2. אין כתיבה ישירה בלי Pipeline.
3. אין פעולה מסוכנת בלי Approval Gate.
4. אין בניית Entity Resolution חדש.
5. אין החלפת anti_hallucination.
6. אין Auto-Ingestion לפני Manual Flow יציב.
7. אין logic כפול.
8. כל שער מחזיר GateResult.
9. כל Stage חייב Definition of Done.
10. כל שינוי חייב להיות additive.
11. כל טבלה חייבת tenant_id.
12. כל החלטה חייבת Owner.
13. כל Event חייב Raw Content.
14. כל Event חשוב נשמר גם אם לא משפיע.
15. כל Status חייב להיות מוסבר למשתמש.
16. כל ספק או בלבול נכנס ל־Review Queue, לא לניחוש.
17. כל Stage נבדק עצמאית.
18. כל פיתוח מתחיל מקריאת מסמך זה.

---

# 14. Non Goals

Decision Hub לא עושה בשלב ראשון:

* החלטה אוטומטית במקום המשתמש.
* שליחת הודעות חיצוניות.
* חתימה על מסמכים.
* שינוי עסקאות בלי אישור.
* חיבור אוטומטי לכל WhatsApp/Email לפני בדיקה ידנית.
* ניתוח משפטי מחייב.
* החלפת יועץ משפטי/רו"ח.

---

# 15. Open Questions

1. האם Decision הוא תמיד עצמאי או לפעמים Child של Deal?
2. האם Parent Decision נכנס כבר ב־Stage 0 או רק בעתיד?
3. האם Stakeholder Position מתעדכן אוטומטית או רק ידנית בהתחלה?
4. האם Decision Inbox הוא טבלה כללית לכל המשתמשים או לכל tenant view נפרד?
5. האם Readiness יכול להציע escalation לגורם ספציפי?
6. האם Daily Digest מציג כל Decision פתוח או רק Urgent/Blocked?
7. מה רף החשיפה הכספית שמחייב Approval?
8. האם Voice transcription נכנס דרך Media Layer הקיים או כ־Stage נפרד?

---

# 16. Future Backlog

לא לבנות עכשיו, רק לשמור:

* Parent Decision
* Decision Merge
* Decision Split
* Decision Graph
* Pattern Detection
* Negotiation Analytics
* Repeated Pressure Score
* Stakeholder Reliability Score
* AI Recommendation Engine
* Decision Similarity Search
* Cross-Decision Learning
* Visual Timeline
* TMA Decision Screen
* Auto-generated Legal/CPA question list
* Weekly Decision Review

---

# 17. Stage 0 SPEC ONLY Prompt for Claude Code

הוראה לקלוד קוד:

```text
Read DECISION_HUB_MASTER_SPEC.md first.

Implement SPEC ONLY — Stage 0.

Do not implement Stage 1-6.
Do not build auto-ingestion.
Do not replace anti_hallucination.
Do not replace Approval Gate.
Do not create duplicate contact matching logic.

Build only:

1. Airtable schema support for:
   - Decisions
   - Decision Events
   - Decision Stakeholders
   - Decision Inbox

2. Commands:
   - /decision new
   - /decision update
   - /decision status

3. Forward/manual input to Decision Inbox.

4. Manual assignment from Inbox to Decision.

5. Create Decision Event after assignment.

6. Implement GateResult contract.

7. Implement Stage 0 pipeline:
   - Delta Gate active, keyword-based.
   - Entity Gate active only when needed.
   - Trust Gate stub returns passed=True.
   - Readiness Gate stub returns passed=True.
   - Risk Gate stub returns passed=True but must not bypass existing Approval Gate for future external actions.

8. Add Supersedes field support in Decision Events.

9. Enforce:
   - Never delete signal.
   - Pressure/no-change is saved as Logged Event.
   - No Canonical update for pressure-only.
   - tenant_id and Owner supported.
```

---

# 18. Done Definition for Stage 0

Stage 0 נחשב גמור רק אם:

```text
[ ] 4 הטבלאות מוגדרות.
[ ] ניתן ליצור Decision.
[ ] ניתן להכניס Raw Input ל־Inbox.
[ ] ניתן לשייך Inbox item ל־Decision.
[ ] נוצר Decision Event.
[ ] Delta=לחץ נשמר כ־Logged.
[ ] Delta=לחץ לא משנה Canonical State.
[ ] Supersedes קיים ב־Schema.
[ ] GateResult קיים ומאוחד.
[ ] Trust/Readiness/Risk קיימים כ־stubs.
[ ] אין החלפת רכיבים קיימים.
[ ] אין Auto-Ingestion.
[ ] אין כתיבה חיצונית.
[ ] יש בדיקות בסיסיות.
[ ] יש verification commands.
```

---

# 19. Verification Commands

לפני סיום פיתוח:

```bash
python -m compileall .
pytest
```

בדיקות ידניות:

```text
1. /decision new יוצר החלטה.
2. forward הודעה יוצר Inbox item.
3. שיוך יוצר Event.
4. הודעת לחץ מסווגת כ־לחץ.
5. הודעת לחץ לא משנה Status/Readiness.
6. Event נשמר עם Raw Content.
7. כפילות Entity לא מנחשת.
8. Trust/Readiness/Risk לא עושים פעולה אמיתית ב־Stage 0.
```

---

# 20. Summary

Decision Hub הוא שכבת ניהול החלטות בתוך BOSS.

הוא מתחיל מדלת אחת: Decision Inbox.
הוא ממשיך דרך Pipeline אחיד.
הוא שומר כל signal.
הוא מבדיל בין לחץ לבין עובדה.
הוא משתמש בתשתיות הקיימות.
הוא נבנה ידני קודם ואוטומטי אחר כך.
הוא לא מחליף את Approval Gate, anti_hallucination או Contacts.
הוא הופך החלטות עסקיות מורכבות לתהליך מנוהל, מתועד, ומוגן.

זהו מקור האמת לפיתוח Decision Hub.
