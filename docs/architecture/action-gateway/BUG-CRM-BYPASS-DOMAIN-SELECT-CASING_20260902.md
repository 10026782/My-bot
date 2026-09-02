# Deal creation canary #4: canonical domain slug vs. Airtable's live select casing

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— פונקציה משותפת אחת חדשה ב-`core/runtime_schema_provider.py` (שימוש
חוזר מלא בתשתית `RuntimeSchemaProvider` הקיימת) + שימוש בה בשתי נקודות
כתיבה קיימות ב-`commercial_crm.py`. אין כותב חדש, אין חוזה/authority/
routing חדש.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — מוכל כליל בגבול
ה-persistence של Deal/Payment; אינו נוגע בפרסור, בניתוב, או במדיניות
אישור.

## הרקע

מיד לאחר deploy של PR #1177 (BUG-CRM-BYPASS-DOMAIN-TRANSLATION), הבעלים
הריץ קנריית production נוספת: "צור עסקה בשם בדיקת-קנרית 10 בתחום Import".

## מה עבד ומה לא

**מה שכן עבד, בדיוק כמתוכנן:** `parse_deterministic_create_deal()`
תרגם "Import" (אנגלית, אות ראשונה גדולה) לסלאג הקנוני "import" — התיקון
הקודם עומד במבחן.

**מה שנכשל:** הכתיבה בפועל ל-Airtable. הלוג חשף שני דברים בבת אחת:
1. `[SelectValueValidation:SHADOW] invalid value table=עסקאות (Deals)
   field=Domain value='import' allowed=['Real Estate ', 'General',
   'SaaS', 'Recruitment', 'Import']` — שכבת ולידציה **קיימת מראש**
   (`tools/airtable_gateway.py::_provider_invalid_select_values()`) כבר
   זיהתה את אי-ההתאמה, אבל היא בשלב shadow — מלוגגת, לא חוסמת.
2. `HTTP 422: INVALID_MULTIPLE_CHOICE_OPTIONS — Insufficient permissions
   to create new select option "import"` — Airtable עצמו דחה את הכתיבה
   הגולמית.

## ההנחיה הארכיטקטונית של הבעלים (קריטית להבנת התיקון)

הבעלים היה מפורש וחד-משמעי: **אסור** לתקן את זה ב-parser.
`resolve_domain_word()` חייב להמשיך להחזיר "import" (lowercase, הסלאג
הקנוני) — אחרת שכבת ההבנה/שפה חוזרת להיות תלויה בפרטי-תצוגה של
Airtable, בדיוק הבעיה שכל התיקון הקודם (BUG-CRM-BYPASS-DOMAIN-TRANSLATION)
נועד לפתור. התרשים שהבעלים נתן:

```
USER LANGUAGE ("יבוא"/"Import"/"import")
  ↓ resolve_domain_word()           [ללא שינוי — נשאר "import"]
BUSINESS CANONICAL ("import")
  ↓ storage/schema mapping          [השכבה החסרה]
AIRTABLE DEAL DOMAIN ("Import")
```

השכבה החסרה היא בגבול ה-**persistence**, לא בגבול השפה.

## מה נבדק לפני התיקון (לפי בקשת הבעלים: "לבדוק אם כבר קיים mapper")

- `core/lead_service.py::build_lead_fields()` — כותב
  `LeadFields.DOMAIN: payload.domain` **ישירות**, בלי מיפוי. אותה חשיפה
  מבנית בדיוק קיימת שם — **לא תוקן במסגרת זו** (ראה "מה נשאר פתוח" למטה).
- `schema_validator.py` — בודק רק **שמות שדות**, לא ערכים בכלל.
- `core/runtime_schema_provider.py::RuntimeSchemaProvider.get_table_contract()`
  — **כן** קיים, וכבר משמש בדיוק לצורך הזה (השוואת ערכים מול choices
  חיים) — `tools/airtable_gateway.py`'s `_provider_invalid_select_values()`
  כבר קורא לו כדי **לזהות** אי-התאמה (ה-SHADOW log למעלה). אבל שום דבר
  לא השתמש בו כדי **לתקן** — רק לדווח.

## התיקון

פונקציה משותפת חדשה: `core.runtime_schema_provider.resolve_live_select_value(table, field, canonical_value)`.
משתמשת **באותה תשתית קיימת בדיוק** — לא מקור schema שני:

```python
def resolve_live_select_value(table, field, canonical_value):
    contract = get_provider().get_table_contract(table)
    if contract["mode"] != "full":
        return canonical_value          # אין choices לבדוק מולם — ללא שינוי
    info = contract["fields"].get(field)
    if not info or info["type"] not in (...) or not info["choices"]:
        return canonical_value          # לא שדה select, או אין choices מוגדרים
    if canonical_value in info["choices"]:
        return canonical_value          # כבר תואם במדויק
    lowered = canonical_value.strip().casefold()
    for choice in info["choices"]:
        if choice.strip().casefold() == lowered:
            return choice                # ההתאמה ה-live המדויקת (casing נכון)
    return None                          # לא נמצאה התאמה בכלל — דומיין לא-מוכר
```

שלוש תוצאות אפשריות, כל אחת מתועדת ונבדקת:
1. **ללא שינוי** — כשאין מה לבדוק מולו (contract `name_only`, לא select,
   אין choices) — אף פעם לא false rewrite/false rejection מ-seed חסר-מידע.
2. **הערך ה-live המדויק** — כשנמצאה התאמה case-insensitive.
3. **`None`** — דומיין באמת לא-מוכר, גם אחרי בדיקה case-insensitive מלאה.
   הקוראים **חייבים** להתייחס לזה ככשל סגור — לעולם לא להמציא/לכתוב ערך
   לא-מאומת (Airtable ממילא מסרב ליצור אופציה חדשה).

הוחל ב-`commercial_crm.py::create_deal()` ו-`create_payment()`, ממש לפני
בניית ה-`fields` dict, לפני `airtable_create()`. נקודת-מעבר יחידה —
כל קורא (agent ישיר, המסלול הדטרמיניסטי, ההפניה מ-`airtable_add`)
נהנה מהתיקון אוטומטית.

## מה נשאר פתוח

- **Leads' `build_lead_fields()`** — אותה חשיפה מבנית בדיוק
  (`LeadFields.DOMAIN: payload.domain` ישירות). לא אומת אם ה-Domain
  select של טבלת Leads בפועל מוגדר עם casing שונה (יתכן שכן, יתכן
  שהאופציות שם כבר lowercase, יתכן שזה לא select strict). דורש אימות
  נפרד לפני תיקון (נתיב כתיבה שונה, לא נגוע כאן).
- `tools/dispatcher.py`'s `airtable_update` domain-canonicalization gates
  (BUG-CRM-BYPASS-UPDATE, PR #1178 — טרם merged) כותבים גם הם ישירות
  דרך `airtable_update()` בלי לעבור דרך `commercial_crm.py` — יטופלו
  בנפרד באותו ה-PR, לפני שהוא ממוזג, כדי לא לשלוח את אותו הבאג לפרודקשן
  פעמיים.

## Verification

- `test_runtime_schema_provider.py` — 9 טסטים חדשים ל-`resolve_live_select_value()`
  (75/75 סה"כ): התאמה מדויקת, case-insensitive, ערך לא-מוכר → `None`,
  שדה שאינו select לא נבדק, contract `name_only` → ללא שינוי.
- `test_commercial_crm.py` — 10 טסטים חדשים (107/107 סה"כ): `create_deal()`/
  `create_payment()` קוראים לפונקציה עם הסלאג הקנוני; הערך ה-live נכתב
  בפועל; דומיין לא-פתיר נכשל סגור **לפני** שהכתיבה ל-Airtable מתבצעת
  בכלל. כל 97 הטסטים הקיימים ממשיכים לעבור ללא שינוי — סביבת הטסט חסרת
  גישה חיה ל-Airtable, כך שה-contract תמיד `name_only`, וההתנהגות הישנה
  נשמרת בדיוק כשאין מידע לבדוק מולו.
- `python3 -m compileall -q .`, `smoke_tests.py`,
  `tools/audit_turn_coordinator_bypass.py`, `tools/status_sync_validator.py`,
  imports (`app`/`commercial_crm`/`core.runtime_schema_provider`) — עברו.
- סוויטת regression מלאה: `test_bug_commercial_crm_dispatcher_bypass_closure.py`,
  `test_commercial_crm_dispatcher_wiring.py`,
  `test_bug_crm_bypass_create_deal_deterministic_route.py`,
  `core/router/test_router.py` — כולם ירוקים, אפס רגרסיות.
- `git diff --check` — נקי.

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** ממתין לקנרית production חיה חמישית ("צור עסקה
בשם X בתחום Y") שהפעם צריכה להצליח עד הסוף — כולל רשומת Deal אמיתית
ב-Airtable עם Domain בערך ה-live הנכון.
