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


_LABELS = {
    "name": ("שם העסקה", "מה שם העסקה?"),
    "domain": ("תחום", "באיזה תחום העסקה?"),
    "owner": ("בעלים", "מי הבעלים של העסקה?"),
    "origin_lead": ("ליד מקור", "מאיזה ליד העסקה הגיעה?"),
    "counterparty_contact": ("איש קשר", "עם מי העסקה?"),
    "counterparty_organization": ("ארגון", "עם מי העסקה?"),
    "deal_type": ("סוג עסקה", "מה סוג העסקה?"),
    "relationship_type": ("אופי הקשר", "מה אופי הקשר העסקי?"),
    "currency": ("מטבע", "באיזה מטבע העסקה?"),
    "commercial_status": ("סטטוס מסחרי", "מה הסטטוס המסחרי?"),
    "expected_value": ("שווי צפוי", "מה השווי הצפוי?"),
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
]
