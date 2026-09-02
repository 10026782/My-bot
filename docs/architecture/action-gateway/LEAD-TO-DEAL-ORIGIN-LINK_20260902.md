# LEAD-TO-DEAL-ORIGIN-LINK — a deterministic inlet for Lead-linked Deal creation, plus a 7th CI guard

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— פרמטר אופציונלי חדש לפונקציה קיימת (`app._queue_deterministic_create_deal`),
פקודת טלגרם חדשה (`/dealfromlead`, flag-gated `LEAD_TO_DEAL`, כבוי כברירת
מחדל) שקוראת לאותה פונקציה, ופונקציית resolve חדשה ב-`lead_conversion.py`
שאינה מבצעת כתיבה. שער CI שביעי ב-`tools/audit_turn_coordinator_bypass.py`,
באותו דפוס בדיוק כמו 6 השערים הקיימים. אין כותב קנוני חדש, אין
חוזה/authority/routing חדש — ה-writer (`commercial_crm.create_deal`),
ה-schema, וה-dispatcher כבר תמכו ב-`origin_lead_id` נכון.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — מוכל כליל בשכבת
ה-Turn Coordinator/Deterministic Router ב-`app.py`/`lead_conversion.py`
ובשער ה-CI הסטטי שמאמת אותה.

## הרקע

אודיט יזום (לא קנרית production) מצא: ל-`crm_create_deal` יש שני מסלולים —
Agent (ה-LLM בוחר את הכלי, יכול לספק `origin_lead_id` כי זה בשדה ה-schema)
ודטרמיניסטי (`core.router.router.parse_deterministic_create_deal` →
`app._queue_deterministic_create_deal`, agent_calls=0, נבנה ב-BUG-CRM-BYPASS
follow-up כדי שה-Agent לעולם לא יבחר בין `crm_create_deal` ל-`airtable_add`).
המסלול הדטרמיניסטי מעולם לא קיבל דרך לספק `origin_lead_id` — כל עסקה
מקושרת-ליד יכלה להיווצר רק דרך ה-Agent, בדיוק המסלול שה-Turn Coordinator
כולו קיים כדי לעקוף. זה חור ב-inlet, לא writer שבור: `commercial_crm.
create_deal()` כבר קיבל וכתב את השדה נכון (`DealFields.ORIGIN_LEAD`), ה-schema
כבר הכריז עליו, וה-dispatcher כבר העביר אותו — רק שום דבר לא סיפק אותו
דטרמיניסטית.

## החלטת ארכיטקטורה שנבדקה ונדחתה: TMA endpoint

ההצעה הראשונית (endpoint TMA חדש שדומה ל-`create_lead_task`) נבדקה בפועל
ונמצאה שגויה: `tma_api.py`'s `_queue_or_owner_execute`/`_queue_tma_write_
approval` הם נתיב כתיבה גולמי בלבד (`{"op":"post","table":...,"fields":...}`
ישירות ל-Airtable) — אין להם היום שום מנגנון לקריאת כלי קנוני בשם
(`crm_create_deal`). `_queue_deterministic_create_deal()` עצמה בנויה סביב
`chat_id`/`channel` טלגרם ושליחת הודעה אינטראקטיבית ל-owner — קריאה לה
מ-Flask route Ø ללא בניית plumbing חדש לגמרי מ-TMA לכלים קנוניים, מה
שהיה הופך את הסקופ מ-SINGLE-LAYER ל-FULL. הוחלף בתקדים קיים ומתאים: `/convert`
(`lead_conversion.py`) — פקודת owner מפורשת שמחפשת ליד לפי שם/טלפון, כבר
עם `chat_id`/`channel` טלגרם אמיתיים, בדיוק מה ש-`_queue_deterministic_
create_deal()`'s ה-signature מצפה לו.

## התיקון

### 1. `_queue_deterministic_create_deal()` — פרמטר אופציונלי חדש

`origin_lead_id: str = ""` — נכנס ל-payload רק כשסופק:
```python
deal_inputs = {"name": name, "domain": domain, "owner_id": owner_self_reference}
if origin_lead_id:
    deal_inputs["origin_lead_id"] = origin_lead_id
```
ללא שינוי כלל לצורת ה-payload של המסלול הטקסטואלי הקיים ("צור עסקה בשם X
בתחום Y"), שאף פעם לא מספק את זה.

### 2. `/dealfromlead` + `lead_conversion.resolve_lead_for_deal()`

פקודת טלגרם חדשה, owner-only, flag-gated (`LEAD_TO_DEAL`, כבוי כברירת
מחדל). `resolve_lead_for_deal(query)` הוא resolve-only — אינו מבצע שום
כתיבה: מחפש ליד יחיד (משתמש ב-helper משותף `_resolve_single_lead_by_query()`
שחולץ מ-`convert_lead_to_contact()`'s לוגיקת החיפוש הקיימת, לא מעתיק אותה
בשנית), מחלץ `name`, ומחלץ `domain` דרך `core.lead_service.resolve_domain_
word()` — **אותה** טבלת מילים משותפת שהמסלול הטקסטואלי ("צור עסקה בשם X
בתחום Y") כבר עובר דרכה (`core/router/router.py`'s
`parse_deterministic_create_deal`), לא טבלת ניחוש שנייה. domain לא-מוכר/ריק
נכשל ל-CLARIFY (מחזיר שגיאה), בדיוק כמו `DeterministicDealParse`'s עצמה
עושה לטקסט חופשי — לא ניחוש, לא כתיבת ערך שגוי. `app.py`'s `cmd_deal_from_
lead()` קורא את התוצאה ומעביר ל-`_queue_deterministic_create_deal(...,
origin_lead_id=lead_id)` — **אותו writer יחיד** שהמסלול הטקסטואלי כבר
משתמש בו, לא endpoint/payload מקביל.

### 3. שער CI שביעי — `CRM_CREATE_DEAL_SINGLE_PAYLOAD_BUILDER`

נוסף ל-`tools/audit_turn_coordinator_bypass.py`: מוודא ש-**כל** Call node
מהצורה `_queue_approval_detailed("crm_create_deal", ...)` ב-`app.py` חי
בגוף הפונקציה של `_queue_deterministic_create_deal()` בלבד. **מבוסס AST,
לא regex/ספירת מחרוזות** — הגרסה הראשונה של השער הזה ניסתה לספור מופעי
מחרוזת גולמיים, ותפסה false positive אמיתי תוך כדי הבנייה: ה-docstring של
`_queue_deterministic_create_deal()` עצמה, שמסביר את הכלל, הזכיר את צורת
הקריאה כטקסט והשער ספר אותה כ"קריאה שנייה". הבעלים הצביע בזמן אמת שספירת
call-sites היא guard שביר שלא בודק את ה-invariant האמיתי (המסלול
הדטרמיניסטי לא אמור לקרוא ל-writer ישירות בכלל — הוא מציע ActionContract,
וה-Dispatcher מגיע ל-writer בביצוע) — התיקון: `ast.parse()` + ביקור
`FunctionDef`/`Call` נודות, מזהה בדיוק את שם הפונקציה המכילה (לא רק אם
המחרוזת מופיעה איפשהו בקובץ). **נבדק בפועל** (לא רק תיאורטית): נוצרה
פונקציה שנייה בעותק זמני של `app.py` שמציעה `crm_create_deal` ישירות
(בדיוק צורת הרגרסיה) — אומת שהשער נכשל ומצביע בשם על הפונקציה הפוגעת
המדויקת (`cmd_deal_from_lead_BROKEN`), ולא רק על מספר מופעים; אומת גם
שדוקסטרינג/הערה שמזכירים את צורת הקריאה כטקסט **לא** נתפסים בטעות; ושוחזר
ואומת שהשער עובר שוב על הקוד האמיתי.

## Verification

`test_lead_to_deal_origin_link.py` (קובץ חדש, 11 טסטים pytest-native —
`assert` ולא scaffold מבוסס-הדפסה: הקובץ תואם את regex הזיהוי האוטומטי
של CI, `^def test_`, ומנותב ל-pytest — helper שרק מדפיס בכישלון היה מדווח
"עבר" בטעות, בדיוק מחלקת הבאג המתועדת ב-
`docs/audit/CI_TEST_HARNESS_FALSE_PASS_20260830.md`): `_queue_deterministic_
create_deal()` כולל/משמיט `origin_lead_id` כנדרש; `resolve_lead_for_deal()`
על כל מקרי הקצה; הוכחה ששתי הפונקציות חולקות את אותו helper חיפוש.

`test_audit_turn_coordinator_bypass.py` — 4 טסטים חדשים לשער 7 (33/33 עם
הקיימים), כולל הטסט הייעודי לתפיסת ה-false-positive.

`python3 -m compileall -q .`, `smoke_tests.py`,
`tools/audit_turn_coordinator_bypass.py`, `core/router/test_router.py`
(54/54), `test_bug_crm_deal_duplicate_approval_reply.py` (8/8),
`test_bug_deterministic_queue_duplicate_reply_suppression.py` (9/9),
`test_bug_crm_bypass_create_deal_deterministic_route.py` — כולם ירוקים,
אפס רגרסיות.

## סטטוס

Fixed (STATIC_VERIFIED) — ממתין ל-merge + deploy + הפעלת `LEAD_TO_DEAL`
+ קנרית production חיה (`/dealfromlead <שם/טלפון קיים>`). ראה
`BUG_AUDIT_LOG.md`'s `LEAD-TO-DEAL-ORIGIN-LINK` entry למעקב מלא.
