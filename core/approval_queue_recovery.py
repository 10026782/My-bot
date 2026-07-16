# core/approval_queue_recovery.py — PA-01 approval-queue failure recovery
#
# Mechanically extracted from app.py (structural cleanup, no behavior change).
# Holds the normalization/recovery helpers PA-01 added for approval-queue
# failures: verified revoke/cancel of an orphaned ActionContract / EventBus
# pending item, and the distinct "unverifiable/unattributable" terminal
# response shape.
#
# This module imports only low-level modules (core.action_gateway, event_bus)
# and does so lazily inside each function — it must NEVER import app.py, to
# avoid a circular import. app.py imports these names back into its own
# namespace so its existing call sites (and the tests that reference
# app._revoke_and_verify_contract etc.) keep working unchanged.
#
# Every constant, message, terminal-outcome string, and return shape here is
# byte-for-byte identical to what previously lived in app.py — this file is a
# move, not a rewrite. See docs/architecture/turn-coordinator/
# PA-01_PLANNING_GATE.md for the semantics.

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Codex re-audit of 818c8a6 — architectural ruling: a business-action
# FINGERPRINT proves two calls describe the same business action; it does
# NOT prove the ActionContract found under that fingerprint was created BY
# THIS call. A fingerprint match can be a genuinely pre-existing contract
# (created by an earlier, unrelated turn) or a concurrently-created one
# (a race with another turn/request) — mutating either one because OUR call
# happened to fail would silently interfere with a request this call has no
# authority over. _find_live_contract_by_fingerprint() (the previous round's
# fingerprint-based rediscovery helper) is therefore REMOVED — deleted, not
# demoted to a read-only diagnostic, since nothing else ever needs it. The
# only status this codebase's ActionGateway.reject() ever transitions a
# contract TO is "rejected" — there is no separate "cancelled"/"revoked"
# status — so that is the sole state _revoke_and_verify_contract() below
# accepts as a confirmed cancellation.
_SAFE_CANCELLED_CONTRACT_STATUSES = frozenset({"rejected"})


def _revoke_and_verify_contract(canonical_user_id: str, contract_id: str, reason: str) -> bool:
    """
    Only ever called with a contract_id PROVEN to belong to the current
    call's own propose_action() invocation (a fresh GatewayResult.ok=True
    return from THIS call) — never a fingerprint-matched guess (Codex
    re-audit of 818c8a6, ownership rule). Returns whether the revocation was
    actually VERIFIED.

    Codex re-audit of 0d658c1 (TOCTOU race fix): the cancellation is now
    performed by action_gateway.reject_if_pending(), an ATOMIC conditional
    pending -> rejected transition. reject() (used previously here) reads the
    status, checks "pending", then in a SEPARATE step writes "rejected" — a
    window in which a concurrent turn moving the contract pending -> approved
    is silently clobbered to "rejected" by the RAM ledger's unconditional
    set (the default, persistence-off path does no CAS). This function would
    then read back "rejected" and wrongly report success while having
    overwritten a live approval. reject_if_pending() returns True only if it
    itself performed the pending -> rejected transition atomically, so a
    contract that was already non-pending at the write is never touched and
    never reported as our success.

    Two independent conditions must BOTH hold for success, defense in depth:
      1. reject_if_pending() reports it performed the atomic transition
         (transitioned is True) — a contract a concurrent event already
         moved past "pending" yields False here without any mutation.
      2. an EXACT, authoritative re-read of this one contract_id
         (find_contract(), checking its own status — NOT find_live_
         contracts() membership, which only proves "not pending") still
         shows a safe-cancelled status. This catches the reverse ordering
         too: we transitioned to "rejected", then a concurrent writer
         overwrote it back to approved/executing before we verified.
    _SAFE_CANCELLED_CONTRACT_STATUSES is {"rejected"} — the only real
    cancellation status this codebase's lifecycle has. A missing contract
    (find_contract() returns None) is NOT success either.
    """
    try:
        from core.action_gateway import action_gateway as _gw_revoke
        transitioned = _gw_revoke.reject_if_pending(contract_id, rejected_by=f"system:{reason}")
        found = _gw_revoke.find_contract(contract_id)
    except Exception as exc:
        logger.error(
            "[Approval] revoke-and-verify itself failed for contract=%s reason=%s error=%s",
            contract_id, reason, exc, exc_info=True,
        )
        return False
    if not transitioned:
        logger.error(
            "[Approval] contract=%s reason=%s was NOT pending at the atomic reject transition "
            "(a concurrent lifecycle event owns it, or it was already resolved) -- not "
            "reporting cleanup success, contract left untouched", contract_id, reason,
        )
        return False
    if found is None:
        logger.error(
            "[Approval] contract=%s reason=%s missing after atomic revoke -- treating as "
            "unverified", contract_id, reason,
        )
        return False
    if found.status not in _SAFE_CANCELLED_CONTRACT_STATUSES:
        logger.error(
            "[Approval] contract=%s reason=%s status=%s after atomic revoke -- not a safe "
            "cancelled state (a concurrent lifecycle event overwrote our rejection)",
            contract_id, reason, found.status,
        )
        return False
    logger.warning("[Approval] revoked orphaned contract=%s reason=%s", contract_id, reason)
    return True


def _cancel_and_verify_pending(action_id: str, reason: str) -> bool:
    """
    Codex re-audit of 8e05d67, P3: mirrors _revoke_and_verify_contract() for
    the legacy EventBus pending-item store — PendingActionsStore.cancel()
    completing without raising is not itself proof the item is gone; re-
    checked via pending.get() (which independently re-validates TTL/
    existence) before this function reports success.
    """
    try:
        from event_bus import pending as _pending_cancel
        _pending_cancel.cancel(action_id)
        still_live = _pending_cancel.get(action_id) is not None
    except Exception as exc:
        logger.error(
            "[Approval] cancel-and-verify itself failed for action_id=%s reason=%s error=%s",
            action_id, reason, exc, exc_info=True,
        )
        return False
    if still_live:
        logger.error(
            "[Approval] EventBus pending item=%s reason=%s STILL LIVE after cancel attempt",
            action_id, reason,
        )
        return False
    logger.warning("[Approval] cancelled orphaned EventBus pending item=%s reason=%s", action_id, reason)
    return True


def _orphan_cleanup_failure_response(tool_name: str, contract_id: str | None) -> dict:
    """
    The distinct, honest terminal state whenever cleanup could not be
    verified to have taken effect (Codex re-audit of 8e05d67), OR whenever
    ownership of any contract_id was never proven for this call in the first
    place (Codex re-audit of 818c8a6). Two distinct callers pass different
    things here — both are legitimate:

      contract_id = a REAL id this call proved it owns (a fresh
      GatewayResult.ok=True from THIS call's own propose_action()), but
      _revoke_and_verify_contract() could not confirm the revoke took
      effect. Never invented/guessed via a fingerprint match.

      contract_id = None, meaning no id is known or attributable to this
      call at all (propose_action() raised without ever returning one,
      canonicalization failed, or any other unattributed exception) — this
      is NOT the same None as APPROVAL_QUEUE_ERROR's "verified no contract
      exists"; it means "unknown," not "confirmed absent." Never backfilled
      via a fingerprint lookup, since a fingerprint match cannot prove this
      call created or owns it (a pre-existing or concurrently-created
      contract for the identical business action is indistinguishable from
      one this call caused, by fingerprint alone).

    "created_this_turn" stays False regardless: even a real, still-live
    contract in the first case was never properly notified to the owner, so
    it must not be treated as usable evidence for row 2.
    """
    return {
        "message": (
            "❌ אירעה שגיאה בעת ניסיון לבטל בקשת אישור לאחר כשל. "
            "ייתכן שנותרה בקשה תקועה במערכת — יש לבדוק ידנית מול מנהל המערכת."
        ),
        "contract_id": contract_id,
        "ok": False,
        "terminal_outcome": "APPROVAL_QUEUE_ORPHANED",
        "action_tool": tool_name,
        "created_this_turn": False,
    }
