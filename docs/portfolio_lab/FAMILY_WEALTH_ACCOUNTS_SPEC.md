# SPEC — מודל חשבונות להון משפחתי

תאריך: 14/10/2026 · גרסה 2.1 · סטטוס: **הכיוון והשאלות הפתוחות אושרו על ידי הבעלים (סעיף 8); יצירת `Financial Accounts` והרחבת סכמת Airtable עדיין ממתינות לאישור נפרד.**
אין עדיין אישור להוספת טבלאות, שדות או קוד יישומי. אין שינוי Airtable. מסמך זה הוא הרחבה של שורת `PORTFOLIO_LAB` ב-`BOSS_UNIFIED_MASTER_PLAN.md`, לא מסמך אב נוסף.
Planning Gate: **FULL** (persistence + authority + schema + multi-layer).

## 0. החלטות בעלים שמעצבות את המודל

1. **כמה בעלי חשבונות במשפחה.** בעלות כלכלית על חשבון נפרדת מהרשאות מערכת (סעיף 4).
2. **סוגי חשבון:** פנסיה, קרן השתלמות, קופת גמל להשקעה, ביטוח מנהלים, חשבון מסחר, חשבון נזיל.
3. **מס:** מאפיינים תיאוריים בלבד. אין חישוב מס ואין המלצה על סדר משיכות.
4. **הקצאת שווי חשבון בין כמה מטרות:** נדחית, אך הארכיטקטורה לא חוסמת אותה (סעיף 5.3).
5. **יתרות:** צילומים מתוארכים; אין דריסת היסטוריה.
6. **העברות בין חשבונות:** אסור שיספרו פעמיים (סעיף 5.2).
7. **הפרדה סמנטית:** הפקדה · משיכה · עמלה · העברה · צילום יתרה (סעיף 5.1).
8. **תאימות:** כל הצרכנים הקיימים של `Financial Progress Events` נשארים תקינים (סעיף 6).

## 1. אימות מול Airtable החי (קריאה בלבד, 14/10/2026)

בסיס `app4bcgoX7t0HUVnm`, דרך Airtable MCP (`list_tables_for_base`, `get_table_schema`). לא נכתב דבר.

| בדיקה | תוצאה |
| --- | --- |
| `Financial Goals`, `Financial Progress Events`, `Assets`, `Profile` | **זהות לחלוטין** ל-`schema_cache.json` (21 / 13 / 21 / 17 שדות) |
| ערכי `Kind` חיים ב-`Financial Progress Events` | 6: `one_time`, `monthly_recurring`, `target_change`, `note`, `direct_cost`, `household_expense` — תואם `calc.EVENT_KINDS` |
| `Financial Progress Events.Goal` | קישור **מרובה** ל-`Financial Goals`; `Financial Owner` קישור ל-`Profile` |
| `Loans` | שדה `Direction` חי, חסר ב-cache (הקוד כבר משתמש בו) |
| `Contacts` | 41 שדות חיים מול 36 ב-cache; 5 שדות Allocation/Worker חסרים ב-cache |
| טבלאות חיות שאינן ב-cache | `Allocation Rules`, `Allocation Snapshots`, `Deal Economics`, `Monthly Calculation Batches`, `Organizations`, `Worker Assignments`, `Worker Monthly Results` — עסקיות, לא קשורות ל-FCC |
| טבלת חשבונות פיננסיים | **לא קיימת** |

**סטיות cache** (לא קשורות לשינוי הזה) יטופלו בשלב ה-reconcile לפני מימוש. **שם תפוס:** `Allocation Rules` / `Allocation Snapshots` קיימות כבר (חלוקות עמלות עסקיות), ולכן הטבלה העתידית להקצאת שווי בין מטרות תיקרא `Account Goal Shares`, לא "Allocations".

## 2. עיקרון ההפרדה

| ממד | איפה |
| --- | --- |
| **חשבון / מוצר** (איפה הכסף מוחזק) | `Financial Accounts` — חדש |
| **מטרה** (בשביל מה) | `Financial Goals` — קיים, ללא שינוי |
| **תנועות ויתרות** (הפקדה, משיכה, עמלה, העברה, צילום) | `Financial Progress Events` — קיים, מורחב |
| **נזילות ומיסוי** | שדות תיאוריים בחשבון |
| **בעלות כלכלית** | קישור בחשבון (סעיף 4) |
| **הרשאה** | `Financial Owner` → `Profile` (קיים) |

אין שדה יתרה בחשבון ואין שדה יתרה במטרה. יתרה היא עובדה בנקודת זמן ולכן נגזרת מצילומים.

## 3. מבנה השדות הסופי המוצע

### 3.1 טבלה חדשה: `Financial Accounts`

| שדה | סוג | חובה | הערה |
| --- | --- | --- | --- |
| `Name` | singleLineText | כן | שם החשבון |
| `Account Type` | singleSelect | כן | `pension` · `study_fund` · `provident_investment` (קופת גמל להשקעה) · `managers_insurance` (ביטוח מנהלים) · `brokerage` (חשבון מסחר) · `liquid` (חשבון נזיל) · `other` (**אושר, כולל `other`**). קרן חירום, לימודים, חתונות ופרישה מוקדמת הן **מטרות** המוחזקות בחשבונות, לא סוגי חשבון — סוג המוצר הפיננסי נפרד תמיד ממטרת החיסכון |
| `Institution` | singleLineText | לא | בית השקעות / חברה מנהלת / בנק |
| `Financial Owner` | link → `Profile` | כן | **הרשאה בלבד** (owner-of-record, כמו שאר טבלאות ה-FCC) |
| `Holder Names` | singleLineText | לא | **בעלות כלכלית בשלב הראשון (הוחלט):** שמות בעלי החשבון כטקסט; נקרא ב-OWNER_SCOPED בלבד |
| `Holders` | link → `Contacts` | — | **לא ייווצר בשלב הראשון.** שלב מאוחר, מותנה בהחלטת פרטיות נפרדת (סעיף 4) |
| `Status` | singleSelect | כן | `active` · `closed` |
| `Liquidity` | singleSelect | כן | `immediate` · `locked_until_date` · `age_based` · `unknown` |
| `Liquid From` | date | לא | כשהנזילות קבועה בזמן |
| `Tax Treatment` | singleSelect | כן | `taxable` · `tax_advantaged` · `pension_rules` · `unknown` — **תיאור בלבד** |
| `Tax Notes` | multilineText | לא | הערות חופשיות, ללא חישוב |
| `Management Fee %` | number | לא | דמי ניהול שנתיים כפי שדווחו |
| `Opened At` · `Closed At` | date | לא | |
| `Notes` | multilineText | לא | **לא לשמור מספרי חשבון או פוליסה מלאים** |
| `Financial Progress Events` | link (הפוך, אוטומטי) | — | |

### 3.2 הרחבה של `Financial Progress Events` (בלי טבלת תנועות נוספת)

| שדה | סוג | הערה |
| --- | --- | --- |
| `Account` | link → `Financial Accounts` | אופציונלי; אירועי מטרות קיימים אינם משתנים |
| `Counter Account` | link → `Financial Accounts` | רק ב-`transfer`: חשבון היעד |
| `Verification` | singleSelect | `self_reported` (ברירת מחדל) · `statement` · `bank_or_fund_confirmed` |
| `Kind` — ערכים חדשים | singleSelect | `deposit` · `withdrawal` · `fee` · `transfer` · `balance_snapshot` |

סכומים תמיד חיוביים; הכיוון נקבע לפי ה-`Kind`. הערכים הקיימים אינם משתנים.

**חלופה שנדחתה:** טבלת `Account Movements` נפרדת — משכפלת idempotency, supersede, owner-scope ותשתית כתיבה קיימים.

### 3.3 מדיניות גישה (קוד, בשלב המימוש)

- `Financial Accounts` נרשמת ב-`core/data_access_policy.py` כ-`OWNER_SCOPED` עם `owner_field = Financial Owner`.
- `linked_owner_checks` של `Financial Progress Events` מורחב ב-`Account` וב-`Counter Account`: אסור לקשר לחשבון של אדם אחר.
- הוספה ל-`_TMA_WRITE_ALLOWED_TABLES` רק אם נכתב דרך זרימת ה-TMA; הכתיבה נשארת טיוטה ← "אשר", ללא כתיבה אוטומטית.

### 3.4 תשומות תחזית לכל חשבון (שלב 9, אושר ע"י הבעלים 18/10/2026)

שמונה שדות בטבלת `Financial Accounts`, כולם ערכי בעלים — ריק = לא ידוע ומוצג כ"חסר לדיוק", לעולם לא מומצא. הקוד קורא אותם ב-`accounts_overview` ואינו כותב אותם.

| שדה | סוג | משמעות |
|---|---|---|
| `Planned Monthly Deposit` | number | הפקדה חודשית מתוכננת (₪); תכנון, לא הוראת קבע מאומתת. הקלדה במסך גוברת |
| `Deposit Fee %` | number | דמי ניהול מההפקדה (%), מנוכים מכל הפקדה לפני המנוע; "הושקע" נשאר ברוטו |
| `Investment Track` | singleSelect | `equities` / `bonds` / `mixed` / `index_tracking` / `money_market` / `unknown` — תיעוד |
| `Linkage` | singleSelect | `none` / `cpi` / `sp500` / `other_index` / `fx` / `unknown` (הצמדה) |
| `Linkage Notes` | text | איזה מדד/מטבע |
| `Expected Return %` | number | תשואה שנתית צפויה לחשבון; **ריאלית** כש-`Linkage=cpi` (מומרת לנומינלית בהנחת האינפלציה), נומינלית אחרת |
| `Insurance Cost Monthly` | number | עלות ביטוח חודשית (נכות+שאירים), נומינלית וקבועה |
| `Insurance Cost As Of` | date | תאריך נכונות העלות |

כללים: ערך חשבון תקף גובר על ברירת מחדל והמקור מסומן; ערך פגום/מחוץ לטווח נחשב חסר; הצמדה שאינה `cpi` אינה מדמה את המדד (תיעוד בלבד). המנוע קיבל `Scenario.monthly_fixed_cost` (ברירת מחדל 0 = ללא שינוי).

**נוצרו בפועל ב-Airtable (18/10/2026, באישור הבעלים, דרך Airtable MCP `create_field`; כולם ריקים בכל 5 הרשומות, ללא backfill):**

| שדה | Field ID | טיפוס |
|---|---|---|
| `Planned Monthly Deposit` | `fldLer9VCD0VTAvtD` | number (2) |
| `Deposit Fee %` | `fldlQR01XNk364cvY` | number (2) |
| `Investment Track` | `fldvhl4k3PlbVxzH1` | singleSelect (6 אפשרויות כבטבלה) |
| `Linkage` | `fldDjYCkbtInKuSFr` | singleSelect (6 אפשרויות כבטבלה) |
| `Linkage Notes` | `fldeu0VKg6GJpg5ng` | singleLineText |
| `Expected Return %` | `fldvFlFuqDdGDsB5V` | number (2) |
| `Insurance Cost Monthly` | `fldCA8JgczUFBfMw0` | number (2) |
| `Insurance Cost As Of` | `fldqoYL8IwnjPTrEY` | date (ISO) |

לפני היצירה אומת מול הסכמה החיה (`get_table_schema` + `list_tables_for_base`) ש-17 השדות הקיימים אינם מכילים אף אחד מהשמות; אחרי היצירה אומת מחדש. אף שדה קיים לא שונה.

### 3.5 נזילות וכיסוי מטרות (A2, אושר ע"י הבעלים 18/10/2026, ללא שדות חדשים)

שלושה מצבים לכל חשבון בכל חודש, מהשדות הקיימים בלבד (`Liquidity`, `Liquid From`, `Account Type`), ותמיד `accessible + conditional + locked = שווי מאוחד`:

| מצב | מתי |
|---|---|
| `accessible` (נזילות מאומתת) | `Liquidity=immediate` ואינו מוצר פרישה (`pension`, `managers_insurance`) |
| `conditional` | `locked_until_date`/`age_based` **אחרי** `Liquid From` (סוף החודש ≥ התאריך; זכאות למשיכה לא מוסקת מגיל/תאריך); `unknown`/ריק (לא אומת); מוצר פרישה גם אם סומן `immediate` |
| `locked` | `locked_until_date`/`age_based` לפני `Liquid From`, או בלי תאריך |

כיסוי מטרה (`long_term`, `emergency_fund`, `investment`, `savings`; פעילה בלבד): מטרה עם `Target Amount` ו-`End Date` תקפים → `covered` / `short` (+פער) / `not_comparable` (סיבה: חסר סכום, חסר תאריך, תאריך עבר, מעבר לאופק, אין חשבון נגיש מאומת). ההשוואה רק מול `accessible`, בערך נומינלי בסוף **החודש האחרון שהושלם עד תאריך היעד** (שורות חודשיות מהמנוע, לא סוף השנה; ערך פתיחה כשהתאריך בחודש הנוכחי לפני סופו) — הפקדה או צמיחה שאחרי תאריך היעד, גם באותו חודש, אינן נספרות; שמרני גם להפקדות שהוקדמו לתחילת החודש; קרן חירום — רק חשבונות `immediate` מאומתים. זה **כיסוי פוטנציאלי, לא הקצאה**: אותו כסף עשוי להופיע בכיסוי של כמה מטרות עד B2. ללא מס/משיכות (A3), ללא המלצה.

מגבלה: בלי שדה אימות נזילות, `accessible` = `immediate` בלבד; קרנות השתלמות ופנסיות יופיעו `conditional` גם אחרי תאריך השחרור.


### 3.6 הקצאת חשבון למטרה — `Goal Allocations` (B2, אושר ע"י הבעלים 18/10/2026, שלב 2: סכמה ומדיניות בלבד)

טבלה חדשה `Goal Allocations` (`tblZgqHiBbSeyRTCA`), ריקה, `OWNER_SCOPED` לפי `Financial Owner`; שדות: `Name`, `Goal`, `Account` (קישור יחיד נאכף במדיניות, ושניהם חייבים להיות של המשתמש), `Financial Owner`, `Mode` (`percent` / `fixed_amount`), `Percent`, `Amount`, `Status` (`active` / `ended`), `Effective From`, `Notes`, `Created At`. הזנה ידנית; הקוד אינו כותב לטבלה. כללי החישוב (אחוז מכלל שווי החשבון, חריגה מסומנת ולא מקוצצת, מטרה בלי הקצאה נשארת עם כיסוי A2) ב-[B2_GOAL_ALLOCATIONS_SCHEMA_REQUEST.md](B2_GOAL_ALLOCATIONS_SCHEMA_REQUEST.md); מודל הקריאה וה-UI — שלבים 3-4, באישור נפרד.

**מודל הקריאה (B2 שלב 3, אושר 18/10/2026; קריאה בלבד, ללא כתיבה):** `service.allocations_for_forecast` קורא רק את שורות הבעלים עצמו (מדיניות הטבלה), ו-`accounts_forecast` מקבל אותן כקלט ומחזיר `allocations` ו-`goals[].basis`. כללים: `percent` = אחוז מכלל שווי החשבון בצילום האחרון, `fixed_amount` = סכום נומינלי; שורה שהמטרה או החשבון שלה אינם של הבעלים נדחית (`unknown_link`) בלי חשיפת שם; רק `Status=active` נספר; הקצאה ל-`Effective From` עתידי לא נספרת היום ונכנסת מאותו חודש בתחזית. לכל חשבון: מוקצה / פנוי / `over_allocated` + `over_by` (מוצג, לא נחתך לאפס, ואינו נכנס לסכומי "הוקצה/פנוי" — המטרות שלו `not_comparable: over_allocated`). לכל מטרה: מה שהוקצה לה מפוצל ל-`accessible` / `conditional` / `locked` לפי נזילות החשבון (A2) — **הוקצה ≠ נגיש**: הקצאה לפנסיה נשארת `conditional` והמטרה `allocated_not_accessible`, לא "חסר" ולא "מכוסה". בתחזית: `percent` גדל עם החשבון, `fixed_amount` קבוע ומוגבל יחסית לשווי החשבון בכל חודש (`allocation_capped`). מטרה בלי הקצאה נשארת `basis=potential` (כיסוי A2) עם `allocated_elsewhere_accessible` לשקיפות. אין שינוי ביתרות, בהפקדות/משיכות, ב-`Financial Progress Events` או ב-ActionGateway.
## 4. בעלות כלכלית מול הרשאות מערכת

**ממצא מ-Contacts:**

- `Contacts` היא טבלת CRM עסקית: `Role Category` = `lead` · `broker` · `expert` · `supplier` · `operator` · `partner` · `investor` · `client` · `other`. אין קטגוריית משפחה.
- שדה `Owner` ב-`Contacts` מקשר ל-`Profile` ומתועד בקוד כ"מטא-דאטה עסקית, **לא גבול הרשאה**".
- ל-`Contacts` **אין מדיניות `data_access_policy`**. כל קורא יכול לראות את הרשומות, ולכן שמות בני משפחה שם חשופים לתפקידים עסקיים.
- `Profile` הוא גבול ההרשאה: משתמשי מערכת עם `Role`. בן משפחה אינו בהכרח משתמש מערכת.

**ההפרדה המוצעת:**

| מושג | שדה | משמעות |
| --- | --- | --- |
| הרשאה | `Financial Owner` → `Profile` | מי רשאי לראות ולכתוב את הרשומה. לעולם לא נגזר מ-`Holders` |
| בעלות כלכלית | `Holder Names` (טקסט; קישור ל-`Contacts` בעתיד בלבד) | של מי הכסף. מידע בלבד; אינו מעניק גישה |

**שימוש חוזר ב-Contacts דורש החלטה, כי הוא נוגע בטבלה עסקית חיה:**

- הוספת קטגוריה (למשל `family`) ל-`Role Category` — שדה שנצרך ב-`crm.py`, `commercial_crm.py`, `commercial_completion*.py`.
- מדיניות פרטיות לרשומות משפחה (`RECORD_MARKER`).
- בדיקה שזרימות הלידים, ה-dedup והייבוא לא נוגעות ברשומות האלה.

**הוחלט (14/10/2026):** בשלב הראשון `Holder Names` (טקסט) — תומך בכמה בעלים לחשבון, בלי לגעת ב-CRM. אין קישור ל-`Contacts`. מעבר ל-`Holders` יתבצע רק אחרי החלטת פרטיות נפרדת, והוא תוספת שדה, לא שינוי מבנה.

**בידוד ממשתמשים עסקיים (דרישה מחייבת):**

- `Holder Names`, `Notes`, `Tax Notes` ו-`Institution` נקראים רק דרך מסלול ה-FCC עם `OWNER_SCOPED`; אף תפקיד עסקי (Manager, Sales, Finance וכו') אינו רואה אותם.
- הטבלה לא מוצגת בשום כלי כללי (`airtable_get` ואחיו) ולא נכללת בהקשר שנבנה לסוכן.
- **אין לשמור מספרי חשבון או פוליסה מלאים.** בשלב המימוש ייאכף בקוד: ערך בשדות הטקסט שמכיל רצף של 8 ספרות ומעלה נדחה בטיוטה (לא רק הנחיה).

## 5. סמנטיקת תנועות ויתרות

### 5.1 הפרדה בין סוגי האירועים

| Kind | משמעות | משפיע על יתרת חשבון | נספר כהפקדה / תרומה למטרה |
| --- | --- | --- | --- |
| `deposit` | כסף חדש נכנס לחשבון מבחוץ | + | כן |
| `withdrawal` | כסף יוצא מהחשבון החוצה | − | לא (משיכה) |
| `fee` | עמלה / דמי ניהול שנגבו | − | לא |
| `transfer` | כסף עובר בין שני חשבונות של המשפחה | − ב-`Account`, + ב-`Counter Account` | **לא** |
| `balance_snapshot` | שווי מדווח בתאריך | קובע את היתרה בתאריך | לא |

`one_time` על יעד `long_term` נשאר כפי שהוא ("הפקדה לא משויכת לחשבון", דיווח עצמי). אין שכתוב של אירועים קיימים.

### 5.2 מניעת ספירה כפולה

1. **העברה היא אירוע אחד** עם `Account` (מקור) ו-`Counter Account` (יעד), לא שתי רשומות. אי אפשר לשכוח צד אחד או לספור אותה פעמיים.
2. **העברה אינה הפקדה ואינה משיכה**: אינה נכנסת לסיכומי הפקדות, לממוצע חודשי, לרצף או לפער מול התכנון.
3. **שווי מאוחד = סכום הצילום האחרון לכל חשבון**, לא סכום תנועות. תנועה לבדה לעולם לא משנה את השווי המאוחד.
4. **הפקדה נרשמת פעם אחת**: או `one_time` (ישן, בלי חשבון) או `deposit` (חדש, עם חשבון). בעת המעבר הזרימה של "הפקד" כותבת `deposit` בלבד, וה-idempotency key הקיים נשמר.
5. כשהצילום האחרון חדש מתנועות, התנועות שלפניו אינן מתווספות ליתרה (הצילום קובע).

### 5.3 צילומי יתרה, בלי דריסת היסטוריה

- `balance_snapshot` הוא אירוע append-only. תיקון נעשה בסימון `Superseded By` (מנגנון קיים), לא בעריכה.
- היתרה הנוכחית = הצילום התקף האחרון לפי `Occurred At`. היסטוריית השווי = כל הצילומים התקפים.
- `Verification` מתעד אם הצילום דווח ידנית, נלקח מדו"ח או אומת מול הגוף המנהל. ברירת המחדל `self_reported`.
- **יתרה משוערת** (לפי הפקדות מאז הצילום האחרון) תוצג רק כהערכה מסומנת, לא כעובדה, ולא תישמר.

### 5.4 מטרה ↔ חשבון (רבים-לרבים) ולא לחסום הקצאה עתידית

אירוע נושא `Goal` ו-`Account` גם יחד, ולכן הפקדה לשני חשבונות לאותה מטרה, או מחשבון אחד לשתי מטרות (שני אירועים), נרשמת בלי טבלת קשר. **שווי** חשבון משותף בין מטרות דורש אחוזי הקצאה. נדחה: טבלת `Account Goal Shares` תתווסף בלי שינוי ב-`Financial Progress Events` או בחשבונות.

## 6. תאימות הצרכנים הקיימים של `Financial Progress Events`

| צרכן | מה עושה | סיכון | טיפול |
| --- | --- | --- | --- |
| `calc.parse_events` | מדלג על `Kind` לא מוכר | **אין** — אירוע חדש לא נספר בחישובי מטרות קיימים | נשאר; הרחבה מפורשת רק בשלב המימוש |
| `calc.deposit_status` / `deposits_in_month` / `deposit_history` (#1315) | סופרים `one_time` בלבד | `deposit` חדש לא ייספר בסיכומי הפקדות | להרחיב במכוון ל-`one_time ∪ deposit` על אותו יעד, עם בדיקה |
| `service.overview().recent_events` | **10 האירועים האחרונים מכל סוג**, ללא סינון Kind | **סיכון אמיתי:** `balance_snapshot` של ₪500,000 יוצג בכרטיס "התקדמות אחרונה" כהתקדמות | לסנן ל-Kinds של התקדמות מטרות **לפני** כתיבת כל Kind חדש; בדיקה חדשה |
| `FinancialControlCenter.tsx` (רשימת התקדמות אחרונה) | מציג כל Kind כסכום | אותו סיכון | אותו תיקון בשרת; הלקוח לא משתנה |
| `service.recent_incomes` | מסנן `one_time`/`direct_cost` על יעדי הכנסה | אין | — |
| `conversation.income_followup` | בודק `Kind == one_time` ביעד הכנסה | אין | — |
| `draft.py` (`FCC_EVENT`) | חוזה כתיבה: `Goal` חובה, Kinds מוגבלים | אירוע חשבון (ללא מטרה) לא נכנס לחוזה | חוזה/ישות חדשים לחשבונות; `FCC_EVENT` לא משתנה |
| `data_access_policy` | `OWNER_SCOPED` + `linked_owner_checks` על `Goal` | קישור `Account` לחשבון של אחר | הרחבת `linked_owner_checks` (סעיף 3.3) |
| `tools/approval_actions` | רשימת טבלאות מותרות לכתיבת TMA | טבלה חדשה לא ברשימה | הוספה מפורשת רק אם נדרשת כתיבה |
| `schema_cache.json`, `airtable_schema.py` | מקור שמות השדות | שדות חדשים נחסמים כ-unknown | עדכון באותו PR (כמו ב-FCC Slice 1) |
| PR #1315 (`savings_history`) | נגזר מ-`one_time` | אין | נשאר בהיקפו |

## 7. מסלולים ושלבי מימוש

מודל החשבונות הוא **תלות משותפת D1** לשני המסלולים, לא תוכנית שלישית.

- **מסלול A — סימולטורים:** A1 תחזית לכל חשבון וסכום מאוחד (המנוע לא משתנה) · A2 מטרות ומועדי נזילות · A3 משיכות מתוזמנות ידנית. סדר משיכות לפי מס **מחוץ להיקף** ודורש SPEC נפרד.
- **מסלול ב — המסך:** B0 קיים (#1313, #1314, ו-#1315 בטיוטה) · B1 רשימת חשבונות ושווי מאוחד · B2 התקדמות לכל מטרה · B3 צילום יתרה והעברות דרך זרימת האישור.

**שלבי מימוש קטנים (כל שלב PR נפרד; שלבים 3 ואילך דורשים אישור נפרד):**

| # | שלב | סכמה | אישור | בדיקות חובה |
| --- | --- | --- | --- | --- |
| 1 | תיקון `recent_events`: רשימת היתר של Kinds קיימים בלבד, סינון **לפני** חיתוך ל-10 | אין | **ניתן** (סעיף 8) | התנהגות קיימת: כל ששת ה-Kinds הקיימים מוצגים כמו קודם; Kinds לא מוכרים (`balance_snapshot`, `withdrawal`, `fee`, `transfer`, `deposit`) מוסתרים ואינם דוחקים אירועים אמיתיים מה-10 |
| 2 | Reconcile חי נוסף + בקשת אישור סכמה: `Financial Accounts`, `Account` / `Counter Account` / `Verification`, ערכי `Kind` חדשים | הצעה בלבד | נדרש | — |
| 3 | סכמה בפועל + `airtable_schema.py` + `schema_cache.json` + `Tables`, מדיניות גישה `OWNER_SCOPED` ל-`Financial Accounts`, הרחבת `linked_owner_checks` ל-`Account` / `Counter Account` | כן | נדרש | **אבטחה:** תפקיד עסקי (Manager) לא רואה חשבונות; קישור לחשבון של אחר נדחה ביצירה ובעדכון; `PersonalDataAccessDenied` כשהזהות לא מזוהה; אין נתיב כללי שמחזיר את הטבלה |
| 4 | אכיפת "אין מספרי חשבון או פוליסה": ולידציה לרצף 8+ ספרות בשדות הטקסט | אין | בהמשך ישיר לשלב 3 | ערכים עם מספר ארוך נדחים; שמות רגילים, תאריכים וסכומים בהערות לא נחסמים בטעות |
| 5 | מודל קריאה בלבד `accounts_overview`: צילום תקף אחרון לכל חשבון, שווי מאוחד, העברות מחוץ לסיכומים | אין | נדרש | שווי מאוחד לא משתנה מתנועה בלבד; העברה לא נספרת כהפקדה / משיכה; צילום מבוטל (`Superseded By`) מתעלמים ממנו; אירועי מטרות קיימים לא משתנים |
| 6 | הרחבת `deposit_history` ל-`one_time ∪ deposit` על אותו יעד | אין | נדרש | אותה הפקדה לא נספרת פעמיים; #1315 ללא שינוי בהתנהגות |
| 7 | B1 (מסך, קריאה בלבד) ו-A1 (תחזית פר חשבון) במקביל | אין | נדרש | אין חישוב כספי בלקוח; הרשאות כמו FCC (דגל + canary + בעלים) |
| 8 | כתיבה (B3): ישות חדשה בחוזה הטיוטה, "אשר", idempotency | אין | נדרש | אין כתיבה אוטומטית; אירוע חשבון נדחה בלי בעלות מאומתת על החשבון |

## 8. החלטות הבעלים (14/10/2026)

1. **בעלות כלכלית:** בשלב הראשון `Holder Names` (טקסט), ללא קישור ל-`Contacts`. בידוד נתוני בעלי החשבונות ממשתמשים עסקיים הוא דרישה מחייבת; אין לשמור מספרי חשבון או פוליסה מלאים (סעיף 4).
2. **סוגי חשבון:** הרשימה בסעיף 3.1 מאושרת, כולל `other`. סוג מוצר פיננסי נפרד תמיד ממטרת חיסכון.
3. **תיקון `recent_events`:** אושר לתכנון ולמימוש כשלב עצמאי, לפני כל Kind חדש. חייב לשמור על האירועים הקיימים ולמנוע הצגת צילומי יתרה, העברות ועמלות כהתקדמות חיסכון.

**עדיין לא אושר:** יצירת `Financial Accounts` והרחבת סכמת Airtable.

## 9. מה אינו משתנה

#1315 נשאר בהיקפו (סיכומי הפקדות על יעד `long_term` קיים) ואינו מוסיף יתרות תיק. אין חישוב מס, אין המלצת משיכה, ואין כתיבה אוטומטית.
