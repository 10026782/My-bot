#!/usr/bin/env python3
"""
test_tc8_repo_stub_fidelity.py — Audit #9-4 fidelity regression for
tc8_test_repo_stub.py's InMemoryTurnStateRepository.

Proves finalize()/release() enforce the same CAS (expected_version +
claimed-operation ownership) as the real core.turn_state_repository
.TurnStateRepository._owner_mutate() — not an unconditional mutation —
without touching the real approval-callback tests that consume this stub
for their own, separate scenarios.
"""

import sys

from core.turn_state_repository import TurnStateConflictError
from tc8_test_repo_stub import InMemoryTurnStateRepository

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _claimed_repo():
    repo = InMemoryTurnStateRepository()
    state = repo.begin_or_get("boss_hq", "owner-1", "turn-1", "c1")
    claimed = repo.claim("boss_hq", "owner-1", expected_version=state.version,
                          operation_id="approve:op1", owner_kind="approval")
    return repo, claimed.state


# 1. Valid claimed/version/operation path succeeds
repo, row = _claimed_repo()
repo.finalize("boss_hq", "owner-1", expected_version=row.version, operation_id=row.operation_id)
chk("finalize: valid claimed/version/operation succeeds", row.state == "terminal")

# 2. Stale version fails
repo, row = _claimed_repo()
try:
    repo.release("boss_hq", "owner-1", expected_version=row.version + 1, operation_id=row.operation_id)
    raised = False
except TurnStateConflictError:
    raised = True
chk("release: stale version raises TurnStateConflictError", raised)
chk("release: stale version does not mutate row state", row.state == "claimed")

# 3. Wrong operation ownership fails
repo, row = _claimed_repo()
try:
    repo.finalize("boss_hq", "owner-1", expected_version=row.version, operation_id="someone_else:op2")
    raised = False
except TurnStateConflictError:
    raised = True
chk("finalize: wrong operation_id raises TurnStateConflictError", raised)
chk("finalize: wrong operation_id does not mutate row state", row.state == "claimed")

# 4. release() on a non-claimed (still active) row fails
repo = InMemoryTurnStateRepository()
row = repo.begin_or_get("boss_hq", "owner-1", "turn-1", "c1")
try:
    repo.release("boss_hq", "owner-1", expected_version=row.version, operation_id="op1")
    raised = False
except TurnStateConflictError:
    raised = True
chk("release: never-claimed row raises TurnStateConflictError", raised)

print(f"\n{'='*50}")
print(f"TC8 repo stub fidelity tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
