# BUG-154 — create_task date-marker parser crash fix

**תאריך:** 04/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— `core/router/router.py::route_request()` הוא ה-de-facto owner של שכבה 2
(TurnCoordinator) כפי שהשער עצמו קובע ב-§1 ("מי בפועל ממלא את התפקיד היום").

## הבאג (BUG-154, אומת ב-staging 03/08/2026)

קלט:
```text
צור משימה לבדוק את אימות 546 המעודכן, ל־5/8/26 בשעה 10:30
```

גרם ל-`AttributeError: 'NoneType' object has no attribute 'start'` בתוך
`parse_deterministic_create_task()` (`core/router/router.py:115`), ונתפס
ע"י `app.py::_safe_route()`'s catch-all fallback — `intent=unknown,
handler=APPROVAL, confidence=0.0`, מציג approval כללי לא-קנוני במקום
clarification.

## שורש הבעיה — מאומת ישירות בקוד

```python
date_marker = re.search(r"\bעד\b", body)          # None אם אין "עד"
date_match = _CREATE_TASK_DATE_RE.search(body)     # מוצא "5/8/26"
...
if date_match:
    ...
    if date_marker.start() > date_match.start():   # קורס אם date_marker is None
        uncertain = True
```

הקלט משתמש ב-"ל־" (ל + מקף עברי/מקף) כמסמן-תאריך במקום "עד" — `date_marker`
נשאר `None`, אבל `date_match` כן נמצא, אז השורה קוראת ל-`.start()` על `None`.

## התיקון

1. **הגנה על `None`.** אין עוד קריאה בלתי-מותנית ל-`date_marker.start()`.
2. **תמיכה ב-"ל" + מקף/hyphen כמסמן-תאריך חלופי.** מסמן חדש נבדק **רק** צמוד
   (עם רווח אופציונלי) ממש **לפני** מיקום ה-date_match עצמו — לא חיפוש
   גלובלי של "ל" בכל הטקסט (ש"ל" הוא אות עברית נפוצה מדי לשמש marker
   עצמאי). אם לא נמצא מסמן בשום צורה (לא "עד", לא "ל-" צמוד לתאריך) —
   `uncertain=True`, בדיוק כמו היום עבור כל תרחיש date-shaped-token-בלי-
   marker אחר — fail-closed, לא fail-crash.

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input/output/authority impact: אין
shared identifiers: אין
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `grep -n "leads_reasoning_projection\|BUG-104" core/router/router.py` — 0 תוצאות

### שכבה 2 — TurnCoordinator (de-facto: `core/router/router.py`)
touched: directly
input impact: אין שינוי לחתימת `parse_deterministic_create_task(text: str)`; קלט זהה
output impact: `DeterministicTaskParse` — עבור הקלט הספציפי הזה (`ל־5/8/26`),
  `certain=True` במקום exception; `title`/`due_date`/`due_time` מחושבים נכון.
  לכל קלט אחר (שכבר עבד) — **byte-identical output**, ראה regression tests למטה.
authority impact: אין — עדיין אותה קביעה (`Handler.TOOL` אם certain,
  `Handler.CLARIFY` אם uncertain) ב-`route_request()`, ללא שינוי ללוגיקה שם
shared identifiers: אין שם חדש נחשף מחוץ למודול; `_CREATE_TASK_DATE_PREFIX_MARKER_RE`
  הוא קבוע מודול פרטי חדש, לא API ציבורי
invariants: **משוחזר** — "date-shaped token ללא marker מזוהה → uncertain,
  לא crash" (זו הייתה הכוונה המקורית של הקוד; עכשיו מתקיימת בפועל גם
  כשה-marker חסר לגמרי, לא רק כשהוא "אחרי" ה-תאריך)
failure semantics: **שופר מ-crash ל-fail-closed** — `_safe_route()`'s
  fallback (`intent=unknown, handler=APPROVAL, confidence=0.0`) כבר לא
  מופעל לתרחיש הזה; זרימת השגיאה הישנה (exception → generic approval
  לא-קנוני) מוחלפת ב-parse תקין (המקרה הנפוץ) או `handler=CLARIFY` תקין
  (המקרה הנדיר-יותר, בדיוק כמו תאריך/שעה פגומים אחרים)
observability: אין שינוי ל-logging (אין exception יותר להיתפס/להירשם
  ב-`_safe_route()`'s `logger.error`)
cross-layer tests: `core/router/test_router.py` (44/44) הורץ ללא שינוי;
  `test_create_task_deterministic_route.py` (13/13) הורץ ללא שינוי; טסט
  חדש (`test_bug154_date_marker_prefix_parser.py`) מוסיף כיסוי ל-crash
  המדויק + regression לכל תבניות ה-marker הקיימות ("עד")

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: `_queue_deterministic_create_task()`/`ActionGateway.propose_action()`
  מקבלים `DeterministicTaskParse` תקין עכשיו לקלט הזה, במקום שלא להגיע
  לשם בכלל (כי `route_request()` עצמו קרס לפני זה)
output impact: אין שינוי לחוזה C53a
authority impact: אין
shared identifiers: אין
invariants: `agent_calls=0` לבקשת create_task דטרמיניסטית — נשמר (הקלט הזה
  עכשיו עובר במסלול הדטרמיניסטי בלי exception, לא נופל ל-Agent)
failure semantics: ללא שינוי
observability: ללא שינוי
cross-layer tests: לא רלוונטי ישירות — נבדק דרך שכבה 2

### שכבה 4 — Durable Atomic Approval
touched: indirectly
input impact: `fingerprint_payload`/`business_identity()` עבור הקלט הזה
  עכשיו מחושב נכון (`due_time="10:30"` נכלל) — לפני התיקון, `route_request()`
  קרס לפני שהגיע ל-ActionGateway בכלל, כך שלא נוצר שום contract (לא שגוי,
  פשוט לא-קיים)
output impact: אין שינוי ל-`ActionContract`/`GatewayResult` shape
authority impact: אין
shared identifiers: אין
invariants: ללא שינוי
failure semantics: ללא שינוי
observability: ללא שינוי
cross-layer tests: לא רלוונטי ישירות

### Proof of non-impact — שכבה 1
1. grep evidence: `grep -n "leads_reasoning_projection\|BUG-104" core/router/router.py` — 0 תוצאות
2. unchanged-tests evidence: `test_bug104_*.py` לא נוגעים ב-`core/router/router.py` כלל (אומת ב-grep) — לא הורצו מחדש, אין תלות
3. no-new-coupling evidence: אין import חדש ב-`core/router/router.py`

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: no — אין שינוי ל-action-status claims, tool-result evidence,
`ActionContract.status`, `outcome_unknown`, או reply grounding. זהו תיקון
parser טהור בשכבה 2; אין claim חדש על "מה קרה" לפעולה כלשהי.

## Verification

- `python3 -m py_compile core/router/router.py`
- `python3 test_bug154_date_marker_prefix_parser.py` (חדש)
- `python3 core/router/test_router.py` — 44/44, ללא שינוי
- `python3 test_create_task_deterministic_route.py` — 13/13, ללא שינוי
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## סטטוס

קוד מומש ונבדק מקומית. **לא מוזג, לא deployed, לא verified בפרודקשן.**
