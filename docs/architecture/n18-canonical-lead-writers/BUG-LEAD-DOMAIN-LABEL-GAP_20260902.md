# BUG-LEAD-DOMAIN-LABEL-GAP — completing `_LEAD_DOMAIN_LABELS`, deterministically

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— תיקון נקודתי בשכבת התצוגה (`core/lead_service.py`) בלבד; אין שינוי
ל-parsing, ל-writer, ל-Airtable schema, או למדיניות אישור.
**Cross-Layer Planning Gate assessment:** NONE — שינוי מקומי מוכח, dict
lookup completion + assert, בפונקציה קיימת אחת (`_lead_display_items()`
צורכת את ה-dict, לא שונתה בעצמה).

## הרקע

הבעלים דיווח ("לא מתרגם לגיוס") על תרגום דומיין חסר בזרימת יצירת ליד,
תוך פירוט מפורש: "אל תשתמש ברגקס או משהו שביר, תקן בתוך שכבת ההבנה
בצורה דטרמיניסטית."

## מה נבדק ומה נמצא

1. **הרצה אמפירית של הטקסט המדויק** מהצילום-מסך של הבעלים
   ("ליד חדש/משה בדיקה/0502222222/recruitment/בעל מספר צוותים") דרך
   `core/lead_service.py::parse_structured_command()` על `origin/main`
   הנוכחי, ומעקב אחר הקורא: `core/lead_candidate_handler.py::_handle_structured_command()`.
   **ממצא:** נתיב זה מבצע כתיבה מיידית (`create_lead()` + "✅ ליד נוצר: ...")
   **ללא כרטיס אישור בכלל.** זה סותר את מה שצילום-המסך של "bostaging"
   הראה (כרטיס אישור מלא). המסקנה: סביבת "bostaging" קרוב לוודאי מריצה
   קוד ישן/שונה מ-`origin/main` הנוכחי — **לא** תוקן כאן, כי אין נתיב קוד
   נוכחי שמשחזר את הבעיה המדויקת שהוצגה. מומלץ לבעלים לוודא באופן עצמאי
   איזה commit רץ בפועל ב-staging (Render dashboard מול `origin/main`).
2. **פער אמיתי, נפרד, שכן קיים כרגע:** נתיב הכרטיס-לפני-כתיבה
   (free-text draft flow — `build_lead_draft_message_contract()` →
   `render_lead_draft_message()`/`render_lead_draft_card()` →
   `_lead_display_items()`) צורך את `_LEAD_DOMAIN_LABELS`, ו-dict זה כיסה
   רק 5 מתוך 8 הערכים ב-`CANONICAL_LEAD_DOMAINS`. חסרים: `saas`, `media`,
   `furniture_import`. עבור ליד באחד משלושת התחומים האלה, הכרטיס היה
   מציג את ה-slug הפנימי הגולמי במקום תווית עברית — קוסמטי בלבד (הערך
   שנשמר ב-Airtable תמיד היה נכון), אבל בפועל בעייתי לקריאה למשתמש
   שמאשר את הכרטיס.

## התיקון

הושלמו שלוש התוויות החסרות ב-`_LEAD_DOMAIN_LABELS`
(`core/lead_service.py`), עם ערכים **שאולים**, לא מומצאים, מקונבנציות
קיימות כבר במקומות אחרים בקוד:

- `"furniture_import": "ייבוא רהיטים"` — זהה ל-`cmd_marketing.py`'s
  רשימת ה-DOMAINS.
- `"saas": "SaaS"`, `"media": "מדיה"` — זהים ל-`weekly_summary.py::_DOMAIN_LABELS`
  ול-`cmd_update.py::DOMAINS`.

בנוסף נוסף `assert` ברמת המודול:

```python
_missing_lead_domain_labels = set(CANONICAL_LEAD_DOMAINS) - set(_LEAD_DOMAIN_LABELS)
assert not _missing_lead_domain_labels, (
    f"_LEAD_DOMAIN_LABELS is missing a Hebrew label for: {_missing_lead_domain_labels} "
    f"— a Lead Draft Card would show the raw internal domain slug instead."
)
```

תוספת תחום עתידי ל-`CANONICAL_LEAD_DOMAINS` בלי תווית עברית מתאימה
תגרום כעת לכשל `import` מיידי וברור (fail loud), במקום נפילה שקטה
חזרה ל-slug גולמי בכרטיס משתמש (fail silent) — זהו הדפוס הדטרמיניסטי
שהבעלים ביקש: לא regex, לא ניחוש, dict lookup מלא + בדיקת שלמות
סטטית שרצה בזמן import.

## למה לא תוקן `_DOMAIN_DISPLAY_HE` (הסיבלינג ב-`core/lead_candidate_handler.py`)

`core/lead_candidate_handler.py::_DOMAIN_DISPLAY_HE` הוא dict נפרד
(לשימוש בהודעות הבהרה בעת batch clarification), חסר גם הוא `general`
ו-`furniture_import` — אך זה **לא** חלק מהדיווח הנוכחי (שהתמקד בכרטיס
Draft, לא בהודעות הבהרה) ולא נבדק אמפירית כאן. נשאר פתוח, לא נגוע,
לבירור נפרד אם וכאשר יידווח.

## Verification

- אימות אמפירי ישיר: כל 8 התחומים מתורגמים נכון
  (`saas`→SaaS, `media`→מדיה, `furniture_import`→ייבוא רהיטים, וחמשת
  הקיימים ללא שינוי).
- `python3 test_n18_slice1_lead_preview.py` — 6/6
- `python3 -m pytest -q test_f52_g3_s7_structured_lead_capture.py test_r4_1_optional_note.py test_n18_phase4_telegram_buttons.py` — 12/12
- `python3 test_lead_service_phase1.py` — 109/109 (כולל טסט קיים
  "Structured command: '/' delimiter (staging QA report)" שכבר עובר)
- `python3 test_draft_flow.py` — 16/16
- `python3 test_n18_draft_dispatch_unification.py` — 8/8
- `python3 test_structured_command.py` — 11/11
- `python3 test_bug_lead_02_single_word_name_clarification.py` — 17/17
- `python3 -m compileall -q .` — עבר
- `python3 smoke_tests.py` — עבר
- `python3 -c "import app; import tma_api; import tools.dispatcher; import core.lead_service"` (עם env מזויף כמו ב-CI) — עבר
- `python3 tools/audit_turn_coordinator_bypass.py` — PASS, לא מושפע
- `git diff --check` — נקי

## סטטוס (חלק 1 — completeness)

קוד מומש ונבדק מקומית (STATIC_VERIFIED). תיקון זה נפרד במכוון מ-
`BUG-CRM-BYPASS-FINGERPRINT-PARITY` (PR #1175) — branch שונה, אין נגיעה
ל-Deal/CRM/ActionGateway — לפי בקשת הבעלים המפורשת ("תקן בנפרד").

---

## תיקון המשך — BUG-LEAD-DOMAIN-FURNITURE-NOT-A-DOMAIN (אותו יום, אותו branch)

מיד לאחר התיקון לעיל, הבעלים תיקן הנחת-יסוד: "הענף הנכון הוא ייבוא
(IMPORT) ולא רהיטים — שזו רק דוגמא למוצר, ולא הענף בעצמו." כלומר
`furniture_import` **מעולם לא היה אמור** להיות אחד מ-8 הדומיינים
הקנוניים — התווית שהושלמה לו לעיל (סעיף 1) תיקנה סימפטום (slug גולמי
בכרטיס) על גבי דומיין שגוי מיסודו.

**חקירת scope שנעשתה לפני התיקון** (ראה `BUG_AUDIT_LOG.md`'s
`BUG-LEAD-DOMAIN-FURNITURE-NOT-A-DOMAIN` entry לפירוט המלא): אומת בקוד
ש-`furniture_import` מופיע בשני מושגים שונים ולא-קשורים —
(1) כערך ב-`CANONICAL_LEAD_DOMAINS` (הפגם), ו-(2) כערך "Demand Type"
במערכת השיווק (`cmd_marketing.py`, `marketing_domain_profiles.py`,
`marketing_fact_authority.py`) — מושג נפרד ותקין, לא נגוע. גם `config.py::get_domain()`
ו-`furniture_lead_funnel.py::DOMAIN` ממשיכים להשתמש ב-`"furniture_import"`
כמפתח ניתוב פנימי בלבד (בחירת handler) — לא כערך שנכתב לרשומת Lead,
ולכן **לא שונו**: שינוים היה שובר את הניתוב הלייב לפאנל הרהיטים הייעודי
בלי צורך אמיתי.

**התיקון בפועל:**
1. `core/lead_service.py::CANONICAL_LEAD_DOMAINS` — הוסר `"furniture_import"`
   (נשארו 7 דומיינים קנוניים: `real_estate, import, media, saas, finance,
   recruitment, general`).
2. `core/lead_service.py::_LEAD_DOMAIN_LABELS` — הוסרה התווית התואמת.
3. `core/noninteractive_lead_cutovers.py::create_furniture_inbound_lead()` —
   `domain="furniture_import"` → `domain="import"` (זהו הקורא היחיד
   שכתב בפועל ליד עם דומיין זה).
4. `test_noninteractive_lead_cutovers.py` — עודכן לאמת `domain == "import"`.

**חשוב — לא backfill רטרואקטיבי:** רשומות Lead קיימות ב-Airtable עם
`Domain=furniture_import` (שנוצרו לפני התיקון) לא משתנות על ידי תיקון
זה — זהו תיקון prospective בלבד. Backfill היסטורי, אם רצוי, הוא החלטת
בעלים נפרדת.

### Verification (חלק 2)

חבילת regression מלאה ירוקה, כולל בדיקה מפורשת שמערכת ה-Demand
Type/שיווק לא נפגעה (מושג נפרד לגמרי): `test_noninteractive_lead_cutovers.py`
(4/4), `test_n18_slice1_lead_preview.py` (6/6), `test_lead_service_phase1.py`
(109/109), `test_draft_flow.py` (16/16), `test_n18_draft_dispatch_unification.py`
(8/8), `test_structured_command.py` (11/11),
`test_bug_lead_02_single_word_name_clarification.py` (17/17),
`test_f52_g3_s7_structured_lead_capture.py` + `test_r4_1_optional_note.py`
+ `test_n18_phase4_telegram_buttons.py` + `test_marketing_fact_authority.py`
+ `test_marketing_creative_templates.py` (32/32, pytest).
`python3 -m compileall -q .`, `smoke_tests.py`, imports (כולל
`core.noninteractive_lead_cutovers`, `furniture_lead_funnel`),
`tools/audit_turn_coordinator_bypass.py`, `tools/status_sync_validator.py`,
`git diff --check` — כולם עברו.

## סטטוס (סופי)

קוד מומש ונבדק מקומית (STATIC_VERIFIED) עבור שני התיקונים ביחד.
**לא מוזג, לא deployed, לא verified בפרודקשן.**
