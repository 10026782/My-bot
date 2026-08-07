# BUG-158 — כפתור אישור/ביטול שפג ב-EventBus מדווח "לא זמין" גם כש-ActionContract עדיין pending

**תאריך:** 07/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ישירות ב-Durable Atomic Approval layer (שכבה 4): `app.py::_handle_approval_callback_impl()`
ו-`core/action_gateway.py::ActionGateway`.
**רקע:** נמצא ע"י בדיקת staging ידנית (owner, 05-07/08/2026) על `my-bot-approval-staging`
— לוגים מלאים אומתו, ראה ניתוח מפורט בהודעות ה-session. הבעיה **לא** קשורה ל-BUG-155
(שתוקן ב-PR #550/#552) — היא באג נפרד, במנגנון אחר לגמרי.

## הבעיה

לחיצה על כפתור טלגרם (✅/❌) לאחר שה-item המתאים ב-`event_bus.py`'s `PendingActionsStore`
כבר פג (TTL הפנימי של EventBus, ~30 דקות — נפרד לגמרי מ-24h TTL של ה-`ActionContract`
עצמו) מחזירה למשתמש: **"ℹ️ הפעולה כבר אינה זמינה, ולכן לא בוצעה."** — ניסוח שמשתמע ממנו
שאין יותר שום פעולה קיימת. בפועל, ה-`ActionContract` (מקור האמת האמיתי, 24h TTL) יכול
**להישאר pending וחי לגמרי**, ולחזור מאוחר יותר (reconfirmation אחרי הודעה לא-קשורה,
או "מאשר"/"כן" בטקסט) — מה שהמשתמש כבר האמין שבוטל/לא קיים מבצע בפועל.

### הרצף שאומת ב-staging (05/08/2026, 22:50-23:53)

1. `22:50:57` — `propose_action()` יוצר contract `acafca28...` (status=pending).
2. משתמש לוחץ כפתור (זמן מדויק לא ידוע, לפני `22:50:57` או סמוך לו) על callback ישן
   שכבר לא ב-`bus` → מקבל "ℹ️ הפעולה כבר אינה זמינה" — **ה-contract לא נוגע בכלל**.
3. `22:54:57` — הודעה לא-קשורה מגיעה → `context_interrupted=True` מסומן על ה-contract
   (מנגנון תקין, לא קשור לבאג הזה).
4. `23:33:59`, `23:53:xx` — בקשות create_task חדשות נחסמות (`BUG-122` gate, `live_
   contracts_count=1`) — כי ה-contract "המבוטל-כביכול" עדיין pending.
5. `23:53:45` — אחרי reconfirmation, ה-contract **מבוצע בפועל**.

## Root Cause (אומת בקוד, 07/08/2026)

`app.py::_handle_approval_callback_impl()` — **שני** ה-branches (`action=="approve"`,
שורה 2538, ו-`action=="reject"`, שורה 2923) קוראים ל-`bus.pop(action_id)`. אם `bus.pop()`
מחזיר `None` (ה-item פג ב-TTL הפנימי של `event_bus.py`, ~30 דקות) — **שניהם** מיד קוראים
ל-`_notify_missing_or_expired_callback()` (שורות 2597, 2926) ומחזירים — **בלי לבדוק את
מצב ה-`ActionContract` בכלל**.

זה סותר קוד שכבר קיים **באותה פונקציה, מוקדם יותר**: שורות 2519-2536 —
```python
if callback_contract_id and _flag_enabled("FEATURE_ACTION_GATEWAY"):
    _callback_result = _callback_gateway.lifecycle_result(callback_contract_id, repeated=True)
    if _callback_result.canonical_state != "pending":
        ...  # מדווח נכון ומחזיר
```
כלומר: ה-callback_data של הכפתור עצמו (לא ה-`bus` item!) כבר **נושא את ה-contract_id
הקנוני** (`callback_contract_id`, מפורמט PR1: `action:action_id:contract_id`) — ובודק את
מצבו האמיתי **לפני** ש-`bus.pop()` בכלל נקרא. אבל הבדיקה הזו רק **חוסמת** כשה-contract
כבר terminal (לא pending) — כשהוא **עדיין pending**, היא נופלת דרך בכוונה, על ההנחה
שהזרימה הרגילה (מבוססת `bus.pop()`) תטפל בו כרגיל. ההנחה הזו שוברת בדיוק כש-`bus.pop()`
נכשל: הידע הנכון ("ה-contract עדיין pending!") שכבר חושב **באותה קריאה**, נזרק, ומוחלף
ב"אינה זמינה" — שקר תפעולי, כפי שה-owner זיהה.

**חוסר סימטריה נוסף שנחשד בתחילה ("reject שונה מ-approve") — נבדק ונמצא לא-רלוונטי:**
שני ה-branches (approve/reject) **חולקים בדיוק את אותו קוד כשל** (`if not item:
_notify_missing_or_expired_callback(...); return`) — זה לא הבדל בין reject ל-approve,
זו נקודת-כשל אחת (`_notify_missing_or_expired_callback` לא בודקת ActionGateway) שמופיעה
פעמיים, ב-branch ANDN. כשה-`bus.pop()` **כן** מצליח (בתוך ~30 הדק'), שני ה-branches
כן פועלים כראוי מול ה-Gateway עם וידוא מפורש (`app.py:2965-2976` ל-reject,
`app.py:2748-2759` ל-approve).

## המדיניות שנבחרה (owner, 07/08/2026)

מבין שתי החלופות הלגיטימיות שהעלה ה-owner:
- **אפשרות א** — פקיעת הכפתור מבטלת גם את הפעולה (`pending → expired/rejected`).
- **אפשרות ב** — רק הכפתור פג; הפעולה עדיין pending; ההודעה חייבת לומר זאת במפורש.

**נבחרה אפשרות ב', בלי לשנות התנהגות קיימת**: ה-`ActionContract` הוא מקור האמת (24h
TTL, קיים ומכוון — ראה `core/action_contract_repository.py:79-84`). אין הצדקה לבטל
פעולה אמיתית רק כי עותק-cache פנימי ב-EventBus (רכיב legacy, 30 דק') פג. הבעיה איננה
ה-TTL עצמו — היא ש**המערכת כבר יודעת** (`callback_contract_id`) שה-contract עדיין
pending, ומתעלמת מהידע הזה. התיקון: השתמש בידע הזה **גם** כש-`bus.pop()` נכשל, במקום
לוותר.

## התיקון

פונקציית עזר חדשה, `_recover_pending_item_from_contract(contract_id)` — משחזרת מבנה
`item` זהה-בצורתו ל-item רגיל של `bus.pop()`, **ישירות מתוך ה-`ActionContract`** (לא
מ-EventBus): `tool_name`, `normalized_payload`, `origin_channel`, `origin_chat_id`,
`canonical_user_id` — כל אלה כבר שדות קיימים וסמכותיים על ה-contract עצמו, לא צריך
עותק EventBus כדי לדעת אותם. מחזירה `None` אם ה-contract לא נמצא או כבר לא pending —
במקרה הזה ההתנהגות הקיימת (`_notify_missing_or_expired_callback`) ממשיכה **ללא שינוי**
(זה עדיין המקרה הנכון — אין מה לשחזר).

בשני ה-branches (`approve`, `reject`), כש-`bus.pop()` מחזיר `None`:
```python
item = bus.pop(action_id)
if not item:
    item = _recover_pending_item_from_contract(callback_contract_id)
    if not item:
        _notify_missing_or_expired_callback(cq, approver_chat_id)
        return
```
משם, **כל שאר הקוד הקיים רץ ללא שום שינוי** — כי `item["payload"]`/`item.get("label")`
כבר בדיוק באותה צורה שהקוד הקיים מצפה לה. שום duplicate logic — reuse מלא של
`approve_with_lifecycle_result()`/`reject_with_lifecycle_result()` הקיימים, כולל
הוידוא המפורש שכבר קיים שם.

**ללא שינוי בהתנהגות** כש-`bus.pop()` מצליח (המקרה הנפוץ, תוך ~30 דק') — הפונקציה
החדשה אף פעם לא נקראת. גם `_reject_stale_telegram_approval()`'s TTL check (10 דק',
BUG-112/155) **לא** מושפע — `item.get("created")` על ה-item המשוחזר הוא `None`, אז
בדיקת ה-staleness שם פשוט לא מופעלת (סביר: כבר ביססנו ישירות מול ActionGateway
ש-הcontract pending — בדיקה חלשה יותר מבוססת-timestamp מיותרת פה).

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched — אין קשר ל-`leads_reasoning_projection`/routing.

### שכבה 2 — TurnCoordinator
touched: not touched — `route_request()` לא נוגע; זה callback_query, לא text turn.

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly — `_handle_approval_callback_impl()` היא caller קיים של
`ActionGateway`, לא tool/schema/dispatcher חדשים. אין שינוי ל-`tool_registry.py`/
`tools/dispatcher.py`/`tools/schemas.py`.

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `_handle_approval_callback_impl()` מקבלת אותו `cq` בדיוק — אין שינוי
  ל-callback_data format/API.
output impact: **התנהגות חדשה רק כש-`bus.pop()` נכשל אך `callback_contract_id`
  מצביע ל-contract pending** — כרגע היה: "אינה זמינה" שגוי. אחרי: reject/approve
  אמיתי מול ה-contract, בדיוק כמו כפתור טרי. **ללא שינוי** בכל שאר המקרים
  (item נמצא רגיל, contract לא נמצא/לא pending).
authority impact: אין הרחבת סמכות — עדיין רק ה-approver המאומת (`approver_identity.
  is_owner or can("actions.approve")`, נבדק **לפני** השינוי הזה, שורה 2508) יכול
  לפעול; התיקון רק מרחיב **אילו callbacks תקינים מטופלים נכון**, לא מי מורשה.
shared identifiers: `_recover_pending_item_from_contract` שם חדש לגמרי.
invariants: **מבטיח לראשונה** ש-`ActionContract` pending אמיתי לא "נעלם" מנקודת
  מבט המשתמש רק כי cache פנימי (EventBus) פג — האינווריאנט המוצהר כבר ("ActionContract
  הוא מקור האמת") נאכף עכשיו גם בנתיב הזה.
failure semantics: `_recover_pending_item_from_contract` מחזירה `None` בכל מקרה
  לא-ודאי (contract לא נמצא, לא pending, flag כבוי) — fail-closed לאותה התנהגות
  קיימת ("אינה זמינה"), לא exception חדש.
observability: לוג `logger.info` חדש כש-שחזור מצליח (לראות תדירות התופעה בפועל).
cross-layer tests: `test_bug158_approval_callback_eventbus_ttl_recovery.py` (חדש).

### Proof of non-impact — שכבות 1, 2
1. grep evidence: `grep -n "route_request\|RouteDecision\|TurnCoordinator" app.py` בטווח
   השינוי (`_handle_approval_callback_impl`, שורות 2408-3000) — 0 תוצאות רלוונטיות.
2. no-new-coupling: אין import חדש מ-`core/router/*`.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — נוגע ב-approve/reject lifecycle. **איך:** משחזר item ישירות מ-`ActionContract`
עצמו (מקור האמת הקיים) — לא ממציא evidence/status חדש; ה-`safe_user_message` שמוחזר
למשתמש מיוצר ע"י אותם `approve_with_lifecycle_result()`/`reject_with_lifecycle_result()`
קיימים, ללא שינוי לניסוח שלהם.

## Verification

- `python3 -m py_compile app.py`
- `python3 test_bug158_approval_callback_eventbus_ttl_recovery.py` (חדש)
- `python3 smoke_tests.py` / `test_integration.py`

## סטטוס

עיצוב אושר ע"י owner (07/08/2026 — אפשרות ב', "רק הכפתור פג, הפעולה עדיין pending").
קוד בעבודה.
