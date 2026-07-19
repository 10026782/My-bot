# test_bug114_context_interrupt_amplification.py — regression tests for
# BUG-114: ExecutionLedger.mark_context_interrupted() re-patched every live
# pending ActionContract for a user on every unrelated inbound message,
# including contracts already context_interrupted=True — a pure no-op
# GET+PATCH+GET(readback) per contract, unbounded in time (nothing expires
# a pending contract), observed in production as 19 Airtable calls for one
# unrelated message against 6 live contracts.
#
# See docs/architecture/action-gateway/
# BUG-114_CONTEXT_INTERRUPT_CALL_AMPLIFICATION_AUDIT.md for the full audit
# (all 6 questions, root cause, why this fix is safe).
#
# Fix (core/action_gateway.py::ExecutionLedger.mark_context_interrupted()):
# the existing list-comprehension filter gained one condition —
# `and (c.reconfirmation_required or not c.context_interrupted)` — a pure
# in-memory check (context_interrupted is already a cached ActionContract
# field), zero new Airtable calls. A contract with reconfirmation_required
# =True is NEVER skipped by this, even if its context_interrupted happens
# to already be True — it still needs a real supersede transition (a
# genuine status change), not a no-op re-write of an unchanged field. This
# distinction matters: a naive `and not c.context_interrupted` alone (no
# reconfirmation_required carve-out) would silently break the existing
# one-shot reconfirmation FSM's second-interruption-supersedes rule, since
# by the time a contract needs superseding its context_interrupted is
# already True from the first interruption — Test 3 below is exactly that
# regression guard.
#
# Explicitly NOT touched by this fix: ActionContractRepository.transition()'s
# pre-PATCH read (TOCTOU safety) and post-PATCH readback (verification) —
# both still run in full for every contract that DOES need a write. No
# ActionGateway approval semantics changed.

from __future__ import annotations

import time
from unittest.mock import patch

from core.action_gateway import ActionContract, ExecutionLedger

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_contract(
    contract_id: str, canonical_user_id: str, *,
    status: str = "pending",
    context_interrupted: bool = False,
    reconfirmation_required: bool = False,
) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id=canonical_user_id,
        tool_name="airtable_add",
        normalized_payload={"table": "Tasks", "fields": {"Task": "test"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-1",
        requires_approval=True,
        status=status,
        created_at=time.time(),
        context_interrupted=context_interrupted,
        reconfirmation_required=reconfirmation_required,
    )


USER = "boss_hq:eliyahu"

# ══════════════════════════════════════════════════
# Test 1 — all contracts context_interrupted=False -> all still get marked
# (existing behavior, must be unaffected by the fix)
# ══════════════════════════════════════════════════

ledger1 = ExecutionLedger()
ids1 = [f"c1-{i}" for i in range(3)]
for cid in ids1:
    ledger1.save(_make_contract(cid, USER))

ledger1.mark_context_interrupted(USER)
chk("Test 1: all 3 previously-uninterrupted contracts are now context_interrupted=True",
    all(ledger1._store[cid].context_interrupted for cid in ids1))
chk("Test 1: all 3 remain 'pending' (not superseded — no reconfirmation shown yet)",
    all(ledger1._store[cid].status == "pending" for cid in ids1))

# ══════════════════════════════════════════════════
# Test 2 — mixed already-interrupted / not-interrupted -> only the
# not-interrupted ones trigger update_status() (the actual call-count fix)
# ══════════════════════════════════════════════════

ledger2 = ExecutionLedger()
already_interrupted_ids = [f"c2-already-{i}" for i in range(4)]
not_interrupted_ids = [f"c2-fresh-{i}" for i in range(2)]
for cid in already_interrupted_ids:
    ledger2.save(_make_contract(cid, USER, context_interrupted=True))
for cid in not_interrupted_ids:
    ledger2.save(_make_contract(cid, USER, context_interrupted=False))

with patch.object(ledger2, "update_status", wraps=ledger2.update_status) as spy2:
    ledger2.mark_context_interrupted(USER)
    chk("Test 2: update_status() called exactly for the not-yet-interrupted contracts only "
        "(2, not all 6)", spy2.call_count == len(not_interrupted_ids))
    called_ids = {call.args[0] for call in spy2.call_args_list}
    chk("Test 2: the call set is exactly the not-yet-interrupted contract ids",
        called_ids == set(not_interrupted_ids))

chk("Test 2: the already-interrupted contracts are still context_interrupted=True (unchanged)",
    all(ledger2._store[cid].context_interrupted for cid in already_interrupted_ids))
chk("Test 2: the freshly-interrupted contracts are now context_interrupted=True too",
    all(ledger2._store[cid].context_interrupted for cid in not_interrupted_ids))

# ══════════════════════════════════════════════════
# Test 3 — regression guard: a contract with reconfirmation_required=True
# is NOT skipped even though its context_interrupted is already True — it
# must still supersede (the one-shot FSM's core rule, must survive BUG-114).
# ══════════════════════════════════════════════════

ledger3 = ExecutionLedger()
ready_to_supersede = "c3-ready"
ledger3.save(_make_contract(
    ready_to_supersede, USER, context_interrupted=True, reconfirmation_required=True,
))

ledger3.mark_context_interrupted(USER)
chk("Test 3: a reconfirmation_required contract is NOT skipped by the context_interrupted "
    "filter — it still supersedes", ledger3._store[ready_to_supersede].status == "superseded")
chk("Test 3: superseded contract is no longer 'live' (find_live_by_user excludes it)",
    ledger3.find_live_by_user(USER) == [])

# ══════════════════════════════════════════════════
# Test 4 — regression: pre-existing filters (different user, non-pending
# status) are completely unaffected by the new condition
# ══════════════════════════════════════════════════

ledger4 = ExecutionLedger()
other_user_contract = "c4-other-user"
approved_contract = "c4-approved"
ledger4.save(_make_contract(other_user_contract, "boss_hq:someone_else", context_interrupted=False))
ledger4.save(_make_contract(approved_contract, USER, status="approved", context_interrupted=False))

ledger4.mark_context_interrupted(USER)
chk("Test 4: a different user's contract is untouched",
    ledger4._store[other_user_contract].context_interrupted is False)
chk("Test 4: a non-pending (already approved) contract is untouched",
    ledger4._store[approved_contract].context_interrupted is False
    and ledger4._store[approved_contract].status == "approved")

# ══════════════════════════════════════════════════
# Test 5 — end-to-end call-count assertion matching the production shape:
# N=6 live contracts, M=6 already interrupted (the exact observed
# production sample) -> a subsequent unrelated message triggers 0 calls,
# not 6. This is the concrete "19 Airtable calls -> ~1" claim.
# ══════════════════════════════════════════════════

ledger5 = ExecutionLedger()
six_ids = [f"c5-{i}" for i in range(6)]
for cid in six_ids:
    ledger5.save(_make_contract(cid, USER, context_interrupted=True))

with patch.object(ledger5, "update_status", wraps=ledger5.update_status) as spy5:
    ledger5.mark_context_interrupted(USER)
    chk("Test 5: production-shape sample (6 already-interrupted live contracts) -> "
        "0 update_status() calls on a later unrelated message", spy5.call_count == 0)

# Now interleave: a NEW contract arrives (not yet interrupted) alongside the
# 6 already-interrupted ones — exactly 1 call, not 7.
new_contract_id = "c5-new"
ledger5.save(_make_contract(new_contract_id, USER, context_interrupted=False))
with patch.object(ledger5, "update_status", wraps=ledger5.update_status) as spy5b:
    ledger5.mark_context_interrupted(USER)
    chk("Test 5: adding one fresh contract among 6 already-interrupted -> exactly 1 call, not 7",
        spy5b.call_count == 1)


print()
print("=" * 50)
print(f"BUG-114 context-interrupt amplification tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
