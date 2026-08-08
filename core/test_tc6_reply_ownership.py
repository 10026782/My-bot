"""TC6 — exact-contract reply-ownership authority (WS2).

Covers ``ActionGateway.reply_ownership_for_contract()`` (the narrow helper
this PR adds) and the ``query_execution_status()`` fix that stops discarding
``approval_status()``'s projection. Does not touch app.py — the
enforcement/OwnershipSignal cutover described in the TC6 design correction
is an isolated integrator patch, tracked and tested separately (see
docs/architecture/turn-coordinator-full/TC6_APP_INTEGRATOR_PATCH_SPEC.md).
"""

import time

import pytest

from core.action_gateway import (
    ActionContract,
    ActionGateway,
    ExecutionLedger,
    _PENDING_STATUS_UNVERIFIABLE_MESSAGE,
)
from core.router.ownership_contracts import ActionLifecycleResult


def _contract(status: str, *, contract_id: str = "c1", created_at: float | None = None) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="tenant-a",
        canonical_user_id="user-a",
        tool_name="airtable_add",
        normalized_payload={"table": "Leads", "fields": {"name": "Alice"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-a",
        requires_approval=True,
        status=status,
        created_at=time.time() if created_at is None else created_at,
    )


# ── A. Exact-contract ownership helper ────────────────────────────────


@pytest.mark.parametrize(
    ("status", "expected_lifecycle_state"),
    [
        ("pending", "pending"),
        ("rejected", "rejected"),
        ("completed", "completed"),
        ("failed", "failed"),
        ("outcome_unknown", "outcome_unknown"),
    ],
)
def test_reply_ownership_for_contract_covers_terminal_and_pending_states(
    status: str, expected_lifecycle_state: str,
) -> None:
    gateway = ActionGateway()
    gateway._ledger.save(_contract(status))

    result = gateway.reply_ownership_for_contract("c1")

    assert result is not None
    assert result.contract_ref == "c1"
    assert result.lifecycle_state == expected_lifecycle_state
    assert result.reply_owner == "gateway"


@pytest.mark.parametrize("blank_id", [None, "", "   ", "\t\n"])
def test_reply_ownership_for_contract_blank_id_returns_none(blank_id) -> None:
    """Whitespace-only ids must normalize to blank, not reach the
    repository lookup as a literal '   ' key."""
    gateway = ActionGateway()
    assert gateway.reply_ownership_for_contract(blank_id) is None


def test_reply_ownership_for_contract_whitespace_padded_id_is_normalized() -> None:
    """A contract_id with incidental surrounding whitespace must still
    resolve to the real contract — the normalization strips, not rejects."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="c1"))

    result = gateway.reply_ownership_for_contract("  c1  ")

    assert result is not None
    assert result.contract_ref == "c1"


def test_reply_ownership_for_contract_unknown_id_returns_none() -> None:
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="c1"))

    assert gateway.reply_ownership_for_contract("does-not-exist") is None


def test_reply_ownership_for_contract_repository_failure_propagates_not_none() -> None:
    """A repository read failure must be distinguishable from a clean
    'no such contract' — it must raise, never silently return None (which a
    caller could misread as 'no ownership claim, Agent may speak').
    ExecutionLedger.find_by_id() already keeps this distinction (comment at
    its own definition: 'Repository lookup failures intentionally
    propagate; only clean not-found/expiry returns None') — this test
    proves reply_ownership_for_contract() does not swallow it."""

    class _RaisingRepository:
        def get(self, contract_id: str):
            raise RuntimeError("simulated repository outage")

    gateway = ActionGateway(ledger=ExecutionLedger(repository=_RaisingRepository()))

    with pytest.raises(RuntimeError):
        gateway.reply_ownership_for_contract("some-contract-id")


# ── B. Current-turn correlation ────────────────────────────────────────


def test_stale_unrelated_contract_for_same_user_cannot_own_this_turn() -> None:
    """Two contracts exist for the same user; this turn touched contract A
    (older). Asking for B's ownership by exact id must reflect B, not A —
    and asking for an id this turn never touched must not silently borrow
    A's or B's answer."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("completed", contract_id="A", created_at=time.time() - 200))
    gateway._ledger.save(_contract("pending", contract_id="B", created_at=time.time() - 100))

    result_a = gateway.reply_ownership_for_contract("A")
    result_b = gateway.reply_ownership_for_contract("B")

    assert result_a.contract_ref == "A"
    assert result_a.lifecycle_state == "completed"
    assert result_b.contract_ref == "B"
    assert result_b.lifecycle_state == "pending"


def test_ownership_derived_from_exact_touched_contract_not_latest_or_earliest() -> None:
    """Three contracts exist for one user; this turn's own evidence names
    the OLDEST one (A) by exact id, even though B (newer) and C (newest)
    also exist. reply_ownership_for_contract('A') must reflect A regardless
    of what approval_status() (the user-scoped 'latest contract' query)
    would have returned for the same user."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("rejected", contract_id="A", created_at=time.time() - 300))
    gateway._ledger.save(_contract("pending", contract_id="B", created_at=time.time() - 200))
    gateway._ledger.save(_contract("completed", contract_id="C", created_at=time.time() - 100))

    exact = gateway.reply_ownership_for_contract("A")
    latest_for_user = gateway.approval_status("user-a")

    assert exact.contract_ref == "A"
    assert exact.lifecycle_state == "rejected"
    # approval_status() answers a different question (latest live/most
    # recent contract for the user) — proving the two can legitimately
    # disagree is the point of exact-contract correlation.
    assert latest_for_user.contract_ref != "A"


# ── F. query_execution_status: the projection now GATES rendering ─────


def test_query_execution_status_pending_batch_wording_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """The canonical projection is actually consulted (and must succeed) to
    reach the legacy renderer at all — but the actual user-facing text for
    a multi-pending status query must stay byte-identical to before this
    change once that gate passes."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="p1", created_at=time.time() - 200))
    gateway._ledger.save(_contract("pending", contract_id="p2", created_at=time.time() - 100))

    calls = []
    original = ActionGateway.approval_status

    def _tracking(self, canonical_user_id, **kwargs):
        calls.append(canonical_user_id)
        return original(self, canonical_user_id, **kwargs)

    monkeypatch.setattr(ActionGateway, "approval_status", _tracking)

    text = gateway.query_execution_status("user-a")

    assert calls == ["user-a"], "approval_status() must actually be invoked, not skipped"
    assert text is not None
    assert text != _PENDING_STATUS_UNVERIFIABLE_MESSAGE
    assert "ממתינות לאישור" in text or "ממתין לאישור" in text


def test_query_execution_status_single_pending_wording_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="p1"))

    calls = []
    original = ActionGateway.approval_status

    def _tracking(self, canonical_user_id, **kwargs):
        calls.append(canonical_user_id)
        return original(self, canonical_user_id, **kwargs)

    monkeypatch.setattr(ActionGateway, "approval_status", _tracking)

    text = gateway.query_execution_status("user-a")

    assert calls == ["user-a"]
    assert text is not None
    assert text != _PENDING_STATUS_UNVERIFIABLE_MESSAGE
    assert "ממתינה לאישור" in text or "ממתין לאישור" in text


def test_query_execution_status_projection_failure_fails_closed_not_legacy_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read failure while building the canonical projection must NOT
    silently fall through to rendering the legacy pending text anyway — it
    must return the existing deterministic non-Agent fallback instead."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="p1"))

    def _raising(self, canonical_user_id, **kwargs):
        raise RuntimeError("simulated projection failure")

    monkeypatch.setattr(ActionGateway, "approval_status", _raising)

    text = gateway.query_execution_status("user-a")

    assert text == _PENDING_STATUS_UNVERIFIABLE_MESSAGE
    # never the legacy pending renderer's own multi/single wording shape
    assert "שלח מספר" not in text and "יש פעולה שממתינה" not in text and "יש משימה שממתינה" not in text


def test_query_execution_status_none_projection_fails_closed_not_legacy_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """approval_status() unexpectedly returning None (despite live being
    non-empty) must not be treated as license to render the legacy pending
    text — the returned projection is actually consulted, not merely
    called."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="p1"))

    monkeypatch.setattr(ActionGateway, "approval_status", lambda self, *a, **kw: None)

    text = gateway.query_execution_status("user-a")

    assert text == _PENDING_STATUS_UNVERIFIABLE_MESSAGE


def test_query_execution_status_non_gateway_reply_owner_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A projection that does not claim reply_owner=='gateway' must not be
    allowed to proceed to legacy pending rendering — proves the gate checks
    the RETURNED projection's content, not merely that a call happened."""
    gateway = ActionGateway()
    gateway._ledger.save(_contract("pending", contract_id="p1"))

    def _wrong_owner(self, canonical_user_id, **kwargs):
        return ActionLifecycleResult(
            contract_ref="p1", lifecycle_state="pending", approval_state="pending",
            execution_state="not_started", reply_owner="agent",
        )

    monkeypatch.setattr(ActionGateway, "approval_status", _wrong_owner)

    text = gateway.query_execution_status("user-a")

    assert text == _PENDING_STATUS_UNVERIFIABLE_MESSAGE
