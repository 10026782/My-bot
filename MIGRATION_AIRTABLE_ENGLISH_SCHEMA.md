# MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md

## מטרה

הסבת כל שמות שדות ה-Airtable וערכי ה-single-select מעברית לאנגלית.
המיגרציה **חייבת להתבצע בבת אחת** — שינוי חלקי שובר את הסנכרון בין קוד ל-Airtable.

**גרסת אודיט**: ביצוע: 2026-06-13 | אחראי: Claude Code

---

## מה כבר הועבר לאנגלית

| מה | קובץ | תאריך |
|----|------|--------|
| `DealStatus` — שלבי ביצוע + שלבי Strategic Layer | `airtable_schema.py` | 2026-06-13 |
| `ContactRoleCategory` | `airtable_schema.py` | 2026-06-13 |
| `LeadFields` + `LeadStatus` | `airtable_schema.py` | קודם לכן |
| `RiskLevel` | `airtable_schema.py` | קודם לכן |
| `UnitStatus`, `ProjectStatus`, `LoanPaymentStatus` | `airtable_schema.py` | קודם לכן |
| `QuestStatus`, `WorldStatus`, `RoadmapTaskStatus`, `DailyTaskStatus` | `airtable_schema.py` | קודם לכן |
| `ApprovalStatus` (class חדשה) | `airtable_schema.py` | 2026-06-13 |

---

## מה נשאר בעברית — לשלב עתידי

### 1. שמות שדות Airtable (Column Names) — דורש שינוי UI ידני

כל שדה ה**חייב** להשתנות גם ב-Airtable UI וגם בקוד בו-זמנית:

#### ContactFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"שם"` | `"Name"` |
| `COMPANY` | `"חברה"` | `"Company"` |
| `EMAIL` | `"אימייל"` | `"Email"` |
| `PHONE` | `"טלפון"` | `"Phone"` |
| `FOLLOWUP_DATE` | `"תאריך פולו אפ"` | `"Follow-up Date"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `DEALS_LINK` | `"עסקאות (Deals)"` | `"Deals"` |
| `TASKS_LINK` | `"משימות (Tasks)"` | `"Tasks"` |

#### DealFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"שם העסקה"` | `"Deal Name"` |
| `AMOUNT` | `"סכום"` | `"Amount"` |
| `STAGE` | `"שלב"` | `"Stage"` |
| `CLOSE_DATE` | `"תאריך סגירה"` | `"Close Date"` |
| `CONTACTS_LINK` | `"מקושר לאנשי קשר"` | `"Contacts"` |
| `TASKS_LINK` | `"משימות (Tasks)"` | `"Tasks"` |
| `PAYMENTS_LINK` | `"תשלומים (Payments)"` | `"Payments"` |

#### TaskFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"כותרת המשימה"` | `"Task Name"` |
| `DESCRIPTION` | `"תיאור"` | `"Description"` |
| `DUE_DATE` | `"תאריך יעד"` | `"Due Date"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `CONTACTS_LINK` | `"מקושר לאנשי קשר"` | `"Contacts"` |
| `DEALS_LINK` | `"מקושר לעסקאות"` | `"Deals"` |

#### PaymentFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` / `REF` | `"אסמכתא"` | `"Reference"` |
| `AMOUNT` | `"סכום"` | `"Amount"` |
| `DATE` / `DUE_DATE` | `"תאריך"` | `"Date"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `DEAL_LINK` | `"מקושר לעסקאות"` | `"Deals"` |
| `CONTACT` | `"מקושר לאנשי קשר"` | `"Contacts"` |
| `NOTES` | `"הערות"` | `"Notes"` |

#### ExpenseFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"שם ההוצאה"` | `"Expense Name"` |
| `AMOUNT` | `"סכום"` | `"Amount"` |
| `CATEGORY` | `"קטגוריה"` | `"Category"` |
| `DATE` | `"תאריך"` | `"Date"` |

#### DeadlineFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"שם המשימה"` | `"Task Name"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `DEADLINE` | `"תאריך דדליין"` | `"Deadline"` |
| `RESPONSIBLE` | `"אחראי"` | `"Responsible"` |
| `DESCRIPTION` | `"תיאור המשימה"` | `"Description"` |
| `PRIORITY` | `"עדיפות"` | `"Priority"` |
| `UNIT_LINK` | `"קישור לרשומת מכירה/יחידה"` | `"Unit"` |
| `NOTES` | `"הערות"` | `"Notes"` |

#### ApprovalsFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `ACTION` | `"פעולה"` | `"Action"` |
| `REQUESTED_BY` | `"מבוקש על ידי"` | `"Requested By"` |
| `REQUESTED_AT` | `"בוקש בתאריך"` | `"Requested At"` |
| `RISK_LEVEL` | `"רמת סיכון"` | `"Risk Level"` |
| `CONTEXT_TYPE` | `"סוג הקשר"` | `"Context Type"` |
| `CONTEXT_ID` | `"מזהה הקשר"` | `"Context ID"` |
| `CONTEXT_DATA` | `"נתוני הקשר"` | `"Context Data"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `REJECTION_NOTE` | `"הערת דחייה"` | `"Rejection Note"` |

#### AssetsFields
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `NAME` | `"שם הנכס"` | `"Asset Name"` |
| `TYPE` | `"סוג"` | `"Type"` |
| `COST` | `"עלות רכישה"` | `"Purchase Cost"` |
| `VALUE` | `"שווי נוכחי"` | `"Current Value"` |
| `MORTGAGE` | `"משכנתא"` | `"Mortgage"` |
| `RENTAL_INCOME` | `"הכנסה חודשית"` | `"Monthly Income"` |
| `STATUS` | `"סטטוס"` | `"Status"` |
| `NOTES` | `"הערות"` | `"Notes"` |
| `DOCUMENTS` | `"מסמכים"` | `"Documents"` |

#### Tables constants
| Python constant | ערך עברי נוכחי | ערך אנגלי מוצע |
|----------------|----------------|----------------|
| `EXPENSES` | `"הוצאות (Expenses)"` | `"Expenses"` |
| `PAYMENTS` | `"תשלומים (Payments)"` | `"Payments"` |
| `CONTACTS` | `"אנשי קשר (Contacts)"` | `"Contacts"` |
| `DEALS` | `"עסקאות (Deals)"` | `"Deals"` |
| `DEADLINES` | `"משימות ודד ליינים"` | `"Deadlines"` |
| `TASKS` | `"משימות (Tasks)"` | `"Tasks"` |
| `LEARNINGS` | `"למידות ותובנות"` | `"Learnings"` |

---

### 2. ערכי Single-Select בעברית — דורש שינוי UI ידני

| Class | ערכים עבריים נוכחיים | ערכים אנגליים מוצעים |
|-------|---------------------|---------------------|
| `TaskStatus` | `ממתין / בביצוע / בוצע` | `Pending / In Progress / Done` |
| `DeadlineStatus` | `לא התחיל / בתהליך / הושלם` | `Not Started / In Progress / Done` |
| `DeadlinePriority` | `גבוהה / בינונית / נמוכה` | `High / Medium / Low` |
| `ContactStatus` | `חדש / בתהליכים / פולו-אפ / לא רלוונטי` | `New / Active / Follow-up / Not Relevant` |
| `DealStage` | `הזדמנות / במשא ומתן / סגור-ניצחון / סגור-הפסד` | `Opportunity / Negotiation / Closed Won / Closed Lost` |
| `PaymentStatus` | `התקבל / בתהליך / בוטל` | `Received / In Progress / Cancelled` |
| `ExpenseCategory` | `שיווק / משרד / נסיעות / תפעול / אחר` | `Marketing / Office / Travel / Operations / Other` |
| `ApprovalStatus` | `ממתין / אושר / נדחה` | `Pending / Approved / Rejected` |

---

### 3. שינויי קוד נדרשים (ללא שינוי UI)

| קובץ | שורות | מה לשנות |
|------|--------|----------|
| `crm.py` | 168, 317–319, 360–361 | formula strings עם `{סטטוס}`, `{שלב}`, `{תאריך}` |
| `tools/dispatcher.py` | 35–48 | `_DEDUP_FIELDS` + `_ALIAS_MAP` — Hebrew table/field names |
| `tools/dispatcher.py` | 197 | `.get("סטטוס", ...)` dedup display |
| `airtable_schema.py` | `FIELD_MAP` dict | display strings (user-facing, lower priority) |

---

## סדר עבודה מומלץ

1. **קוד בלבד** (ללא Airtable UI): עדכן `crm.py` + `tools/dispatcher.py` להשתמש בקבועים במקום literals — הכן את הקוד לקראת ה-UI migration
2. **Airtable UI + קוד יחד** (חייב להיות deploy atomically):
   a. שנה שמות שדות + ערכי single-select ב-Airtable UI (לכל טבלה בנפרד)
   b. עדכן `airtable_schema.py` — ערכי ה-enum והשמות
   c. Deploy מיידי אחרי כל טבלה — אל תשנה 3 טבלאות ותעשה deploy אחד
3. **Casing alignment**: `ContactRoleCategory` ו-`ContactStatus` → Title Case

## Piggyback Trigger

ביצוע רק כשיש sprint ייעודי לתחזוקה (≥0.5 יום). לא ביזמה עצמאית.
ראה: `ARCHITECTURE_DRIFT_MAP.md`
