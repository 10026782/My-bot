# core/anti_hallucination.py — A32 Anti-Hallucination Layer
#
# Principle: if the tool didn't confirm it, the agent didn't do it.
# Three gates:
#   1. verify_execution  — did the tool actually succeed?
#   2. verify_result_claim — does the agent's text match reality?
#   3. sanitize_agent_response — replace hallucinated text with safe copy.

from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Evidence validator registry
# ══════════════════════════════════════════════════
# Each entry maps a tool name → callable(tool_name, result_dict) → VerifyResult | None
# None means "evidence acceptable, caller should return ok".
# VerifyResult means "failed with this reason".
# Tools NOT in the registry are non-structured tools (plain strings accepted).
# Structured tools (those in _EVIDENCE_VALIDATORS) MUST supply a dict.

_REC_PATTERN = re.compile(r'^rec[A-Za-z0-9]{14}$')


def _validate_airtable_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {})
    record_id = str(evidence.get("record_id", "") if isinstance(evidence, dict) else "") or external_id
    rec_id = external_id or record_id
    if not rec_id:
        return VerifyResult("failed", f"{tool_name}: missing external_id/record_id in structured result")
    if not _REC_PATTERN.match(rec_id):
        return VerifyResult(
            "failed",
            f"{tool_name}: external_id '{rec_id[:30]}' is not a valid Airtable record_id "
            f"(expected ^rec[A-Za-z0-9]{{14}}$)"
        )
    return None


def _validate_sheets_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    evidence = result.get("evidence", {}) or {}
    ext = result.get("external_id", "")
    has = (
        result.get("spreadsheet_id")
        or (isinstance(evidence, dict) and (
            evidence.get("spreadsheet_id") or evidence.get("sheet_id")
            or evidence.get("updated_range") or evidence.get("rows_appended")
        ))
        or ext
    )
    if not has:
        return VerifyResult(
            "failed",
            f"{tool_name}: missing spreadsheet_id/sheet_id/updated_range/rows_appended in evidence"
        )
    return None


def _validate_drive_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    evidence = result.get("evidence", {}) or {}
    ext = result.get("external_id", "")
    has = (
        ext
        or (isinstance(evidence, dict) and (evidence.get("file_id") or evidence.get("drive_url")))
    )
    if not has:
        return VerifyResult(
            "failed",
            f"{tool_name}: missing file_id or drive_url in evidence"
        )
    return None


def _validate_gmail_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {}) or {}
    has = (
        external_id
        or (isinstance(evidence, dict) and (evidence.get("draft_id") or evidence.get("message_id")))
    )
    if not has:
        return VerifyResult(
            "failed",
            f"{tool_name}: missing external_id/draft_id/message_id in structured result"
        )
    return None


def _validate_calendar_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {}) or {}
    has_id = external_id or (isinstance(evidence, dict) and evidence.get("event_id"))
    if not has_id:
        return VerifyResult(
            "failed",
            f"{tool_name}: missing external_id/event_id in structured result"
        )
    # Google Calendar API returns "htmlLink" (camelCase) — support both forms defensively
    if isinstance(evidence, dict):
        html_link = evidence.get("htmlLink") or evidence.get("html_link") or ""
    else:
        html_link = ""
    if not html_link:
        return VerifyResult("failed", f"{tool_name}: missing evidence.htmlLink")
    return None


def _validate_crm_payment_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {}) or {}
    has = (
        external_id
        or (isinstance(evidence, dict) and (
            evidence.get("payment_id") or evidence.get("record_id")
            or evidence.get("updated_at") or evidence.get("paid_at")
        ))
    )
    if not has:
        return VerifyResult(
            "failed",
            f"{tool_name}: missing payment_id/record_id/paid_at in evidence"
        )
    return None


def _validate_media_memory_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {}) or {}
    has = external_id or (isinstance(evidence, dict) and evidence.get("record_id"))
    if not has:
        return VerifyResult("failed", f"{tool_name}: missing external_id/record_id in structured result")
    return None


def _validate_owner_draft_evidence(tool_name: str, result: dict) -> "VerifyResult | None":
    """send_followup/send_recovery: evidence is the output_gateway audit_id proving
    the draft delivery to the owner was actually attempted and audited — there is
    no external record_id since these never write to Airtable."""
    external_id = str(result.get("external_id", "") or "")
    evidence = result.get("evidence", {}) or {}
    has = external_id or (isinstance(evidence, dict) and evidence.get("audit_id"))
    if not has:
        return VerifyResult("failed", f"{tool_name}: missing external_id/audit_id in structured result")
    return None


# Registry: tool_name → evidence validator function.
# Only tools with explicit validators here are permitted to produce success claims.
_EVIDENCE_VALIDATORS: dict[str, Any] = {
    "airtable_add":          _validate_airtable_evidence,
    "airtable_update":       _validate_airtable_evidence,
    "sheets_append":         _validate_sheets_evidence,
    "drive_upload":          _validate_drive_evidence,
    "drive_create":          _validate_drive_evidence,
    "gmail_draft":           _validate_gmail_evidence,
    "gmail_send_draft":      _validate_gmail_evidence,
    "calendar_create_event": _validate_calendar_evidence,
    "crm_mark_payment_paid": _validate_crm_payment_evidence,
    "media_save_to_memory":  _validate_media_memory_evidence,
    "send_followup":         _validate_owner_draft_evidence,
    "send_recovery":         _validate_owner_draft_evidence,
    # Phase 4B-2 wiring — tma_write always writes/updates a real Airtable
    # record (Leads/Tasks/ProjectsHub/Contacts), so the same record_id shape
    # check as airtable_add/airtable_update applies.
    "tma_write":             _validate_airtable_evidence,
}

# Write/action/sensitive tools that must fail closed if not in _EVIDENCE_VALIDATORS.
# Derived from tool_registry: requires_approval=True OR high_risk=True.
# Kept in sync manually — if a new write tool is added to tool_registry it must also
# get an entry in _EVIDENCE_VALIDATORS (or at minimum appear here to fail closed).
_WRITE_ACTION_TOOLS: frozenset[str] = frozenset(_EVIDENCE_VALIDATORS) | frozenset({
    # Future tools: add here until a proper validator is implemented.
})

# Keep for backward-compat with any code that still imports this name.
_STRUCTURED_ID_TOOLS = {k: "external_id" for k in _EVIDENCE_VALIDATORS}

# ══════════════════════════════════════════════════
# "No tool was called" detection patterns.
# If agent text matches a claim AND no result from one of the required
# tools is present in tool_results (by tool name, not text-guessing)
# → agent hallucinated a live check / action on an external system.
# ══════════════════════════════════════════════════

_NO_TOOL_CLAIMS: list[tuple[re.Pattern, frozenset[str]]] = [
    # Agent claims it checked / created a calendar event
    (
        re.compile(
            r"(בדקתי.*(ביומן|קלנדר)|אין חפיפות|הפגישה קבועה|קבעתי|נוצר ביומן|הוסף לקלנדר|"
            r"יוצר (את ה)?(פגיש|אירוע)|קובע (את ה)?(פגיש|אירוע)|פגישה חדשה)",
            re.UNICODE,
        ),
        frozenset({"calendar_get_events", "calendar_create_event"}),
    ),
    # Agent claims it read / drafted / sent email
    (
        re.compile(
            r"(בדקתי.*מייל|קראתי.*הודעות|לא.*מצאתי.*מייל|המייל.*נשלח|שלחתי.*מייל|טיוטה.*נשמר)",
            re.UNICODE,
        ),
        frozenset({"gmail_read", "gmail_draft", "gmail_send_draft"}),
    ),
    # CRM creation claims — דורשות airtable_add בלבד.
    # FOUND לא כותב airtable_add → אסור לשמש כ-evidence ליצירה.
    # גוף ראשון (הוספתי/שמרתי/רשמתי/תיעדתי) נוסף symmetric ל-UPDATE claims
    # (ראה BUG-NEW-09 למטה) — "הוספתי... 30 רשומות פעילות" חמק מה-Gate
    # בדוגמה חיה (09/07) כי ה-pattern הקודם תפס רק צורות גוף שלישי/סביל.
    (
        re.compile(
            r"(הרשומה נוצרה|נוצר ליד|הליד נוצר|נוסף ל-?Airtable|נוספה רשומה|ליד חדש נוצר|lead_capture:created|"
            r"(?<!לא )(?<!עדיין )(הוספתי|שמרתי|רשמתי|תיעדתי).{0,40}(רשומ|ליד|תיעוד|זיכרון ה?עסקי|Business Memory))",
            re.UNICODE,
        ),
        frozenset({"airtable_add"}),
    ),
    # CRM update claims — דורשות airtable_update או airtable_add.
    # BUG-NEW-09 (30/06 18:04): "עדכנתי את rec... — שם השתנה ל-..." חמק מה-Gate
    # כי הregex הקודם תפס רק "עודכן ב-Airtable"/"הליד עודכן" — לא גוף ראשון
    # ("עדכנתי") ולא ניסוח "X השתנה ל-Y" שמתלווה אליו לעתים קרובות.
    (
        re.compile(
            r"(עודכן ב-?Airtable|הליד עודכן|נשמר ב-?Airtable|lead_capture:updated|"
            r"עדכנתי את (rec\w+|ה(רשומה|ליד|שם|טלפון|פרטים))|"
            r"(שם|טלפון|פרט(ים)?) (השתנה|השתנו|עודכן) ל-)",
            re.UNICODE,
        ),
        frozenset({"airtable_update", "airtable_add"}),
    ),
    # CRM search/found claims — דורשות airtable_get או search_lead.
    (
        re.compile(
            r"(?<!לא )(מצאתי ליד קיים|הליד קיים|ליד קיים במערכת|lead_capture:found)",
            re.UNICODE,
        ),
        frozenset({"airtable_get", "search_lead"}),
    ),
    # Agent claims it can/did search or read a file in Drive (BUG-014: "אני
    # יכול לחפש בDrive" was said with no tool call at all)
    (
        re.compile(
            r"(אני יכול לחפש (ב-?)?Drive|חיפשתי (ב-?)?Drive|מצאתי (את ה)?קובץ|הקובץ נמצא|"
            r"קראתי (את ה)?קובץ|פתחתי (את ה)?קובץ)",
            re.UNICODE,
        ),
        frozenset({"search_drive", "read_drive_file"}),
    ),
    # BUG-V1-A32-SHEETS-FALSE-SUCCESS: agent claims a row was written to Sheets
    # without sheets_append evidence. Covers Hebrew variants of "row added",
    # "I added to sheet", "written to Sheets", etc.
    (
        re.compile(
            r"(השורה נוספה|הוספתי לגל?יון|הוספתי (ל-?Google Sheets|לשיטס|לגיל?יון)|"
            r"(נוסף|נוספו|נוספה) ל-?Google Sheets|כתוב לגל?יון|שורה נוספה לטבלה|"
            r"נכתב (ל-?|אל-?)(גיל?יון|גל?יון|שיטס?|Sheets)|"
            r"הנתונים (נכתבו|נוספו) (ל-?)?גל?יון|כתבתי (ל-?|אל-?)(גל?יון|שיטס))",
            re.UNICODE,
        ),
        frozenset({"sheets_append"}),
    ),
    # BUG-V1-FAKE-APPROVAL-STATE: agent emits "⏳ ממתינה לאישור" text without a
    # real approval having been queued. app.py injects a __approval_queued__
    # sentinel into tool_results_log whenever _queue_approval() actually runs.
    # Without that sentinel, this pattern fires → NO_TOOL_EVIDENCE_FALLBACK.
    (
        re.compile(
            r"(⏳.{0,25}(ממתינ[הת] לאישור|אישור הבעלים)|"
            r"הפעולה ממתינה לאישור|ממתינ[הת] לאישור הבעלים|"
            r"כשתאשר.{0,40}(תתווסף|יבוצע|תישלח|יישלח))",
            re.UNICODE,
        ),
        frozenset({"__approval_queued__"}),
    ),
    # BUG-V6-UI-STATE: agent speaks about approval UI (buttons/keyboard) — this
    # is Gateway-owned territory; agent must never mention UI controls.
    (
        re.compile(
            r"(לחץ על (כפתור|הכפתור)|לחץ ✅|לחץ ❌|"
            r"יש (כפתור|לחצן) (אישור|אשר|ביטול)|"
            r"נא ל?לחוץ|אשר באמצעות הכפתור|"
            r"הכפתור (שנשלח|שקיבלת|שמעלה))",
            re.UNICODE,
        ),
        frozenset({"__approval_queued__"}),
    ),
]

# ══════════════════════════════════════════════════
# "No tool was called" detection — NEGATIVE claims.
# Mirror image of _NO_TOOL_CLAIMS: the agent can fabricate a *failure*
# diagnosis just as easily as a fake success. Evidence here means "a tool
# was actually attempted" (ok True or False) — unlike _has_required_tool,
# a real ok=False result IS valid evidence for a failure claim.
# ══════════════════════════════════════════════════

_NEGATIVE_NO_TOOL_CLAIMS: list[tuple[re.Pattern, frozenset[str] | None]] = [
    # Agent claims the calendar action specifically failed / wasn't saved
    (
        re.compile(
            r"(הפגישה לא נשמרה|בעיה בתזמון)",
            re.UNICODE,
        ),
        frozenset({"calendar_get_events", "calendar_create_event"}),
    ),
    # Generic failure/error diagnosis — scoped to "no tool call at all this
    # turn", not a specific category, since this phrasing isn't calendar-only
    (
        re.compile(
            r"(לא הצלחתי לבדוק|לא ניתן לגשת|המערכת לא מגיבה|השגיאה היא)",
            re.UNICODE,
        ),
        None,  # None = evidence is "any tool result present", any category
    ),
    # BUG-SB-05: agent emits A32-like self-diagnosis ("לא ביצעתי שינוי",
    # "לא הצלחתי לאמת") with no tool attempt — blocks fabricated failure explanations.
    (
        re.compile(
            r"(לא ביצעתי שינוי|לא הצלחתי לאמת|לא אמת(י|תי) את הפעולה|"
            r"לא ניתן לאמת כרגע|לא בצעתי שינוי)",
            re.UNICODE,
        ),
        None,
    ),
    # BUG-V6-GMAIL: agent claims gmail failed / email wasn't sent without a tool attempt
    (
        re.compile(
            r"(המייל לא נשלח|לא הצלחתי לשלוח (את ה)?מייל|שליחת המייל נכשלה|"
            r"המייל לא הגיע|הדוא\"?ל לא נשלח)",
            re.UNICODE,
        ),
        frozenset({"gmail_draft", "gmail_send_draft"}),
    ),
]


# ══════════════════════════════════════════════════
# "Self-reported fix" claims (SPEC-FIX Section 5 / Section 6.6).
# The agent has no tool that performs a code change, test run, or deploy —
# so any claim of having fixed/changed the system's behavior is, by
# definition, never backed by tool evidence within a conversation turn.
# Unconditional block, unlike _NO_TOOL_CLAIMS which only fires when a
# specific tool category is missing.
# ══════════════════════════════════════════════════

_SELF_FIX_CLAIMS = re.compile(
    r"(?<!לא )(?<!עדיין )"
    r"(תיקנתי|מעכשיו אני|שיניתי את ה|זה יעבוד מעתה|זה כבר לא יקרה|"
    r"הבעיה (כבר )?נפתרה|הנושא נפתר|סגור הנושא)",
    re.UNICODE,
)

_SELF_FIX_FALLBACK = "קיבלתי דיווח באג. לא שיניתי את המערכת. צריך שינוי קוד, בדיקות ופריסה."


# ══════════════════════════════════════════════════
# Result Type
# ══════════════════════════════════════════════════

@dataclass
class VerifyResult:
    status: str   # "ok" | "warn" | "failed" | "hallucination" | "mismatch"
    reason: str = ""


# ══════════════════════════════════════════════════
# 1. verify_execution
# ══════════════════════════════════════════════════

def _content_text(content: Any) -> str:
    if isinstance(content, dict):
        return str(content.get("user_message") or content.get("external_id") or content)
    return str(content or "")


def verify_execution(tool_name: str, raw_output: Any) -> VerifyResult:
    """
    Checks whether a tool call actually succeeded.

    Rules:
    1. Tool in _EVIDENCE_VALIDATORS → run its validator; must pass explicitly.
    2. Tool in _WRITE_ACTION_TOOLS but NOT in _EVIDENCE_VALIDATORS →
       fail closed: no validator means no verified success claim.
    3. Read-only / listing tools (not in either set) →
       plain string accepted if non-empty; structured dict accepted.

    Called immediately after validate_tool_output().
    """
    if not raw_output:
        return VerifyResult("failed", "output is empty or None")

    validator = _EVIDENCE_VALIDATORS.get(tool_name)
    is_write = tool_name in _WRITE_ACTION_TOOLS

    if isinstance(raw_output, dict):
        if not raw_output.get("ok"):
            return VerifyResult("failed", _content_text(raw_output)[:160])

        if validator:
            result = validator(tool_name, raw_output)
            if result is not None:
                return result
            return VerifyResult("ok")

        if is_write:
            # Write/action tool with no registered validator — fail closed.
            # The tool must be added to _EVIDENCE_VALIDATORS before success claims are permitted.
            return VerifyResult(
                "failed",
                f"{tool_name}: execution result unverified — no evidence validator registered"
            )

        # Read-only / listing tool returning a structured dict — accepted.
        return VerifyResult("ok")

    # Plain string result
    raw_text = _content_text(raw_output)
    if raw_text.lstrip().startswith("❌"):
        return VerifyResult("failed", raw_text[:120])

    if validator or is_write:
        # Write/action tool must return a structured dict, not a plain string
        return VerifyResult(
            "failed",
            f"{tool_name}: expected structured result dict with ok=true; got plain string"
        )

    if not raw_text.strip():
        return VerifyResult("failed", "output is empty or None")

    return VerifyResult("ok")


# ══════════════════════════════════════════════════
# 2. verify_result_claim
# ══════════════════════════════════════════════════

# BUG-NEW-09: כולל גם גוף ראשון/עבר ("שמרתי"/"הוספתי"/"עדכנתי") — אותיות
# סופיות (ך/ם/ן/ף/ץ) לא תואמות regex substring כנגד צורת גוף-ראשון הרגילה
# (לדוג' "הוסף" עם ף סופית לא תואם "הוספתי" עם פ רגילה) — זו הייתה הסיבה
# שתביעת "הוספתי את הטלפון" חמקה מה-Gate בדוגמה החיה של 30/06 14:59.
_POSITIVE_CLAIMS = re.compile(
    r"(נשלח|בוצע|נוצר|נשמר|הוסף|עודכן|נרשם|"
    r"שמרתי|הוספתי|עדכנתי|יצרתי|שלחתי|רשמתי|ביצעתי|קבעתי)",
    re.UNICODE,
)
_NEGATIVE_CLAIMS = re.compile(r"לא מצאתי|אין תוצאות|לא נמצא", re.UNICODE)


def _all_failed(tool_results: list[dict]) -> bool:
    """True if every tool result content is a failed structured result or starts with ❌."""
    if not tool_results:
        return False
    for r in tool_results:
        content = r.get("content")
        if isinstance(content, dict):
            if content.get("ok"):
                return False
            continue
        if not (isinstance(content, str) and content.lstrip().startswith("❌")):
            return False
    return True


def _has_data(tool_results: list[dict]) -> bool:
    """True if any tool result contains non-error, non-empty content."""
    for r in tool_results:
        content = r.get("content", "")
        if isinstance(content, dict):
            if content.get("ok") or content.get("external_id"):
                return True
            continue
        if (isinstance(content, str)
                and content.strip()
                and not content.lstrip().startswith("❌")):
            return True
    return False


def verify_result_claim(agent_text: str, tool_results: list[dict]) -> VerifyResult:
    """
    Cross-checks what the agent says against what the tools actually returned.
    """
    if _POSITIVE_CLAIMS.search(agent_text) and _all_failed(tool_results):
        return VerifyResult(
            "hallucination",
            "agent claims success but all tool calls failed"
        )

    if _NEGATIVE_CLAIMS.search(agent_text) and _has_data(tool_results):
        return VerifyResult(
            "mismatch",
            "agent says 'not found' but tool results contain data"
        )

    return VerifyResult("ok")


# ══════════════════════════════════════════════════
# 3. sanitize_agent_response
# ══════════════════════════════════════════════════

_SAFE_FALLBACK   = "לא הצלחתי לבצע את הפעולה. אנא נסה שוב."
_MISMATCH_PREFIX = "⚠️ שים לב — ייתכן שהתוצאה אינה מדויקת.\n"
# BUG-SB-05: must NOT state action-status ("לא ביצעתי שינוי") without Ledger evidence.
# Neutral only — Gateway/Ledger is the single source of action-state truth.
_NO_TOOL_EVIDENCE_FALLBACK = "לא ניתן לאמת כרגע את מצב הפעולה. פנה למרכז הניהול לבירור."

# Single Speaker: when FEATURE_ACTION_GATEWAY=true, the Agent must NOT emit action-status
# text (נוסף/בוצע/נשלח etc.) — only the Gateway/compose_status_reply may do so.
# Also reused (see _has_write_tool_evidence / the generic structural gate below)
# as the trigger for an always-on, category-agnostic hallucination check.
# First-person forms (הוספתי/שמרתי/...) carry a (?<!לא )(?<!עדיין ) guard since
# they're common enough in negated/hedged sentences that a bare match would
# false-positive too often; the original passive forms are left as they were.
_AGENT_ACTION_STATUS_PATTERN = re.compile(
    r"(?<!\?)\b(נוסף|נוספה|נוספו|בוצע|בוצעה|נשלח|נשלחה|נשמר|נשמרה|"
    r"נוצר|נוצרה|עודכן|עודכנה|הושלם|הושלמה|"
    r"מושלם|המשימה נוספה|הפעולה בוצעה|הרשומה נוצרה)\b|"
    r"(?<!לא )(?<!עדיין )\b(הוספתי|שמרתי|עדכנתי|יצרתי|שלחתי|רשמתי|ביצעתי|קבעתי|תיעדתי)\b",
    re.UNICODE,
)
# BUG-SS-MULTITURN-PENDING-NARRATION: multi-turn task flows (e.g. a task
# missing its due date, completed on a later turn) surfaced a second class of
# Single-Speaker violation the completion-verb pattern above doesn't catch —
# the agent narrating that the action is *ready/pending approval* (true,
# evidenced, not a hallucination) in the same turn ActionGateway already sent
# its own canonical pending-approval message. Reuses the same wording already
# trusted elsewhere in this module (the __approval_queued__-gated NO_TOOL_CLAIMS
# entry below) — only the trigger differs: there it *permits* this phrasing
# when evidenced, here it additionally flags it for Single-Speaker suppression.
_AGENT_PENDING_STATUS_PATTERN = re.compile(
    r"(מוכנ[הת]?\s.{0,25}(לאישור|ממתינ)|ממתינ[הת]\s?(ל)?אישור|"
    r"⏳.{0,25}(ממתינ[הת] לאישור|אישור הבעלים)|"
    r"הפעולה ממתינה לאישור|ממתינ[הת] לאישור הבעלים|"
    r"כשתאשר.{0,40}(תתווסף|יבוצע|תישלח|יישלח))",
    re.UNICODE,
)
# BUG-FAKE-APPROVAL-INVITE: live incident — the agent (Claude, on this turn
# running claude-haiku-4-5-20251001) wrote "✅ המשימה מוכנה להוספה:\n...\n
# שלח מאשר כדי לאשר הוספה." without ever calling a tool at all this turn —
# no _queue_approval(), no EventBus item, no ActionContract. "מאשר"/"כן"
# afterward correctly found nothing pending (there genuinely was nothing),
# but the user had no way to know that from the fabricated message alone.
# This phrasing matched neither _AGENT_PENDING_STATUS_PATTERN above (no
# "לאישור"/"ממתינ" near "מוכנה") nor the __approval_queued__-gated
# NO_TOOL_CLAIMS entry below (no "⏳"/"ממתינה לאישור"/"כשתאשר") — a novel
# phrasing slipping past both enumerated patterns, the same "whack-a-mole"
# risk _has_write_tool_evidence's category-agnostic design already exists
# to close for completion claims. This is the parallel structural net for
# approval-invite claims: matches the actual call-to-action inviting the
# user to send a confirm word, regardless of the surrounding phrasing.
_AGENT_APPROVAL_INVITE_PATTERN = re.compile(
    r"(שלח\s*\*?(מאשר|כן)\*?|לחץ.{0,15}(מאשר|אשר)|"
    r"אשר\s*(כדי|על מנת|בבקשה)|"
    r"מוכנ[הת]?\s.{0,40}(להוספה|לביצוע|לשליחה|לעדכון|ליצירה|לשמירה)|"
    r"הצעד הבא.{0,30}אשר\b)",
    re.UNICODE,
)
# Was "הפעולה התקבלה. תוצאה תישלח בנפרד." — a false continuation claim with
# no real pending/queue behind it: when this gate fires, nothing actually
# follows up. Same claim-without-evidence class the rest of this module
# exists to block, just in the fallback copy itself.
_SINGLE_SPEAKER_FALLBACK = "לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת."


def _has_required_tool(tool_results: list[dict], required_tools: frozenset[str]) -> bool:
    """
    True if a non-failed result from one of required_tools is present.
    Identity-based (by tool name), not text-guessing — a tool call that
    itself failed does not count as evidence for the agent's claim.
    """
    return any(
        r.get("tool") in required_tools and r.get("ok", True)
        for r in tool_results
    )


def _has_write_tool_evidence(tool_results: list[dict]) -> bool:
    """
    True if at least one successful (ok=True) result from ANY tool in
    _WRITE_ACTION_TOOLS is present — deliberately "any write tool", not
    "any tool at all": read-only calls (airtable_get etc.) must not count
    as evidence for a completed-write claim. This is the structural,
    category-agnostic safety net behind _AGENT_ACTION_STATUS_PATTERN,
    complementing (not replacing) the specific per-category _NO_TOOL_CLAIMS
    patterns above — it exists to catch phrasing those don't yet enumerate.

    Live incident (09/07): 3x airtable_get (read-only) preceded a fabricated
    "✅ הוספתי... 30 רשומות פעילות" claim with zero write-tool calls. A naive
    "any tool call at all" check would have missed it — the reads would have
    silenced the guard even though nothing was actually written.
    """
    return any(
        r.get("tool") in _WRITE_ACTION_TOOLS and r.get("ok", True)
        for r in tool_results
    )


def _has_approval_queued_evidence(tool_results: list[dict]) -> bool:
    """
    True if this turn actually queued an approval (the __approval_queued__
    sentinel app.py's tool loop injects whenever _queue_approval() ran).
    Structural counterpart to _has_write_tool_evidence(), but for
    approval-invite claims rather than completion claims: an agent inviting
    the user to send a confirm word must be backed by a real pending
    EventBus item / ActionContract, not just text that reads that way.
    """
    return any(r.get("tool") == "__approval_queued__" for r in tool_results)


def _has_negative_evidence(tool_results: list[dict], required_tools: frozenset[str] | None) -> bool:
    """
    True if a real tool attempt grounds a *failure* claim. Unlike
    _has_required_tool, ok=False counts — a genuine failed call is exactly
    what would justify reporting a failure. required_tools=None means "any
    tool result at all" (used for category-agnostic failure phrasing).
    """
    if not tool_results:
        return False
    if required_tools is None:
        return True
    return any(r.get("tool") in required_tools for r in tool_results)


def sanitize_agent_response(agent_text: str, tool_results: list[dict],
                             _gateway_active: bool = False) -> str:
    """
    Final gate before the reply reaches the user.
    Replaces hallucinated text; adds a warning for mismatches.
    _gateway_active: pass True when FEATURE_ACTION_GATEWAY is on to enforce Single Speaker.
    """
    # Single Speaker: when Gateway is active, Agent must not emit action-status
    # text — covers both completion claims (_AGENT_ACTION_STATUS_PATTERN) and
    # pending/ready-for-approval narration (_AGENT_PENDING_STATUS_PATTERN); the
    # latter is truthful and evidenced (see BUG-SS-MULTITURN-PENDING-NARRATION
    # above) but still a second speaker describing a status ActionGateway's own
    # pending message already covers.
    if _gateway_active and (
        _AGENT_ACTION_STATUS_PATTERN.search(agent_text)
        or _AGENT_PENDING_STATUS_PATTERN.search(agent_text)
    ):
        # BUG-SS-FALLBACK-CONTRADICTION: if a pending-approval message was
        # already sent this turn (the __approval_queued__ sentinel — see
        # app.py's _queue_approval() call site), the agent's follow-up text
        # is a redundant/contradictory second message, not a hallucination
        # to correct. Replacing it with _SINGLE_SPEAKER_FALLBACK ("לא הצלחתי
        # לבצע את הפעולה...") falsely tells the user the action failed when
        # it is, correctly, still pending — suppress entirely instead.
        if any(r.get("tool") == "__approval_queued__" for r in tool_results):
            logger.info(
                "[A32] Single-Speaker: agent emitted action-status text after an approval "
                "was already queued this turn — suppressing (not replacing with fallback)"
            )
            return ""
        logger.warning("[A32] Single-Speaker: agent emitted action-status text, replacing")
        return _SINGLE_SPEAKER_FALLBACK

    # F52-PR6-DUP-PROSE (live incident): a real approval WAS queued this turn
    # (ActionGateway already sent its own "⏳ בקשת אישור..." prompt), yet the
    # agent's accompanying text still slipped through as a *second* message —
    # "✅ המשימה מוכנה להוספה...\n➡️ הצעד הבא המומלץ: שלח מאשר כדי לאשר...".
    # Neither pattern in the block above caught it: _AGENT_ACTION_STATUS_PATTERN
    # needs a completion verb ("נוספה" etc — "להוספה" isn't one), and
    # _AGENT_PENDING_STATUS_PATTERN needs "לאישור"/"ממתינ" within 25 chars of
    # "מוכנ[הת]" — "מוכנה להוספה" doesn't have either nearby. It DOES match
    # _AGENT_APPROVAL_INVITE_PATTERN (already defined above, reused here — see
    # BUG-FAKE-APPROVAL-INVITE), which today is only consulted at the
    # NO-TOOL-EVIDENCE gate further below and only when NO approval was
    # queued (the unevidenced/fabricated-invite case). This is the mirror,
    # evidenced case: a real __approval_queued__ sentinel is present, so this
    # is Single-Speaker duplication of ActionGateway's own prompt, not a
    # hallucination — suppress exactly like the block above (never replace
    # with a fallback, which would falsely read as failure while the action
    # is, correctly, still pending).
    if (
        _gateway_active
        and _AGENT_APPROVAL_INVITE_PATTERN.search(agent_text)
        and any(r.get("tool") == "__approval_queued__" for r in tool_results)
    ):
        logger.info(
            "[A32] Single-Speaker: agent emitted approval-invite prose after an approval "
            "was already queued this turn — suppressing (not replacing with fallback)"
        )
        return ""

    if _SELF_FIX_CLAIMS.search(agent_text):
        logger.error("[A32] SELF-REPORTED-FIX claim blocked (no code/deploy tool exists)")
        return _SELF_FIX_FALLBACK

    check = verify_result_claim(agent_text, tool_results)

    if check.status == "hallucination":
        logger.error(f"[A32] HALLUCINATION detected: {check.reason}")
        return _SAFE_FALLBACK

    if check.status == "mismatch":
        logger.warning(f"[A32] MISMATCH detected: {check.reason}")
        return _MISMATCH_PREFIX + agent_text

    # "No tool called" gate: agent claims a live check/action on an
    # external system but no result from a required tool is present.
    for claim_pattern, required_tools in _NO_TOOL_CLAIMS:
        if claim_pattern.search(agent_text) and not _has_required_tool(tool_results, required_tools):
            logger.error(
                f"[A32] NO-TOOL-EVIDENCE hallucination: "
                f"agent claims '{claim_pattern.pattern[:40]}' but no {sorted(required_tools)} tool result found"
            )
            return _NO_TOOL_EVIDENCE_FALLBACK

    # Generic structural safety net — always on, not gated by _gateway_active.
    # Complements _NO_TOOL_CLAIMS above: those patterns require a *specific*
    # tool category per claim wording (e.g. "CREATE claims" → airtable_add
    # only) and need a new entry whenever a new phrasing shows up. This check
    # is category-agnostic — it fires on ANY action-completion-shaped text
    # (_AGENT_ACTION_STATUS_PATTERN) as long as NO write tool succeeded this
    # turn, regardless of which verb/table/service was actually claimed.
    if _AGENT_ACTION_STATUS_PATTERN.search(agent_text) and not _has_write_tool_evidence(tool_results):
        logger.error(
            "[A32] NO-TOOL-EVIDENCE generic action-claim hallucination: "
            f"agent text matched action-status language but no successful "
            f"write-tool result found (checked: {sorted(_WRITE_ACTION_TOOLS)})"
        )
        return _NO_TOOL_EVIDENCE_FALLBACK

    # BUG-FAKE-APPROVAL-INVITE structural safety net — parallel to the
    # completion-claim net above, same rationale: _AGENT_PENDING_STATUS_PATTERN
    # and the __approval_queued__-gated NO_TOOL_CLAIMS entry both require
    # specific wording ("ממתינ"/"⏳"/"כשתאשר") and missed a live incident where
    # the agent invited the user to send a confirm word ("שלח מאשר כדי לאשר
    # הוספה") without ever calling a tool this turn. Category-agnostic: fires
    # on ANY approval-invite-shaped text as long as no approval was actually
    # queued this turn, regardless of the surrounding phrasing.
    if _AGENT_APPROVAL_INVITE_PATTERN.search(agent_text) and not _has_approval_queued_evidence(tool_results):
        logger.error(
            "[A32] NO-TOOL-EVIDENCE fake-approval-invite hallucination: "
            "agent text invites the user to confirm/approve but no "
            "__approval_queued__ evidence found this turn"
        )
        return _NO_TOOL_EVIDENCE_FALLBACK

    # Mirror gate: agent claims a live check/action *failed* with no tool
    # attempt at all to back that diagnosis up — a fabricated failure is
    # just as much a hallucination as a fabricated success.
    for claim_pattern, required_tools in _NEGATIVE_NO_TOOL_CLAIMS:
        if claim_pattern.search(agent_text) and not _has_negative_evidence(tool_results, required_tools):
            logger.error(
                f"[A32] NO-TOOL-EVIDENCE negative-claim hallucination: "
                f"agent claims failure '{claim_pattern.pattern[:40]}' but no tool attempt found"
            )
            return _NO_TOOL_EVIDENCE_FALLBACK

    return agent_text


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _make_result(
    tool: str,
    external_id: str = "",
    ok: bool = True,
    evidence: dict | None = None,
    user_message: str = "ok",
) -> dict:
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id,
        "evidence": evidence or {},
        "user_message": user_message,
    }


def _run_tests() -> bool:
    passed = failed = 0

    def check(desc: str, got, expected_status: str):
        nonlocal passed, failed
        ok = got.status == expected_status
        print(f"{'✅' if ok else '❌'} {desc}")
        if not ok:
            print(f"     got={got.status!r}  expected={expected_status!r}  reason={got.reason!r}")
            failed += 1
        else:
            passed += 1

    # ── verify_execution — structured dict contract ──────────

    # Airtable
    check("airtable_add success (rec-id 14 chars)",
          verify_execution("airtable_add", _make_result("airtable_add", "rec1234abcXYZpqrs")),
          "ok")
    check("airtable_add ok=False → failed",
          verify_execution("airtable_add", _make_result("airtable_add", ok=False, user_message="❌ Airtable error 422")),
          "failed")
    check("airtable_add empty output → failed",
          verify_execution("airtable_add", ""),
          "failed")
    check("airtable_add non-rec external_id → failed",
          verify_execution("airtable_add", _make_result("airtable_add", "not_a_rec")),
          "failed")
    check("airtable_add fake Hebrew rec id → failed",
          verify_execution("airtable_add", _make_result("airtable_add", "rec[שמור בהצלחה]")),
          "failed")
    check("airtable_add short rec id → failed",
          verify_execution("airtable_add", _make_result("airtable_add", "rec123")),
          "failed")
    check("airtable_add plain string (old format) → failed",
          verify_execution("airtable_add", "Created: rec1234abc"),
          "failed")

    # Sheets (must NOT check Airtable rec ID pattern)
    check("sheets_append success (spreadsheet_id in evidence)",
          verify_execution("sheets_append", _make_result(
              "sheets_append", "spreadsheet_abc",
              evidence={"spreadsheet_id": "1AbCdEf", "updated_range": "Sheet1!A1:C1"},
          )),
          "ok")
    check("sheets_append success (updated_range only)",
          verify_execution("sheets_append", _make_result(
              "sheets_append", "",
              evidence={"updated_range": "Sheet1!A5:D5", "rows_appended": 1},
          )),
          "ok")
    check("sheets_append missing all evidence → failed",
          verify_execution("sheets_append", _make_result("sheets_append", "")),
          "failed")
    check("sheets_append plain string → failed",
          verify_execution("sheets_append", "Row appended"),
          "failed")

    # Drive
    check("drive_upload success (file_id in evidence)",
          verify_execution("drive_upload", _make_result(
              "drive_upload", "file_abc123",
              evidence={"file_id": "1AbCdEf", "drive_url": "https://drive.google.com/file/d/1AbCdEf"},
          )),
          "ok")
    check("drive_upload success (external_id only)",
          verify_execution("drive_upload", _make_result("drive_upload", "file_xyz789")),
          "ok")
    check("drive_upload missing all evidence → failed",
          verify_execution("drive_upload", _make_result("drive_upload", "")),
          "failed")
    check("drive_create success (drive_url in evidence)",
          verify_execution("drive_create", _make_result(
              "drive_create", "",
              evidence={"drive_url": "https://drive.google.com/file/d/xyz"},
          )),
          "ok")

    # Gmail
    check("gmail_draft success (structured dict)",
          verify_execution("gmail_draft", _make_result("gmail_draft", "draft_xyz")),
          "ok")
    check("gmail_draft ok=False → failed",
          verify_execution("gmail_draft", _make_result("gmail_draft", ok=False, user_message="❌ Gmail 403")),
          "failed")
    check("gmail_draft plain string (old format) → failed",
          verify_execution("gmail_draft", "Draft created (id=draft_xyz)"),
          "failed")
    check("gmail_send_draft success (structured dict)",
          verify_execution("gmail_send_draft", _make_result("gmail_send_draft", "msg_abc123")),
          "ok")
    check("gmail_send_draft ok=False → failed",
          verify_execution("gmail_send_draft", _make_result("gmail_send_draft", ok=False, user_message="❌ Gmail 500")),
          "failed")
    check("gmail_send_draft plain string (old format) → failed",
          verify_execution("gmail_send_draft", "📧 טיוטה draft_abc נשלחה בהצלחה!"),
          "failed")

    # Calendar (htmlLink camelCase — matches Google API actual output)
    check("calendar_create_event success (event_id + htmlLink camelCase)",
          verify_execution("calendar_create_event", _make_result(
              "calendar_create_event", "evt_abc123",
              evidence={"htmlLink": "https://calendar.google.com/event?eid=abc"},
          )),
          "ok")
    check("calendar_create_event success (html_link snake_case also accepted)",
          verify_execution("calendar_create_event", _make_result(
              "calendar_create_event", "evt_abc123",
              evidence={"html_link": "https://calendar.google.com/event?eid=abc"},
          )),
          "ok")
    check("calendar_create_event ok=True but missing htmlLink → failed",
          verify_execution("calendar_create_event", _make_result("calendar_create_event", "evt_abc123")),
          "failed")
    check("calendar_create_event conflict (ok=False) → failed",
          verify_execution("calendar_create_event", _make_result(
              "calendar_create_event", ok=False,
              evidence={"conflict": "⚠️ כבר קיים ביומן: 'אירוע' (14:00)"},
              user_message="⚠️ כבר קיים ביומן: 'אירוע' (14:00). לקבוע בכל זאת?",
          )),
          "failed")
    check("calendar_create_event plain string (old format) → failed",
          verify_execution("calendar_create_event", "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00."),
          "failed")

    # CRM payment
    check("crm_mark_payment_paid success (paid_at in evidence)",
          verify_execution("crm_mark_payment_paid", _make_result(
              "crm_mark_payment_paid", "rec1234abcXYZpqrs",
              evidence={"paid_at": "2026-07-01T10:00:00", "record_id": "rec1234abcXYZpqrs"},
          )),
          "ok")
    check("crm_mark_payment_paid missing evidence → failed",
          verify_execution("crm_mark_payment_paid", _make_result("crm_mark_payment_paid", "")),
          "failed")
    check("crm_mark_payment_paid plain string → failed",
          verify_execution("crm_mark_payment_paid", "Payment marked paid"),
          "failed")

    # Unknown write/sensitive tool without validator — fail closed
    # (simulate: temporarily inject a tool into _WRITE_ACTION_TOOLS without adding a validator)
    import sys as _sys
    _self_mod = _sys.modules[__name__]
    _orig_write = _self_mod._WRITE_ACTION_TOOLS
    _self_mod._WRITE_ACTION_TOOLS = _orig_write | frozenset({"future_write_tool"})
    check("unknown write tool with dict output → fails closed",
          verify_execution("future_write_tool", {"ok": True, "tool": "future_write_tool",
                                                  "external_id": "x", "evidence": {}, "user_message": "ok"}),
          "failed")
    _self_mod._WRITE_ACTION_TOOLS = _orig_write  # restore

    # Read-only tool returning dict — accepted
    check("unknown read-only tool returning dict → ok",
          verify_execution("airtable_get", {"ok": True, "records": [{"id": "rec123"}],
                                             "tool": "airtable_get", "user_message": "ok"}),
          "ok")

    # Non-structured tools (read-only / listing tools)
    check("calendar_get_events plain string → ok",
          verify_execution("calendar_get_events", "📅 3 אירועים קרובים:"),
          "ok")
    check("calendar_get_events empty string → failed",
          verify_execution("calendar_get_events", ""),
          "failed")

    # ── verify_result_claim ──────────────────────
    failed_results = [{"content": _make_result("airtable_add", ok=False, user_message="❌ connection error")}]
    ok_results     = [{"content": _make_result("airtable_add", "rec1234")}]
    empty_results  = []

    check("agent says 'נשלח' but tool failed → hallucination",
          verify_result_claim("המייל נשלח בהצלחה!", failed_results),
          "hallucination")

    check("agent says 'בוצע' but tool failed → hallucination",
          verify_result_claim("הפעולה בוצעה.", failed_results),
          "hallucination")

    check("agent says 'לא מצאתי' but tool has data → mismatch",
          verify_result_claim("לא מצאתי כלום במערכת.", ok_results),
          "mismatch")

    check("agent says 'לא מצאתי' with empty results → ok",
          verify_result_claim("לא מצאתי כלום.", empty_results),
          "ok")

    check("agent correct success claim",
          verify_result_claim("הרשומה נוצרה.", ok_results),
          "ok")

    # ── sanitize_agent_response ──────────────────
    hallucinated = sanitize_agent_response("המייל נשלח!", failed_results)
    ok1 = hallucinated == _SAFE_FALLBACK
    print(f"{'✅' if ok1 else '❌'} agent says 'נשלח' but tool failed → sanitized to safe message")
    if not ok1:
        print(f"     got: {hallucinated!r}")
        failed += 1
    else:
        passed += 1

    normal = sanitize_agent_response("לא מצאתי לידים.", empty_results)
    ok2 = normal == "לא מצאתי לידים."
    print(f"{'✅' if ok2 else '❌'} agent says 'לא מצאתי' correctly → returned as-is")
    if not ok2:
        print(f"     got: {normal!r}")
        failed += 1
    else:
        passed += 1

    # ── "no tool called" gate — identity-based (by tool name), production format ──
    calendar_results = [{
        "tool": "calendar_create_event",
        "content": "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00.",
        "ok": True,
    }]
    failed_calendar_results = [{
        "tool": "calendar_create_event",
        "content": "❌ הפעולה לא הושלמה: calendar_create_event: missing evidence.htmlLink",
        "ok": False,
    }]

    no_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", []
    )
    ok3 = no_tool_calendar == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok3 else '❌'} agent claims calendar check with no tool result → blocked")
    if not ok3:
        print(f"     got: {no_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    with_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", calendar_results
    )
    ok4 = with_tool_calendar not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok4 else '❌'} agent claims calendar, real tool result present → passed through")
    if not ok4:
        print(f"     got: {with_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    failed_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", failed_calendar_results
    )
    ok4b = failed_tool_calendar == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok4b else '❌'} agent claims calendar but the tool call itself failed → blocked")
    if not ok4b:
        print(f"     got: {failed_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    no_tool_gmail = sanitize_agent_response(
        "בדקתי את המיילים שלך — לא מצאתי הודעות חדשות.", []
    )
    ok5 = no_tool_gmail == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok5 else '❌'} agent claims gmail read with no tool result → blocked")
    if not ok5:
        print(f"     got: {no_tool_gmail!r}")
        failed += 1
    else:
        passed += 1

    no_tool_gmail_draft = sanitize_agent_response("טיוטה נשמרה.", [])
    ok6 = no_tool_gmail_draft == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok6 else '❌'} agent claims 'טיוטה נשמרה' with no gmail_draft result → blocked")
    if not ok6:
        print(f"     got: {no_tool_gmail_draft!r}")
        failed += 1
    else:
        passed += 1

    no_tool_airtable = sanitize_agent_response("הרשומה נוצרה בהצלחה.", [])
    ok7 = no_tool_airtable == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok7 else '❌'} agent claims Airtable record created with no airtable tool result → blocked")
    if not ok7:
        print(f"     got: {no_tool_airtable!r}")
        failed += 1
    else:
        passed += 1

    with_tool_airtable = sanitize_agent_response(
        "הרשומה נוצרה בהצלחה.",
        [{"tool": "airtable_add", "content": "✅ רשומה נוספה | ID: rec123", "ok": True}],
    )
    ok8 = with_tool_airtable not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok8 else '❌'} agent claims Airtable record created, real tool result present → passed through")
    if not ok8:
        print(f"     got: {with_tool_airtable!r}")
        failed += 1
    else:
        passed += 1

    no_tool_drive = sanitize_agent_response("אני יכול לחפש בDrive ולמצוא את הקובץ.", [])
    ok9 = no_tool_drive == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok9 else '❌'} agent claims Drive search (BUG-014) with no search_drive result → blocked")
    if not ok9:
        print(f"     got: {no_tool_drive!r}")
        failed += 1
    else:
        passed += 1

    with_tool_drive = sanitize_agent_response(
        "מצאתי את הקובץ ב-Drive.",
        [{"tool": "search_drive", "content": "✅ נמצאו 1 קבצים | חוזה.pdf", "ok": True}],
    )
    ok10 = with_tool_drive not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok10 else '❌'} agent claims Drive file found, real search_drive result present → passed through")
    if not ok10:
        print(f"     got: {with_tool_drive!r}")
        failed += 1
    else:
        passed += 1

    # ── BUG-V1-A32-SHEETS-FALSE-SUCCESS ─────────
    no_tool_sheets = sanitize_agent_response("השורה נוספה לגליון.", [])
    ok11 = no_tool_sheets == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok11 else '❌'} BUG-V1-SHEETS: 'השורה נוספה' with no sheets_append → blocked")
    if not ok11:
        print(f"     got: {no_tool_sheets!r}")
        failed += 1
    else:
        passed += 1

    with_tool_sheets = sanitize_agent_response(
        "השורה נוספה לגליון.",
        [{"tool": "sheets_append", "content": "✅ שורה נוספה", "ok": True}],
    )
    ok12 = with_tool_sheets not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok12 else '❌'} BUG-V1-SHEETS: 'השורה נוספה' with real sheets_append → passed through")
    if not ok12:
        print(f"     got: {with_tool_sheets!r}")
        failed += 1
    else:
        passed += 1

    no_tool_sheets2 = sanitize_agent_response("הוספתי לגליון בדיקה.", [])
    ok13 = no_tool_sheets2 == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok13 else '❌'} BUG-V1-SHEETS: 'הוספתי לגליון' with no sheets_append → blocked")
    if not ok13:
        print(f"     got: {no_tool_sheets2!r}")
        failed += 1
    else:
        passed += 1

    # ── BUG-V1-FAKE-APPROVAL-STATE ───────────────
    no_approval_queued = sanitize_agent_response(
        "⏳ הפעולה ממתינה לאישור הבעלים. כשתאשר — השורה תתווסף.", []
    )
    ok14 = no_approval_queued == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok14 else '❌'} BUG-V1-FAKE-APPROVAL: '⏳ ממתינה לאישור' with no __approval_queued__ → blocked")
    if not ok14:
        print(f"     got: {no_approval_queued!r}")
        failed += 1
    else:
        passed += 1

    with_approval_queued = sanitize_agent_response(
        "⏳ הפעולה ממתינה לאישור הבעלים.",
        [{"tool": "__approval_queued__", "content": "⏳ ...", "ok": True}],
    )
    ok15 = with_approval_queued not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok15 else '❌'} BUG-V1-FAKE-APPROVAL: '⏳ ממתינה' with real __approval_queued__ sentinel → passed through")
    if not ok15:
        print(f"     got: {with_approval_queued!r}")
        failed += 1
    else:
        passed += 1

    # ── BUG-NEW-09: first-person success claims ("הוספתי"/"שמרתי") must be
    # caught the same way as the passive forms — this is the literal wording
    # from the live example (30/06 14:59) that previously slipped through. ──
    blocked_update = [{"content": _make_result("airtable_update", ok=False, user_message="❌ record_id 'rec_משה_יצחקוב' לא תקין")}]
    check_a = verify_result_claim("הוספתי את הטלפון, הפרטים שמורים.", blocked_update)
    print(f"{'✅' if check_a.status == 'hallucination' else '❌'} 'הוספתי...שמורים' after blocked airtable_update → hallucination")
    if check_a.status != "hallucination":
        failed += 1
    else:
        passed += 1

    check_b = verify_result_claim("עדכנתי את הרשומה בהצלחה.", blocked_update)
    print(f"{'✅' if check_b.status == 'hallucination' else '❌'} 'עדכנתי' after blocked airtable_update → hallucination")
    if check_b.status != "hallucination":
        failed += 1
    else:
        passed += 1

    # ── live incident (09/07): "הוספתי... 30 רשומות פעילות" with zero tool
    # calls this turn slipped through _NO_TOOL_CLAIMS entirely — the CRM
    # creation pattern only matched third-person/passive forms, unlike the
    # UPDATE pattern above (already fixed for BUG-NEW-09). ──
    no_tool_create_first_person = sanitize_agent_response(
        "✅ הוספתי לזיכרון העסקי. יש כעת 30 רשומות פעילות.", []
    )
    ok16 = no_tool_create_first_person == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok16 else '❌'} live incident: 'הוספתי...רשומות פעילות' with no airtable_add result → blocked")
    if not ok16:
        print(f"     got: {no_tool_create_first_person!r}")
        failed += 1
    else:
        passed += 1

    with_tool_create_first_person = sanitize_agent_response(
        "✅ הוספתי את העדכון לזיכרון העסקי.",
        [{"tool": "airtable_add", "content": "✅ רשומה נוספה | ID: rec123", "ok": True}],
    )
    ok17 = with_tool_create_first_person not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok17 else '❌'} 'הוספתי' with real airtable_add result present → passed through")
    if not ok17:
        print(f"     got: {with_tool_create_first_person!r}")
        failed += 1
    else:
        passed += 1

    for verb in ("שמרתי", "רשמתי", "תיעדתי"):
        text = f"✅ {verb} את הרשומה בזיכרון העסקי."
        got = sanitize_agent_response(text, [])
        okv = got == _NO_TOOL_EVIDENCE_FALLBACK
        print(f"{'✅' if okv else '❌'} '{verb}' with no airtable_add result → blocked")
        if not okv:
            print(f"     got: {got!r}")
            failed += 1
        else:
            passed += 1

    no_false_positive = sanitize_agent_response(
        "לא הוספתי רשומה כי חסר לי מידע.", []
    )
    ok18 = no_false_positive not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok18 else '❌'} 'לא הוספתי' (negation) does not false-positive trigger the creation gate")
    if not ok18:
        print(f"     got: {no_false_positive!r}")
        failed += 1
    else:
        passed += 1

    # ── Generic structural safety net (_AGENT_ACTION_STATUS_PATTERN +
    # ── Single-Speaker fallback message no longer promises a fake
    # continuation ("תוצאה תישלח בנפרד" — nothing actually follows up when
    # this gate fires). DoD: (1) when the gate fires, the user gets the new
    # message, not the old false-continuation one; (2) trigger conditions
    # are unchanged — still only fires when _gateway_active=True AND the
    # action-status pattern matches; still passed-through otherwise. ──
    print("\n── Single-Speaker fallback message ───")

    ss_text = "✅ הפעולה בוצעה בהצלחה."
    ss_result = sanitize_agent_response(ss_text, [], _gateway_active=True)
    ok_ss1 = ss_result == _SINGLE_SPEAKER_FALLBACK
    print(f"{'✅' if ok_ss1 else '❌'} Single-Speaker gate fires when gateway_active + action-status text")
    if not ok_ss1:
        print(f"     got: {ss_result!r}")
        failed += 1
    else:
        passed += 1

    ok_ss2 = ss_result == "לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת."
    print(f"{'✅' if ok_ss2 else '❌'} fallback text no longer promises a fake continuation")
    if not ok_ss2:
        print(f"     got: {ss_result!r}")
        failed += 1
    else:
        passed += 1

    ss_no_gateway = sanitize_agent_response(ss_text, [{"tool": "airtable_add", "content": "✅ ok", "ok": True}], _gateway_active=False)
    ok_ss3 = ss_no_gateway not in (_SINGLE_SPEAKER_FALLBACK, _NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok_ss3 else '❌'} regression: gateway_active=False → Single-Speaker gate does not fire (unchanged trigger condition)")
    if not ok_ss3:
        print(f"     got: {ss_no_gateway!r}")
        failed += 1
    else:
        passed += 1

    ss_no_action_text = sanitize_agent_response("בטח, איך אפשר לעזור?", [], _gateway_active=True)
    ok_ss4 = ss_no_action_text == "בטח, איך אפשר לעזור?"
    print(f"{'✅' if ok_ss4 else '❌'} regression: gateway_active=True but no action-status text → gate does not fire")
    if not ok_ss4:
        print(f"     got: {ss_no_action_text!r}")
        failed += 1
    else:
        passed += 1

    # ── Generic structural safety net (_AGENT_ACTION_STATUS_PATTERN +
    # _has_write_tool_evidence) — category-agnostic, always-on. DoD per the
    # design review: (1) the original live incident is blocked, (2) a real
    # GET+CREATE turn is NOT blocked (must not break the common case),
    # (3) a *failed* airtable_add + success claim is still blocked (the
    # actual 422 Real Estate/SaaS scenario), (4) a verb not in any specific
    # _NO_TOOL_CLAIMS list is still caught, generically, with no new regex
    # entry needed. ──
    print("\n── generic structural safety net ─────")

    # 1. Original incident: 3x read-only GET, zero writes, fabricated claim.
    reads_only = [
        {"tool": "airtable_get", "content": "28 records", "ok": True},
        {"tool": "airtable_get", "content": "28 records", "ok": True},
        {"tool": "airtable_get", "content": "28 records", "ok": True},
    ]
    g1 = sanitize_agent_response("✅ הוספתי לזיכרון העסקי. יש כעת 30 רשומות פעילות.", reads_only)
    okg1 = g1 == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if okg1 else '❌'} generic guard: reads-only + fabricated claim → blocked (naive 'any tool' check would have missed this)")
    if not okg1:
        print(f"     got: {g1!r}")
        failed += 1
    else:
        passed += 1

    # 2. Regression: real GET + real successful CREATE + matching claim → NOT blocked.
    reads_then_write = reads_only + [
        {"tool": "airtable_add", "content": "✅ רשומה נוספה | ID: rec123", "ok": True},
    ]
    g2 = sanitize_agent_response("✅ הוספתי לזיכרון העסקי. יש כעת 29 רשומות פעילות.", reads_then_write)
    okg2 = g2 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if okg2 else '❌'} generic guard: real airtable_add ok=True + matching claim → passed through (common case not broken)")
    if not okg2:
        print(f"     got: {g2!r}")
        failed += 1
    else:
        passed += 1

    # 3. The actual 422-style scenario: airtable_add attempted but failed,
    # agent still claims success — must be blocked.
    failed_write = [{"tool": "airtable_add", "content": "❌ Airtable 422: invalid select value", "ok": False}]
    g3 = sanitize_agent_response("✅ הוספתי לזיכרון העסקי בהצלחה.", failed_write)
    okg3 = g3 in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if okg3 else '❌'} generic guard: airtable_add ok=False + success claim → still blocked")
    if not okg3:
        print(f"     got: {g3!r}")
        failed += 1
    else:
        passed += 1

    # 4. A verb/phrasing not present in any specific _NO_TOOL_CLAIMS entry —
    # caught generically via _AGENT_ACTION_STATUS_PATTERN, no new regex needed.
    g4 = sanitize_agent_response("הפעולה בוצעה והמידע נשמר במערכת.", [])
    okg4 = g4 == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if okg4 else '❌'} generic guard: unenumerated passive phrasing with zero tools → blocked without a category-specific pattern")
    if not okg4:
        print(f"     got: {g4!r}")
        failed += 1
    else:
        passed += 1

    print(f"\n{'═'*45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)


# ══════════════════════════════════════════════════
# CXX Tests — ActionResult → A32 integration
# ══════════════════════════════════════════════════

def _run_cxx_tests() -> bool:
    """
    בדיקות CXX:
    1. FOUND ממופה ל-airtable_get, ok=True
    2. CREATED ממופה ל-airtable_add, ok=True
    3. A32 דוחה "נוצר ליד" כשיש רק evidence של airtable_get
    4. A32 מאשר "מצאתי ליד קיים" כשיש evidence של airtable_get
    """
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond:
            print(f"  ✅ {desc}"); passed += 1
        else:
            print(f"  ❌ {desc}"); failed += 1

    print("\n── CXX A32 Integration Tests ──")

    # בדיקה 1 — FOUND → airtable_get
    found_entry = {
        "tool": "airtable_get",
        "content": "lead_capture:found:record_id=recEXIST",
        "ok": True,
    }
    chk("FOUND maps to airtable_get",
        found_entry["tool"] == "airtable_get")
    chk("FOUND ok=True",
        found_entry["ok"] is True)

    # בדיקה 2 — CREATED → airtable_add
    created_entry = {
        "tool": "airtable_add",
        "content": "lead_capture:created:record_id=recNEW123",
        "ok": True,
    }
    chk("CREATED maps to airtable_add",
        created_entry["tool"] == "airtable_add")
    chk("CREATED ok=True",
        created_entry["ok"] is True)

    # בדיקה 3 — A32 דוחה "נוצר ליד" כשיש רק airtable_get
    text_created = "נוצר ליד חדש במערכת"
    only_get = [{"tool": "airtable_get", "content": "lead found", "ok": True}]
    result3 = sanitize_agent_response(text_created, only_get)
    chk("A32 blocks 'נוצר ליד' when only airtable_get present",
        result3 == _NO_TOOL_EVIDENCE_FALLBACK)

    # בדיקה 4 — A32 מאשר "נוצר ליד" כשיש airtable_add
    with_add = [{"tool": "airtable_add", "content": "lead_capture:created:record_id=rec123", "ok": True}]
    result4 = sanitize_agent_response(text_created, with_add)
    chk("A32 passes 'נוצר ליד' when airtable_add present",
        result4 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK))

    # בדיקה 5 — A32 מאשר "מצאתי ליד קיים" כשיש airtable_get
    text_found = "מצאתי ליד קיים במערכת"
    result5 = sanitize_agent_response(text_found, only_get)
    chk("A32 passes 'מצאתי ליד קיים' when airtable_get present",
        result5 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK))

    # בדיקה 6 — A32 דוחה "מצאתי ליד קיים" בלי שום tool
    result6 = sanitize_agent_response(text_found, [])
    chk("A32 blocks 'מצאתי ליד קיים' with no tool result",
        result6 == _NO_TOOL_EVIDENCE_FALLBACK)

    # בדיקה 7 — tool loop לא נשבר (רשומה רגילה עוברת)
    normal_entry = [{"tool": "airtable_get", "content": "3 leads found", "ok": True}]
    result7 = sanitize_agent_response("מצאתי 3 לידים.", normal_entry)
    chk("Normal flow not broken — unrelated text passes through",
        result7 == "מצאתי 3 לידים.")

    print(f"  {'─'*38}")
    print(f"  CXX Tests: {passed} passed, {failed} failed\n")
    return failed == 0
