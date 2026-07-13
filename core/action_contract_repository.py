# core/action_contract_repository.py — PR-0C Phase 4B0
#
# Durable repository for ActionContract, backed by Tables.ACTION_CONTRACTS.
# This is the source of truth across restarts and separate Render instances —
# ExecutionLedger's in-memory _store is a CACHE in front of this repository,
# never the reverse. find_by_id() falls back here on a cache miss and
# hydrates the full contract (including actor identity/policy fields) so a
# restarted or second process can safely resume and authorize execution
# exactly as the original propose_action() call intended.
#
# SCOPE OF THIS FILE — persistence, hydration, identity-binding, and
# fail-closed reads ONLY. There is NO transition/claim mechanism in this
# file. An earlier version of this file included a guarded_transition()
# method built on read -> check (in Python) -> PATCH -> re-read against
# Airtable's REST API, which has no compare-and-swap / conditional-PATCH
# primitive. That method was removed: it is a plain TOCTOU sequence, not
# optimistic concurrency control. Two callers that both read before either
# writes independently compute the identical expected_version+1 and the
# identical new_status, both PATCH, both re-read (version, status) matching,
# and BOTH get a non-None success back — even though the second PATCH
# silently overwrote the first caller's other fields (e.g. approved_by). For
# genuinely concurrent callers (duplicate webhook delivery, a double-tap, two
# Render instances handling the same request at once) it provided NO
# protection and both callers would proceed to execute. This is not a
# "narrowed race window" that was hardened here — it never worked, and no
# claim mechanism has replaced it yet.
#
# A real fix requires a genuinely atomic coordination primitive outside
# Airtable (transactional SQL/CAS, Redis SET-NX with lease and fencing, or a
# single-consumer execution queue) — tracked separately as Phase 4B0.1. Until
# that lands, Phase 4B (TMA routing approve/reject by contract_id) must stay
# blocked, and ActionGateway.approve()/_execute_contract() must keep using
# their original in-memory update_status() path, not anything in this file.
#
# Never re-plan/re-derive a replacement contract as "recovery" — get()
# returns None on any failure to find/verify the exact durable record
# (not-found, store unreachable, expired). Callers must fail closed on None,
# never fabricate a new contract to fill the gap; that would defeat the
# entire frozen-contract security model this work protects (approved_payload
# must always equal executed_payload).

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
)
# _safe_formula_param is airtable_gateway's own sanctioned formula-value
# escaping helper (see its docstring) — reused here rather than duplicated.
from tools.airtable_gateway import _safe_formula_param

if TYPE_CHECKING:
    from core.action_gateway import ActionContract

logger = logging.getLogger(__name__)

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
    )
    contract.version = int(f.get(ActionContractsFields.VERSION) or 1)
    return contract


class ActionContractRepository:
    """See module docstring. Stateless — every call talks to Airtable fresh."""

    def save(self, contract: "ActionContract") -> bool:
        """Full upsert. Appropriate for a brand-new contract (version=1) or a
        non-contentious field update (e.g. context_interrupted). This file has
        no transition/claim mechanism — see module docstring — so callers
        must not use save() to implement an approve/reject/execute race
        without an external atomic claim (Phase 4B0.1, not yet built)."""
        fields = _contract_to_fields(contract)
        return at_upsert(
            Tables.ACTION_CONTRACTS, fields,
            match_field=ActionContractsFields.CONTRACT_ID,
            source="action_contract_repository",
        )

    def get(self, contract_id: str) -> "ActionContract | None":
        """Returns None for "not found", "store unreachable", AND "found but
        expired while still pending" — all three are fail-closed cases from
        the caller's perspective. Never distinguishes them via a truthy
        fallback; ExecutionLedger.find_by_id() must not treat None as
        license to fabricate a replacement contract."""
        try:
            record = at_get_by_field(Tables.ACTION_CONTRACTS, ActionContractsFields.CONTRACT_ID, contract_id)
        except AirtableLookupError as exc:
            logger.warning("[ActionContractRepository] get(%s) store unreachable: %s", contract_id, exc)
            return None
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
            return []
        contracts = [_record_to_contract(r) for r in records]
        return [c for c in contracts if not _is_expired(c)]
