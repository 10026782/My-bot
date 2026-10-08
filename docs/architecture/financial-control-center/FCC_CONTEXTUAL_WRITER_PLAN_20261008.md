# FCC — Contextual Writer (תכנון UX + חוזה Intent) — 08/10/2026

**סטטוס: תכנון בלבד. אין קוד, אין שינוי ב־Airtable. ממתין לאישור לפני מימוש.**

## 1. הבעיה
1. הכותב ("עדכון מהיר") חי רק בלשונית "התנהלות חודשית" (`QuickUpdate` בתוך הפאנל `monthly`).
2. כותב חופשי אחד לכל סוגי הנתונים → צריך "מדריך תחביר" (איך מעדכנים יתרה? פעולה הבאה בנכס? נכס שנמכר?).

## 2. העיקרון
```
Writer Engine אחד (BusinessDraft / Diamond — SSOT, ללא שינוי)
        ↓
Composer הקשרי בכל לשונית (אותו state, שלוש הצגות)
        ↓
Intent chips  — קובעים רק {tab, intent}
        ↓
פעולות על הכרטיס — קובעות {intent, entity_id}
        ↓
אותה השלמה מובנית: שואל רק מה שחסר → Review → אישור → ActionGateway
```
כפתור **לא כותב**. הוא מגדיר כוונה והקשר ופותח draft. הכתיבה היחידה: אישור מפורש → `ConfirmedSnapshot` → `tma_fcc_write` → ActionGateway (כמו היום).

## 3. UX
### 3.1 Composer אחד בשלושה לבושים
`useFccWriter()` (hook אחד ב־`FinancialControlCenter`) מחזיק את ה־draft/turn/receipt/error. כל פאנל מציג `ContextualComposer` עם **config** משלו, מעל התוכן:

| לשונית | כותרת | chips |
|---|---|---|
| monthly | עדכון כספי | `+ הכנסה` · `+ הוצאה` · `+ התחייבות` · `+ עדכון יעד` |
| loans | עדכון הלוואה | `עדכון הלוואה` · `הלוואה חדשה` · `עדכון יתרה` · `שינוי החזר` · `סגירת הלוואה` |
| assets | עדכון נכס | `עדכון נכס` · `עדכון שווי` · `עדכון משכנתא` · `פעולה הבאה` · `נכס נמכר` |

* **draft פתוח אחד לכל אדם** (slot משותף TMA/צ'אט — כבר כך היום). לכן ה־state מורם להורה: ה־turn הפתוח מוצג בפאנל הפעיל, ובשאר הלשוניות chips מושבתים עם הערה "יש עדכון פתוח ב־<לשונית>" וקישור לחזרה אליו. אין שני draftים, אין שני controls פעילים (הפאנלים הלא־פעילים נשארים `hidden`).
* מעבר לשונית **לא** מבטל draft; הוא נשמר (כמו היום).
* chip לחוץ → מוצג "פעולה נבחרה: <שם>" + שדה קלט ממוקד עם placeholder מהשדה החסר הראשון ("יתרה חדשה: ____"). כתיבה חופשית נשארת זמינה בכל מקום.
* כתיבה חופשית ללא chip ב־loans/assets: ה־tab נשלח כ־`scope` ומגביל את הסיווג ל־intentים של אותה לשונית (למשל "כאל 48,300" בלשונית הלוואות ⇒ `loan.update_balance`; חיפוש הלוואה בשם בין **הלוואות הבעלים בלבד**; כמה התאמות ⇒ שאלה עם כפתורי בחירה, כמו `needs_goal` היום).

### 3.2 פעולות בתוך כרטיס
* הלוואה: `עדכן` (תפריט: יתרה / החזר חודשי / יתרה לסגירה) · `סגור`  (· `השווה` — כבר קיים כמסלול קריאה, לא כתיבה).
* נכס: `עדכן` (שווי / משכנתא) · `פעולה הבאה` · `נמכר`.
* לחיצה ⇒ `{intent, entity_id}` ⇒ ה־composer של הלשונית נפתח עם הקשר ("הלוואה: כאל") — לא כותבים את שם הרשומה.

### 3.3 מצב־מעבר (state transition)
`loan.close` ו־`asset.mark_sold`: **אין כתיבה ישירה**, אין דילוג על Review; האישור רק בכפתור/מילת אישור מפורשת בתור נפרד מהתור שפתח את ה־draft. ה־Review מציג במפורש מה ישתנה ומה **לא** (למשל: הלוואות מקושרות לנכס שנמכר **לא** נסגרות אוטומטית; מוצגות כהערה).

## 4. חוזה Intent (שרת)
Registry אחד בשרת (`core/financial_control/intents.py` או בתוך `draft.py` הקיים — ראו §7), לא בלקוח:

```
Intent {
  id            "loan.update_balance"
  tab           "monthly" | "loans" | "assets"
  entity        FCC entity contract (קיים או חדש ב-FCC_CONTRACTS)
  target        None | "loan" | "asset" | "goal"      # סוג הרשומה שנבחרת
  prefill       {kind/field_key קבוע מה-intent — לא ניתן לעריכה}
  editable      שדות שהמשתמש ממלא
  transition    bool                                  # סגירה/מכירה → Review חובה, תור אישור נפרד
  writes        פונקציה טהורה: values+ctx → writes[]  # כמו loan_close_writes
}
```
נקודת כניסה אחת (לא endpoint לכל פעולה): `POST /api/fcc/intent/start {intent, entity_id?}` ⇒ `TurnResult`. `/api/fcc/loans/close` הקיים הופך ל־alias דק לאותו handler. **אין כתיבה בנקודה הזו**; ההמשך כולו דרך `/api/fcc/write` הקיים.

כללי חובה (כבר נאכפים, ממשיכים לחול):
* `entity_id` חייב להשתייך לבעלים (policy); "לא נמצא" = "לא שלך" — אותה תשובה.
* שם השדה ב־Airtable נגזר מה־intent בשרת (רשימה סגורה), **לא** מקלט המשתמש.
* `_already_applied` + מפתח idempotency לכל intent; כשל חלקי משאיר CONFIRMED לניסיון חוזר.
* אין `self_confirm` חדש; ביצוע רק דרך `_queue_or_owner_execute`.

### Intentים לפי לשונית
| id | ישות | כותב | הערה |
|---|---|---|---|
| `monthly.income` / `monthly.expense` / `monthly.obligation` / `monthly.goal_progress` | קיימות: event / obligation / goal | קיים | **החלטה פתוחה #1** (§6): "הוצאה" |
| `loan.update_balance` | חדשה | patch `Loans.Outstanding Balance` | שדה אחד, ערך ≥0, מציג "היום: ₪X" |
| `loan.update_payment` | חדשה | patch `Current Monthly Payment` | |
| `loan.update_early_closure` | חדשה | patch `Outstanding Principal for Early Closure` | הציטוט של הבנק |
| `loan.close` | קיימת | Paid Off + אירוע ביעד חוב | transition |
| `loan.create` | חדשה | post ל־`Loans` | **החלטה #2** — שדות חובה/בחירות |
| `asset.update_value` / `asset.update_mortgage` | חדשות | patch `Current Value` / `Mortgage Balance` | |
| `asset.next_step` | חדשה | patch `Next Step` | שדה קיים בסכמה (`schema_cache`) — לבדוק סוג בשדה |
| `asset.mark_sold` | חדשה | patch `Status` | transition; **חסום** עד החלטה #3 |

## 5. מה לא משתנה (אין write paths חדשים)
Engine = `core/business_draft.py` + `FccEntityAdapter`. כתיבה = ActionGateway בלבד. טבלאות מורשות: `Loans` (נוספה ב־#1288), `Assets` (כבר ברשימה). חוזים חדשים ב־`FCC_CONTRACTS` — **לא** מסלול כתיבה חדש וללא לוגיקת השלמה כפולה (`_set_fields/_missing/_render` משותפים).

## 6. החלטות פתוחות (נדרש ממך, חלקן דורשות בדיקת סכמה חיה לקריאה בלבד)
1. **"הוצאה"**: במודל היום אין ספר הוצאות בפועל (התחייבות = commitment, לא שורת הוצאה). `+ הוצאה` = אירוע `direct_cost` על יעד קיים (קיים), או רוצים ספר הוצאות? המלצה: להישאר ב־`direct_cost`, בלי ספר.
2. **`הלוואה חדשה`**: אילו שדות חובה (שם, סכום, יתרה, ריבית, החזר, תאריך), ואילו בחירות ל־`Loan Type`/`Payment Schedule`. נדרש `schema` חי.
3. **`נכס נמכר`**: ערכי `Assets.Status` החיים (איזה ערך = נמכר), ואיפה נשמרים תאריך וסכום המכירה — אין לכך שדות היום. אפשרויות: Notes (טקסט מובנה), או אירוע FCC. **שום שדה חדש בבסיס החי בלי אישורך.**
4. סוג השדה `Assets.Next Step` ו־`Next Step Owner` (טקסט חופשי / בחירה).

## 7. שלבי מימוש מוצעים (כל שלב PR נפרד, ללא כתיבה חיה)
* **P1 — מעטפת**: `useFccWriter` מורם להורה; `ContextualComposer` בכל לשונית; כותרות לפי לשונית; chips ל־monthly (על ישויות קיימות) ו־`סגור` בכרטיס; endpoint `intent/start` + registry; סיווג מוגבל־scope. פותר את הבעיה א׳ (כותב רק בראשונה).
* **P2 — הלוואות**: update_balance / payment / early_closure + `הלוואה חדשה` (אחרי החלטה #2).
* **P3 — נכסים**: update_value / mortgage / next_step.
* **P4 — `נכס נמכר`**: אחרי החלטות #3–#4.

כל שלב: טסטי pytest (בעלות, idempotency, transition מחייב Review, אין כתיבה לפני אישור) + טסטי node לווי ה־UI + בדיקת Chromium (focus/a11y/אין controls כפולים בין לשוניות). הגבלות CI מוכרות: הוספת שורות מעל `import crm` ב־`tools/approval_actions.py` שוברת את ה־audit; ה־Context Librarian דורש רישום מקורות runtime חדשים (נעדיף לשלב בקבצים רשומים); ל־`turn_coordinator_routing` נותרו ~7 טוקנים תקציב.

## 8. Cross-Layer Planning Gate
סיווג: **FULL** (חוזה כתיבה חדש, routing של intent, persistence של draft). בעלות: `core/financial_control/*`; ללא שינוי ב־identity/dispatcher/ActionGateway.
