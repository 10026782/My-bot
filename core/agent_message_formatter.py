# core/agent_message_formatter.py
# F52 — Unified Approval Runtime · PR 1 — Message Contract Foundation
#
# The single, channel-neutral semantic formatter that turns a canonical message
# STATE + a structured business PAYLOAD into final user-facing text. This is the
# "Semantic Formatter" stage of the F52 flow:
#
#     Internal Result -> Message Contract -> Semantic Formatter -> Channel Renderer
#
# Authority: docs/architecture/f52-unified-approval-runtime/spec/
#            UNIFIED_MESSAGE_UX_STANDARD.md (UX source of truth).
#
# Layer boundary (do not mix):
#   - RP5 / the Evidence Contract owns CLASSIFICATION and STATE. It decides,
#     from backend evidence, what state a turn is in. It NEVER lives here.
#   - This formatter owns final user-facing WORDING. It renders the state it is
#     told; it never derives, upgrades, or infers truth. A formatter must never
#     turn `outcome_unknown`/`approval_pending`/`unverified_effect`/`mixed*`
#     into success (see UX standard, "Relationship to RP5 Evidence Contract").
#
# FOUNDATION ONLY (PR 1): this module is standalone and import-free. It is NOT
# wired into app.py / Telegram / WhatsApp / ActionGateway yet, changes no runtime
# behavior, and activates no flags. Future PRs will route specific surfaces
# through format_agent_message() incrementally and reconcile it with
# ActionGateway.compose_status_reply() so exactly one formatter exists.
#
# State-name reconciliation (spec vs. this module): the UX standard's version-1
# vocabulary names seven states (`approval_single`/`approval_batch`/
# `clarification`/`success`/`failure`/`idle`/`unverified_effect`). This module's
# canonical set is a superset (10 states) that also carries the RP5/RP4
# `TurnEvidenceSummary.classification()` names (`outcome_unknown`, `mixed`,
# `mixed_with_unknown`) so the future evidence-derived state can be rendered
# safely without a second translation layer. The spec's names are accepted as
# aliases (see _STATE_ALIASES). No state is ever rendered as an upgrade.

from __future__ import annotations

import re

FORMATTER_VERSION = 1

# ── Canonical message states ──────────────────────────────────────────────────
STATE_SUCCESS                 = "success"
STATE_FAILURE                 = "failure"
STATE_APPROVAL_PENDING        = "approval_pending"
# F52 D-015: a NEW approval prompt (right after the user's request is queued)
# and a STATUS QUERY about an already-pending action need distinct wording —
# "כדי לבצע/ליצור ... נדרש אישור" vs. "יש פעולה/משימה שממתינה לאישור". This
# state is a distinct MessageContract presentation semantic; lifecycle
# authority remains the existing pending ActionContract.
STATE_APPROVAL_PENDING_QUERY  = "approval_pending_query"
STATE_APPROVAL_PENDING_BATCH  = "approval_pending_batch"
STATE_CLARIFICATION_NEEDED    = "clarification_needed"
STATE_IDLE                    = "idle"
STATE_OUTCOME_UNKNOWN         = "outcome_unknown"
STATE_UNVERIFIED_EFFECT       = "unverified_effect"
STATE_MIXED                   = "mixed"
STATE_MIXED_WITH_UNKNOWN      = "mixed_with_unknown"
STATE_CANCELLED               = "cancelled"

# D-019 context-free vocabulary.  These summaries do not replace the richer
# surface renderers governed by D-014 through D-017.
BASELINE_STATUS_SUMMARIES = {
    STATE_APPROVAL_PENDING: "הפעולה ממתינה לאישור.",
    STATE_FAILURE: "הפעולה לא הושלמה.",
    "cancelled": "הפעולה בוטלה.",
    STATE_SUCCESS: "הפעולה הושלמה.",
}


def format_baseline_status_summary(
    state: str, *, execution_verified: bool | None = None,
) -> str:
    """Render D-019's baseline summary without inferring business state.

    Success fails closed unless its caller explicitly supplies verified
    execution evidence.  Surface-specific renderers do not call this helper
    automatically, preserving D-014 through D-017.
    """
    if state not in BASELINE_STATUS_SUMMARIES:
        raise ValueError("unsupported baseline status state")
    if state == STATE_SUCCESS and execution_verified is not True:
        return "לא ניתן לאמת שהפעולה הושלמה."
    return BASELINE_STATUS_SUMMARIES[state]

CANONICAL_STATES = frozenset({
    STATE_SUCCESS, STATE_FAILURE, STATE_APPROVAL_PENDING,
    STATE_APPROVAL_PENDING_QUERY,
    STATE_APPROVAL_PENDING_BATCH, STATE_CLARIFICATION_NEEDED, STATE_IDLE,
    STATE_OUTCOME_UNKNOWN, STATE_UNVERIFIED_EFFECT, STATE_MIXED,
    STATE_MIXED_WITH_UNKNOWN, STATE_CANCELLED,
})

# UX-standard version-1 names -> this module's canonical names.
_STATE_ALIASES = {
    "approval_single": STATE_APPROVAL_PENDING,
    "approval_batch":  STATE_APPROVAL_PENDING_BATCH,
    "clarification":   STATE_CLARIFICATION_NEEDED,
    # success / failure / idle / unverified_effect match directly.
}

# ── First-person success verbs by business action ─────────────────────────────
# UX rule: prefer first-person action wording, never passive "בוצע".
_ACTION_VERB = {
    "create": "יצרתי",
    "update": "עדכנתי",
    "delete": "מחקתי",
    "send":   "שלחתי",
}

# ── Stable reason codes -> human, non-technical text ──────────────────────────
# UX rule: formatter decisions use stable codes, never raw exception text.
_REASON_TEXT = {
    "GOOGLE_AUTH_REQUIRED":     "צריך לחבר מחדש את חשבון Google כדי להמשיך.",
    "STRUCTURED_RESULT_INVALID":"התקבלה תשובה לא תקינה מהמערכת.",
    "PERMISSION_DENIED":        "אין הרשאה לבצע את הפעולה הזאת.",
    "ACTION_REJECTED":          "הפעולה בוטלה.",
    "ACTION_EXPIRED":           "בקשת האישור פגה. צריך להתחיל מחדש.",
    "EXECUTION_NOT_VERIFIED":   "לא ניתן לאמת שהפעולה בוצעה.",
    "PROVIDER_UNAVAILABLE":     "השירות אינו זמין כרגע.",
    "VALIDATION_FAILED":        "חלק מהפרטים חסרים או לא תקינים.",
    "UNKNOWN_ERROR":            "משהו השתבש. אפשר לנסות שוב מאוחר יותר.",
}
_DEFAULT_REASON_TEXT = _REASON_TEXT["UNKNOWN_ERROR"]

# ── Length bounds (UX rule: bound field / item / total lengths) ───────────────
_MAX_FIELD_LEN   = 80
_MAX_ITEM_LEN    = 120
_MAX_TOTAL_LEN   = 900
_MAX_BATCH_ITEMS = 10
_MAX_OPTIONS     = 3   # clarification: at most three choices (spec)

# ── Sanitization patterns ─────────────────────────────────────────────────────
# Protect legitimate business data before redaction, restore afterwards.
_EMAIL_RE  = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE  = re.compile(r"(?<!\d)\+?\d[\d\-\s]{6,}\d(?!\d)")
_ISO_DT_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:[.+\-Z][\d:]*)?)?\b")

# Technical identifiers that must never reach user text.
_AIRTABLE_ID_RE = re.compile(r"\brec[A-Za-z0-9]{10,}\b")
_UUID_RE        = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX_ID_RE      = re.compile(r"\b(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{12,}\b")
_URL_RE         = re.compile(r"https?://\S+")
# ASCII snake_case token (airtable_add, calendar_create_event, crm_mark_payment_paid,
# human_summary, ...) — never legitimate Hebrew user-facing text.
_SNAKE_RE       = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
# Long opaque tokens (API keys, callback refs).
_LONG_TOKEN_RE  = re.compile(r"\b[A-Za-z0-9\-]{24,}\b")
# Shorter mixed letter+digit ASCII tokens (keyABCDEF0123456789, contract refs):
# business text almost never contains a 16+ char token that mixes letters and
# digits; ids and secrets do. Digit-only runs (phones) are excluded by the
# letter lookahead; all-letter words are excluded by the digit lookahead.
_MIXED_ID_RE    = re.compile(r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{16,}\b")
# JSON-object-shaped raw provider payload block (contains a quote or colon).
_JSON_BLOCK_RE  = re.compile(r"\{[^{}]*[:\"][^{}]*\}")
# Airtable-style id-label leftovers like "| מזהה:" once the id itself is gone.
_ID_LABEL_RE    = re.compile(r"[|·•]?\s*(?:מזהה|id|record|רשומה)\s*[:=]?\s*$", re.IGNORECASE)

# Markdown / control characters to neutralize (never enable parse mode).
_MD_RE      = re.compile(r"[*_`~#>\[\]]")
_CTRL_RE    = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Injected execution-claim glyphs/words that must never ride inside a field
# value (only the single state marker may express status).
_INJECTED_CLAIM_RE = re.compile(
    r"✅|❌|⏳|✓|✔|\bהפעולה\s+בוצעה\b|\bבוצע(?:ה|ו)?\b|\bהושלמ(?:ה|ו)?\b|\bנשלח(?:ה|ו)?\b",
)


class _Redactor:
    """Accumulates a redaction count while cleaning a single string."""

    def __init__(self) -> None:
        self.count = 0

    def _sub(self, pattern: re.Pattern, text: str, repl: str = "") -> str:
        def _r(_m):
            self.count += 1
            return repl
        return pattern.sub(_r, text)

    def clean(self, value) -> str:
        """Sanitize one display string: redact technical ids, strip markdown,
        neutralize injected execution claims, bound length. Preserves Hebrew,
        emails, phone numbers, and (via _human_date) human dates.

        Ordering matters: emails are protected before ANY redaction (snake/token
        redaction would otherwise mangle an email local part); record/UUID/hex
        ids are redacted before phones are protected (so digits inside an id
        such as recABC1234567890 are consumed by the id redactor, not shielded
        as a phone). Protection sentinels use the Unicode private-use area so the
        control-character cleaner never strips them."""
        if value is None:
            return ""
        text = str(value)
        protected: dict[str, str] = {}

        def _protect(pattern: re.Pattern, tag: str, s: str) -> str:
            def _p(m):
                key = f"{tag}{len(protected)}"   # private-use sentinels
                protected[key] = m.group(0)
                return key
            return pattern.sub(_p, s)

        # 1. Protect emails first (redaction would break local parts).
        text = _protect(_EMAIL_RE, "E", text)

        # 2. Redact raw provider-payload blocks and technical ids whose shape
        #    overlaps digits.
        text = self._sub(_JSON_BLOCK_RE, text)
        text = self._sub(_URL_RE, text)
        text = self._sub(_AIRTABLE_ID_RE, text)
        text = self._sub(_UUID_RE, text)
        text = self._sub(_HEX_ID_RE, text)

        # 3. Protect phone numbers (now safe from id patterns above).
        text = _protect(_PHONE_RE, "P", text)

        # 4. Redact remaining technical tokens.
        text = self._sub(_SNAKE_RE, text)
        text = self._sub(_LONG_TOKEN_RE, text)
        text = self._sub(_MIXED_ID_RE, text)

        # 5. Strip markdown / control chars (never enable parse mode). The
        #    private-use sentinels (U+E000/U+E001) are outside this range.
        if _MD_RE.search(text):
            text = _MD_RE.sub("", text)
        text = _CTRL_RE.sub("", text)

        # 6. Neutralize injected execution claims inside the value.
        text = self._sub(_INJECTED_CLAIM_RE, text)

        # 7. Tidy leftover id-labels, whitespace, and separators left dangling
        #    by redaction (e.g. a redacted trailing token leaving "..., ").
        text = _ID_LABEL_RE.sub("", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        text = re.sub(r"([,/;:])(?:\s*[,/;:])+", r"\1", text)   # collapse adjacent seps
        text = text.strip(" \t|·•,-:/")

        # 8. Restore protected business tokens.
        for key, original in protected.items():
            text = text.replace(key, original)

        return text.strip()


def _clean(value, redactor: _Redactor, limit: int = _MAX_FIELD_LEN) -> str:
    text = redactor.clean(value)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _human_date(value, redactor: _Redactor) -> str:
    """Render an ISO timestamp as a human dd/mm/YYYY date; otherwise clean text.
    UX rule: dates must not be raw ISO in user-facing text."""
    if value is None:
        return ""
    raw = str(value).strip()
    m = _ISO_DT_RE.search(raw)
    if m:
        iso = m.group(0).replace(" ", "T")
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            pass
    return _clean(raw, redactor)


# ── Descriptor helpers ────────────────────────────────────────────────────────

def _normalize_payload(payload) -> dict:
    """Unified payload mapping (F52 display_payload adoption).

    Accepts the spec's canonical `display_payload` field names (`action`,
    `entity_type`, `entity_name`, `key_fields`, `count`, `items`, `reason_code`,
    `execution_verified`, `occurred_at`) AND the legacy loose shape (`fields`,
    `reason`, `business_identifier`, `human_summary`, `user_options`), mapping
    both into one internal structure. Canonical names win; legacy names are a
    compatibility layer.

    `human_summary` is demoted to a compatibility HINT per the UX standard's
    "human_summary migration decision": it is never execution evidence, never
    enables a success state, and is ignored when a valid structured
    display_payload exists (any of entity_name / key_fields / items / action).
    """
    p = payload if isinstance(payload, dict) else {}
    key_fields = p.get("key_fields")
    if key_fields is None:
        key_fields = p.get("fields")          # legacy name
    structured = bool(p.get("entity_name") or key_fields or p.get("items") or p.get("action"))
    return {
        "action":              p.get("action"),
        "entity_type":         p.get("entity_type"),
        "entity_name":         p.get("entity_name"),
        "business_identifier": p.get("business_identifier"),
        "key_fields":          key_fields or [],
        "count":               p.get("count"),
        "items":               p.get("items") or [],
        "reason_code":         p.get("reason_code"),
        "reason_text":         p.get("reason"),          # legacy human/text reason
        "occurred_at":         p.get("occurred_at"),
        "user_options":        p.get("user_options") or [],
        "execution_verified":  p.get("execution_verified"),
        "human_summary":       p.get("human_summary"),   # compatibility hint only
        "interaction":         p.get("interaction"),
        "_structured":         structured,
    }


def _structured_descriptor(norm: dict, redactor: _Redactor) -> str:
    """Human business descriptor from STRUCTURED fields only (entity_name +
    business_identifier, else the first key_field value). Never human_summary."""
    name = _clean(norm.get("entity_name"), redactor)
    ident = _clean(norm.get("business_identifier"), redactor)
    if name and ident:
        return f"{name} ({ident})"
    if name:
        return name
    if ident:
        return ident
    for field in (norm.get("key_fields") or []):
        if isinstance(field, dict):
            value = _clean(field.get("value"), redactor)
            if value:
                return value
    return ""


def _descriptor(norm: dict, redactor: _Redactor) -> str:
    """Full descriptor: structured first; the human_summary hint is used only
    when no structured display_payload is present (spec migration rule)."""
    structured = _structured_descriptor(norm, redactor)
    if structured:
        return structured
    if not norm.get("_structured"):
        return _clean(norm.get("human_summary"), redactor, _MAX_ITEM_LEN)
    return ""


def _render_fields(norm: dict, redactor: _Redactor) -> list[str]:
    """Render up to two key business fields as 'label: value' (hyphen rows)."""
    rows: list[str] = []
    for field in (norm.get("key_fields") or [])[:2]:
        if not isinstance(field, dict):
            continue
        label = _clean(field.get("label"), redactor, _MAX_FIELD_LEN)
        if "occurred_at" in field or field.get("is_date"):
            value = _human_date(field.get("value"), redactor)
        else:
            value = _clean(field.get("value"), redactor, _MAX_FIELD_LEN)
        if label and value:
            rows.append(f"- {label}: {value}")
        elif value:
            rows.append(f"- {value}")
    return rows


def _render_items(payload: dict, redactor: _Redactor, numbered: bool) -> list[str]:
    """Render batch business items (human summaries only, never IDs)."""
    rows: list[str] = []
    for i, item in enumerate(payload.get("items") or [], start=1):
        if isinstance(item, dict):
            text = _clean(
                item.get("human_summary") or item.get("entity_name") or item.get("label"),
                redactor, _MAX_ITEM_LEN,
            )
        else:
            text = _clean(item, redactor, _MAX_ITEM_LEN)
        if not text:
            continue
        rows.append(f"{i}. {text}" if numbered else f"- {text}")
        if len(rows) >= _MAX_BATCH_ITEMS:
            break
    return rows


def _bound_total(text: str) -> str:
    if len(text) > _MAX_TOTAL_LEN:
        text = text[: _MAX_TOTAL_LEN - 1].rstrip() + "…"
    return text


# ── Per-state renderers ───────────────────────────────────────────────────────

def _render_success(norm: dict, redactor: _Redactor) -> str:
    if norm.get("entity_type") == "lead" and norm.get("items"):
        rows = _render_items(norm, redactor, numbered=False)
        head = "✅ הליד עודכן" if norm.get("action") == "update" else "✅ הליד נשמר"
        return head + ("\n" + "\n".join(rows) if rows else "")
    # Success wording is generated here; it is never derived from a tool name or
    # raw parameters. A single leading marker only.
    # display_payload evidence gate: an explicit execution_verified=False is
    # never rendered as success (spec locked principle 2). Absent/True → normal.
    if norm.get("execution_verified") is False:
        return "לא ניתן לאמת שהפעולה הושלמה. צריך לבדוק את המצב לפני שממשיכים."
    structured = _structured_descriptor(norm, redactor)
    if structured:
        verb = _ACTION_VERB.get(str(norm.get("action") or "").lower())
        head = f"✓ {verb} {structured}" if verb else f"✓ {structured}"
    else:
        hint = _clean(norm.get("human_summary"), redactor, _MAX_ITEM_LEN) \
            if not norm.get("_structured") else ""
        head = f"✓ {hint}" if hint else "✓ הפעולה הושלמה."
    rows = _render_fields(norm, redactor)   # up to two key business fields
    occurred = _human_date(norm.get("occurred_at"), redactor) if norm.get("occurred_at") else ""
    if occurred:
        rows.append(f"- {occurred}")
    return head + ("\n" + "\n".join(rows) if rows else "")


def _render_failure(norm: dict, redactor: _Redactor) -> str:
    code = str(norm.get("reason_code") or norm.get("reason_text") or "").strip().upper()
    human = _REASON_TEXT.get(code)
    if not human:
        # An explicit human reason (already business-safe) may be provided.
        human = _clean(norm.get("reason_text"), redactor, _MAX_ITEM_LEN) or _DEFAULT_REASON_TEXT
    return f"לא הצלחתי להשלים את הפעולה. {human}"


def _render_approval_pending(norm: dict, redactor: _Redactor) -> str:
    """NEW approval prompt — rendered immediately after the user's request is
    queued for approval (F52 D-015). The only live caller today is
    ActionGateway._render_pending_prompt(), at the moment propose_action()
    just queued the contract — nothing was "already" pending from the user's
    point of view, so the framing is forward-looking ("כדי ... נדרש אישור"),
    not a status report. See _render_approval_pending_query() below for the
    "already pending, user is asking" wording."""
    interaction = norm.get("interaction") or {}
    if interaction.get("type") == "review_edit" and norm.get("entity_type") == "lead":
        rows = _render_items(norm, redactor, numbered=False)
        return "👤 ליד חדש" + ("\n\n" + "\n".join(rows) if rows else "")
    is_task = norm.get("entity_type") == "task"
    if is_task:
        intro = "כדי ליצור את המשימה הזו נדרש אישור"
        fallback = "כדי ליצור משימה זו נדרש אישור. חסר לי מידע כדי להציג אותה בצורה בטוחה."
    else:
        intro = "כדי לבצע את הפעולה הזו נדרש אישור"
        fallback = "כדי לבצע פעולה זו נדרש אישור. חסר לי מידע כדי להציג אותה בצורה בטוחה."
    desc = _descriptor(norm, redactor)
    if not desc:
        # Safe missing-contract fallback (spec) — same framing, no business data.
        return fallback
    return f"{intro}:\n{desc}\nלאשר? כן / לא"


def _render_approval_pending_query(norm: dict, redactor: _Redactor) -> str:
    """STATUS QUERY wording — rendered when the user asks about an action/task
    that is ALREADY pending approval (F52 D-015). Distinct from
    _render_approval_pending() above, which is the new-prompt wording. The
    status-query path reaches this renderer through MessageContract; other
    legacy formatter paths remain intentionally unmigrated."""
    noun = "משימה" if norm.get("entity_type") == "task" else "פעולה"
    desc = _descriptor(norm, redactor)
    if not desc:
        # Safe missing-contract fallback (spec).
        return f"יש {noun} שממתינה לאישור. חסר לי מידע כדי להציג אותה בצורה בטוחה."
    return f"יש {noun} שממתינה לאישור:\n{desc}\nלאשר? כן / לא"


def _render_approval_pending_batch(norm: dict, redactor: _Redactor) -> str:
    rows = _render_items(norm, redactor, numbered=True)
    count = len(rows) or int(norm.get("count") or 0)
    if not rows:
        return "יש פעולות שממתינות לאישור. חסר לי מידע כדי להציג אותן בצורה בטוחה."
    header = f"יש {count} פעולות שממתינות לאישור:"
    return header + "\n" + "\n".join(rows) + "\nשלח מספר כדי לבחור."


def _render_clarification(norm: dict, redactor: _Redactor) -> str:
    question = _clean(
        norm.get("human_summary") or norm.get("reason_text"),
        redactor, _MAX_ITEM_LEN,
    ) or "צריך פרט נוסף כדי להמשיך. מה לעשות?"
    options = []
    for opt in (norm.get("user_options") or [])[:_MAX_OPTIONS]:
        text = _clean(opt, redactor, _MAX_FIELD_LEN)
        if text:
            options.append(f"- {text}")
    if options:
        return question + "\n" + "\n".join(options)
    return question


def _render_idle(norm: dict, redactor: _Redactor) -> str:
    # Short; never a repeated capability list.
    desc = _clean(norm.get("human_summary"), redactor, _MAX_ITEM_LEN)
    return desc or "אין כרגע פעולה שממתינה. אפשר להמשיך."


def _render_outcome_unknown(payload: dict, redactor: _Redactor) -> str:
    # Never success; no automatic retry (spec unverified-execution fallback).
    return "לא ניתן לאמת כרגע אם הפעולה בוצעה. אין לנסות שוב עד לבדיקת המצב."


def _render_unverified_effect(payload: dict, redactor: _Redactor) -> str:
    # Manual-review state: never success, never regular pending, no auto-retry.
    return (
        "ייתכן שהפעולה השפיעה, אבל אין מספיק מידע כדי לאמת זאת. "
        "צריך לבדוק את המצב ידנית לפני שממשיכים, ואין לנסות שוב אוטומטית."
    )


def _render_cancelled(payload: dict, redactor: _Redactor) -> str:
    return "↩️ בוטל"


def _render_mixed(payload: dict, redactor: _Redactor) -> str:
    # Must not collapse into full success.
    rows = _render_items(payload, redactor, numbered=False)
    head = "חלק מהפעולות הושלמו וחלק לא."
    if rows:
        return head + "\n" + "\n".join(rows)
    return head + " צריך לבדוק מה הושלם לפני שממשיכים."


def _render_mixed_with_unknown(payload: dict, redactor: _Redactor) -> str:
    # Must not collapse into full success; flags the unverifiable part.
    rows = _render_items(payload, redactor, numbered=False)
    head = (
        "חלק מהפעולות הושלמו, וחלק לא ניתן לאמת. "
        "צריך לבדוק את המצב ידנית, ואין לנסות שוב אוטומטית."
    )
    if rows:
        return head + "\n" + "\n".join(rows)
    return head


_RENDERERS = {
    STATE_SUCCESS:                _render_success,
    STATE_FAILURE:                _render_failure,
    STATE_APPROVAL_PENDING:       _render_approval_pending,
    STATE_APPROVAL_PENDING_QUERY: _render_approval_pending_query,
    STATE_APPROVAL_PENDING_BATCH: _render_approval_pending_batch,
    STATE_CLARIFICATION_NEEDED:   _render_clarification,
    STATE_IDLE:                   _render_idle,
    STATE_OUTCOME_UNKNOWN:        _render_outcome_unknown,
    STATE_UNVERIFIED_EFFECT:      _render_unverified_effect,
    STATE_MIXED:                  _render_mixed,
    STATE_MIXED_WITH_UNKNOWN:     _render_mixed_with_unknown,
    STATE_CANCELLED:              _render_cancelled,
}


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_state(state) -> str | None:
    """Map an input state (canonical or spec alias) to a canonical state, or
    None when unrecognized."""
    key = str(state or "").strip().lower()
    if key in CANONICAL_STATES:
        return key
    return _STATE_ALIASES.get(key)


def format_agent_message(state, payload=None) -> str:
    """Render a canonical message STATE + structured business PAYLOAD to final
    user-facing text.

    state   — a canonical state (see CANONICAL_STATES) or a UX-standard alias.
    payload — a dict of structured BUSINESS data only. Never pass raw tool
              names, technical IDs, provider payloads, credentials, queue IDs,
              UUIDs, or record IDs: any such token found in a rendered string is
              redacted defensively, but callers must not rely on that.

    Returns plain text (no Markdown). An unknown state falls back to a neutral,
    non-committal message and is never rendered as success.
    """
    text, _meta = format_agent_message_with_meta(state, payload)
    return text


def format_agent_message_with_meta(state, payload=None) -> tuple[str, dict]:
    """Same as format_agent_message() but also returns an observability record
    (message_state, formatter_version, fallback_used, redaction_count). The
    values are for logging only and are never part of the user text."""
    norm = _normalize_payload(payload)   # unified display_payload / legacy mapping
    redactor = _Redactor()

    canonical = normalize_state(state)
    fallback_used = False
    if canonical is None:
        # Fail closed: an unknown state is never success and never technical.
        canonical = None
        text = "אין לי מספיק מידע כדי להשלים את הבקשה כרגע."
        fallback_used = True
    else:
        text = _RENDERERS[canonical](norm, redactor)

    text = _bound_total(text.strip())

    meta = {
        "message_state":    canonical or "unrecognized",
        "formatter_version": FORMATTER_VERSION,
        "fallback_used":    fallback_used,
        "redaction_count":  redactor.count,
    }
    return text, meta
