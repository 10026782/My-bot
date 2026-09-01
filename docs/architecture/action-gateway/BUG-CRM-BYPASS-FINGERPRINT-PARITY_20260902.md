# BUG-CRM-BYPASS-FINGERPRINT-PARITY — Deal deterministic route approved but failed execution proof

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— התיקון מוכל כולו בתוך `app.py`/`core/router/router.py` (הסרת ייצוג
כפול); תיקון נלווה קטן ב-`core/action_gateway.py`'s תיאור-עסקי גנרי. אין
שינוי ל-`ActionGateway`'s מנגנון fingerprint עצמו, ל-`tools/dispatcher.py`,
או למדיניות אישור.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — תיקון בשכבת ה-caller
בלבד (Turn Coordinator) + תוספת ענפים לפונקציית תיאור גנרית קיימת; אין
חוזה/authority/routing חדש.

## הרקע

מיד לאחר deploy של PR #1173 (`BUG-CRM-BYPASS-OWNER-PRESENCE`), הבעלים שלח
שוב את אותה קנרית: "צור עסקה בשם בדיקת-קנרית 3/4 בתחום יבוא". הפעם
`action_validator`'s שער-הנוכחות **לא** חסם (התיקון הקודם עבד) — אבל
הביצוע נכשל בכל זאת, בהודעה **אחרת**: "approval-sensitive execution proof
does not match the action payload." הבעלים זיהה מיד: "אנחנו עכשיו חוזרים
לבאגים שתוקנו כבר" — ובצדק: זו אותה מחלקת באג בדיוק כמו **BUG-TASK-01**
(fingerprint/payload divergence בין זמן ה-propose לזמן הביצוע).

## הבאג

`_queue_deterministic_create_deal()` המשיך להעביר
`fingerprint_payload=deal_parse.business_identity()` (`{"name":...,
"domain":...}`, **בלי** `owner_id`) — שריד מהתיקון הראשון (PR #1172), לפני
ש-PR #1173 הוסיף `owner_id` ל-`tool_inputs` **האמיתי**. `core/action_gateway.py`'s
`propose_action()`:

```python
fingerprint_basis = normalized if fingerprint_payload is None else self.normalize_payload(fingerprint_payload)
```

— כש-`fingerprint_payload` מסופק במפורש (לא `None`), ה-fingerprint
הנשמר על ה-contract מחושב **ממנו**, לא מ-`tool_inputs` שבאמת יישלח
לביצוע. `tools/dispatcher.py::_validate_execution_proof()` מחשב מחדש,
בזמן ביצוע, fingerprint מתוך ה-`inputs` **האמיתיים** (3 שדות, כולל
`owner_id`) — לעולם לא יכול להיות שווה לזה שנשמר (2 שדות). כל contract
מאושר נכשל.

**אירוני:** `DeterministicDealParse.business_identity()`'s התיעוד הפנימי
ציטט במפורש את הלקח של BUG-TASK-01 ("different table/field keys than the
real write payload broke every approved deterministic create_task
contract") — בזמן שיצר בדיוק את אותה בעיה בעצמו, כי לא עודכן כש-PR #1173
שינה את ה-payload האמיתי.

## התיקון

הוסרה ה-divergence **מהמקור**, לא תוקנה ע"י סנכרון ידני של שני ייצוגים:

1. **`app.py::_queue_deterministic_create_deal()`** — לא מעביר עוד
   `fingerprint_payload` מותאם-אישית בכלל. ה-fingerprint מחושב תמיד
   מאותו `tool_inputs` יחיד שבאמת נשלח לביצוע (`{"name":..., "domain":...,
   "owner_id":...}`) — אין עוד ייצוג שני שיכול להתיישן.
2. **`core/router/router.py::DeterministicDealParse.business_identity()`**
   — הוסרה לגמרי (הייתה המקור היחיד לבעיה). הפרמטר `deal_parse` שהפך
   מיותר הוסר גם הוא מ-`_queue_deterministic_create_deal()` ומקריאתה
   ב-`app.py`.
3. **תיקון נלווה, אותו commit** — `core/action_gateway.py::_safe_contract_business_description()`
   לא הכיר את `crm_create_deal`/`crm_create_payment_term`/`crm_create_payment`
   כלל, ונפל תמיד ל-fallback הגנרי "הפעולה המבוקשת" — בדיוק מה שהבעלים
   ראה בהודעות ה-pending-approval בקנריות החיות (במקום שם העסקה). נוספו 3
   ענפים ייעודיים, מבלי לגעת ב-`is_task_creation`'s מנגנון הקיים ל-Tasks.

## למה זה לא יקרה שוב (התאמה לבקשת הבעלים)

הבעלים ביקש במפורש: "הכותב הוא זהב אבל כל מה שסביבו מעולם לא נבחן...
צריך לבנות סביבה זהה לשאר הכותבים." בשני הסבבים האלה (`OWNER-PRESENCE`
ו-`FINGERPRINT-PARITY`), `commercial_crm.py`'s הכותב עצמו מעולם לא היה
הבעיה — כל באג היה בשכבת ה-Turn Coordinator/caller סביבו, ששני
regression-suites הקודמים (PR #1172/#1173) לא כיסו במלואה כי בדקו רק את
שלב ה-`propose` (contract pending), לא את ה-round-trip המלא. regression
test חדש (`test_bug_crm_bypass_create_deal_deterministic_route.py`) נבנה
במפורש לבצע round-trip אמיתי — propose_action אמיתי → execution_context
אמיתי מה-contract שנוצר → `_validate_execution_proof()` אמיתי — מראה
בדיוק את מבנה הבדיקה ש-BUG-TASK-01's regression test כבר השתמש בו
ל-Tasks, ומה ש-Deal-creation לא קיבל עד עכשיו.

## Verification

- `python3 -m py_compile app.py core/router/router.py core/action_gateway.py` — עבר
- regression test חדש: round-trip אמיתי (propose_action → execution_context
  אמיתי → `_validate_execution_proof()` אמיתי) — אומת דרך `git stash`
  שנכשל בדיוק עם הודעת השגיאה האמיתית מהפרודקשן ("approval-sensitive
  execution proof does not match the action payload") על הקוד הישן, ועובר
  עם התיקון.
- בדיקה נוספת: תיאור עסקי (`build_approval_lifecycle_result`) עבור
  contract מסוג `crm_create_deal` כולל את שם העסקה בפועל, לא "הפעולה
  המבוקשת".
- רגרסיה מלאה: `smoke_tests.py`, `test_integration.py`,
  `core/router/test_router.py`, `test_create_task_deterministic_route.py`,
  `test_bug_task_01_execution_proof_fingerprint_parity.py` (11/11),
  `test_action_gateway.py` (46/46), `test_stage_b_full_suite.py` (128/128),
  `test_commercial_crm.py` (97/97), `test_commercial_crm_dispatcher_wiring.py` (40/40),
  `test_bug_commercial_crm_dispatcher_bypass_closure.py`,
  `test_pa01_phantom_approval_enforcement.py` (108/108),
  `test_bug123_approval_rendering_fail_closed.py` (20/20),
  `test_bug161_agent_no_reconfirmation_promise.py` (7/7),
  `test_bug162_gateway_reply_owner_on_generic_block.py` (57/57),
  `test_bug_approval_callback_hardening.py` (41/41),
  `test_f52_status_reply_reconciliation.py` (51/51),
  `test_a32_enforcement.py` (6/6), `test_approval_concurrency.py` (22/22),
  `test_c53a.py` (50/50) — כולם ירוקים, אף שינוי בהתנהגות הקיימת.
- `python3 tools/audit_turn_coordinator_bypass.py` — `PASS`
- `python3 tools/audit_dispatcher_bypass.py` — `new=0`
- `git diff --check` — נקי

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** דורש קנרית owner-approved אמיתית **שלישית** (אותה
הודעה בדיוק) שהפעם צריכה להצליח עד הסוף — כולל רשומת Deal אמיתית ב-Airtable
עם owner שנפתר ל-Profile record ID — לפני שסטטוס זה יתעדכן ל-Verified.
