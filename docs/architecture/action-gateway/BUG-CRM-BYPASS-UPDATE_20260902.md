# BUG-CRM-BYPASS-UPDATE — closing the airtable_update gap for Deals/Payment Terms/Payments

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— תוספת בלוק אחד בתוך `tools/dispatcher.py`'s existing `case "airtable_update":`;
אין כותב קנוני חדש, אין חוזה/authority/routing חדש — שימוש חוזר בתשתית
קיימת (`_CRM_TABLE_ROUTING`, `_DEAL_FIELD_MAP`/וכו', `resolve_domain_word()`).
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — מוכל כליל בשכבת
ה-Dispatcher, מראה בדיוק את הדפוס הקיים כבר ל-`airtable_add`.

## הרקע

אודיט קריאה-בלבד חיצוני על `origin/main` (מיד לאחר סבב תיקוני
BUG-CRM-BYPASS-DOMAIN-TRANSLATION/DEAL-AGENT-FALLTHROUGH) מצא: `airtable_add`
כבר מופנה (מ-01/09/2026) אל הכותבים הקנוניים של Deals/Payment
Terms/Payments — אבל `airtable_update` **מעולם לא** קיבל הפניה מקבילה.
הבעלים אישר את סדר העדיפויות ובחר בפריט הזה (מתוך 9 ממצאים באודיט)
כתיקון הראשון.

## הממצא

`tools/dispatcher.py`'s `case "airtable_update":` כלל הפניה ל-Contacts
(`crm.update_contact()`) — אבל שום דבר עבור Deals/Payment Terms/Payments.
`airtable_update(table="Deals"/"Payments"/"Payment Terms", record_id, fields)`
גולמי נפל ישר ל-`airtable_update()` הגנרי, בלי:
1. Whitelist שדות (כל שם שדה Airtable מתקבל, גם אחד שהכותב הקנוני לא מכיר).
2. תרגום דומיין (אם `fields` כלל עדכון לשדה Domain — אותו באג בדיוק
   כמו BUG-CRM-BYPASS-DOMAIN-TRANSLATION, אבל בנתיב עדכון במקום יצירה).

## למה לא ניתן פשוט לחסום את הטבלאות האלה כליל

בניגוד ל-Contacts (שיש לו כותב-update קנוני כללי, `crm.update_contact()`),
Deals/Payment Terms/Payments **אין** להם כותב-update קנוני כללי מקביל —
רק כותבי-CREATE (`create_deal`/`create_payment_term`/`create_payment`)
ותוסף-מטרה-יחידה (`crm_mark_payment_paid`). `Intent.UPDATE_DEAL_STAGE`
(`core/router/risk_router.py`'s `_CONTRACT_REQUIRED_INTENT_TO_TOOL`)
מסתמך **במפורש ולגיטימית** על אותו `airtable_update` גנרי היום כדי
לעדכן את שלב העסקה מהצ'אט. חסימה גורפת הייתה שוברת פיצ'ר production
אמיתי.

## התיקון

נוסף בלוק "Commercial CRM update-boundary closure" — **שימוש חוזר**
באותה תשתית שכבר קיימת ל-CREATE, לא מפה/מנגנון חדש:

1. `_resolve_protected_crm_table(table)` — כבר קיים, זהה לזה ש-`airtable_add`
   כבר משתמש בו.
2. `enforce(_canonical_tool, identity)` — re-check תפקיד, מראה את הדפוס
   של `airtable_add`. **הבהרה:** `airtable_update`'s `roles_allowed`
   (`tool_registry.py`) הוא כבר `_MANAGEMENT` (לא `_INTERNAL` כמו
   `airtable_add`) — כך שאין כרגע role שנחסם מהכותב הקנוני אך מורשה
   ל-`airtable_update` עצמו. הבדיקה הזו **inert היום** — הגנת-עומק
   לעתיד, לא סגירת פרצה קיימת בפועל.
3. Whitelist שדות: `set(fields) - set(field_map) - _GENERIC_WRITE_IGNORED_KEYS`
   — כל שדה לא-מוכר נכשל סגור, עם שם השדה בהודעה (לא נשמט בשקט).
4. אם `DealFields.DOMAIN`/`PaymentFields.DOMAIN` נמצא ב-`fields` המעודכנים,
   מתורגם דרך `core.lead_service.resolve_domain_word()` — **אותה טבלה
   משותפת בדיוק** שכבר משמשת Leads וכעת גם הפרסר הדטרמיניסטי של Deal
   (BUG-CRM-BYPASS-DOMAIN-TRANSLATION) — לא טבלת-ניחוש שנייה. מילה לא
   מוכרת → נכשל סגור.
5. לאחר כל הבדיקות: `airtable_update(_resolved_table, record_id, fields)`
   — אותה כתיבה גנרית כמו קודם, אבל רק אחרי ולידציה. `Stage` (שדה
   UPDATE_DEAL_STAGE) כבר קיים ב-`_DEAL_FIELD_MAP`, כך שהפיצ'ר הקיים
   ממשיך לעבוד ללא שינוי.

## מה נשאר פתוח (לא בסקופ תיקון זה)

מתוך 9 הממצאים באודיט, הבעלים בחר בפריט הזה בלבד לתיקון ראשון. נותרו
פתוחים: voice legacy Lead writer bypass (`voice_adapter.py`, כשה-flag
כבוי — ברירת המחדל), gateway-level protected-table enforcement
(`tools/airtable_gateway.py` מקבל כל טבלה ללא מדיניות אחידה), עקביות
דומיין (`domain_utils.py`/`core/lead_candidate_handler.py`/`voice_adapter.py`
משתמשים במפות נפרדות שיכולות לסטות), domain validation ב-`commercial_crm.create_deal()`/
`create_payment()` עצמם (כרגע רק הפרסר הדטרמיניסטי מתרגם — קריאת agent
ישירה ל-`crm_create_deal` עדיין יכולה לשלוח דומיין גולמי), LCH ownership
מפורש (fallthrough ל-Agent גם ל-CREATE_LEAD/UPDATE_LEAD), ו-Agent-fallthrough
עבור create_contact/update_contact/create_event/update_event/crm_create_payment(_term).

## Verification

- קובץ regression חדש: `test_bug_crm_bypass_airtable_update.py` — מכסה
  עדכון stage לגיטימי (ממשיך לעבוד), תרגום/דחיית דומיין, whitelist שדות,
  role gate (מתועד למה הוא קורה ב-enforce() העליון), aliases (כולל alias
  דו-משמעי), וטבלאות לא-CRM (לא מושפעות).
- כ-40 קובצי טסט קיימים שמזכירים `airtable_update` (Leads/Tasks/Contacts/
  approval flows) — כולם ירוקים, אפס רגרסיות.
- `python3 -m compileall -q .`, `smoke_tests.py`,
  `tools/audit_turn_coordinator_bypass.py`, `tools/status_sync_validator.py`,
  imports (`app`/`tma_api`/`tools.dispatcher`) — עברו.
- `git diff --check` — נקי.

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.**
