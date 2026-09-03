"""Production orchestration for the Commercial V2 completion contracts.

This module is deliberately an adapter around :mod:`commercial_completion`.
It owns deterministic recognition/orchestration and hands a complete,
validated payload to the existing approval queue.  It does not import an
Airtable client, a generic mutation helper, or an ActionGateway implementation;
the caller supplies the already-existing queue boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from commercial_completion import (
    CompletionBlockedError,
    CompletionSession,
    CommercialCompletionWriter,
    InputType,
)
from airtable_schema import ChargeFields, DealFields, OrganizationFields, PaymentFields, PaymentTermFields


SUPPORTED_COMPLETION_ENTITIES = frozenset(
    {"deal", "payment_term", "organization", "charge", "payment"}
)

MUTATION_TOOLS = {
    "deal": "crm_create_deal",
    "payment_term": "crm_create_payment_term",
    "organization": "crm_find_or_create_organization",
    "charge": "crm_create_charge",
    "payment": "crm_create_charge_payment",
}


class CommercialRoutingError(ValueError):
    """Fail-closed routing error."""


@dataclass(frozen=True)
class CompletionRoute:
    """One deterministic result: clarify, tool handoff, or block."""

    outcome: str
    entity: str
    session: CompletionSession | None = None
    field_name: str | None = None
    field_type: InputType | None = None
    tool_name: str | None = None
    tool_inputs: Mapping[str, Any] | None = None
    queue_outcome: Any = None
    reason: str = ""
    user_label: str = ""
    prompt: str = ""
    choices: tuple[Any, ...] = ()


def serialize_completion_session(session: CompletionSession) -> dict[str, Any]:
    """Serialize pure completion state for the existing universal Session store."""
    return {"frames": [
        {
            "target_entity": frame.writer.target_entity,
            "current_values": dict(frame.writer.current_values),
            "source_context": dict(frame.writer.source_context),
            "identity": dict(frame.writer.identity),
            "return_field": frame.return_field,
        }
        for frame in session.frames
    ]}


def deserialize_completion_session(state: Mapping[str, Any]) -> CompletionSession:
    """Restore completion state without introducing a second persistence system."""
    from commercial_completion import _CompletionFrame
    frames = []
    for raw in state.get("frames", []):
        frames.append(_CompletionFrame(
            CommercialCompletionWriter(
                str(raw["target_entity"]), dict(raw.get("current_values") or {}),
                dict(raw.get("source_context") or {}), dict(raw.get("identity") or {}),
            ), raw.get("return_field"),
        ))
    if not frames:
        raise CommercialRoutingError("persisted commercial completion state is empty")
    return CompletionSession(tuple(frames))


def _link_id(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise CommercialRoutingError("linked entity must resolve to one record")
        value = value[0]
    return str(value or "").strip()


def _primitive_inputs(entity: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Translate one canonical completion payload to the exact primitive API.

    The translation is explicit and lossless for the fields currently accepted
    by the canonical primitives.  No field is inferred or silently discarded.
    """
    p = dict(payload)
    if entity == "organization":
        return {"display_name": p[OrganizationFields.NAME]}
    if entity == "deal":
        result = {
            "name": p[DealFields.NAME], "domain": p[DealFields.DOMAIN],
            "owner_id": _link_id(p[DealFields.OWNER]),
        }
        optional = {
            DealFields.ORIGIN_LEAD: "origin_lead_id", DealFields.AMOUNT: "amount",
            DealFields.STAGE: "stage", DealFields.NOTES: "notes",
            DealFields.COUNTERPARTY_CONTACT: "counterparty_contact_id",
            DealFields.COUNTERPARTY_ORGANIZATION: "counterparty_organization_id",
            DealFields.DEAL_TYPE_CODE: "deal_type_code",
            DealFields.RELATIONSHIP_TYPE: "relationship_type",
            DealFields.CURRENCY: "currency",
            DealFields.COMMERCIAL_STATUS: "commercial_status",
            DealFields.START_DATE: "start_date",
        }
        for field_name, arg_name in optional.items():
            if field_name in p:
                result[arg_name] = (
                    _link_id(p[field_name]) if field_name in {
                        DealFields.ORIGIN_LEAD, DealFields.COUNTERPARTY_CONTACT,
                        DealFields.COUNTERPARTY_ORGANIZATION,
                    } else p[field_name]
                )
        return result
    if entity == "payment_term":
        result = {
            "deal_id": _link_id(p[PaymentTermFields.DEAL]),
            "name": p.get(PaymentTermFields.NAME, "Payment Term"),
            "calc_type": p[PaymentTermFields.CALC_TYPE_CODE],
        }
        mapping = {
            "Fixed Amount": "fixed_amount", "Rate %": "rate_pct",
            "Calculation Basis Code": "calc_basis",
            "Trigger Type Code": "trigger_type", "Trigger Date": "trigger_date",
            "Cadence Code": "cadence", "VAT Rule": "vat_rule",
            "Start Date": "start_date", "End Date": "end_date", "Notes": "notes",
        }
        result.update({arg: p[name] for name, arg in mapping.items() if name in p})
        return result
    if entity == "charge":
        result = {
            "deal_id": _link_id(p[ChargeFields.DEAL]), "direction": p[ChargeFields.DIRECTION],
            "amount": p[ChargeFields.AMOUNT], "currency": p[ChargeFields.CURRENCY_CODE],
            "status": p[ChargeFields.STATUS], "collection_state": p[ChargeFields.COLLECTION_STATE],
            "vat_rule": p[ChargeFields.VAT_RULE],
            "document_requirement": p[ChargeFields.DOCUMENT_REQUIREMENT],
            "document_status": p[ChargeFields.DOCUMENT_STATUS],
        }
        mapping = {
            "Billing Term": "billing_term_id", "Reference": "reference",
            "Original Due Date": "original_due_date",
            "Current Expected Date": "current_expected_date",
            "Base Amount": "base_amount", "Rate %": "rate_pct",
            "Quantity": "quantity", "Unit Rate": "unit_rate",
            "VAT Amount": "vat_amount", "Promised Payment Date": "promised_payment_date",
            "Promised Payment Amount": "promised_payment_amount", "Notes": "notes",
        }
        result.update({arg: _link_id(p[name]) if name == "Billing Term" else p[name] for name, arg in mapping.items() if name in p})
        return result
    if entity == "payment":
        result = {
            "charge_id": _link_id(p[PaymentFields.CHARGE]), "deal_id": _link_id(p[PaymentFields.DEAL_LINK]),
            "direction": p[PaymentFields.DIRECTION], "amount": p[PaymentFields.AMOUNT],
            "currency": p[PaymentFields.CURRENCY], "paid_at": p[PaymentFields.PAID_AT],
            "status": p[PaymentFields.STATUS], "document_requirement": p[PaymentFields.DOCUMENT_REQUIREMENT],
            "document_status": p[PaymentFields.DOCUMENT_STATUS],
        }
        mapping = {
            "Payment Term": "payment_term_id", "Reference": "reference",
            "Method": "method", "Counterparty Contact": "counterparty_contact_id",
            "Counterparty Organization": "counterparty_organization_id", "Notes": "notes",
        }
        result.update({arg: _link_id(p[name]) if "Counterparty" in name or name == "Payment Term" else p[name] for name, arg in mapping.items() if name in p})
        return result
    raise CommercialRoutingError(f"unsupported commercial completion entity: {entity}")


class CommercialCompletionRouter:
    """Single production completion authority for the approved V2 entities."""

    def __init__(self, *, queue: Callable[[str, dict[str, Any]], Any], contracts=None):
        self._queue = queue
        self._contracts = contracts

    def start(self, entity: str, *, current_values=None, source_context=None, identity=None) -> CompletionRoute:
        if entity not in SUPPORTED_COMPLETION_ENTITIES:
            return CompletionRoute("BLOCK", entity, reason="commercial entity is not approved for S2C")
        writer = CommercialCompletionWriter(
            entity, current_values or {}, source_context or {}, identity or {},
            contracts=self._contracts or CommercialCompletionWriter.__dataclass_fields__["contracts"].default_factory(),
        )
        return self._inspect(CompletionSession.start(writer))

    def restore(self, state: Mapping[str, Any]) -> CompletionRoute:
        try:
            session = deserialize_completion_session(state)
            field = session.active.next_field()
            if field is None:
                return CompletionRoute(
                    "BLOCK", session.active.target_entity, session=session,
                    reason="persisted completion is already complete",
                )
            return CompletionRoute(
                "CLARIFY", session.active.target_entity, session=session,
                field_name=field.field_name, field_type=field.input_type,
                **self._presentation(session.active.target_entity, field.field_name),
            )
        except (KeyError, TypeError, ValueError, CompletionBlockedError, CommercialRoutingError) as exc:
            return CompletionRoute("BLOCK", "commercial", reason=str(exc))

    def answer(self, session: CompletionSession, field_name: str, value: Any) -> CompletionRoute:
        try:
            return self._inspect(session.answer(field_name, value))
        except (ValueError, CompletionBlockedError) as exc:
            return CompletionRoute("BLOCK", session.active.target_entity, session=session, reason=str(exc))

    def answer_human(
        self,
        session: CompletionSession,
        value: Any,
        *,
        link_lookup: Callable[[str, str, int], Any] | None = None,
        scope: str = "",
    ) -> CompletionRoute:
        """Accept a user-facing answer without weakening canonical validation.

        Links are resolved by the injected bounded lookup and then passed to
        the same ``answer`` method.  A caller may use this seam for Contact,
        Organization, Deal, or Payment Term lookups; no storage identifier is
        ever requested from the user.
        """
        field = session.active.next_field()
        if field is None:
            return self._inspect(session)
        if field.input_type.name != "LINK":
            return self.answer(session, field.field_name, value)
        if link_lookup is None or not scope:
            return CompletionRoute(
                "BLOCK", session.active.target_entity, session=session,
                field_name=field.field_name,
                reason="לא ניתן לזהות את הגורם לפי השם כרגע.",
                **self._presentation(session.active.target_entity, field.field_name),
            )
        from commercial_completion_ux import resolve_human_link
        entity = {
            "counterparty_contact": "contact",
            "counterparty_organization": "organization",
            "origin_lead": "lead",
            "owner": "owner",
            "deal": "deal",
            "billing_term": "payment_term",
            "charge": "charge",
        }.get(field.field_name, session.active.target_entity)
        resolution = resolve_human_link(
            entity, str(value), link_lookup, scope=scope,
            create_allowed=entity == "organization",
        )
        if resolution.status == "resolved":
            return self.answer(session, field.field_name, resolution.canonical_value)
        return CompletionRoute(
            "CLARIFY" if resolution.choices else "BLOCK",
            session.active.target_entity, session=session,
            field_name=field.field_name, field_type=field.input_type,
            choices=tuple(choice.label for choice in resolution.choices),
            reason=resolution.reason,
            **self._presentation(session.active.target_entity, field.field_name),
        )

    def _inspect(self, session: CompletionSession) -> CompletionRoute:
        writer = session.active
        field = writer.next_field()
        if field is not None:
            return CompletionRoute(
                "CLARIFY", writer.target_entity, session=session,
                field_name=field.field_name, field_type=field.input_type,
                **self._presentation(writer.target_entity, field.field_name),
            )
        try:
            payload = writer.complete_payload()
            tool = MUTATION_TOOLS[writer.target_entity]
            # The exact dict is handed to the existing queue; it is never
            # changed after this point, preserving Gateway fingerprint parity.
            inputs = _primitive_inputs(writer.target_entity, payload)
            result = self._queue(tool, inputs)
        except (KeyError, ValueError, CompletionBlockedError) as exc:
            return CompletionRoute("BLOCK", writer.target_entity, session=session, reason=str(exc))
        return CompletionRoute(
        "TOOL", writer.target_entity, session=session, tool_name=tool,
            tool_inputs=inputs, queue_outcome=result,
            reason="queued through existing ActionGateway boundary",
        )

    @staticmethod
    def _presentation(entity: str, field_name: str) -> dict[str, Any]:
        from commercial_completion_ux import field_presentation
        from commercial_completion import ENTITY_CONTRACTS

        presentation = field_presentation(
            entity, ENTITY_CONTRACTS[entity].field(field_name)
        )
        from commercial_completion_ux import render_prompt
        return {
            "user_label": presentation.user_label,
            "prompt": render_prompt(presentation),
            "choices": presentation.choices,
        }


__all__ = [
    "CommercialCompletionRouter", "CommercialRoutingError", "CompletionRoute",
    "MUTATION_TOOLS", "SUPPORTED_COMPLETION_ENTITIES",
    "serialize_completion_session", "deserialize_completion_session",
]
