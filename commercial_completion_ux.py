"""Human-facing presentation and deterministic reference resolution.

This is deliberately a thin adapter over the canonical commercial completion
contracts.  It owns no persistence, routing, approval, or mutation authority.
Record identifiers and storage field names stay on the adapter's internal
side of the boundary and are never included in rendered user text.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Iterable, Mapping

from commercial_completion import ENTITY_CONTRACTS, FieldContract, InputType
from core.draft_fields import FieldMetadata
from core.router.entity_resolvers import _resolve_bounded_entity, resolve_contact, resolve_deal
from core.router.ownership_contracts import ResolverResult


FieldPresentation = FieldMetadata

# DIAMOND PATH nested-entity approval continuation: entities eligible for
# the confirm-to-create flow when resolve_human_link() finds no match.
# Only entities with a real canonical find-or-create writer and an
# EntityContract belong here — never widen this to entities the nested-
# completion bridge doesn't actually support yet.
_NESTED_ENTITY_LABELS: dict[str, str] = {
    "organization": "ארגון",
    "contact": "איש קשר",
}

@dataclass(frozen=True)
class HumanChoice:
    """A safe, display-only choice.  No stable record reference is exposed."""

    label: str
    token: str


@dataclass(frozen=True)
class LinkResolution:
    status: str  # resolved, clarify, create
    canonical_value: str = ""
    choices: tuple[HumanChoice, ...] = ()
    reason: str = ""
    create_allowed: bool = False
    # Internal-only, parallel to `choices` by index: the canonical record
    # reference each displayed HumanChoice would resolve to. Never rendered
    # (nothing in this module puts it into prompt/reason text) — it exists
    # so a caller can let a HumanChoice.token pick deterministically among
    # candidates that happen to share an identical display label, instead of
    # re-running a free-text search that can't tell them apart.
    candidate_ids: tuple[str, ...] = ()


# BUG-DIAMOND-EXPECTED-VALUE-RANGE: business-language button labels for the
# two Estimated Value select fields — the canonical enum values themselves
# (e.g. "100k_300k") are internal-only and must never be shown to a user.
# See field_presentation() (renders these as choices) and
# resolve_estimated_value_choice() (maps a clicked/typed label back to its
# canonical value) below.
ESTIMATED_VALUE_BASIS_LABELS: dict[str, str] = {
    "monthly": "חודשי",
    "total": "סכום כולל",
    "one_off": "חד-פעמי",
}

ESTIMATED_VALUE_RANGE_LABELS: dict[str, str] = {
    "under_10k": "עד 10,000",
    "10k_100k": "10,000–100,000",
    "100k_300k": "100,000–300,000",
    "300k_1m": "300,000–1,000,000",
    "over_1m": "מעל 1,000,000",
    "unknown": "עדיין לא ידוע",
}

# DIAMOND — BUSINESS FIELDS MIGRATION (06/09/2026): Commercial Status'
# stored value is unchanged (canonical English enum, prospect/active/
# at_risk/completed/cancelled/written_off — no lifecycle/schema change in
# this migration) — this is DISPLAY-ONLY, the same pattern as the two
# Estimated Value label dicts above: field_presentation() shows these
# Hebrew labels as the offered choices, resolve_estimated_value_choice()
# (below) maps a clicked/typed label back to the stored canonical value.
COMMERCIAL_STATUS_LABELS: dict[str, str] = {
    "prospect": "פוטנציאלית",
    "active": "פעילה",
    "at_risk": "דורשת טיפול / בסיכון",
    "completed": "הושלמה",
    "cancelled": "בוטלה",
    "written_off": "נסגרה ללא מימוש",
}

_LABELS = {
    "name": ("שם העסקה", "מה שם העסקה?"),
    "domain": ("תחום", "באיזה תחום העסקה?"),
    "owner": ("בעלים", "מי הבעלים של העסקה?"),
    "origin_lead": ("ליד מקור", "מאיזה ליד העסקה הגיעה?"),
    "counterparty_contact": ("איש קשר", "עם מי העסקה?"),
    "counterparty_organization": ("ארגון", "עם מי העסקה?"),
    "deal_type": ("סוג עסקה", "מה סוג העסקה?"),
    "relationship_type": ("אופי הקשר", "מה אופי הקשר העסקי?"),
    # DIAMOND — BUSINESS FIELDS MIGRATION: canonical replacement for the
    # two entries above (no longer asked in the Diamond enrichment flow —
    # see DealFields.BUSINESS_DEAL_TYPE's own comment).
    "business_deal_type": ("סוג עסקה", "מה סוג העסקה?"),
    "relationship_role": ("אופי הקשר", "מה אופי הקשר העסקי?"),
    "engagement_duration": ("משך התקשרות", "מה משך ההתקשרות?"),
    "currency": ("מטבע", "באיזה מטבע העסקה?"),
    "commercial_status": ("סטטוס מסחרי", "מה הסטטוס המסחרי?"),
    # BUG-DIAMOND-EXPECTED-VALUE-RANGE: "expected_value" (a single scalar
    # number) no longer exists as a Deal field — replaced by the three
    # entries below. The "estimated_value_range" prompt here is only the
    # generic fallback (used if a field-name lookup for it ever happens
    # outside the enrichment loop, e.g. a generic BLOCK message) —
    # app.py's _deal_enrichment_prompt() builds the real, basis-dependent
    # question ("מה טווח השווי החודשי המשוער?" etc.), never the flat
    # "מה השווי הצפוי?" this replaces.
    "estimated_value_basis": ("אופן הערכת שווי", "מה הצפי מתאר?"),
    "estimated_value_range": ("טווח שווי משוער", "מה טווח השווי המשוער?"),
    "estimated_value_notes": ("הערות לשווי משוער", "יש הערות על השווי המשוער?"),
    "stage": ("שלב", "באיזה שלב העסקה?"),
    "start_date": ("תאריך התחלה", "מה תאריך ההתחלה? (YYYY-MM-DD)"),
    "notes": ("הערות", "יש הערות?"),
    # BUG-3-MISSING-PROMPTS: Organization / Payment Term / Charge / Payment
    # fields — every manually-enterable field these 4 entities can ask about
    # needs a real business-language label here, or field_presentation()
    # falls back to the generic "פרט נוסף" / "נא להשלים את הפרט הבא." for
    # every single one of them (verified: it did, for all but a handful of
    # fields shared with Deal above).
    "organization_name": ("שם הארגון", "מה שם הארגון?"),
    # BUG-DIAMOND-CREATE-CONFIRM-PRECEDENCE follow-on: Contact's own
    # manually-enterable fields (beyond "name", pre-filled by begin_nested()
    # and never asked interactively along the only reachable path today —
    # see commercial_completion_routing.py's DIAMOND PATH nested-entity
    # continuation) fell back to the same generic "פרט נוסף" / "נא להשלים
    # את הפרט הבא." fallback BUG-3-MISSING-PROMPTS already fixed for
    # Organization/Payment Term/Charge/Payment — the CREATE_CONFIRM "כן"
    # flow's very next question (phone) was affected in production.
    "phone": ("טלפון", "מה מספר הטלפון?"),
    "email": ("אימייל", "מה כתובת האימייל?"),
    "company": ("חברה", "באיזו חברה?"),
    "role_category": ("קטגוריית תפקיד", "מה קטגוריית התפקיד?"),
    "deal": ("עסקה", "לאיזו עסקה זה משויך?"),
    "billing_term": ("תנאי תשלום", "לאיזה תנאי תשלום זה משויך?"),
    "charge": ("חיוב", "לאיזה חיוב זה משויך?"),
    "payment_term": ("תנאי תשלום", "לאיזה תנאי תשלום זה משויך?"),
    "direction": ("כיוון תשלום", "זה תשלום שמתקבל או שמשולם?"),
    "amount": ("סכום", "מה הסכום?"),
    "calculation_type": ("שיטת חישוב", "איך מחשבים את הסכום?"),
    "fixed_amount": ("סכום קבוע", "מה הסכום הקבוע?"),
    "rate_pct": ("אחוז", "מה האחוז?"),
    "calculation_basis": ("בסיס חישוב", "על בסיס מה מחשבים את הסכום?"),
    "tier_configuration": ("הגדרת מדרגות", "מה הגדרת מדרגות המחיר?"),
    "custom_calculation_rule": ("כלל חישוב מותאם", "מה כלל החישוב המותאם אישית?"),
    "unit_rate": ("תעריף ליחידה", "מה התעריף ליחידה?"),
    "minimum_amount": ("סכום מינימלי", "מה הסכום המינימלי?"),
    "maximum_amount": ("סכום מקסימלי", "מה הסכום המקסימלי?"),
    "cadence": ("תדירות", "מה תדירות התשלום?"),
    "installment_count": ("מספר תשלומים", "לכמה תשלומים לחלק?"),
    "trigger_type": ("סוג הפעלה", "מה מפעיל את התשלום?"),
    "trigger_date": ("תאריך הפעלה", "באיזה תאריך זה מופעל?"),
    "trigger_delay_days": ("ימי המתנה להפעלה", "כמה ימים להמתין לפני ההפעלה?"),
    "trigger_event": ("אירוע מפעיל", "איזה אירוע מפעיל את זה?"),
    "due_rule": ("כלל מועד תשלום", "איך נקבע מועד התשלום?"),
    "specific_due_date": ("תאריך פירעון", "מה תאריך הפירעון?"),
    "schedule_anchor_date": ("תאריך עוגן", "מה תאריך העוגן ללוח הזמנים?"),
    "net_days": ("ימי אשראי", "כמה ימי אשראי (נטו)?"),
    "grace_period_days": ("ימי חסד", "כמה ימי חסד יש?"),
    "status": ("סטטוס", "מה הסטטוס?"),
    "vat_rule": ("כלל מע\"מ", "איך מתייחסים למע\"מ?"),
    "vat_amount": ("סכום מע\"מ", "מה סכום המע\"מ?"),
    "end_date": ("תאריך סיום", "מה תאריך הסיום?"),
    "reference": ("מספר אסמכתא", "מה מספר האסמכתא?"),
    "base_amount": ("סכום בסיס", "מה סכום הבסיס לחישוב?"),
    "original_due_date": ("תאריך פירעון מקורי", "מה תאריך הפירעון המקורי?"),
    "current_expected_date": ("תאריך צפי נוכחי", "מה התאריך הצפוי הנוכחי לתשלום?"),
    "collection_state": ("מצב גבייה", "מה מצב הגבייה?"),
    "quantity": ("כמות", "מה הכמות?"),
    "document_requirement": ("דרישת מסמך", "איזה מסמך נדרש?"),
    "promised_payment_date": ("תאריך הבטחת תשלום", "מתי הובטח לשלם?"),
    "promised_payment_amount": ("סכום הבטחת תשלום", "כמה הובטח לשלם?"),
    "paid_at": ("תאריך תשלום", "באיזה תאריך שולם?"),
    "method": ("אמצעי תשלום", "באיזה אמצעי שולם?"),
}


def field_presentation(entity: str, field: FieldContract) -> FieldPresentation:
    """Map a canonical field contract to business-language UI metadata."""
    label, prompt = _LABELS.get(
        field.field_name,
        ("פרט נוסף", "נא להשלים את הפרט הבא."),
    )
    resolver = ""
    if field.input_type == InputType.LINK:
        resolver = {
            "counterparty_contact": "contact",
            "counterparty_organization": "organization",
            "origin_lead": "lead",
            "owner": "owner",
        }.get(field.field_name, entity)
    choices = tuple(field.choices)
    if field.field_name == "counterparty_contact":
        choices = ("איש קשר", "ארגון")
    elif field.field_name == "estimated_value_basis":
        choices = tuple(ESTIMATED_VALUE_BASIS_LABELS[c] for c in field.choices)
    elif field.field_name == "estimated_value_range":
        choices = tuple(ESTIMATED_VALUE_RANGE_LABELS[c] for c in field.choices)
    elif field.field_name == "commercial_status":
        # DIAMOND — BUSINESS FIELDS MIGRATION §5: display-only translation —
        # the stored canonical value is untouched (see COMMERCIAL_STATUS_LABELS).
        choices = tuple(COMMERCIAL_STATUS_LABELS[c] for c in field.choices)
    return FieldPresentation(
        field_key=field.field_name,
        user_label=label,
        prompt=prompt,
        input_type=field.input_type,
        resolver=resolver,
        choices=choices,
    )


def presentation_for(entity: str, field_key: str) -> FieldPresentation:
    """Return presentation metadata for one existing contract field."""
    contract = ENTITY_CONTRACTS[entity].field(field_key)
    return field_presentation(entity, contract)


def render_prompt(presentation: FieldPresentation) -> str:
    """Render safe user text; never include a storage key or internal ID."""
    text = presentation.prompt
    if presentation.choices:
        options = " / ".join(str(choice) for choice in presentation.choices)
        text = f"{text}\nאפשרויות: {options}"
    return text


def render_counterparty_prompt() -> str:
    return "עם מי העסקה? אפשר לבחור: איש קשר / ארגון."


def _display_label(record: Mapping[str, Any], *, entity: str) -> str:
    fields = record.get("fields") if isinstance(record.get("fields"), Mapping) else record
    if not isinstance(fields, Mapping):
        return "בחירה"
    candidates = (
        ("Name", "שם") if entity == "contact" else ("Organization Name", "שם הארגון"),
        ("Full Name", "שם מלא"), ("שם", "שם"), ("Company", "חברה"),
    )
    for key, _ in candidates:
        value = fields.get(key)
        if value:
            return str(value)
    return str(record.get("name") or record.get("label") or "בחירה")


def _normalized_label(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


# BUG-DIAMOND-ENRICHMENT-RUNTIME-SWEEP (06/09/2026, owner bug sweep, item 2):
# a typed SELECT-field answer must tolerate harmless formatting noise a
# human naturally types — different case ("Ils" for "ILS"), a stray
# leading/trailing "/", or a missing thousands-comma ("עד 10000" for the
# Hebrew label "עד 10,000") — without ever fuzzy/substring-matching. This
# is deliberately narrower than _normalized_label() above (used for
# Contact/Organization NAME matching in resolve_human_link() below): it
# also strips commas and a small set of leading/trailing wrapper
# punctuation, which would be wrong for a person/company name (e.g.
# "Cohen, Inc." must stay distinct from "Cohen Inc"). It must never strip
# an internal character that is part of a label's actual content — in
# particular the "–" range separator inside "10,000–100,000" — so only
# LEADING/TRAILING punctuation is stripped, never anything mid-string.
_SELECT_ANSWER_WRAPPER_RE = re.compile(r"^[/\\.!?;:]+|[/\\.!?;:]+$")


def _normalize_select_answer(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace(",", "")
    text = re.sub(r"\s+", " ", text)
    text = _SELECT_ANSWER_WRAPPER_RE.sub("", text)
    return text.strip().casefold()


def resolve_estimated_value_choice(field_name: str, raw_value: str) -> str | None:
    """Map a clicked/typed Hebrew button label (or the raw canonical value
    itself, for programmatic/test callers) back to its canonical enum
    value for "estimated_value_basis"/"estimated_value_range"/
    "commercial_status" — every Diamond field with a separate Hebrew
    display-label layer (one shared registry per DIAMOND — BUSINESS FIELDS
    MIGRATION §10: never a second, duplicated label map). Never invents a
    value — returns None on no match so the caller fails closed, exactly
    like any other invalid SELECT answer. Fields other than these three are
    returned unchanged (nothing to translate — their stored value already
    IS the displayed choice)."""
    labels = {
        "estimated_value_basis": ESTIMATED_VALUE_BASIS_LABELS,
        "estimated_value_range": ESTIMATED_VALUE_RANGE_LABELS,
        "commercial_status": COMMERCIAL_STATUS_LABELS,
    }.get(field_name)
    if labels is None:
        return raw_value
    if raw_value in labels:
        return raw_value
    normalized = _normalize_select_answer(raw_value)
    for canonical, label in labels.items():
        if _normalize_select_answer(label) == normalized:
            return canonical
    return None


def resolve_select_answer(raw_value: str, choices: tuple[str, ...]) -> str | None:
    """Case/whitespace/comma/wrapper-punctuation-insensitive match of a
    typed answer against a SELECT field's own canonical choice values
    directly — for fields with no separate Hebrew label layer (deal_type,
    relationship_type, currency, commercial_status: the canonical value
    itself, e.g. "ILS"/"one_off", is what is shown and typed). "Ils"/
    "ils "/"ILS" all resolve to the canonical "ILS".

    Exact match only, after normalization — never fuzzy/substring. If
    normalization makes the input match more than one distinct choice
    (should not happen for this bot's own small enum vocabularies, but
    guards against any future overlapping pair), returns None rather than
    silently picking one, exactly like a zero-match — the caller's normal
    invalid-value rejection applies either way, so a garbled or genuinely
    ambiguous answer is always rejected, never guessed."""
    if raw_value in choices:
        return raw_value
    normalized = _normalize_select_answer(raw_value)
    if not normalized:
        return None
    matches = [c for c in choices if _normalize_select_answer(c) == normalized]
    return matches[0] if len(matches) == 1 else None


# DIAMOND — BUSINESS FIELDS MIGRATION §7/§8 (06/09/2026): "עדכון רשומה:
# recurring" production bug — the generic approval-lifecycle description
# (core/action_gateway.py's _first_field_preview()) picks ONE raw field
# value out of the airtable_update payload with no business meaning at
# all, for every table that writer touches (Leads/Tasks/generic). That
# function is deliberately generic/table-agnostic and must stay that way
# (no system-wide normalization consolidation here) — this is the
# Diamond-only replacement: one shared, per-field, label-aware summary
# builder, called from BOTH the pending-approval prompt (app.py's
# _describe_tool_call()) and the completion message
# (core/action_gateway.py's Deals-specific branches) so both surfaces
# read from the exact same source of truth, never independently
# duplicated.
_DEAL_AIRTABLE_FIELD_TO_CONTRACT: dict[str, FieldContract] | None = None


def _deal_airtable_field_index() -> dict[str, FieldContract]:
    global _DEAL_AIRTABLE_FIELD_TO_CONTRACT
    if _DEAL_AIRTABLE_FIELD_TO_CONTRACT is None:
        _DEAL_AIRTABLE_FIELD_TO_CONTRACT = {
            contract.airtable_field: contract
            for contract in ENTITY_CONTRACTS["deal"].fields
        }
    return _DEAL_AIRTABLE_FIELD_TO_CONTRACT


def deal_field_business_summary(fields: Mapping[str, Any]) -> str:
    """One verified mutation -> one clear, per-field business-readable
    summary line — never a raw internal enum token (DIAMOND — BUSINESS
    FIELDS MIGRATION §7/§8). `fields` is Airtable-field-name-keyed, the
    exact shape both the Deal enrichment flow's `collected` dict and
    commercial_crm.create_deal()'s own `fields` dict already use — no
    caller needs to reshape anything to call this.

    Derived strictly from the verified field set actually being written
    (the caller's own `fields` dict) plus this module's own label
    registry — never from dict ordering, argument order, or a "first
    field" heuristic. A field this module has no Deal contract entry for
    (e.g. a raw linked-record id list, or a field with no completion-flow
    field_name) is silently skipped — this is a business-readable
    highlight list, not a full field-by-field diff, and never claims a
    field was updated that wasn't actually present in `fields`."""
    index = _deal_airtable_field_index()
    lines: list[str] = []
    for airtable_field, raw_value in fields.items():
        contract = index.get(airtable_field)
        if contract is None or not raw_value or isinstance(raw_value, (list, tuple, dict)):
            continue
        if contract.field_name in ("deal_type", "relationship_type"):
            # DIAMOND — BUSINESS FIELDS MIGRATION: these two are compat-only
            # (see DealFields.DEAL_TYPE_CODE's own comment) — no longer part
            # of the current business model this summary represents, and
            # their raw values are internal English enum tokens with no
            # Hebrew display-label mapping, so they are never shown here
            # rather than leaking one verbatim.
            continue
        presentation = field_presentation("deal", contract)
        display = str(raw_value)
        # `fields` values are the already-CANONICAL stored values (exactly
        # what was/will be written to Airtable) — the label dicts map
        # canonical -> Hebrew display, the same direction field_presentation()
        # uses for the offered choices, never resolve_estimated_value_choice()
        # (that maps the OTHER direction: a clicked/typed label back to
        # canonical, for validating an incoming answer, not for display).
        if contract.field_name == "commercial_status":
            display = COMMERCIAL_STATUS_LABELS.get(str(raw_value), display)
        elif contract.field_name == "estimated_value_basis":
            display = ESTIMATED_VALUE_BASIS_LABELS.get(str(raw_value), display)
        elif contract.field_name == "estimated_value_range":
            display = ESTIMATED_VALUE_RANGE_LABELS.get(str(raw_value), display)
        lines.append(f"• {presentation.user_label}: {display}")
    return "\n".join(lines)


def resolve_human_link(
    entity: str,
    query: str,
    lookup: Callable[[str, str, int], Iterable[Mapping[str, Any]]],
    *,
    scope: str,
    limit: int = 5,
    create_allowed: bool = False,
) -> LinkResolution:
    """Resolve human input through the bounded canonical resolver seam.

    The lookup is injected, identity-scoped, and bounded.  A unique result is
    returned internally as a canonical reference; multiple results become
    display-only choices and are never silently selected.
    """
    captured: list[Mapping[str, Any]] = []

    def capture(q: str, s: str, bound: int):
        records = list(lookup(q, s, bound))
        captured.extend(records[: bound])
        return records

    resolver = {
        "contact": resolve_contact,
        "deal": resolve_deal,
    }.get(entity)
    if resolver is None:
        resolver = lambda q, source, *, scope, limit: _resolve_bounded_entity(
            entity, q, source, scope=scope, limit=limit
        )
    result: ResolverResult = resolver(query, capture, scope=scope, limit=limit)
    if result.match_count == 1 and result.stable_reference:
        label = _display_label(captured[0], entity=entity) if captured else ""
        if label and _normalized_label(label) == _normalized_label(query):
            return LinkResolution("resolved", canonical_value=result.stable_reference)
        choice = HumanChoice(label or "התאמה אפשרית", "1")
        return LinkResolution(
            "clarify", choices=(choice,),
            reason="מצאתי התאמה אפשרית; נא לאשר את הבחירה.",
            candidate_ids=(result.stable_reference,),
        )
    if result.match_count > 1:
        choices = tuple(
            HumanChoice(_display_label(record, entity=entity), str(index + 1))
            for index, record in enumerate(captured[:limit])
        )
        candidate_ids = tuple(
            str(record.get("record_id") or record.get("id") or "").strip()
            for record in captured[:limit]
        )
        return LinkResolution(
            "clarify", choices=choices,
            reason="מצאתי יותר מאפשרות אחת; נא לבחור לפי השם.",
            candidate_ids=candidate_ids,
        )
    # DIAMOND PATH nested-entity approval continuation (04/09/2026):
    # supersedes the earlier BUG-2-ORGANIZATION-CREATE interim hand-off
    # ("send a separate 'צור ארגון X' command, then repeat this answer").
    # That workaround existed only because there was no mechanism to resume
    # THIS parent completion after an async approval — the nested-completion
    # + ContinuationRef bridge (commercial_completion.py, commercial_completion_routing.py)
    # is that mechanism now, so both Contact and Organization get a direct
    # confirm-to-create prompt instead of a redirect to a separate command.
    # The router (not this pure presentation layer) turns `status="create"`
    # into the actual [כן]/[לא] CLARIFY route with a pending-create marker —
    # this function only decides whether creation is offered at all and
    # renders the human-facing question.
    name = str(query).strip()
    if not create_allowed:
        return LinkResolution("clarify", reason="לא מצאתי התאמה; נא לנסות שם אחר.")
    label = _NESTED_ENTITY_LABELS.get(entity, entity)
    return LinkResolution(
        "create",
        reason=f'לא מצאתי את {name}. ליצור {label} חדש?',
        create_allowed=True,
    )


__all__ = [
    "FieldPresentation", "HumanChoice", "LinkResolution",
    "field_presentation", "presentation_for", "render_prompt",
    "render_counterparty_prompt", "resolve_human_link",
    "deal_field_business_summary", "resolve_estimated_value_choice",
    "resolve_select_answer", "COMMERCIAL_STATUS_LABELS",
    "ESTIMATED_VALUE_BASIS_LABELS", "ESTIMATED_VALUE_RANGE_LABELS",
]
