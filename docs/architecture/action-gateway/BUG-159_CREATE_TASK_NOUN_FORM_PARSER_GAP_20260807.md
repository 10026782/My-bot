# BUG-159 — הפרסר הדטרמיניסטי של create_task לא מזהה "משימת" (סמיכות) ו-הוסף/תוסיף

**תאריך:** 07/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ב-TurnCoordinator (שכבה 2, `core/router/router.py`'s deterministic
create_task gate) ובעקיפין ב-Durable Atomic Approval (שכבה 4) — הפלט של
הפרסר קובע האם הבקשה עוברת דרך `app.py::_queue_deterministic_create_task()`
(שיוצר `ActionContract` בעל `trusted_source="deterministic_create_task"`,
carve-out BUG-153) או נופלת ל-Agent loop הכללי.
**רקע:** נמצא ע"י owner בבדיקת staging ידנית (07/08/2026) — אבחון מדויק
מול הקוד, ראה ניתוח מלא ב-session. Owner אישר את התיקון ואת קריטריוני
הסגירה במפורש.

## הבעיה

`core/router/router.py:26-28`:
```python
_STRUCTURED_CREATE_TASK_RE = re.compile(
    r"^\s*(?:צור|תיצור)\s+משימה\s*:?\s*(?P<title>.+?)\s*$"
)
```

הרג'קס דורש **בדיוק** את המילה "**משימה**" (צורת יסוד) ורק את הפעלים
"צור"/"תיצור". שני פערים נבדקו ואומתו בקוד:

1. **צורת סמיכות ("משימת X")** — "צור משימ**ת** בדיקת באג 155" (ניסוח
   עברי טבעי לגמרי, נפוץ לפחות כמו "משימה") לא תואם `fullmatch()` →
   `parse_deterministic_create_task()` מחזיר `DeterministicTaskParse()`
   ברירת מחדל (`matched=False`) → לא `certain` וגם לא `uncertain`
   במפורש → נופל דרך ל-`detect_risk()` הגנרי (`risk=normal,
   handler=agent`) במקום המסלול הדטרמיניסטי (`risk=NEEDS_APPROVAL,
   handler=TOOL`, `router.py:239`).
2. **פעלים נוספים ("הוסף"/"תוסיף")** — `detect_intent()`'s regex
   (`intent_router.py`, `rule='(פתח|צור|\bתייצר\b|הוסף|תוסיף).*(משימ|
   טאסק|task)'`) **כן** מזהה "הוסף משימה"/"תוסיף משימה" כ-`intent=
   create_task` ברמת ה-intent — אבל `_STRUCTURED_CREATE_TASK_RE`
   (הפרסר הדטרמיניסטי, שקובע risk/handler) תומך **רק** ב-"צור"/"תיצור".
   כלומר גם "הוסף משימה X" (עם "משימה" תקנית!) לא עובר את המסלול
   הדטרמיניסטי היום.

**השפעה בפועל (אומת ב-staging, 05-07/08/2026):** שתי בקשות עם אותה
כוונת משתמש בדיוק ("צור משימה" מול "צור משימת") מקבלות routing שונה —
אחת עוברת ב-`_queue_deterministic_create_task()` (`agent_calls=0`,
מהיר, ה-carve-out של BUG-153 חל עליה), השנייה עוברת ב-Agent loop המלא
(קריאת Claude אמיתית, `POST api.anthropic.com`, `agent_calls=1`,
BUG-153's `trusted_source="deterministic_create_task"` **לא חל בכלל**
כי לא עוברת דרך אותו קוד-caller). ניסוח עברי טבעי, לא שגיאת קלט, קובע
מדיניות אישור/reconfirmation שונה — לא עקבי ולא מכוון.

## התיקון

הרחבת שני מרכיבי הרג'קס — **סגורה ומצומצמת**, לא `\w+`/regex רחב:

```python
_STRUCTURED_CREATE_TASK_RE = re.compile(
    r"^\s*(?:צור|תיצור|הוסף|תוסיף)\s+משימ(?:ה|ת)\s*:?\s*(?P<title>.+?)\s*$"
)
```

- `משימ(?:ה|ת)` (owner-approved, נדחה `\bמשימ\w?` כרחב מדי) — תופס
  בדיוק "משימה"/"משימת", שתי הצורות הלגיטימיות היחידות, לא צורות אחרות.
- `(?:צור|תיצור|הוסף|תוסיף)` — מרחיב את הפעלים הנתמכים כך שיתאימו בדיוק
  לרשימת הפעלים ש-`detect_intent()` כבר מזהה כ-create_task ברמת
  ה-intent (`intent_router.py`) — לא מוסיף פועל שלא כבר היה
  contract-requiring ברמת ה-intent, רק סוגר את הפער בין רמת ה-intent
  לרמת ה-parser הדטרמיניסטי.

שום שינוי לשאר `parse_deterministic_create_task()` — לוגיקת תאריך/שעה/
title extraction (BUG-154/BUG-156) נשארת זהה, פשוט מופעלת עכשיו גם על
צורות ניסוח נוספות.

## קריטריוני סגירה (owner, 07/08/2026)

עבור **כל** הניסוחים: "צור משימה בדיקת X", "צור משימת בדיקת X", "צור
משימת בדיקה", "תיצור משימת בדיקה", "הוסף משימת בדיקה", "תוסיף משימת
בדיקה" — `route_request()` חייב להחזיר:
- `intent=create_task`
- `risk=needs_approval` (`Risk.NEEDS_APPROVAL`)
- `handler=tool` (`Handler.TOOL`)
- אותו `title` מנורמל (בהתעלם מהמילה/פועל עצמם) עבור תוכן זהה
- `_queue_deterministic_create_task()` נקרא (לא Agent loop)
- `agent_calls=0`, אין קריאת Claude
- fingerprint קנוני שקול כש-שאר התוכן זהה (משום ש-`business_identity()`
  לא תלוי בפועל/בצורת "משימה"/"משימת" עצמם — הם נחתכים ב-title
  extraction לפני חישוב ה-fingerprint)
- אותה מדיניות BUG-153/reconfirmation (`trusted_source=
  "deterministic_create_task"` מגיע מ-`_queue_deterministic_create_task()`
  בכל המקרים כעת)

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched — אין קשר ל-`leads_reasoning_projection`.

### שכבה 2 — TurnCoordinator
touched: directly
input impact: `parse_deterministic_create_task()`/
  `_STRUCTURED_CREATE_TASK_RE` — הרחבת קלט מוכר בלבד (2 מילים חדשות
  לצורת "משימה", 2 פעלים חדשים) — לא שינוי סמנטי לניסוחים שכבר תאמו.
output impact: ניסוחים שהיו נופלים ל-`RouteDecision(handler=AGENT,
  risk=normal)` עכשיו מקבלים `RouteDecision(handler=TOOL,
  risk=NEEDS_APPROVAL)` — **רק** עבור הניסוחים החדשים שנתמכים; אפס
  שינוי לניסוחים קיימים.
authority impact: אין — עדיין אותו gate (`identity.role not in
  ("lead", "guest", "readonly")`, `router.py:237`) לפני שהמסלול
  הדטרמיניסטי מופעל.
shared identifiers: אין שמות חדשים — הרחבת קבוע רג'קס קיים בלבד.
invariants: `agent_calls=0` למסלול דטרמיניסטי — **מתרחב** לניסוחים
  נוספים, לא מופר לאף ניסוח קיים.
failure semantics: לא רלוונטי — אין exception path חדש.
observability: אין לוג חדש.
cross-layer tests: `core/router/test_router.py` (44/44) — regression;
  `test_bug159_create_task_noun_form_and_verbs.py` (חדש) — כל 6
  הניסוחים מקריטריוני הסגירה.

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly — אין שינוי ל-`ToolMeta`/`tools/schemas.py`/
`tools/dispatcher.py`; יותר בקשות עוברות דרך `_queue_deterministic_
create_task()` (קיים, לא חדש) במקום Agent loop.

### שכבה 4 — Durable Atomic Approval
touched: indirectly
input impact: `propose_action()` מקבל אותה חתימה — `title` המנורמל
  (אחרי חיתוך המילה/פועל) הוא מה שנכנס ל-`fingerprint_payload`, ולכן
  fingerprint זהה לתוכן זהה בין הניסוחים.
output impact: ניסוחים חדשים מקבלים את מדיניות ה-BUG-153 carve-out
  (`trusted_source="deterministic_create_task"`) — **תוספת**, לא שינוי
  להתנהגות קיימת.
authority impact: אין.
shared identifiers: אין.
invariants: ללא שינוי.
failure semantics: ללא שינוי.
observability: ללא שינוי.
cross-layer tests: `test_bug153_create_task_reconfirmation_after_
  rejection.py` (16/16, ללא שינוי-אחורה) — מוודא ה-carve-out עדיין
  עובד נכון גם עם המסלול המורחב.

### Proof of non-impact — שכבה 1
1. grep evidence: `grep -n "leads_reasoning_projection\|BUG-104"
   core/router/router.py` — 0 תוצאות בטווח השינוי.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: no — אין שינוי ל-evidence/status claims כלפי המשתמש; זו
הרחבת התאמת-קלט בלבד לפני שהזרימה הרגילה (ללא שינוי) ממשיכה.

## Verification

- `python3 -m py_compile core/router/router.py`
- `python3 test_bug159_create_task_noun_form_and_verbs.py` (חדש)
- `python3 core/router/test_router.py` — regression
- `python3 test_bug153_create_task_reconfirmation_after_rejection.py` — regression
- `python3 test_bug154_date_marker_prefix_parser.py` — regression (אותו
  parser, פורמט תאריך — לוודא ללא שינוי)
- `python3 smoke_tests.py` / `test_integration.py`

## סטטוס

עיצוב אושר ע"י owner (07/08/2026) — כולל דחיית `\bמשימ\w?` (רחב מדי)
לטובת `משימ(?:ה|ת)` המצומצם, והרחבת קריטריוני הסגירה ל-4 צירופי
פועל/צורה נוספים. קוד בעבודה.
