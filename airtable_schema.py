# airtable_schema.py
# קבועי סכמה לכל טבלאות Airtable של אליהו חזן
# שנה כאן → משתנה בכל המערכת. אין magic strings.

def format_schema_for_prompt() -> str:
    """בונה תיאור סכמה מהקבועים הסטטיים להזרקה לsystem prompt."""
    return (
        "שמות טבלאות Airtable (השתמש בשמות המדויקים האלה בלבד):\n"
        f"• \"{Tables.CONTACTS}\" | שדות: {ContactFields.NAME}, {ContactFields.PHONE}, {ContactFields.EMAIL}, {ContactFields.TYPE}, {ContactFields.COMPANY}, {ContactFields.LAST_CONTACT}\n"
        f"• \"{Tables.DEALS}\"    | שדות: {DealFields.NAME}, {DealFields.ADDRESS}, {DealFields.STATUS}, {DealFields.PRICE}, {DealFields.FUNDING_COST}, {DealFields.DEADLINE}\n"
        f"• \"{Tables.PAYMENTS}\" | שדות: {PaymentFields.NAME}, {PaymentFields.AMOUNT}, {PaymentFields.DUE_DATE}, {PaymentFields.STATUS}, {PaymentFields.DEAL}\n"
        f"• \"{Tables.TASKS}\"    | שדות: {TaskFields.NAME}, {TaskFields.STATUS}, {TaskFields.PRIORITY}, {TaskFields.DEADLINE}\n"
        f"• \"{Tables.EXPENSES}\" | שדות: {ExpenseFields.NAME}, {ExpenseFields.AMOUNT}, {ExpenseFields.DATE}, {ExpenseFields.CATEGORY}\n"
        f"• \"{Tables.LEARNINGS}\"| שדות: Name, Notes\n"
    )

# ══════════════════════════════════════════════════
# שמות טבלאות
# ══════════════════════════════════════════════════

class Tables:
    # ── שמות מדויקים כפי שמופיעים ב-Airtable ──
    CONTACTS   = "אנשי קשר (Contacts)"
    DEALS      = "עסקאות (Deals)"
    TASKS      = "משימות (Tasks)"
    EXPENSES   = "הוצאות (Expenses)"
    PAYMENTS   = "תשלומים (Payments)"
    LEARNINGS  = "למידות ותובנות (Learnings & Insights)"
    PROFILE    = "Profile"
    CASHFLOW   = "Weekly Cash Flow Reports"
    SALES_DEBT = "Unit Sales & Debt Distribution"
    DEADLINES  = "משימות ודד ליינים"
    PROJECTS   = "Projects"
    UNITS      = "Units"
    LOANS      = "Loans"
    DEBT_MGMT  = "Company A - Debt Management"
    # IMPORTS — אין טבלה תואמת עדיין ב-Airtable


# ══════════════════════════════════════════════════
# שדות לכל טבלה
# ══════════════════════════════════════════════════

class ContactFields:
    NAME        = "Name"
    PHONE       = "Phone"
    EMAIL       = "Email"
    TYPE        = "Type"          # Client | Supplier | Partner | Lawyer | Accountant
    COMPANY     = "Company"
    NOTES       = "Notes"
    LAST_CONTACT = "Last Contact"  # Date
    STATUS      = "Status"        # Active | Inactive


class DealFields:
    NAME        = "Name"
    ADDRESS     = "Address"
    STATUS      = "Status"        # Prospect | Due Diligence | Active | Closed | Cancelled
    PRICE       = "Price"         # ₪
    FUNDING_COST = "Funding Cost %" # % — כלל ה-9%
    ROI         = "ROI %"
    CONTACT     = "Contact"       # Link → Contacts
    DEADLINE    = "Deadline"
    NOTES       = "Notes"
    RISK_LEVEL  = "Risk Level"    # Low | Medium | High


class TaskFields:
    NAME        = "Name"
    STATUS      = "Status"        # Open | In Progress | Done | Cancelled
    PRIORITY    = "Priority"      # Urgent | High | Normal | Low
    DEADLINE    = "Deadline"
    DEAL        = "Deal"          # Link → Deals (optional)
    NOTES       = "Notes"
    CREATED     = "Created"


class ExpenseFields:
    NAME        = "Name"
    AMOUNT      = "Amount"        # ₪
    DATE        = "Date"
    CATEGORY    = "Category"      # Import | Real Estate | Operations | Legal | Other
    DEAL        = "Deal"          # Link → Deals (optional)
    RECEIPT     = "Receipt"       # Attachment
    NOTES       = "Notes"


class ImportFields:
    PRODUCT     = "Product"
    SUPPLIER    = "Supplier"      # Link → Contacts
    STATUS      = "Status"        # Sample | Approval | Production | QC | Shipping | Done
    ADVANCE_PCT = "Advance %"     # אמור להיות 30
    BALANCE_PCT = "Balance %"     # אמור להיות 70
    TOTAL_USD   = "Total USD"
    SHIP_DATE   = "Ship Date"
    QC_PASSED   = "QC Passed"     # Checkbox
    NOTES       = "Notes"


class PaymentFields:
    NAME        = "Name"
    AMOUNT      = "Amount"        # ₪
    DUE_DATE    = "Due Date"
    STATUS      = "Status"        # Pending | Paid | Overdue
    DEAL        = "Deal"          # Link → Deals (optional)
    CONTACT     = "Contact"       # Link → Contacts (optional)
    NOTES       = "Notes"


# ══════════════════════════════════════════════════
# ערכים חוקיים לשדות Enum
# ══════════════════════════════════════════════════

class ContactType:
    CLIENT      = "Client"
    SUPPLIER    = "Supplier"
    PARTNER     = "Partner"
    LAWYER      = "Lawyer"
    ACCOUNTANT  = "Accountant"

class ContactStatus:
    ACTIVE      = "Active"
    INACTIVE    = "Inactive"

class DealStatus:
    PROSPECT       = "Prospect"
    DUE_DILIGENCE  = "Due Diligence"
    ACTIVE         = "Active"
    CLOSED         = "Closed"
    CANCELLED      = "Cancelled"

class RiskLevel:
    LOW         = "Low"
    MEDIUM      = "Medium"
    HIGH        = "High"

class TaskStatus:
    OPEN        = "Open"
    IN_PROGRESS = "In Progress"
    DONE        = "Done"
    CANCELLED   = "Cancelled"

class Priority:
    URGENT      = "Urgent"
    HIGH        = "High"
    NORMAL      = "Normal"
    LOW         = "Low"

class ExpenseCategory:
    IMPORT       = "Import"
    REAL_ESTATE  = "Real Estate"
    OPERATIONS   = "Operations"
    LEGAL        = "Legal"
    OTHER        = "Other"

class ImportStatus:
    SAMPLE      = "Sample"
    APPROVAL    = "Approval"
    PRODUCTION  = "Production"
    QC          = "QC"
    SHIPPING    = "Shipping"
    DONE        = "Done"

class PaymentStatus:
    PENDING     = "Pending"
    PAID        = "Paid"
    OVERDUE     = "Overdue"


# ══════════════════════════════════════════════════
# כלל ה-9% — ולידציה
# ══════════════════════════════════════════════════

MAX_FUNDING_COST_PCT = 9.0  # חוק ברזל מספר 1

def validate_funding_cost(pct: float) -> tuple[bool, str]:
    """
    מחזיר (True, "") אם עלות המימון בגבולות.
    מחזיר (False, הודעת שגיאה) אם חורג.
    """
    if pct > MAX_FUNDING_COST_PCT:
        return False, (
            f"⚠️ הפרת חוק ברזל #1: עלות מימון {pct}% > {MAX_FUNDING_COST_PCT}%!\n"
            f"העסקה לא מאושרת אוטומטית. נדרש אישור מפורש של אליהו."
        )
    return True, ""


# ══════════════════════════════════════════════════
# Import Protocol — ולידציה (חוק ברזל #3)
# ══════════════════════════════════════════════════

REQUIRED_ADVANCE_PCT = 30
REQUIRED_BALANCE_PCT = 70

def validate_import_payment(advance_pct: float, balance_pct: float) -> tuple[bool, str]:
    """
    בודק שהתשלום עומד בפרוטוקול הייבוא: 30% מקדמה, 70% אחרי QC.
    """
    errors = []
    if advance_pct != REQUIRED_ADVANCE_PCT:
        errors.append(f"מקדמה {advance_pct}% ≠ {REQUIRED_ADVANCE_PCT}% הנדרש")
    if balance_pct != REQUIRED_BALANCE_PCT:
        errors.append(f"יתרה {balance_pct}% ≠ {REQUIRED_BALANCE_PCT}% הנדרש")
    if errors:
        return False, "🚨 חריגה מפרוטוקול ייבוא (חוק #3):\n" + "\n".join(errors)
    return True, ""
