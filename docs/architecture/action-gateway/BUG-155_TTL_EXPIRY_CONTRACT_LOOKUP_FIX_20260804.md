# BUG-155 — TTL expiry contract lookup fix

**תאריך:** 04/08/2026
**שער מחייב:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — מסמך זה נכתב
לפני כל שינוי קוד, כנדרש עבור כל שינוי הנוגע ב-Durable Atomic Approval layer (שכבה 4).

## הבאג (מ-BUG_AUDIT_LOG.md BUG-155, אומת ב-staging 03/08/2026)

Telegram callback שמגיע אחרי `_PENDING_APPROVAL_TTL` (600 שניות, ה-TTL המוצג
למשתמש על הכפתור) מפעיל `_reject_stale_telegram_approval()` (`app.py:2223`),
שאמור לדחות (`reject()`) את ה-`ActionContract` התואם ולהעביר אותו למצב terminal.
בפועל — למשתמש נאמר "פג תוקף — הפעולה לא בוצעה", אבל ה-contract נשאר `pending`,
נספר כ-live, וחזר ל-reconfirmation ובוצע בפועל מאוחר יותר.

## שורש הבעיה — מאומת ישירות בקוד, לא הנחה

`_reject_stale_telegram_approval()` (`app.py:2246-2274`) מזהה את ה-contract
לדחייה **על ידי חישוב מחדש** של ה-`business_action_fingerprint` מתוך
`payload.get("tool_inputs", {})` בלבד:

```python
_fp_stale = _gw_stale.compute_business_fingerprint(
    tenant_id, canonical_user_id, tool_name,
    _gw_stale.normalize_payload(payload.get("tool_inputs", {})),
)
_contract_stale = _gw_stale._ledger.find_by_fingerprint(_fp_stale)
```

אבל `propose_action()` (`core/action_gateway.py:1460-1467`) מחשב את ה-fingerprint
המקורי מתוך `fingerprint_payload` **כאשר הוא מועבר בנפרד מ-`tool_inputs`**:

```python
fingerprint_basis = normalized if fingerprint_payload is None else self.normalize_payload(fingerprint_payload)
...
fingerprint = self.compute_business_fingerprint(tenant_id, canonical_user_id, tool_name, fingerprint_basis)
```

עבור יצירת משימה (`_queue_deterministic_create_task()`, `app.py:966-987`):
`fingerprint_payload = task_parse.business_identity()` (כולל `due_time` כשקיים),
בעוד `tool_inputs`/`task_fields` (payload הכתיבה בפועל) **אינו** כולל `due_time`
(זהו בדיוק BUG-156 — השעה חלק מהזהות אך לא נכתבת). כתוצאה מכך, לכל משימה עם שעה,
ה-fingerprint שמחושב מחדש ב-`_reject_stale_telegram_approval()` **שונה** מה-fingerprint
האמיתי שנשמר על ה-contract. `find_by_fingerprint()` מחזיר `None` (או contract לא-קשור),
התנאי `_contract_stale is not None and _contract_stale.status == "pending"` נכשל,
`reject()` **לעולם לא נקרא**, אבל הקוד ממשיך כרגיל ומודיע למשתמש "פג תוקף".

**זו לא בעיה תיאורטית בלבד** — `payload["contract_id"]` **כבר קיים ונשמר** באותו
payload (`app.py:1612`, בזמן `bus.request_approval()`), ומעולם לא נעשה בו שימוש
כאן. תיקון: שימוש ישיר ב-`contract_id` הידוע, ללא צורך בחישוב fingerprint מחדש כלל.

## התיקון

`_reject_stale_telegram_approval()`: כאשר `payload.get("contract_id")` קיים —
`find_by_id(contract_id)` ישיר, במקום recompute של fingerprint. Fallback לנתיב
ה-fingerprint הישן נשאר **רק** לפריטים ישנים/לא-Gateway-tracked שבהם contract_id
לא נשמר בפועל (לא קיים תרחיש כזה במסלולים החיים כיום, אך נשמר להתאמה לאחור בלי
לשבור התנהגות קיימת).

**לא מוצג status חדש ("expired")** — `reject(rejected_by="ttl_expired")` הקיים כבר
מעביר למצב terminal `"rejected"` הנתמך במלואו (`find_live_contracts()` מסנן לפי
`status == "pending"` בלבד — `rejected` כבר לא-live; `propose_action()` כבר חוסם
re-proposal אוטומטי דרך הבדיקה הקיימת ל-`status == "rejected"`). הוספת status
חדש ("expired") נפרד מ-"rejected" תדרוש audit חוצה-קוד של כל הצרכנים
(`propose_action()`, `describe_pending_queue()`, `build_approval_lifecycle_result()`,
UI rendering) — scope גדול משמעותית מהבאג המדווח, ואינו נדרש כדי לספק את כל
קריטריוני הסגירה שדווחו. **מזוהה כשיפור עתידי אפשרי, לא מומש כאן** (root-cause-first,
לא scope creep).

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input impact: אין
output impact: אין
authority impact: אין
shared identifiers: אין — אין import/reference בין הקבצים שהשתנו ל-`core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py`
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: לא רלוונטי — `grep -rn "leads_reasoning_projection\|BUG-104" app.py core/action_gateway.py` מחזיר 0 תוצאות בקבצים שהשתנו

### שכבה 2 — TurnCoordinator
touched: not touched
input impact: אין — `route_request()`/`core/router/router.py` לא נגעו
output impact: אין
authority impact: אין — routing/handler-selection לא משתנה
shared identifiers: `contract_id` נקרא מ-`payload` (שממנו TurnCoordinator/router לא קוראים ישירות — `payload` הוא מבנה פנימי של `event_bus`/`app.py`'s approval flow, לא route_decision)
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `grep -n "route_request\|RouteDecision" app.py` בטווח השורות שהשתנו (2223-2311) — 0 תוצאות; `core/router/test_router.py` ירוק ללא שינוי (לא רץ קוד מהשכבה הזו)

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: אין שינוי ל-`ToolMeta`/`tools/schemas.py`/`tools/dispatcher.py`
output impact: אין שינוי לחוזה C53a (`{ok, tool, external_id, evidence, user_message}`)
authority impact: אין — policy/capability של tool_registry לא נוגע
shared identifiers: `tool_name` נקרא מ-`payload` (כפי שכבר נעשה בקוד המקורי, ללא שינוי בשימוש)
invariants: ללא שינוי — הבדיקה `if tool_name and canonical_user_id:` נשארת זהה
failure semantics: ללא שינוי — try/except שמסביב לכל הבלוק נשאר; כשל בלוקאפ עדיין non-blocking (`logger.warning`, לא raise)
observability: **שופר** — נוסף `logger.error` חדש כשלא נמצא contract גם ב-lookup הישיר (ראה קוד) — נראות טובה יותר למקרה עתידי, לא שינוי-התנהגות
cross-layer tests: `test_bug112_telegram_approval_ttl.py`, `test_bug_stale_callback_ux.py` — קיימים כבר, מכסים בדיוק את הפונקציה הזו; ירוקים לפני ואחרי (ראו §Verification)

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `_reject_stale_telegram_approval()` מקבל את אותו `item`/`payload` כמו קודם — אין שינוי לחתימת הפונקציה או למבנה ה-payload הנכנס
output impact: **משתפר** — `reject()` בפועל נקרא ומצליח (transition `pending → rejected`) עבור כל contract שיש לו `contract_id` שמור ב-payload, כולל אלו שבהם `fingerprint_payload != tool_inputs` (למשל create_task עם `due_time`) — קודם נכשל שקט
authority impact: אין — עדיין `reject()` בלבד, אין ביצוע/אישור נוסף; אותה בדיקת `contract.status != "pending"` idempotency-guard בתוך `reject()` עצמו נשארת ללא שינוי
shared identifiers: `contract_id` — כבר קיים ב-`ActionContract`/ב-payload, לא שם חדש; `find_by_id()` כבר קיים ומשמש באותה פונקציה שורה מתחת (ל-verification) — לא API חדש
invariants: **משוחזר** — ה-invariant התיעודי "TTL expiry מבצע pending→rejected אטומי" (כבר היה בקוד כ-כוונה, לא בפועל בגלל הבאג) עכשיו מתקיים בפועל לכל המקרים שבהם contract_id נשמר; `reject()`'s עצמו נשאר ה-source of truth היחיד ל-transition, לא נוצר מקור-אמת מקביל
failure semantics: fail-open ל-cleanup בלבד (כפי שהיה) — אם ה-lookup/reject נכשל, המשתמש עדיין רואה "פג תוקף" (לא נחסם), אבל כעת עם visibility גבוהה יותר (logger.error חדש) למקרה שזה עדיין קורה
observability: `logger.error` חדש למקרה contract_id קיים אך `find_by_id()` לא מחזיר תוצאה — permits future audit
cross-layer tests: `test_bug112_telegram_approval_ttl.py` (מבחן קיים ל-TTL-expired callback flow), `test_bug_stale_callback_ux.py` — הורצו לפני ואחרי השינוי, ירוקים; טסט חדש נוסף (`test_bug155_ttl_expiry_contract_id_lookup.py`) שמדגים במפורש את התרחיש שהיה שבור: contract עם `fingerprint_payload` שונה מ-`tool_inputs` (due_time) — מוודא ש-TTL expiry מעביר אותו ל-`rejected` בפועל

### Proof of non-impact — שכבות 1, 2
1. **grep evidence:** `grep -n "leads_reasoning_projection\|BUG-104\|route_request\|RouteDecision\|TurnCoordinator" <diff files>` — 0 תוצאות בקוד שהשתנה (`app.py` שורות 2246-2280 בלבד שונו).
2. **unchanged-tests evidence:** `python3 core/router/test_router.py` ו-`python3 test_bug104_*.py` (כל 5 החבילות) הורצו לפני ואחרי השינוי — תוצאה זהה (ראו §Verification).
3. **no-new-coupling evidence:** אין import חדש מ-`core/router/*` או מ-`core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py` בקובץ ששונה.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — השינוי נוגע ב-`ActionContract.status` (transition pending→rejected)
ובניסוח-הפונה-למשתמש-על-status ("TTL expired"). **איך:** לא נוסף מנגנון grounding/
evidence עצמאי — הקוד ממשיך להשתמש אך ורק ב-`core/action_gateway.py`'s
`reject()`/`find_by_id()`/`_ledger` הקיימים כ-source of truth היחיד. אין קריאה
ל-`core/anti_hallucination.py`/RP4 כאן (לא היה קודם, לא נוסף) — התיקון הוא תיקון
לוקאפ בתוך שכבה 4 בלבד, לא משנה את איך evidence/grounding מחושבים או מדווחים.
`validate_agent_output()` (שכבה שלא קיימת) לא מעורב.

## Verification (לפני מיזוג)

- `python3 -m py_compile app.py` — syntax תקין.
- `python3 test_bug112_telegram_approval_ttl.py` — ירוק, ללא שינוי בתוצאה.
- `python3 test_bug_stale_callback_ux.py` — ירוק, ללא שינוי בתוצאה.
- `python3 test_bug155_ttl_expiry_contract_id_lookup.py` (חדש) — ירוק, משחזר את
  התרחיש המדויק מ-staging (contract עם `fingerprint_payload` הכולל `due_time`
  השונה מ-`tool_inputs`) ומוודא ש-`reject()` נקרא בפועל ומעביר ל-`status=rejected`.
- `python3 smoke_tests.py` — ירוק.

## סטטוס

קוד מומש. **לא מוזג ל-main, לא deployed, לא verified ב-production** — עומד
בדרישות ה-Cross-Layer gate לביצוע קוד, לא ב-Rule 15 (main+deploy+production
verification) שנדרש לפני כל טענת "תוקן"/"✅ Fixed".
