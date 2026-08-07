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
import time

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
results1: list[str | None] = []
results1_lock = threading.Lock()


def _claim_worker():
    barrier1.wait()  # release all N threads at the same instant
    token = ledger1.claim_fingerprint_cas(fingerprint1, None)
    with results1_lock:
        results1.append(token)


threads1 = [threading.Thread(target=_claim_worker, daemon=True) for _ in range(N)]
for t in threads1:
    t.start()
for t in threads1:
    t.join(timeout=5.0)

chk("all threads finished (no deadlock)", not any(t.is_alive() for t in threads1))
_won1 = [r for r in results1 if r is not None]
chk(f"exactly one of {N} simultaneous claims wins", len(_won1) == 1)
chk(f"the other {N - 1} all lose (race, not duplicate success)",
    results1.count(None) == N - 1)


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
a_token = ledger1b.claim_fingerprint_cas(fingerprint1b, a_expected)
b_token = ledger1b.claim_fingerprint_cas(fingerprint1b, b_expected)

chk(
    "exactly one of the two interleaved 'threads' is granted the claim — "
    "this is the exact check that was MISSING before BUG-157 (the old code "
    "had no such gate at all, so both would have proceeded to save())",
    (a_token is not None) != (b_token is not None),
)


# ══════════════════════════════════════════════════════════════════
print("\n── 2. release_fingerprint_claim() frees a claim for a later attempt ──")

ledger2 = ExecutionLedger()
fingerprint2 = "test-fingerprint-release"
token2a = ledger2.claim_fingerprint_cas(fingerprint2, None)
chk("first claim on an unclaimed fingerprint succeeds (returns a token)",
    token2a is not None)
chk("a second claim attempt on the SAME (still in-flight) fingerprint fails",
    ledger2.claim_fingerprint_cas(fingerprint2, None) is None)
ledger2.release_fingerprint_claim(fingerprint2, token2a)
token2b = ledger2.claim_fingerprint_cas(fingerprint2, None)
chk("after release, a fresh claim on the same fingerprint succeeds again",
    token2b is not None)
chk("the second claim gets a DIFFERENT token than the first (opaque, per-claim)",
    token2b != token2a)
# idempotency — releasing with the (now-stale) first token, or repeatedly with
# the current one, must never raise and must never clear an unrelated claim
ledger2.release_fingerprint_claim(fingerprint2, token2a)
chk("release with a STALE token is a safe no-op — the current claim (token2b) "
    "survives it", ledger2.claim_fingerprint_cas(fingerprint2, None) is None)
ledger2.release_fingerprint_claim(fingerprint2, token2b)
ledger2.release_fingerprint_claim(fingerprint2, token2b)
chk("release_fingerprint_claim() is idempotent (double release doesn't raise)", True)


# ══════════════════════════════════════════════════════════════════
# BUG-157 round 2 (CodeRabbit, 07/08/2026): _cache_contract() used to
# release ANY claim on a fingerprint unconditionally — including when
# called from a pure READ-path cache-warm (find_by_id()/find_by_fingerprint()
# hydrating from the repository), not just from the legitimate claim
# holder's own save(). A caller that merely LOOKS UP a fingerprint could
# accidentally steal/void another caller's active claim. The token-based
# fix closes this: only the exact token a caller was granted can release
# its own claim; a cache-warm with no token can never touch it.
print("\n── 2b. _cache_contract() read-path cache-warm never releases another "
      "caller's active claim (no claim_token passed) ──")

ledger2b = ExecutionLedger()
fingerprint2b = "test-fingerprint-cache-warm-no-steal"
token2b_owner = ledger2b.claim_fingerprint_cas(fingerprint2b, None)
chk("caller A holds a real claim", token2b_owner is not None)

# Simulate a concurrent caller's pure read-path cache warm (e.g.
# find_by_fingerprint()'s repository-recovery branch) — no claim_token.
from core.action_gateway import ActionContract as _AC2b  # noqa: E402

_fake_contract2b = _AC2b(
    contract_id="fake-cached-id", tenant_id="boss_hq", canonical_user_id="u",
    tool_name="airtable_add", normalized_payload={}, business_action_fingerprint=fingerprint2b,
    origin_channel="telegram", origin_chat_id="u", requires_approval=True,
    status="rejected", created_at=time.time(),
)
ledger2b._cache_contract(_fake_contract2b)  # no claim_token — read-path shape

chk(
    "caller A's claim is UNTOUCHED by the unrelated cache-warm — a second "
    "claimer still cannot steal it",
    ledger2b.claim_fingerprint_cas(fingerprint2b, "fake-cached-id") is None,
)
ledger2b.release_fingerprint_claim(fingerprint2b, token2b_owner)
chk(
    "only caller A's own (correct) token actually releases it",
    ledger2b.claim_fingerprint_cas(fingerprint2b, "fake-cached-id") is not None,
)


# ══════════════════════════════════════════════════════════════════
print("\n── 3. claim_fingerprint_cas() correctly rejects a stale expectation ──")

ledger3 = ExecutionLedger()
fingerprint3 = "test-fingerprint-stale-expectation"
token3 = ledger3.claim_fingerprint_cas(fingerprint3, None)
chk("claim with expected=None succeeds when nothing exists yet",
    token3 is not None)
ledger3.release_fingerprint_claim(fingerprint3, token3)
# simulate: another thread already saved a real contract for this
# fingerprint (updates _by_fingerprint directly, mirroring what save() does)
ledger3._by_fingerprint[fingerprint3] = "some-other-contract-id"
chk(
    "a caller whose earlier lookup still expects 'no contract' (None) loses "
    "the claim once someone else's contract is actually indexed",
    ledger3.claim_fingerprint_cas(fingerprint3, None) is None,
)
chk(
    "a caller whose lookup correctly observed the CURRENT contract_id wins "
    "the claim (this is the BUG-153 rejected-carve-out case: expected == "
    "the rejected contract's own id, not None)",
    ledger3.claim_fingerprint_cas(fingerprint3, "some-other-contract-id") is not None,
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


# ══════════════════════════════════════════════════════════════════
# CodeRabbit round 2 (05/08/2026): מפסיד ב-race אסור שימצה מייד את
# _CLAIM_MAX_ATTEMPTS בזמן שהמנצח עדיין באמצע save() (רלוונטי כש-
# FEATURE_ACTION_CONTRACT_PERSISTENCE מבצע I/O עמיד אמיתי עם latency
# לא-טריוויאלי) — הוא חייב להמתין ל-claim המתחרה שישוחרר, ואז לראות את
# ה-contract האמיתי של המנצח, לא לדווח כשל-עומס "persistence_lookup_
# failed" שגוי.
print("\n── 6. delayed save(): a losing caller waits for the winner's "
      "in-flight claim instead of exhausting retries ──")

gw6 = ActionGateway(ledger=ExecutionLedger())
identity6 = _identity("req_bug157_delayed_save")
barrier6 = threading.Barrier(2)
_save_delay_seconds = 0.5
_real_save6 = gw6._ledger.save


def _delayed_save6(contract, *, claim_token=None):
    time.sleep(_save_delay_seconds)
    return _real_save6(contract, claim_token=claim_token)


gw6._ledger.save = _delayed_save6
results6: dict[str, object] = {}
results6_lock = threading.Lock()


def _propose_worker6(label: str):
    barrier6.wait()
    result = gw6.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity6.memory_key,
        tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "בדיקת delayed save"}},
        origin_channel="telegram", origin_chat_id=identity6.user_id,
        requires_approval=True, identity=identity6, trusted_source="agent",
    )
    with results6_lock:
        results6[label] = result


threads6 = [
    threading.Thread(target=_propose_worker6, args=("a",), daemon=True),
    threading.Thread(target=_propose_worker6, args=("b",), daemon=True),
]
_start6 = time.monotonic()
for t in threads6:
    t.start()
_join_deadline6 = _start6 + _save_delay_seconds + 5.0
for t in threads6:
    t.join(timeout=max(0.0, _join_deadline6 - time.monotonic()))
_elapsed6 = time.monotonic() - _start6

winners6 = [r for r in results6.values() if r.ok]
losers6 = [r for r in results6.values() if not r.ok]

chk(
    "both concurrent calls returned (no deadlock/hang)",
    len(results6) == 2 and not any(t.is_alive() for t in threads6),
)
chk("exactly one call won and created the contract", len(winners6) == 1)
chk("exactly one call lost", len(losers6) == 1)
if losers6:
    loser6 = losers6[0]
    chk(
        "the loser waited for the winner's contract instead of reporting a "
        "false 'load too high' exhaustion failure",
        loser6.failure_code != "persistence_lookup_failed",
    )
    chk(
        "the loser's response correctly points at the winner's own "
        "contract_id (real dedup, not a generic failure)",
        winners6 and loser6.contract_id == winners6[0].contract_id,
    )
chk(
    f"total race time (~{_elapsed6:.2f}s) is bounded by the winner's single "
    f"save() delay ({_save_delay_seconds}s), not multiplied by retries",
    _elapsed6 < _save_delay_seconds + 1.0,
)


# ══════════════════════════════════════════════════════════════════
# BUG-157 round 2 (CodeRabbit, 07/08/2026) — the exact scenario from the
# review comment: two deterministic_create_task proposals for the SAME
# fingerprint, where the existing contract is "rejected" (the BUG-153
# reconfirmation-after-rejection carve-out — the one case propose_action()
# lets a new contract be created for an already-rejected fingerprint).
# Caller A wins the claim first. Before A saves, a concurrent COLD-CACHE
# read (e.g. find_by_fingerprint()'s repository-recovery branch re-hydrating
# the same rejected contract into RAM) re-caches the identical rejected
# contract — simulated directly via _cache_contract() with no claim_token,
# exactly the shape that read path uses. Pre-fix, this unconditionally
# cleared A's claim, letting a second claimer (caller B) win it too, and
# BOTH could go on to save a replacement contract for one fingerprint —
# the very duplicate this whole bug fix exists to prevent.
print("\n── 7. cold-cache re-hydration of the SAME rejected contract mid-"
      "claim never lets a second caller steal the reservation ──")

ledger7 = ExecutionLedger()
identity7 = _identity("req_bug157_cold_cache_reject")
fingerprint7 = "test-fingerprint-cold-cache-rejected-race"

rejected7 = _AC2b(
    contract_id="rejected-contract-7", tenant_id="boss_hq",
    canonical_user_id=identity7.memory_key, tool_name="airtable_add",
    normalized_payload={"table": "Tasks", "fields": {"כותרת המשימה": "נדחה קודם"}},
    business_action_fingerprint=fingerprint7, origin_channel="telegram",
    origin_chat_id=identity7.user_id, requires_approval=True,
    status="rejected", created_at=time.time(),
)
ledger7._cache_contract(rejected7)  # seed: rejected contract already "known"

# Caller A: sees the rejected contract, wins the claim to (re)propose it —
# mirrors propose_action()'s own expected_prior_contract_id == existing.contract_id.
token_a7 = ledger7.claim_fingerprint_cas(fingerprint7, rejected7.contract_id)
chk("caller A wins the claim on the rejected-but-reconfirmable fingerprint",
    token_a7 is not None)

# Caller B's concurrent COLD-CACHE READ re-hydrates the SAME rejected
# contract from the repository (no claim_token — this is the exact call
# shape find_by_id()/find_by_fingerprint()/find_live_by_user() use).
ledger7._cache_contract(rejected7)

chk(
    "the cold-cache re-hydration did NOT release caller A's claim — a "
    "second claimer still cannot win it",
    ledger7.claim_fingerprint_cas(fingerprint7, rejected7.contract_id) is None,
)

# Caller A completes its proposal normally with its own (still-valid) token.
replacement7 = _AC2b(
    contract_id="replacement-contract-7", tenant_id="boss_hq",
    canonical_user_id=identity7.memory_key, tool_name="airtable_add",
    normalized_payload={"table": "Tasks", "fields": {"כותרת המשימה": "נדחה קודם"}},
    business_action_fingerprint=fingerprint7, origin_channel="telegram",
    origin_chat_id=identity7.user_id, requires_approval=True,
    status="pending", created_at=time.time(),
)
ledger7.save(replacement7, claim_token=token_a7)

chk("caller A's save() succeeds and correctly releases its own claim",
    ledger7.claim_fingerprint_cas(fingerprint7, "replacement-contract-7") is not None)
chk(
    "exactly one contract is now indexed for this fingerprint — never two "
    "'winners' from the cold-cache steal",
    ledger7._by_fingerprint[fingerprint7] == "replacement-contract-7",
)


print()
print("=" * 50)
print(f"BUG-157 (atomic fingerprint claim) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
