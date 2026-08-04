# BUG-156 — due_time fingerprint-vs-persistence fix (Option B)

**תאריך:** 04/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ב-canonical business identity (שכבה 2/4 המשותפת) ובחוזה ה-fingerprint
של ActionGateway (שכבה 4).
**החלטת owner (04/08/2026, AskUserQuestion):** Option B — "stop promising
the time." קוד-בלבד, ללא שינוי schema Airtable חי.

## הבאג (BUG-156, אומת ב-staging 03/08/2026)

בקשה עם שעה (`"...עד 5/8/26 בשעה 10:30"`) גרמה ל-fingerprint שונה מבקשה
זהה עם שעה אחרת — השעה היא חלק מהזהות העסקית. אבל הרשומה שנכתבה בפועל
ל-Airtable (`משימות (Tasks)`) הכילה רק כותרת ותאריך יעד — **לא שעה**.
בדיקת סכמה אישרה: השדה `תאריך יעד` הוא מסוג `date`, לא `dateTime`. תוצאה:
שתי בקשות זהות בתאריך, שונות רק בשעה, מקבלות זהויות-עסקיות שונות
(fingerprints שונים, contracts נפרדים, אישורים נפרדים) — אך לאחר ביצוע,
שתיהן נכתבות זהה לחלוטין ב-Airtable. המידע שאושר (השעה) אינו נשמר במלואו.

## שתי אפשרויות שהוצגו ל-owner

- **אפשרות א:** להפוך את השדה ל-`dateTime` או להוסיף שדה שעה נפרד — שינוי
  schema חי ב-Airtable, סיכון גבוה יותר, דורש אישור נפרד לפני נגיעה בסכמה.
- **אפשרות ב (נבחרה):** קוד-בלבד — להוציא את `due_time` מה-fingerprint,
  ולהודיע למשתמש במפורש שהשעה לא תישמר.

## התיקון

1. **`DeterministicTaskParse.business_identity()`** (`core/router/router.py`)
   — כבר לא כולל `due_time` ב-fields. `due_time` עדיין **מנותח ומאומת**
   (parse_deterministic_create_task ממשיך ל-fail-closed על שעה פגומה,
   BUG "קלט שעה פגומה" ב-staging report נשאר תקין) — רק לא חלק מהזהות/
   fingerprint יותר.
2. **הודעה מפורשת** — `_queue_deterministic_create_task()` (`app.py`) בונה
   `due_time_note` כשיש `task_parse.due_time`, ומעביר אותו כ-`extra_note`
   חדש דרך `_queue_approval_detailed()`/`_queue_approval_detailed_impl()`
   — מצורף הן להודעת ה-pending שנשלחת ל-owner (עם כפתורי אישור), הן
   ל-`message` המוחזר לקורא כשלא מדוכא (`duplicate_reply_suppressed`).
   נוסח: "⚠️ שים לב: השעה שצוינה ({HH:MM}) לא תישמר ברשומה — רק התאריך
   יישמר."

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input/output/authority impact: אין
shared identifiers: אין
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `grep -n "leads_reasoning_projection\|BUG-104" <diff files>` — 0 תוצאות

### שכבה 2 — TurnCoordinator (`core/router/router.py`)
touched: directly
input impact: אין שינוי לחתימת `parse_deterministic_create_task()`/קלט
output impact: `DeterministicTaskParse.business_identity()`'s output field
  set משתנה — `due_time` לא נכלל יותר. `due_time` עצמו (attribute) נשאר
  זמין וללא שינוי לצרכנים אחרים (למשל `app.py`'s due-time note)
authority impact: אין — `route_request()`'s handler-selection (`Handler.TOOL`/
  `Handler.CLARIFY`) לא משתנה; fail-closed לשעה פגומה נשאר בדיוק כמו היום
shared identifiers: אין שם חדש נחשף
invariants: **נשמר** — שעה פגומה עדיין `uncertain=True` (לא קשור ל-business_identity);
  **משתנה במכוון** — שעה תקינה כבר לא חלק מה-fingerprint (זו בדיוק מטרת התיקון)
failure semantics: ללא שינוי
observability: ללא שינוי (אין logging חדש בשכבה הזו)
cross-layer tests: `test_create_task_deterministic_route.py::test_create_task_parser_builds_structured_business_identity`
  עודכן ישירות (מצפה עכשיו ל-fields ללא due_time) — שינוי-התנהגות מכוון,
  לא regression. שאר 12 הטסטים בקובץ ללא שינוי.

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: `_queue_approval_detailed()`/`_queue_approval_detailed_impl()`
  מקבלים פרמטר חדש `extra_note: str | None = None` — ברירת מחדל `None`,
  כל קורא קיים (Agent tool_use loop, `_queue_deterministic_task_update()`)
  ממשיך לא להעביר אותו, אפס שינוי התנהגות עבורם
output impact: `_pending_text`/`outcome["message"]` יכולים לכלול suffix
  נוסף כש-`extra_note` מועבר — משפיע **רק** על create_task עם due_time
authority impact: אין
shared identifiers: `extra_note` הוא פרמטר חדש, לא שם קיים מוגדר-מחדש
invariants: `agent_calls=0` נשמר; C53a evidence contract לא נוגע
failure semantics: ללא שינוי — `extra_note` הוא string concatenation בלבד,
  לא משפיע על אף branch של הצלחה/כשל
observability: ללא שינוי ל-logs קיימים
cross-layer tests: `test_create_task_deterministic_route.py` (13/13,
  אחד עודכן במכוון), `test_bug153_create_task_reconfirmation_after_rejection.py`
  (11/11, ללא שינוי — לא משתמש ב-due_time)

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `fingerprint_payload` שמגיע מ-`_queue_deterministic_create_task()`
  לעולם לא כולל `due_time` יותר — `propose_action()`'s `compute_business_fingerprint()`
  מקבל basis שונה (קטן יותר) עבור אותה בקשה, אך המנגנון עצמו (hash של
  tenant+user+tool+payload) לא השתנה
output impact: שתי בקשות create_task זהות בכותרת+תאריך, שונות רק בשעה,
  **מייצרות כעת את אותו fingerprint** (שינוי מכוון — היו שונים לפני
  התיקון). המשמעות: בקשה שנייה עם שעה שונה, כשה-contract הראשון עדיין
  `pending`, תיחסם כ-duplicate (נכון עסקית — התוצאה הכתובה זהה בכל מקרה)
authority impact: אין
shared identifiers: אין
invariants: **תוקן** — fingerprint כבר לא "מבטיח" יותר דיוק-זהות ממה
  שה-write payload בפועל שומר (זו בדיוק ההגדרה של הבאג שתוקן)
failure semantics: ללא שינוי
observability: ללא שינוי ל-`propose_action()` עצמו (השינוי כולו בצד הקורא,
  `app.py`, לפני שה-payload מגיע ל-Gateway)
cross-layer tests: `test_business_action_fingerprint_normalization.py`
  (8/8, ללא שינוי — בונה `fingerprint_payload` ידנית, לא דרך
  `business_identity()`, אז לא מושפע ישירות); `test_bug155_ttl_expiry_
  contract_id_lookup.py` (5/5, ללא שינוי — התרחיש שם עדיין תקף כבדיקה
  כללית ל-lookup-by-contract_id, גם אם הטריגר הספציפי-לdue_time כבר לא
  יכול לקרות בפועל דרך create_task האמיתי)

### Proof of non-impact — שכבה 1
1. grep evidence: `grep -rn "leads_reasoning_projection\|BUG-104" core/router/router.py app.py` (בטווח השינויים) — 0 תוצאות
2. unchanged-tests evidence: `test_bug104_*.py` לא נוגעים בקבצים ששונו — לא הורצו מחדש, אין תלות
3. no-new-coupling evidence: אין import חדש מ-`core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py`

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — נוגע בניסוח-הפונה-למשתמש לגבי מה ייכתב בפועל (due_time_note).
**איך:** ההודעה החדשה מדווחת במפורש **מה לא** ייכתב — היפוך-כיוון של
BOSS NEVER FAKES (לא טוענים הצלחה חלקית כמלאה) — לא נוסף מנגנון grounding
עצמאי, רק string נוסף שמדייק את המסר הקיים.

## Verification

- `python3 -m py_compile app.py core/router/router.py`
- `python3 -m pytest test_create_task_deterministic_route.py -q` — 13/13
  (1 עודכן במכוון לשקף את ה-Option B behavior)
- `python3 test_business_action_fingerprint_normalization.py` (דרך pytest) — 8/8, ללא שינוי
- `python3 test_bug155_ttl_expiry_contract_id_lookup.py` — 5/5, ללא שינוי
- `python3 test_bug153_create_task_reconfirmation_after_rejection.py` — 11/11, ללא שינוי
- `python3 core/router/test_router.py` — 44/44, ללא שינוי
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## סטטוס

עיצוב אושר ע"י owner (Option B). קוד מומש ונבדק מקומית. **לא מוזג, לא
deployed, לא verified בפרודקשן.**
