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
    LEARNINGS       = "למידות ותובנות (Learnings & Insights)"  # שם חי מאומת ב-Airtable MCP 2026-06-24 — לא "למידות ותובנות" בלבד
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
    # F23 — BOSS Marketing Bridge (M1). קיים חי בבסיס Airtable app4bcgoX7t0HUVnm
    # (tbljxJMyeSlF4VC42 / tblLWwYRntaZtpVgW / tblUhWCdS8s4H1aS7). אין ליצור מחדש.
    # ראה marketing_gateway.py / marketing_brief_composer.py / cmd_marketing.py.
    MARKETING_DEMAND       = "Marketing Demand"
    MARKETING_CREATIVES    = "Marketing Creatives"
    MARKETING_PUBLICATIONS = "Marketing Publications"
    # Decision Hub (Stage 0) — created manually in Airtable base app4bcgoX7t0HUVnm. See SPEC_Decision_Hub_Stage0.md.
    DECISIONS              = "Decisions"
    DECISION_EVENTS         = "Decision Events"
    DECISION_STAKEHOLDERS   = "Decision Stakeholders"
    DECISION_INBOX          = "Decision Inbox"
    # BUG-B — LeadSessions schema governance. ראה SPEC_BUG_B_LeadSessions_Schema.md.
    # ⚠️ DEPRECATED (C58, SPEC_C58_Universal_Sessions.md): טבלה זו מעולם לא נוצרה ב-Airtable
    # בפועל (403/לא קיימת) — session_store.py הוחלף לכתוב ל-Tables.SESSIONS. לא נמחק כאן
    # כדי לא לשבור קוד היסטורי/דוחות שמתייחסים לקבוע הזה; אין שימוש חי בו.
    LEAD_SESSIONS           = "LeadSessions"
    # C58 — Universal Sessions. טבלה קיימת ב-Airtable (tblHLfE24lTkVUhz0), משותפת לכל
    # context_type (lead/decision/task/...), ראה SPEC_C58_Universal_Sessions.md.
    SESSIONS                 = "Sessions"
    # Growth — קיימת חיה, עדיין לא מחוברת לאף מודול קוד (מאומת 2026-06-24)
    TRAFFIC_SOURCES  = "TRAFFIC_SOURCES"   # BOSS Growth P0 — attribution במפלס ערוץ (לא wall/synagogue-level)
    # Lead Events — אירועים על ליד קיים (topic חדש, עדכון domain, interest, note)
    # יש ליצור ידנית ב-Airtable לפני הפעלה. ראה LeadEventFields.
    LEAD_EVENTS      = "Lead Events"
    # PR3A — Airtable schema snapshot archive. Must be created manually in Airtable
    # before FEATURE_AIRTABLE_SCHEMA_SNAPSHOT can be turned on. ראה SchemaSnapshotFields.
    SCHEMA_SNAPSHOTS = "System Schema Snapshots"
    # PR-0C Phase 4A — canonical durable persistence for core/action_gateway.py's
    # ActionContract/ExecutionLedger (Stage B). One state owner: this table is
    # the source of truth; "Approvals" (below, TMA) is a display-safe projection
    # of it, never an independent source of approval truth. Created in the live
    # base (app4bcgoX7t0HUVnm) via Airtable MCP, 12/07/2026. ראה ActionContractsFields.
    ACTION_CONTRACTS = "ActionContracts"
    EXTERNAL_EXECUTION_JOBS = "External Execution Jobs"
    # PATCH 3B — durable Emergency Stop persistence (Option B: dedicated table,
    # not a reuse of Sessions). Must be created manually in Airtable before use;
    # pre-seed with one record per known EMERGENCY_STOP_* flag name (see
    # feature_flags.py). ראה core/emergency_stop.py / adapters/airtable_emergency_stop_store.py.
    EMERGENCY_STOP_FLAGS = "Emergency Stop Flags"


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
    FUNDING_COST    = "Funding Cost"
    ROI             = "Roi"
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
    OWNER           = "Owner"           # multipleRecordLinks -> Tables.PROFILE (NOT plain text; verified via Airtable MCP 2026-08-19). Read/write as a list of Profile record IDs -- see tma_api._resolve_profile_record_id.
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
    TIER            = "tier"         # singleSelect — real, writable field (verified via Airtable MCP, not a formula/read-only). Values: קר/חם/לוהט/רותח/ליד חדש. Currently 0/39 live records populated and no code path writes it intentionally — treat as dead-in-practice, not canonical for reasoning, pending an owner decision to remove it (see docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md §7C and the Canonical Leads Schema v1 proposal).
    NOTES           = "notes"        # multilineText — written only by voice_adapter.py (IVR), read by core/leads_reasoning_projection.py
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
    OWNER           = "Owner"         # multipleRecordLinks -> Tables.PROFILE (NOT plain text; verified via Airtable MCP 2026-08-19). Never written from the TMA today (see tma_api.create_lead_task).
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
    Airtable option string.

    Canonical Leads Schema v1 (Track B, 21/08/2026): the live Airtable
    options were renamed to this trimmed form on 22/08/2026 (the field
    originally carried a baked-in trailing space on 7 of its 8 choices).
    Read paths that compare a raw fetched value against one of these
    constants still .strip() first (core/adapters/leads_adapter.py's
    _normalise_business_outcome, audience_intelligence.py) — kept
    permanently as cheap, ongoing hardening against future drift, not as
    migration scaffolding (owner decision, 21/08/2026). The temporary
    write-side fallback (LEGACY_VALUE_FOR / option_fallback) that bridged
    writes during the migration window was removed once the rename landed
    and the fallback log went quiet (Track B step 5).

    Originally verified via Airtable MCP get_table_shape, 2026-06-17, field
    fldVa5wSmAqcKLi86. Airtable's typecast is OFF for this base, so a write
    that doesn't match an existing option byte-for-byte fails with 422
    INVALID_MULTIPLE_CHOICE_OPTIONS ("Insufficient permissions to create new
    select option") instead of creating it.
    """
    OPEN               = "open"
    NEEDS_FOLLOWUP     = "needs_followup"
    MEETING_SCHEDULED  = "meeting_scheduled"
    CONVERTED          = "converted"
    NOT_RELEVANT       = "not_relevant"
    LOST               = "lost"
    DUPLICATE          = "duplicate"
    ARCHIVED           = "archived"

    # canonical (frontend/internal) key -> exact Airtable value (target, trimmed form)
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
    DOMAIN          = "Domain"          # canonical business domain; adapters handle legacy options


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
    """Team/people roster — table: Tables.PROFILE ("Profile").
    NOT a single-row config table (that was a stale assumption -- corrected
    2026-08-19). Live table has one row per team member (owner/partner/
    manager/marketing/...), linked from Tasks.Owner and Leads.Owner
    (multipleRecordLinks) plus Contacts/Deals/Payments/etc. Each row's NAME
    is a person's first name (e.g. "Eliyahu", capitalized), used to resolve
    an identity.user_id to a Profile record ID -- see
    tma_api._resolve_profile_record_id (case-insensitive match).
    profile.py's separate "single-row business config" table concept
    (ProfileData field, "always main" row) does not exist on the live base
    at all -- that code remains unwired (see CLAUDE.md), do not confuse it
    with this table.
    """
    NAME            = "name"          # person's display name, e.g. "Eliyahu". Live field is lowercase.
    ROLE            = "Role"          # singleSelect: Owner|Manager|Sales|Marketing|Operations|Finance|Sistem|Partner


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
    Real-estate assets table. Table name: "Assets" (already exists live).
    NOTE: this is NOT the originally-planned TMA Personal Mode (PN1/PN2) Hebrew
    schema described in earlier docs/comments — the live table was built for
    real-estate asset tracking with English fields. Verified via Airtable MCP
    2026-06-24; the old Hebrew field set (שם הנכס/סוג/עלות רכישה/...) does not
    exist on this table at all.
    """
    NAME              = "Name"
    ASSET_TYPE        = "Asset Type"
    CURRENT_VALUE     = "Current Value"
    MONTHLY_INCOME    = "Monthly Income"
    MORTGAGE_BALANCE  = "Mortgage Balance"
    STATUS            = "Status"
    NOTES             = "Notes"
    RELATED_PROJECT   = "Related Project"   # linked record → Projects
    ASSET_POTENTIAL   = "Asset Potential"   # AI text field
    ASSET_RISKS       = "Asset Risks"       # AI text field
    EQUITY            = "Equity"            # formula
    OWNERSHIP_PCT     = "Ownership %"
    MY_EQUITY         = "My Equity"         # formula
    OWNER             = "Owner"             # linked record
    DOMAIN            = "Domain"
    NEXT_STEP         = "Next Step"
    NEXT_STEP_OWNER   = "Next Step Owner"


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
    LOGICAL_MEDIA_KEY     = "Logical Media Key"  # provider-neutral durable identity
    PERSISTENCE_STATE     = "Persistence State"  # see MediaPersistenceState
    LAST_ERROR_CODE       = "Last Error Code"    # populated only after failed/uncertain persistence
    DOMAIN                = "Domain"
    SOURCE                = "Source"             # telegram/tma/whatsapp
    RAW_TRANSCRIPT        = "Raw Transcript"      # long text — גולמי, לא לשנות
    NORMALIZED_TRANSCRIPT = "Transcript"          # long text — אחרי ניקוי ניקוד
    SIZE_BYTES            = "Size Bytes"
    CREATED_BY            = "Created By"
    TELEGRAM_FILE_ID      = "Telegram File ID"
    LINKED_LEAD           = "Linked Lead"         # multipleRecordLinks → Leads, always written as [rec_id]
    LINKED_DEMAND         = "Linked Demand"       # שדה חי קיים M1, multipleRecordLinks → Marketing Demand
    LINKED_CREATIVE       = "Linked Creative"     # שדה חי קיים M1, multipleRecordLinks → Marketing Creatives
    APPROVAL_STATUS       = "Approval Status"     # שדה חי קיים M1, singleSelect: Pending|Approved|Rejected


class MediaPersistenceState:
    """Exact lifecycle values for the additive Media Files persistence field.

    These constants are foundation-only in PR1. No runtime media flow reads or
    writes them until the durable lookup/reconciliation PRs land.
    """

    PENDING         = "PENDING"         # event accepted; upload not completed
    DRIVE_UPLOADED  = "DRIVE_UPLOADED"  # Drive object confirmed; asset persistence incomplete
    ASSET_PERSISTED = "ASSET_PERSISTED" # Media Files record + Drive ID durably confirmed
    PARTIAL         = "PARTIAL"         # persistence failed or outcome uncertain after Drive success
    FAILED          = "FAILED"          # terminal/non-completed state according to policy

    ALL = (PENDING, DRIVE_UPLOADED, ASSET_PERSISTED, PARTIAL, FAILED)


class MarketingDemandFields:
    """
    F23 — BOSS Marketing Bridge (M1). טבלה: Tables.MARKETING_DEMAND ("Marketing Demand").
    Domain הוא תחום העסקי הקנוני (ראה domain_utils.py / identity.Domain) — אין להוסיף
    כאן ערכים אד-הוק. Demand Type הוא enum נפרד, בבעלות Marketing, שבוחר איזה
    DomainProfile לטעון (marketing_domain_profiles.py) — נפרד מ-Domain בכוונה.
    """
    NAME              = "Demand Title"
    DOMAIN            = "Domain"                 # תחום עסקי קנוני (domain_utils.py)
    DEMAND_TYPE       = "Demand Type"            # בורר פרופיל, לא תחום: recruitment|furniture_import|fiber_equipment|real_estate_listing|service
    TARGET_AUDIENCE   = "Target Audience"
    LOCATION          = "Location"
    GOAL              = "Goal"
    CONSTRAINTS       = "Constraints"
    CURRENT_STAGE     = "Current Stage"          # intake|brief_composed|ideas_generated|selected|handoff_sent|published|closed — ראה MarketingDemandStage
    NEXT_ACTION       = "Next Action"
    STATUS            = "Status"                 # Active|Paused|Done|Cancelled
    CREATIVES         = "Marketing Creatives"    # שדה קישור הפוך שנוצר אוטומטית (Marketing Creatives.Linked Demand)
    PUBLICATIONS      = "Marketing Publications" # שדה קישור הפוך שנוצר אוטומטית (Marketing Publications.Demand)
    MEDIA_FILES       = "Media Files"            # שדה קישור הפוך שנוצר אוטומטית (Media Files.Linked Demand)


class MarketingDemandStage:
    INTAKE           = "intake"
    BRIEF_COMPOSED   = "brief_composed"
    IDEAS_GENERATED  = "ideas_generated"
    SELECTED         = "selected"
    HANDOFF_SENT     = "handoff_sent"
    PUBLISHED        = "published"
    CLOSED           = "closed"


class MarketingCreativesFields:
    """F23 — BOSS Marketing Bridge (M1). טבלה: Tables.MARKETING_CREATIVES ("Marketing Creatives")."""
    NAME              = "Title"
    LINKED_DEMAND     = "Linked Demand"    # multipleRecordLinks → Marketing Demand
    IDEA_1            = "Idea 1"
    IDEA_2            = "Idea 2"
    IDEA_3            = "Idea 3"
    REVIEWER_NOTES    = "Reviewer Notes"
    SELECTED_IDEA     = "Selected Idea"    # singleSelect: Idea 1|Idea 2|Idea 3|None
    SELECTION_STATUS  = "Selection Status" # singleSelect: Pending Review|Selected|Rejected All
    BRIEF_USED        = "Brief Used"
    PRODUCTION_HANDOFF = "Production Handoff"
    SCRIPT_DRAFT      = "Script Draft"
    APPROVED_SCRIPT    = "Approved Script"
    SCRIPT_SHA256      = "Script SHA256"
    MEDIA_FILES       = "Media Files"      # שדה קישור הפוך שנוצר אוטומטית (Media Files.Linked Creative)


class MarketingPublicationFields:
    """F23 — BOSS Marketing Bridge (M1). טבלה: Tables.MARKETING_PUBLICATIONS ("Marketing Publications")."""
    NAME                 = "Title"
    DEMAND               = "Demand"          # multipleRecordLinks → Marketing Demand
    ASSET                = "Asset"           # multipleRecordLinks → Media Files
    CHANNEL              = "Channel"         # multipleRecordLinks → TRAFFIC_SOURCES
    PUBLISHED_AT         = "Published At"
    SOURCE_CODE          = "Source Code"
    RESPONSES            = "Responses"
    QUALIFIED_RESPONSES  = "Qualified Responses"
    PASSED_FORWARD       = "Passed Forward"
    SPEND                = "Spend"
    NOTES                = "Notes"


class ExternalExecutionJobFields:
    CONTRACT_ID       = "contract_id"
    ADAPTER_NAME      = "adapter_name"
    PROVIDER_JOB_ID   = "provider_job_id"
    STATUS            = "status"
    SUBMITTED_AT      = "submitted_at"
    LAST_CHECKED_AT   = "last_checked_at"
    COMPLETED_AT      = "completed_at"
    ATTEMPT_COUNT     = "attempt_count"
    RESULT_REF        = "result_ref"
    EVIDENCE          = "evidence"
    FAILURE_CODE      = "failure_code"


class ApprovalsFields:
    """
    Approval queue for TMA O6 Approvals screen.
    Table name: Approvals
    Must be created manually in Airtable.
    Owner only.

    Phase 4B-2 (schema-prep stage) — three additive projection fields, not yet
    wired to any write/read path (tma_api.py is unchanged in this stage). Per
    the Phase 4B-2 audit, Approvals is a non-authoritative TMA display
    projection of ActionContracts (below); it must never be sufficient by
    itself to authorize a claim or execution. Must be created manually in
    Airtable before use, same as the rest of this table:
      action_contract_id           singleLineText  — FK to
                                    ActionContractsFields.CONTRACT_ID. Empty on
                                    any pre-4B-2 ("legacy") row.
      legacy_read_only             checkbox (default false) — true for any row
                                    with no action_contract_id. Never
                                    auto-replayed, never actionable.
      projected_lifecycle_status   singleSelect — display-only mirror of
                                    ActionContractsFields.STATUS, see
                                    core/approvals_projection.py::
                                    project_lifecycle_status(). Mutable,
                                    non-authoritative — never consulted for
                                    claim/execution authority.
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
    # Phase 4B-2 — projection fields (schema-prep stage; not yet wired)
    ACTION_CONTRACT_ID         = "action_contract_id"
    LEGACY_READ_ONLY           = "legacy_read_only"
    PROJECTED_LIFECYCLE_STATUS = "projected_lifecycle_status"

class ApprovalStatus:
    PENDING    = "ממתין"
    PROCESSING = "מעבד"   # transient claim state — execution in progress
    APPROVED   = "אושר"
    REJECTED   = "נדחה"
    FAILED     = "נכשל"   # execution was attempted but failed


class ProjectedLifecycleStatus:
    """
    Phase 4B-2 — display-only bucket values for
    ApprovalsFields.PROJECTED_LIFECYCLE_STATUS. Mirrors ActionContractStatus
    (canonical, below) for TMA display purposes only. Mutable, non-
    authoritative — never consulted to authorize a claim or execution; see
    core/approvals_projection.py for the pure mapping and the Phase 4B-2 audit
    for the full canonical-status -> bucket table (draft is intentionally
    excluded from the owner-approval pending list — it may be a self_confirm
    proposal confirmed through a separate free-text flow, not this screen).
    """
    PENDING         = "pending"
    APPROVED        = "approved"
    REJECTED        = "rejected"
    EXECUTING       = "executing"
    COMPLETED       = "completed"
    FAILED          = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUPERSEDED      = "superseded"
    LEGACY          = "legacy"   # bucket for ActionContractStatus.EXECUTED (legacy compat)


class ActionContractsFields:
    """
    PR-0C Phase 4B0 / Phase 4B-1A — durable NEW proposal persistence and
    proposal-recovery lookups for ActionContract/ExecutionLedger
    (core/action_gateway.py), fronted by core/action_contract_repository.py::
    ActionContractRepository. This does not claim a fully durable lifecycle:
    status/context write-through is deferred to Phase 4B-1B. find_by_id()
    falls back to the repository on a cache miss and hydrates the frozen
    proposal fields from here. Field names match exactly what
    core/action_contract_repository.py's serializer sends (do not rename
    without updating that module). Table name: Tables.ACTION_CONTRACTS.
    contract_id is the match/primary field.

    agent_observations is deliberately NOT persisted here — per its own
    docstring it is "never user-facing, never executable" signal data, not
    needed to safely re-authorize or re-execute a hydrated contract.

    VERSION is persisted metadata only — it is NOT an active concurrency-
    control mechanism today. No transition path in this codebase checks or
    CAS's on it; ActionContractRepository has no transition/claim method at
    all (see its module docstring). A real claim mechanism using this field
    (or a replacement) is tracked separately as Phase 4B0.1, requiring a
    genuinely atomic coordination primitive outside Airtable.

    Reproducible schema spec (table created/extended via Airtable MCP in
    app4bcgoX7t0HUVnm — no automated provisioning script exists yet; recreate
    these fields by hand in any other environment/base until one is written):
      contract_id                  singleLineText (primary field)
      tenant_id                    singleLineText
      canonical_user_id            singleLineText
      tool_name                    singleLineText
      normalized_payload           multilineText   (JSON string)
      business_action_fingerprint  singleLineText
      origin_channel                singleLineText
      origin_chat_id                singleLineText
      requires_approval             checkbox
      status                        singleSelect {draft, pending, approved,
                                     rejected, executing, completed, failed,
                                     outcome_unknown, superseded, executed}
                                     (executed is legacy read compatibility)
      created_at                    number (precision 3)
      approved_by                   singleLineText
      approved_at                   number (precision 3)
      version                       number (precision 0)
      actor_role                    singleLineText
      actor_user_id                 singleLineText
      actor_display_name            singleLineText
      actor_domain_id               singleLineText
      actor_external_id             singleLineText
      actor_allowed_domains         multilineText   (JSON array string)
      approval_policy               singleLineText
      trusted_source                singleLineText
      context_interrupted           checkbox
      reconfirmation_required       checkbox
      context_integrity_unknown     checkbox
      idempotency_key               singleLineText
    """
    CONTRACT_ID      = "contract_id"
    TENANT_ID        = "tenant_id"
    CANONICAL_USER_ID = "canonical_user_id"
    TOOL_NAME        = "tool_name"
    NORMALIZED_PAYLOAD = "normalized_payload"       # JSON string
    BUSINESS_FINGERPRINT = "business_action_fingerprint"
    ORIGIN_CHANNEL   = "origin_channel"
    ORIGIN_CHAT_ID   = "origin_chat_id"
    REQUIRES_APPROVAL = "requires_approval"
    STATUS           = "status"    # draft|pending|approved|rejected|executing|completed|failed|outcome_unknown|superseded
    CREATED_AT       = "created_at"       # unix timestamp (float)
    APPROVED_BY      = "approved_by"
    APPROVED_AT      = "approved_at"      # unix timestamp (float)
    VERSION          = "version"          # persisted metadata only — not an active concurrency guard (see class docstring)
    ACTOR_ROLE               = "actor_role"
    ACTOR_USER_ID             = "actor_user_id"
    ACTOR_DISPLAY_NAME        = "actor_display_name"
    ACTOR_DOMAIN_ID           = "actor_domain_id"
    ACTOR_EXTERNAL_ID         = "actor_external_id"
    ACTOR_ALLOWED_DOMAINS     = "actor_allowed_domains"    # JSON array string
    APPROVAL_POLICY           = "approval_policy"
    TRUSTED_SOURCE            = "trusted_source"
    CONTEXT_INTERRUPTED       = "context_interrupted"
    RECONFIRMATION_REQUIRED   = "reconfirmation_required"
    CONTEXT_INTEGRITY_UNKNOWN = "context_integrity_unknown"
    IDEMPOTENCY_KEY           = "idempotency_key"  # frozen proposal key; execution wiring unchanged in 4B-1A


class ActionContractStatus:
    DRAFT      = "draft"
    PENDING    = "pending"
    APPROVED   = "approved"
    REJECTED   = "rejected"
    EXECUTING  = "executing"
    COMPLETED  = "completed"
    FAILED     = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUPERSEDED = "superseded"
    EXECUTED   = "executed"  # legacy terminal value; do not emit for new transitions


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


# C58 — Universal Sessions. ראה SPEC_C58_Universal_Sessions.md.
# Session = מצב עבודה זמני סביב ישות קיימת (lead/decision/task/...) — לא דאטה עסקי.
# טבלה אחת משותפת (Tables.SESSIONS), context_type מבדיל בין סוגי השימוש.
class SessionsFields:
    SESSION_ID       = "Session ID"
    CONTEXT_TYPE     = "Context Type"      # select: lead/decision/task/payment/deal/contact/media/general
    STATE_JSON       = "State JSON"
    LAST_TOOL_RESULT = "Last Tool Result"
    CHANNEL          = "Channel"
    SENDER_ID        = "Sender ID"
    CREATED_AT       = "Created At"
    UPDATED_AT       = "Updated At"
    # Links (כולם אופציונליים):
    LINKED_LEAD            = "Linked Lead"
    LINKED_CONTACT         = "Linked Contact"
    LINKED_DECISION        = "Linked Decision"
    LINKED_DECISION_EVENT  = "Linked Decision Event"
    LINKED_DEAL            = "Linked Deal"
    LINKED_TASK            = "Linked Task"
    LINKED_PAYMENT         = "Linked Payment"
    LINKED_VENTURE         = "Linked Venture"
    LINKED_MEDIA_FILE      = "Linked Media File"
    LINKED_BUSINESS_MEMORY = "Linked Business Memory"


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
    COINS_EARNED = "Coins_Earned"


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
    # Stage 2 (F17, Smart Trust Layer) — NOT YET created in live Airtable.
    # airtable_patch() will silently drop these (schema_cache.json doesn't know
    # them yet) until Eliyahu adds the 4 fields manually and schema_audit.py
    # refreshes the cache. Telegram display of computed values works regardless
    # (decision_confidence.py computes in-memory; persistence is best-effort).
    EVIDENCE_IDS         = "Evidence Ids"          # long text (JSON array of Decision Event record IDs)
    EVIDENCE_SUMMARY     = "Evidence Summary"      # long text — human-readable
    CONFIDENCE_SCORE     = "Confidence Score"      # number 0.0-1.0
    MISSING_EVIDENCE     = "Missing Evidence"      # long text (JSON array)
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
    # REVIEW added for Stage 3 (Readiness Engine) — not in original two-value
    # enum. NOT confirmed as a live Airtable singleSelect option yet; same
    # best-effort-write pattern as Stage 2's not-yet-created fields applies
    # (airtable_patch silently drops unknown option values until Eliyahu adds
    # it in Airtable). Disclosed deviation, see CHANGE_CONTROL_LOG.md.
    REVIEW     = "REVIEW"


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
    CLAIM_TOPIC           = "Claim Topic"            # single line text — Stage 1
    CLAIM_TOPIC_SOURCE    = "Claim Topic Source"     # singleSelect — see DecisionClaimTopicSource
    CLAIM_TOPIC_CONFIDENCE = "Claim Topic Confidence" # number 0-100


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
    DOCUMENT   = "מסמך"
    PARTNER    = "שותף"
    CLIENT     = "לקוח"
    MANUAL     = "ידני"
    EMPLOYEE   = "עובד"
    RUMOR      = "שמועה"
    UNKNOWN    = "לא_ידוע"


class DecisionClaimTopicSource:
    """singleSelect options on Decision Events.Claim Topic Source (Airtable-confirmed)."""
    AUTO       = "Auto"
    FILENAME   = "Filename"
    KEYWORD    = "Keyword"
    EVENT_TYPE = "Event Type"
    MANUAL     = "Manual"


class DecisionEventTag:
    PARTIAL_TRANSCRIPT = "תמלול_חלקי"
    VAGUE              = "עמום"
    CONFLICT           = "קונפליקט"
    PRESSURE_ONLY       = "לחץ_בלבד"
    MISSING_CONTEXT     = "חסר_הקשר"
    # NOT CONFIRMED against live Airtable Tags multipleSelects options — added for Stage 1,
    # may need to be created in Airtable before first real write reaches these branches.
    LOW_CONFIDENCE      = "אמינות_נמוכה"
    PRESSURE_HIGH_RISK  = "לחץ_סיכון_גבוה"


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


class TrafficSourcesFields:
    """BOSS Growth P0 — channel-level traffic source attribution.
    Table name: Tables.TRAFFIC_SOURCES ("TRAFFIC_SOURCES"), already live.
    Discovered via Airtable MCP 2026-06-24 — not yet referenced by any code
    module (no read/write path wired in; documented here for future use,
    e.g. ad_attribution.py).
    """
    SOURCE_NAME  = "Source Name"
    SOURCE_TYPE  = "Source Type"
    AUDIENCE     = "Audience"
    CONTACT      = "Contact"
    REACH        = "Reach"
    LEADS        = "Leads"
    DEALS        = "Deals"
    REVENUE      = "Revenue"
    COST         = "Cost"
    STATUS       = "Status"
    NOTES        = "Notes"
    ROI          = "ROI"          # formula — (Revenue - Cost) / Cost
    # F23 — BOSS Marketing Bridge (M1) additions
    URL                    = "URL"
    LOCATION               = "Location"
    SUITABLE_DOMAINS       = "Suitable Domains"        # multipleSelects: canonical business domains (domain_utils.py)
    FREE_PAID              = "Free/Paid"               # singleSelect: Free|Paid
    SUITABLE_DEMAND_TYPES  = "Suitable Demand Types"   # multipleSelects: recruitment|furniture_import|fiber_equipment|real_estate_listing|service
    POSTING_RULES          = "Posting Rules"
    LAST_PUBLISHED_AT      = "Last Published At"
    QUALITY_NOTES          = "Quality Notes"


# ══════════════════════════════════════════════════
# LeadEventFields — N-LEAD-EVENT: Lead Events table
# טבלה נפרדת לאירועים על ליד קיים.
# נוצרת ידנית ב-Airtable. Linked Record ל-Leads.
#
# שדות ליצור ב-Airtable:
#   Name (primary, text) — כותרת האירוע
#   Lead (linked record → Leads) — מי הליד
#   Event Type (singleSelect) — interest|note|domain_change|followup_request|other
#   Domain (singleSelect) — real_estate|import|recruiting|general|...
#   Message (long text) — ההודעה המלאה
#   Summary (short text) — תקציר קצר
#   Channel (singleSelect) — whatsapp|telegram
#   Created At (dateTime) — auto
# ══════════════════════════════════════════════════

class LeadEventFields:
    NAME         = "Name"           # Primary Field — כותרת האירוע
    LEAD_LINK    = "Lead"           # Linked record → Tables.LEADS
    EVENT_TYPE   = "Event Type"     # singleSelect — ראה LeadEventType
    DOMAIN       = "Domain"         # canonical business domain; legacy values read through domain_utils
    MESSAGE      = "Message"        # הודעה מלאה (עד 5000 תווים)
    SUMMARY      = "Summary"        # תקציר קצר (עד 200 תווים)
    CHANNEL      = "Channel"        # whatsapp | telegram
    CREATED_AT   = "Created At"     # dateTime — auto


class LeadEventType:
    """Lead Events.Event Type singleSelect — ערכים מדויקים."""
    INTEREST         = "interest"         # עניין בנושא חדש
    NOTE             = "note"             # הערה כללית
    DOMAIN_CHANGE    = "domain_change"    # שינוי domain לאותו ליד
    FOLLOWUP_REQUEST = "followup_request" # ליד מבקש שיחזרו אליו
    OTHER            = "other"            # אחר


# ══════════════════════════════════════════════════
# PR3A — Schema Snapshot Archive
# ══════════════════════════════════════════════════

class SchemaSnapshotFields:
    """Tables.SCHEMA_SNAPSHOTS — must be created manually in Airtable before use."""
    SNAPSHOT_DATE  = "Snapshot Date"    # dateTime
    SNAPSHOT_FILE  = "Snapshot File"    # multipleAttachments — JSON + XLSX
    TABLES_COUNT   = "Tables Count"     # number
    STATUS         = "Status"           # singleSelect — see SchemaSnapshotStatus
    NOTES          = "Notes"            # multilineText
    SCHEMA_HASH    = "Schema Hash"      # singleLineText
    BASE_ID        = "Base ID"          # singleLineText


class SchemaSnapshotStatus:
    """Tables.SCHEMA_SNAPSHOTS.Status singleSelect — exact values."""
    OK             = "OK"
    DRIFT_DETECTED = "Drift Detected"
    ERROR          = "Error"


# ══════════════════════════════════════════════════
# PATCH 3B — Emergency Stop persistence (Option B: dedicated table)
# ══════════════════════════════════════════════════

class EmergencyStopFlagFields:
    """Tables.EMERGENCY_STOP_FLAGS — must be created manually in Airtable before use.

    One record per flag name (e.g. EMERGENCY_STOP_ALL — see feature_flags.py for
    the live list). Flag Name is a plain singleLineText primary field, NOT a
    singleSelect — a reader must treat missing/duplicate Flag Name values across
    records as a data-integrity error, not something the field's own type system
    will ever catch for us. Enabled is a checkbox — Airtable omits the key
    entirely from a record's fields when unchecked, so a reader must default
    missing Enabled to False rather than treat it as invalid.
    """
    FLAG_NAME    = "Flag Name"     # singleLineText — primary field; must appear exactly once per known flag
    ENABLED      = "Enabled"       # checkbox — absent key means False, not "invalid"
    OPERATION_ID = "Operation ID"  # singleLineText — CAS token, see EmergencyStopStore.write()
    UPDATED_AT   = "Updated At"    # dateTime
    UPDATED_BY   = "Updated By"    # singleLineText
    SOURCE       = "Source"        # singleLineText
    REASON       = "Reason"        # multilineText
