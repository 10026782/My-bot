# BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY — closing the duplicate approval-pending reply for crm_create_deal

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— תוספת guard אחד בתוך `app.py`'s `_queue_deterministic_create_deal()`,
שכפול מדויק של guard קיים שכבר פועל ב-`_queue_deterministic_create_task()`.
אין כותב קנוני חדש, אין חוזה/authority/routing חדש.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — מוכל כליל בשכבת
ה-Turn Coordinator/Reply layer ב-`app.py`, מראה בדיוק את הדפוס הקיים כבר
ל-Task.

## הרקע

קנרית production חיה (02/09/2026, "בדיקת-קנרית 11": "צור עסקה בשם
בדיקת-קנרית 11 בתחום Import") — לאחר ש-BUG-CRM-BYPASS-DOMAIN-SELECT-CASING
ו-BUG-CRM-BYPASS-UPDATE כבר סגרו את שכבות ה-domain-translation/casing
ו-airtable_update, הבעלים דיווח על תופעה חדשה: הבוט שלח **שתי** הודעות
נפרדות על אותה בקשת יצירת עסקה — אחת "הפעולה הושלמה: ..." ואחת "יש פעולה
שממתינה לאישור: ...". אבחון ראשוני שגוי שלי (סתירת completed/pending)
תוקן ישירות על ידי הבעלים: זו לא סתירה אלא באג כפל-הודעות ישן — ההודעה
השנייה (הלא-אינטראקטיבית) נשארת קפואה עם "ממתין לאישור" גם אחרי שהפעולה
כבר אושרה, בדיוק כמו באג UX שכבר תוקן פעם אחת בעבר ("תוקן בעבר במסגרת
UX עכשיו חזר כחלק מהרגרסיה של הסבבים שלנו").

## הממצא

`_queue_approval_detailed_impl()` שולח **שתי** תוצרים נפרדים לכל בקשת
אישור:

1. הודעת Telegram **אינטראקטיבית** ל-`owner_chat_id`, עם מקלדת
   אישור/ביטול inline (`bot.send_message(owner_chat_id, _pending_text,
   reply_markup=kb)`), שנשלחת סינכרונית בתוך `_queue_approval_detailed_impl`
   עצמה. הודעה זו **כן** מתעדכנת במקום (`edit_message_text`) כשלוחצים
   אשר/בטל, כי ה-`callback_data` שלה נושא את `action_id`/`contract_id`.
2. ערך `outcome["message"]` (טקסט פשוט, "יש פעולה שממתינה לאישור: ..."),
   שמוחזר לקורא לשימוש כתשובת הצ'אט הרגילה לבקשה המקורית.

`app._queue_deterministic_create_task()` **כבר** נושא הגנה מפורשת למקרה
שבו ה-requester וה-`owner_chat_id` הם אותו chat (המקרה הרגיל בבוט
חד-בעלים זה): אם `outcome.get("owner_notified")` וה-chat זהה, הפונקציה
מחזירה מחרוזת ריקה במקום `outcome["message"]`, כדי לא לשלוח הודעה שנייה
על אותה פעולה בדיוק. `app._queue_deterministic_create_deal()` — שנכתב
במפורש "מראה את `_queue_deterministic_create_task()` בדיוק" (ראה
ה-docstring שלה, מ-BUG-CRM-BYPASS follow-up, 01/09/2026) — **לא כלל
את ההגנה הזו בכלל**. זו רגרסיה נקודתית בהעתקה, לא בעיה ארכיטקטונית
חדשה: ה-guard כבר קיים, פתור, ומכוסה ב-regression test (Task); הוא
פשוט לא הועתק יחד עם שאר התבנית כשנוסף המסלול הדטרמיניסטי ל-Deal.

## למה לא ניתן פשוט להסיר את השליחה הראשונה (ההודעה האינטראקטיבית)

ההודעה האינטראקטיבית (עם מקלדת האישור) היא **חובה** — היא הערוץ היחיד
שדרכו הבעלים בפועל מאשר/מבטל את הפעולה, ורק היא נעקבת ל-`edit_message_text`.
ה-guard לכן חייב לפעול בכיוון ההפוך: להשתיק את ההודעה השנייה (הפשוטה,
הלא-נעקבת), לא לגעת בראשונה.

## התיקון

נוסף ל-`_queue_deterministic_create_deal()` **בדיוק** אותו guard הקיים
ב-`_queue_deterministic_create_task()`:

```python
owner_chat_id = (
    os.environ.get("OWNER_TELEGRAM_ID", "") or
    os.environ.get("ELIYAHU_CHAT_ID", "") or
    os.environ.get("DIGEST_CHAT_ID", "")
)
if outcome.get("owner_notified") and str(owner_chat_id) == str(chat_id):
    logger.info(
        "[DeterministicCreateDeal] duplicate_reply_suppressed=true "
        "reason=owner_notification_already_sent"
    )
    return ""
return outcome.get("message") or "לא הצלחתי להכניס את העסקה לאישור."
```

כשה-requester **שונה** מה-owner (מקרה תיאורטי/עתידי, לא הבוט חד-הבעלים
הנוכחי) — ההודעה השנייה **כן** ממשיכה להישלח: היא לגיטימית שם, כי
המבקש (שאינו ה-owner) צריך לדעת שהבקשה שלו נכנסה לתור, ורק ה-owner
רואה את ההודעה האינטראקטיבית. נוספה גם השלמת
`out_meta["reply_owner"]`/`out_meta["final_response_count"]` לענף
היצירה, לעקביות עם `_queue_deterministic_create_task()`.

## Verification

קובץ regression חדש (`test_bug_crm_deal_duplicate_approval_reply.py`,
8 טסטים) — מוכיח:

1. כשה-requester הוא ה-owner: ה-send השני מדוכא (מחרוזת ריקה), רק
   שליחת Telegram אחת קורית בפועל, וה-contract הפנימי עדיין נוצר פעם
   אחת בלבד (ה-suppression משפיע על טקסט-התשובה בלבד, לא על ה-contract).
2. כשה-requester **שונה** מה-owner: שתי ההודעות ממשיכות להישלח כצפוי
   (לא נשברה התנהגות לגיטימית).
3. הרצה מלאה דרך ה-parser האמיתי עם הטקסט המדויק מהקנריה ("צור עסקה
   בשם בדיקת-קנרית 11 בתחום Import") משחזרת ומוכיחה את הסגירה.

`python3 -m compileall -q .`, `smoke_tests.py`,
`tools/audit_turn_coordinator_bypass.py`,
`tools/status_sync_validator.py`, `git diff --check`, ו-
`test_bug_crm_bypass_create_deal_deterministic_route.py`,
`test_first_pending_notification_failure_suppression.py`,
`test_bug_crm_bypass_airtable_update.py`,
`test_pr1_single_speaker_approval_ux.py`,
`test_f52_status_reply_reconciliation.py` (51/51),
`test_bug_approval_callback_hardening.py` (41/41),
`core/router/test_router.py` (54/54) — כולם ירוקים, אפס רגרסיות.

## סטטוס

Fixed (STATIC_VERIFIED) — ממתין ל-merge + deploy + קנרית production חיה
שמאמתת שאחרי אישור נשלחת/מתעדכנת הודעה **אחת** בלבד, ללא שאריות "ממתין
לאישור" קפואות. ראה `BUG_AUDIT_LOG.md`'s `BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY`
entry למעקב מלא.
