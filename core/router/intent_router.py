# intent_router.py — CORE_02_ROUTER
# זיהוי כוונת המשתמש.
#
# עקרון: Rule-based קודם. LLM רק כשאין ודאות.
# אף פעם לא מנחשים על פעולה רגישה.

from __future__ import annotations
import re
import logging
from typing import Optional
from .route_decision import Intent

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Rule Tables — עברית + אנגלית
# ══════════════════════════════════════════════════

# (pattern, intent, confidence)
# סדר חשוב — ספציפי לפני כללי

_RULES: list[tuple[str, str, float]] = [

    # ── Greeting / Smalltalk / Bot Status ────────
    (r"^(שלום|היי|הי|בוקר טוב|ערב טוב|צהריים טובים|hello|hi|hey)[\s!.]*$", Intent.GREETING, 0.99),
    (r"^(שלום|היי|הי)\b",                                                    Intent.GREETING, 0.95),
    (r"(מה נשמע|מה קורה|איך הולך|מה שלומך|what\'s up|how are you)",         Intent.SMALLTALK, 0.95),
    # BUG-ROUTER-TEST-WORD-COLLISION: "בדיקה"/"test" must be the ENTIRE message.
    # Without anchoring, "תוסיף לגליון בשם בדיקה..." was wrongly classified as
    # BOT_STATUS_CHECK because the word "בדיקה" appeared inside the sheet name.
    (r"^(בדיקה|test)\s*[\?!.]*$",                                            Intent.BOT_STATUS_CHECK, 0.99),
    # Contextual phrases that are inherently bot-status-only (safe to match anywhere)
    (r"(אתה עובד\??|שומע אותי\??|are you (working|there|alive))",            Intent.BOT_STATUS_CHECK, 0.95),

    # BUG-IC-01/C89: explicit action verb (בדוק/תבדוק) + integration name is
    # required for a REAL connectivity check to fire — placed early so it
    # wins over the generic "calendar"→LIST_EVENTS / "בדוק"→RESEARCH_TOPIC
    # rules below. Bare "סטטוס"/"מצב" nouns without a verb are NOT matched
    # here — they fall through to _AMBIGUOUS_PHRASES → CLARIFY instead of a
    # live check. Plain text must not inherit /status's slash-command power.
    (r"(בדוק|תבדוק|תבדקי).*(חיבור|gmail|calendar|airtable|מערכת)", Intent.SYSTEM_STATUS, 0.95),

    # ── Tasks ────────────────────────────────────
    (r"(פתח|צור|הוסף|תוסיף).*(משימ|טאסק|task)", Intent.CREATE_TASK, 0.95),
    (r"(עדכן|שנה|תעדכן).*(משימ|טאסק|task)", Intent.UPDATE_TASK, 0.95),
    (r"(סגור|סיים|סמן.*סיים|complete).*(משימ|טאסק|task)", Intent.COMPLETE_TASK, 0.95),
    (r"(מחק|הסר).*(משימ|טאסק|task)", Intent.DELETE_TASK, 0.90),
    (r"(רשימ|הצג|תראה|מה).*משימ|list.*task", Intent.LIST_TASKS, 0.90),

    # ── Calendar ─────────────────────────────────
    (r"(קבע|תקבע|צור|תצור|פתח|תפתח|הוסף|תוסיף).*(פגיש|אירוע|ישיב|פגישה|event|meeting)", Intent.CREATE_EVENT, 0.95),
    (r"(בטל|ביטול|cancel).*(פגיש|אירוע|event)", Intent.CANCEL_EVENT, 0.95),
    (r"(עדכן|שנה).*(פגיש|אירוע|event)", Intent.UPDATE_EVENT, 0.90),
    (r"(מה יש|מה.*יומן|אירועים|לוח זמנים|פגישות.*היום|calendar|events)", Intent.LIST_EVENTS, 0.90),
    (r"(קבע.*פגיש|schedule.*meeting|잡아|잡다)", Intent.SCHEDULE_MEETING, 0.90),

    # ── Leads / CRM ──────────────────────────────
    (r"(הוסף|תוסיף|צור|תצור|פתח|תפתח|רשום).*(ליד|lead|לקוח פוטנציאלי)", Intent.CREATE_LEAD, 0.95),
    (r"(עדכן|שנה).*(ליד|lead)", Intent.UPDATE_LEAD, 0.90),
    # BUG-130: "תעדכן את הטלפון של X" (a field-update phrased around a
    # PERSON, not the literal word "ליד"/"lead") fell through every rule
    # above straight to Intent.UNKNOWN — the router never told
    # core/lead_candidate_handler.py this was an update at all, so it had
    # no chance to look the existing lead up by name (see BUG-130 in
    # BUG_AUDIT_LOG.md). "של" is required to anchor the field to a person
    # ("the PHONE OF X"), not just any sentence containing an update verb
    # and a phone-ish noun.
    (r"(עדכן|שנה).*(טלפון|מספר|פלאפון|נייד).*של", Intent.UPDATE_LEAD, 0.85),
    (r"(חפש|מצא|תמצא).*(ליד|lead)", Intent.FIND_LEAD, 0.90),
    (r"(כשיר|qualify|דרג).*(ליד|lead)", Intent.QUALIFY_LEAD, 0.90),
    (r"(סגור|סגירת).*(עסק|עסקה|deal)", Intent.CLOSE_DEAL, 0.90),
    (r"(עדכן|שנה).*(שלב|סטטוס|stage).*(עסק|עסקה|deal)", Intent.UPDATE_DEAL_STAGE, 0.90),

    # ── Contacts ─────────────────────────────────
    (r"(הוסף|צור|פתח).*(איש קשר|contact|לקוח|ספק)", Intent.CREATE_CONTACT, 0.90),
    (r"(עדכן|שנה).*(איש קשר|contact)", Intent.UPDATE_CONTACT, 0.90),
    (r"(חפש|מצא).*(איש קשר|contact|לקוח|ספק)", Intent.FIND_CONTACT, 0.90),
    (r"(רשימ|הצג).*(אנשי קשר|contacts|לקוחות|ספקים)", Intent.LIST_CONTACTS, 0.85),

    # ── Email ────────────────────────────────────
    (r"(כתוב|נסח|הכן|draft).*(מייל|אימייל|email)", Intent.DRAFT_EMAIL, 0.95),
    (r"(שלח).*(מייל|אימייל|email)", Intent.SEND_EMAIL, 0.95),

    # ── Reporting ────────────────────────────────
    (r"(דוח|דו.ח|report|סיכום).*(כספ|פיננס|finance|financial)|(תזרים|cash.flow|מאזן)", Intent.FINANCIAL_REPORT, 0.95),
    (r"(דוח|דו.ח|report|סיכום).*(מכיר|מכירות|sales)", Intent.SALES_REPORT, 0.90),
    (r"(דוח|דו.ח|report|סיכום|generate)", Intent.GENERATE_REPORT, 0.80),

    # ── Knowledge / Documents ────────────────────
    (r"(חפש|מצא|search).*(מסמך|קובץ|drive|document|file)", Intent.READ_DOCUMENT, 0.90),
    (r"(קרא|פתח|תראה).*(מסמך|קובץ|file|document)", Intent.READ_DOCUMENT, 0.90),
    (r"(חפש|מצא|search).*(מידע|נתון|knowledge|info)", Intent.SEARCH_KNOWLEDGE, 0.85),
    (r"(זכור|שמור|store).*(זיכרון|memory|מידע)", Intent.STORE_MEMORY, 0.90),

    # ── Research ─────────────────────────────────
    (r"(חקור|מחקר|research).*(חברה|company|ארגון)", Intent.RESEARCH_COMPANY, 0.90),
    (r"(חקור|מחקר|research|בדוק)", Intent.RESEARCH_TOPIC, 0.80),

    # ── System ───────────────────────────────────
    (r"(סטטוס|status|מצב).*(מערכת|system|בוט|bot)", Intent.SYSTEM_STATUS, 0.95),
    (r"(הגדרות|settings|ניהול|admin|manage)", Intent.ADMIN_ACTION, 0.85),

    # ── Communication — כלליים בסוף ──────────────
    (r"(תרגם|translate)", Intent.TRANSLATE, 0.95),
    (r"(סכם|תסכם|summarize|סיכום)", Intent.SUMMARIZE, 0.90),
    (r"(הסבר|explain|מה זה|מה הכוונה)", Intent.EXPLAIN, 0.85),
    (r"(מידע|פרטים|תגיד לי|tell me|information about)", Intent.REQUEST_INFO, 0.75),
]

# Compile פעם אחת
_COMPILED: list[tuple[re.Pattern, str, float]] = [
    (re.compile(pattern, re.IGNORECASE | re.UNICODE), intent, conf)
    for pattern, intent, conf in _RULES
]


# ══════════════════════════════════════════════════
# Engineering / meta-content markers (SPEC-ROUTER-06)
# Evaluated by the caller BEFORE the business rule table — bug reports and
# debug instructions must never fall into a business intent just because
# they happen to contain words like "עדכן"/"ליד".
# ══════════════════════════════════════════════════

_ENGINEERING_MARKERS = [
    "יש באג", "נדרש תיקון", "Definition of Done", "Root Cause", "Symptom",
    "record_id", "sender_identity", "subject_identity", "ClaimGate", "approval_id",
]


def count_engineering_markers(text: str) -> int:
    """כמה מהמילות-מפתח ההנדסיות מופיעות בטקסט (case-insensitive ל-latin)."""
    text_lower = text.lower()
    return sum(1 for marker in _ENGINEERING_MARKERS if marker.lower() in text_lower)


def detect_intent(text: str, confidence_threshold: float = 0.75) -> tuple[str, float, str]:
    """
    מחזיר (intent, confidence, matched_rule).
    אם אין התאמה מעל הסף — מחזיר (UNKNOWN, 0.0, "").
    """
    text_clean = text.strip()

    for pattern, intent, confidence in _COMPILED:
        if pattern.search(text_clean):
            logger.debug(f"[Intent] '{text_clean[:40]}' → {intent} ({confidence:.2f}) via {pattern.pattern[:30]}")
            return intent, confidence, pattern.pattern

    # אין התאמה
    logger.debug(f"[Intent] No rule match for: '{text_clean[:40]}'")
    return Intent.UNKNOWN, 0.0, ""


# ══════════════════════════════════════════════════
# Ambiguous short-phrase detector (BUG-IC-01 / C89)
#
# Slash commands are commands. Natural language is intent input.
# A bare status/task noun-phrase from the owner ("סטטוס", "בדיקות מערכת",
# "מה המצב", "למלא משימות") must NOT fall through Intent.UNKNOWN into the
# general Agent, where it could decide on its own initiative to run a full
# connectivity check (Gmail/Calendar/Airtable) or guess at a task action.
# Only a literal /status (or an explicit action verb + target, e.g.
# "בדוק חיבורי מערכת") is allowed to trigger that. Everything else here
# routes to Handler.CLARIFY with a specific disambiguating question.
#
# BUG-IC-01B: Also catches prefixed ambiguous phrases with common natural-language
# prefixes (אני צריך, צריך, רוצה, אפשר, תעזור לי) before the ambiguous object.
# ══════════════════════════════════════════════════

_AMBIGUOUS_PHRASES: list[tuple[re.Pattern, str]] = [
    # Status/System check — bare or prefixed
    (re.compile(r"^(סטטוס|status|מה המצב|מצב)\s*[\?!.]*$", re.IGNORECASE),
     "אתה רוצה שאבדוק חיבורים עכשיו (Gmail/Calendar/Airtable), או משהו אחר?"),
    (re.compile(r"^(אני\s+)?(צריך|רוצה|אפשר|תעזור לי).*(סטטוס|status|מה המצב|מצב)\s*[\?!.]*$", re.IGNORECASE),
     "אתה רוצה שאבדוק חיבורים עכשיו (Gmail/Calendar/Airtable), או משהו אחר?"),

    # System tests — bare or prefixed
    # BUG-056: the ? must sit on the ו (בדיקה/בדיקת vs בדיקות), not on the
    # trailing ת — a ?-on-ת regex never matches the singular/construct form
    # "בדיקת" (no ו) at all, only "בדיקו"/"בדיקות".
    (re.compile(r"^בדיקו?ת\s*מערכת\s*[\?!.]*$", re.IGNORECASE),
     "אתה רוצה שאבדוק חיבורים עכשיו או שאתה מתכוון לתיעוד בדיקות?"),
    (re.compile(r"^(אני\s+)?(צריך|רוצה|אפשר|תעזור לי).*בדיקו?ת\s*מערכת\s*[\?!.]*$", re.IGNORECASE),
     "אתה רוצה שאבדוק חיבורים עכשיו או שאתה מתכוון לתיעוד בדיקות?"),

    # Tasks — bare or prefixed
    (re.compile(r"^(תמלא|למלא)\s*משימות\s*[\?!.]*$", re.IGNORECASE),
     "להוסיף משימה חדשה, לעדכן קיימת, או לראות רשימה?"),
    (re.compile(r"^(אני\s+)?(צריך|רוצה|אפשר|תעזור לי).*(תמלא|למלא|לראות|לעדכן).*משימ", re.IGNORECASE),
     "להוסיף משימה חדשה, לעדכן קיימת, או לראות רשימה?"),
]


def detect_ambiguous_phrase(text: str) -> Optional[str]:
    """
    מזהה משפט קצר דו-משמעי (בעיקר owner/staff) שאסור שיפעיל בדיקת מערכת
    או פעולה רחבה אוטומטית. מחזיר שאלת הבהרה אם נמצאה התאמה, אחרת None.
    רץ רק כשdetect_intent כבר החזיר UNKNOWN — לא דורס כוונה מפורשת שזוהתה.
    Supports both bare phrases ("למלא משימות") and prefixed ones ("אני צריך למלא משימות").
    """
    stripped = text.strip()
    for pattern, question in _AMBIGUOUS_PHRASES:
        if pattern.match(stripped):
            return question
    return None
