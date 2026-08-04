# core/router/router.py — CORE_02 Soft Router
# Orchestrator only. Calls 4 sub-routers → returns one RouteDecision.
# No business logic. No DB writes. No agent calls.

from __future__ import annotations
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date as _date
from typing import TYPE_CHECKING

from .route_decision  import RouteDecision, Intent, Handler, Risk, RouterDomain
from .channel_router  import detect_channel, resolve_tool_for_channel
from .intent_router   import detect_intent, count_engineering_markers, detect_ambiguous_phrase
from .domain_router   import detect_domain
from .risk_router     import detect_risk

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)

INTENT_CONFIDENCE_THRESHOLD = 0.75

_STRUCTURED_CREATE_TASK_RE = re.compile(
    r"^\s*(?:צור|תיצור)\s+משימה\s*:?\s*(?P<title>.+?)\s*$"
)
_CREATE_TASK_DATE_RE = re.compile(r"(?P<date>\d{1,2}[./-]\d{1,2}[./-]\d{2,4})")
_CREATE_TASK_TIME_RE = re.compile(r"בשעה\s*(?P<hour>\d{1,2})\s*:\s*(?P<minute>\d{2})")
_CREATE_TASK_PREFIX_RE = re.compile(r"^(?:>\s*)?(?:Eli|אלי)\s*:\s*", re.IGNORECASE)
_CREATE_TASK_DATE_WORD_MARKER_RE = re.compile(r"\bעד\b")
# BUG-154: מסמן-קידומת בסגנון "ל־5/8/26" — ל ואחריו ישירות (עם רווח סופי
# אופציונלי) מקף עברי/hyphen/en-dash/em-dash, ממש לפני התאריך עצמו. נבדק
# רק בתוך המחרוזת שקודמת ל-date_match.start(), עם עוגן $, לעולם לא חיפוש
# על כל הטקסט — "ל" לבדה היא אות/קידומת עברית נפוצה מדי לשמש כמסמן עצמאי.
# מקף עברי (maqaf, U+05BE)/en-dash (U+2013)/em-dash (U+2014) מקודדים כ-\uXXXX
# (לא הליטרלים עצמם) כדי למנוע בלבול חזותי/mojibake בקוד המקור; "-" (hyphen,
# ASCII) נשאר ליטרל רגיל.
_CREATE_TASK_DATE_PREFIX_MARKER_RE = re.compile(r"ל[\u05be\-\u2013\u2014]\s*$")
_CREATE_TASK_QUOTE_PAIRS = (("\"", "\""), ("'", "'"), ("(", ")"), ("[", "]"), ("{", "}"))


@dataclass(frozen=True)
class DeterministicTaskParse:
    title: str | None = None
    due_date: str | None = None
    due_time: str | None = None
    matched: bool = False
    uncertain: bool = False

    @property
    def certain(self) -> bool:
        return self.matched and not self.uncertain and bool(self.title)

    def business_identity(self) -> dict:
        """Identity-only payload; it is not written to Airtable.

        BUG-156: due_time is deliberately excluded here. The Tasks table's
        due-date field is Airtable type "date", not "dateTime" — no live
        field persists a time value, so a fingerprint that included due_time
        would distinguish two requests (e.g. same title/date, different
        time) whose actual Airtable write ends up byte-identical, promising
        more identity/dedup precision than the write payload can honor.
        due_time is still parsed and validated (parse_deterministic_create_
        task() still fail-closes on a malformed time) and still shown to the
        user before approval (see app.py's _queue_deterministic_create_task()
        due-time note) — it's excluded from the identity/fingerprint only.
        """
        fields = {"title": self.title or ""}
        if self.due_date:
            fields["due_date"] = self.due_date
        return {"table": "Tasks", "fields": fields}


def _normalize_create_task_input(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("\u00a0", " ")
    for _ in range(4):
        value = value.strip()
        value = _CREATE_TASK_PREFIX_RE.sub("", value, count=1).strip()
        if len(value) >= 2 and any(
            value.startswith(opening) and value.endswith(closing)
            for opening, closing in _CREATE_TASK_QUOTE_PAIRS
        ):
            for opening, closing in _CREATE_TASK_QUOTE_PAIRS:
                if value.startswith(opening) and value.endswith(closing):
                    value = value[1:-1].strip()
                    break
            continue
        if value.startswith(">"):
            value = value[1:].strip()
            continue
        break
    return " ".join(value.split())


def parse_deterministic_create_task(text: str) -> DeterministicTaskParse:
    normalized = _normalize_create_task_input(text)
    match = _STRUCTURED_CREATE_TASK_RE.fullmatch(normalized)
    if not match:
        return DeterministicTaskParse()

    body = match.group("title").strip()
    if not body:
        return DeterministicTaskParse(matched=True, uncertain=True)

    date_match = _CREATE_TASK_DATE_RE.search(body)
    date_marker = _CREATE_TASK_DATE_WORD_MARKER_RE.search(body)
    if date_marker is None and date_match is not None:
        # BUG-154: "ל־5/8/26"-style marker — only checked immediately before
        # the date itself (never a whole-body search; see the constant's own
        # comment for why). None here means no recognized marker at all —
        # falls through to the uncertain=True guard below, same fail-closed
        # outcome as any other unrecognized date-marker shape.
        date_marker = _CREATE_TASK_DATE_PREFIX_MARKER_RE.search(
            body[:date_match.start()]
        )
    time_marker = re.search(r"בשעה", body)
    time_match = _CREATE_TASK_TIME_RE.search(body)
    uncertain = False
    due_date = None
    due_time = None

    # Natural-language placeholders such as "עד לתאריך Y" remain a valid
    # task title.  We only enter clarification when the user supplied a
    # date/time-shaped value that cannot be parsed safely.
    date_like_token = re.search(r"\d+[./-]\d+", body)
    time_like_token = re.search(r"\d{1,2}\s*:\s*\d{1,2}", body)
    if date_like_token and not date_match:
        uncertain = True
    if time_marker and time_like_token and not time_match:
        uncertain = True
    if date_match:
        raw_date = date_match.group("date").replace(".", "/").replace("-", "/")
        day, month, year = (int(part) for part in raw_date.split("/"))
        if year < 100:
            year += 2000
        try:
            due_date = _date(year, month, day).isoformat()
        except ValueError:
            uncertain = True
        if date_marker is None or date_marker.start() > date_match.start():
            uncertain = True
    if time_match:
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute"))
        if hour > 23 or minute > 59:
            uncertain = True
        else:
            due_time = f"{hour:02d}:{minute:02d}"

    title = body
    if date_marker and date_match and date_marker.start() < date_match.start():
        title = body[:date_marker.start()].strip(" ,:;-–—")
    if not title:
        uncertain = True
    return DeterministicTaskParse(
        title=title or None,
        due_date=due_date,
        due_time=due_time,
        matched=True,
        uncertain=uncertain,
    )


def deterministic_create_task_title(text: str) -> str | None:
    """Return the title only for a certain, normalized deterministic request."""
    parsed = parse_deterministic_create_task(text)
    return parsed.title if parsed.certain else None


def route_request(
    text:                str,
    channel_raw:         str,
    identity:            "Identity",
    domain_from_channel: str = "",
    envelope_id:         str = "",
) -> RouteDecision:
    """
    text + channel + identity → RouteDecision

    domain_from_channel: comes from config.get_domain(to_number) in webhook.
    envelope_id: C94 Stage ג — the caller's IngressEnvelope id, if it built
    one (currently only Telegram, via app.py/core/telegram_ingress_adapter.py).
    Optional/"" for any other caller — forwarded to capture_router so a
    classify_ingress() failure's EvidenceTrace can link back to its Envelope.
    """
    # 1. Channel
    channel = detect_channel(channel_raw)

    # 2. Intent
    intent, confidence, matched_rule = detect_intent(text)
    if confidence < INTENT_CONFIDENCE_THRESHOLD:
        intent = Intent.UNKNOWN

    # 2b. Engineering / meta-safety override (SPEC-ROUTER-06).
    # Runs AFTER business-intent detection but takes priority over it: a
    # bug report from staff/owner must never be treated as a business
    # action just because it incidentally contains words like "עדכן ליד" —
    # and must not silently fall through to the general Agent via
    # intent=unknown either (BUG-NEW-11b regression: that path was observed
    # live querying Leads on an engineering message).
    marker_count = count_engineering_markers(text)
    is_staff = identity.role in (
        "owner", "partner", "manager", "employee",
    )
    if is_staff and marker_count >= 2:
        intent = Intent.ENGINEERING_NOTE

    # 3. Domain
    if intent == Intent.ENGINEERING_NOTE:
        domain = RouterDomain.INTERNAL
    else:
        domain, _ = detect_domain(
            text                 = text,
            domain_from_channel  = domain_from_channel,
            domain_from_identity = identity.domain_id,
        )

    # 4. Risk + Handler
    if intent == Intent.ENGINEERING_NOTE:
        risk, handler, needs_approval = Risk.READ_ONLY, Handler.ENGINEERING_NOTE, False
    else:
        risk, handler, needs_approval = detect_risk(
            intent = intent,
            role   = identity.role,
            domain = domain,
        )

    # פקודות משימה מובנות שלמות מספיקות ל-Coordinator כדי לבנות contract אישור.
    # ניסוחים רחבים יותר נשארים במסלול Agent; זהו שער דטרמיניסטי ומצומצם בכוונה.
    _create_task_parse = parse_deterministic_create_task(text)
    if (
        intent == Intent.CREATE_TASK
        and _create_task_parse.certain
        and identity.role not in ("lead", "guest", "readonly")
    ):
        risk, handler, needs_approval = Risk.NEEDS_APPROVAL, Handler.TOOL, True

    # 4b. Capture Policy (Stage 3 / C89 integration) — observability only.
    # Gate is identity.is_internal alone, with NO intent filter — this must
    # match app.py's real invocation condition for handle_lead_candidate()
    # exactly, or RouteDecision would show capture_tier=None for messages
    # LCH still independently auto-writes (e.g. an explicit "תוסיף ליד: ..."
    # that intent_router already matched as CREATE_LEAD with high confidence
    # — LCH runs on it regardless of what intent detection decided).
    capture_tier, capture_reason, raw_ref = None, "", ""
    capture_ic = None
    if identity.is_internal:
        from .capture_router import classify_capture_ic, _WRITE_WORTHY_TIERS
        capture_ic = classify_capture_ic(
            text, chat_id=getattr(identity, "memory_key", ""), envelope_id=envelope_id,
        )
        # C94 Stage ג: capture_ic can now legitimately be None (classify_ingress()
        # itself failed, already logged + traced inside classify_capture_ic) —
        # same as the identity.is_internal=False case above, handled the same way.
        if capture_ic is not None:
            capture_tier = capture_ic.tier if capture_ic.tier in _WRITE_WORTHY_TIERS else None
            capture_reason = capture_ic.reason
            raw_ref = capture_ic.raw_ref

    # 5. Channel-specific tool override
    tool_override = resolve_tool_for_channel(intent, channel)

    # 6. Restricted flow resolution
    restricted   = False
    notify_owner = False
    tool_allowed = True

    if handler == Handler.RESTRICTED:
        # Agent talks naturally; tools are silently blocked; owner gets a log.
        restricted   = True
        notify_owner = True
        tool_allowed = False
        handler      = Handler.AGENT

    if handler == Handler.BLOCK:
        # Hard block (rate-limit / extreme case) — no tools.
        tool_allowed = False

    # 7. Edge cases / response overrides
    if intent == Intent.ENGINEERING_NOTE:
        handler           = Handler.ENGINEERING_NOTE
        tool_allowed       = False
        response_override = "קיבלתי דיווח באג. לא שיניתי את המערכת. צריך שינוי קוד, בדיקות ופריסה."

    elif capture_ic is not None and capture_ic.tier == 4:
        # BUG-056 (C89 Tier 4 stop-gate): table/export/log/bot-output pasted
        # in must stop routing HERE — never reach the Agent/tools, regardless
        # of what keyword (e.g. "הוסף משימה") intent_router happened to match
        # inside the pasted text. handle_lead_candidate() already refuses to
        # auto-write for tier>=4, but only this router-level override stops
        # the message from reaching Handler.AGENT at all.
        handler            = Handler.CLARIFY
        tool_allowed       = False
        response_override  = (
            "📄 זה נראה כמו טבלה/ייצוא/פלט מודבק — לא ביצעתי שום פעולה אוטומטית. "
            "אם התכוונת לבקש משהו ספציפי, כתוב את זה במשפט רגיל."
        )

    elif intent == Intent.UNKNOWN:
        # BUG-IC-01/C89: before falling through to the general Agent (which
        # has full tool access and might decide on its own to "check" Gmail/
        # Calendar/Airtable), check whether this is a known ambiguous short
        # phrase ("סטטוס", "בדיקות מערכת", "מה המצב", "למלא משימות"). Those
        # get a clarifying question instead of silent broad-tool guessing.
        _ambiguous_q = detect_ambiguous_phrase(text)
        if _ambiguous_q:
            handler            = Handler.CLARIFY
            response_override  = _ambiguous_q
        else:
            handler            = Handler.AGENT   # safety net
            response_override  = ""

    elif intent == Intent.CREATE_TASK and _create_task_parse.uncertain:
        handler = Handler.CLARIFY
        tool_allowed = False
        needs_approval = False
        response_override = (
            "לא בטוח שהבנתי את כותרת המשימה או את התאריך/שעה. "
            "נא לנסח מחדש, בלי תיקון אוטומטי של שגיאות כתיב."
        )

    elif risk == Risk.NEEDS_APPROVAL and confidence < 0.85 and not restricted:
        handler           = Handler.CLARIFY
        response_override = f"לא בטוח שהבנתי — כוונתך: {intent}?"

    elif handler == Handler.BLOCK:
        response_override = "פעולה זו אינה זמינה. לסיוע, פנה לאליהו."

    else:
        response_override = ""

    decision = RouteDecision(
        channel           = channel,
        intent            = intent,
        domain            = domain,
        risk              = risk,
        handler           = handler,
        needs_approval    = needs_approval,
        confidence        = confidence,
        matched_rule      = matched_rule,
        llm_classified    = False,
        response_override = response_override,
        restricted        = restricted,
        notify_owner      = notify_owner,
        tool_allowed      = tool_allowed,
        capture_tier      = capture_tier,
        capture_reason    = capture_reason,
        raw_ref           = raw_ref,
        capture_ic        = capture_ic,
    )
    if tool_override:
        decision.matched_rule = f"{matched_rule} [tool:{tool_override}]"

    logger.info(decision.to_log())
    return decision
