# Deal creation canary #3: domain translation + agent-fallthrough routing gap

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— שני תיקונים נקודתיים בתוך `core/router/router.py` בלבד (parser +
routing condition); אין שינוי ל-`ActionGateway`, ל-`tools/dispatcher.py`,
או למדיניות אישור.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — שני התיקונים
מוכלים כליל בשכבת ה-Router (הבנה + ניתוב); אין חוזה/authority/routing
חדש, רק תיקון לוגיקה קיימת בתוך אותה שכבה.

## הרקע

מיד לאחר deploy של PR #1175 (fingerprint-parity fix) + PR #1176 (lead
domain labels), הבעלים הריץ שתי קנריות production חיות נוספות ליצירת
עסקה, ושתיהן נכשלו — סבב שלישי ורביעי ברצף על אותו intent.

## שני ממצאים נפרדים, שני תיקונים נפרדים

### 1. BUG-CRM-BYPASS-DOMAIN-TRANSLATION

קלט: "צור עסקה בשם בדיקת-קנרית 6 בתחום יבוא".

`parse_deterministic_create_deal()` (`core/router/router.py`) חילץ את
המילה העברית הגולמית ("יבוא") מהרגקס `_STRUCTURED_CREATE_DEAL_RE`, ושלח
אותה כפי שהיא כערך `domain` ל-`crm_create_deal`. `commercial_crm.create_deal()`
כותב `fields[DealFields.DOMAIN] = domain` ללא שום תרגום — Airtable's
single-select דחה את "יבוא" (לא ערך מוכר) עם HTTP 422.

**התיקון:** הפניה לטבלת התרגום המשותפת שכבר קיימת ומשמשת ל-Leads —
`core.ingress_classifier._DOMAIN_HINT_CANONICAL`, דרך
`core.lead_service.resolve_domain_word()`. לא טבלת-ניחוש שנייה, לא regex
חדש — אותו מקור אמת יחיד. מילה לא-מוכרת → `uncertain=True` (CLARIFY),
לעולם לא נכתבת גולמית.

```python
from core.lead_service import resolve_domain_word
domain = resolve_domain_word(domain_raw)
if not domain:
    return DeterministicDealParse(matched=True, uncertain=True)
```

### 2. BUG-CRM-BYPASS-DEAL-AGENT-FALLTHROUGH

קלט: "צור עסקה בשם בדיקת-קנרית 7 domain import" (מילת מפתח אנגלית
"domain" במקום "בתחום").

`_STRUCTURED_CREATE_DEAL_RE` דורש במפורש את המילה העברית "בתחום" —
"domain" האנגלית לא תואמת בכלל, אז `parse_deterministic_create_deal()`
מחזיר `matched=False` (לא `uncertain=True`). ה-`elif` ב-`route_request()`
שמפעיל `Handler.CLARIFY` בדק רק `_create_deal_parse.uncertain` — כך
ש-`matched=False` לא כוסה, וההודעה נפלה בשקט דרך כל שרשרת ה-`elif`
(intent_router עדיין זיהה `Intent.CREATE_DEAL` בביטחון 0.95, אז אף אחד
מהתנאים האחרים לא תפס אותה) עד ל-`Handler.AGENT` — עם גישה מלאה
ובלתי-מוגבלת לכלים.

הסוכן, כשקיבל בחירה חופשית, בחר את `airtable_add` הגנרי במקום
`crm_create_deal` הייעודי, ונכשל עם `❌ owner_id חסר.` — **אותה מחלקת
באג בדיוק כמו BUG-CRM-BYPASS-OWNER-PRESENCE**, שנפתחה מחדש לא דרך
המסלול הדטרמיניסטי (שכבר תוקן), אלא דרך הנתיב היחיד שמעולם לא נותב
דטרמיניסטית מלכתחילה.

**זו בדיוק הפרצה האדריכלית** שה-Turn Coordinator effort (PR #1172, 01/09/2026)
נועד לסגור: "המערכת מנתבת, לא הסוכן." הפרצה לא הייתה בעיצוב המסלול
הדטרמיניסטי עצמו (שעובד נכון כשהוא תואם) — היא הייתה בכך שההחלטה
"מה קורה כשהוא *לא* תואם" לא כיסתה את כל צורות אי-ההתאמה.

**חשוב — זה שונה במכוון מ-CREATE_TASK:** ל-Task יש החלטת עיצוב מפורשת
ומתועדת ("ניסוחים רחבים יותר נשארים במסלול Agent") — Task **לא** קיבל
את אותו תיקון, ובכוונה. ל-Deal יש החלטת ארכיטקטורה שונה לגמרי (הסוכן
לעולם לא בוחר כלי בשבילו) — התיקון הזה סוגר את הפער *רק* עבור Deal.

**התיקון:**
```python
elif intent == Intent.CREATE_DEAL and not _create_deal_parse.certain:
    handler = Handler.CLARIFY
    ...
```
במקום `_create_deal_parse.uncertain` — מכסה גם `uncertain=True` וגם
`matched=False` כאחד. כל בקשת create_deal שאינה "certain" באופן מלא
מקבלת כעת CLARIFY, לעולם לא Handler.AGENT.

**פרט טכני של שער ה-CI:** `tools/audit_turn_coordinator_bypass.py`'s
`_CLARIFY_RE` דורש ש-`handler = Handler.CLARIFY` יופיע מיד אחרי שורת
ה-`elif ...:` (רק whitespace ביניהם). הערת התיעוד המקורית שנוספה בין
ה-`elif` לשורת ה-`handler` שברה את הזיהוי הסטטי (false positive של
השער, לא רגרסיה אמיתית) — הועברה מעל ל-`elif` במקום, ללא שינוי בשער
ה-CI עצמו.

## Verification

- regression tests חדשים משחזרים את שני הטקסטים המדויקים מהקנריות
  (#6, #7) — ב-`test_bug_crm_bypass_create_deal_deterministic_route.py`.
- `core/router/test_router.py`'s "CREATE_DEAL loose/unstructured phrasing"
  עודכן מ-`Handler.AGENT` (הישן, השגוי) ל-`Handler.CLARIFY`, עם תיעוד
  מלא של הסיבה לשינוי — 54/54 עוברים.
- `test_bug_crm_bypass_create_deal_deterministic_route.py` — עודכנו כל
  ההנחות שציפו ל-`domain == "יבוא"` ל-`"import"`; נוספו טסטים לתרגום
  זהות (הקלדת "import" ישירות) ולמילה לא-מוכרת.
- `python3 tools/audit_turn_coordinator_bypass.py` — PASS.
- `python3 -m compileall -q .`, `smoke_tests.py`, imports
  (`app`/`tma_api`/`tools.dispatcher`/`core.router.router`/`core.lead_service`) — עברו.
- `test_commercial_crm.py` (97/97), `test_commercial_crm_dispatcher_wiring.py`
  (40/40), `test_bug_commercial_crm_dispatcher_bypass_closure.py`,
  `test_audit_turn_coordinator_bypass.py`, `test_commercial_crm_owner_ssot.py`,
  `test_phase_4b2_wiring.py` (86/86), `test_bug157_atomic_fingerprint_claim.py`
  (34/34) — כולם ירוקים, אפס רגרסיות.
- `git diff --check` — נקי.

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** ממתין לקנרית production חיה רביעית ("צור עסקה
בשם X בתחום Y") שהפעם צריכה להצליח עד הסוף — כולל רשומת Deal אמיתית
ב-Airtable עם Domain מתורגם נכון ו-Owner מאוכלס.
