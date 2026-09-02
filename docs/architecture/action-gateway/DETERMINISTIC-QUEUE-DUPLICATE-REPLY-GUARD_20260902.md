# DETERMINISTIC-QUEUE-DUPLICATE-REPLY-GUARD — a shared helper + CI guard so the BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY class of gap can't ship again

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— refactor בתוך `app.py` (חילוץ helper משותף מ-3 פונקציות קיימות, ללא
שינוי התנהגות) + שער CI שישי ב-`tools/audit_turn_coordinator_bypass.py`,
באותו דפוס בדיוק כמו 5 השערים הקיימים. אין כותב קנוני חדש, אין
חוזה/authority/routing חדש.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — מוכל כליל בשכבת
ה-Turn Coordinator/Reply layer ב-`app.py` ובשער ה-CI הסטטי שמאמת אותה.

## הרקע

לאחר סגירת BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY (הודעה כפולה על אותה
בקשת-אישור ל-`crm_create_deal`), הבעלים שאל: איך מונעים את החזרה על אותם
סבבים בכל כתיבה/writer חדש — האם צריך תבנית/template מתועדת ליצירת כותב
חדש? התשובה שניתנה: תיעוד בלבד כבר נכשל פעם אחת בדיוק על הבאג הזה —
ה-docstring של `_queue_deterministic_create_deal()` הצהיר במפורש "מראה את
`_queue_deterministic_create_task()` בדיוק", ועדיין החסיר את ההגנה
הספציפית הזו. הבעלים אישר לפעול לפי הגישה המועדפת: helper משותף (מבני,
לא תיעודי) + שער CI (כמו שכבר נעשה ל-`airtable_update`).

## הממצא הנוסף (התגלה תוך כדי בניית ה-helper)

`app._queue_deterministic_task_update()` (המשמש `update_task`/`complete_task`)
**גם הוא** מעולם לא נשא את הגנת ה-`duplicate_reply_suppressed` — מופע
שלישי, סמוי, של אותה מחלקת באג בדיוק: `queue_task_request()`'s תוצאה
מוחזרת ישירות (`return outcome.get("message") or "..."`) ללא בדיקת
`owner_notified`/same-chat. זוהי אותה חשיפה מבנית בדיוק כמו ב-Deal לפני
התיקון. נסגר באותו PR, לא נפתח כפריט נפרד — הוא בדיוק המקרה שה-CI guard
נועד לתפוס.

## התיקון

### 1. Helper משותף — `app._finalize_deterministic_queue_outcome()`

חילוץ הזנב החוזר משלוש הפונקציות (`_queue_deterministic_create_task`,
`_queue_deterministic_create_deal`, `_queue_deterministic_task_update`)
ל-helper אחד:

```python
def _finalize_deterministic_queue_outcome(
    outcome: dict, chat_id: str, out_meta: dict | None, log_prefix: str,
    fallback_message: str,
) -> str:
    ...
```

מבצע, בסדר הזה: (1) `out_meta` population כש-contract נוצר בפועל
בתור הזה; (2) לוג `[log_prefix] בעלות_coordinator=True ...`; (3) חישוב
`owner_chat_id`; (4) אם `outcome.get("owner_notified")` וה-chat זהה —
מדכא (מחזיר `""`); אחרת מחזיר `outcome["message"]` או `fallback_message`.
כל אחת משלוש הפונקציות הקוראות עברה refactor להעביר את ה-`outcome` שלה
דרך ה-helper במקום לבנות את התשובה בעצמה — **ללא שינוי התנהגות** לשני
הנתיבים שכבר עבדו נכון (create_task, create_deal), ו**סגירת** הבאג
הסמוי ב-task_update.

### 2. שער CI שישי — `DETERMINISTIC_QUEUE_DUPLICATE_REPLY_SUPPRESSION`

נוסף ל-`tools/audit_turn_coordinator_bypass.py`, באותו דפוס בדיוק כמו
שער 5 (`PROTECTED_BUSINESS_TABLE_RAW_UPDATE`): `find_deterministic_queue_
functions()` מחלץ (regex, לא AST מלא — אותה רמת קפדנות כמו שאר השערים
בקובץ) כל `def _queue_deterministic_*(...)` מ-`app.py`, ו-
`check_deterministic_queue_duplicate_reply_suppression()` מוודא ש-**כל**
פונקציה כזו קוראת ל-`_finalize_deterministic_queue_outcome(` בגוף שלה.
פונקציה חדשה שלא קוראת ל-helper — או הסרת ה-helper עצמו — נכשלת, עם
הודעה מפורשת שמצביעה בדיוק על השם והפתרון.

**נבדק בפועל** (לא רק תיאורטית): נוצר עותק זמני של `app.py` שבו
`_queue_deterministic_create_deal()` חוזר לבנות את התשובה בעצמו (בדיוק
צורת הרגרסיה המקורית) — אומת שהשער נכשל ומצביע במדויק על הפונקציה
הפגומה, בלי לתפוס את השתיים האחרות. אומת גם שהסרת ה-helper עצמו נתפסת.
שוחזר ואומת שהשער עובר שוב על הקוד האמיתי.

## Verification

`test_audit_turn_coordinator_bypass.py` — 6 טסטים חדשים (28/28 עם
הקיימים): חילוץ שלוש הפונקציות מ-snippet חי, זיהוי הסרת ה-helper
כליל, זיהוי "אח" אחד שעוקף את ה-helper (בלי לתפוס את השאר), ניקיון
כששלושתם קוראים ל-helper, וזיהוי "אין אף פונקציה כזו בכלל".

`test_bug_deterministic_queue_duplicate_reply_suppression.py` (קובץ
חדש, 9 טסטים) — מוכיח: (1) התנהגות ה-helper עצמו ברמת יחידה (owner
כ-requester → מדוכא; requester אחר → לא מדוכא; `out_meta` מתמלא רק
כש-contract נוצר בפועל; fallback message כשאין `message`); (2)
`_queue_deterministic_task_update()` — המופע הסמוי השלישי שהתגלה תוך
כדי הבנייה — כעת גם הוא סוגר את הכפילות, דרך ה-helper.

`python3 -m compileall -q .`, `smoke_tests.py`,
`tools/audit_turn_coordinator_bypass.py`,
`tools/status_sync_validator.py`, `git diff --check`, ו-
`test_bug_crm_deal_duplicate_approval_reply.py` (8/8),
`test_first_pending_notification_failure_suppression.py` (14/14),
`test_bug_crm_bypass_create_deal_deterministic_route.py`,
`test_turn_coordinator_task_runtime_integration.py`,
`test_bug_crm_bypass_airtable_update.py`,
`test_pr1_single_speaker_approval_ux.py`,
`test_f52_status_reply_reconciliation.py` (51/51),
`test_bug_approval_callback_hardening.py` (41/41),
`core/router/test_router.py` (54/54) — כולם ירוקים, אפס רגרסיות.

## סטטוס

Fixed (STATIC_VERIFIED) — ממתין ל-merge + deploy. הבא בתור (production
verification) יגיע בטבעיות מהשימוש הרגיל בבוט: כל בקשת create_task/
create_deal/update_task/complete_task עתידית שדורשת אישור היא כבר
בדיקת-רגרסיה חיה להתנהגות הזו. ראה `BUG_AUDIT_LOG.md`'s
`DETERMINISTIC-QUEUE-DUPLICATE-REPLY-GUARD` entry למעקב מלא.
