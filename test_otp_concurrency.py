"""
Regression test — core/otp.py verify_otp() concurrency race (C05-C07 audit finding #2).

Covers:
  1. Concurrent verify_otp() calls with the WRONG code never exceed MAX_ATTEMPTS
     recorded attempts, even when fired from many threads at once (the original
     bug: unlocked read-increment-write let concurrent callers under-count).
  2. Concurrent verify_otp() calls with the RIGHT code result in exactly one
     True (single consumption) — no double-success from a race on `consumed`.
  3. After consumption (success or attempt-exhaustion), further calls always
     return False (replay rejection holds under concurrency too).

Uses real threads (not asyncio) against the module's actual `_lock` — this
would have been flaky/failing before the fix and is deterministic after it.
"""

import sys
import threading

import core.otp as otp


def _fresh_request(monkeypatch_send=True):
    """Issues an OTP without hitting Telegram — returns (request_id, code)."""
    captured = {}

    def _fake_send(code, purpose):
        captured["code"] = code
        return True

    orig_send = otp._send_code
    otp._send_code = _fake_send
    try:
        request_id = otp.request_otp("test-purpose", "test-identity")
    finally:
        otp._send_code = orig_send
    return request_id, captured["code"]


def run() -> bool:
    results = []

    def chk(desc, cond):
        results.append((desc, bool(cond)))

    # ── 1. Concurrent wrong-code attempts never exceed MAX_ATTEMPTS accounting ──
    request_id, real_code = _fresh_request()
    wrong_code = "000000" if real_code != "000000" else "111111"

    N_THREADS = 30
    outcomes = []
    outcomes_lock = threading.Lock()
    barrier = threading.Barrier(N_THREADS)

    def _attempt_wrong():
        barrier.wait()
        r = otp.verify_otp(request_id, wrong_code)
        with outcomes_lock:
            outcomes.append(r)

    threads = [threading.Thread(target=_attempt_wrong) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entry = otp._store.get(request_id)
    chk("all concurrent wrong-code attempts returned False", all(r is False for r in outcomes))
    # Once attempts crosses MAX_ATTEMPTS, `consumed` is set and every later
    # racer short-circuits on the `entry["consumed"]` check before incrementing
    # again — so the counter must land at exactly MAX_ATTEMPTS + 1, never less
    # (a lost update) and never more (a racer squeezing past the boundary
    # after consumption was set, which is exactly what the unlocked version
    # allowed).
    chk(
        "attempts counter stops at exactly MAX_ATTEMPTS + 1 (no lost/extra updates)",
        entry is not None and entry["attempts"] == otp.MAX_ATTEMPTS + 1,
    )
    chk(
        "entry consumed (blocked) once attempts exceeded MAX_ATTEMPTS",
        entry is not None and entry["consumed"] is True,
    )
    chk(
        "further verify after exhaustion still returns False (no un-consume)",
        otp.verify_otp(request_id, real_code) is False,
    )

    # ── 2. Concurrent correct-code attempts → exactly one success (single consumption) ──
    request_id2, real_code2 = _fresh_request()

    N_RACERS = 20
    successes = []
    successes_lock = threading.Lock()
    barrier2 = threading.Barrier(N_RACERS)

    def _attempt_correct():
        barrier2.wait()
        r = otp.verify_otp(request_id2, real_code2)
        with successes_lock:
            successes.append(r)

    threads2 = [threading.Thread(target=_attempt_correct) for _ in range(N_RACERS)]
    for t in threads2:
        t.start()
    for t in threads2:
        t.join()

    chk(
        "exactly one concurrent verify_otp() call succeeded (single consumption)",
        sum(1 for r in successes if r is True) == 1,
    )
    chk(
        "all other concurrent racers got False, not a second True",
        sum(1 for r in successes if r is False) == N_RACERS - 1,
    )

    entry2 = otp._store.get(request_id2)
    chk("consumed flag set after the winning verification", entry2 is not None and entry2["consumed"] is True)

    # ── 3. Replay after success is rejected ──
    chk(
        "replay with correct code after success → False",
        otp.verify_otp(request_id2, real_code2) is False,
    )

    # ── 4. Sequential sanity: correct code on a fresh, unraced request still works ──
    request_id3, real_code3 = _fresh_request()
    chk("sequential correct verify still succeeds (no functional regression)",
        otp.verify_otp(request_id3, real_code3) is True)
    chk("sequential replay rejected", otp.verify_otp(request_id3, real_code3) is False)

    # ── report ──
    print("\n=== core/otp.py verify_otp() concurrency regression test ===")
    failed = [d for d, ok in results if not ok]
    for desc, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return not failed


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
