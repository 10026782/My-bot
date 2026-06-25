# airtable_schema.py — v2
# Source of Truth: Airtable Real Estate Project Tracker
# 17 טבלאות — שמות מדויקים כפי שקיימים ב-Airtable
# עדכון אחד כאן = משתנה בכל המערכת

# ══════════════════════════════════════════════════
# שמות טבלאות — מדויקים
# ══════════════════════════════════════════════════

# ══════════════════════════════════════════════════
# FIELD ALIASES — מקור אמת יחיד
# variant (English/lowercase/legacy) → שם שדה קנוני ב-Airtable
# צרכנים: airtable_gateway.normalize_airtable_fields(),
#          airtable_tools._resolve_table()
# ══════════════════════════════════════════════════

FIELD_ALIASES: dict[str, dict[str, str]] = {
    "Leads": {
        "score":         "Score",
        "next_followup": "Next Followup",
    },
    "Coins_Log": {
        "note":  "Note",
        "Notes": "Note",
        "notes": "Note",
    },
}

class Tables:
    # פרויקטים ונכסים
    PROJECTS        = "Projects"
    UNITS           = "Units"
    UNIT_SALES      = "Unit Sales & Debt Distribution"
    # פיננסים
    LOANS           = "Loans"
    DEBT_MGMT       = "Company A - Debt Management"
    CASH_FLOW       = "Weekly Cash Flow Reports"
    EXPENSES        = "Expenses"
    PAYMENTS        = "Payments"
    # קשרים ועסקאות
    CONTACTS        = "אנשי קשר (Contacts)"
    DEALS           = "עסקאות (Deals)"
    LEADS           = "Leads"
    VENTURES        = "Ventures"           # Strategic Layer — הזדמנויות לפני שהן עסקאות
    # משימות
    DEADLINES       = "משימות ודד ליינים"
    TASKS           = "משימות (Tasks)"
    # אחר
    PROFILE         = "Profile"
    LEARNINGS       = "למידות ותובנות"
    # זיכרון עסקי
    BUSINESS_MEMORY  = "Business Memory"   # אירועים אסטרטגיים — הזנה ידנית
    INTERACTION_LOG  = "Interaction Log"   # לוג אוטומטי — agent/system interactions
    # Game / Gamification
    WORLDS          = "Worlds"
    QUESTS          = "Quests"
    COINS_LOG       = "Coins_Log"
    DAILY_CHECKIN   = "Daily_Checkin"
    # Roadmap
    ROADMAP_TASKS   = "Roadmap_Tasks"
    WEEKLY_GOALS    = "Weekly_Goals"
    BOSS_BATTLES    = "Boss_Battles"
    # System / Monitoring
    AI_USAGE_DAILY  = "AI_Usage_Daily"   # שורה יומית לכל source_type — 1 רשומה/יום
    EMERGENCY_WINDOW = "Emergency_Window"  # חריג מבוקר ל-High מהטלפון — ראה Approval_Policy_Spec.md
    # F16 — Media Layer
    MEDIA_FILES      = "Media Files"       # F16 — voice notes + file uploads (drive_url + metadata). Must be created manually in Airtable.
    # Decision Hub (Stage 0) — created manually in Airtable base app4bcgoX7t0HUVnm. See SPEC_Decision_Hub_Stage0.md.
    DECISIONS              = "Decisions"
    DECISION_EVENTS         = "Decision Events"
    DECISION_STAKEHOLDERS   = "Decision Stakeholders"
    DECISION_INBOX          = "Decision Inbox"
    # BUG-B — LeadSessions schema governance. ראה SPEC_BUG_B_LeadSessions_Schema.md.
    LEAD_SESSIONS           = "LeadSessions"


# ══════════════════════════════════════════════════
# TABLE ALIASES — מיפוי שמות קצרים (אנגלית) לשמות production
# צרכן: airtable_tools._resolve_table()
# ══════════════════════════════════════════════════

TABLE_ALIASES: dict[str, str] = {
    "Tasks":    Tables.TASKS,
    "Contacts": Tables.CONTACTS,
    "Deals":    Tables.DEALS,
    "Expenses": Tables.EXPENSES,
    "Payments": Tables.PAYMENTS,
}


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
    NAME            = "name"
    AMOUNT          = "amount"
    CATEGORY        = "category"
    DATE            = "date"
    STATUS          = "status"
    DOMAIN          = "domain"


class PaymentFields:
    REF             = "reference"
    AMOUNT          = "amount"
    DATE            = "date"
    STATUS          = "status"          # pending | received | overdue | cancelled
    DEAL_LINK       = "deal_id"
    DOMAIN          = "domain"
    # backwards compat — crm.py uses these
    NAME            = "reference"
    DUE_DATE        = "date"
    DEAL            = "deal_id"
    CONTACT         = "contact_id"
    NOTES           = "notes"


class ContactFields:
    NAME          = "שם"
    COMPANY       = "חברה"
    EMAIL         = "אימייל"
    PHONE         = "טלפון"
    TYPE          = "Type"            # Client | Supplier | Partner | Lawyer | Accountant
    FOLLOWUP_DATE = "תאריך פולו אפ"
    STATUS        = "סטטוס"           # חדש|בתהליכים|פולו-אפ|לא רלוונטי
    ROLE_CATEGORY = "Role Category"   # single select — ראה ContactRoleCategory
    SPECIALTY     = "Specialty"       # text — התמחות ספציפית (שמאי מקרקעין / רו"ח מיסוי / ...)
    DEALS_LINK    = "עסקאות (Deals)"
    TASKS_LINK    = "משימות (Tasks)"
    ORIGIN_LEAD   = "Origin Lead"     # linked record — fldGE1seCyCdWJGCO


class DealFields:
    NAME            = "שם העסקה"
    AMOUNT          = "סכום"
    STAGE           = "שלב"             # הזדמנות|במשא ומתן|סגור-ניצחון|סגור-הפסד
    CLOSE_DATE      = "תאריך סגירה"
    CONTACTS_LINK   = "מקושר לאנשי קשר"
    TASKS_LINK      = "משימות (Tasks)"
    PAYMENTS_LINK   = "תשלומים (Payments)"
    ORIGIN_LEAD     = "Origin Lead"     # linked record — fldoobGq4PS78C0Em
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


class VentureFields:
    """Ventures — Strategic Layer. הזדמנות לפני שהיא עסקה (pre-lead/pre-deal evaluation)."""
    NAME                  = "Venture Name"
    STAGE                 = "Stage"
    DOMAIN                = "Domain"
    CONVICTION            = "Conviction"
    ESTIMATED_POTENTIAL   = "Estimated Potential (NIS)"
    TARGET_DECISION_DATE  = "Target Decision Date"
    DECISION_LOG          = "Decision Log"
    NEXT_ACTION           = "Next Action"
    NOTES                 = "Notes"
    LINKED_CONTACTS       = "Linked Contacts"
    INTERACTION_LOG       = "Interaction Log"
    BUSINESS_MEMORY       = "Business Memory"
    OWNER                 = "Owner"
    CONVERTED_TO_DEAL     = "Converted To Deal"
    CREATED_AT            = "Created At"


class VentureStage:
    RESEARCH          = "Research"
    SUPPLIER_SOURCE   = "Supplier/Source Contact"
    DUE_DILIGENCE     = "Due Diligence"
    LEGAL_TAX_REVIEW  = "Legal/Tax Review"
    SMOKE_TEST        = "Smoke Test"
    GO                = "GO"
    NO_GO             = "NO-GO"
    CONVERTED         = "Converted"


class VentureDomain:
    REAL_ESTATE  = "Real Estate"
    IMPORT       = "Import"
    SAAS         = "SaaS"
    RECRUITMENT  = "Recruitment"
    GENERAL      = "General"


class VentureConviction:
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


class TaskFields:
    """משימות (Tasks)"""
    NAME            = "כותרת המשימה"   # ← לא "Name"!
    DESCRIPTION     = "תיאור"
    DUE_DATE        = "תאריך יעד"
    STATUS          = "סטטוס"           # ממתין|בביצוע|בוצע
    CONTACTS_LINK   = "מקושר לאנשי קשר"
    DEALS_LINK      = "מקושר לעסקאות"
    DOMAIN          = "Domain"          # domain copied from lead on create-from-lead
    OWNER           = "Owner"           # owner copied from lead on create-from-lead
    LEAD_LINK       = "Leads"           # linked record to Leads table (Airtable linked field name)


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
    SCORE           = "Score"        # raw numeric — Airtable field "Score" (capital S); written by lead_memory/lead_capture
    TIER            = "tier"         # singleSelect — writable. Values: קר/חם/לוהט/רותח (set by scoring logic)
    SUMMARY         = "summary"
    ANSWERS         = "answers"
    SOURCE          = "source"
    CHANNEL         = "channel"
    CREATED_AT      = "created_at"
    MEMORY_KEY      = "memory_key"
    TENANT_ID       = "tenant_id"
    DOMAIN          = "domain"
    CONVERTED_AT    = "converted_at"  # written by ad_attribution.mark_converted + lead_conversion
    OUTCOME         = "Business Outcome"  # singleSelect — see LeadOutcome below for exact option strings (some have a trailing space baked into the Airtable config)
    NEXT_FOLLOWUP   = "Next Followup" # ISO date of next scheduled followup
    OWNER           = "Owner"         # assigned owner / responsible person
    NEXT_STEP       = "Next Action"   # call_now|call_today|schedule_this_week|send_details|follow_up|waiting_response|create_deal|archive|none — NOTE: live Airtable options are actually "Call Back/Send Details/Follow Up/Waiting Response/Create Deal/Convert Contact/Schedule Meeting /Closed Won/Closed Lost" (verified via Airtable MCP 2026-06-17) — this field is not currently written from the TMA, so the mismatch is latent, not active
    EXTERNAL_ID     = "external_id"   # gmail:<msg_id> — idempotency key מדויק (F06)
    SENDER_ID       = "sender_id"     # email address / phone — dedup by sender (F06)


class LeadStatus:
    """Leads.status singleSelect — exact live Airtable option values (verified via Airtable MCP get_table_schema, 2026-06-17, field fldvTgONHx7D8JFw0)."""
    WAITING_CALL     = "waiting_call"
    ACTIVE           = "active"
    HIGH_CONFIDENCE  = "high_confidence"
    NEW              = "new"
    WAITING_RESPONSE = "waiting_response"
    ARCHIVED         = "archived"
    LOST             = "lost"
    DUPLICATE        = "duplicate"
    NOT_RELEVANT     = "not_relevant"
    DONE             = "done"

    ALL = {
        WAITING_CALL, ACTIVE, HIGH_CONFIDENCE, NEW, WAITING_RESPONSE,
        ARCHIVED, LOST, DUPLICATE, NOT_RELEVANT, DONE,
    }


class LeadOutcome:
    """Leads.'Business Outcome' singleSelect — canonical (clean) key -> exact live
    Airtable option string. Verified via Airtable MCP get_table_schema, 2026-06-17,
    field fldVa5wSmAqcKLi86. Airtable's typecast is OFF for this base, so a write
    that doesn't match an existing option byte-for-byte fails with 422
    INVALID_MULTIPLE_CHOICE_OPTIONS ("Insufficient permissions to create new
    select option") instead of creating it. Every option except ARCHIVED has a
    trailing space baked into the Airtable field config itself — do not "fix" it
    by stripping the space in code; that would just recreate this bug.
    """
    OPEN               = "open "
    NEEDS_FOLLOWUP      = "needs_followup "
    MEETING_SCHEDULED  = "meeting_scheduled "
    CONVERTED          = "converted "
    NOT_RELEVANT       = "not_relevant "
    LOST               = "lost "
    DUPLICATE          = "duplicate "
    ARCHIVED           = "archived"

    # canonical (frontend/internal, no trailing space) key -> exact Airtable value
    BY_KEY = {
        "open": OPEN,
        "needs_followup": NEEDS_FOLLOWUP,
        "meeting_scheduled": MEETING_SCHEDULED,
        "converted": CONVERTED,
        "not_relevant": NOT_RELEVANT,
        "lost": LOST,
        "duplicate": DUPLICATE,
        "archived": ARCHIVED,
    }


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


class ProfileFields:
    """Owner/business profile config — table: Tables.PROFILE.
    Single-row table; mirrors profile.py's actual read/write fields.
    """
    NAME            = "Name"          # always "main" — single profile row
    PROFILE_DATA    = "ProfileData"   # full profile dict, stored as JSON (Long text)


class WorldsFields:
    """Game Worlds table. Table name: Tables.WORLDS."""
    NAME               = "Name"
    NUMBER             = "Number"
    STATUS             = "Status"             # Active | Completed | Locked
    BOSS               = "Boss"
    PRIZE              = "Prize"
    TOTAL_COINS_TARGET = "Total_Coins_Target"
    COINS_EARNED       = "Coins_Earned"      # legacy static field — no longer the source of truth, see tma_api._get_active_world_dict
    START_DATE         = "Start_Date"
    END_DATE           = "End_Date"
    NOTES              = "Notes"
    QUESTS             = "Quests"          # linked records → Quests


class QuestsFields:
    """Game Quests table. Table name: Tables.QUESTS."""
    NAME       = "Name"
    WORLD      = "World"          # linked record → Worlds
    STATUS     = "Status"         # Todo | In Progress | Done | Skipped
    COINS      = "Coins"
    WEEK_START = "Week_Start"
    IMPACT     = "Impact"         # checkbox — high-impact quest
    DONE_BY    = "Done_By"
    NOTES      = "Notes"


class CoinsLogFields:
    """Game Coins_Log table. Table name: Tables.COINS_LOG."""
    ACTION        = "Action"
    COINS         = "Coins"
    DATE          = "Date"
    QUEST         = "Quest"          # linked record → Quests
    NOTE          = "Note"


class DailyCheckinFields:
    """BOSS Daily Check-in table. One record per owner per day. Table name: Tables.DAILY_CHECKIN."""
    DATE        = "Date"          # ISO YYYY-MM-DD — natural key, one record per day
    OWNER       = "Owner"
    TASKS_JSON  = "Tasks_JSON"     # serialized array of today's freeform tasks
    TOTAL_XP    = "Total_XP"
    UPDATED_AT  = "Updated_At"
    UPDATED_BY  = "Updated_By"


class QuestStatus:
    TODO        = "Todo"
    IN_PROGRESS = "In Progress"
    DONE        = "Done"
    SKIPPED     = "Skipped"


class WorldStatus:
    ACTIVE    = "Active"
    COMPLETED = "Completed"
    LOCKED    = "Locked"


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
    PENDING         = "pending"
    RECEIVED        = "received"
    OVERDUE         = "overdue"
    CANCELLED       = "cancelled"
    # backwards compat — crm.py
    IN_PROGRESS     = "pending"
    PAID            = "received"

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


class MediaFileFields:
    """
    F16 — Media Layer: voice notes + file uploads.
    Table name: Tables.MEDIA_FILES ("Media Files").
    Must be created manually in Airtable before FEATURE_VOICE_NOTES/FEATURE_MEDIA_UPLOAD are enabled.
    Distinct from the existing "Assets" table (real estate) — no field/name overlap.
    Drive is the storage primary; this table holds metadata + drive_url only, never the file bytes.
    """
    NAME                  = "Name"
    FILE_TYPE             = "File Type"          # single select: image/document/audio/video
    MIME_TYPE             = "Mime Type"
    DRIVE_URL             = "Drive URL"
    DRIVE_FILE_ID         = "Drive File ID"
    DOMAIN                = "Domain"
    SOURCE                = "Source"             # telegram/tma/whatsapp
    RAW_TRANSCRIPT        = "Raw Transcript"      # long text — גולמי, לא לשנות
    NORMALIZED_TRANSCRIPT = "Transcript"          # long text — אחרי ניקוי ניקוד
    SIZE_BYTES            = "Size Bytes"
    CREATED_BY            = "Created By"
    TELEGRAM_FILE_ID      = "Telegram File ID"
    LINKED_LEAD           = "Linked Lead"         # multipleRecordLinks → Leads, always written as [rec_id]


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

class ApprovalStatus:
    PENDING    = "ממתין"
    PROCESSING = "מעבד"   # transient claim state — execution in progress
    APPROVED   = "אושר"
    REJECTED   = "נדחה"
    FAILED     = "נכשל"   # execution was attempted but failed


class EmergencyWindowFields:
    """
    Controlled exception mechanism — Owner-only. Allows High-risk actions from
    mobile for a bounded period (24/48/72h) with per-action OTP. Never raises
    the ceiling to Critical. Table name: Tables.EMERGENCY_WINDOW.
    See Approval_Policy_Spec.md.
    """
    WINDOW_ID         = "Window ID"
    ACTIVATED_BY      = "Activated By"
    ACTIVATED_AT      = "Activated At"
    EXPIRES_AT        = "Expires At"
    REASON            = "Reason"
    STATUS            = "Status"
    MAX_RISK_ALLOWED  = "Max Risk Allowed"
    ACTIONS_APPROVED  = "Actions Approved"
    REVOKED_AT        = "Revoked At"


class EmergencyWindowStatus:
    ACTIVE   = "Active"
    EXPIRED  = "Expired"
    REVOKED  = "Revoked"


class EmergencyWindowMaxRisk:
    # קבוע — לעולם לא Critical, גם לא ב-Emergency Window.
    HIGH = "High"

# BUG-B — LeadSessions schema governance. ראה SPEC_BUG_B_LeadSessions_Schema.md.
class LeadSessionsFields:
    SENDER        = "sender"
    DOMAIN        = "domain"
    CHANNEL       = "channel"
    STEP          = "step"
    ANSWERS       = "answers"
    DONE          = "done"
    DROP_OFF_STEP = "drop_off_step"
    UPDATED_AT    = "updated_at"
    CREATED_AT    = "created_at"
    SCORE         = "score"
    TIER          = "tier"
    # future: LAST_UPLOADED_FILE = "last_uploaded_file" (אחרי שנוצרת עמודה ב-Airtable)

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
        "Score":         "ציון מספרי",
        "tier":          "HOT | WARM | COLD",
        "summary":       "תקציר",
        "answers":       "תשובות/פרטים",
        "source":        "מקור",
        "channel":       "ערוץ",
        "created_at":    "תאריך יצירה",
        "memory_key":    "מפתח זיכרון",
        "tenant_id":     "מזהה tenant",
        "domain":        "real_estate | import | recruitment | saas | finance | general",
        "converted_at":  "תאריך המרה",
        "Business Outcome": "open | needs_followup | meeting_scheduled | converted | not_relevant | lost | duplicate | archived",
        "Next Followup": "תאריך פולואפ הבא",
        "Owner":         "אחראי",
        "Next Action":   "call_now | call_today | schedule_this_week | send_details | follow_up | waiting_response | create_deal | archive | none",
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


class ContactRoleCategory:
    """Single select — שדה `Role Category` ב-Contacts (Strategic Layer).
    קטגוריות עסקיות כלליות; פירוט ספציפי → ContactFields.SPECIALTY (text).
    """
    LEAD     = "lead"      # לקוח / מתעניין
    BROKER   = "broker"    # מביא הזדמנות / מתווך
    EXPERT   = "expert"    # איש מקצוע בודק (עו"ד / רו"ח / שמאי / יועץ)
    SUPPLIER = "supplier"  # ספק / יבואן / נותן שירות
    OPERATOR = "operator"  # מבצע בפועל (קבלן / מתקין / צוות)
    PARTNER  = "partner"   # שותף עסקי
    INVESTOR = "investor"  # משקיע
    CLIENT   = "client"    # לקוח קיים
    OTHER    = "other"     # אחר


class DealStatus:
    # ── שלבי הערכה (לפני החלטה) — Strategic Layer ──────────────────
    IDEA             = "Idea"               # דיל בתחילת חיים
    FEASIBILITY      = "Feasibility Check"  # מספרים, שמאות, מתחרים, ביקוש
    LEGAL_REVIEW     = "Legal/Tax Review"   # עו"ד/רו"ח בודקים
    PENDING_DECISION = "Pending Decision"   # כל המידע נאסף, מחכה לאישור
    # ── שלבי ביצוע (קיימים — לא נגענו) ─────────────────────────────
    PROSPECT         = "Prospect"
    DUE_DILIGENCE    = "Due Diligence"
    ACTIVE           = "Active"
    CLOSED           = "Closed"
    CANCELLED        = "Cancelled"
    # ── נדחה — שונה מ-Cancelled: נדחה לפני שהיה Active כלל ─────────
    REJECTED         = "Rejected"           # לניתוח יחס הזדמנויות→ביצוע

class RiskLevel:
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


# ══════════════════════════════════════════════════
# Roadmap / Boss-Game Tables
# ══════════════════════════════════════════════════

class RoadmapTaskFields:
    TASK             = "Task"
    WORLD            = "World"           # Link → Worlds
    QUEST            = "Quest"           # Link → Quests
    OWNER            = "Owner"           # אליהו | קלוד קוד | אורי | אהרן | אח
    PRIORITY         = "Priority"        # P0 | P1 | P2 | P3
    STATUS           = "Status"          # Todo | In Progress | Done | Blocked
    DUE_DATE         = "Due_Date"
    ESTIMATED_HOURS  = "Estimated_Hours"
    COINS            = "Coins"
    BLOCKER          = "Blocker"         # Checkbox
    NOTES            = "Notes"

class RoadmapTaskStatus:
    TODO        = "Todo"
    IN_PROGRESS = "In Progress"
    DONE        = "Done"
    BLOCKED     = "Blocked"

class RoadmapTaskPriority:
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class WeeklyGoalsFields:
    GOAL        = "Goal"
    WORLD       = "World"        # Link → Worlds
    TARGET_DATE = "Target_Date"
    STATUS      = "Status"       # Todo | Done | Missed


class BossBattlesFields:
    WEEK         = "Week"
    WEEK_START   = "Week_Start"
    QUESTION     = "Question"
    ANSWER       = "Answer"
    STATUS       = "Status"       # Boss Defeated | Boss Won


# ══════════════════════════════════════════════════
# Decision Hub (Stage 0) — verified live via Airtable MCP get_table_schema,
# base app4bcgoX7t0HUVnm, 2026-06-24. See SPEC_Decision_Hub_Stage0.md.
# ══════════════════════════════════════════════════

class DecisionFields:
    """Table: Tables.DECISIONS."""
    TITLE               = "Title"
    DOMAIN               = "Domain"             # singleSelect — see DecisionDomain
    ESTIMATED_EXPOSURE   = "Estimated Exposure"  # currency
    EXPOSURE_TYPE        = "Exposure Type"       # singleSelect — see DecisionExposureType
    STATUS               = "Status"              # singleSelect — see DecisionStatus
    READINESS            = "Readiness"           # singleSelect — see DecisionReadiness; Stage 3 fills, default empty
    URGENCY              = "Urgency"              # singleSelect — see DecisionUrgency
    CURRENT_DRAFT        = "Current Draft #"      # number (integer)
    RISK_IF_YES          = "Risk If Yes"          # long text
    RISK_IF_NO           = "Risk If No"           # long text
    MISSING_INFO         = "Missing Info"         # long text
    FINAL_DECISION       = "Final Decision"       # long text
    LESSONS_LEARNED      = "Lessons Learned"      # long text
    LINKED_CONTACTS      = "Linked Contacts"      # Link → Tables.CONTACTS
    LINKED_DEAL          = "Linked Deal"          # Link → Tables.DEALS
    LINKED_TASKS         = "Linked Tasks"         # Link → Tables.TASKS
    LINKED_MEMORY        = "Linked Memory"        # Link → Tables.BUSINESS_MEMORY
    TENANT_ID            = "tenant_id"
    CREATED              = "Created"              # createdTime
    LAST_UPDATED         = "Last Updated"         # lastModifiedTime
    # NOTE: live schema has a duplicate-name artifact — two distinct link fields
    # both named "Decision Events" (fldZ4cKSmuvx8vBJY, fldNYIC3D6FTfaOFW). Not
    # referenced by field name here since Airtable would reject an ambiguous
    # write target; leave both alone until Eliyahu resolves the duplication.


class DecisionDomain:
    REAL_ESTATE  = "נדל\"ן"
    IMPORT       = "ייבוא"
    RECRUITMENT  = "גיוס"
    PARTNERSHIP  = "שותפות"
    GENERAL      = "כללי"


class DecisionExposureType:
    FINANCIAL  = "כספי"
    LEGAL      = "משפטי"
    OPERATIONAL = "תפעולי"
    REPUTATION = "מוניטין"


class DecisionStatus:
    OPEN           = "Open"
    PENDING_INPUT  = "Pending Input"
    DECIDED_YES    = "Decided Yes"
    DECIDED_NO     = "Decided No"
    CANCELLED      = "Cancelled"


class DecisionReadiness:
    READY      = "READY"
    NOT_READY  = "NOT_READY"


class DecisionUrgency:
    NONE       = "אין"
    WEEK       = "שבוע"
    H48        = "48 שעות"
    NOW        = "עכשיו"


class DecisionEventFields:
    """Table: Tables.DECISION_EVENTS — timeline + evidence."""
    DECISION             = "Decision"             # Link → Tables.DECISIONS
    EVENT_DATE           = "Event Date"           # dateTime
    EVENT_TYPE           = "Event Type"           # singleSelect — see DecisionEventType
    CHANNEL              = "Channel"              # singleSelect — see DecisionEventChannel
    STAKEHOLDER          = "Stakeholder"           # Link → Tables.CONTACTS
    RAW_CONTENT          = "Raw Content"           # long text — raw evidence, never deleted
    ATTACHMENT           = "Attachment"
    TRUST_LEVEL          = "Trust Level"           # singleSelect — see DecisionTrustLevel; Stage 1 fills, default empty
    SOURCE_RELIABILITY   = "Source Reliability"    # singleSelect — see DecisionSourceReliability
    CONFIDENCE           = "Confidence"            # number 0-100
    TAGS                 = "Tags"                  # multipleSelects — see DecisionEventTag
    DELTA_TYPE           = "Delta Type"             # singleSelect — see DecisionDeltaType
    STATUS               = "Status"                 # singleSelect — see DecisionEventStatus; default Active
    SUPERSEDES           = "Supersedes"             # self-link — NOT "Supersedes Decision (ignore)" (legacy setup field, do not use)
    AI_SUMMARY           = "AI Summary"             # long text
    TENANT_ID            = "tenant_id"


class DecisionEventType:
    MESSAGE   = "הודעה"
    DOCUMENT  = "מסמך"
    MEETING   = "פגישה"
    DRAFT     = "טיוטה"
    PRESSURE  = "לחץ"
    POSITION  = "עמדה"
    DECISION  = "החלטה"


class DecisionEventChannel:
    WHATSAPP  = "וואטסאפ"
    TELEGRAM  = "טלגרם"
    EMAIL     = "אימייל"
    DOCUMENT  = "מסמך"
    VOICE     = "קולי"
    MANUAL    = "ידני"


class DecisionTrustLevel:
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class DecisionSourceReliability:
    CONTRACT   = "חוזה"
    LAWYER     = "עו\"ד"
    ACCOUNTANT = "רו\"ח"
    CLIENT     = "לקוח"
    PARTNER    = "שותף"
    RUMOR      = "שמועה"


class DecisionEventTag:
    PARTIAL_TRANSCRIPT = "תמלול_חלקי"
    VAGUE              = "עמום"
    CONFLICT           = "קונפליקט"
    PRESSURE_ONLY       = "לחץ_בלבד"
    MISSING_CONTEXT     = "חסר_הקשר"


class DecisionDeltaType:
    FACT          = "עובדה"
    DOCUMENT      = "מסמך"
    POSITION_SHIFT = "שינוי_עמדה"
    PRESSURE      = "לחץ"
    NO_CHANGE     = "ללא_שינוי"


class DecisionEventStatus:
    LOGGED      = "Logged"
    ACTIVE      = "Active"
    SUPERSEDED  = "Superseded"


class DecisionStakeholderFields:
    """Table: Tables.DECISION_STAKEHOLDERS."""
    DECISION          = "Decision"           # Link → Tables.DECISIONS
    CONTACT           = "Contact"            # Link → Tables.CONTACTS
    ROLE              = "Role"               # singleSelect — see DecisionStakeholderRole
    POSITION          = "Position"           # singleSelect — see DecisionStakeholderPosition
    POSITION_DETAILS  = "Position Details"   # long text
    LAST_UPDATED      = "Last Updated"       # lastModifiedTime
    TENANT_ID         = "tenant_id"


class DecisionStakeholderRole:
    DECIDER     = "מחליט"
    ADVISOR     = "מייעץ"
    AFFECTED    = "מושפע"
    OPPONENT    = "מתנגד"
    PENDING     = "ממתין"


class DecisionStakeholderPosition:
    FOR        = "בעד"
    AGAINST    = "נגד"
    PENDING    = "ממתין"
    UNKNOWN    = "לא ידוע"


class DecisionInboxFields:
    """Table: Tables.DECISION_INBOX — entry door for forwarded/raw input."""
    RAW_INPUT           = "Raw Input"           # long text — exactly as received
    CHANNEL             = "Channel"             # singleSelect — see DecisionInboxChannel (NOTE: live options are English, unlike Decision Events' Hebrew Channel field)
    RECEIVED            = "Received"            # dateTime
    ATTACHMENT          = "Attachment"          # multipleAttachments — write as [{"url": ..., "filename": ...}], verified via Airtable MCP
    SUGGESTED_DECISION  = "Suggested Decision"  # Link → Tables.DECISIONS
    MATCH_CONFIDENCE    = "Match Confidence"    # number 0-100
    STATUS              = "Status"              # singleSelect — see DecisionInboxStatus; default Pending
    LINKED_EVENT        = "Linked Event"        # Link → Tables.DECISION_EVENTS
    TENANT_ID           = "tenant_id"


class DecisionInboxChannel:
    """Live options verified via Airtable MCP — English, unlike Decision Events.Channel (Hebrew)."""
    TELEGRAM  = "Telegram"
    WHATSAPP  = "WhatsApp"
    EMAIL     = "Email"
    DOCUMENT  = "Document"
    VOICE     = "Voice"
    MANUAL    = "Manual"


class DecisionInboxStatus:
    PENDING   = "Pending"
    LINKED    = "Linked"
    REJECTED  = "Rejected"
    COINS_EARNED = "Coins_Earned"
