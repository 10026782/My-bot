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
    "notes": ("הערות", "יש הערות לעסקה?"),
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
        )
    if result.match_count > 1:
        choices = tuple(
            HumanChoice(_display_label(record, entity=entity), str(index + 1))
            for index, record in enumerate(captured[:limit])
        )
        return LinkResolution(
            "clarify", choices=choices,
            reason="מצאתי יותר מאפשרות אחת; נא לבחור לפי השם.",
        )
    return LinkResolution(
        "create" if create_allowed else "clarify",
        reason=("לא מצאתי ארגון כזה; אפשר ליצור ארגון חדש." if create_allowed
                else "לא מצאתי התאמה; נא לנסות שם אחר."),
        create_allowed=create_allowed,
    )


__all__ = [
    "FieldPresentation", "HumanChoice", "LinkResolution",
    "field_presentation", "presentation_for", "render_prompt",
    "render_counterparty_prompt", "resolve_human_link",
]
