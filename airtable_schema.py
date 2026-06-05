# airtable_schema.py — v2
# Source of Truth: Airtable Real Estate Project Tracker
# 17 טבלאות — שמות מדויקים כפי שקיימים ב-Airtable
# עדכון אחד כאן = משתנה בכל המערכת

# ══════════════════════════════════════════════════
# שמות טבלאות — מדויקים
# ══════════════════════════════════════════════════

class Tables:
    # פרויקטים ונכסים
    PROJECTS        = "Projects"
    UNITS           = "Units"
    UNIT_SALES      = "Unit Sales & Debt Distribution"
    # פיננסים
    LOANS           = "Loans"
    DEBT_MGMT       = "Company A - Debt Management"
    CASH_FLOW       = "Weekly Cash Flow Reports"
    EXPENSES        = "הוצאות (Expenses)"
    PAYMENTS        = "תשלומים (Payments)"
    # קשרים ועסקאות
    CONTACTS        = "אנשי קשר (Contacts)"
    DEALS           = "עסקאות (Deals)"
    LEADS           = "Leads"
    # משימות
    DEADLINES       = "משימות ודד ליינים"
    TASKS           = "משימות (Tasks)"
    # אחר
    PROFILE         = "Profile"
    LEARNINGS       = "למידות ותובנות"
    # זיכרון עסקי
    BUSINESS_MEMORY  = "Business Memory"   # אירועים אסטרטגיים — הזנה ידנית
    INTERACTION_LOG  = "Interaction Log"   # לוג אוטומטי — agent/system interactions
    # שמורים לשימוש פנימי
    IMPORTS         = "Imports"
    TENANTS         = "Tenants"


# ══════════════════════════════════════════════════
# שדות — מדויקים לכל טבלה
# ══════════════════════════════════════════════════

class ProjectFields:
    NAME            = "Project Name"
    LOCATION        = "Location"
    STATUS          = "Status"          # Planning|Active|Completed|On Hold|Cancelled|In Progress
    TOTAL_UNITS     = "Total Units"
    PROJECT_TYPE    = "Project Type"
    START_DATE      = "Start Date"
    END_DATE        = "End Date"
    TOTAL_COST      = "Total Cost"
    TOTAL_REVENUE   = "Total Revenue"
    MANAGER         = "Project Manager"
    LENDER          = "Primary Lender"
    NOTES           = "Notes"


class UnitFields:
    UNIT_NUMBER     = "Unit Number"
    PROJECT         = "Project"
    TYPE            = "Type"
    SIZE            = "Size (sqft)"
    PRICE           = "Price"
    STATUS          = "Status"          # Available|Reserved|Sold|Leased|Occupied
    FLOOR           = "Floor"
    BEDROOMS        = "Bedrooms"
    BATHROOMS       = "Bathrooms"
    FEATURES        = "Features"
    OWNER_TENANT    = "Owner/Tenant"
    AVAILABILITY    = "Availability Date"
    NOTES           = "Notes"
    SALE_PRICE_NIS  = "Sale Price (NIS)"


class LoanFields:
    NAME            = "Loan Name/ID"
    PROJECT         = "Project"
    LENDER          = "Lender"
    AMOUNT          = "Loan Amount"
    INTEREST_RATE   = "Interest Rate (%)"
    TERM_MONTHS     = "Term (months)"
    START_DATE      = "Start Date"
    END_DATE        = "End Date"
    PAYMENT_SCHED   = "Payment Schedule"
    OUTSTANDING     = "Outstanding Balance"
    NEXT_PAYMENT    = "Next Payment Due"
    STATUS          = "Payment Status"  # Current|Due|Overdue|Paid Off
    NOTES           = "Notes"


class DebtMgmtFields:
    INVOICE_NUM     = "Invoice Number"
    PAYMENT_DATE    = "Payment Date"
    GROSS_PAYMENT   = "Gross Payment (NIS)"
    REFUND_STATUS   = "Refund Status"   # Pending|Received


class CashFlowFields:
    ID              = "Id"
    WEEK_END        = "Week End Date"
    WEEK_START      = "Week Start Date"
    NOTES           = "Notes"


class ExpenseFields:
    NAME            = "שם ההוצאה"
    AMOUNT          = "סכום"
    CATEGORY        = "קטגוריה"         # שיווק|משרד|נסיעות|תפעול|אחר
    DATE            = "תאריך"


class PaymentFields:
    REF             = "אסמכתא"
    AMOUNT          = "סכום"
    DATE            = "תאריך"
    STATUS          = "סטטוס"           # התקבל|בתהליך|בוטל
    DEAL_LINK       = "מקושר לעסקאות"
    # backwards compat — crm.py uses these
    NAME            = "אסמכתא"
    DUE_DATE        = "תאריך"
    DEAL            = "מקושר לעסקאות"
    CONTACT         = "מקושר לאנשי קשר"
    NOTES           = "הערות"


class ContactFields:
    NAME            = "שם"
    COMPANY         = "חברה"
    EMAIL           = "אימייל"
    PHONE           = "טלפון"
    TYPE            = "Type"            # Client | Supplier | Partner | Lawyer | Accountant
    FOLLOWUP_DATE   = "תאריך פולו אפ"
    STATUS          = "סטטוס"           # חדש|בתהליכים|פולו-אפ|לא רלוונטי
    DEALS_LINK      = "עסקאות (Deals)"
    TASKS_LINK      = "משימות (Tasks)"


class DealFields:
    NAME            = "שם העסקה"
    AMOUNT          = "סכום"
    STAGE           = "שלב"             # הזדמנות|במשא ומתן|סגור-ניצחון|סגור-הפסד
    CLOSE_DATE      = "תאריך סגירה"
    CONTACTS_LINK   = "מקושר לאנשי קשר"
    TASKS_LINK      = "משימות (Tasks)"
    PAYMENTS_LINK   = "תשלומים (Payments)"
    # backwards compat — crm.py uses these
    STATUS          = "שלב"
    PRICE           = "סכום"
    ADDRESS         = "Address"
    FUNDING_COST    = "Funding Cost %"
    ROI             = "ROI %"
    RISK_LEVEL      = "Risk Level"
    CONTACT         = "מקושר לאנשי קשר"
    DEADLINE        = "תאריך סגירה"
    NOTES           = "Notes"


class TaskFields:
    """משימות (Tasks)"""
    NAME            = "כותרת המשימה"   # ← לא "Name"!
    DESCRIPTION     = "תיאור"
    DUE_DATE        = "תאריך יעד"
    STATUS          = "סטטוס"           # ממתין|בביצוע|בוצע
    CONTACTS_LINK   = "מקושר לאנשי קשר"
    DEALS_LINK      = "מקושר לעסקאות"


class DeadlineFields:
    """משימות ודד ליינים"""
    NAME            = "שם המשימה"
    STATUS          = "סטטוס"           # לא התחיל|בתהליך|הושלם
    DEADLINE        = "תאריך דדליין"
    RESPONSIBLE     = "אחראי"
    DESCRIPTION     = "תיאור המשימה"
    PRIORITY        = "עדיפות"          # גבוהה|בינונית|נמוכה
    UNIT_LINK       = "קישור לרשומת מכירה/יחידה"
    NOTES           = "הערות"


class LeadFields:
    NAME            = "Name"
    PHONE           = "phone"
    STATUS          = "status"
    SCORE           = "score ציון"      # ← לא "score"
    SUMMARY         = "summary"
    ANSWERS         = "answers"
    SOURCE          = "source"
    CHANNEL         = "channel"
    CREATED_AT      = "created_at"
    MEMORY_KEY      = "memory_key"
    TENANT_ID       = "tenant_id"
    DOMAIN          = "domain"


class BusinessMemoryFields:
    """Strategic/manual business event log — table: Tables.BUSINESS_MEMORY."""
    TITLE           = "Event Title"
    DESCRIPTION     = "Event Description"
    DATE            = "Event Date"
    IMPACT          = "Business Impact"
    EVENT_TYPE      = "Event Type"      # Milestone|Decision|Crisis|Announcement|Learning|Other
    LEARNINGS_LINK  = "Related Learnings & Insights"
    TAGS            = "Tags"            # multi-select list field


class InteractionLogFields:
    """Automated agent/system interaction log — table: Tables.INTERACTION_LOG.
    Maps to the existing Airtable 'Interaction Log' table.
    """
    TITLE            = "Interaction Subject"   # primary title (was: title)
    SUMMARY          = "Details"               # summary/details (was: summary)
    TIMESTAMP        = "Interaction Date"      # date+time (was: timestamp)
    PARTICIPANTS     = "Participants"           # people/entities involved (was: source)
    CHANNEL          = "Interaction Type"      # channel/type (was: channel)
    BUSINESS_MEMORY  = "Business Memory"       # linked Business Memory record (was: related_record_id)
    KEY_INSIGHTS     = "Key Insights"          # insights (was: sentiment)
    FOLLOWUP_ACTIONS = "Follow-up Actions"     # follow-up actions (no prior equivalent)


class LearningFields:
    TITLE           = "כותרת התובנה"
    DESCRIPTION     = "תיאור"
    DATE            = "תאריך יצירה"


# ══════════════════════════════════════════════════
# Enum values — ערכים חוקיים
# ══════════════════════════════════════════════════

class TaskStatus:
    PENDING         = "ממתין"
    IN_PROGRESS     = "בביצוע"
    DONE            = "בוצע"

class DeadlineStatus:
    NOT_STARTED     = "לא התחיל"
    IN_PROGRESS     = "בתהליך"
    DONE            = "הושלם"

class DeadlinePriority:
    HIGH            = "גבוהה"
    MEDIUM          = "בינונית"
    LOW             = "נמוכה"

class ContactStatus:
    NEW             = "חדש"
    IN_PROGRESS     = "בתהליכים"
    FOLLOWUP        = "פולו-אפ"
    NOT_RELEVANT    = "לא רלוונטי"
    # backwards compat — crm.py
    ACTIVE          = "בתהליכים"

class DealStage:
    OPPORTUNITY     = "הזדמנות"
    NEGOTIATION     = "במשא ומתן"
    CLOSED_WIN      = "סגור-ניצחון"
    CLOSED_LOSS     = "סגור-הפסד"

class PaymentStatus:
    RECEIVED        = "התקבל"
    IN_PROGRESS     = "בתהליך"
    CANCELLED       = "בוטל"
    # backwards compat — crm.py
    PENDING         = "בתהליך"
    PAID            = "התקבל"
    OVERDUE         = "בתהליך"

class ExpenseCategory:
    MARKETING       = "שיווק"
    OFFICE          = "משרד"
    TRAVEL          = "נסיעות"
    OPERATIONS      = "תפעול"
    OTHER           = "אחר"

class ProjectStatus:
    PLANNING        = "Planning"
    ACTIVE          = "Active"
    COMPLETED       = "Completed"
    ON_HOLD         = "On Hold"
    CANCELLED       = "Cancelled"
    IN_PROGRESS     = "In Progress"


# ══════════════════════════════════════════════════
# TMA Tables — create these in Airtable before using
# ══════════════════════════════════════════════════

class ProjectsHubFields:
    """
    Dynamic project registry for TMA O0 Projects Hub.
    Table name: ProjectsHub
    Must be created manually in Airtable.
    """
    NAME          = "Name"
    EMOJI         = "emoji"
    SLUG          = "slug"          # kebab-case identifier, used in API URLs
    MODE          = "mode"           # business | personal
    PROJECT_TYPE  = "project_type"  # real_estate|recruitment|import|saas|custom
    DOMAIN        = "domain"        # saas|real_estate|import|recruitment|finance|general
    KPI_FIELDS    = "kpi_fields"    # JSON string — which KPIs to show
    QUICK_ACTIONS = "quick_actions" # JSON string — per-project quick actions
    STATUS        = "status"        # active|paused|archived
    OWNER_IDS     = "owner_ids"     # comma-separated telegram user_ids
    TENANT_ID     = "tenant_id"


class AssetsFields:
    """
    Personal assets table for TMA Personal Mode (PN1/PN2).
    Table name: Assets (Personal)
    Must be created manually in Airtable.
    Owner + Co-Owner access only (allowed_domains includes 'personal').
    """
    NAME          = "שם הנכס"
    TYPE          = "סוג"           # דירה|קרקע|מסחרי|אחר
    COST          = "עלות רכישה"
    VALUE         = "שווי נוכחי"
    MORTGAGE      = "משכנתא"
    RENTAL_INCOME = "הכנסה חודשית"
    STATUS        = "סטטוס"         # מושכר|פנוי|בבנייה
    NOTES         = "הערות"
    DOCUMENTS     = "מסמכים"


class ApprovalsFields:
    """
    Approval queue for TMA O6 Approvals screen.
    Table name: Approvals
    Must be created manually in Airtable.
    Owner only.
    """
    ACTION         = "פעולה"
    REQUESTED_BY   = "מבוקש על ידי"
    REQUESTED_AT   = "בוקש בתאריך"
    RISK_LEVEL     = "רמת סיכון"       # גבוה|בינוני|נמוך
    CONTEXT_TYPE   = "סוג הקשר"       # lead|deal|asset|general
    CONTEXT_ID     = "מזהה הקשר"
    CONTEXT_DATA   = "נתוני הקשר"     # JSON string
    STATUS         = "סטטוס"           # ממתין|אושר|נדחה
    REJECTION_NOTE = "הערת דחייה"

class UnitStatus:
    AVAILABLE       = "Available"
    RESERVED        = "Reserved"
    SOLD            = "Sold"
    LEASED          = "Leased"
    OCCUPIED        = "Occupied"

class LoanPaymentStatus:
    CURRENT         = "Current"
    DUE             = "Due"
    OVERDUE         = "Overdue"
    PAID_OFF        = "Paid Off"


# ══════════════════════════════════════════════════
# FIELD_MAP — לvalidation ולתצוגה לבוט
# ══════════════════════════════════════════════════

FIELD_MAP = {
    Tables.TASKS: {
        "כותרת המשימה": "שם המשימה",
        "תיאור":         "תיאור חופשי",
        "תאריך יעד":     "YYYY-MM-DD",
        "סטטוס":         "ממתין | בביצוע | בוצע",
    },
    Tables.DEADLINES: {
        "שם המשימה":     "שם המשימה",
        "סטטוס":         "לא התחיל | בתהליך | הושלם",
        "תאריך דדליין":  "YYYY-MM-DD",
        "אחראי":         "שם האחראי",
        "עדיפות":        "גבוהה | בינונית | נמוכה",
    },
    Tables.CONTACTS: {
        "שם":            "שם מלא",
        "טלפון":         "0XX-XXXXXXX",
        "סטטוס":         "חדש | בתהליכים | פולו-אפ | לא רלוונטי",
    },
    Tables.DEALS: {
        "שם העסקה":      "שם",
        "סכום":          "מספר",
        "שלב":           "הזדמנות | במשא ומתן | סגור-ניצחון | סגור-הפסד",
    },
    Tables.PAYMENTS: {
        "אסמכתא":        "מזהה התשלום",
        "סכום":          "מספר",
        "סטטוס":         "התקבל | בתהליך | בוטל",
    },
    Tables.LEADS: {
        "Name":          "שם הליד",
        "phone":         "טלפון",
        "status":        "new | qualified | hot | cold",
        "domain":        "real_estate | import | general",
    },
}


def get_table_fields(table: str) -> str:
    """מחזיר רשימת שדות קריאה לבוט."""
    fields = FIELD_MAP.get(table)
    if not fields:
        return f"טבלת {table} — שדות לא ידועים"
    return "\n".join(f"• {k}: {v}" for k, v in fields.items())


# ══════════════════════════════════════════════════
# חוקי ברזל
# ══════════════════════════════════════════════════

MAX_FUNDING_COST_PCT  = 9.0
REQUIRED_ADVANCE_PCT  = 30
REQUIRED_BALANCE_PCT  = 70


def validate_funding_cost(pct: float) -> tuple[bool, str]:
    if pct > MAX_FUNDING_COST_PCT:
        return False, (
            f"⚠️ הפרת חוק ברזל #1: עלות מימון {pct}% > {MAX_FUNDING_COST_PCT}%!\n"
            "העסקה לא מאושרת אוטומטית."
        )
    return True, ""


def validate_import_payment(advance_pct: float, balance_pct: float) -> tuple[bool, str]:
    errors = []
    if advance_pct != REQUIRED_ADVANCE_PCT:
        errors.append(f"מקדמה {advance_pct}% ≠ {REQUIRED_ADVANCE_PCT}% הנדרש")
    if balance_pct != REQUIRED_BALANCE_PCT:
        errors.append(f"יתרה {balance_pct}% ≠ {REQUIRED_BALANCE_PCT}% הנדרש")
    if errors:
        return False, "🚨 חריגה מפרוטוקול ייבוא (חוק #3):\n" + "\n".join(errors)
    return True, ""


# ══════════════════════════════════════════════════
# Backwards compatibility — crm.py imports these
# ══════════════════════════════════════════════════

class ContactType:
    CLIENT      = "Client"
    SUPPLIER    = "Supplier"
    PARTNER     = "Partner"
    LAWYER      = "Lawyer"
    ACCOUNTANT  = "Accountant"

class DealStatus:
    PROSPECT       = "Prospect"
    DUE_DILIGENCE  = "Due Diligence"
    ACTIVE         = "Active"
    CLOSED         = "Closed"
    CANCELLED      = "Cancelled"

class RiskLevel:
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"
