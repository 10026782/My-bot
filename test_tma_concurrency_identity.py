"""
Reproduction test — TMA concurrent-user identity/session isolation
(owner-reported, 04/10/2026): "when two people open the Telegram Mini App
at the same time, only one of them seems able to use it."

Uses two FIXTURE Telegram actors (not live Eliyahu/Avi data):
  USER_A = fake telegram id 100000001 ("TestUserA")
  USER_B = fake telegram id 200000002 ("TestUserB")
both registered under the same fixture tenant, exactly like two real
internal users of the same business would be.

Drives the real production code path — tma_api.require_tma_auth() →
tma_api._validate_initdata() (real HMAC check, fixture bot token) →
identity.resolve_identity() — from two threads with a Barrier forcing
request bodies to execute interleaved, repeated over many rounds, to
surface any shared/global mutable state a single serialized test could
miss. Matches the owner's required scenario: A opens, B opens, A reads,
B reads, A reads again — run both as a strict sequence and under forced
concurrency.

Run: python3 test_tma_concurrency_identity.py
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import tma_api
import identity as identity_mod
from flask import Flask

_FAKE_BOT_TOKEN = "123456:FAKE-BOT-TOKEN-FOR-TEST-ONLY"

_USER_A_ID = "100000001"
_USER_B_ID = "200000002"

_FIXTURE_REGISTRY = {
    f"telegram:{_USER_A_ID}": {
        "tenant": "fixture_tenant", "user": "fixture_user_a",
        "role": identity_mod.Role.OWNER, "name": "TestUserA",
        "domains": list(identity_mod.Domain.ALL),
    },
    f"telegram:{_USER_B_ID}": {
        "tenant": "fixture_tenant", "user": "fixture_user_b",
        "role": identity_mod.Role.MANAGER, "name": "TestUserB",
        "domains": [],
    },
}


def _make_init_data(telegram_user_id: str, bot_token: str) -> str:
    """Builds a real, HMAC-valid Telegram WebApp initData query string."""
    user_json = json.dumps({"id": int(telegram_user_id), "first_name": "Fixture"})
    params = {"auth_date": str(int(time.time())), "user": user_json}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac_mod.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac_mod.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = digest
    return urllib.parse.urlencode(params)


def _build_test_app() -> Flask:
    """A minimal Flask app exposing one endpoint through the REAL
    require_tma_auth decorator — isolates exactly the auth/identity layer
    under test without needing live Airtable/Telegram credentials."""
    app = Flask(__name__)

    @app.route("/whoami")
    @tma_api.require_tma_auth
    def whoami(identity):
        # Deliberate scheduling window: widens the race if ANY shared
        # mutable state (global/module var, cache, session) were involved.
        time.sleep(0.01)
        return {
            "user_id": identity.user_id,
            "tenant_id": identity.tenant_id,
            "role": identity.role,
            "display_name": identity.display_name,
        }

    return app


def _call(client, telegram_user_id: str) -> dict:
    init_data = _make_init_data(telegram_user_id, _FAKE_BOT_TOKEN)
    resp = client.get("/whoami", headers={"X-Telegram-Init-Data": init_data})
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.get_data(as_text=True)}"
    return resp.get_json()


def run():
    tma_api._BOT_TOKEN = _FAKE_BOT_TOKEN
    identity_mod._REGISTRY = dict(_FIXTURE_REGISTRY)
    app = _build_test_app()
    client = app.test_client()

    # ── 1. Sequential scenario exactly as specified: A, B, A, B, A ──
    r1 = _call(client, _USER_A_ID)
    assert r1["user_id"] == "fixture_user_a", r1
    r2 = _call(client, _USER_B_ID)
    assert r2["user_id"] == "fixture_user_b", r2
    r3 = _call(client, _USER_A_ID)
    assert r3["user_id"] == "fixture_user_a", r3
    r4 = _call(client, _USER_B_ID)
    assert r4["user_id"] == "fixture_user_b", r4
    r5 = _call(client, _USER_A_ID)
    assert r5["user_id"] == "fixture_user_a", r5
    print("✅ sequential A→B→A→B→A: each actor got its own identity every time")

    # No identity ever crossed tenant/role boundaries either.
    for r in (r1, r3, r5):
        assert r["tenant_id"] == "fixture_tenant" and r["role"] == identity_mod.Role.OWNER
    for r in (r2, r4):
        assert r["tenant_id"] == "fixture_tenant" and r["role"] == identity_mod.Role.MANAGER
    print("✅ no tenant/role bleed between actors")

    # ── 2. Forced concurrency: many interleaved A/B calls from threads,
    #        barrier-synchronized so both threads are mid-request at once ──
    rounds = 200
    barrier = threading.Barrier(2)
    errors: list[str] = []

    def worker(telegram_user_id: str, expected_user: str):
        try:
            barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            pass
        result = _call(client, telegram_user_id)
        if result["user_id"] != expected_user:
            errors.append(
                f"IDENTITY LEAK: asked for {telegram_user_id}, expected "
                f"{expected_user}, got {result['user_id']}"
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        for i in range(rounds):
            barrier.reset()
            futures = [
                pool.submit(worker, _USER_A_ID, "fixture_user_a"),
                pool.submit(worker, _USER_B_ID, "fixture_user_b"),
            ]
            for f in as_completed(futures):
                f.result()  # re-raise any worker exception immediately

    assert not errors, "\n".join(errors)
    print(f"✅ {rounds} rounds of forced-concurrent A/B calls: zero identity leakage, zero cross-user state")

    print("\nALL CHECKS PASSED — no identity/session/cache leak found between concurrent TMA actors.")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)
