# BUG-CONTACT-03 — ContactResult collapsed "invalid" status gave no reason

**תאריך:** 01/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— תיקון מוכל לגמרי בתוך `crm.py`'s Contact writer (שכבה 2/4 המשותפת) ובשלושת
הקוראים שלו; אין שינוי ל-ActionGateway, Dispatcher proof rules, approval
policy, או lifecycle semantics.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — אין שינוי חוזה/
authority/routing/runtime-wiring חוצה-שכבות; רק תיקוף ומיפוי-הודעות.

## הרקע — למה זה נבדק

הבעלים ביקש למפות את כל נתיבי הכתיבה העסקיים במערכת (לידים/משימות/עסקאות/
תשלומים/אנשי-קשר) ולבחור כותב-ייחוס ("זהב") שכל השאר יושוו אליו, לפני
שממשיכים לתקן מדיניות שם-ליד (`POLICY-LEAD-NAME-01`). נבחר מודל משולב:
`commercial_crm.py`'s Deal/PaymentTerm/Payment writers (תיקוף שדות + tool
מוקדש ב-registry) + `crm.py`'s Contact writer (הדיספצ'ר עצמו סוגר כל
עקיפה של כתיבה גולמית לטבלת אנשי-קשר). לפני אימוץ המודל כבסיס להשוואה,
בוצע אימות ("stress test") של שני החלקים מול אותם 4 סוגי-באגים שכבר
זוהו במערכת (BUG-LEAD-02/03/04, BUG-TASK-01).

## הבאג (BUG-CONTACT-03, נמצא באימות, לא live-reported)

`commercial_crm.py` יצא נקי לחלוטין. `crm.py`'s Contact writer נמצא **כמעט**
נקי — עם פער אחד מסוג BUG-LEAD-03 (משוב תיקוף לא-פעיל) שלא תועד בעבר:

```python
# crm.py:154-156 (לפני התיקון)
normalized = _normalize_contact_phone(phone)
if not normalized or not name:
    return ContactResult("invalid")
```

שתי סיבות דחייה שונות לחלוטין — טלפון פגום/חסר, ושם חסר — התמזגו לסטטוס
אחד `"invalid"` **בלי שום מחרוזת error**. שלושה קוראים עצמאיים
(`lead_conversion.py`, `tools/dispatcher.py`'s Contacts interception,
`tools/approval_actions.py`'s TMA write path) כל אחד מימש בעצמו מיפוי
סטטוס→הודעה חלקי, שנפל בחזרה להודעה גנרית (או, גרוע יותר, להצגת שם
ה-enum הפנימי הגולמי, המילה `"invalid"` ממש, למשתמש) לכל סטטוס שהמיפוי
המקומי שלו לא הכיר. הסטטוס `"ambiguous"` היה גרוע יותר — `ContactResult.matches`
(רשומות הכפילות בפועל) קיים באובייקט אבל **מעולם לא נכלל** בהודעה או
ב-evidence שנשלח החוצה.

## התיקון

1. **`crm.py::_find_or_create_contact_unlocked()`** — כעת מחזיר `invalid_phone`
   או `missing_name` נפרדים (עם `error` מלא), ונופל ל-`invalid` רק כששני
   השדות חסרים יחד.
2. **`crm.describe_contact_failure()`** (חדש) — מקור יחיד להודעה
   המשתמש-פונה לכל סטטוס לא-הצלחה; כולל `result.error` כשקיים, ומציג את
   מספר ההתאמות בפועל עבור `"ambiguous"`. סטטוס חדש שלא הוגדר עדיין מקבל
   הודעת ברירת-מחדל בטוחה (לא קורס, לא ריק) — כך שקוראים עתידיים לא
   צריכים לזכור לעדכן מיפוי מקומי.
3. **שלושת הקוראים** (`lead_conversion.py`, `tools/dispatcher.py`,
   `tools/approval_actions.py`) עודכנו להשתמש ב-`describe_contact_failure()`
   במקום המיפוי המקומי/הגנרי שלהם; `evidence["matches"]` נוסף בשני
   מקומות הכתיבה (dispatcher/TMA) עבור המקרה `"ambiguous"`.

## Cross-Layer Impact Matrix (מקוצר — שינוי חד-שכבתי)

- **תיקוף (crm.py)**: touched directly — סטטוסים חדשים, שדה `error` מאוכלס
  בכל מקרה. `invariant` שנשמר: `status not in ("created","existing")` עדיין
  True לכל שלושת המקרים — שום קורא קיים שבדק את זה לא נשבר.
- **קוראים** (`lead_conversion.py`/`dispatcher.py`/`approval_actions.py`):
  touched directly — כולם משתמשים כעת בפונקציה משותפת אחת; אין עוד לוגיקת
  מיפוי כפולה.
- **ActionGateway/Dispatcher proof rules/approval policy**: not touched.
- **Cross-layer tests**: `grep -n "ContactResult(\"invalid\")" crm.py` — 0
  תוצאות (הוחלף); `grep -n "contact.status ==\|contact_result.status" *.py tools/*.py`
  — כל האתרים הקיימים בודקים רק `"created"`/`"existing"`/`"outcome_unknown"`,
  אף אחד לא בדק את המחרוזת `"invalid"` במפורש (מאומת לפני התיקון).

## Verification

- `python3 -m py_compile crm.py lead_conversion.py tools/dispatcher.py tools/approval_actions.py test_bug_contact_03_invalid_status_feedback.py` — עבר
- `python3 test_bug_contact_03_invalid_status_feedback.py` — 15/15 (חדש; אומת שנכשל לפני התיקון דרך `git stash`)
- `python3 test_f14_contact_gate.py` — 8/8 (assertion אחד עודכן לסטטוס המדויק החדש)
- `python3 test_f14_b2_contact_integration.py` — 21/21 (assertion אחד עודכן)
- `python3 test_audit3_findings3_6_contracts.py`, `test_audit_dispatcher_bypass_enforcement.py`, `test_bug105_non_canonical_converted_status.py`, `test_core_reasoning.py`, `test_f14_b1_legacy_migration.py` — ללא שינוי, ירוקים
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** אינו תלוי בשום canary נפרד — זהו תיקון UX/משוב
בלבד, לא שינוי לוגיקת יצירה/דדופ.
