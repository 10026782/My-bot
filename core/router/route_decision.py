# route_decision.py — CORE_02_ROUTER
# מבנה הנתונים המרכזי של שכבת הניתוב.
# כל בקשה מחזירה RouteDecision לפני שהAgent רץ.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ingress_classifier import IngressClassification


# ══════════════════════════════════════════════════
# Intent Catalog — 35 intents קבועים
# ══════════════════════════════════════════════════

class Intent:
    # Tier 0 — Conversational
    GREETING         = "greeting"
    SMALLTALK        = "smalltalk"
    BOT_STATUS_CHECK = "bot_status_check"

    # Tier 1 — Communication
    ASK_QUESTION      = "ask_question"
    REQUEST_INFO      = "request_information"
    SUMMARIZE         = "summarize"
    TRANSLATE         = "translate"
    EXPLAIN           = "explain"

    # Tier 2 — Task Management
    CREATE_TASK       = "create_task"
    UPDATE_TASK       = "update_task"
    COMPLETE_TASK     = "complete_task"
    DELETE_TASK       = "delete_task"
    LIST_TASKS        = "list_tasks"

    # Tier 3 — Calendar
    CREATE_EVENT      = "create_event"
    UPDATE_EVENT      = "update_event"
    CANCEL_EVENT      = "cancel_event"
    LIST_EVENTS       = "list_events"
    SCHEDULE_MEETING  = "schedule_meeting"

    # Tier 4 — Contacts
    CREATE_CONTACT    = "create_contact"
    UPDATE_CONTACT    = "update_contact"
    FIND_CONTACT      = "find_contact"
    LIST_CONTACTS     = "list_contacts"

    # Tier 5 — CRM / Leads
    CREATE_LEAD       = "create_lead"
    UPDATE_LEAD       = "update_lead"
    FIND_LEAD         = "find_lead"
    QUALIFY_LEAD      = "qualify_lead"
    CLOSE_DEAL        = "close_deal"
    UPDATE_DEAL_STAGE = "update_deal_stage"

    # Tier 6 — Knowledge
    SEARCH_KNOWLEDGE  = "search_knowledge"
    READ_DOCUMENT     = "read_document"
    STORE_MEMORY      = "store_memory"
    RETRIEVE_MEMORY   = "retrieve_memory"

    # Tier 7 — Communication Actions
    DRAFT_EMAIL       = "draft_email"
    SEND_EMAIL        = "send_email"
    DRAFT_MESSAGE     = "draft_message"
    SEND_MESSAGE      = "send_message"

    # Tier 8 — Reporting
    GENERATE_REPORT   = "generate_report"
    FINANCIAL_REPORT  = "financial_report"
    SALES_REPORT      = "sales_report"

    # Tier 9 — Research
    RESEARCH_TOPIC    = "research_topic"
    RESEARCH_COMPANY  = "research_company"

    # Tier 10 — System
    SYSTEM_STATUS     = "system_status"
    ADMIN_ACTION      = "admin_action"

    # Fallback — אף פעם לא מנחשים
    UNKNOWN           = "unknown"

    # Tier 11 — Engineering / meta (SPEC-ROUTER-06)
    ENGINEERING_NOTE  = "engineering_note"

    # Marketing bridge — fixed, validated /marketing_new action
    DRAFT_MARKETING_CREATIVES = "draft_marketing_creatives"

    DETECT_DAILY_PERSISTENCE_GAPS = "detect_daily_persistence_gaps"
    ANALYZE_BUSINESS_INTERACTION = "analyze_business_interaction"

    ALL = {
        GREETING, SMALLTALK, BOT_STATUS_CHECK,
        ASK_QUESTION, REQUEST_INFO, SUMMARIZE, TRANSLATE, EXPLAIN,
        CREATE_TASK, UPDATE_TASK, COMPLETE_TASK, DELETE_TASK, LIST_TASKS,
        CREATE_EVENT, UPDATE_EVENT, CANCEL_EVENT, LIST_EVENTS, SCHEDULE_MEETING,
        CREATE_CONTACT, UPDATE_CONTACT, FIND_CONTACT, LIST_CONTACTS,
        CREATE_LEAD, UPDATE_LEAD, FIND_LEAD, QUALIFY_LEAD, CLOSE_DEAL, UPDATE_DEAL_STAGE,
        SEARCH_KNOWLEDGE, READ_DOCUMENT, STORE_MEMORY, RETRIEVE_MEMORY,
        DRAFT_EMAIL, SEND_EMAIL, DRAFT_MESSAGE, SEND_MESSAGE,
        GENERATE_REPORT, FINANCIAL_REPORT, SALES_REPORT,
        RESEARCH_TOPIC, RESEARCH_COMPANY,
        SYSTEM_STATUS, ADMIN_ACTION,
        UNKNOWN, ENGINEERING_NOTE, DRAFT_MARKETING_CREATIVES,
        DETECT_DAILY_PERSISTENCE_GAPS,
        ANALYZE_BUSINESS_INTERACTION,
    }


# ══════════════════════════════════════════════════
# Domain Catalog
# ══════════════════════════════════════════════════

class RouterDomain:
    REAL_ESTATE = "real_estate"
    IMPORT      = "import"
    MEDIA       = "media"
    SAAS        = "saas"
    FINANCE     = "finance"
    RECRUITMENT = "recruitment"
    CRM         = "crm"
    GENERAL     = "general"
    INTERNAL    = "internal"  # הנדסי/מטא — לא דומיין עסקי


# ══════════════════════════════════════════════════
# Risk Levels
# ══════════════════════════════════════════════════

class Risk:
    READ_ONLY        = "read_only"    # שליפת מידע בלבד
    NORMAL           = "normal"       # פעולה רגילה הפיכה
    NEEDS_APPROVAL   = "needs_approval"  # פעולה שדורשת אישור
    BLOCK            = "block"        # חסימה מוחלטת


# ══════════════════════════════════════════════════
# Execution Handlers
# ══════════════════════════════════════════════════

class Handler:
    AGENT       = "agent"         # Agent רגיל עם כלים
    TOOL        = "tool"          # כלי ישיר ללא Agent
    CLARIFY     = "clarify"       # בקש הבהרה מהמשתמש
    APPROVAL    = "approval"      # המתן לאישור אנושי
    BLOCK       = "block"         # חסום — שמור לשימוש פנימי קיצוני
    RESTRICTED  = "restricted"    # agent מדבר, tools חסומים, owner מקבל לוג
    ENGINEERING_NOTE = "engineering_note"  # דיווח באג/הודעה הנדסית — אין כלים, אין claim של תיקון


# ══════════════════════════════════════════════════
# RouteDecision — הפלט של router.py
# ══════════════════════════════════════════════════

@dataclass
class RouteDecision:
    # מקור
    channel:         str = "unknown"

    # סיווג
    intent:          str = Intent.UNKNOWN
    domain:          str = RouterDomain.GENERAL
    risk:            str = Risk.NORMAL

    # החלטת ביצוע
    handler:         str = Handler.AGENT
    needs_approval:  bool = False

    # Restricted flow — agent מדבר, tools לא רצים
    restricted:    bool = False   # פעולה מוגבלת
    notify_owner:  bool = False   # שלח לוג/התראה לowner
    tool_allowed:  bool = True    # האם מותר להפעיל tools

    # ביטחון בסיווג (0.0–1.0)
    # מתחת ל-0.5 → intent=unknown, handler=clarify
    confidence:      float = 1.0

    # מידע נוסף לdebugging
    matched_rule:    str = ""       # איזה חוק זיהה את ה-intent
    llm_classified:  bool = False   # האם LLM השתמש בסיווג

    # הודעה למשתמש אם handler=clarify/block
    response_override: str = ""

    # Capture Policy (Stage 3 / C89 router integration) — additive, observability
    # only. Mirrors what core.lead_candidate_handler will independently decide
    # for identity.is_internal senders (same classify_ingress() call) — does
    # NOT gate whether LCH runs; see core/router/capture_router.py.
    capture_tier:    int | None = None   # 1-3 when classify_ingress() sees a
                                          # write-worthy capture, else None
    capture_reason:  str = ""            # classify_ingress() reason string
    raw_ref:         str = ""            # Interaction Log reference (future)
    capture_ic:      "IngressClassification | None" = None  # BUG-056: full
                                          # classification (all 5 tiers), so
                                          # handle_lead_candidate() can reuse
                                          # it instead of re-classifying, and
                                          # router.py can stop-gate Tier 4.

    def is_blocked(self) -> bool:
        return self.handler == Handler.BLOCK

    def needs_clarification(self) -> bool:
        return self.handler == Handler.CLARIFY

    def to_log(self) -> str:
        return (
            f"[Route] channel={self.channel} intent={self.intent} "
            f"domain={self.domain} risk={self.risk} "
            f"handler={self.handler} confidence={self.confidence:.2f} "
            f"rule='{self.matched_rule}'"
        )
