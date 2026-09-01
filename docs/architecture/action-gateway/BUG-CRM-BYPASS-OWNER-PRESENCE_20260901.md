# BUG-CRM-BYPASS-OWNER-PRESENCE — deterministic create_deal approved but failed execution

**תאריך:** 01/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— התיקון מוכל כולו בתוך `app.py::_queue_deterministic_create_deal()`; אין
שינוי ל-`action_validator.py`, ל-`tools/dispatcher.py`, ל-`ActionGateway`,
או למדיניות אישור.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — תיקון payload
בשכבת ה-caller (Turn Coordinator) שכבר קיים; אין שינוי חוזה/authority/
routing/runtime-wiring חדש.

## הרקע

מיד לאחר deploy של PR #1172 (המסלול הדטרמיניסטי ל-`Intent.CREATE_DEAL`,
`86c5c13`), הבעלים שלח קנרית production אמיתית: "צור עסקה בשם
בדיקת-קנרית 2 בתחום יבוא". המסלול הדטרמיניסטי עבד **בדיוק** כמתוכנן —
`intent=create_deal handler=tool`, `agent_calls=0`, `action_tool=crm_create_deal`,
contract הוצע ואושר ע"י הבעלים. אבל הביצוע נכשל: "❌ אושר אך נכשל
בביצוע". קרה פעמיים ברציפות, אותה תוצאה בדיוק.

## הבאג

`_queue_deterministic_create_deal()` בנה במכוון payload בלי `owner_id` —
ההנחה הייתה ש-`tools/dispatcher.py`'s `case "crm_create_deal":` הקיים
יפתור owner חסר בעצמו דרך `_resolve_authenticated_crm_owner()`/
`core/owner_resolution.py` (מנגנון שנוסף ב-**PR #1166**, "Commercial CRM
Owner SSOT remediation").

ההנחה שגויה: `action_validator.py`'s שער-נוכחות עצמאי
(`_REQUIRED_PARAMS["crm_create_deal"] = ["name", "domain", "owner_id"]`)
**רץ לפני** לוגיקת ה-case הפרטנית של הדיספצ'ר, וחוסם כל קריאה בלי המפתח
`owner_id` — בלי קשר לכך שהדיספצ'ר בעצמו יכול היה למלא אותו. לוגיקת
ה-resolution מ-PR #1166 מעולם לא הופעלה בפועל.

**נקודה חשובה:** זה חושף שהתיקון של PR #1166 מעולם לא הוכח שעובד
end-to-end בפרודקשן. תיעוד ה-TR-27 של אותו PR עצמו אמר זאת במפורש: "No
successful production canary exists" — הבדיקות שם היו STATIC_VERIFIED
בלבד (unit tests עם מוקים), ואף אחת מהן לא הריצה נתיב אמיתי דרך
`action_validator`+dispatcher+resolution יחד, כי עד למסלול הדטרמיניסטי
הזה לא היה שום קורא חי (Telegram) שהגיע ל-`crm_create_deal`'s ביצוע
בפועל. הבאג היה שם **מאז PR #1166**, וחיכה לקורא אמיתי שיחשוף אותו.

## התיקון

`_queue_deterministic_create_deal()` שולח כעת `owner_id=identity.user_id`
— ה-self-reference הגולמי של הזהות המאומתת (לא record ID מפוברק). זה:
1. מספק את שער-הנוכחות של `action_validator.py`.
2. תואם בדיוק לרשימת ה-"self values" שכבר קיימת ונבדקה
   ב-`_resolve_authenticated_crm_owner()` (מ-PR #1166) — ממשיכה לפתור
   אותו ל-Profile record ID אמיתי כרגיל, בלי לעקוף שום תיקוף.

`fingerprint_payload` (המשמש לזיהוי עסקי/dedup) נשאר ללא `owner_id` —
זהה ל-`deal_parse.business_identity()` המקורי, בכוונה (owner_id תלוי-זמן
ריצה, לא חלק מהזהות העסקית שהמשתמש הקליד).

## Verification

- regression test חדש (`test_bug_crm_bypass_create_deal_deterministic_route.py`'s
  "regression: full execution path") מריץ את `action_validator`+
  `tools/dispatcher.py`+`_resolve_authenticated_crm_owner()` האמיתיים יחד
  (רק קריאת ה-Airtable עצמה מדומה) — אומת דרך `git stash` שנכשל **בדיוק**
  עם הודעת השגיאה האמיתית מהפרודקשן ("מי הבעלים?") על הקוד הישן, ועובר
  עם התיקון.
- רגרסיה מלאה: `smoke_tests.py`, `test_integration.py`,
  `core/router/test_router.py` (54/54), `test_create_task_deterministic_route.py`,
  `test_bug_task_01_execution_proof_fingerprint_parity.py` (11/11),
  `test_action_gateway.py` (46/46), `test_stage_b_full_suite.py` (128/128),
  `test_commercial_crm.py` (97/97), `test_commercial_crm_dispatcher_wiring.py` (40/40),
  `test_bug_commercial_crm_dispatcher_bypass_closure.py`,
  `test_pa01_phantom_approval_enforcement.py` (108/108),
  `test_commercial_crm_owner_ssot.py`, `test_avi_pilot_scope.py`,
  `test_audit_turn_coordinator_bypass.py` (22/22 combined) — כולם ירוקים.
- `python3 tools/audit_turn_coordinator_bypass.py` — `PASS`
- `python3 tools/audit_dispatcher_bypass.py` — `new=0`
- `python3 -c "import app; import tma_api; import tools.dispatcher"` (עם משתני CI) — עבר
- `git diff --check` — נקי

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** דורש קנרית owner-approved אמיתית חוזרת (אותה הודעה
בדיוק: "צור עסקה בשם X בתחום Y") אחרי merge+deploy לפני שסטטוס זה יתעדכן
ל-Verified — ראה `BUG_AUDIT_LOG.md`'s `BUG-CRM-BYPASS-OWNER-PRESENCE`
entry.
