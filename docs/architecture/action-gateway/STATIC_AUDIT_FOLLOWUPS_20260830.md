# Static-audit follow-ups — נעילת approve(), אסימטריית כפתור/טקסט חופשי, ותיקון baseline

**תאריך:** 30/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ישירות ב-Durable Atomic Approval layer (שכבה 4): `core/action_gateway.py`'s
`ActionGateway.approve()`, ו-`app.py::_handle_approval_callback_impl()` (השכבה שממלאת
בפועל את מקום ה-approval callback boundary).
**רקע:** שלושת ה-follow-ups שנרשמו ב-`docs/audit/ACTIONGATEWAY_STATIC_BYPASS_VERIFICATION_20260830.md`
(#1106) — סקירת bypass סטטית ל-ActionGateway/dispatcher/approval שסיימה ב-STATIC
VERIFIED (אין bypass נתמך). שלושת הממצאים לא היו bypass חי, אבל נרשמו כ-code gaps/
drift שראוי לסגור. מסמך זה סוגר את שלושתם ב-PR נפרד (#1107, doc-only ל-#1106 עצמו
כבר מוזג).

---

## 1. `ActionGateway.approve()` — TOCTOU בין בדיקת status לכתיבתו

**הבעיה:** `approve()` קורא `find_by_id()`, בודק `contract.status != "pending"`,
ורק אח"כ קורא `update_status(..., "approved", ...)` — שני צעדים נפרדים, ללא נעילה
אטומית משל עצמו. שני threads שקוראים ל-`approve()` על אותו `contract_id` בו-זמנית
יכולים שניהם לעבור את הבדיקה לפני ששניהם כותבים, ושניהם להמשיך ל-`_execute_contract()`
— ביצוע כפול של אותה פעולה עסקית.

הבטיחות היום נשענת **לחלוטין** על כל caller שמנעל חיצונית: `app.py`'s TC8
turn-claim (`_tc8_claim_contract`/`TurnStateRepository`, Postgres CAS אמיתי) לפני
קריאת ה-callback/free-text confirm, ו-`tools/approval_actions.py`/`tma_api.py`'s
`threading.Lock` per-approval_id (in-process בלבד, לא cross-process-safe).

**למה לא `update_status(require_status="pending")`:** `ActionContractRepository`
(האחסון העמיד ל-Airtable) מצהיר `supports_atomic_conditional_transition = False`
(`transition()` הוא read-check-PATCH, לא CAS אמיתי) — כשה-repository הזה פעיל
(`FEATURE_ACTION_CONTRACT_PERSISTENCE=true`), כל קריאה ל-`update_status(require_status=...)`
נכשלת-סגורה תמיד (ללא PATCH כלל), לא רק בעימות אמיתי. הוספת `require_status="pending"`
ל-`approve()` הייתה שוברת כל אישור, לא רק אישורים מקבילים.

**התיקון:** `ActionGateway` מחזיק striped lock פנימי (64 מנעולים, `hash(contract_id) % 64`)
— `approve()` נועל את ה-stripe של ה-contract_id לפני שהיא מאצילה ל-`_approve_unlocked()`
(שם עברה כל הלוגיקה המקורית ללא שינוי). כך שני threads שמנסים לאשר את אותו contract_id
בו-זמנית לעולם לא יעברו את הבדיקה שניהם. הבטיחות הופכת אינהרנטית ל-Gateway עצמו, לא
מוסכמה שכל caller עתידי חייב לחזור עליה.

**ponytail:** striping 64-way, לא lock פר-contract_id — זיכרון חסום לאורך חיי ה-singleton.
שני contract_id שונים עלולים (נדיר) להתנגש על אותו stripe (סריאליזציה עודפת לא-מזיקה);
אותו contract_id תמיד ממופה לאותו stripe (הערבות שבאמת חשובה). שדרוג ל-lock אמיתי
פר-contract (עם ניקוי) אם אי-פעם יתגלה contention.

**ראיה:** `test_action_gateway.py` — טסט חדש (`STATIC-AUDIT-20260830`) עם 8 threads
אמיתיים שמנסים `approve()` על אותו contract_id בו-זמנית (executor עם `time.sleep(0.05)`
כדי להרחיב את חלון ה-race). אומת שהטסט **נכשל** בלי הנעילה ו**עובר** איתה. 46/46 עברו.

## 2. אסימטריה בין כפתור טלגרם לטקסט חופשי כש-`FEATURE_ACTION_GATEWAY` כבוי

**הבעיה:** `_handle_approval_callback_impl()` חיפש contract חי ב-ActionGateway
עבור כפתור ה-approve **רק** כש-`FEATURE_ACTION_GATEWAY` פעיל. כשהדגל כבוי (ברירת
המחדל בקוד), כפתור נכשל תמיד עם `LEGACY_GATEWAY_DISABLED` — גם מול contract חי
ותקין — בעוד שנתיב האישור בטקסט חופשי ("כן") כבר בודק contracts חיים ללא תלות
בדגל (BUG-056, `app.py`'s `route_confirmation_word` branch). זו לא פרצת אבטחה
(נכשל-סגור, לא נכשל-פתוח) אלא פער-זמינות: אותו contract התנהג אחרת דרך שני
נתיבי-אישור נתמכים.

**התיקון:** הוסר ה-`if _flag_enabled("FEATURE_ACTION_GATEWAY")` שעטף את חיפוש
ה-contract בכפתור — עכשיו רץ ללא תנאי, בדיוק כמו BUG-056. שני הענפים שהיו תלויים
בדגל (`elif` flag-on-no-contract, `else` flag-off) אוחדו לענף אחד: "לא נמצא
contract → נכשל-סגור עם תשובת stale/expired דטרמיניסטית", ללא תלות בדגל.

**ראיה:** `test_pr0c_telegram_callback_gateway.py` — Test 1 עודכן לצפות לתשובה
המאוחדת (לא ל-`LEGACY_GATEWAY_DISABLED`); Test 6 חדש מוכיח שכשה-flag כבוי אבל
contract חי קיים, הכפתור עכשיו מבצע דרך `ActionGateway.approve()` בדיוק כמו
Test 2. 15/15 עברו.

## 3. Line-drift ב-baseline של `tools/audit_result_parsing.py`

**הבעיה:** `tools/audit_result_parsing.py` (סורק false-success text-parsing,
warning-only ב-CI) דיווח `media_handler.py:852` כממצא חדש. חקירה: זו אותה assertion
עצמה שכבר קיימת ב-baseline בשורה 521 (`assert "✅" in ok_text` על הפלט של
`_format_media_result()` עצמו — self-test, לא parsing של תוצאת tool חיצוני) —
`media_handler.py` גדל מ-~600 ל-1500+ שורות מאז שה-baseline נלקח (03/07/2026),
והזיז את אותה assertion בלי לגעת בתוכנה. שורה 521 כבר לא תואמת את הדפוס בכלל.

**התיקון:** עדכון ה-`BASELINE` tuple במקום (521 → 852) עם הערה שמסבירה את ה-drift.
אין שינוי התנהגות קוד; הסקריפט נשאר warning-only.

**ראיה:** `python3 tools/audit_result_parsing.py` — `0 new` (היה `1 new`).
`test_response_contract_fixes.py`'s static guard (19/19) לא הושפע.

---

## סיכום ראיות

- `test_action_gateway.py`: 46/46
- `test_pr0c_telegram_callback_gateway.py`: 15/15
- `test_response_contract_fixes.py`: 19/19
- סוויטת רגרסיה מלאה (~30 קבצי `test_*.py` הקשורים ל-approval/dispatcher/gateway): 0 נכשלים
- `tools/audit_dispatcher_bypass.py`, `tools/audit_gateway_bypass.py`: `new=0`
- `smoke_tests.py`, `python -m compileall -q .`: עוברים
