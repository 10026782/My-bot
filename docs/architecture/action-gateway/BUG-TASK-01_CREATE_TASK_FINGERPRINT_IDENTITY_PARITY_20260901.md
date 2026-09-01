# BUG-TASK-01 — create_task fingerprint/write-payload identity parity fix

**תאריך:** 01/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ב-canonical business identity (שכבה 2, `core/router/router.py`) ובחוזה
ה-fingerprint שהוא מזין לתוך ActionGateway (שכבה 4). לא נוגע ב-Dispatcher
proof rules, ב-approval policy, או ב-BUG-122 pending gate.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — תיקון מוכל לגמרי
בתוך `DeterministicTaskParse.business_identity()` (שכבה 2), שהיא הבעלים
היחיד של הבנייה הזו; אין שינוי חוזה/lifecycle/authority/routing/runtime-
wiring/fallback חוצה-שכבות.

## הבאג (BUG-TASK-01, אומת ב-live runtime — R10 bug report, 01/09/2026)

כל משימה שנוצרה דרך מסלול ה-create_task הדטרמיניסטי (למשל "צור משימה טיפול
במשכנתא דחוף") אושרה בהצלחה על ידי הבעלים, אך נכשלה בביצוע:

```
❌ אושר אך נכשל בביצוע
הפעולה לא הושלמה
```

עם הלוג:
```
[Dispatch] denied — missing/invalid execution proof | tool=airtable_add
reason=approval-sensitive execution proof does not match the action payload.
```

**שורש הבעיה (אומת אמפירית לפני כתיבת התיקון, ולא רק בבדיקת קוד):**
`core/action_gateway.py::propose_action()` מקבל `fingerprint_payload`
אופציונלי — כשמסופק, `business_action_fingerprint` מחושב ממנו ולא מ-
`tool_inputs` האמיתי. מסלול ה-create_task הדטרמיניסטי
(`app.py::_queue_deterministic_create_task`) מעביר
`fingerprint_payload = task_parse.business_identity()`.
`DeterministicTaskParse.business_identity()` (`core/router/router.py`) בנה
payload שונה **מבנית** מה-payload שבאמת נשלח ל-Airtable:

| | table | fields key |
|---|---|---|
| `business_identity()` (לפני התיקון) | `"Tasks"` | `"title"` |
| ה-payload האמיתי שנשלח לכתיבה (`core/router/task_builders.py` / `core/turn_coordinator_runtime.py::gateway_call()`) | `Tables.TASKS` = `"משימות (Tasks)"` | `TaskFields.NAME` = `"כותרת המשימה"` |

`tools/dispatcher.py::_validate_execution_proof()` מחשב מחדש, בעצמאות, את
ה-fingerprint הצפוי מתוך ה-payload האמיתי שבאמת נשלח לביצוע
(`contract.normalized_payload`) — fingerprint שחושב מתוך payload שונה
במבנהו לעולם לא יכול להיות שווה לו. זו לא בעיית edge-case של canonicalization
(פיסוק/רווחים/תווים נסתרים) — זו כשל **מובנה ובלתי-מותנה**: כל משימה
שנוצרה דרך המסלול הדטרמיניסטי נכשלה, ללא תלות בתוכן המשימה.

**היפותזה ראשונית שנבדקה ונשללה:** שה-Dispatcher לא מפעיל מחדש את
`_canonical_task_payload()` לפני חישוב ה-fingerprint. נבדק ונשלל בשחזור
סטטי: `contract.normalized_payload` כבר קנוני בזמן ה-propose (מיושם שם על
ידי `propose_action()` עצמו לפני האחסון), אז הפעלה חוזרת של
`_canonical_task_payload()` ב-Dispatcher היא no-op ולעולם לא הייתה מקור
אי-ההתאמה בפועל.

## התיקון

`DeterministicTaskParse.business_identity()` (`core/router/router.py`)
משתמש כעת באותם קבועים (`airtable_schema.Tables.TASKS` /
`TaskFields.NAME` / `TaskFields.DUE_DATE`) שהמסלול הכתיבה האמיתי משתמש
בהם — כך ששני ה-payloads מתקנוננים (`_canonical_task_payload()`) לאותה
צורה בדיוק ומייצרים את אותו fingerprint. `due_time` נשאר מוחרג מהזהות
(BUG-156, ללא שינוי, לא קשור לתיקון הזה).

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
cross-layer tests: `grep -n "leads_reasoning_projection\|BUG-104" core/router/router.py test_create_task_deterministic_route.py test_bug_task_01_execution_proof_fingerprint_parity.py` — 0 תוצאות

### שכבה 2 — TurnCoordinator (`core/router/router.py`)
touched: directly
input impact: אין שינוי לחתימת `parse_deterministic_create_task()`/קלט
output impact: `DeterministicTaskParse.business_identity()`'s output — table
  alias ו-field key משתנים ל-`Tables.TASKS`/`TaskFields.NAME`/`TaskFields.DUE_DATE`;
  `due_time` נשאר מוחרג (ללא שינוי מ-BUG-156)
authority impact: אין — `route_request()`'s handler-selection לא משתנה
shared identifiers: אין שם חדש נחשף; רק שימוש בקבועים קיימים (`airtable_schema`)
invariants: **תוקן** — ה-identity payload כבר לא "מבטיח" זהות-fingerprint
  שונה מה-write payload בפועל עבור אותה בקשה בדיוק
failure semantics: ללא שינוי
observability: ללא שינוי
cross-layer tests: `test_create_task_deterministic_route.py::test_create_task_parser_builds_structured_business_identity`
  עודכן ישירות (מצפה עכשיו ל-`Tables.TASKS`/`TaskFields.NAME`/`TaskFields.DUE_DATE`
  במקום `"Tasks"`/`"title"`/`"due_date"`) — תיקון-רגרסיה של assertion שקיבע
  את הבאג כ"התנהגות צפויה", לא שינוי-התנהגות מכוון. שאר 12 הטסטים בקובץ
  ללא שינוי (13/13 עוברים)

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: not touched — `_queue_deterministic_create_task()` (`app.py`) ממשיך
  להעביר `fingerprint_payload=task_parse.business_identity()` בדיוק כמו
  קודם; רק תוכן ה-payload המוחזר משתנה

### שכבה 4 — Durable Atomic Approval
touched: indirectly (via input, not via mechanism)
input impact: `fingerprint_payload` שמגיע מ-`business_identity()` כעת
  מיושר-מבנית עם `tool_inputs` — `compute_business_fingerprint()` עצמו,
  `_canonical_task_payload()`, ו-`tools/dispatcher.py::_validate_execution_proof()`
  **לא נגעו כלל**
output impact: fingerprint שנשמר על ה-contract בזמן ה-propose שווה עכשיו
  ל-fingerprint שה-Dispatcher מחשב מחדש בזמן הביצוע, עבור אותה משימה
authority impact: אין
invariants: **תוקן** — ה-fingerprint שנשמר כבר לא יכול לסטות מבנית
  מה-payload שבאמת נשלח לביצוע עבור מסלול זה
failure semantics: ללא שינוי — משימה מזויפת/שונה אחרי אישור עדיין נכשלת
  fail-closed עם אותה הודעת שגיאה בדיוק (ראה בדיקות שליליות למטה)
observability: ללא שינוי
cross-layer tests: `test_bug_task_01_execution_proof_fingerprint_parity.py`
  (חדש, 11/11) מפעיל את `propose_action()` וה-`_validate_execution_proof()`
  האמיתיים קצה-לקצה עבור 7 צורות טקסט שקולות (כותרת רגילה, פיסוק בסוף,
  רווחים כפולים, תו ברוחב-אפס, מרכאות עוטפות, סימן ציטוט מוביל, עם due_date)
  ו-4 בדיקות שליליות (כותרת שונה/טבלה שונה/שדה נוסף/כלי אחר אחרי אישור —
  כולן נכשלות fail-closed בדיוק כמו לפני); `test_bug155_ttl_expiry_contract_id_lookup.py`
  (5/5, ללא שינוי), `test_bug156_due_time_note_and_fingerprint_exclusion.py`
  (11/11, ללא שינוי), `test_action_gateway.py` (46/46, ללא שינוי),
  `test_stage_b_full_suite.py` (128/128, ללא שינוי)

### Proof of non-impact — Lead path
`core/action_gateway.py::_make_dispatch_executor()` מנתב Lead writes עם
`trusted_source="lead_capture"` ו-`_lead_payload` ישירות ל-
`core.lead_service.create_lead()`, **לפני** כל קריאה ל-`dispatch_tool()` —
מסלול זה כלל לא עובר דרך `_validate_execution_proof()` ולכן לא מושפע לא
מהבאג ולא מהתיקון. אומת ב-`test_f14_b2_contact_integration.py`,
`test_pr0c_writer_migration.py`, `test_bug099c_lead_clarification.py`,
`test_bug051fu_create_contact_precedence.py` — כולם ירוקים ללא שינוי.

## Verification

- `python3 -m py_compile core/router/router.py test_create_task_deterministic_route.py test_bug_task_01_execution_proof_fingerprint_parity.py app.py tools/dispatcher.py core/action_gateway.py`
- `python3 -m pytest test_create_task_deterministic_route.py -q` — 13/13
- `python3 test_bug_task_01_execution_proof_fingerprint_parity.py` — 11/11 (חדש)
- `python3 test_bug155_ttl_expiry_contract_id_lookup.py` — 5/5
- `python3 test_bug156_due_time_note_and_fingerprint_exclusion.py` — 11/11
- `python3 test_bug159_create_task_noun_form_and_verbs.py` — 52/52
- `python3 test_action_gateway.py` — 46/46
- `python3 test_stage_b_full_suite.py` — 128/128
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** לאחר merge + deploy: קנרי חי אחד — "צור משימה בדיקת
Task proof runtime" ואישור מיידי — צפוי ליצור משימה בפועל ללא כשל
execution-proof.
