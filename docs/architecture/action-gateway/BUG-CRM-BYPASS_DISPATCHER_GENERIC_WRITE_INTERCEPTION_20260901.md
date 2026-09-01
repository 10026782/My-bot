# BUG-CRM-BYPASS — generic `airtable_add` bypassed canonical Deal/Payment Term/Payment writers

**תאריך:** 01/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— התיקון מוכל לגמרי בתוך `tools/dispatcher.py`'s `case "airtable_add":` (אותה
שכבה ואותה תבנית שכבר קיימת עבור Contacts); אין שינוי ל-ActionGateway,
ל-execution-proof, למדיניות אישור, או ל-lifecycle semantics.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — הרחבת דפוס יירוט
קיים (Contacts→Deals/PaymentTerms/Payments) בתוך הדיספצ'ר; אין חוזה/
authority/routing/runtime-wiring חדש חוצה-שכבות, ואין שינוי לתיקוף העסקי
(שנשאר בבעלות `commercial_crm.py` הבלעדית).

## הרקע — למה זה נבדק

בהמשך לביקורת "GOLDEN WRITER" (`commercial_crm.py`'s Deal/PaymentTerm/Payment
writers + `crm.py`'s Contact writer, לאחר תיקון BUG-CONTACT-03), בוצעה
ביקורת נתיב-מלא (proposal→ActionGateway→approval→execution proof→
dispatcher→writer→Airtable→evidence→response) שהוכיחה פער ארכיטקטוני קיים:
`tools/dispatcher.py`'s גנרי `case "airtable_add":` כבר מיירט וממיר כתיבות
גולמיות לטבלת Contacts לכותב הקנוני (`crm.py`), אך **לא** ביצע את אותו יירוט
עבור Deals / Payment Terms / Payments — כך שכתיבה גולמית לשלוש הטבלאות הללו
דרך `airtable_add` הייתה עוקפת לחלוטין את התיקוף העסקי הקנוני
(`commercial_crm.py`'s `create_deal`/`create_payment_term`/`create_payment`).

## הבאג (BUG-CRM-BYPASS, נמצא בביקורת, לא live-reported)

1. **עקיפת תיקוף עסקי**: `crm_create_deal`/`crm_create_payment_term`/
   `crm_create_payment` הם `requires_approval=True`, `high_risk=True`,
   `roles_allowed=_MANAGEMENT`, ועוברים דרך תיקוף שדות קנוני
   (`commercial_crm.py`). `airtable_add` הגנרי, לעומת זאת, לא זיהה את שלוש
   הטבלאות הללו כלל — כתיבה גולמית אליהן הייתה נכתבת ל-Airtable ללא אף אחד
   מהתיקופים העסקיים הללו (שם עסקה חסר, calc_type לא תקין, סכום ≤ 0 וכו').
2. **הסלמת הרשאה (role escalation)**: `airtable_add`'s `roles_allowed=_INTERNAL`
   (`owner/partner/manager/employee`) **רחב יותר** מ-`_MANAGEMENT`
   (`owner/partner/manager`) של שלושת הכלים הייעודיים — כלומר `employee`,
   שאסור לו להפעיל את הכלי הייעודי, יכול היה תיאורטית להגיע לאותה טבלה דרך
   `airtable_add` הגנרי.

## התיקון

הורחב דפוס היירוט הקיים של Contacts (`tools/dispatcher.py`'s
`case "airtable_add":`) לשלוש הטבלאות הנוספות — **ללא** שכפול תיקוף עסקי:

1. **`_DEAL_FIELD_MAP` / `_PAYMENT_TERM_FIELD_MAP` / `_PAYMENT_FIELD_MAP`**
   (`tools/dispatcher.py:116-152`) — מיפוי סגור משדה Airtable גנרי (קבועי
   `airtable_schema.py`) לפרמטר של הכותב הקנוני; כל פרמטר אופציונלי שנתמך
   בפועל על ידי הכותב הקנוני מיוצג כאן, כך שאין דחייה או אובדן שקט של שדה
   חוקי.
2. **`_CRM_TABLE_ROUTING`** (`tools/dispatcher.py:159-163`) — טבלה →
   (שם כלי קנוני, מיפוי שדות, פרמטרי-חובה) לכל אחת משלוש הטבלאות.
3. **`_map_generic_fields_to_canonical()`** (`tools/dispatcher.py:166-186`)
   — פונקציית עזר משותפת: שדה לא-ממופה **נכשל סגור** (fail closed) עם הודעה
   ששמה את השדה הבעייתי — לעולם לא משמיט שדה בשקט. אין כאן שום תיקוף עסקי
   (לא בודקת calc_type/amount>0/וכו') — זה נשאר אך ורק בבעלות `commercial_crm.py`.
4. **בלוק היירוט עצמו** (`tools/dispatcher.py:569-` בתוך `case "airtable_add":`,
   מיד אחרי בלוק ה-Contacts הקיים): לכל טבלה מיוצגת ב-`_CRM_TABLE_ROUTING`,
   מריץ `enforce(_canonical_tool, identity)` (אכיפת התפקיד המנהלי ה**צר**
   של הכלי הקנוני — לא זה הרחב של `airtable_add`), ואז ממפה ומעביר את
   הבקשה לכותב הקנוני (`commercial_crm.create_deal`/`create_payment_term`/
   `create_payment`) — לעולם לא לכתיבה הגנרית.

   resolver קנוני מנרמל רווחים ואותיות עבור aliases מוכרים; שם מוגן לא מוכר
   או דו-משמעי, כולל `PaymentTerms`, נכשל סגור ואינו מגיע לכותב הגנרי.

### נקודת יירוט: זמן ביצוע (post-approval), לא זמן הצעה

היירוט רץ **בתוך `dispatch_tool()`**, כלומר בזמן ביצוע (אחרי אישור
ActionGateway), לא בזמן סיווג ה-approval policy של ההצעה. מאחר ש-`airtable_add`
כבר `requires_approval=True`/`high_risk=True` עם אותם flags בדיוק כמו הכלים
הקנוניים (רק `roles_allowed` שונה) — אכיפת `enforce()` בזמן ביצוע **מספיקה
כדי למנוע כל כתיבה בפועל** מזהות לא-מורשית: אף רשומה לא נוצרת. **אך** זה לא
מונע מההצעה הגנרית (עם ניסוח כללי) מלהגיע לתור האישורים של מאשר-פוטנציאלי
לפני שהבדיקה בזמן הביצוע דוחה אותה — זהו פער חוויית-משתמש (UX), לא פרצת
אבטחה (שום רשומה לא נכתבת), וסגירתו דורשת נגיעה ב-`core/action_gateway.py`'s
`classify_approval_policy()`/`propose_action()` — מחוץ לתחום המוצהר של תיקון
זה (`tools/dispatcher.py` כבעלים ראשי).

## Cross-Layer Impact Matrix (מקוצר — שינוי חד-שכבתי)

- **Dispatcher (`tools/dispatcher.py`)**: touched directly — 3 בלוקי יירוט
  חדשים + מיפויי שדות + פונקציית עזר משותפת. שום שינוי לחתימת `dispatch_tool()`
  או לזרימת ה-`match` הקיימת מעבר להוספה.
- **`commercial_crm.py`**: not touched — נשאר הבעלים הבלעדי של התיקוף העסקי;
  הדיספצ'ר רק מזמן אותו.
- **`tool_registry.py`**: not touched — `enforce()` מופעל על שם הכלי הקנוני
  הקיים (`crm_create_deal` וכו'), לא נוסף ToolMeta חדש.
- **ActionGateway/execution-proof/approval policy**: not touched — נבדק
  במפורש (תרחיש H) שתשלום מזויף אחרי אישור עדיין נדחה באותו מנגנון proof
  הקיים לכל כלי `requires_approval`.
- **Cross-layer tests**: `python3 tools/audit_dispatcher_bypass.py` →
  `new=0` (ה-`from commercial_crm import ...` החדשים בתוך הדיספצ'ר עצמו
  אינם מסומנים כעקיפה — הדיספצ'ר המזמן את מימושי-הכלים שלו הוא הדפוס
  הסנקציוני, לא עקיפה).

## Post-fix write-path audit (Deals / Payment Terms / Payments)

| כותב/נתיב | סיווג | פרטים |
|---|---|---|
| `commercial_crm.create_deal/create_payment_term/create_payment` | (A) כותב קנוני | הכתובת האמיתית היחידה שנכתבת אליה בפועל |
| `tools/dispatcher.py`'s `case "airtable_add":` יירוט חדש | (B) יירוט קנוני בדיספצ'ר | ממפה ומעביר לכותב הקנוני; fail-closed על שדה לא ממופה |
| `tools/dispatcher.py`'s `case "crm_create_deal/payment_term/payment":` (קיים, ללא שינוי) | (B) יירוט קנוני בדיספצ'ר | כבר קיים לפני תיקון זה |
| `crm.crm_add_deal()` / `crm.crm_update_deal_status()` / `crm.crm_add_payment()` | (C) legacy/dead | לא רשומים ב-`tool_registry.py`/`tools/dispatcher.py`/`tools/schemas.py` — לא ניתן להגיע אליהם מלולאת ה-Agent החיה |
| `scripts/verify_f15_staging.py` | (C) test/legacy | סקריפט staging ידני (מופעל ע"י מפעיל עם גישת shell ישירה, לא ע"י identity/agent) הקורא ל-`crm.crm_add_deal/crm_add_payment` המתות לעיל |
| `crm.crm_mark_payment_paid()` | (C) מחוץ לתחום | **עדכון סטטוס** על רשומה קיימת, לא CREATE; רשום ומאובטח בנפרד (`tool_registry.py:348`, `_SENIOR`, `requires_approval=True`) |
| `crm.crm_overdue_payment_records()`/`_read_overdue_payments()` (נקרא מ-`payment_reminder.py`) | (C) מחוץ לתחום | Job רקע אוטומטי; PATCH סטטוס (`OVERDUE`) על רשומה קיימת, לא CREATE, לא מונע ע"י identity/agent |
| `diagnose_airtable.py` / `data_engines.py` / `daily_digest.py` / `tma_api.py` / `schema_audit.py` | (C) קריאה בלבד | כל ההתייחסויות ל-`Tables.DEALS`/`.PAYMENTS` בקבצים אלה הן read/reporting, לא כתיבה |

**CURRENT SUPPORTED BYPASS: 0** — אין קורא-חי (מלולאת ה-Agent, מ-Telegram/
WhatsApp/TMA) שיכול עדיין לכתוב רשומת Deal/PaymentTerm/Payment חדשה מבלי
לעבור דרך `commercial_crm.py`'s תיקוף קנוני.

## Verification

- `python3 -m py_compile tools/dispatcher.py test_bug_commercial_crm_dispatcher_bypass_closure.py` — עבר
- `python3 test_bug_commercial_crm_dispatcher_bypass_closure.py` — 29/29 (חדש; אומת שנכשל לפני התיקון דרך `git stash`)
- `python3 test_commercial_crm.py` — 97/97
- `python3 test_commercial_crm_dispatcher_wiring.py` — 40/40
- `python3 test_f14_contact_gate.py` — 8/8
- `python3 test_f14_b2_contact_integration.py` — 21/21
- `python3 test_bug_contact_03_invalid_status_feedback.py` — 15/15
- `python3 test_create_task_deterministic_route.py` — עבר (ירוק)
- `python3 test_bug_task_01_execution_proof_fingerprint_parity.py` — 11/11
- `python3 test_action_gateway.py` — 46/46
- `python3 test_stage_b_full_suite.py` — 128/128
- `python3 test_airtable_gateway.py` — 37/37
- `python3 test_approval_concurrency.py` — 22/22
- `python3 test_c53a.py` — 50/50
- `python3 test_inbound_handler.py` — 8/8
- `python3 test_a32_enforcement.py` — 6/6
- `python3 test_identity_smoke.py` — 4/4
- `python3 smoke_tests.py` / `python3 test_integration.py` / `python3 core/router/test_router.py` — ירוקים
- `python3 tools/audit_dispatcher_bypass.py` — `new=0` (exit 0)
- `git diff --check` — נקי

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.**
