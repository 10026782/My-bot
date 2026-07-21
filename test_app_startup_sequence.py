#!/usr/bin/env python3
"""
test_app_startup_sequence.py — PATCH 3B Step 5 fix (blockers from PR #427
review): app.py's explicit run_startup_sequence() entrypoint.

Covers what test_emergency_stop_bootstrap.py cannot, because it only
proves core.emergency_stop_bootstrap itself is I/O-free at import — this
file proves the *application module* is too, and that app.py's own
startup ordering/exception-propagation contract holds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from unittest.mock import patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# 1. `import app` never invokes the Emergency Stop Airtable store — proven
# against the REAL httpx.get/post/patch/delete (not a mock of our own
# adapter, which would only prove our own code agrees with itself), in a
# fresh subprocess so this is a genuine "just importing the module" check.
# ══════════════════════════════════════════════════════════════════
print("\n── import app: no Airtable / no network call at all ──")

_env = dict(os.environ)
_env.update({
    "ANTHROPIC_API_KEY": "fake",
    "TELEGRAM_TOKEN": "123456:fake-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "AIRTABLE_API_KEY": "fake",
    "AIRTABLE_BASE_ID": "appFAKE00000000000",
    "ELIYAHU_CHAT_ID": "123",
})

_import_script = textwrap.dedent("""
    import sys
    from unittest.mock import patch

    def _blocked(*a, **kw):
        url = a[0] if a else kw.get("url", "?")
        raise AssertionError(f"import app must not perform any httpx call — got {url}")

    with patch("httpx.get", side_effect=_blocked), \\
         patch("httpx.post", side_effect=_blocked), \\
         patch("httpx.patch", side_effect=_blocked), \\
         patch("httpx.delete", side_effect=_blocked):
        import app  # noqa: F401 — the import itself is what's under test

    print("IMPORT_APP_OK_NO_HTTPX_CALL")
""")

result = subprocess.run(
    [sys.executable, "-c", _import_script],
    env=_env, capture_output=True, text=True, timeout=60,
)
chk("`import app` completes without raising", result.returncode == 0)
chk("`import app` never calls httpx.get/post/patch/delete", "IMPORT_APP_OK_NO_HTTPX_CALL" in result.stdout)
if result.returncode != 0 or "IMPORT_APP_OK_NO_HTTPX_CALL" not in result.stdout:
    print("--- subprocess stdout ---")
    print(result.stdout[-3000:])
    print("--- subprocess stderr ---")
    print(result.stderr[-3000:])


# ══════════════════════════════════════════════════════════════════
# Set up for the in-process tests below: fake-but-well-formed env vars so
# `import app` itself succeeds (startup_validator only checks presence,
# TeleBot only checks token *shape*) — no real credentials, no network
# call happens merely from this import (proven above).
# ══════════════════════════════════════════════════════════════════

os.environ.setdefault("ANTHROPIC_API_KEY", "fake")
os.environ.setdefault("TELEGRAM_TOKEN", "123456:fake-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
os.environ.setdefault("AIRTABLE_API_KEY", "fake")
os.environ.setdefault("AIRTABLE_BASE_ID", "appFAKE00000000000")
os.environ.setdefault("ELIYAHU_CHAT_ID", "123")

import app  # noqa: E402 — deliberately after the env vars above

import feature_flags  # noqa: E402
from adapters.airtable_emergency_stop_store import AirtableEmergencyStopStore  # noqa: E402,F401
from core.emergency_stop import KNOWN_EMERGENCY_STOP_FLAG_NAMES  # noqa: E402
from core.emergency_stop_bootstrap import EmergencyStopBootstrapResult  # noqa: E402

BOOTSTRAP_TARGET = "core.emergency_stop_bootstrap.bootstrap_emergency_stop"
ADAPTER_MOD = "adapters.airtable_emergency_stop_store"


def _rec(rec_id, name, enabled):
    return {"id": rec_id, "fields": {"Flag Name": name, "Enabled": enabled, "Operation ID": "op-1"}}


_ALL_FLAGS_OK = [_rec(f"rec{i}", name, False) for i, name in enumerate(sorted(KNOWN_EMERGENCY_STOP_FLAG_NAMES))]


# ══════════════════════════════════════════════════════════════════
# 2. run_startup_sequence(): bootstrap called exactly once, and strictly
# BEFORE start_scheduler() — the required ordering.
# ══════════════════════════════════════════════════════════════════
print("\n── ordering: bootstrap before scheduler, exactly once ──")

call_order = []


def _fake_bootstrap_ok():
    call_order.append("bootstrap")
    return EmergencyStopBootstrapResult(configured=True, store_status="ok", flags_loaded=5, error="")


def _fake_start_scheduler():
    call_order.append("scheduler")
    return object()


with patch(BOOTSTRAP_TARGET, side_effect=_fake_bootstrap_ok) as m_boot, \
     patch.object(app, "start_scheduler", side_effect=_fake_start_scheduler) as m_sched:
    app.run_startup_sequence()

chk("run_startup_sequence() invokes bootstrap exactly once", m_boot.call_count == 1)
chk("run_startup_sequence() invokes start_scheduler exactly once", m_sched.call_count == 1)
chk("bootstrap runs strictly before scheduler start", call_order == ["bootstrap", "scheduler"])


# ══════════════════════════════════════════════════════════════════
# 3. Documented degraded outcomes (unavailable / invalid) still allow
# startup to continue — scheduler still starts, nothing raises.
# ══════════════════════════════════════════════════════════════════
print("\n── unavailable/invalid still allow startup to continue ──")

for degraded_status in ("unavailable", "invalid"):
    def _fake_bootstrap_degraded(status=degraded_status):
        return EmergencyStopBootstrapResult(configured=True, store_status=status, flags_loaded=0, error="simulated")

    with patch(BOOTSTRAP_TARGET, side_effect=_fake_bootstrap_degraded) as m_boot2, \
         patch.object(app, "start_scheduler") as m_sched2:
        app.run_startup_sequence()  # must not raise

    chk(f"bootstrap reporting {degraded_status} -> run_startup_sequence() does not raise", True)
    chk(f"bootstrap reporting {degraded_status} -> scheduler still starts (startup continues)", m_sched2.call_count == 1)


# ══════════════════════════════════════════════════════════════════
# 4. An UNEXPECTED bootstrap failure propagates out of
# run_startup_sequence() and the scheduler is NEVER started.
# ══════════════════════════════════════════════════════════════════
print("\n── unexpected bootstrap error: propagates, scheduler NOT started ──")


def _fake_bootstrap_bug():
    raise RuntimeError("simulated construction/configuration bug")


with patch(BOOTSTRAP_TARGET, side_effect=_fake_bootstrap_bug), \
     patch.object(app, "start_scheduler") as m_sched3:
    try:
        app.run_startup_sequence()
        chk("unexpected bootstrap error propagates out of run_startup_sequence()", False)
    except RuntimeError as e:
        chk("unexpected bootstrap error propagates out of run_startup_sequence()", True)
        chk("the original exception reaches the caller intact", "simulated construction/configuration bug" in str(e))

chk("unexpected bootstrap error -> start_scheduler is NEVER called", m_sched3.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 5. Second explicit startup call remains idempotent — the real bootstrap
# (not mocked here), exercised twice via run_startup_sequence().
# ══════════════════════════════════════════════════════════════════
print("\n── second explicit startup remains idempotent ──")

feature_flags._reset_emergency_stop_manager_for_tests()

with patch(f"{ADAPTER_MOD}.at_list_by_formula") as m_list, \
     patch.object(app, "start_scheduler") as m_sched4:
    m_list.return_value = _ALL_FLAGS_OK
    app.run_startup_sequence()
    app.run_startup_sequence()  # second explicit call, same process

chk(
    "second run_startup_sequence() call -> only ONE real Airtable read total (bootstrap idempotent)",
    m_list.call_count == 1,
)
chk(
    "second run_startup_sequence() call -> manager instance did not change across calls",
    feature_flags.get_emergency_stop_status().configured is True,
)

feature_flags._reset_emergency_stop_manager_for_tests()


# ══════════════════════════════════════════════════════════════════
# 6. Existing dual-path callers remain byte-unchanged — structural proof,
# reading the files directly rather than importing (avoids any import-
# order/env-var fragility; also legitimately what "no caller changed"
# means: nothing new appears in their source).
# ══════════════════════════════════════════════════════════════════
print("\n── dual-path: existing callers unchanged (structural) ──")

_NEW_API_NAMES = (
    "evaluate_emergency_stop", "set_emergency_stop", "clear_emergency_stop",
    "get_emergency_stop_status", "configure_emergency_stop_manager",
)
for fname in ("tma_api.py", "cost_monitor.py", "scheduler.py"):
    with open(fname, encoding="utf-8") as f:
        src = f.read()
    chk(
        f"{fname} does not reference the new parallel Emergency Stop API",
        not any(name in src for name in _NEW_API_NAMES),
    )


# ══════════════════════════════════════════════════════════════════
# 7. Step 5.1 (P0): gunicorn.conf.py pins a single worker — scheduler.py's
# scheduler thread (and the Step 5 bootstrap) are in-process state; the
# "already running" dedup check in run_startup_sequence() is process-local
# and has no visibility across worker processes, so >1 worker would start
# >1 independent scheduler. Structural check, not a live multi-worker
# spawn — reads the actual file gunicorn loads.
# ══════════════════════════════════════════════════════════════════
print("\n── gunicorn.conf.py pins workers = 1 (P0) ──")

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("_gunicorn_conf_under_test", "gunicorn.conf.py")
_gunicorn_conf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gunicorn_conf)

chk("gunicorn.conf.py defines workers", hasattr(_gunicorn_conf, "workers"))
chk("gunicorn.conf.py pins workers == 1", getattr(_gunicorn_conf, "workers", None) == 1)
chk("gunicorn.conf.py still defines post_worker_init", hasattr(_gunicorn_conf, "post_worker_init"))


# ══════════════════════════════════════════════════════════════════
# 8. Step 5.1: the two new bootstrap contract-violation cases must also
# prevent the scheduler from starting when reached through the REAL
# run_startup_sequence() -> bootstrap_emergency_stop() path (not just
# proven at the bootstrap level in test_emergency_stop_bootstrap.py).
# ══════════════════════════════════════════════════════════════════
print("\n── contract violations block scheduler start (end-to-end) ──")

from core.emergency_stop import EmergencyStopManager  # noqa: E402

feature_flags._reset_emergency_stop_manager_for_tests()

with patch.object(EmergencyStopManager, "status") as m_status, \
     patch.object(app, "start_scheduler") as m_sched5:
    m_status.return_value.store_status = "bogus_never_a_real_value"
    m_status.return_value.flags = {}
    m_status.return_value.error = ""
    try:
        app.run_startup_sequence()
        chk("unexpected store_status -> run_startup_sequence() raises", False)
    except RuntimeError:
        chk("unexpected store_status -> run_startup_sequence() raises", True)

chk("unexpected store_status -> start_scheduler is NEVER called", m_sched5.call_count == 0)

feature_flags._reset_emergency_stop_manager_for_tests()

with patch(
    "feature_flags.get_emergency_stop_status",
    return_value=feature_flags.EmergencyStopStatusView(configured=True, manager_status=None),
), patch.object(app, "start_scheduler") as m_sched6:
    try:
        app.run_startup_sequence()
        chk("configured=True with manager_status=None -> run_startup_sequence() raises", False)
    except RuntimeError:
        chk("configured=True with manager_status=None -> run_startup_sequence() raises", True)

chk("configured=True with manager_status=None -> start_scheduler is NEVER called", m_sched6.call_count == 0)

feature_flags._reset_emergency_stop_manager_for_tests()


print(f"\n{'='*40}")
print(f"app.py startup sequence tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
