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
    r"^\s*(?:צור|תיצור|הוסף|תוסיף)\s+משימ(?:ה|ת)\s*:?\s*(?P<title>.+?)\s*$"
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

# PA-01 — same fail-closed shape as _STRUCTURED_CREATE_TASK_RE above: the
# ENTIRE message must be "<verb> [את ][ה]משימה[/טאסק/task] <reference>", not
# just a loose intent-regex match somewhere in a longer sentence. Verb group
# mirrors intent_router.py's UPDATE_TASK/COMPLETE_TASK rules (עדכן/שנה/
# תעדכן/סגור/סיים/השלם/סמן/mark/complete/update) — intent detection already
# guarantees one of those verbs plus a task noun matched *somewhere*; this
# only additionally requires the strict verb-noun-reference order and a
# non-empty reference before Handler.TOOL is safe to assign.
_STRUCTURED_TASK_REF_RE = re.compile(
    r"^\s*(?:עדכן|תעדכן|שנה|תשנה|סגור|תסגור|סיים|תסיים|השלם|תשלים|סמן|תסמן"
    r"|mark|complete|update)\s+(?:את\s+)?(?:ה)?(?:משימ(?:ה|ת)|טאסק|task)"
    r"\s*:?\s*(?P<reference>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DeterministicTaskRefParse:
    reference: str | None = None
    matched:   bool = False
    uncertain: bool = False

    @property
    def certain(self) -> bool:
        return self.matched and not self.uncertain and bool(self.reference)


def parse_deterministic_task_reference(text: str) -> DeterministicTaskRefParse:
    """UPDATE_TASK/COMPLETE_TASK counterpart of parse_deterministic_create_task.

    Only classifies whether the message is a structured enough task
    reference for the router to hand off deterministically — actual entity
    resolution (0/1/many matches) stays owned by task_resolvers.resolve_task
    downstream, unchanged.
    """
    normalized = _normalize_create_task_input(text)
    match = _STRUCTURED_TASK_REF_RE.fullmatch(normalized)
    if not match:
        return DeterministicTaskRefParse()
    reference = match.group("reference").strip()
    if not reference:
        return DeterministicTaskRefParse(matched=True, uncertain=True)
    return DeterministicTaskRefParse(reference=reference, matched=True)


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

        BUG-TASK-01: table/field keys must match exactly what
        core/router/task_builders.py::build_create_task_proposal() /
        core/turn_coordinator_runtime.py::gateway_call() actually dispatch
        (Tables.TASKS / TaskFields.NAME / TaskFields.DUE_DATE) — this identity
        payload becomes the ActionGateway's business_action_fingerprint basis
        (core/action_gateway.py propose_action()), which
        tools/dispatcher.py::_validate_execution_proof() independently
        recomputes from the real dispatched payload (contract.
        normalized_payload) at execution time. Using ad-hoc "Tasks"/"title"
        keys here — a different table alias and field name than the write
        payload — made that recomputed fingerprint never equal the stored
        one, so every approved deterministic create_task contract failed
        Dispatcher's proof check ("approval-sensitive execution proof does
        not match the action payload") regardless of the task content.
        """
        from airtable_schema import Tables, TaskFields
        fields = {TaskFields.NAME: self.title or ""}
        if self.due_date:
            fields[TaskFields.DUE_DATE] = self.due_date
        return {"table": Tables.TASKS, "fields": fields}


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
        # BUG-160: מרכאה/סוגר פותח לא-מאוזן — הסוגר המתאים לו לא מופיע בכלל
        # בהמשך הטקסט — הוא רעש של עטיפת-הודעה (ארטיפקט העתק-הדבק, מרכאה
        # תועה), לא תוכן. מוסרים רק את התו הפותח היחיד; לעולם לא מניחים
        # שקיים סוגר תואם במקום אחר ומסירים משני הצדדים. מכוון בכוונה יותר
        # צר מהמקרה המאוזן למעלה: אם תו-הסגירה כן מופיע מאוחר יותר (רק לא
        # בדיוק בסוף), הצורה הזו עדיין דו-משמעית באמת, ונשארת ללא שינוי —
        # אותה התנהגות של נפילה-ללא-התאמה כמו לפני התיקון הזה.
        if len(value) >= 2:
            for opening, closing in _CREATE_TASK_QUOTE_PAIRS:
                if value.startswith(opening) and closing not in value[1:]:
                    value = value[1:].strip()
                    break
            else:
                break
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


# BUG-CRM-BYPASS follow-up (01/09/2026): Deal creation used to reach
# Handler.AGENT unconditionally — no Intent.CREATE_DEAL existed at all, so
# the LLM was always the one choosing between crm_create_deal and the
# generic airtable_add. That is the actual root cause of the repeated
# production failures (PR #1165/#1166/#1169): every fix patched the
# generic-write interception layer instead of keeping the agent out of the
# decision. Turn Coordinator already solved this for Task creation (see
# _STRUCTURED_CREATE_TASK_RE above) — this mirrors that exact pattern
# instead of inventing a new one: same certain/uncertain split, same
# "unstructured phrasing falls through to the existing risk-based route"
# behavior (Task's own gate is equally narrow — see its own comment above
# route_request()'s wiring).
#
# BUG-CRM-BYPASS-DEAL-OPTIONAL-NAME-MARKER (live production, 05/09/2026):
# this used to be a single anchored fullmatch regex requiring the literal
# marker "בשם" before the Deal name, in either field order ("...בשם X
# בתחום Y" / "...בתחום Y בשם X"). Real owner phrasing regularly omits it
# entirely ("צור עסקה X בתחום Y", "פתח עסקה X תחום Y") — every such message
# still classified as Intent.CREATE_DEAL with high confidence and a
# correctly resolved domain, but the structured parser simply didn't match
# at all (matched=False) and CLARIFIED with a message that doesn't even
# mention the real gap. One more regex variant for "בשם" specifically
# optional would just be the next name in this same bug's history — fixed
# instead by replacing the whole extraction with a strip-based contract:
# match the mandatory command prefix, locate and remove the domain clause
# (wherever it sits — field order is not fixed), remove an optional
# trailing self-ownership suffix and an optional "בשם" marker if either is
# present, and treat whatever text remains as the Deal Name — never a
# second per-phrasing regex again.
_CREATE_DEAL_PREFIX_RE = re.compile(
    r"^\s*(?:פתח|תפתח|צור|תיצור|הוסף|תוסיף)\s+עסק(?:ה|ת)\s+"
)
# BUG-CRM-BYPASS-DEAL-DOMAIN-PREFIX (live production, 04/09/2026): "ב?תחום"
# accepts both "בתחום Y" and the owner's own natural "תחום Y" (no ב-prefix).
# \S+ deliberately captures a single token — every canonical domain word in
# this vocabulary (Hebrew or the English slug) is one token; a wider .+?
# capture would risk swallowing part of the Deal Name instead.
_DEAL_DOMAIN_CLAUSE_RE = re.compile(r"ב?תחום\s+(?P<domain_word>\S+)")
_DEAL_TRAILING_SELF_OWNER_RE = re.compile(r"\s+בבעלותי\s*$")
_DEAL_NAME_MARKER_RE = re.compile(r"(?:^|\s)בשם(?:\s|$)")


@dataclass(frozen=True)
class DeterministicDealParse:
    name:      str | None = None
    domain:    str | None = None
    matched:   bool = False
    uncertain: bool = False

    @property
    def domain_resolved(self) -> bool:
        """True once the domain half of this parse is confidently resolved,
        independent of whether a Deal name was also found. The Commercial
        Completion router's own per-field CLARIFY already asks for a
        missing name exactly like it asks for any other missing Deal
        field (deal_type, currency, ...) once the writer is started with
        whatever WAS extracted — a missing name alone must never fall back
        to a router-level generic message or, worse, Handler.AGENT, both
        of which this property gates (see route_request()'s CREATE_DEAL
        branches and app.py's own create_deal handling)."""
        return self.matched and not self.uncertain and bool(self.domain)

    @property
    def certain(self) -> bool:
        """Both name AND domain confidently extracted — used only where a
        caller needs the complete pair in one shot (e.g. a fingerprint
        basis); routing decisions use domain_resolved instead, see above."""
        return self.domain_resolved and bool(self.name)

    # BUG-CRM-BYPASS-FINGERPRINT-PARITY (live production regression,
    # 01-02/09/2026): a business_identity() method used to live here,
    # returning {"name":..., "domain":...} without owner_id, on the theory
    # that this was a safe "identity-only" fingerprint basis distinct from
    # the real dispatched payload. It was passed to app.py's
    # _queue_deterministic_create_deal() as a custom fingerprint_payload —
    # which core/action_gateway.py's propose_action() then uses INSTEAD of
    # the real tool_inputs to compute the stored business_action_fingerprint
    # (fingerprint_basis = normalized if fingerprint_payload is None else
    # normalize_payload(fingerprint_payload)). Once BUG-CRM-BYPASS-OWNER-
    # PRESENCE added owner_id to the real dispatched inputs, that stored
    # fingerprint (2 keys) could never again match tools/dispatcher.py's
    # _validate_execution_proof() recomputation from the real inputs
    # (3 keys) — every approved contract failed with "approval-sensitive
    # execution proof does not match the action payload," the exact
    # BUG-TASK-01 failure mode this method's own docstring warned about
    # while itself recreating it. Fixed by removing the divergence at its
    # source: app.py no longer passes a custom fingerprint_payload at all,
    # so the fingerprint is always computed from the one real payload that
    # actually gets dispatched — there is no second representation left to
    # go stale.


def parse_deterministic_create_deal(text: str) -> DeterministicDealParse:
    normalized = _normalize_create_task_input(text)  # generic reply/quote-wrapper stripping, not Task-specific
    prefix_match = _CREATE_DEAL_PREFIX_RE.match(normalized)
    if not prefix_match:
        return DeterministicDealParse()
    rest = normalized[prefix_match.end():]

    # A trailing self-ownership marker can sit after either the name or the
    # domain clause depending on field order -- remove it once, up front,
    # so the domain-clause/name-marker stripping below stays order-
    # independent instead of needing to handle it in two places.
    rest = _DEAL_TRAILING_SELF_OWNER_RE.sub("", rest)

    domain_match = _DEAL_DOMAIN_CLAUSE_RE.search(rest)
    if not domain_match:
        # No domain clause anywhere in the text -- this doesn't fit the
        # structured template closely enough to extract anything from;
        # never guess a domain. (Canary #7, live production 02/09/2026:
        # "...domain import" uses the English word "domain" instead of
        # "תחום"/"בתחום" and must keep failing to match here, unchanged by
        # this rewrite -- verified by its own regression test below.)
        return DeterministicDealParse()
    domain_raw = domain_match.group("domain_word")
    # Remove the domain clause (marker + word) from the remaining text,
    # regardless of where it sits -- "...בשם X בתחום Y" and "...בתחום Y
    # בשם X" both occur in real owner phrasing (BUG-CRM-BYPASS follow-up's
    # own "reversed field order" regression test).
    remainder = (rest[:domain_match.start()] + " " + rest[domain_match.end():]).strip()

    # "בשם" is an OPTIONAL marker, not a required structural anchor
    # (BUG-CRM-BYPASS-DEAL-OPTIONAL-NAME-MARKER) -- strip a bare "בשם"
    # token wherever it sits in what's left. Whatever remains after that is
    # the Deal Name candidate, full stop -- never a second per-phrasing
    # regex for "no בשם" specifically.
    remainder = _DEAL_NAME_MARKER_RE.sub(" ", remainder, count=1)
    remainder = " ".join(remainder.split())

    # An explicit "בעלות <מישהו>" (a named owner other than the caller)
    # isn't the literal self-ownership suffix "בבעלותי" already stripped
    # above, so it survives into the remainder here -- without this guard
    # it would silently become part of the Deal Name instead of being
    # rejected. Resolving a named owner deterministically is out of scope
    # (see business_identity()'s docstring above) -- fail to CLARIFY
    # instead of writing a corrupted field.
    if "בעלות" in remainder:
        return DeterministicDealParse(matched=True, uncertain=True)

    # BUG-CRM-BYPASS-DOMAIN-TRANSLATION (live production, 02/09/2026): this
    # used to write domain_raw (the literal Hebrew/English word the caller
    # typed, e.g. "יבוא") straight into crm_create_deal's payload. Airtable's
    # Domain single-select only accepts the canonical English slugs
    # ("import", "real_estate", ...) and rejected every raw Hebrew word with
    # HTTP 422 -- every deterministic Deal creation with a Hebrew domain word
    # failed. Fixed by canonicalizing through the SAME shared word->slug
    # table Leads already use (core.lead_service.resolve_domain_word / its
    # core.ingress_classifier._DOMAIN_HINT_CANONICAL table) -- one shared
    # vocabulary, never a second guess table. An unrecognized word fails to
    # CLARIFY, exactly like a corrupted-name case above -- never guessed,
    # never written raw.
    from core.lead_service import resolve_domain_word
    domain = resolve_domain_word(domain_raw)
    if not domain:
        return DeterministicDealParse(matched=True, uncertain=True)

    # A genuinely empty remainder (no "בשם" clause AND nothing else left
    # after removing the domain clause, e.g. "צור עסקה בתחום יבוא") is a
    # real, distinct case -- domain confidently resolved, Deal Name simply
    # never supplied. domain_resolved is True here (matched, not uncertain,
    # domain present) even though certain is False (name is None) -- the
    # caller starts the Commercial Completion writer with the domain it
    # already has and lets the writer's own per-field CLARIFY ask for the
    # Deal Name next, exactly like any other missing field. Never a
    # router-level generic "name or domain?" message when domain is
    # actually known.
    name = remainder or None
    return DeterministicDealParse(name=name, domain=domain, matched=True)


_COMMERCIAL_COMPLETION_PREFIXES = (
    (r"(?:צור|תיצור|הוסף|תוסיף)\s+(?:תנאי\s+תשלום|payment\s+term)", Intent.CREATE_PAYMENT_TERM),
    (r"(?:צור|תיצור|הוסף|תוסיף)\s+(?:ארגון|organization)", Intent.CREATE_ORGANIZATION),
    (r"(?:צור|תיצור|הוסף|תוסיף)\s+(?:חיוב|charge)", Intent.CREATE_CHARGE),
    (r"(?:צור|תיצור|הוסף|תוסיף)\s+(?:תשלום\s+לחיוב|charge\s+payment)", Intent.CREATE_CHARGE_PAYMENT),
)


@dataclass(frozen=True)
class DeterministicCommercialCompletionParse:
    intent: str | None = None
    matched: bool = False
    uncertain: bool = False

    @property
    def certain(self) -> bool:
        return self.matched and not self.uncertain and self.intent is not None


def parse_deterministic_commercial_completion(text: str) -> DeterministicCommercialCompletionParse:
    """Recognize only explicit S2C entity prefixes; never infer an entity."""
    normalized = _normalize_create_task_input(text)
    for pattern, intent in _COMMERCIAL_COMPLETION_PREFIXES:
        if re.match(r"^\s*" + pattern + r"(?:\s|:|$)", normalized, re.IGNORECASE):
            return DeterministicCommercialCompletionParse(intent=intent, matched=True)
    return DeterministicCommercialCompletionParse()


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

    # PA-01: same deterministic gate, reused for the entity-dependent task
    # intents. Downstream (task_integration.prepare_task_proposal →
    # task_resolvers.resolve_task) still owns 0/many-match resolution and
    # fails closed there — this only decides whether the message is
    # structured enough to be worth handing to that path at all.
    _task_ref_parse = parse_deterministic_task_reference(text)
    if (
        intent in (Intent.UPDATE_TASK, Intent.COMPLETE_TASK)
        and _task_ref_parse.certain
        and identity.role not in ("lead", "guest", "readonly")
    ):
        risk, handler, needs_approval = Risk.NEEDS_APPROVAL, Handler.TOOL, True

    # BUG-CRM-BYPASS follow-up: same deterministic gate, reused for Deal
    # creation — see parse_deterministic_create_deal()'s own comment for why
    # this exists. Structured requests are queued straight to
    # crm_create_deal; the Agent is never given a choice of tool for this
    # intent. Gated on domain_resolved, not certain: a missing Deal Name
    # alone must still reach Handler.TOOL and the Commercial Completion
    # writer's own per-field CLARIFY, never a router-level generic message
    # or Handler.AGENT (BUG-CRM-BYPASS-DEAL-OPTIONAL-NAME-MARKER).
    _create_deal_parse = parse_deterministic_create_deal(text)
    if (
        intent == Intent.CREATE_DEAL
        and _create_deal_parse.domain_resolved
        and identity.role not in ("lead", "guest", "readonly")
    ):
        risk, handler, needs_approval = Risk.NEEDS_APPROVAL, Handler.TOOL, True

    _commercial_completion_intent = parse_deterministic_commercial_completion(text)
    if (
        _commercial_completion_intent.certain
        and identity.role not in ("lead", "guest", "readonly")
    ):
        intent = _commercial_completion_intent.intent

    if (
        intent in (
            Intent.CREATE_PAYMENT_TERM, Intent.CREATE_ORGANIZATION,
            Intent.CREATE_CHARGE, Intent.CREATE_CHARGE_PAYMENT,
        )
        and _commercial_completion_intent.certain
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

    elif intent in (Intent.UPDATE_TASK, Intent.COMPLETE_TASK) and _task_ref_parse.uncertain:
        handler = Handler.CLARIFY
        tool_allowed = False
        needs_approval = False
        response_override = (
            "לא בטוח לאיזו משימה התכוונת. נא לציין את שם המשימה במדויק."
        )

    # BUG-CRM-BYPASS-DEAL-AGENT-FALLTHROUGH (live production, 02/09/2026):
    # the condition below used to check only `.uncertain` (matched=True but
    # incomplete), so a message the intent_router still classified as
    # create_deal but that didn't fit the structured template at all
    # (matched=False -- e.g. "domain X" instead of "בתחום X") fell through
    # this whole elif chain untouched and reached Handler.AGENT with normal,
    # unrestricted tool access. The agent then picked the generic
    # airtable_add bypass tool (no deterministic route ever offers it
    # crm_create_deal directly), which has no owner-resolution fallback and
    # hard-fails with "owner_id חסר" -- the exact BUG-CRM-BYPASS-OWNER-
    # PRESENCE failure class this session already fixed for the
    # deterministic route, reopened via the one path that was never routed
    # at all. Per the standing architecture decision for this intent (the
    # system routes Deal creation deterministically; the Agent is never
    # given a tool choice for it), ANY parse whose domain isn't confidently
    # resolved -- uncertain OR unmatched -- must CLARIFY, never fall
    # through to the Agent. Gated on domain_resolved (not certain): once
    # domain IS known, a missing Deal Name alone already reached
    # Handler.TOOL above and never lands here at all -- this branch is
    # purely the "we can't even trust the domain" case. This does not touch
    # Intent.CREATE_TASK's deliberately different design (broader task
    # phrasings intentionally stay on the Agent path).
    elif intent == Intent.CREATE_DEAL and not _create_deal_parse.domain_resolved:
        handler = Handler.CLARIFY
        tool_allowed = False
        needs_approval = False
        response_override = (
            "לא בטוח שהבנתי את שם העסקה או את התחום. נסח כך: "
            "\"פתח עסקה בשם X בתחום Y\"."
        )

    elif intent in (
        Intent.CREATE_PAYMENT_TERM, Intent.CREATE_ORGANIZATION,
        Intent.CREATE_CHARGE, Intent.CREATE_CHARGE_PAYMENT,
    ) and not _commercial_completion_intent.certain:
        handler = Handler.CLARIFY
        tool_allowed = False
        needs_approval = False
        response_override = "נא לנסח בקשה מסחרית מפורשת כדי להתחיל השלמה דטרמיניסטית."

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
