# D1 — הוראת יצירה ב-Airtable (אפשרות F, באישור הבעלים 15/10/2026)

**זהו נוסח הוראה בלבד. לא בוצע ב-Airtable על ידי הסוכן; הבעלים ביצע ב-15/10/2026 והתוצאה אומתה בבקשת השינוי (סעיף "תוצאת היצירה והתאמה").** היוצר: הבעלים. מקור סמכות: [FAMILY_WEALTH_ACCOUNTS_SPEC.md](FAMILY_WEALTH_ACCOUNTS_SPEC.md) §3 ו-[D1_SCHEMA_CHANGE_REQUEST.md](D1_SCHEMA_CHANGE_REQUEST.md).

- בסיס: `app4bcgoX7t0HUVnm`.
- החלטות בעלים (15/10/2026): אפשרות **F** (מלאה) · הסדר המתוקן (מדיניות לפני נתונים) · הבעלים יוצר את הסכמה · אושרו השדה ההפוך ב-`Profile` ורשימות הערכים.

## 0. כללים לפני שמתחילים

1. **לא להזין שום נתון בטבלה החדשה** (לא רשומה אחת, גם לא לבדיקה) עד שהסוכן יאשר שהמדיניות `OWNER_SCOPED` ממוזגת ל-`main`. טבלה ריקה אינה חושפת דבר; טבלה עם נתונים לפני המדיניות כפופה לכללי תפקידים כלליים.
2. שמות שדות וערכים **בדיוק כמו בהוראה** (אותיות גדולות/קטנות, רווחים, `snake_case`). הקוד מבצע התאמה מדויקת.
3. **לא** להוסיף: נוסחאות, Rollup, Lookup, Automations, ערכי ברירת מחדל, שדות נוספים, או שינוי שם/מחיקה של שדה או ערך קיים בטבלאות קיימות.
4. אפשר להשאיר את צבעי ברירת המחדל של ערכי ה-select.
5. אחרי היצירה: ללחוץ "בצע בדיקה" (סעיף 4) — הסוכן יריץ reconcile בקריאה בלבד ויחזיר התאמה/סטייה לפני כל המשך.

## 1. טבלה חדשה: `Financial Accounts`

תיאור הטבלה (Description): `FCC: private owner-scoped financial accounts (pension, study fund, brokerage, liquid…). Product, not goal. No full account/policy numbers.`

| # | שם שדה | סוג | הגדרות |
| --- | --- | --- | --- |
| 1 | `Name` | Single line text | **שדה ראשי** |
| 2 | `Account Type` | Single select | ערכים בדיוק: `pension` · `study_fund` · `provident_investment` · `managers_insurance` · `brokerage` · `liquid` · `other` |
| 3 | `Institution` | Single line text | |
| 4 | `Financial Owner` | Link to another record → `Profile` | **כמו ב-`Financial Goals`/`Financial Progress Events`:** מותר קישור למספר רשומות (ללא "limit to single record"); **ליצור שדה הפוך ב-`Profile` בשם `Financial Accounts`** (אושר) |
| 5 | `Holder Names` | Single line text | |
| 6 | `Status` | Single select | `active` · `closed` |
| 7 | `Liquidity` | Single select | `immediate` · `locked_until_date` · `age_based` · `unknown` |
| 8 | `Liquid From` | Date | פורמט ISO (`YYYY-MM-DD`), ללא שעה |
| 9 | `Tax Treatment` | Single select | `taxable` · `tax_advantaged` · `pension_rules` · `unknown` |
| 10 | `Tax Notes` | Long text | ללא עיצוב עשיר (Rich text כבוי) |
| 11 | `Management Fee %` | Number | עשרוני, **שני** ספרות אחרי הנקודה; ללא סימן אחוז/מטבע. הערך באחוזים (למשל `0.75`) |
| 12 | `Opened At` | Date | ISO, ללא שעה |
| 13 | `Closed At` | Date | ISO, ללא שעה |
| 14 | `Notes` | Long text | Rich text כבוי. **לא לרשום מספרי חשבון/פוליסה מלאים** |
| 15 | `Created At` | Created time | דפוס FCC הקיים; תאריך+שעה |

הערות:
- שדה 15 הוא תוספת לפי הדפוס של שאר טבלאות ה-FCC (ב-SPEC לא נרשם במפורש).
- השדה ההפוך `Financial Progress Events` ב-`Financial Accounts` ייווצר אוטומטית בשלב 2 (ראו להלן). לא ליצור אותו ידנית.
- אל תיצור "תצוגות" נוספות מעבר לברירת המחדל.

## 2. הרחבה של `Financial Progress Events` (טבלה קיימת — **תוספות בלבד**)

| # | פעולה | שם | סוג / ערכים |
| --- | --- | --- | --- |
| 2.1 | שדה חדש | `Account` | Link → `Financial Accounts`. **Limit to a single record**: כן. **שדה הפוך ב-`Financial Accounts`: כן, בשם `Financial Progress Events`** |
| 2.2 | שדה חדש | `Counter Account` | Link → `Financial Accounts`. **Limit to a single record**: כן. **שדה הפוך: לא** (אם האפשרות לא זמינה ב-UI — ליצור הפוך בשם `Incoming Transfers` ולדווח) |
| 2.3 | שדה חדש | `Verification` | Single select: `self_reported` · `statement` · `bank_or_fund_confirmed` (ללא ברירת מחדל) |
| 2.4 | הוספת ערכים לשדה הקיים `Kind` | `Kind` | **להוסיף בלבד** חמישה ערכים: `deposit` · `withdrawal` · `fee` · `transfer` · `balance_snapshot`. **לא לשנות/למחוק/לשנות סדר** של ששת הקיימים: `one_time`, `monthly_recurring`, `target_change`, `note`, `direct_cost`, `household_expense` |

אסור לשנות את `Goal`, `Financial Owner`, `Idempotency Key`, `Superseded By` או כל שדה קיים אחר.

## 3. סדר ביצוע מומלץ

1. סעיף 1 (הטבלה, כולל שדה 4 עם ההפוך ב-`Profile`).
2. סעיף 2.1–2.3, ואז 2.4.
3. בדיקה ראשונית ב-UI: הטבלה ריקה; באירועים קיימים `Account`, `Counter Account`, `Verification` ריקים; `Kind` מציג 11 ערכים.
4. לעצור. לא להזין נתונים.

**סדר מול הקוד (מאושר):** שלב 3א — PR יישומי עם רישום `OWNER_SCOPED` — ימוזג לפני הזנת נתונים. היצירה עצמה (טבלה ריקה) אפשרית לפני, אך **אין להזין נתונים**.

## 4. בדיקת התאמה (על ידי הסוכן, קריאה בלבד, אחרי היצירה)

הסוכן יקרא `list_tables_for_base` ו-`get_table_schema` ויבדוק:

- קיימת טבלה `Financial Accounts` עם בדיוק 15 שדות בנוסף לשדה ההפוך `Financial Progress Events`; שמות וסוגים ורשימות הערכים זהים לסעיף 1.
- ב-`Profile` נוסף שדה הפוך `Financial Accounts` (קישור) — והוא היחיד שנוסף.
- ב-`Financial Progress Events` נוספו רק `Account`, `Counter Account`, `Verification`; `Kind` = 11 ערכים, ששת הקיימים ללא שינוי (כולל מזהי הערכים).
- מספר השדות ב-`Financial Goals` (21), `Assets` (21), `Recurring Obligations` (19) ללא שינוי.
- אין טבלאות נוספות/שונות (56 → 57).
- תוצאה: **MATCH** או רשימת סטיות מדויקת. אל תתקן בעצמך סטייה לפני שתחזור אליי.

## 5. חזרה לאחור (אם משהו נוצר לא נכון)

- **לפני נתונים:** מחיקת הטבלה/השדות החדשים בלבד (פעולה הרסנית, רק באישורך המפורש). ערכי `Kind` שנוספו אינם מזיקים אם נשארים ללא שימוש.
- **לעולם לא** למחוק או לשנות שדה או ערך קיים; אם בטעות שונה — לעצור ולדווח לפני כל תיקון.
- השדה ההפוך `Financial Accounts` ב-`Profile` נמחק יחד עם שדה הקישור שיצר אותו.
- לא נבדק מראש (ולכן לא מובטח): אפשרויות שחזור של שדות או טבלאות שנמחקו ב-Airtable.

## 6. מה לא מכוסה

הוראה זו אינה יוצרת: `Account Goal Shares`, `Holders`→`Contacts`, נתונים, ממשק, TMA, קוד או flags. A1–A3 ו-B1–B3 לא הותחלו.
