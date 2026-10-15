# D1 שלב 2 — בקשת שינוי סכמה (Schema Change Request) — מודל חשבונות להון משפחתי

**סטטוס: בקשה לאישור בלבד.** לא נוצרה טבלה, לא נוסף שדה, לא נכתבו נתונים, לא נפתח PR יישומי, לא הופעל flag ולא בוצעה פריסה. המסמך נגזר מ-[FAMILY_WEALTH_ACCOUNTS_SPEC.md](FAMILY_WEALTH_ACCOUNTS_SPEC.md) (סמכות) ואינו משנה אותו; אינדקס המסלולים ב-[MASTER_PLAN.md](MASTER_PLAN.md).

- **בסיס:** `origin/main` @ `73be4af6` · Airtable `app4bcgoX7t0HUVnm`, קריאה בלבד דרך MCP (`list_tables_for_base`, `get_table_schema`), 14/10/2026.
- **Planning Gate:** `Cross-Layer Impact: FULL` (מודל נתונים חדש, persistence, מדיניות הרשאה, קשר בין שכבות).
- **המלצה:** **READY FOR SCHEMA APPROVAL — לאפשרות M בלבד** (סעיף 9), בכפוף להחלטות הבעלים בסעיף 8. לאפשרות F (המלאה) — לא מומלץ לאשר עכשיו.

## 1. Reconcile חי מול הקוד וה-cache (קריאה בלבד)

| בדיקה | תוצאה |
| --- | --- |
| טבלאות חיות / ב-`schema_cache.json` | 56 / 49 — **זהה** לממצא מהבוקר; 7 הטבלאות החיות שאינן ב-cache עסקיות ולא קשורות (`Allocation Rules`, `Allocation Snapshots`, `Deal Economics`, `Monthly Calculation Batches`, `Organizations`, `Worker Assignments`, `Worker Monthly Results`) |
| `Financial Goals` (21 שדות), `Financial Progress Events` (13), `Profile` (17), `Assets` (21), `Recurring Obligations` (19) | **זהים לחלוטין** ל-cache |
| `Loans` | שדה חי `Direction` חסר ב-cache (הקוד כבר משתמש בו) — סטייה קיימת, לא קשורה |
| `Contacts` | 41 חי מול 36 ב-cache (5 שדות עסקיים) — לא קשור; הטבלה אינה נוגעת בשינוי |
| `Kind` חי באירועים | 6 ערכים: `one_time`, `monthly_recurring`, `target_change`, `note`, `direct_cost`, `household_expense` (= `calc.EVENT_KINDS`) |
| `Financial Progress Events.Goal` | קישור מרובה ל-`Financial Goals`; `Financial Owner` → `Profile` |
| טבלה בשם `Financial Accounts` | **אינה קיימת**; גם אין אזכור שלה בקוד |
| קונבנציית ערכי select ב-FCC | אנגלית `snake_case` (`active/paused/done`, `monthly/weekly/custom`, `period_sum/cumulative/recurring_level`) — ההצעה עוקבת אחריה |

**סטיות ה-cache הקיימות** (`Loans.Direction`, 5 שדות Contacts, 7 טבלאות) אינן חוסמות ולא יטופלו כאן; ייסגרו בריענון ה-cache שבשלב 3.

## 2. מה אפשר למחזר? (בדיקת מינימליות)

| מועמד למחזור | החלטה | נימוק |
| --- | --- | --- |
| טבלת `Assets` לחשבונות | **נדחה** | ערכי `Asset Type` נדל"ניים בלבד (Income Property, Residential, Land, Commercial…); `Status` בעברית של נדל"ן (מושכר/נמכר/בבנייה); `Current Value`, `Mortgage Balance` ונוסחאות `Equity`/`My Equity` מוזנים ללשונית "נכסים והון" (`core/financial_control/assets.py`) — פנסיה בתוכה תתערבב בסיכומי הון עצמי של נדל"ן; יש `Domain` (Finance/Personal) וזרימת כתיבה ייעודית ("נכס נמכר"). יתרון בלבד: כבר `OWNER_SCOPED` — לא מספיק כדי לפצות |
| `Financial Goals` כמחזיק יתרה | **נדחה** | החלטת הבעלים: שדה היתרה בתוך Goals בוטל; חשבון ≠ מטרה |
| שדות `Source`/`Source Ref` באירועים כמקור לאימות | **חלקי** | טקסט חופשי, לא ניתן לסינון אמין — מספיק כרגע כתחליף ל-`Verification` (נדחה, ראו להלן) |
| `Idempotency Key`, `Superseded By`, `Recorded By`, `Raw Text`, `Note`, `Occurred At`, `Amount`, `Financial Owner` | **ממוחזרים כמות שהם** | כבר מכסים כפילות, ביטול-ללא-מחיקה, תיעוד ובעלות; אין צורך בטבלת תנועות נפרדת (חלופה שנדחתה ב-SPEC §3.2) |
| `Recurring Obligations` / `Expenses` | לא רלוונטי | התחייבויות והוצאות, לא חשבונות |

**מסקנה:** טבלה חדשה נדרשת (אין טבלה קיימת שמתאימה סמנטית ובטוחה לשימוש חוזר), אך הרחבת האירועים וסט השדות ניתנים לצמצום (סעיף 3).

## 3. השוואה מדויקת: קיים ↔ SPEC המלא (F) ↔ מצומצם מומלץ (M)

### 3.1 `Financial Accounts` — טבלה חדשה

| שדה | סוג | F (SPEC) | **M (מומלץ)** | הערה |
| --- | --- | --- | --- | --- |
| `Name` (ראשי) | singleLineText | כן | **כן** | |
| `Account Type` | singleSelect | כן | **כן** | `pension`, `study_fund`, `provident_investment`, `managers_insurance`, `brokerage`, `liquid`, `other` (אושר) |
| `Institution` | singleLineText | כן | **כן** | |
| `Financial Owner` | link → `Profile` | כן | **כן** | הרשאה בלבד; יוצר שדה הפוך בטבלת `Profile` (ראו 5.3) |
| `Holder Names` | singleLineText | כן | **כן** | בעלות כלכלית כטקסט (אושר); ללא קישור ל-`Contacts` |
| `Status` | singleSelect | כן | **כן** | `active`, `closed` |
| `Liquidity` | singleSelect | כן | **כן** | `immediate`, `locked_until_date`, `age_based`, `unknown` |
| `Liquid From` | date | כן | **כן** | |
| `Tax Treatment` | singleSelect | כן | **כן** | `taxable`, `tax_advantaged`, `pension_rules`, `unknown` — **תיאורי בלבד** |
| `Notes` | multilineText | כן | **כן** | ללא מספרי חשבון/פוליסה מלאים |
| `Created At` | createdTime | (דפוס FCC) | **כן** | זהה לטבלאות FCC; מחליף `Opened At` |
| `Financial Progress Events` | link הפוך | אוטומטי | אוטומטי | נוצר עם `Events.Account` |
| `Tax Notes` | multilineText | כן | **נדחה** | מתמזג ב-`Notes`; ניתן להוסיף בהמשך (תוספת בלבד) |
| `Opened At` / `Closed At` | date | כן | **נדחה** | `Created At` + `Status`; תאריך סגירה — אירוע בהמשך אם יידרש |
| `Management Fee %` | number | כן | **נדחה ל-A1** | נדרש רק לתחזית פר חשבון; תוספת שדה בלבד, באישור A1 |

M: 10 שדות + `Created At` (11) מול 16 ב-F.

### 3.2 `Financial Progress Events` — הרחבה

| פריט | F (SPEC) | **M (מומלץ)** | הערה |
| --- | --- | --- | --- |
| שדה `Account` (link → `Financial Accounts`) | כן | **כן** | אופציונלי; אירועים קיימים נשארים ריקים |
| `Kind`: `deposit`, `withdrawal`, `fee`, `balance_snapshot` | כן | **כן (4 ערכים)** | `parse_events` מדלג על Kind לא מוכר, ו-`recent_events` מסנן בהיתר (#1318 ממוזג) |
| `Kind`: `transfer` + שדה `Counter Account` | כן | **נדחה** | נדרשים רק כשיש כתיבת העברות (B3); תוספת בלבד. עד אז אין כתיבה, ולכן אין סיכון לספירה כפולה |
| שדה `Verification` | כן | **נדחה** | עד B3 כל הצילומים "דיווח עצמי"; ברירת מחדל עתידית `self_reported` לאירועים קיימים — תוספת בלבד |

M: שדה אחד חדש + 4 ערכי `Kind` מול 3 שדות + 5 ערכים ב-F. **אין אובדן יכולת עד B3.**

**מה M לא מאפשר עד התוספות:** העברה בין חשבונות כאירוע יחיד; הבחנה בין צילום מדו"ח לצילום בדיווח עצמי; אחוז דמי ניהול פר חשבון (A1). אף אחד מאלה אינו נדרש ל-B1/B2 (קריאה בלבד) ולא ל-A0.

## 4. תאימות לאחור (נבדק בקוד, לא רק בתכנון)

| צרכן | מה נבדק | תוצאה |
| --- | --- | --- |
| `calc.parse_events` | שורה 88: `kind not in EVENT_KINDS` → דילוג | אירוע חדש לא נספר בחישובי מטרות; לא נדרש שינוי |
| `service.recent_events` | #1318 ממוזג, רשימת היתר | צילום יתרה/עמלה/משיכה לא יוצג כהתקדמות |
| `calc.deposit_history`/`deposit_status` | סופרים `one_time` בלבד | `deposit` חדש לא ייספר — הרחבה מכוונת רק בשלב 6 |
| `service._goal_ids_of` | מחזיר `[]` כשאין `Goal` | אירוע חשבון בלי מטרה אינו שובר צרכן |
| `draft.py` `FCC_EVENT` | דורש `Goal` | חוזה הכתיבה הקיים לא משתנה; כתיבת אירוע חשבון = ישות חדשה בשלב 8 |
| `Profile` | קוד שקורא את הטבלה | בסריקת grep לא נמצא קורא שמונה את כל שדות `Profile` (`tma_api`, `owner_resolution` ניגשים לרשומה לפי שדות ידועים); שדה הפוך חדש אינו נקרא. `schema_audit` ימפה את `ProfileFields` — יש לעדכן את הקבוע/ה-cache בשלב 3 |
| `Assets`, `Loans`, `Contacts`, `Recurring Obligations` | | לא משתנים |
| אירועים קיימים (נתוני פרודקשן) | | לא נערכים, לא נמחקים, `Account` ריק |

## 5. הרשאות, בעלות ופרטיות

1. **`OWNER_SCOPED`** ל-`Financial Accounts` ב-`core/data_access_policy.py` עם `owner_field = Financial Owner`; תפקיד עסקי (גם בעלים עסקי) אינו מעניק גישה — כמו שאר טבלאות ה-FCC.
2. **`linked_owner_checks`** של `Financial Progress Events` יורחב ב-`Account` (ב-F גם `Counter Account`): אסור לקשר אירוע לחשבון של אדם אחר, ביצירה ובעדכון.
3. **שדה הפוך ב-`Profile`:** קישור `Financial Owner` יוצר ב-`Profile` שדה `Financial Accounts` (כמו הקיימים `Financial Goals`/`Financial Progress Events`). זו השפעה על טבלה קיימת; היא רק קישור הפוך ללא נתון חדש, ויש לאשר אותה במפורש.
4. **פרטיות:** `Holder Names` נקרא רק דרך הטבלה ה-OWNER_SCOPED; אין קישור ל-`Contacts` (ללא מדיניות גישה ועם תפקידים עסקיים). אין לשמור מספרי חשבון/פוליסה מלאים; ולידציה לרצף 8+ ספרות (SPEC שלב 4) חלה רק על נתיבי קוד — הזנה ידנית ב-Airtable לא עוברת בה.
5. **גבול Airtable:** מי שיש לו גישת Base ב-Airtable רואה את כל הטבלאות; המגבלה זהה לטבלאות FCC הקיימות והיא מחוץ להיקף קוד.

## 6. סדר מימוש מוצע (תיקון לסדר ב-SPEC)

ממצא: טבלה שאינה רשומה ב-`data_access_policy` מקבלת `policy_for(...) = None` — כלומר חלות עליה כללי התפקידים הכלליים. לכן **המדיניות חייבת להיות ממוזגת לפני יצירת הטבלה**, ולא באותו שלב.

| # | שלב | מי | סכמה | בדיקות חובה |
| --- | --- | --- | --- | --- |
| 3א | PR יישומי (טיוטה): קבועי `FinAccountFields`, `Tables.FIN_ACCOUNTS`, רישום `OWNER_SCOPED` + `linked_owner_checks` (`Account`) | סוכן, באישור | אין | **אבטחה:** Manager/Employee לא מקבלים חשבונות; קישור לחשבון של אחר נדחה (יצירה ועדכון); זהות לא מזוהה → `PersonalDataAccessDenied`; אין נתיב כללי שמחזיר את הטבלה; **תאימות:** כל טסטי FCC הקיימים עוברים ללא שינוי; הטבלה הלא-קיימת לא שוברת קריאות |
| 3ב | יצירת הטבלה והשדות בפועל (סעיף 4), קריאה חוזרת וגיבוי סכמה לפני/אחרי | באישור סכמה נפרד | כן | קריאה חוזרת: שמות/סוגים/ערכים זהים לבקשה; `Kind` מכיל 6+4; אין שינוי בשדות קיימים |
| 3ג | ריענון `schema_cache.json` + `ProfileFields` | סוכן | אין | `schema_audit` ללא סטייה חדשה |
| 4 | ולידציית 8+ ספרות בנתיבי קוד | סוכן | אין | לפי SPEC שלב 4 |
| 5+ | `accounts_overview` וכו' | לפי SPEC | | לפי SPEC |

אין כתיבת נתונים, ממשק או TMA בשלבים 3א–3ג.

## 7. תוכנית חזרה לאחור

**עקרונות:** כל שינוי תוספתי; אין שינוי בשדות קיימים או בנתונים; אין flag חדש ולכן אין מה לכבות; הקוד לא נוגע בטבלה עד שלב 5.

| שלב שנכשל | חזרה | הערות |
| --- | --- | --- |
| 3א (קוד) | `git revert` של ה-PR | אין תלות נתונים |
| 3ב — טבלה/שדה שגויים, **לפני נתונים** | מחיקת הטבלה/השדות החדשים בלבד (פעולה הרסנית — רק באישור מפורש); לפני כן גיבוי סכמה | הטבלה ריקה; שדה `Account` ריק בכל האירועים |
| 3ב — ערכי `Kind` חדשים | להשאיר ערכים לא בשימוש (אינרטיים: `parse_events` מדלג, `recent_events` מסתיר); הסרה ידנית אופציונלית | אין תלות |
| שדה הפוך ב-`Profile` | נמחק יחד עם שדה הקישור | |
| אחרי תחילת כתיבת נתונים | אירועים append-only: ביטול באמצעות `Superseded By`; חשבון — `Status = closed`; **לא מוחקים** נתוני פרודקשן | |

**תנאי עצירה:** כל סטייה בקריאה החוזרת, כל שינוי בשדה קיים, או כל כשל טסט תאימות — עוצרים ומחזירים לפי הטבלה. **לא נבדק מראש ולכן לא מובטח:** אפשרויות שחזור של שדות/טבלאות שנמחקו ב-Airtable, והאם הוספת ערכי `Kind` דרך ה-API ללא `typecast` זמינה — יאומתו בקריאה חוזרת בשלב 3ב ולא על סמך הנחה.

## 8. החלטות פתוחות לבעלים

1. **אפשרות M (מומלץ) או F** — סעיף 3.
2. **אישור הסדר המתוקן** (מדיניות לפני טבלה) — סעיף 6.
3. **מי יוצר את הסכמה:** הסוכן דרך Airtable MCP (באישור מפורש לכל פעולה) או הבעלים ידנית ב-Airtable.
4. **אישור השדה ההפוך ב-`Profile`** — סעיף 5.3.
5. **רשימות הערכים הסופיות** (`Account Type`, `Liquidity`, `Tax Treatment`, `Status`) — סעיף 3.1.
6. **הודעת מדיניות לבעלים:** אין הגנה על הזנה ידנית ב-Airtable (ספרות ארוכות) — סעיף 5.4.

### החלטות הבעלים (15/10/2026) — נקלטו

| # | החלטה |
| --- | --- |
| 1 | **אפשרות F (המלאה)** נבחרה — בניגוד להמלצה על M; כל השדות והערכים של §3.1/§3.2 במסמך SPEC נכללים (15 שדות כולל `Created At` + `Account`, `Counter Account`, `Verification` + 5 ערכי `Kind`) |
| 2 | הסדר המתוקן אושר (מדיניות לפני נתונים) |
| 3 | הבעלים יוצר את הסכמה ב-Airtable; הסוכן מכין הוראה מדויקת ומבצע בדיקת התאמה אחריה: [D1_AIRTABLE_CREATION_INSTRUCTIONS.md](D1_AIRTABLE_CREATION_INSTRUCTIONS.md) |
| 4 | השדה ההפוך `Financial Accounts` ב-`Profile` אושר |
| 5 | רשימות הערכים הסופיות אושרו |
| 6 | (נשאר) הזנה ידנית ב-Airtable אינה מוגנת ע"י ולידציית הקוד — ראו §5.4 |

**השפעת הבחירה ב-F:** ל-`Events` שני קישורים ל-`Financial Accounts`, ולכן יש לקבוע במפורש את השדות ההפוכים (`Account` → הפוך `Financial Progress Events`; `Counter Account` → ללא הפוך) — מפורט בהוראת היצירה. `linked_owner_checks` יורחב ב-`Account` **וגם** ב-`Counter Account`. הסיכון של שדות ללא צרכן עד B3 (`Verification`, `Counter Account`, `transfer`) התקבל במודע; אין כתיבה אליהם לפני B3.

## 9. המלצה

**READY FOR SCHEMA APPROVAL — לאפשרות M.** נימוקים: reconcile חי נקי וללא סטייה בטבלאות הרלוונטיות; אין טבלה קיימת מתאימה; תאימות לאחור אומתה בקוד; השינוי תוספתי ובר-חזרה; ההרשאה ממומשת לפני יצירת הטבלה.

**תנאים לפני כל פעולה:** אישור מפורש נפרד של סעיף 8 (1–5); אין התחלה של A1–A3 או B1–B3 ללא אישור משלהם. **NOT READY** לאפשרות F: תוסיף שדות (`Verification`, `Counter Account`, `transfer`) שאין להם צרכן עד B3 — העדפה לצמצם.

**מה לא בוצע:** יצירת טבלה/שדות, כתיבת נתונים, קוד יישומי, flags, פריסה.
