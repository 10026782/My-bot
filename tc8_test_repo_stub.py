"""
tc8_test_repo_stub.py — shared TC8 TurnStateRepository test double.

NOT itself a test_*.py file (deliberately named without that prefix) — CI's
`for f in test_*.py; do python "$f"; done` loop would otherwise try to
execute this as a standalone test script.

app.py's _tc8_claim_contract() unconditionally instantiates
core.turn_state_repository.TurnStateRepository() at all 4 approve/reject/
text-confirm/cancel callback sites. That class defaults to
core.database.get_conn(), which returns None whenever DATABASE_URL isn't
configured — true for local/CI runs with no Postgres. Without a stub, any
test that exercises a live ActionContract through the callback path hits
TurnStateStoreError, and app.py's own try/except at each call site fails
closed with a generic "already being handled" reply — correct production
behavior, but it masks the approve/reject/execute outcome these tests
assert on. test_tc8_runtime_integration.py already established this
monkeypatch pattern for its own single-identity concurrency scenario; this
module generalizes it (multiple identities/contracts, sequential use only)
for the other callback-path regression tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch


@dataclass
class _Row:
    version: int
    state: str = "active"
    operation_id: str = ""


class InMemoryTurnStateRepository:
    """Sequential-use stand-in for TurnStateRepository — one row per
    (tenant_id, canonical_user_id), no real concurrency guarantees."""

    def __init__(self):
        self._rows: dict[tuple[str, str], _Row] = {}

    def begin_or_get(self, tenant_id, canonical_user_id, turn_id, active_contract_id):
        key = (tenant_id, canonical_user_id)
        row = self._rows.get(key)
        if row is None or row.state in ("released", "terminal"):
            row = _Row(version=(row.version + 1) if row else 1)
            self._rows[key] = row
        return row

    def claim(self, tenant_id, canonical_user_id, *, expected_version, operation_id, owner_kind):
        row = self._rows[(tenant_id, canonical_user_id)]
        if row.state != "active" or row.version != expected_version:
            from core.turn_state_repository import TurnStateConflictError
            raise TurnStateConflictError("stub: claim lost race")
        row.state = "claimed"
        row.operation_id = operation_id
        row.version += 1
        return type("Result", (), {"state": row})()

    def _owner_mutate(self, tenant_id, canonical_user_id, expected_version, operation_id, state):
        # Audit #9-4 fidelity: mirrors TurnStateRepository._owner_mutate()'s
        # CAS — WHERE state = 'claimed' AND operation_id = %s AND version = %s
        # — instead of mutating unconditionally.
        row = self._rows[(tenant_id, canonical_user_id)]
        if row.state != "claimed" or row.version != expected_version or row.operation_id != operation_id:
            from core.turn_state_repository import TurnStateConflictError
            raise TurnStateConflictError("stub: stale, terminal, or non-owner operation")
        row.state = state
        row.version += 1

    def finalize(self, tenant_id, canonical_user_id, *, expected_version, operation_id, terminal_reason=None):
        self._owner_mutate(tenant_id, canonical_user_id, expected_version, operation_id, "terminal")

    def release(self, tenant_id, canonical_user_id, *, expected_version, operation_id, terminal_reason=None):
        self._owner_mutate(tenant_id, canonical_user_id, expected_version, operation_id, "released")


def patch_turn_state_repository() -> None:
    """Patch core.turn_state_repository.TurnStateRepository for the rest of
    this process's lifetime — call once near the top of a standalone
    test_*.py script (which runs top-level, not inside pytest fixtures)."""
    patch("core.turn_state_repository.TurnStateRepository", InMemoryTurnStateRepository).start()
