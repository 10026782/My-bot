#!/usr/bin/env python3
"""
test_feature_flags_cutover.py — PATCH 3B Step 6 (atomic emergency-stop cutover)

End-to-end coverage that doesn't naturally belong in any single existing
file: the dynamic set_flag() call-site structural scan, the removed /tmp
mechanism's absence, durable-survives-restart, the full set->status->clear
operation_id round trip (incl. conflict), dispatcher/scheduler integration
through the real durable manager, cost_monitor's retry-on-failed-write
behavior, and the tma_api stop/clear HTTP endpoints (Flask test client).

Per-file unit coverage for the pieces this file assembles lives elsewhere:
  - core/emergency_stop.py, adapters/airtable_emergency_stop_store.py:
    test_core_emergency_stop.py, test_airtable_emergency_stop_store.py
  - feature_flags.py Step 3 API + is_enabled()/set_flag() cutover:
    test_feature_flags_emergency_stop_step3.py
  - app.py bootstrap/startup ordering: test_emergency_stop_bootstrap.py,
    test_app_startup_sequence.py
"""

from __future__ import annotations

import ast
import glob
import sys
import uuid

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


import feature_flags  # noqa: E402
from core.emergency_stop import (  # noqa: E402
    KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    EmergencyStopManager,
    FlagRecord,
    ReadResult,
    WriteResult,
)


class FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class StatefulFakeStore:
    """
    A stateful EmergencyStopStore double that behaves like a real durable
    store across multiple read()/write() calls — necessary for end-to-end
    set -> status -> clear flows, where write() invalidates the manager's
    cache and the NEXT read must reflect the NEW state (including the NEW
    operation_id), and for the expected_operation_id CAS check, which
    compares against whatever this store currently holds. Mirrors
    adapters/airtable_emergency_stop_store.py's real CAS semantics closely
    enough for feature_flags/manager-level tests without touching Airtable.
    """

    def __init__(self, initial: dict[str, FlagRecord] | None = None):
        self._records: dict[str, FlagRecord] = dict(initial or {
            name: FlagRecord(enabled=False, operation_id=None)
            for name in KNOWN_EMERGENCY_STOP_FLAG_NAMES
        })
        self.read_calls = 0
        self.write_calls: list[tuple] = []

    def read(self) -> ReadResult:
        self.read_calls += 1
        return ReadResult(status="ok", flags=dict(self._records))

    def write(self, flag_name, enabled, *, operation_id, updated_by, source,
              reason, expected_operation_id=None) -> WriteResult:
        self.write_calls.append((flag_name, enabled, operation_id, expected_operation_id))
        current = self._records.get(flag_name)
        if expected_operation_id is not None and current is not None \
                and current.operation_id != expected_operation_id:
            return WriteResult(
                ok=False, verified=False, conflict=True,
                error=f"expected_operation_id={expected_operation_id!r} but record has "
                      f"{current.operation_id!r}",
            )
        self._records[flag_name] = FlagRecord(enabled=enabled, operation_id=operation_id)
        return WriteResult(ok=True, verified=True)


def _configure(store) -> EmergencyStopManager:
    feature_flags._reset_emergency_stop_manager_for_tests()
    mgr = EmergencyStopManager(store=store, clock=FakeClock(), ttl_seconds=7.0)
    feature_flags.configure_emergency_stop_manager(mgr)
    return mgr


# ══════════════════════════════════════════════════════════════════
# 1. Structural: no production set_flag() call site can write an
# EMERGENCY_STOP_* name — including a DYNAMICALLY computed name, not just
# a string literal a plain grep would catch. (Runtime already hard-blocks
# this via EmergencyStopLegacyWriteBlocked; this proves no code even
# attempts it anymore, e.g. the tma_api.py f"EMERGENCY_{action.upper()}"
# pattern this cutover specifically removed.)
# ══════════════════════════════════════════════════════════════════
print("\n── structural: no production set_flag() writer of an emergency name ──")

_EXCLUDE_FILES = {
    "feature_flags.py",             # set_flag()'s own definition
    "emergency_stop_test_support.py",
}


def _iter_production_py_files():
    for path in glob.glob("**/*.py", recursive=True):
        base = path.split("/")[-1]
        if base.startswith("test_") or base in _EXCLUDE_FILES:
            continue
        if "/tests/" in path or path.startswith("tests/"):
            continue
        yield path


_dynamic_set_flag_sites: list[str] = []
_literal_emergency_set_flag_sites: list[str] = []

for _path in _iter_production_py_files():
    try:
        with open(_path, encoding="utf-8") as f:
            _src = f.read()
        _tree = ast.parse(_src, filename=_path)
    except (SyntaxError, UnicodeDecodeError):
        continue

    for _node in ast.walk(_tree):
        if not isinstance(_node, ast.Call):
            continue
        _func = _node.func
        _func_name = _func.id if isinstance(_func, ast.Name) else (
            _func.attr if isinstance(_func, ast.Attribute) else None
        )
        if _func_name != "set_flag":
            continue
        if not _node.args:
            continue
        _first_arg = _node.args[0]
        if isinstance(_first_arg, ast.Constant) and isinstance(_first_arg.value, str):
            if _first_arg.value in KNOWN_EMERGENCY_STOP_FLAG_NAMES:
                _literal_emergency_set_flag_sites.append(f"{_path}:{_node.lineno}")
            # a literal that is NOT an emergency name is a legitimate,
            # ordinary feature flag — not our concern here.
        else:
            # Non-literal first argument -> cannot be proven safe by static
            # analysis. After this cutover, no production code has any
            # legitimate reason to compute a set_flag() name dynamically —
            # this is exactly the shape the old tma_api.py
            # f"EMERGENCY_{action.upper()}" bug had.
            _dynamic_set_flag_sites.append(f"{_path}:{_node.lineno}")

chk(
    "no production set_flag() call site uses an EMERGENCY_STOP_* string literal",
    _literal_emergency_set_flag_sites == [],
)
chk(
    "no production set_flag() call site uses a dynamically-computed flag name",
    _dynamic_set_flag_sites == [],
)
if _literal_emergency_set_flag_sites or _dynamic_set_flag_sites:
    print(f"    literal emergency sites: {_literal_emergency_set_flag_sites}")
    print(f"    dynamic sites: {_dynamic_set_flag_sites}")


# ══════════════════════════════════════════════════════════════════
# 2. Structural: zero code references to the removed /tmp mechanism —
# AST string-literal scan (not grep), so explanatory comments/docstrings
# about the REMOVAL (which legitimately mention the old path in prose)
# don't false-positive; only an actual string literal used BY CODE would.
# ══════════════════════════════════════════════════════════════════
print("\n── structural: zero code references to emergency_flags.json ──")

_bad_literal_sites: list[str] = []
for _path in glob.glob("**/*.py", recursive=True):
    # Exclude this file itself — its own description/error-reporting
    # strings necessarily quote the target path in prose (see this
    # section's chk() calls above/below), which is not a real usage the
    # check is trying to catch.
    if _path.split("/")[-1] == "test_feature_flags_cutover.py":
        continue
    try:
        with open(_path, encoding="utf-8") as f:
            _src = f.read()
        _tree = ast.parse(_src, filename=_path)
    except (SyntaxError, UnicodeDecodeError):
        continue
    for _node in ast.walk(_tree):
        if isinstance(_node, ast.Constant) and isinstance(_node.value, str):
            if "emergency_flags.json" in _node.value:
                _bad_literal_sites.append(f"{_path}:{_node.lineno}")

chk(
    "no .py file contains '/tmp/emergency_flags.json' as an actual string literal",
    _bad_literal_sites == [],
)
if _bad_literal_sites:
    print(f"    sites: {_bad_literal_sites}")

chk(
    "feature_flags module no longer defines _load_persistent",
    not hasattr(feature_flags, "_load_persistent"),
)
chk(
    "feature_flags module no longer defines _save_persistent",
    not hasattr(feature_flags, "_save_persistent"),
)
chk(
    "feature_flags module no longer defines _PERSIST_PATH",
    not hasattr(feature_flags, "_PERSIST_PATH"),
)
chk(
    "feature_flags module no longer defines _PERSISTENT_FLAG_NAMES",
    not hasattr(feature_flags, "_PERSISTENT_FLAG_NAMES"),
)


# ══════════════════════════════════════════════════════════════════
# 2.5. _env_force_stop_provider() itself — production-shaped tests, not
# just the generic force_stop_provider mechanism (already covered via a
# throwaway lambda in test_core_emergency_stop.py's "env force-stop
# precedence" section). Only the literal "true" forces a stop; false/
# missing never cancel a durable stop; never calls is_enabled() (would be
# circular post-cutover).
# ══════════════════════════════════════════════════════════════════
print("\n── _env_force_stop_provider() — production-shaped env precedence ──")

import os as _os  # noqa: E402

_ENV_FLAG = "EMERGENCY_STOP_WHATSAPP"
_missing = object()
_old_env_val = _os.environ.pop(_ENV_FLAG, _missing)
try:
    for _raw, _expected in (
        ("true", True), ("TRUE", True), (" True ", True),
        ("false", False), ("1", False), ("yes", False), ("on", False),
        ("", False),
    ):
        _os.environ[_ENV_FLAG] = _raw
        _got = feature_flags._env_force_stop_provider(_ENV_FLAG)
        chk(f"_env_force_stop_provider() with env={_raw!r} -> {_expected}", _got is _expected)

    _os.environ.pop(_ENV_FLAG, None)
    chk(
        "_env_force_stop_provider() with the env var entirely unset -> False",
        feature_flags._env_force_stop_provider(_ENV_FLAG) is False,
    )
finally:
    if _old_env_val is not _missing:
        _os.environ[_ENV_FLAG] = _old_env_val
    else:
        _os.environ.pop(_ENV_FLAG, None)

import inspect as _inspect  # noqa: E402
_provider_src = _inspect.getsource(feature_flags._env_force_stop_provider)
_provider_tree = ast.parse(_provider_src)
_provider_calls = {
    _n.func.id if isinstance(_n.func, ast.Name) else getattr(_n.func, "attr", None)
    for _n in ast.walk(_provider_tree) if isinstance(_n, ast.Call)
}
chk(
    # AST-based (not a raw substring match on source text) — the
    # docstring itself explains, in prose, why this deliberately doesn't
    # call is_enabled(), which would otherwise false-positive a plain
    # substring check.
    "_env_force_stop_provider() never actually CALLS is_enabled() (would be circular)",
    "is_enabled" not in _provider_calls,
)

# Integration: env force-stop wins over a durable False, through the REAL
# provider (not a lambda), via the standard manager precedence contract.
_os.environ[_ENV_FLAG] = "true"
try:
    store2_5 = StatefulFakeStore(initial={
        name: FlagRecord(enabled=False, operation_id="op-2.5") for name in KNOWN_EMERGENCY_STOP_FLAG_NAMES
    })
    feature_flags._reset_emergency_stop_manager_for_tests()
    mgr2_5 = EmergencyStopManager(
        store=store2_5, clock=FakeClock(), ttl_seconds=7.0,
        force_stop_provider=feature_flags._env_force_stop_provider,
    )
    feature_flags.configure_emergency_stop_manager(mgr2_5)
    ev2_5 = feature_flags.evaluate_emergency_stop(_ENV_FLAG)
    chk(
        "real _env_force_stop_provider wired into a manager -> env wins over durable False",
        ev2_5.blocked is True and ev2_5.source == "env",
    )
finally:
    _os.environ.pop(_ENV_FLAG, None)
    feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 3. Durable True survives a "restart" — a fresh manager backed by the
# SAME durable store (simulating a process restart against durable
# Airtable state, not an in-process cache) immediately reflects a prior
# write, with no stale/cleared state.
# ══════════════════════════════════════════════════════════════════
print("\n── durable state survives restart/bootstrap ──")

_shared_store = StatefulFakeStore()
mgr_before_restart = _configure(_shared_store)
write_result = mgr_before_restart.write(
    "EMERGENCY_STOP_ALL", True,
    operation_id="op-restart-1", updated_by="owner", source="test", reason="pre-restart",
)
chk("pre-restart write succeeds", write_result.ok and write_result.verified)

# Simulate a restart: brand-new manager instance, but the SAME backing
# store (the durable Airtable table would genuinely still hold this state
# after a real Render restart — only the in-process manager is new).
feature_flags._reset_emergency_stop_manager_for_tests()
mgr_after_restart = EmergencyStopManager(store=_shared_store, clock=FakeClock(), ttl_seconds=7.0)
feature_flags.configure_emergency_stop_manager(mgr_after_restart)

ev_after_restart = feature_flags.evaluate_emergency_stop("EMERGENCY_STOP_ALL")
chk("fresh manager after 'restart' -> blocked=True (durable, not process-local)", ev_after_restart.blocked is True)
chk("fresh manager after 'restart' -> source=durable", ev_after_restart.source == "durable")
chk("fresh manager after 'restart' -> operation_id carried over", ev_after_restart.operation_id == "op-restart-1")

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 4. set -> status exposes operation_id -> clear with matching ID succeeds;
# a stale/mismatched operation_id is rejected as a conflict, no write
# applied.
# ══════════════════════════════════════════════════════════════════
print("\n── set -> status exposes operation_id -> clear round trip ──")

store4 = StatefulFakeStore()
_configure(store4)

set_result = feature_flags.set_emergency_stop(
    "EMERGENCY_STOP_WHATSAPP", True,
    operation_id="op-4-a", updated_by="owner", source="test", reason="test set",
)
chk("set_emergency_stop() -> ok+verified", set_result.ok and set_result.verified)

status4 = feature_flags.get_emergency_stop_status()
observed_op_id = status4.manager_status.flags["EMERGENCY_STOP_WHATSAPP"].operation_id
chk("get_emergency_stop_status() exposes the operation_id just written", observed_op_id == "op-4-a")

clear_ok = feature_flags.clear_emergency_stop(
    "EMERGENCY_STOP_WHATSAPP",
    operation_id="op-4-b", updated_by="owner", source="test", reason="test clear",
    expected_operation_id=observed_op_id,
)
chk("clear with the matching observed operation_id -> succeeds", clear_ok.write.ok and clear_ok.write.verified)
chk("clear with the matching operation_id -> no conflict", clear_ok.write.conflict is False)

# Now the durable op-id is "op-4-b" (from the successful clear above). A
# clear using the STALE "op-4-a" must be rejected as a conflict.
stale_clear = feature_flags.clear_emergency_stop(
    "EMERGENCY_STOP_WHATSAPP",
    operation_id="op-4-c", updated_by="owner", source="test", reason="stale clear attempt",
    expected_operation_id="op-4-a",  # stale — the real current value is op-4-b
)
chk("clear with a STALE operation_id -> conflict=True", stale_clear.write.conflict is True)
chk("clear with a STALE operation_id -> ok=False (write rejected)", stale_clear.write.ok is False)
chk(
    "clear with a STALE operation_id -> the store's durable record is unchanged",
    store4._records["EMERGENCY_STOP_WHATSAPP"].operation_id == "op-4-b",
)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 5. dispatcher.py / scheduler.py integration through the REAL durable
# manager (not just is_enabled() unit-level) — proving the cutover didn't
# silently break the two most safety-critical read callers.
# ══════════════════════════════════════════════════════════════════
print("\n── dispatcher/scheduler integration through the durable manager ──")

import tools.dispatcher as _dispatcher_mod  # noqa: E402
from identity import Identity, Role  # noqa: E402

store5 = StatefulFakeStore(initial={
    "EMERGENCY_STOP_ALL": FlagRecord(enabled=True, operation_id="op-5"),
    "EMERGENCY_STOP_WHATSAPP": FlagRecord(enabled=False, operation_id="op-5"),
    "EMERGENCY_STOP_EMAIL": FlagRecord(enabled=False, operation_id="op-5"),
    "EMERGENCY_STOP_AUTOMATION": FlagRecord(enabled=False, operation_id="op-5"),
    "EMERGENCY_STOP_AI": FlagRecord(enabled=False, operation_id="op-5"),
})
_configure(store5)

owner_identity = Identity(user_id="t1", role=Role.OWNER)
dispatch_result = _dispatcher_mod.dispatch_tool("gmail_send_draft", {}, owner_identity)
chk(
    "dispatch_tool() on a blocked_by_emergency tool -> emergency-blocked message, "
    "durable EMERGENCY_STOP_ALL=True honored end-to-end",
    isinstance(dispatch_result, str) and "חירום" in dispatch_result,
)

feature_flags._reset_emergency_stop_manager_for_tests()

store5b = StatefulFakeStore(initial={
    name: FlagRecord(enabled=(name == "EMERGENCY_STOP_AUTOMATION"), operation_id="op-5b")
    for name in KNOWN_EMERGENCY_STOP_FLAG_NAMES
})
_configure(store5b)

import scheduler as _scheduler_mod  # noqa: E402

_job_called = []
def _fake_job():
    _job_called.append(True)

guarded = _scheduler_mod._automation_guard(_fake_job, name="fake_job_for_test")
result5b = guarded()
chk("scheduler._automation_guard() skips the job when EMERGENCY_STOP_AUTOMATION is durably True", _job_called == [])
chk("scheduler._automation_guard() returns None when skipped", result5b is None)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 6. cost_monitor.py: a failed/unverified durable write reverts
# _daily_stopped to False (retried on the next check_thresholds() call)
# instead of silently giving up, and never claims "AI stopped" for a
# write that didn't actually stick.
# ══════════════════════════════════════════════════════════════════
print("\n── cost_monitor retries after a failed/unverified write ──")

import cost_monitor  # noqa: E402


class _FailingWriteStore:
    def read(self) -> ReadResult:
        return ReadResult(status="ok", flags={
            name: FlagRecord(enabled=False) for name in KNOWN_EMERGENCY_STOP_FLAG_NAMES
        })

    def write(self, *a, **kw) -> WriteResult:
        return WriteResult(ok=False, verified=False, error="simulated durable write failure")


_configure(_FailingWriteStore())

_notify_calls = []
_orig_send_owner_message = cost_monitor._send_owner_message
cost_monitor._send_owner_message = lambda text: _notify_calls.append(text)

cost_monitor._daily_stopped = False
try:
    cost_monitor._trigger_daily_stop(999.0)
    chk(
        "failed/unverified durable write -> _daily_stopped reverts to False (will retry)",
        cost_monitor._daily_stopped is False,
    )
    chk(
        "failed/unverified durable write -> owner is NOT told AI stopped",
        _notify_calls == [],
    )
finally:
    cost_monitor._send_owner_message = _orig_send_owner_message
    cost_monitor._daily_stopped = False

feature_flags._reset_emergency_stop_manager_for_tests()

# Contrast: a successful ok+verified write DOES notify and stays stopped.
_configure(StatefulFakeStore())
_notify_calls2 = []
cost_monitor._send_owner_message = lambda text: _notify_calls2.append(text)
cost_monitor._daily_stopped = False
try:
    cost_monitor._trigger_daily_stop(999.0)
    chk("successful ok+verified write -> _daily_stopped stays True", cost_monitor._daily_stopped is True)
    chk("successful ok+verified write -> owner IS notified", len(_notify_calls2) == 1)
    chk("successful notification does not reference the removed /flag command", "/flag" not in _notify_calls2[0])
finally:
    cost_monitor._send_owner_message = _orig_send_owner_message
    cost_monitor._daily_stopped = False

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 7. tma_api.py stop/clear HTTP endpoints — real Flask test client
# (mirrors test_tma_projects_read_path_optimization.py's pattern).
# ══════════════════════════════════════════════════════════════════
print("\n── tma_api.py stop/clear endpoints (Flask test client) ──")

import tma_api  # noqa: E402
from flask import Flask  # noqa: E402


def _make_client():
    flask_app = Flask(__name__)
    flask_app.register_blueprint(tma_api.tma_api)
    return flask_app.test_client()


class _RouteIdentity:
    role = Role.OWNER
    is_owner = True
    user_id = "owner-1"
    display_name = "Test Owner"


_client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}
_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity
tma_api._validate_initdata = lambda s: {"id": "owner-1"}
tma_api.resolve_identity = lambda ch, tid: _RouteIdentity()
_orig_notify = tma_api._notify_owner
_orig_audit = tma_api._audit
tma_api._notify_owner = lambda text: None
tma_api._audit = lambda *a, **kw: None

try:
    # ── GET /api/health: emergency_flags shape ──
    _configure(StatefulFakeStore())
    resp = _client.get("/api/health", headers=_HDR)
    body = resp.get_json()
    chk("GET /api/health -> 200", resp.status_code == 200)
    chk(
        "GET /api/health -> emergency_flags covers all 5 canonical flags",
        set(body["emergency_flags"]) == KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    )
    chk(
        "GET /api/health -> each flag entry has enabled+operation_id",
        all({"enabled", "operation_id"} <= set(v) for v in body["emergency_flags"].values()),
    )

    # ── POST stop: unknown action -> 400 ──
    resp = _client.post("/api/health/emergency", json={"action": "bogus"}, headers=_HDR)
    chk("POST stop with unknown action -> 400", resp.status_code == 400)

    # ── POST stop: success path, operation_id returned ──
    _configure(StatefulFakeStore())
    resp = _client.post("/api/health/emergency", json={"action": "stop_ai"}, headers=_HDR)
    body = resp.get_json()
    chk("POST stop_ai -> 200", resp.status_code == 200)
    chk("POST stop_ai -> ok=True", body.get("ok") is True)
    chk("POST stop_ai -> operation_id present", bool(body.get("operation_id")))
    chk("POST stop_ai -> flag=EMERGENCY_STOP_AI", body.get("flag") == "EMERGENCY_STOP_AI")

    # ── POST stop: ok=True but verified=False must NOT be reported as success ──
    class _UnverifiedWriteStore:
        def read(self) -> ReadResult:
            return ReadResult(status="ok", flags={
                name: FlagRecord(enabled=False) for name in KNOWN_EMERGENCY_STOP_FLAG_NAMES
            })

        def write(self, *a, **kw) -> WriteResult:
            return WriteResult(ok=True, verified=False, error="readback mismatch")

    _configure(_UnverifiedWriteStore())
    resp = _client.post("/api/health/emergency", json={"action": "stop_all"}, headers=_HDR)
    body = resp.get_json()
    chk("POST stop with ok=True/verified=False -> NOT 200", resp.status_code != 200)
    chk("POST stop with ok=True/verified=False -> ok=False in body (never a false 'stopped' claim)",
        body.get("ok") is False)

    # ── POST clear: missing expected_operation_id -> 400 ──
    _configure(StatefulFakeStore())
    resp = _client.post("/api/health/emergency/clear", json={"action": "clear_all"}, headers=_HDR)
    chk("POST clear with no expected_operation_id -> 400", resp.status_code == 400)

    # ── POST clear: unknown action -> 400 ──
    resp = _client.post(
        "/api/health/emergency/clear",
        json={"action": "bogus", "expected_operation_id": "x"}, headers=_HDR,
    )
    chk("POST clear with unknown action -> 400", resp.status_code == 400)

    # ── POST clear: stale operation_id -> 409, no write applied ──
    store7 = StatefulFakeStore(initial={
        "EMERGENCY_STOP_ALL": FlagRecord(enabled=True, operation_id="op-real"),
        **{n: FlagRecord(enabled=False, operation_id="op-real")
           for n in KNOWN_EMERGENCY_STOP_FLAG_NAMES if n != "EMERGENCY_STOP_ALL"},
    })
    _configure(store7)
    resp = _client.post(
        "/api/health/emergency/clear",
        json={"action": "clear_all", "expected_operation_id": "op-stale"}, headers=_HDR,
    )
    body = resp.get_json()
    chk("POST clear with a stale operation_id -> 409", resp.status_code == 409)
    chk("POST clear 409 -> conflict flagged in body", body.get("conflict") is True)
    chk(
        "POST clear 409 -> the durable record is genuinely unchanged",
        store7._records["EMERGENCY_STOP_ALL"].enabled is True,
    )

    # ── clear_ai end-to-end: GET health -> extract operation_id -> POST clear_ai ──
    store8 = StatefulFakeStore(initial={
        "EMERGENCY_STOP_AI": FlagRecord(enabled=True, operation_id="op-ai-1"),
        **{n: FlagRecord(enabled=False, operation_id="op-ai-1")
           for n in KNOWN_EMERGENCY_STOP_FLAG_NAMES if n != "EMERGENCY_STOP_AI"},
    })
    _configure(store8)
    health_resp = _client.get("/api/health", headers=_HDR)
    ai_op_id = health_resp.get_json()["emergency_flags"]["EMERGENCY_STOP_AI"]["operation_id"]
    chk("clear_ai e2e: GET /api/health exposes EMERGENCY_STOP_AI's operation_id", ai_op_id == "op-ai-1")

    clear_resp = _client.post(
        "/api/health/emergency/clear",
        json={"action": "clear_ai", "expected_operation_id": ai_op_id}, headers=_HDR,
    )
    clear_body = clear_resp.get_json()
    chk("clear_ai e2e: POST clear -> 200", clear_resp.status_code == 200)
    chk("clear_ai e2e: POST clear -> ok=True", clear_body.get("ok") is True)
    chk("clear_ai e2e: POST clear -> flag=EMERGENCY_STOP_AI", clear_body.get("flag") == "EMERGENCY_STOP_AI")
    chk(
        "clear_ai e2e: durable record now reads enabled=False",
        store8._records["EMERGENCY_STOP_AI"].enabled is False,
    )
    chk(
        "clear_ai e2e: not still_blocked_by_env (no env override set)",
        clear_body.get("still_blocked_by_env") is False,
    )

    # ── POST clear: ok=True but verified=False must NOT be reported as success ──
    class _UnverifiedClearStore:
        def read(self) -> ReadResult:
            return ReadResult(status="ok", flags={
                "EMERGENCY_STOP_ALL": FlagRecord(enabled=True, operation_id="op-x"),
                **{n: FlagRecord(enabled=False, operation_id="op-x")
                   for n in KNOWN_EMERGENCY_STOP_FLAG_NAMES if n != "EMERGENCY_STOP_ALL"},
            })

        def write(self, *a, **kw) -> WriteResult:
            return WriteResult(ok=True, verified=False, error="readback mismatch")

    _configure(_UnverifiedClearStore())
    resp = _client.post(
        "/api/health/emergency/clear",
        json={"action": "clear_all", "expected_operation_id": "op-x"}, headers=_HDR,
    )
    body = resp.get_json()
    chk("POST clear with ok=True/verified=False -> NOT 200", resp.status_code != 200)
    chk("POST clear with ok=True/verified=False -> ok=False in body (never a false 'cleared' claim)",
        body.get("ok") is False)

finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve
    tma_api._notify_owner = _orig_notify
    tma_api._audit = _orig_audit
    feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"feature_flags/tma_api Step 6 cutover tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
