# core/action_contract_repository.py — PR-0C Phase 4B0
#
# Durable repository for ActionContract proposals, lifecycle transitions, and
# recovery lookups, backed by Tables.ACTION_CONTRACTS. When
# FEATURE_ACTION_CONTRACT_PERSISTENCE is enabled, ExecutionLedger's in-memory
# _store is a cache for those records. PostgreSQL remains the sole owner of
# atomic execution claims; this repository is the durable contract/audit store.
#
# SCOPE OF THIS FILE — persistence, hydration, identity-binding, fail-closed
# reads, and guarded partial lifecycle audit writes. Airtable has no
# compare-and-swap / conditional-PATCH primitive, so transition() is not an
# execution claim and must never be used as one. It rejects already-stale
# state, limits writes to lifecycle fields, and verifies the resulting
# status/version. PostgreSQL atomic claims remain the execution-ownership
# primitive; Airtable records the canonical state selected by that claim
# owner. A simultaneous same-version Airtable write remains a documented
# read/check/PATCH race rather than a hidden claim guarantee.
#
# Never re-plan/re-derive a replacement contract as "recovery". Clean
# not-found/expiry returns None, while an unavailable lookup raises
# ActionContractLookupError so callers cannot confuse an outage with absence.

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from airtable_schema import ActionContractsFields, Tables
from tools.airtable_gateway import (
    AirtableLookupError,
    at_get_by_field,
    at_list_by_formula,
    at_upsert,
    airtable_patch,
)
# _safe_formula_param is airtable_gateway's own sanctioned formula-value
# escaping helper (see its docstring) — reused here rather than duplicated.
from tools.airtable_gateway import _safe_formula_param

if TYPE_CHECKING:
    from core.action_gateway import ActionContract

logger = logging.getLogger(__name__)


class ActionContractLookupError(RuntimeError):
    """The durable store could not determine whether a contract exists."""


class ActionContractTransitionError(RuntimeError):
    """Base error for a lifecycle transition that was not durably accepted."""


class ActionContractTransitionConflictError(ActionContractTransitionError):
    """The durable contract no longer matches the caller's expected state."""


class ActionContractTransitionPersistenceError(ActionContractTransitionError):
    """The durable store could not persist or verify a lifecycle transition."""


ALLOWED_CONTRACT_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"pending", "approved"}),
    "pending": frozenset({"approved", "rejected", "superseded", "completed", "failed"}),
    "approved": frozenset({"executing", "completed", "failed", "outcome_unknown"}),
    "executing": frozenset({"completed", "failed", "outcome_unknown"}),
}

_LIFECYCLE_FIELD_MAP = {
    "approved_by": ActionContractsFields.APPROVED_BY,
    "approved_at": ActionContractsFields.APPROVED_AT,
    "context_interrupted": ActionContractsFields.CONTEXT_INTERRUPTED,
    "reconfirmation_required": ActionContractsFields.RECONFIRMATION_REQUIRED,
    "context_integrity_unknown": ActionContractsFields.CONTEXT_INTEGRITY_UNKNOWN,
}

# How long a "pending" contract may sit before it's considered too stale to
# safely act on. Longer than event_bus's 30-minute Telegram-button TTL, since
# TMA approvals can reasonably sit for hours before the owner opens the app —
# still bounded, so a stale contract can never be resurrected and executed
# long after its context is meaningless.
CONTRACT_PENDING_TTL_SECONDS = 24 * 3600  # 24h


def _is_expired(contract: "ActionContract") -> bool:
    return (time.time() - contract.created_at) > CONTRACT_PENDING_TTL_SECONDS


def _contract_to_fields(contract: "ActionContract") -> dict:
    return {
        ActionContractsFields.CONTRACT_ID: contract.contract_id,
        ActionContractsFields.TENANT_ID: contract.tenant_id,
        ActionContractsFields.CANONICAL_USER_ID: contract.canonical_user_id,
        ActionContractsFields.TOOL_NAME: contract.tool_name,
        ActionContractsFields.NORMALIZED_PAYLOAD: json.dumps(contract.normalized_payload, ensure_ascii=False),
        ActionContractsFields.BUSINESS_FINGERPRINT: contract.business_action_fingerprint,
        ActionContractsFields.ORIGIN_CHANNEL: contract.origin_channel,
        ActionContractsFields.ORIGIN_CHAT_ID: contract.origin_chat_id,
        ActionContractsFields.REQUIRES_APPROVAL: contract.requires_approval,
        ActionContractsFields.STATUS: contract.status,
        ActionContractsFields.CREATED_AT: contract.created_at,
        ActionContractsFields.APPROVED_BY: contract.approved_by or "",
        ActionContractsFields.APPROVED_AT: contract.approved_at or 0.0,
        ActionContractsFields.VERSION: getattr(contract, "version", 1),
        ActionContractsFields.ACTOR_ROLE: contract.actor_role,
        ActionContractsFields.ACTOR_USER_ID: contract.actor_user_id,
        ActionContractsFields.ACTOR_DISPLAY_NAME: contract.actor_display_name,
        ActionContractsFields.ACTOR_DOMAIN_ID: contract.actor_domain_id,
        ActionContractsFields.ACTOR_EXTERNAL_ID: contract.actor_external_id,
        ActionContractsFields.ACTOR_ALLOWED_DOMAINS: json.dumps(contract.actor_allowed_domains or [], ensure_ascii=False),
        ActionContractsFields.APPROVAL_POLICY: contract.approval_policy,
        ActionContractsFields.TRUSTED_SOURCE: contract.trusted_source,
        ActionContractsFields.CONTEXT_INTERRUPTED: contract.context_interrupted,
        ActionContractsFields.RECONFIRMATION_REQUIRED: contract.reconfirmation_required,
        ActionContractsFields.CONTEXT_INTEGRITY_UNKNOWN: contract.context_integrity_unknown,
        ActionContractsFields.IDEMPOTENCY_KEY: contract.idempotency_key,
    }


def _record_to_contract(record: dict) -> "ActionContract":
    from core.action_gateway import ActionContract  # lazy: avoid circular import at module load

    f = record.get("fields", {})

    try:
        normalized_payload = json.loads(f.get(ActionContractsFields.NORMALIZED_PAYLOAD) or "{}")
    except (TypeError, ValueError):
        normalized_payload = {}
    try:
        actor_allowed_domains = json.loads(f.get(ActionContractsFields.ACTOR_ALLOWED_DOMAINS) or "[]")
    except (TypeError, ValueError):
        actor_allowed_domains = []

    contract = ActionContract(
        contract_id=f.get(ActionContractsFields.CONTRACT_ID, ""),
        tenant_id=f.get(ActionContractsFields.TENANT_ID, ""),
        canonical_user_id=f.get(ActionContractsFields.CANONICAL_USER_ID, ""),
        tool_name=f.get(ActionContractsFields.TOOL_NAME, ""),
        normalized_payload=normalized_payload,
        business_action_fingerprint=f.get(ActionContractsFields.BUSINESS_FINGERPRINT, ""),
        origin_channel=f.get(ActionContractsFields.ORIGIN_CHANNEL, ""),
        origin_chat_id=f.get(ActionContractsFields.ORIGIN_CHAT_ID, ""),
        requires_approval=bool(f.get(ActionContractsFields.REQUIRES_APPROVAL, False)),
        status=f.get(ActionContractsFields.STATUS, "pending"),
        created_at=float(f.get(ActionContractsFields.CREATED_AT) or 0.0),
        approved_by=f.get(ActionContractsFields.APPROVED_BY) or None,
        approved_at=(float(f.get(ActionContractsFields.APPROVED_AT) or 0.0) or None),
        actor_role=f.get(ActionContractsFields.ACTOR_ROLE, ""),
        actor_user_id=f.get(ActionContractsFields.ACTOR_USER_ID, ""),
        actor_display_name=f.get(ActionContractsFields.ACTOR_DISPLAY_NAME, ""),
        actor_domain_id=f.get(ActionContractsFields.ACTOR_DOMAIN_ID, ""),
        actor_external_id=f.get(ActionContractsFields.ACTOR_EXTERNAL_ID, ""),
        actor_allowed_domains=actor_allowed_domains,
        approval_policy=f.get(ActionContractsFields.APPROVAL_POLICY) or "approval",
        trusted_source=f.get(ActionContractsFields.TRUSTED_SOURCE) or "agent",
        context_interrupted=bool(f.get(ActionContractsFields.CONTEXT_INTERRUPTED, False)),
        reconfirmation_required=bool(f.get(ActionContractsFields.RECONFIRMATION_REQUIRED, False)),
        context_integrity_unknown=bool(f.get(ActionContractsFields.CONTEXT_INTEGRITY_UNKNOWN, False)),
        idempotency_key=f.get(ActionContractsFields.IDEMPOTENCY_KEY, ""),
    )
    contract.version = int(f.get(ActionContractsFields.VERSION) or 1)
    return contract


class ActionContractRepository:
    """See module docstring. Stateless — every call talks to Airtable fresh."""

    # Codex re-audit of ce990a0, fix 1 — capability declared at the
    # ledger/repository boundary (NOT a feature flag consulted in app.py):
    # Airtable has no conditional-PATCH / compare-and-swap primitive, so a
    # `require_status` conditional lifecycle transition cannot be performed
    # atomically here. transition() is read-then-check-then-PATCH — three
    # separate operations, TOCTOU-prone: a concurrent writer can change the
    # durable state between the check-read and the unconditional PATCH, so a
    # destructive conditional write (e.g. PA-01's pending->rejected orphan
    # cleanup) could clobber a live approval. ExecutionLedger consults this
    # BEFORE ever attempting such a write; False => fail closed, no PATCH,
    # caller maps the result to APPROVAL_QUEUE_ORPHANED. A future
    # Postgres-backed repository offering a real atomic conditional
    # `UPDATE ... WHERE status = :expected` can declare this True.
    supports_atomic_conditional_transition = False

    def save(self, contract: "ActionContract") -> bool:
        """Full upsert used by 4B-1A for a brand-new contract (version=1).

        This file has no transition/update API. Callers must not use save() as
        status/context write-through; lifecycle persistence is Phase 4B-1B.
        """
        fields = _contract_to_fields(contract)
        return at_upsert(
            Tables.ACTION_CONTRACTS, fields,
            match_field=ActionContractsFields.CONTRACT_ID,
            source="action_contract_repository",
            fail_closed_on_lookup_error=True,
        )

    def transition(
        self,
        contract_id: str,
        *,
        expected_status: str,
        expected_version: int,
        new_status: str,
        updates: dict | None = None,
    ) -> "ActionContract":
        """Persist one expected lifecycle transition using a partial PATCH.

        Airtable has no conditional PATCH/CAS primitive. This method therefore
        rejects stale state before the write, patches only lifecycle fields
        (never the frozen payload/identity), and verifies status+version with a
        read-back. PostgreSQL remains the atomic execution-ownership boundary.
        """
        updates = dict(updates or {})
        unknown_updates = set(updates) - set(_LIFECYCLE_FIELD_MAP)
        if unknown_updates:
            raise ActionContractTransitionConflictError(
                f"unsupported lifecycle fields: {sorted(unknown_updates)}"
            )

        current, record_id = self._get_for_transition(contract_id)
        # Codex re-audit of ce990a0, fix 2 — strict expected-state ordering:
        # the expected-status/version check MUST run before the idempotent
        # shortcut. Otherwise a call like (expected_status=pending,
        # actual_status=rejected, new_status=rejected) would hit the shortcut
        # (actual == new_status, no updates) and return SUCCESS, silently
        # accepting a stale expectation as though this call performed the
        # transition. That is exactly the false-success reject_if_pending()
        # must never produce. Fail closed with a conflict instead.
        if current.status != expected_status or current.version != expected_version:
            raise ActionContractTransitionConflictError(
                f"stale lifecycle state: expected={expected_status}/v{expected_version} "
                f"actual={current.status}/v{current.version}"
            )
        # Idempotent shortcut only AFTER the expectation is confirmed to match:
        # expected_status == current.status here, so a no-op same-status write
        # is a genuine, correctly-expected idempotent replay, not a stale one.
        if current.status == new_status and not updates:
            return current
        if (new_status != current.status
                and new_status not in ALLOWED_CONTRACT_TRANSITIONS.get(current.status, frozenset())):
            raise ActionContractTransitionConflictError(
                f"invalid lifecycle transition: {current.status} -> {new_status}"
            )

        next_version = current.version + 1
        patch_fields = {
            ActionContractsFields.STATUS: new_status,
            ActionContractsFields.VERSION: next_version,
        }
        for attr, value in updates.items():
            if attr == "approved_by":
                value = value or ""
            elif attr == "approved_at":
                value = value or 0.0
            patch_fields[_LIFECYCLE_FIELD_MAP[attr]] = value

        try:
            patched = airtable_patch(
                Tables.ACTION_CONTRACTS,
                record_id,
                patch_fields,
                source="action_contract_repository.lifecycle",
            )
        except Exception as exc:
            raise ActionContractTransitionPersistenceError(
                f"lifecycle PATCH raised: {contract_id}"
            ) from exc
        if not patched:
            raise ActionContractTransitionPersistenceError(
                f"lifecycle PATCH failed: {contract_id}"
            )

        verified, _ = self._get_for_transition(contract_id)
        if verified.status != new_status or verified.version != next_version:
            raise ActionContractTransitionConflictError(
                f"lifecycle read-back conflict: expected={new_status}/v{next_version} "
                f"actual={verified.status}/v{verified.version}"
            )
        return verified

    def _get_for_transition(self, contract_id: str) -> tuple["ActionContract", str]:
        try:
            record = at_get_by_field(
                Tables.ACTION_CONTRACTS,
                ActionContractsFields.CONTRACT_ID,
                contract_id,
            )
        except AirtableLookupError as exc:
            raise ActionContractTransitionPersistenceError(
                f"lifecycle lookup failed: {contract_id}"
            ) from exc
        if not record:
            raise ActionContractTransitionConflictError(
                f"contract not found for lifecycle transition: {contract_id}"
            )
        return _record_to_contract(record), record["id"]

    def get(self, contract_id: str) -> "ActionContract | None":
        """Return a verified contract, or None for clean not-found/expiry.

        Raises ActionContractLookupError when Airtable cannot answer. This
        distinction prevents callers from inventing absence during an outage.
        """
        try:
            record = at_get_by_field(Tables.ACTION_CONTRACTS, ActionContractsFields.CONTRACT_ID, contract_id)
        except AirtableLookupError as exc:
            logger.warning("[ActionContractRepository] get(%s) store unreachable: %s", contract_id, exc)
            raise ActionContractLookupError(f"contract-id lookup failed: {contract_id}") from exc
        if not record:
            return None

        contract = _record_to_contract(record)
        if contract.status == "pending" and _is_expired(contract):
            logger.info(
                "[ActionContractRepository] get(%s) — pending contract expired (created_at=%s)",
                contract_id, contract.created_at,
            )
            return None
        return contract

    def find_pending_by_canonical_user(self, canonical_user_id: str) -> list["ActionContract"]:
        """Durable equivalent of ExecutionLedger.find_live_by_user() — used to
        recover a user's live pending contracts if the cache was lost
        (restart) before they act on it."""
        # Metrics are request-local observability only.  Import lazily so the
        # repository remains usable in its standalone maintenance scripts.
        from core.approval_turn_metrics import record_action_contract_read
        record_action_contract_read()
        formula = (
            f"AND({{{ActionContractsFields.CANONICAL_USER_ID}}}='{_safe_formula_param(canonical_user_id)}', "
            f"{{{ActionContractsFields.STATUS}}}='pending')"
        )
        try:
            records = at_list_by_formula(Tables.ACTION_CONTRACTS, formula)
        except AirtableLookupError as exc:
            logger.warning(
                "[ActionContractRepository] find_pending_by_canonical_user(%s) store unreachable: %s",
                canonical_user_id, exc,
            )
            raise ActionContractLookupError(
                f"pending-contract lookup failed: {canonical_user_id}"
            ) from exc
        contracts = [_record_to_contract(r) for r in records]
        return [c for c in contracts if c.status == "pending" and not _is_expired(c)]

    def find_by_business_fingerprint(self, fingerprint: str) -> "ActionContract | None":
        """Recover the exact frozen contract for restart-safe proposal dedup.

        This is a lookup, not an atomic uniqueness/claim primitive. It makes a
        proposal written by one process visible to later proposals in another
        process, while concurrent creation races remain outside this PR.
        """
        try:
            record = at_get_by_field(
                Tables.ACTION_CONTRACTS,
                ActionContractsFields.BUSINESS_FINGERPRINT,
                fingerprint,
            )
        except AirtableLookupError as exc:
            logger.warning(
                "[ActionContractRepository] find_by_business_fingerprint(%.12s) "
                "store unreachable: %s",
                fingerprint, exc,
            )
            raise ActionContractLookupError(
                f"fingerprint lookup failed: {fingerprint}"
            ) from exc
        if not record:
            return None
        contract = _record_to_contract(record)
        if contract.status == "pending" and _is_expired(contract):
            return None
        return contract
