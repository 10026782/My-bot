#!/usr/bin/env python3
"""
test_fire_and_forget_fixes.py — regression tests for the fire-and-forget
follow-up from PR_RESPONSE_CONTRACT: callers that used to discard the
airtable_add/airtable_update result entirely now check result["ok"] and
log on failure, without changing their best-effort (non-raising) nature.

מאמת:
1. inbound_handler._log_interaction: ok=False → warning logged, no raise.
2. abandoned_lead_worker.create_human_pipeline_task: ok=False → returns
   False, owner NOT notified (was: always returned True regardless).
3. furniture_lead_funnel._save_lead (patch path): ok=False → warning
   logged, no raise.
4. session_store.PersistentSessionStore._delete_from_db: ok=False →
   warning logged, no raise (still best-effort — exceptions still
   swallowed by design, only the ok=False non-exception case is new).
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _ok_result(external_id: str = "recOK1") -> dict:
    return {"ok": True, "tool": "airtable_add", "external_id": external_id,
            "evidence": {}, "user_message": f"✅ {external_id}"}


def _fail_result() -> dict:
    return {"ok": False, "tool": "airtable_add", "external_id": "",
            "evidence": {}, "user_message": "❌ failed"}


# ══════════════════════════════════════════════════════════════════
# 1. inbound_handler._log_interaction
# ══════════════════════════════════════════════════════════════════
print("\n── inbound_handler._log_interaction ──")

from inbound_handler import _log_interaction

with patch("tools.airtable_tools.airtable_add", return_value=_ok_result()):
    try:
        _log_interaction("rec1", "hello")
        chk("_log_interaction: ok=True → no exception", True)
    except Exception:
        chk("_log_interaction: ok=True → no exception", False)

with patch("tools.airtable_tools.airtable_add", return_value=_fail_result()), \
     patch("inbound_handler.logger") as mock_logger:
    _log_interaction("rec1", "hello")
    chk("_log_interaction: ok=False → warning logged (was silently discarded)", mock_logger.warning.called)

# ══════════════════════════════════════════════════════════════════
# 2. abandoned_lead_worker.create_human_pipeline_task
# ══════════════════════════════════════════════════════════════════
print("\n── abandoned_lead_worker.create_human_pipeline_task ──")

from abandoned_lead_worker import create_human_pipeline_task, AbandonedLead

_lead = AbandonedLead(
    sender="voice:+972500000000", channel="voice", domain="general",
    step=2, total_steps=5, minutes_silent=15.0, answers={"name": "Test"},
)

with patch("tools.airtable_tools.airtable_add", return_value=_ok_result("recTASK1")), \
     patch("abandoned_lead_worker._notify_human_pipeline") as mock_notify:
    ok = create_human_pipeline_task(_lead, "owner_chat")
    chk("create_human_pipeline_task: ok=True → returns True", ok is True)
    chk("create_human_pipeline_task: ok=True → owner notified", mock_notify.called)

with patch("tools.airtable_tools.airtable_add", return_value=_fail_result()), \
     patch("abandoned_lead_worker._notify_human_pipeline") as mock_notify:
    ok = create_human_pipeline_task(_lead, "owner_chat")
    chk(
        "create_human_pipeline_task: ok=False → returns False (was: always True)",
        ok is False,
    )
    chk("create_human_pipeline_task: ok=False → owner NOT notified", not mock_notify.called)

# ══════════════════════════════════════════════════════════════════
# 3. furniture_lead_funnel._save_lead (patch path)
# ══════════════════════════════════════════════════════════════════
print("\n── furniture_lead_funnel._save_lead (patch) ──")

from furniture_lead_funnel import _save_lead

_session_existing = {"answers": {"name": "Dani"}, "lead_record_id": "recFURN1"}

with patch("tools.airtable_gateway.airtable_patch", return_value=True) as mock_patch:
    try:
        _save_lead("furn:1", dict(_session_existing))
        chk("_save_lead: patch ok=True → no exception", True)
    except Exception:
        chk("_save_lead: patch ok=True → no exception", False)
    chk("_save_lead: patch called for existing record", mock_patch.called)

with patch("tools.airtable_gateway.airtable_patch", return_value=False), \
     patch("furniture_lead_funnel.logger") as mock_logger:
    _save_lead("furn:1", dict(_session_existing))
    chk("_save_lead: patch ok=False → warning logged (was silently discarded)", mock_logger.warning.called)

# ══════════════════════════════════════════════════════════════════
# 4. session_store.PersistentSessionStore._delete_from_db
# ══════════════════════════════════════════════════════════════════
print("\n── session_store._delete_from_db ─────")

from session_store import PersistentSessionStore

_store = PersistentSessionStore()

with patch("tools.airtable_tools.airtable_update", return_value=_ok_result("recSESS1")):
    try:
        _store._delete_from_db("recSESS1", {"domain": "general"})
        chk("_delete_from_db: ok=True → no exception", True)
    except Exception:
        chk("_delete_from_db: ok=True → no exception", False)

with patch("tools.airtable_tools.airtable_update", return_value=_fail_result()), \
     patch("session_store.logger") as mock_logger:
    _store._delete_from_db("recSESS1", {"domain": "general"})
    chk("_delete_from_db: ok=False → warning logged (was silently discarded)", mock_logger.warning.called)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
