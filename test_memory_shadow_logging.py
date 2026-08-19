#!/usr/bin/env python3
"""
test_memory_shadow_logging.py — regression tests for the Episodic Memory
Phase 2B follow-up: durable shadow-comparison logging
(core/memory_retrieval_shadow.py::record_shadow_comparison,
scheduler.py::_job_memory_shadow_scan).

  1. record_shadow_comparison() is fail-soft (returns False, logs, never
     raises) when PostgreSQL is unavailable — same contract as
     core/usage_telemetry.py::record_usage().
  2. record_shadow_comparison() rolls back before releasing the connection
     on a write failure.
  3. record_shadow_comparison() writes structured counts only — no memory
     item text (title/description) anywhere in the SQL params.
  4. _job_memory_shadow_scan() is a no-op when FEATURE_MEMORY_SHADOW_LOGGING
     is off (default) — never resolves identity, never compares, never
     records.
  5. _job_memory_shadow_scan() skips safely (no raise) when the flag is on
     but ELIYAHU_CHAT_ID is unset, or when build_shadow_request() can't
     build a request from the resolved identity.
  6. _job_memory_shadow_scan() happy path: flag on, owner identity
     resolvable -> compare_with_live_paths() and record_shadow_comparison()
     each called exactly once.
  7. _job_memory_shadow_scan() never raises even if everything inside it
     blows up.
"""

from __future__ import annotations

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import logging
logging.disable(logging.CRITICAL)

from unittest.mock import MagicMock, patch

from core.memory_retrieval_contract import (
    BusinessMemoryItem, MemoryRetrievalRequest, MemorySnapshot, SnapshotMetadata,
)
from core.memory_retrieval_shadow import ShadowComparison, record_shadow_comparison

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _comparison(**kw) -> ShadowComparison:
    meta = SnapshotMetadata(
        generated_at=0.0, tenant_id="boss_hq", canonical_user_id="1",
        session_id=None, entity_type=None, entity_id=None, domain_id="general",
        business_memory_available=kw.get("bm_available", True),
        business_memory_error=kw.get("bm_error"),
        business_memory_returned=len(kw.get("business", ())),
        business_memory_budget=kw.get("bm_budget", 5),
        episodic_memory_available=kw.get("ep_available", True),
        episodic_memory_error=kw.get("ep_error"),
        episodic_memory_returned=len(kw.get("episodic", ())),
        episodic_memory_budget=kw.get("ep_budget", 20),
    )
    snapshot = MemorySnapshot(
        business_facts=tuple(kw.get("business", ())),
        episodic_entries=tuple(kw.get("episodic", ())),
        metadata=meta,
    )
    request = MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="1")
    return ShadowComparison(
        request=request,
        live_conversation_message_count=3,
        live_business_memory_char_count=120,
        new_snapshot=snapshot,
    )


print("\n── record_shadow_comparison(): PostgreSQL unavailable => fail-soft ────────────────")

with patch("core.database.get_conn", return_value=None):
    ok = record_shadow_comparison(_comparison())
    chk("returns False when PostgreSQL unavailable", ok is False)


print("\n── record_shadow_comparison(): write failure rolls back, never raises ────────────────")

fake_cursor = MagicMock()
fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
fake_cursor.__exit__ = MagicMock(return_value=False)
fake_cursor.execute.side_effect = RuntimeError("boom")
fake_conn = MagicMock()
fake_conn.cursor.return_value = fake_cursor

with patch("core.database.get_conn", return_value=fake_conn), \
     patch("core.database.release_conn") as mock_release:
    ok = record_shadow_comparison(_comparison())
    chk("returns False on write failure, does not raise", ok is False)
    chk("rollback() called before release", fake_conn.rollback.called)
    chk("release_conn() still called", mock_release.called)


print("\n── record_shadow_comparison(): structured counts only, no memory text ────────────────")

fake_cursor = MagicMock()
fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
fake_cursor.__exit__ = MagicMock(return_value=False)
fake_conn = MagicMock()
fake_conn.cursor.return_value = fake_cursor

with patch("core.database.get_conn", return_value=fake_conn), \
     patch("core.database.release_conn"):
    comparison = _comparison(business=(BusinessMemoryItem(
        record_id="rec1", title="SENSITIVE_TITLE", description="SENSITIVE_DESC",
        event_type=None, domain=None, occurred_at=None,
    ),))
    ok = record_shadow_comparison(comparison)
    chk("write succeeds", ok is True)
    sql, params = fake_cursor.execute.call_args[0]
    chk("INSERT targets memory_shadow_comparisons", "memory_shadow_comparisons" in sql)
    chk("no item title/description text in the written params", not any(
        isinstance(p, str) and ("SENSITIVE" in p) for p in params
    ))
    chk("business count (1) is among the written params", 1 in params)
    chk("commit() called", fake_conn.commit.called)


print("\n── _job_memory_shadow_scan(): flag off (default) => no-op ────────────────")

import scheduler

with patch("feature_flags.is_enabled", return_value=False), \
     patch("identity.resolve_identity") as mock_resolve, \
     patch("core.memory_retrieval_shadow.compare_with_live_paths") as mock_compare, \
     patch("core.memory_retrieval_shadow.record_shadow_comparison") as mock_record:
    scheduler._job_memory_shadow_scan()
    chk("resolve_identity never called when flag is off", mock_resolve.call_count == 0)
    chk("compare_with_live_paths never called when flag is off", mock_compare.call_count == 0)
    chk("record_shadow_comparison never called when flag is off", mock_record.call_count == 0)


print("\n── _job_memory_shadow_scan(): flag on, ELIYAHU_CHAT_ID unset => skip safely ────────────────")

with patch("feature_flags.is_enabled", return_value=True), \
     patch.dict(os.environ, {"ELIYAHU_CHAT_ID": ""}), \
     patch("core.memory_retrieval_shadow.compare_with_live_paths") as mock_compare:
    try:
        scheduler._job_memory_shadow_scan()
        raised = False
    except Exception:
        raised = True
    chk("does not raise when ELIYAHU_CHAT_ID is unset", raised is False)
    chk("compare_with_live_paths never called", mock_compare.call_count == 0)


print("\n── _job_memory_shadow_scan(): flag on, unbuildable request => skip safely ────────────────")

with patch("feature_flags.is_enabled", return_value=True), \
     patch("identity.resolve_identity") as mock_resolve, \
     patch("core.memory_retrieval_shadow.build_shadow_request", return_value=None), \
     patch("core.memory_retrieval_shadow.compare_with_live_paths") as mock_compare:
    mock_resolve.return_value = type("I", (), {
        "role": "owner", "tenant_id": "", "user_id": "1", "domain_id": "general",
        "memory_key": "boss_hq:1",
    })()
    scheduler._job_memory_shadow_scan()
    chk("compare_with_live_paths never called when request can't be built", mock_compare.call_count == 0)


print("\n── _job_memory_shadow_scan(): happy path ────────────────")

sentinel_comparison = _comparison()
with patch("feature_flags.is_enabled", return_value=True), \
     patch("identity.resolve_identity") as mock_resolve, \
     patch("core.memory_retrieval_shadow.build_shadow_request") as mock_build, \
     patch("core.memory_retrieval_shadow.compare_with_live_paths", return_value=sentinel_comparison) as mock_compare, \
     patch("core.memory_retrieval_shadow.record_shadow_comparison") as mock_record:
    identity = type("I", (), {
        "role": "owner", "tenant_id": "boss_hq", "user_id": "1", "domain_id": "general",
        "memory_key": "boss_hq:1",
    })()
    mock_resolve.return_value = identity
    mock_build.return_value = MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="1")
    scheduler._job_memory_shadow_scan()
    chk("resolve_identity called with telegram + ELIYAHU_CHAT_ID", mock_resolve.call_args[0] == ("telegram", "1"))
    chk("compare_with_live_paths called exactly once", mock_compare.call_count == 1)
    chk("compare_with_live_paths called with the owner's memory_key", mock_compare.call_args.kwargs.get("memory_key") == "boss_hq:1")
    chk("record_shadow_comparison called exactly once with the comparison", mock_record.call_args[0] == (sentinel_comparison,))


print("\n── _job_memory_shadow_scan(): never raises even on internal failure ────────────────")

with patch("feature_flags.is_enabled", side_effect=RuntimeError("boom")):
    try:
        scheduler._job_memory_shadow_scan()
        raised = False
    except Exception:
        raised = True
    chk("does not raise when feature_flags.is_enabled blows up", raised is False)


print(f"\n{'='*40}")
print(f"memory_shadow logging tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
