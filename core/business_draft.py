"""BusinessDraft — the reusable, channel-neutral pre-confirm draft envelope.

BUSINESSDRAFT PHASE 1 (core generalization): wraps the existing proven
completion/edit primitives — ``commercial_completion.CommercialCompletionWriter``
(field contracts, validation, missing-field detection),
``commercial_completion_routing`` (CREATE payload translation, mutation tool
map) and ``core/draft_fields.py`` (the SET_FIELD/CLEAR_FIELD/MOVE_FIELD/
SWAP_FIELDS edit vocabulary) — into one envelope object, per
``docs/architecture/BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md``'s "Final
BusinessDraft Object"/"Final Lifecycle"/"Final Edit Contract"/"Entity Adapter
Contract" sections. It does not replace any of those modules, add
persistence (Phase 2), or migrate any entity's live callers (Phase 3+).

Scope boundary: this module owns draft mutation/lifecycle/confirmation only.
It never touches Airtable, never calls a Golden Writer, never mutates an
ActionContract, and carries no channel UX text (Hebrew strings stay in
``commercial_completion_ux.py``, unchanged).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from commercial_completion import (
    ENTITY_CONTRACTS,
    CommercialCompletionWriter,
    EntityContract,
    FieldContract,
    InputType,
    _coerce_value,
    validate_value,
)
from commercial_completion_routing import MUTATION_TOOLS, _link_id, _primitive_inputs

DRAFT_TTL_SECONDS = 1800  # matches core/draft_flow.DRAFT_TTL_SECONDS


class BusinessDraftError(ValueError):
    """Fail-closed error for an invalid BusinessDraft operation."""


class UnsupportedOperationError(BusinessDraftError):
    """The entity/operation pair has no canonical writer or field mapping yet."""


class DraftConflictError(BusinessDraftError):
    """PHASE 2: optimistic-concurrency CAS failure — the stored draft's
    version no longer matches what the caller loaded (someone else saved
    in between)."""


class DraftIdentityMismatchError(BusinessDraftError):
    """PHASE 2: a load/save was attempted with a (tenant_id, actor_user_id,
    source_channel) that doesn't match the persisted draft's own binding.
    Raised rather than returned as None so a binding violation is never
    silently indistinguishable from "no draft exists"."""


class DraftOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


class DraftState(str, Enum):
    """Pre-execution states only. ACTION_CONTRACT_CREATED/WRITE_PENDING/
    WRITTEN are deliberately not modeled here — the frozen contract defines
    them as thin read-through labels over ``ActionContract.status``, never an
    independently tracked BusinessDraft state (no second source of truth)."""

    CAPTURED = "CAPTURED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    EDITING = "EDITING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


_TERMINAL_STATES = frozenset({DraftState.CONFIRMED, DraftState.CANCELLED, DraftState.EXPIRED, DraftState.FAILED})
_MUTABLE_STATES = frozenset(
    {DraftState.CAPTURED, DraftState.NEEDS_CLARIFICATION, DraftState.READY_FOR_REVIEW, DraftState.EDITING}
)
_EMPTY = (None, "", [], ())


# ══════════════════════════════════════════════════
# Entity adapter — freeze doc "Entity Adapter Contract"
# ══════════════════════════════════════════════════

# Phase 0 canonical UPDATE writers/tools (commercial_crm.py). Only entities
# with a closed canonical UPDATE boundary get one here — every other entity
# (organization, charge, contact/lead's own non-dispatcher writers) stays
# UPDATE-unsupported in this generic adapter rather than guessing a mapping
# with no canonical writer backing it.
_UPDATE_MUTATION_TOOLS: dict[str, str] = {
    "deal": "crm_update_deal",
    "payment_term": "crm_update_payment_term",
    "payment": "crm_update_payment",
}

# completion field_name -> canonical UPDATE writer kwarg name, restricted to
# exactly the kwargs each Phase 0 writer allows (commercial_crm.py's
# _DEAL_UPDATE_ALLOWED / _PAYMENT_TERM_UPDATE_ALLOWED / _PAYMENT_UPDATE_ALLOWED).
# Kwarg names intentionally mirror create_deal()/create_payment_term()'s own
# names (the update writers' own docstrings: "fields keys are create_X()'s
# own kwarg names") — this is the same naming convention _primitive_inputs()
# already uses for CREATE, applied to the update-allowed subset.
_UPDATE_FIELD_MAP: dict[str, dict[str, str]] = {
    "deal": {
        "name": "name", "domain": "domain", "owner": "owner_id", "stage": "stage",
        "notes": "notes", "counterparty_contact": "counterparty_contact_id",
        "counterparty_organization": "counterparty_organization_id",
        "deal_type": "deal_type_code", "relationship_type": "relationship_type",
        "business_deal_type": "business_deal_type", "relationship_role": "relationship_role",
        "engagement_duration": "engagement_duration", "currency": "currency",
        "commercial_status": "commercial_status", "start_date": "start_date",
        "estimated_value_basis": "estimated_value_basis",
        "estimated_value_range": "estimated_value_range",
        "estimated_value_notes": "estimated_value_notes",
    },
    "payment_term": {
        "name": "name", "calculation_type": "calc_type", "fixed_amount": "fixed_amount",
        "rate_pct": "rate_pct", "calculation_basis": "calc_basis",
        "trigger_type": "trigger_type", "trigger_date": "trigger_date",
        "cadence": "cadence", "vat_rule": "vat_rule", "start_date": "start_date",
        "end_date": "end_date", "notes": "notes",
    },
    "payment": {
        "reference": "reference", "method": "method",
        "counterparty_contact": "counterparty_contact_id",
        "counterparty_organization": "counterparty_organization_id",
        "notes": "notes", "document_requirement": "document_requirement",
        "document_status": "document_status",
    },
}
_UPDATE_LINK_FIELDS = frozenset({"counterparty_contact", "counterparty_organization"})


# ══════════════════════════════════════════════════
# PHASE 3 — Deal primitive-kwarg <-> completion-field-name translation.
# Pure, no I/O. Used by app.py's single Deal seam inside
# _queue_approval_detailed_impl() -- see the Phase 3 plan and
# docs/architecture/BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md.
# ══════════════════════════════════════════════════

# CREATE accepts one field UPDATE deliberately excludes (origin_lead_id is
# immutable after creation, per commercial_crm.py's own comment) -- derived
# from _UPDATE_FIELD_MAP, not hand-duplicated, so the 18 shared fields can't
# drift apart between the two maps.
_CREATE_FIELD_MAP: dict[str, dict[str, str]] = {
    "deal": {**_UPDATE_FIELD_MAP["deal"], "origin_lead": "origin_lead_id"},
}

# Primitive kwargs each Golden Writer legally accepts but that have no
# ENTITY_CONTRACTS["deal"] field-contract equivalent -- verified
# independently against commercial_crm.create_deal()'s/update_deal()'s
# actual signatures (not assumed equal just because they happen to match).
# These pass straight through the BusinessDraft seam unvalidated, exactly as
# they do today.
_CREATE_PASSTHROUGH: dict[str, frozenset[str]] = {
    "deal": frozenset({"venture_id", "contact_ids", "priority", "risk_level"}),
}
_UPDATE_PASSTHROUGH: dict[str, frozenset[str]] = {
    "deal": frozenset({"venture_id", "contact_ids", "priority", "risk_level"}),
}

# The Deal "owner" completion field is handled separately by the caller
# (canonicalized through the existing authenticated-owner resolver before
# BusinessDraft field validation -- tools/dispatcher.py's
# _resolve_authenticated_crm_owner()), never through these generic maps.
_OWNER_PRIMITIVE_KEY: dict[str, str] = {"deal": "owner_id"}


def _invert_field_map(mapping: Mapping[str, str]) -> dict[str, str]:
    return {primitive: field_name for field_name, primitive in mapping.items()}


def _split_primitive_inputs(
    field_map: Mapping[str, str],
    passthrough_keys: frozenset[str],
    owner_key: str | None,
    primitive_inputs: Mapping[str, Any],
) -> tuple[dict[str, Any], frozenset[str], dict[str, Any]]:
    """Shared splitter for CREATE/UPDATE. Returns ``(mapped_fields,
    unrecognized_keys, passthrough_kwargs)`` -- ``passthrough_kwargs`` is a
    dict of the RAW primitive key/value pairs (never re-keyed into
    completion field_name space), so a caller merging it back never risks
    the namespace collision that comparing a primitive key against a
    completion-field-name-keyed dict would create (e.g. primitive
    ``"owner_id"`` vs. completion ``"owner"`` never legitimately share a
    key, but some fields, like ``"name"``/``"domain"``/``"stage"``, happen
    to be spelled identically in both spaces -- returning the primitive
    dict directly sidesteps that ambiguity entirely).
    """
    reverse = _invert_field_map(field_map)
    mapped: dict[str, Any] = {}
    unrecognized: set[str] = set()
    passthrough_kwargs: dict[str, Any] = {}
    for key, value in primitive_inputs.items():
        if key == owner_key:
            continue
        if key in reverse:
            mapped[reverse[key]] = value
        elif key in passthrough_keys:
            passthrough_kwargs[key] = value
        else:
            unrecognized.add(key)
    return mapped, frozenset(unrecognized), passthrough_kwargs


def fields_from_primitive_create(
    entity_type: str, primitive_inputs: Mapping[str, Any]
) -> tuple[dict[str, Any], frozenset[str], dict[str, Any]]:
    """Primitive kwarg space -> completion field_name space, for CREATE.

    Returns ``(mapped_fields, unrecognized_keys, passthrough_kwargs)``.
    ``unrecognized_keys`` is never silently dropped by this function -- the
    caller must fail closed on a non-empty result (e.g. the confirmed
    ``tools/schemas.py`` "amount" drift for ``crm_create_deal``, which
    ``commercial_crm.create_deal()`` has never accepted). The owner
    primitive key is excluded from all three outputs -- it is resolved and
    inserted by the caller separately.
    """
    return _split_primitive_inputs(
        _CREATE_FIELD_MAP.get(entity_type, {}),
        _CREATE_PASSTHROUGH.get(entity_type, frozenset()),
        _OWNER_PRIMITIVE_KEY.get(entity_type),
        primitive_inputs,
    )


def fields_from_primitive_update(
    entity_type: str, primitive_inputs: Mapping[str, Any]
) -> tuple[dict[str, Any], frozenset[str], dict[str, Any]]:
    """Primitive kwarg space -> completion field_name space, for UPDATE.

    Same contract as :func:`fields_from_primitive_create`. ``record_id`` is
    always treated as passthrough (it is not a completion field -- see
    :meth:`BusinessDraft.confirm`'s UPDATE branch, which never produces it).
    """
    return _split_primitive_inputs(
        _UPDATE_FIELD_MAP.get(entity_type, {}),
        _UPDATE_PASSTHROUGH.get(entity_type, frozenset()) | {"record_id"},
        _OWNER_PRIMITIVE_KEY.get(entity_type),
        primitive_inputs,
    )


def fields_from_airtable_record(entity_type: str, raw_fields: Mapping[str, Any]) -> dict[str, Any]:
    """Airtable ``airtable_field``-keyed live record -> completion
    ``field_name`` space, matching what ``BusinessDraft.fields``/
    ``original_fields`` expect. Every ``InputType.LINK`` field is unwrapped
    via ``_link_id()`` (Airtable's ``[record_id]`` list shape -> a bare
    scalar id) generically, by ``input_type`` -- never via an output-side-
    only allowlist like ``_UPDATE_LINK_FIELDS``, which governs a narrower,
    differently-scoped concern (which fields ``build_update_payload()``
    re-wraps on the way *out*).
    """
    contract = ENTITY_CONTRACTS[entity_type]
    result: dict[str, Any] = {}
    for fc in contract.fields:
        if fc.airtable_field not in raw_fields:
            continue
        value = raw_fields[fc.airtable_field]
        if fc.input_type == InputType.LINK:
            value = _link_id(value)
        result[fc.field_name] = value
    return result


@runtime_checkable
class EntityAdapter(Protocol):
    """Smallest stable seam between BusinessDraft and an entity's own field
    contracts. Deliberately a structural Protocol, not an ABC — Phase 1 has
    exactly one implementation (``CommercialEntityAdapter``, generic over
    every registered ``ENTITY_CONTRACTS`` entry); a base class with one
    subclass would be premature abstraction."""

    def get_entity_type(self, entity_type: str) -> str: ...
    def get_field_definitions(self, entity_type: str) -> tuple[FieldContract, ...]: ...
    def get_required_fields(self, entity_type: str, values: Mapping[str, Any]) -> tuple[str, ...]: ...
    def get_editable_fields(self, entity_type: str) -> tuple[str, ...]: ...
    def validate_field(self, entity_type: str, field_name: str, value: Any) -> None: ...
    def validate_draft(self, writer: CommercialCompletionWriter) -> tuple[FieldContract, ...]: ...
    def normalize_field(self, entity_type: str, field_name: str, value: Any) -> Any: ...
    def get_preview_order(self, entity_type: str) -> tuple[str, ...]: ...
    def get_canonical_create_tool(self, entity_type: str) -> str | None: ...
    def get_canonical_update_tool(self, entity_type: str) -> str | None: ...
    def build_create_payload(self, writer: CommercialCompletionWriter) -> dict[str, Any]: ...
    def build_update_payload(
        self, writer: CommercialCompletionWriter, original_fields: Mapping[str, Any]
    ) -> dict[str, Any]: ...


class CommercialEntityAdapter:
    """Generic adapter over ``commercial_completion.ENTITY_CONTRACTS`` plus
    the Phase 0 canonical UPDATE writers. One instance serves every entity —
    no per-entity subclass — reusing ``validate_value``/``_coerce_value``/
    ``_primitive_inputs`` verbatim rather than re-deriving their logic."""

    def __init__(self, contracts: Mapping[str, EntityContract] | None = None):
        self._contracts = contracts or ENTITY_CONTRACTS

    def _contract(self, entity_type: str) -> EntityContract:
        try:
            return self._contracts[entity_type]
        except KeyError as exc:
            raise UnsupportedOperationError(f"unknown entity_type: {entity_type!r}") from exc

    def get_entity_type(self, entity_type: str) -> str:
        return self._contract(entity_type).entity

    def get_field_definitions(self, entity_type: str) -> tuple[FieldContract, ...]:
        return self._contract(entity_type).fields

    def get_required_fields(self, entity_type: str, values: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(f.field_name for f in self._contract(entity_type).fields if f.is_required(values))

    def get_editable_fields(self, entity_type: str) -> tuple[str, ...]:
        return tuple(
            f.field_name for f in self._contract(entity_type).fields
            if f.manual_entry_allowed and not f.is_computed
        )

    def get_update_editable_fields(self, entity_type: str) -> frozenset[str]:
        return frozenset(_UPDATE_FIELD_MAP.get(entity_type, {}))

    def validate_field(self, entity_type: str, field_name: str, value: Any) -> None:
        validate_value(self._contract(entity_type).field(field_name), value)

    def validate_draft(self, writer: CommercialCompletionWriter) -> tuple[FieldContract, ...]:
        return writer.missing_fields()

    def normalize_field(self, entity_type: str, field_name: str, value: Any) -> Any:
        return _coerce_value(self._contract(entity_type).field(field_name), value)

    def get_preview_order(self, entity_type: str) -> tuple[str, ...]:
        return tuple(f.field_name for f in self._contract(entity_type).fields)

    def get_canonical_create_tool(self, entity_type: str) -> str | None:
        return MUTATION_TOOLS.get(entity_type)

    def get_canonical_update_tool(self, entity_type: str) -> str | None:
        return _UPDATE_MUTATION_TOOLS.get(entity_type)

    def build_create_payload(self, writer: CommercialCompletionWriter) -> dict[str, Any]:
        return _primitive_inputs(writer.target_entity, writer.complete_payload())

    def build_update_payload(
        self, writer: CommercialCompletionWriter, original_fields: Mapping[str, Any]
    ) -> dict[str, Any]:
        entity = writer.target_entity
        mapping = _UPDATE_FIELD_MAP.get(entity)
        if mapping is None:
            raise UnsupportedOperationError(f"{entity} has no canonical UPDATE field mapping")
        result: dict[str, Any] = {}
        for field_name, value in writer.current_values.items():
            if field_name not in mapping or value == original_fields.get(field_name):
                continue
            kwarg = mapping[field_name]
            result[kwarg] = _link_id(value) if field_name in _UPDATE_LINK_FIELDS else value
        return result


# ══════════════════════════════════════════════════
# ConfirmedSnapshot — freeze doc "Final Confirmation Boundary"
# ══════════════════════════════════════════════════


@dataclass(frozen=True)
class ConfirmedSnapshot:
    """Deterministic, immutable pre-ActionContract payload. Contains exactly
    what ``ActionContract``'s own ``tool_name``/``normalized_payload``/actor
    fields need — no channel UX text, no Airtable write, no ActionContract
    mutation. Phase 1 stops here; handing this to ``propose_action()`` is a
    later phase's job."""

    draft_id: str
    entity_type: str
    operation: DraftOperation
    tenant_id: str
    actor_role: str
    actor_user_id: str
    actor_display_name: str
    actor_domain_id: str
    actor_external_id: str
    tool_name: str
    tool_inputs: Mapping[str, Any]
    confirmed_at: float


# ══════════════════════════════════════════════════
# BusinessDraft — freeze doc "Final BusinessDraft Object"
# ══════════════════════════════════════════════════


@dataclass(frozen=True)
class BusinessDraft:
    """The mutable pre-confirm draft envelope. Wraps, rather than replaces,
    ``CommercialCompletionWriter``'s own shape (``target_entity`` /
    ``current_values`` / ``source_context`` / ``identity`` / ``contracts``)
    — see the frozen doc's "Final BusinessDraft Object" for the field-by-
    field classification this dataclass implements verbatim. Construct via
    :func:`create_draft`, never directly."""

    draft_id: str
    entity_type: str
    operation: DraftOperation
    tenant_id: str
    actor_role: str
    actor_user_id: str
    source_channel: str
    lifecycle_state: DraftState
    created_at: float
    updated_at: float
    expires_at: float
    fields: Mapping[str, Any] = field(default_factory=dict)
    source_context: Mapping[str, Any] = field(default_factory=dict)
    identity: Mapping[str, Any] = field(default_factory=dict)
    original_fields: Mapping[str, Any] | None = None
    actor_display_name: str = ""
    actor_domain_id: str = ""
    actor_external_id: str = ""
    # Draft-object optimistic-concurrency counter (mirrors ActionContract.
    # version) — NOT a business dedup key. That stays
    # ActionContract.business_action_fingerprint, computed once at confirm
    # time; conflating the two would be a real regression, not a simplification.
    idempotency_key: int = 1
    contracts: Mapping[str, EntityContract] = field(default_factory=lambda: ENTITY_CONTRACTS)
    snapshot: ConfirmedSnapshot | None = None

    # -- internal bridge to the existing proven writer -------------------

    def _writer(self) -> CommercialCompletionWriter:
        return CommercialCompletionWriter(
            self.entity_type, dict(self.fields), dict(self.source_context),
            dict(self.identity), self.contracts,
        )

    @property
    def contract(self) -> EntityContract:
        return self._writer().contract

    # -- validity / completeness ------------------------------------------

    def missing_fields(self) -> tuple[FieldContract, ...]:
        """CREATE-contract missing-required-fields. For UPDATE, "required"
        does not apply the same way (nothing must be refilled to change one
        field) — always empty; see :meth:`is_complete` for UPDATE's own
        completeness rule."""
        if self.operation is DraftOperation.UPDATE:
            return ()
        return self._writer().missing_fields()

    def is_complete(self, adapter: EntityAdapter | None = None) -> bool:
        if self.operation is DraftOperation.UPDATE:
            adapter = adapter or CommercialEntityAdapter(self.contracts)
            try:
                return bool(adapter.build_update_payload(self._writer(), self.original_fields or {}))
            except UnsupportedOperationError:
                return False
        return self._writer().is_complete()

    # -- lifecycle guards ---------------------------------------------------

    def _ensure_mutable(self) -> None:
        if self.lifecycle_state not in _MUTABLE_STATES:
            raise BusinessDraftError(f"draft is not editable in state {self.lifecycle_state.value}")

    def _ensure_editable_for_operation(self, field_name: str, adapter: EntityAdapter) -> None:
        if self.operation is DraftOperation.CREATE:
            return
        if isinstance(adapter, CommercialEntityAdapter):
            allowed = adapter.get_update_editable_fields(self.entity_type)
        else:  # pragma: no cover - structural fallback for a future adapter
            allowed = frozenset()
        if field_name not in allowed:
            raise UnsupportedOperationError(
                f"{field_name!r} is not part of {self.entity_type}'s canonical UPDATE boundary"
            )

    # -- field operations: SET_FIELD / CLEAR_FIELD / MOVE_FIELD / SWAP_FIELDS
    # freeze doc "Final Edit Contract": CommercialCompletionWriter's own thin
    # implementation of draft_fields.py's four operations, using
    # dataclasses.replace() + FieldContract's own type/editability rules —
    # never draft_fields.py's dict-mutation bodies verbatim (this wraps an
    # immutable dataclass writer, not a plain dict).

    def set_field(self, field_name: str, value: Any, *, adapter: EntityAdapter | None = None) -> "BusinessDraft":
        self._ensure_mutable()
        adapter = adapter or CommercialEntityAdapter(self.contracts)
        self._ensure_editable_for_operation(field_name, adapter)
        writer = self._writer().apply_answer(field_name, value)
        return self._replace_fields(dict(writer.current_values))

    def clear_field(self, field_name: str, *, adapter: EntityAdapter | None = None) -> "BusinessDraft":
        self._ensure_mutable()
        adapter = adapter or CommercialEntityAdapter(self.contracts)
        self._ensure_editable_for_operation(field_name, adapter)
        contract = self._writer().contract.field(field_name)
        if contract.is_computed or not contract.manual_entry_allowed:
            raise BusinessDraftError(f"field is not editable: {field_name}")
        fields = dict(self.fields)
        fields.pop(field_name, None)
        return self._replace_fields(fields)

    @staticmethod
    def _assert_compatible(source: FieldContract, target: FieldContract) -> None:
        if source.input_type != target.input_type:
            raise BusinessDraftError("incompatible field types")
        if source.input_type == InputType.LINK:
            raise BusinessDraftError("linked fields require explicit link operations")
        if not source.manual_entry_allowed or not target.manual_entry_allowed:
            raise BusinessDraftError("field is not editable")

    def move_field(
        self, source_key: str, target_key: str, *, adapter: EntityAdapter | None = None
    ) -> "BusinessDraft":
        self._ensure_mutable()
        adapter = adapter or CommercialEntityAdapter(self.contracts)
        self._ensure_editable_for_operation(target_key, adapter)
        writer = self._writer()
        self._assert_compatible(writer.contract.field(source_key), writer.contract.field(target_key))
        value = self.fields.get(source_key)
        if value in _EMPTY:
            raise BusinessDraftError(f"nothing to move: {source_key} is empty")
        moved = writer.apply_answer(target_key, value)
        fields = dict(moved.current_values)
        fields.pop(source_key, None)
        return self._replace_fields(fields)

    def swap_fields(
        self, first_key: str, second_key: str, *, adapter: EntityAdapter | None = None
    ) -> "BusinessDraft":
        self._ensure_mutable()
        adapter = adapter or CommercialEntityAdapter(self.contracts)
        self._ensure_editable_for_operation(first_key, adapter)
        self._ensure_editable_for_operation(second_key, adapter)
        writer = self._writer()
        self._assert_compatible(writer.contract.field(first_key), writer.contract.field(second_key))
        first_value = self.fields.get(first_key)
        second_value = self.fields.get(second_key)
        if first_value in _EMPTY and second_value in _EMPTY:
            raise BusinessDraftError("nothing to swap: both fields are empty")
        staged = writer
        staged = staged.apply_answer(first_key, second_value) if second_value not in _EMPTY else replace(
            staged, current_values={k: v for k, v in staged.current_values.items() if k != first_key}
        )
        staged = staged.apply_answer(second_key, first_value) if first_value not in _EMPTY else replace(
            staged, current_values={k: v for k, v in staged.current_values.items() if k != second_key}
        )
        return self._replace_fields(dict(staged.current_values))

    def _replace_fields(self, fields: dict[str, Any]) -> "BusinessDraft":
        updated = replace(
            self, fields=fields, updated_at=time.time(), idempotency_key=self.idempotency_key + 1,
        )
        new_state = DraftState.READY_FOR_REVIEW if updated.is_complete() else DraftState.CAPTURED
        return replace(updated, lifecycle_state=new_state)

    # -- EDITING / CANCEL / EXPIRE ------------------------------------------

    def begin_edit(self) -> "BusinessDraft":
        if self.lifecycle_state != DraftState.READY_FOR_REVIEW:
            raise BusinessDraftError("only a draft ready for review can enter EDITING")
        return replace(self, lifecycle_state=DraftState.EDITING, updated_at=time.time())

    def cancel(self) -> "BusinessDraft":
        if self.lifecycle_state in _TERMINAL_STATES:
            raise BusinessDraftError(f"draft already terminal: {self.lifecycle_state.value}")
        return replace(self, lifecycle_state=DraftState.CANCELLED, updated_at=time.time())

    def is_expired(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) > self.expires_at

    def expire(self) -> "BusinessDraft":
        if self.lifecycle_state in _TERMINAL_STATES:
            raise BusinessDraftError(f"draft already terminal: {self.lifecycle_state.value}")
        return replace(self, lifecycle_state=DraftState.EXPIRED, updated_at=time.time())

    # -- CONFIRM: freeze doc "Final Confirmation Boundary" ------------------

    def confirm(self, adapter: EntityAdapter | None = None) -> tuple["BusinessDraft", ConfirmedSnapshot]:
        """Freeze the mutable draft into a deterministic, immutable snapshot.

        Stops at the snapshot boundary: no ``propose_action()`` call, no
        Airtable write, no ActionContract mutation — a later phase hands this
        to the existing ``queue()``/``propose_action()`` boundary unchanged.
        """
        if self.lifecycle_state != DraftState.READY_FOR_REVIEW:
            raise BusinessDraftError(f"cannot confirm from state {self.lifecycle_state.value}")
        adapter = adapter or CommercialEntityAdapter(self.contracts)
        writer = self._writer()
        if self.operation is DraftOperation.CREATE:
            missing = writer.missing_fields()
            if missing:
                raise BusinessDraftError(
                    "cannot confirm: missing required fields: "
                    + ", ".join(f.field_name for f in missing)
                )
            tool_name = adapter.get_canonical_create_tool(self.entity_type)
            if not tool_name:
                raise UnsupportedOperationError(f"{self.entity_type} has no canonical CREATE tool")
            tool_inputs = adapter.build_create_payload(writer)
        else:
            tool_name = adapter.get_canonical_update_tool(self.entity_type)
            if not tool_name:
                raise UnsupportedOperationError(f"{self.entity_type} has no canonical UPDATE writer")
            tool_inputs = adapter.build_update_payload(writer, self.original_fields or {})
            if not tool_inputs:
                raise BusinessDraftError("cannot confirm: update payload is empty (nothing changed)")

        confirmed_at = time.time()
        snapshot = ConfirmedSnapshot(
            draft_id=self.draft_id, entity_type=self.entity_type, operation=self.operation,
            tenant_id=self.tenant_id, actor_role=self.actor_role, actor_user_id=self.actor_user_id,
            actor_display_name=self.actor_display_name, actor_domain_id=self.actor_domain_id,
            actor_external_id=self.actor_external_id, tool_name=tool_name,
            tool_inputs=MappingProxyType(dict(tool_inputs)), confirmed_at=confirmed_at,
        )
        confirmed_draft = replace(
            self, lifecycle_state=DraftState.CONFIRMED, updated_at=confirmed_at, snapshot=snapshot,
        )
        return confirmed_draft, snapshot


def create_draft(
    *,
    entity_type: str,
    operation: DraftOperation,
    tenant_id: str,
    actor_role: str,
    actor_user_id: str,
    source_channel: str,
    sender: str,
    fields: Mapping[str, Any] | None = None,
    source_context: Mapping[str, Any] | None = None,
    identity: Mapping[str, Any] | None = None,
    original_fields: Mapping[str, Any] | None = None,
    actor_display_name: str = "",
    actor_domain_id: str = "",
    actor_external_id: str = "",
    contracts: Mapping[str, EntityContract] | None = None,
    ttl_seconds: int = DRAFT_TTL_SECONDS,
) -> BusinessDraft:
    """Factory for a fresh CAPTURED draft.

    ``draft_id`` is the deterministic ``f"{tenant_id}:{channel}:{sender}:
    {entity_type}"`` scoping frozen by the contract doc — a computed label
    for the one nested slot Phase 2's Sessions-backed store will use, not an
    independent index (v1 cardinality: one draft per entity-kind per sender,
    Owner Decision #1).
    """
    contracts = contracts or ENTITY_CONTRACTS
    if entity_type not in contracts:
        raise BusinessDraftError(f"unknown entity_type: {entity_type!r}")
    if operation is DraftOperation.UPDATE and original_fields is None:
        raise BusinessDraftError("an UPDATE draft requires original_fields")
    now = time.time()
    draft = BusinessDraft(
        draft_id=f"{tenant_id}:{source_channel}:{sender}:{entity_type}",
        entity_type=entity_type, operation=operation, tenant_id=tenant_id,
        actor_role=actor_role, actor_user_id=actor_user_id, source_channel=source_channel,
        lifecycle_state=DraftState.CAPTURED, created_at=now, updated_at=now,
        expires_at=now + ttl_seconds, fields=dict(fields or {}),
        source_context=dict(source_context or {}), identity=dict(identity or {}),
        original_fields=dict(original_fields) if original_fields is not None else None,
        actor_display_name=actor_display_name, actor_domain_id=actor_domain_id,
        actor_external_id=actor_external_id, contracts=contracts,
    )
    return draft if not draft.is_complete() else replace(draft, lifecycle_state=DraftState.READY_FOR_REVIEW)


# ══════════════════════════════════════════════════
# PHASE 2 — serialization contract (Sessions persistence)
# ══════════════════════════════════════════════════
# Pure data-shape translation only — no I/O, no Sessions/Airtable knowledge.
# session_store.py owns storage; this owns "what a BusinessDraft looks like
# as JSON". `contracts` is deliberately never serialized: it's a live code
# registry (ENTITY_CONTRACTS), not draft data — round-tripping it would
# leak a stale copy of code-owned schema into storage.

_SNAPSHOT_FIELDS = (
    "draft_id", "entity_type", "tenant_id", "actor_role", "actor_user_id",
    "actor_display_name", "actor_domain_id", "actor_external_id", "tool_name", "confirmed_at",
)


def _serialize_snapshot(snapshot: ConfirmedSnapshot) -> dict[str, Any]:
    data = {name: getattr(snapshot, name) for name in _SNAPSHOT_FIELDS}
    data["operation"] = snapshot.operation.value
    data["tool_inputs"] = dict(snapshot.tool_inputs)
    return data


def _deserialize_snapshot(data: Mapping[str, Any]) -> ConfirmedSnapshot:
    try:
        return ConfirmedSnapshot(
            **{name: str(data[name]) if name != "confirmed_at" else float(data[name]) for name in _SNAPSHOT_FIELDS},
            operation=DraftOperation(data["operation"]),
            tool_inputs=MappingProxyType(dict(data.get("tool_inputs") or {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BusinessDraftError(f"malformed ConfirmedSnapshot payload: {exc}") from exc


def serialize_business_draft(draft: BusinessDraft) -> dict[str, Any]:
    """Deterministic, JSON-safe dict for the exact shape ``deserialize_business_draft``
    accepts back. See PHASE 2 module note above for what is intentionally left out."""
    return {
        "draft_id": draft.draft_id,
        "entity_type": draft.entity_type,
        "operation": draft.operation.value,
        "tenant_id": draft.tenant_id,
        "actor_role": draft.actor_role,
        "actor_user_id": draft.actor_user_id,
        "source_channel": draft.source_channel,
        "lifecycle_state": draft.lifecycle_state.value,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "expires_at": draft.expires_at,
        "fields": dict(draft.fields),
        "source_context": dict(draft.source_context),
        "identity": dict(draft.identity),
        "original_fields": dict(draft.original_fields) if draft.original_fields is not None else None,
        "actor_display_name": draft.actor_display_name,
        "actor_domain_id": draft.actor_domain_id,
        "actor_external_id": draft.actor_external_id,
        "idempotency_key": draft.idempotency_key,
        "snapshot": _serialize_snapshot(draft.snapshot) if draft.snapshot is not None else None,
    }


def deserialize_business_draft(
    data: Mapping[str, Any], *, contracts: Mapping[str, EntityContract] | None = None,
) -> BusinessDraft:
    """Inverse of :func:`serialize_business_draft`. Fails closed
    (``BusinessDraftError``) on any missing/malformed/unknown-enum field —
    never returns a partially-reconstructed draft."""
    contracts = contracts or ENTITY_CONTRACTS
    try:
        entity_type = str(data["entity_type"])
        if entity_type not in contracts:
            raise BusinessDraftError(f"unknown entity_type: {entity_type!r}")
        snapshot_raw = data.get("snapshot")
        return BusinessDraft(
            draft_id=str(data["draft_id"]),
            entity_type=entity_type,
            operation=DraftOperation(data["operation"]),
            tenant_id=str(data["tenant_id"]),
            actor_role=str(data["actor_role"]),
            actor_user_id=str(data["actor_user_id"]),
            source_channel=str(data["source_channel"]),
            lifecycle_state=DraftState(data["lifecycle_state"]),
            created_at=float(data["created_at"]),
            updated_at=float(data["updated_at"]),
            expires_at=float(data["expires_at"]),
            fields=dict(data.get("fields") or {}),
            source_context=dict(data.get("source_context") or {}),
            identity=dict(data.get("identity") or {}),
            original_fields=dict(data["original_fields"]) if data.get("original_fields") is not None else None,
            actor_display_name=str(data.get("actor_display_name") or ""),
            actor_domain_id=str(data.get("actor_domain_id") or ""),
            actor_external_id=str(data.get("actor_external_id") or ""),
            idempotency_key=int(data["idempotency_key"]),
            contracts=contracts,
            snapshot=_deserialize_snapshot(snapshot_raw) if snapshot_raw else None,
        )
    except BusinessDraftError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise BusinessDraftError(f"malformed BusinessDraft payload: {exc}") from exc


def demo() -> None:
    draft = create_draft(
        entity_type="deal", operation=DraftOperation.CREATE, tenant_id="t1",
        actor_role="owner", actor_user_id="u1", source_channel="telegram", sender="chat1",
    )
    assert draft.lifecycle_state is DraftState.CAPTURED
    draft = draft.set_field("name", "Acme deal")
    draft = draft.set_field("domain", "import")
    draft = draft.set_field("owner", "recOWNER0000001")
    draft = draft.set_field("counterparty_contact", "recCONTACT00001")
    assert draft.lifecycle_state is DraftState.READY_FOR_REVIEW
    confirmed, snapshot = draft.confirm()
    assert confirmed.lifecycle_state is DraftState.CONFIRMED
    assert snapshot.tool_name == "crm_create_deal"
    assert snapshot.tool_inputs["name"] == "Acme deal"
    try:
        confirmed.set_field("name", "changed")
        raise AssertionError("confirmed draft must not be mutable")
    except BusinessDraftError:
        pass

    roundtripped = deserialize_business_draft(serialize_business_draft(confirmed))
    assert roundtripped.lifecycle_state is DraftState.CONFIRMED
    assert roundtripped.snapshot.tool_inputs == snapshot.tool_inputs
    assert roundtripped.fields == confirmed.fields
    try:
        deserialize_business_draft({"entity_type": "deal"})
        raise AssertionError("malformed payload must fail closed")
    except BusinessDraftError:
        pass

    print("core/business_draft.py: all demo() assertions passed")


if __name__ == "__main__":
    demo()
