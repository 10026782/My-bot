#!/usr/bin/env python3
"""
test_bug157_atomic_fingerprint_claim.py — BUG-157 (propose_action() was not
atomic around its existing-fingerprint lookup and its save(), allowing two
concurrent proposers to each create a live contract for the identical
business fingerprint).

Problem (raised by CodeRabbit on PR #550, 04/08/2026; owner decision: fix in
a separate PR): ActionGateway.propose_action() called
ExecutionLedger.find_by_fingerprint() (check) and, later in the same method,
ExecutionLedger.save() (act) as two independent steps with no lock spanning
both. ExecutionLedger._lock protects each individual operation but not the
sequence.

This is not theoretical: scheduler.py starts a genuine background thread
(threading.Thread(name="scheduler"), scheduler.py:844) running scheduled
jobs — core/lead_recovery.py and followup_engine.py both call
ActionGateway.propose_gated() (-> propose_action()) from that thread, fully
concurrently with the main Flask request-handling thread in the same
process (gunicorn workers=1 rules out multiple PROCESSES, not multiple
THREADS within one). Two threads racing on the identical business
fingerprint could both pass "no blocking existing contract" before either
had saved.

Fix: ExecutionLedger gained an atomic compare-and-set claim
(claim_fingerprint_cas()/release_fingerprint_claim()), and propose_action()
wraps its lookup+status-branch-decision+claim in a small bounded retry loop
(5 attempts) — a claim loss means a concurrent writer just finished, and the
very next lookup sees the now-current state and returns the correct dedup
response instead of creating a duplicate.

See docs/architecture/action-gateway/BUG-157_ATOMIC_FINGERPRINT_CLAIM_20260805.md
for the full design and Cross-Layer Impact Matrix.
"""

from __future__ import annotations

import threading

from core.action_gateway import ActionGateway, ExecutionLedger
from identity import Identity, Role

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


# ══════════════════════════════════════════════════════════════════
print("── 1. claim_fingerprint_cas(): exactly one of N truly-simultaneous "
      "threads wins an unclaimed fingerprint ──")

ledger1 = ExecutionLedger()
fingerprint1 = "test-fingerprint-simultaneous-claim"
N = 8
barrier1 = threading.Barrier(N)
results1: list[bool] = []
results1_lock = threading.Lock()


def _claim_worker():
    barrier1.wait()  # release all N threads at the same instant
    won = ledger1.claim_fingerprint_cas(fingerprint1, None)
    with results1_lock:
        results1.append(won)


threads1 = [threading.Thread(target=_claim_worker) for _ in range(N)]
for t in threads1:
    t.start()
for t in threads1:
    t.join()

chk(f"exactly one of {N} simultaneous claims wins", results1.count(True) == 1)
chk(f"the other {N - 1} all lose (race, not duplicate success)", results1.count(False) == N - 1)


# ══════════════════════════════════════════════════════════════════
# Real OS-thread races are timing-dependent — section 1 above is a genuine
# smoke test, but its pass/fail is technically probabilistic (GIL/scheduler
# permitting). This section reproduces the exact defect DETERMINISTICALLY
# by manually interleaving the check-then-act steps propose_action() itself
# performs — no timing luck involved, fails 100% of the time on the
# pre-fix code (verified directly against core/action_gateway.py before
# this fix: two ActionContracts were created for one identical fingerprint
# every single run) and passes 100% of the time after it.
print("\n── 1b. deterministic manual interleave: the exact race, without OS "
      "thread timing ──")

ledger1b = ExecutionLedger()
fingerprint1b = "test-fingerprint-deterministic-interleave"

# Both "threads" check before either acts — this is the race window itself.
a_seen = ledger1b.find_by_fingerprint(fingerprint1b)
b_seen = ledger1b.find_by_fingerprint(fingerprint1b)
chk("setup: both interleaved lookups see 'no existing contract'",
    a_seen is None and b_seen is None)

a_expected = a_seen.contract_id if a_seen else None
b_expected = b_seen.contract_id if b_seen else None
a_claimed = ledger1b.claim_fingerprint_cas(fingerprint1b, a_expected)
b_claimed = ledger1b.claim_fingerprint_cas(fingerprint1b, b_expected)

chk(
    "exactly one of the two interleaved 'threads' is granted the claim — "
    "this is the exact check that was MISSING before BUG-157 (the old code "
    "had no such gate at all, so both would have proceeded to save())",
    (a_claimed, b_claimed) in ((True, False), (False, True)),
)


# ══════════════════════════════════════════════════════════════════
print("\n── 2. release_fingerprint_claim() frees a claim for a later attempt ──")

ledger2 = ExecutionLedger()
fingerprint2 = "test-fingerprint-release"
chk("first claim on an unclaimed fingerprint succeeds",
    ledger2.claim_fingerprint_cas(fingerprint2, None) is True)
chk("a second claim attempt on the SAME (still in-flight) fingerprint fails",
    ledger2.claim_fingerprint_cas(fingerprint2, None) is False)
ledger2.release_fingerprint_claim(fingerprint2)
chk("after release, a fresh claim on the same fingerprint succeeds again",
    ledger2.claim_fingerprint_cas(fingerprint2, None) is True)
# idempotency
ledger2.release_fingerprint_claim(fingerprint2)
ledger2.release_fingerprint_claim(fingerprint2)
chk("release_fingerprint_claim() is idempotent (double release doesn't raise)", True)


# ══════════════════════════════════════════════════════════════════
print("\n── 3. claim_fingerprint_cas() correctly rejects a stale expectation ──")

ledger3 = ExecutionLedger()
fingerprint3 = "test-fingerprint-stale-expectation"
chk("claim with expected=None succeeds when nothing exists yet",
    ledger3.claim_fingerprint_cas(fingerprint3, None) is True)
ledger3.release_fingerprint_claim(fingerprint3)
# simulate: another thread already saved a real contract for this
# fingerprint (updates _by_fingerprint directly, mirroring what save() does)
ledger3._by_fingerprint[fingerprint3] = "some-other-contract-id"
chk(
    "a caller whose earlier lookup still expects 'no contract' (None) loses "
    "the claim once someone else's contract is actually indexed",
    ledger3.claim_fingerprint_cas(fingerprint3, None) is False,
)
chk(
    "a caller whose lookup correctly observed the CURRENT contract_id wins "
    "the claim (this is the BUG-153 rejected-carve-out case: expected == "
    "the rejected contract's own id, not None)",
    ledger3.claim_fingerprint_cas(fingerprint3, "some-other-contract-id") is True,
)


# ══════════════════════════════════════════════════════════════════
print("\n── 4. end-to-end: N concurrent propose_action() calls, identical "
      "fingerprint — exactly one live contract, never N ──")

gw4 = ActionGateway(ledger=ExecutionLedger())
identity4 = _identity("req_bug157_concurrent")
N4 = 5  # matches propose_action()'s own _CLAIM_MAX_ATTEMPTS budget
barrier4 = threading.Barrier(N4)
results4: list = []
results4_lock = threading.Lock()


def _propose_worker():
    barrier4.wait()
    result = gw4.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity4.memory_key,
        tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת race אמיתי"}},
        origin_channel="telegram", origin_chat_id=identity4.user_id,
        requires_approval=True, identity=identity4, trusted_source="agent",
    )
    with results4_lock:
        results4.append(result)


threads4 = [threading.Thread(target=_propose_worker) for _ in range(N4)]
for t in threads4:
    t.start()
for t in threads4:
    t.join()

chk(f"all {N4} concurrent propose_action() calls returned (no deadlock/hang)",
    len(results4) == N4)
chk("exactly one of them actually created a new contract (ok=True)",
    sum(1 for r in results4 if r.ok) == 1)
chk(
    f"the other {N4 - 1} correctly report the duplicate/pending state, not "
    "a phantom success and not a raised exception",
    sum(1 for r in results4 if not r.ok) == N4 - 1,
)

live4 = gw4.find_live_contracts(identity4.memory_key)
chk(
    "exactly ONE live contract exists for this identity after the race — "
    "this is the actual defect this fix closes (used to be able to become N)",
    len(live4) == 1,
)


# ══════════════════════════════════════════════════════════════════
print("\n── 5. regression: a single, non-concurrent propose_action() call "
      "still behaves exactly as before (no retry-loop side effects) ──")

gw5 = ActionGateway(ledger=ExecutionLedger())
identity5 = _identity("req_bug157_baseline")
result5 = gw5.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity5.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת מקרה רגיל"}},
    origin_channel="telegram", origin_chat_id=identity5.user_id,
    requires_approval=True, identity=identity5, trusted_source="agent",
)
chk("baseline (no contention) proposal succeeds on the first attempt", result5.ok)
chk("baseline contract_id assigned", result5.contract_id is not None)
final5 = gw5.find_contract(result5.contract_id)
chk("baseline contract status is 'pending'", final5 is not None and final5.status == "pending")


print()
print("=" * 50)
print(f"BUG-157 (atomic fingerprint claim) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
