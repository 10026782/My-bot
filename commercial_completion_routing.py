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
from airtable_schema import (
    ChargeFields, ContactFields, DealFields, OrganizationFields, PaymentFields, PaymentTermFields,
)


SUPPORTED_COMPLETION_ENTITIES = frozenset(
    {"deal", "payment_term", "organization", "charge", "payment"}
)
# DIAMOND PATH nested-entity approval continuation (owner decision):
# "contact" is deliberately NOT in this set and must never be added to it —
# router.start("contact", ...) must keep failing closed with BLOCK, exactly
# like today. "Do NOT change existing standalone CREATE_CONTACT routing" /
# "Nested Contact creation is entered only from an active parent
# CommercialCompletionSession" — begin_nested() constructs a Contact
# CommercialCompletionWriter directly and never consults this set, which is
# what makes that the only entry point.

MUTATION_TOOLS = {
    "deal": "crm_create_deal",
    "payment_term": "crm_create_payment_term",
    "organization": "crm_find_or_create_organization",
    "charge": "crm_create_charge",
    "payment": "crm_create_charge_payment",
    # DIAMOND PATH: nested-only, see the SUPPORTED_COMPLETION_ENTITIES note above.
    "contact": "crm_find_or_create_contact",
}

# DIAMOND PATH nested-entity approval continuation: which entities offer
# "no match -> ליצור X חדש?" at all (both now have a canonical find-or-create
# writer + EntityContract), and each one's field_name for its own "name" —
# these differ (organization's is "organization_name", not "name").
_NESTED_CREATE_ENTITIES = frozenset({"organization", "contact"})
_NESTED_CREATE_NAME_FIELD = {"organization": "organization_name", "contact": "name"}
_CREATE_CONFIRM_WORDS = frozenset({"כן", "yes", "y", "אישור", "מאשר"})
_CREATE_DECLINE_WORDS = frozenset({"לא", "no", "n", "ביטול", "בטל"})
_CREATE_CONFIRM_CHOICES = ("כן", "לא")


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
    # Parallel to `choices` by index, when set: a short, callback_data-safe
    # token per choice a channel adapter can put in callback_data instead of
    # the (potentially long, non-unique) display label — see
    # BUG-5-CALLBACK-TOKEN. Empty when the choices are already short/unique
    # enough to send as-is (SELECT enum values, the fixed Contact/
    # Organization picker) — a channel adapter falls back to the literal
    # choice text in that case, unchanged from before this field existed.
    choice_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class NestedResumeOutcome:
    """Result of CommercialCompletionRouter.resume_nested() — see its own
    docstring. Three shapes, deliberately never conflated (owner decision):

      "resumed"   — the exact continuation this approval was minted for was
                    found, folded, and inspection continued. `route` carries
                    the next step (CLARIFY/TOOL/BLOCK) exactly like any other
                    router call.
      "mismatch"  — a DIFFERENT session now occupies this slot (or nothing is
                    parked at all). Fail-closed: the caller must not touch
                    session_store — the parked state, whatever it is, is not
                    this call's to alter.
      "corrupted" — this IS the exact continuation (nonce/shape correlated)
                    but it could not actually be resumed (no evidence record
                    id, or resume_parent() itself refused). The caller must
                    actively clean it up: `session_to_abandon` is that same
                    correlated session, ready for .abandon_nested() and
                    persisting back — never left parked forever.
    """

    status: str
    route: "CompletionRoute | None" = None
    session_to_abandon: CompletionSession | None = None
    reason: str = ""


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
        # BUG-ORGANIZATION-CREATE-PARAM-MISMATCH (production-reported,
        # 06/09/2026): this sent {"display_name": ...} into
        # tool_inputs, but commercial_crm.find_or_create_organization()'s
        # actual parameter (and action_validator.py's/tools/dispatcher.py's
        # crm_find_or_create_organization allowlist, both keyed on
        # "organization_name") is organization_name -- the mismatch made
        # every nested-create-confirmed Organization fail closed at
        # action_validator's presence check ("missing ['organization_name']")
        # immediately after the owner answered "כן", with no way to
        # recover short of retyping the whole request.
        return {"organization_name": p[OrganizationFields.NAME]}
    if entity == "deal":
        result = {
            "name": p[DealFields.NAME], "domain": p[DealFields.DOMAIN],
            "owner_id": _link_id(p[DealFields.OWNER]),
        }
        optional = {
            DealFields.ORIGIN_LEAD: "origin_lead_id",
            DealFields.STAGE: "stage", DealFields.NOTES: "notes",
            DealFields.COUNTERPARTY_CONTACT: "counterparty_contact_id",
            DealFields.COUNTERPARTY_ORGANIZATION: "counterparty_organization_id",
            DealFields.DEAL_TYPE_CODE: "deal_type_code",
            DealFields.RELATIONSHIP_TYPE: "relationship_type",
            # DIAMOND — BUSINESS FIELDS MIGRATION: canonical replacement for
            # the two entries above (see DealFields.BUSINESS_DEAL_TYPE's own
            # comment) — the two old entries stay mapped for compatibility,
            # never removed.
            DealFields.BUSINESS_DEAL_TYPE: "business_deal_type",
            DealFields.RELATIONSHIP_ROLE: "relationship_role",
            DealFields.ENGAGEMENT_DURATION: "engagement_duration",
            DealFields.CURRENCY: "currency",
            DealFields.COMMERCIAL_STATUS: "commercial_status",
            DealFields.START_DATE: "start_date",
            # BUG-DIAMOND-EXPECTED-VALUE-RANGE: replaces DealFields.AMOUNT
            # ("סכום" / "amount") here — never written by this flow anymore.
            DealFields.ESTIMATED_VALUE_BASIS: "estimated_value_basis",
            DealFields.ESTIMATED_VALUE_RANGE: "estimated_value_range",
            DealFields.ESTIMATED_VALUE_NOTES: "estimated_value_notes",
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
    if entity == "contact":
        # DIAMOND PATH nested-entity approval continuation: contact is never
        # a SUPPORTED_COMPLETION_ENTITIES top-level entity (router.start()
        # rejects it) — reachable only via begin_nested(), per owner
        # decision "nested Contact creation is entered only from an active
        # parent CompletionSession". Field names already match
        # find_or_create_contact()'s kwargs 1:1, unlike organization/deal.
        result = {"name": p[ContactFields.NAME], "phone": p[ContactFields.PHONE]}
        optional = {
            ContactFields.EMAIL: "email", ContactFields.COMPANY: "company",
            ContactFields.ROLE_CATEGORY: "role_category",
        }
        result.update({arg: p[name] for name, arg in optional.items() if name in p})
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

    def resume_nested(
        self, state: Mapping[str, Any], *,
        expected_nested_entity: str, expected_return_field: str,
        expected_nonce: str, canonical_record_id: str,
    ) -> NestedResumeOutcome:
        """DIAMOND PATH: reload a parked nested CompletionSession after its
        queued create was approved and executed, verify it is EXACTLY the
        continuation this approval was minted for (nonce + shape
        correlation — see ContinuationRef's own docstring), fold
        canonical_record_id into the parent, and continue inspection.

        Pure and self-contained: takes the persisted state dict plus the
        expected identifiers (whatever the caller read off its
        ContinuationRef) and returns a NestedResumeOutcome — no
        session_store/chat_id/channel knowledge, mirroring every other
        method on this class. See NestedResumeOutcome's own docstring for
        the mismatch-vs-corrupted distinction this exists to make explicit.
        """
        try:
            session = deserialize_completion_session(state)
        except (KeyError, TypeError, ValueError, CompletionBlockedError, CommercialRoutingError) as exc:
            return NestedResumeOutcome("mismatch", reason=str(exc))
        if len(session.frames) < 2:
            return NestedResumeOutcome("mismatch", reason="no nested frame parked in this session")
        active = session.active
        nonce = dict(active.current_values).get("_pending_approval_nonce")
        return_field = session.frames[-1].return_field
        if (
            active.target_entity != expected_nested_entity
            or return_field != expected_return_field
            or nonce != expected_nonce
        ):
            return NestedResumeOutcome(
                "mismatch", reason="continuation does not match the parked nested session",
            )
        if not canonical_record_id:
            # This IS the exact continuation (nonce correlated), but no
            # canonical record id could be extracted as evidence — there is
            # nothing to fold, and per owner decision this must not be left
            # parked forever.
            return NestedResumeOutcome(
                "corrupted", session_to_abandon=session,
                reason="no canonical record id evidence for an otherwise-correlated continuation",
            )
        try:
            resumed = session.resume_parent(canonical_record_id)
        except CompletionBlockedError as exc:
            return NestedResumeOutcome("corrupted", session_to_abandon=session, reason=str(exc))
        return NestedResumeOutcome("resumed", route=self._inspect(resumed))

    def answer(self, session: CompletionSession, field_name: str, value: Any) -> CompletionRoute:
        try:
            return self._inspect(session.answer(field_name, value))
        except (ValueError, CompletionBlockedError) as exc:
            return CompletionRoute(
                "BLOCK", session.active.target_entity, session=session,
                reason=self._validation_failure_message(
                    session.active.target_entity, field_name, exc,
                ),
            )

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
        # Compatibility for an already-canonical internal value supplied by
        # trusted callers/tests. The UI never asks for or renders this form;
        # human text still follows the resolver path below.
        from commercial_completion import _RECORD_ID_RE
        if isinstance(value, str) and _RECORD_ID_RE.fullmatch(value.strip()):
            return self.answer(session, field.field_name, value.strip())
        # BUG-5-CALLBACK-TOKEN: a prior CLARIFY on this same field may have
        # persisted a token -> canonical-candidate map (see the resolver
        # branch below). A token reply (typed or via a callback button)
        # resolves directly to the exact candidate the user was shown —
        # never a fresh free-text search, which cannot tell two candidates
        # with an identical display label apart. The marker is single-use:
        # it is cleared here whether or not the token is recognized, so a
        # stale token can never resolve once the flow has moved on.
        pending = session.active.current_values.get("_ux_pending_link_choice")
        if isinstance(pending, Mapping) and pending.get("field") == field.field_name:
            picked = dict(pending.get("tokens") or {}).get(str(value or "").strip())
            from dataclasses import replace
            from commercial_completion import _CompletionFrame
            cleared = replace(
                session.active,
                current_values={
                    key: val for key, val in session.active.current_values.items()
                    if key != "_ux_pending_link_choice"
                },
            )
            session = CompletionSession((_CompletionFrame(cleared),))
            if picked:
                target_field = (
                    "counterparty_organization"
                    if field.field_name == "counterparty_contact"
                    and cleared.current_values.get("_ux_counterparty_kind") == "organization"
                    else field.field_name
                )
                return self.answer(session, target_field, picked)
            # Unrecognized token text falls through to the normal paths
            # below (counterparty picker / free-text resolver search) with
            # the stale marker already cleared.
        # DIAMOND PATH nested-entity approval continuation: a prior CLARIFY
        # on this same field offered "ליצור X חדש?" — resolve the [כן]/[לא]
        # reply here, before anything else gets a chance to reinterpret the
        # value as a picker choice or a fresh name search. Mutually
        # exclusive with the _ux_pending_link_choice marker above (that one
        # is set only when resolve_human_link() found MULTIPLE matches;
        # this one only when it found NONE) — never both at once for the
        # same field. Marker is cleared unconditionally, same single-use
        # discipline as the token marker above.
        pending_create = session.active.current_values.get("_ux_pending_nested_create")
        if isinstance(pending_create, Mapping) and pending_create.get("field") == field.field_name:
            from dataclasses import replace
            from commercial_completion import _CompletionFrame
            cleared = replace(
                session.active,
                current_values={
                    key: val for key, val in session.active.current_values.items()
                    if key != "_ux_pending_nested_create"
                },
            )
            cleared_session = CompletionSession((_CompletionFrame(cleared),))
            choice = str(value or "").strip()
            if choice in _CREATE_CONFIRM_WORDS:
                nested_entity = str(pending_create.get("nested_entity") or "")
                name_field = _NESTED_CREATE_NAME_FIELD.get(nested_entity)
                if not name_field:
                    return CompletionRoute(
                        "BLOCK", cleared_session.active.target_entity, session=cleared_session,
                        reason="לא ניתן להשלים את היצירה כרגע.",
                    )
                # Same counterparty_contact -> counterparty_organization
                # redirect the "resolved" branch above already applies —
                # field.field_name is the Deal field being ASKED about
                # ("counterparty_contact" even when the answer identifies an
                # Organization); the LINK it must ultimately fill differs.
                return_field = (
                    "counterparty_organization"
                    if field.field_name == "counterparty_contact" and nested_entity == "organization"
                    else field.field_name
                )
                nested = cleared_session.begin_nested(
                    nested_entity, return_field=return_field,
                    current_values={name_field: str(pending_create.get("candidate_name") or "")},
                )
                return self._inspect(nested)
            if choice in _CREATE_DECLINE_WORDS:
                return CompletionRoute(
                    "CLARIFY", cleared_session.active.target_entity, session=cleared_session,
                    field_name=field.field_name, field_type=field.input_type,
                    **self._presentation(cleared_session.active.target_entity, field.field_name),
                )
            # Neither כן nor לא: re-render the exact same confirm question
            # rather than silently reinterpreting free text as a new
            # candidate name or dropping the pending decision — the marker
            # (with its original prompt) stays in place, unmodified.
            same_prompt = str(pending_create.get("prompt") or "")
            return CompletionRoute(
                "CLARIFY", session.active.target_entity, session=session,
                field_name=field.field_name, field_type=field.input_type,
                reason=same_prompt, prompt=same_prompt, choices=_CREATE_CONFIRM_CHOICES,
            )
        if field.field_name == "counterparty_contact":
            choice = str(value or "").strip().casefold()
            if choice in {"ארגון", "organization", "company"}:
                from dataclasses import replace
                marked = replace(
                    session.active,
                    current_values={
                        **dict(session.active.current_values),
                        "_ux_counterparty_kind": "organization",
                    },
                )
                from commercial_completion import _CompletionFrame
                session = CompletionSession((_CompletionFrame(marked),))
                return CompletionRoute(
                    "CLARIFY", "deal", session=session,
                    field_name=field.field_name, field_type=field.input_type,
                    user_label="ארגון", prompt="מה שם הארגון?",
                )
            if choice in {"איש קשר", "contact", "person"}:
                from dataclasses import replace
                marked = replace(
                    session.active,
                    current_values={
                        **dict(session.active.current_values),
                        "_ux_counterparty_kind": "contact",
                    },
                )
                from commercial_completion import _CompletionFrame
                session = CompletionSession((_CompletionFrame(marked),))
                return CompletionRoute(
                    "CLARIFY", "deal", session=session,
                    field_name=field.field_name, field_type=field.input_type,
                    user_label="איש קשר", prompt="מה שם איש הקשר?",
                )
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
        if field.field_name == "counterparty_contact":
            entity = session.active.current_values.get("_ux_counterparty_kind", "contact")
        resolution = resolve_human_link(
            entity, str(value),
            lambda query, _scope, limit: link_lookup(
                query, f"{entity}:{scope}", limit
            ),
            scope=scope,
            create_allowed=entity in _NESTED_CREATE_ENTITIES,
        )
        if resolution.status == "resolved":
            target_field = (
                "counterparty_organization"
                if field.field_name == "counterparty_contact" and entity == "organization"
                else field.field_name
            )
            return self.answer(session, target_field, resolution.canonical_value)
        if resolution.status == "create":
            # DIAMOND PATH nested-entity approval continuation: mark the
            # PARENT (still a single frame — begin_nested() is deliberately
            # NOT called yet, per owner decision) with enough to either
            # start the nested completion on "כן" or drop the offer
            # untouched on "לא"/anything else, with zero rollback needed
            # either way since no frame was ever pushed here.
            from dataclasses import replace
            from commercial_completion import _CompletionFrame
            marked = replace(
                session.active,
                current_values={
                    **dict(session.active.current_values),
                    "_ux_pending_nested_create": {
                        "field": field.field_name, "nested_entity": entity,
                        "candidate_name": str(value).strip(), "prompt": resolution.reason,
                    },
                },
            )
            marked_session = CompletionSession((_CompletionFrame(marked),))
            return CompletionRoute(
                "CLARIFY", marked_session.active.target_entity, session=marked_session,
                field_name=field.field_name, field_type=field.input_type,
                reason=resolution.reason, prompt=resolution.reason,
                choices=_CREATE_CONFIRM_CHOICES,
            )
        # Single-owner merge: the resolver's own choices (when it found
        # candidates to disambiguate) take priority over the field's static
        # presentation choices; never pass both `choices=` and a
        # `**presentation` that also carries `choices` into the same call —
        # that is a duplicate-keyword TypeError, not a value conflict.
        presentation = self._presentation(session.active.target_entity, field.field_name)
        choice_tokens: tuple[str, ...] = ()
        if resolution.choices:
            presentation = {**presentation, "choices": tuple(choice.label for choice in resolution.choices)}
            choice_tokens = tuple(choice.token for choice in resolution.choices)
            # BUG-5-CALLBACK-TOKEN: persist token -> canonical candidate so a
            # later reply (button click or typed token) resolves the exact
            # candidate shown, without a fresh label search that can't
            # distinguish two candidates sharing a display label.
            if resolution.candidate_ids and len(resolution.candidate_ids) == len(resolution.choices):
                from dataclasses import replace
                pending_map = {
                    choice.token: candidate_id
                    for choice, candidate_id in zip(resolution.choices, resolution.candidate_ids)
                    if candidate_id
                }
                if pending_map:
                    marked = replace(
                        session.active,
                        current_values={
                            **dict(session.active.current_values),
                            "_ux_pending_link_choice": {
                                "field": field.field_name, "tokens": pending_map,
                            },
                        },
                    )
                    from commercial_completion import _CompletionFrame
                    session = CompletionSession((_CompletionFrame(marked),))
        return CompletionRoute(
            "CLARIFY" if resolution.choices else "BLOCK",
            session.active.target_entity, session=session,
            field_name=field.field_name, field_type=field.input_type,
            reason=resolution.reason,
            choice_tokens=choice_tokens,
            **presentation,
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
        # DIAMOND PATH nested-entity approval continuation: a nested frame
        # (len(session.frames) > 1) reaching completion here must be queued
        # with enough info for the caller to build a ContinuationRef and
        # resume the PARENT after approval — this module has no
        # session_store/chat_id/channel knowledge (see module docstring),
        # so it only mints the nonce (a pure operation) and embeds it into
        # the same nested frame that gets persisted, then hands the caller
        # everything else it cannot compute itself. The queue() callback's
        # 3rd positional arg is entirely new and optional — every existing
        # (root-only) call site/test passes a 2-arg callable and is
        # unaffected: this branch is unreachable unless begin_nested() was
        # called somewhere upstream in this exact session.
        continuation_hint: dict[str, Any] | None = None
        if len(session.frames) > 1:
            import secrets
            from dataclasses import replace
            from commercial_completion import _CompletionFrame
            nonce = secrets.token_hex(8)
            marked_writer = replace(
                writer,
                current_values={**dict(writer.current_values), "_pending_approval_nonce": nonce},
            )
            frames = list(session.frames)
            frames[-1] = replace(frames[-1], writer=marked_writer)
            session = CompletionSession(tuple(frames))
            writer = session.active
            continuation_hint = {
                "nested_entity": writer.target_entity,
                "return_field": session.frames[-1].return_field,
                "nonce": nonce,
            }
        try:
            payload = writer.complete_payload()
            tool = MUTATION_TOOLS[writer.target_entity]
            # The exact dict is handed to the existing queue; it is never
            # changed after this point, preserving Gateway fingerprint parity.
            inputs = _primitive_inputs(writer.target_entity, payload)
            result = (
                self._queue(tool, inputs, continuation_hint)
                if continuation_hint is not None else self._queue(tool, inputs)
            )
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

    @staticmethod
    def _validation_failure_message(entity: str, field_name: str, exc: Exception) -> str:
        """Business-safe BLOCK text for a rejected answer.

        VALIDATION-TEXT: commercial_completion.validate_value() raises with
        the internal field_name and (for SELECT) a Python repr of the raw
        enum-code tuple — exactly right for logs/tests, never right to send
        to a Hebrew business user verbatim. Canonical validation semantics
        (which values are accepted) are untouched here; only how the
        rejection is worded for a human changes.
        """
        from commercial_completion import ENTITY_CONTRACTS, UnknownFieldError
        from commercial_completion_ux import field_presentation

        try:
            presentation = field_presentation(entity, ENTITY_CONTRACTS[entity].field(field_name))
        except (KeyError, UnknownFieldError):
            return "❌ הערך שהוזן לא תקין. נא לנסות שוב."
        if presentation.choices:
            options = " / ".join(str(choice) for choice in presentation.choices)
            return f'❌ הערך שהוזן לא תקין עבור "{presentation.user_label}". אפשרויות: {options}'
        return f'❌ הערך שהוזן לא תקין עבור "{presentation.user_label}". נא לנסות ערך אחר.'


__all__ = [
    "CommercialCompletionRouter", "CommercialRoutingError", "CompletionRoute",
    "MUTATION_TOOLS", "SUPPORTED_COMPLETION_ENTITIES",
    "serialize_completion_session", "deserialize_completion_session",
]
