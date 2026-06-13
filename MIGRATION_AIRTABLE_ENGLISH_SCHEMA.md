# MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md

## מטרת המסמך

העברת כלל מערכת BOSS OS מ־Hebrew Schema ל־English Schema בצורה
בטוחה, ללא אובדן נתונים, עם יכולת Rollback מלאה.

---

## סטטוס נוכחי

**לא לבצע Migration כעת.**

המערכת בייצור פעיל. מטרת המסמך היא להכין Migration עתידי בלבד.

---

## מה כבר הועבר לאנגלית

| מה | קובץ | תאריך |
|----|------|--------|
| `DealStatus` — שלבי ביצוע + שלבי Strategic Layer | `airtable_schema.py` | 2026-06-13 |
| `ContactRoleCategory` | `airtable_schema.py` | 2026-06-13 |
| `ApprovalStatus` (class חדשה) | `airtable_schema.py` | 2026-06-13 |
| `LeadFields` + `LeadStatus` | `airtable_schema.py` | קודם לכן |
| `RiskLevel` | `airtable_schema.py` | קודם לכן |
| `UnitStatus`, `ProjectStatus`, `LoanPaymentStatus` | `airtable_schema.py` | קודם לכן |
| `QuestStatus`, `WorldStatus`, `RoadmapTaskStatus`, `DailyTaskStatus` | `airtable_schema.py` | קודם לכן |
| `tma_api.py:289` — `"ממתין"` literal → `ApprovalStatus.PENDING` | `tma_api.py` | 2026-06-13 |
| `crm.py:249` — formula Hebrew literals → `DealFields` + `DealStage` constants | `crm.py` | 2026-06-13 |

---

## תנאי סף לפני התחלה

יש להתחיל Migration רק כאשר כל התנאים מתקיימים:

- [ ] גיבוי מלא של Airtable
- [ ] Export CSV לכל הטבלאות
- [ ] Git branch ייעודי
- [ ] Render Deploy תקין
- [ ] Smoke Tests עוברים
- [ ] חלון תחזוקה מוגדר
- [ ] Rollback Plan מאושר

---

## שלב 1 — Standardize Enum Values

### ContactStatus

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NEW` | חדש | `"New"` |
| `IN_PROGRESS` | בתהליכים | `"In Progress"` |
| `FOLLOWUP` | פולו-אפ | `"Follow Up"` |
| `NOT_RELEVANT` | לא רלוונטי | `"Not Relevant"` |

### DealStage

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `OPPORTUNITY` | הזדמנות | `"Opportunity"` |
| `NEGOTIATION` | במשא ומתן | `"Negotiation"` |
| `CLOSED_WIN` | סגור-ניצחון | `"Closed Won"` |
| `CLOSED_LOSS` | סגור-הפסד | `"Closed Lost"` |

### TaskStatus

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `PENDING` | ממתין | `"Pending"` |
| `IN_PROGRESS` | בביצוע | `"In Progress"` |
| `DONE` | בוצע | `"Completed"` |

### DeadlineStatus

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NOT_STARTED` | לא התחיל | `"Not Started"` |
| `IN_PROGRESS` | בתהליך | `"In Progress"` |
| `DONE` | הושלם | `"Completed"` |

### DeadlinePriority

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `HIGH` | גבוהה | `"High"` |
| `MEDIUM` | בינונית | `"Medium"` |
| `LOW` | נמוכה | `"Low"` |

### PaymentStatus

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `RECEIVED` | התקבל | `"Received"` |
| `IN_PROGRESS` | בתהליך | `"Processing"` |
| `CANCELLED` | בוטל | `"Cancelled"` |

### ExpenseCategory

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `MARKETING` | שיווק | `"Marketing"` |
| `OFFICE` | משרד | `"Office"` |
| `TRAVEL` | נסיעות | `"Travel"` |
| `OPERATIONS` | תפעול | `"Operations"` |
| `OTHER` | אחר | `"Other"` |

### ApprovalStatus *(class קיימת — ערכים ישתנו עם Migration)*

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `PENDING` | ממתין | `"Pending"` |
| `APPROVED` | אושר | `"Approved"` |
| `REJECTED` | נדחה | `"Rejected"` |

---

## שלב 2 — Rename Airtable Fields

### Contacts

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | שם | `"Name"` |
| `COMPANY` | חברה | `"Company"` |
| `EMAIL` | אימייל | `"Email"` |
| `PHONE` | טלפון | `"Phone"` |
| `FOLLOWUP_DATE` | תאריך פולו אפ | `"Next Followup"` |
| `STATUS` | סטטוס | `"Status"` |
| `DEALS_LINK` | עסקאות (Deals) | `"Deals"` |
| `TASKS_LINK` | משימות (Tasks) | `"Tasks"` |

### Deals

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | שם העסקה | `"Deal Name"` |
| `AMOUNT` | סכום | `"Amount"` |
| `STAGE` | שלב | `"Stage"` |
| `CLOSE_DATE` | תאריך סגירה | `"Close Date"` |
| `CONTACTS_LINK` | מקושר לאנשי קשר | `"Contacts"` |
| `TASKS_LINK` | משימות (Tasks) | `"Tasks"` |
| `PAYMENTS_LINK` | תשלומים (Payments) | `"Payments"` |

### Tasks

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | כותרת המשימה | `"Title"` |
| `DESCRIPTION` | תיאור | `"Description"` |
| `DUE_DATE` | תאריך יעד | `"Due Date"` |
| `STATUS` | סטטוס | `"Status"` |
| `CONTACTS_LINK` | מקושר לאנשי קשר | `"Contacts"` |
| `DEALS_LINK` | מקושר לעסקאות | `"Deals"` |

### Payments

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` / `REF` | אסמכתא | `"Reference"` |
| `AMOUNT` | סכום | `"Amount"` |
| `DATE` / `DUE_DATE` | תאריך | `"Date"` |
| `STATUS` | סטטוס | `"Status"` |
| `DEAL_LINK` | מקושר לעסקאות | `"Deals"` |
| `CONTACT` | מקושר לאנשי קשר | `"Contacts"` |
| `NOTES` | הערות | `"Notes"` |

### Expenses

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | שם ההוצאה | `"Expense Name"` |
| `AMOUNT` | סכום | `"Amount"` |
| `CATEGORY` | קטגוריה | `"Category"` |
| `DATE` | תאריך | `"Date"` |

### Deadlines

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | שם המשימה | `"Task Name"` |
| `STATUS` | סטטוס | `"Status"` |
| `DEADLINE` | תאריך דדליין | `"Deadline Date"` |
| `RESPONSIBLE` | אחראי | `"Owner"` |
| `DESCRIPTION` | תיאור המשימה | `"Description"` |
| `PRIORITY` | עדיפות | `"Priority"` |
| `UNIT_LINK` | קישור לרשומת מכירה/יחידה | `"Related Record"` |
| `NOTES` | הערות | `"Notes"` |

### Approvals

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `ACTION` | פעולה | `"Action"` |
| `REQUESTED_BY` | מבוקש על ידי | `"Requested By"` |
| `REQUESTED_AT` | בוקש בתאריך | `"Requested At"` |
| `RISK_LEVEL` | רמת סיכון | `"Risk Level"` |
| `CONTEXT_TYPE` | סוג הקשר | `"Context Type"` |
| `CONTEXT_ID` | מזהה הקשר | `"Context ID"` |
| `CONTEXT_DATA` | נתוני הקשר | `"Context Data"` |
| `STATUS` | סטטוס | `"Status"` |
| `REJECTION_NOTE` | הערת דחייה | `"Rejection Note"` |

### Assets

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `NAME` | שם הנכס | `"Asset Name"` |
| `TYPE` | סוג | `"Asset Type"` |
| `COST` | עלות רכישה | `"Purchase Cost"` |
| `VALUE` | שווי נוכחי | `"Current Value"` |
| `MORTGAGE` | משכנתא | `"Mortgage"` |
| `RENTAL_INCOME` | הכנסה חודשית | `"Monthly Income"` |
| `STATUS` | סטטוס | `"Status"` |
| `NOTES` | הערות | `"Notes"` |
| `DOCUMENTS` | מסמכים | `"Documents"` |

### Tables constants

| Python constant | עברית | אנגלית |
|----------------|-------|--------|
| `EXPENSES` | `"הוצאות (Expenses)"` | `"Expenses"` |
| `PAYMENTS` | `"תשלומים (Payments)"` | `"Payments"` |
| `CONTACTS` | `"אנשי קשר (Contacts)"` | `"Contacts"` |
| `DEALS` | `"עסקאות (Deals)"` | `"Deals"` |
| `DEADLINES` | `"משימות ודד ליינים"` | `"Deadlines"` |
| `TASKS` | `"משימות (Tasks)"` | `"Tasks"` |
| `LEARNINGS` | `"למידות ותובנות"` | `"Learnings"` |

---

## שלב 3 — Code Migration

קבצים לעדכון (בקוד בלבד — לאחר שינוי ה-UI):

| קובץ | שורות | מה לשנות |
|------|--------|----------|
| `airtable_schema.py` | כל ה-Fields classes + enum classes | ערכי strings לאנגלית |
| `crm.py` | 168, 317–319, 360–361 | formula strings עם `{סטטוס}`, `{שלב}`, `{תאריך}` |
| `tools/dispatcher.py` | 35–48 | `_DEDUP_FIELDS` + `_ALIAS_MAP` — Hebrew table/field names |
| `tools/dispatcher.py` | 197 | `.get("סטטוס", ...)` dedup display |
| `tma_api.py` | — | כבר תוקן (2026-06-13): `ApprovalStatus.PENDING` |
| `airtable_schema.py` | `FIELD_MAP` dict | display strings (user-facing, lower priority) |

> **הערה**: `interaction_engine.py` לא קיים בקודבייס הנוכחי. אם מודול דומה יופיע בעתיד — לכלול אותו.

---

## שלב 4 — Compatibility Layer

לתקופת מעבר (30–60 יום):

```python
record.get("Status", record.get("סטטוס"))
record.get("Name", record.get("שם"))
```

---

## שלב 5 — Verification

בדיקות חובה לאחר Migration:

- [ ] יצירת Contact
- [ ] יצירת Deal
- [ ] יצירת Task
- [ ] יצירת Approval
- [ ] יצירת Payment
- [ ] Lead Capture
- [ ] Followup Creation
- [ ] Daily Digest
- [ ] Dashboard
- [ ] Game Layer
- [ ] Activity Feed
- [ ] Search

---

## Rollback Plan

אם מתגלה תקלה לאחר Migration:

1. Restore Airtable Export (CSV שגובה לפני)
2. Revert Git Commit (`git revert` — לא `reset`)
3. Redeploy Render
4. Run Smoke Tests
5. Verify Lead Creation
6. Verify Approvals
7. Verify Dashboard

---

## המלצה אסטרטגית

לא לבצע Migration לפני:

- System Health Dashboard פעיל
- Governance Phase 2 הושלם
- Approval System יציב
- לפחות שבועיים ללא תקלות קריטיות

**עדיפות נוכחית: נמוכה.**

זהו חוב טכני ואחידות ארכיטקטונית, לא בעיית ייצור פעילה.

---

## Piggyback Trigger

ביצוע רק כשיש sprint ייעודי לתחזוקה (≥0.5 יום). לא ביזמה עצמאית.
ראה: `ARCHITECTURE_DRIFT_MAP.md`
