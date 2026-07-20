#!/usr/bin/env python3
"""
test_last_tool_result_shadow.py — regression coverage for F52 Safe Refactor
#4 (core/last_tool_result_shadow.py), added 20/07/2026.

FEATURE_LAST_TOOL_RESULT_SHADOW is code-complete and side-effect-free by
design (RAM-only, bounded, never raises, never touches a caller's return
value), but had no dedicated test file — the only prior coverage was the
module's own inline _self_test(), which isn't picked up by this repo's
`python3 test_*.py` / pytest CI convention. This file exercises:

  1. The shadow store itself (bounded size, TTL eviction, never raises).
  2. All three real call sites (tools/dispatcher.py's dispatch_tool()
     finally-block, tma_api.py's _shadow_record_tma(), core/output_gateway.
     py's _shadow_record_send()) for the two properties that actually
     matter for a shadow flag: (a) off by default -> zero calls, and
     (b) even if record() itself raises, the caller's return value/control
     flow is completely unaffected.
"""

from __future__ import annotations

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import logging
import time
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

import core.last_tool_result_shadow as shadow
from identity import Identity
from tools.dispatcher import dispatch_tool

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
# 1. core/last_tool_result_shadow.py — the store itself
# ══════════════════════════════════════════════════════════════════
print("\n── core/last_tool_result_shadow.py ────")

shadow.clear()
chk("recent() empty after clear()", shadow.recent() == [])

eid = shadow.record(source="agent_tool", tool_or_action="airtable_add")
chk("record() returns a non-None id", eid is not None)
chk("recent() reflects the new entry", len(shadow.recent()) == 1)
chk("recorded source/tool_or_action round-trip", shadow.recent()[0].source == "agent_tool" and shadow.recent()[0].tool_or_action == "airtable_add")

shadow.clear()
for i in range(shadow._MAX_ENTRIES + 25):
    shadow.record(source="tma_route", tool_or_action=f"patch_{i}")
chk(f"store never exceeds _MAX_ENTRIES ({shadow._MAX_ENTRIES})", len(shadow._STORE) <= shadow._MAX_ENTRIES)
chk("eviction keeps the most recent entries (oldest evicted first)",
    shadow.recent(1)[0].tool_or_action == f"patch_{shadow._MAX_ENTRIES + 24}")

shadow.clear()
old_id = shadow.record(source="worker", tool_or_action="stale")
shadow._STORE[old_id] = shadow.LastToolResultShadow(
    id=old_id, source="worker", tool_or_action="stale",
    timestamp=time.time() - shadow._TTL_SECONDS - 1,
)
chk("TTL-expired entry evicted from recent()", shadow.recent() == [])

shadow.clear()
with patch("uuid.uuid4", side_effect=RuntimeError("boom")):
    result = shadow.record(source="agent_tool", tool_or_action="x")
chk("record() never raises even if its own internals blow up — returns None instead", result is None)


# ══════════════════════════════════════════════════════════════════
# 2. tools/dispatcher.py — dispatch_tool()'s finally-block call site
# ══════════════════════════════════════════════════════════════════
print("\n── tools/dispatcher.py call site ──────")

_OWNER = Identity(user_id="owner1", role="owner", tenant_id="boss_hq", external_id="owner1", channel="telegram")


def _dispatch_search_drive():
    with patch("tools.dispatcher.search_drive", return_value="✅ found it"):
        return dispatch_tool("search_drive", {"query": "contract"}, _OWNER)


with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "off"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    result = _dispatch_search_drive()
    chk("flag off -> dispatch_tool() still returns the real result", result == "✅ found it")
    chk("flag off -> record() never called", mock_record.call_count == 0)

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    result = _dispatch_search_drive()
    chk("flag on -> dispatch_tool() still returns the real result unchanged", result == "✅ found it")
    chk("flag on -> record() called once with source=agent_tool, tool_or_action=search_drive",
        mock_record.call_count == 1 and
        mock_record.call_args.kwargs.get("source") == "agent_tool" and
        mock_record.call_args.kwargs.get("tool_or_action") == "search_drive")

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record", side_effect=RuntimeError("shadow store exploded")):
    result = _dispatch_search_drive()
    chk("flag on + record() raises -> dispatch_tool() still returns the real result, no propagation",
        result == "✅ found it")


# ══════════════════════════════════════════════════════════════════
# 3. tma_api.py — _shadow_record_tma() (called from _at_patch/_at_post)
# ══════════════════════════════════════════════════════════════════
print("\n── tma_api.py call site ────────────────")

import tma_api

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "off"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    tma_api._shadow_record_tma("patch:Leads")
    chk("tma_api: flag off -> record() never called", mock_record.call_count == 0)

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    tma_api._shadow_record_tma("patch:Leads")
    chk("tma_api: flag on -> record() called with source=tma_route",
        mock_record.call_count == 1 and mock_record.call_args.kwargs.get("source") == "tma_route" and
        mock_record.call_args.kwargs.get("tool_or_action") == "patch:Leads")

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record", side_effect=RuntimeError("boom")):
    try:
        tma_api._shadow_record_tma("patch:Leads")
        raised = False
    except Exception:
        raised = True
    chk("tma_api: record() raising never propagates out of _shadow_record_tma()", raised is False)

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record") as mock_record, \
     patch("tma_api._gw_patch", return_value=True):
    ok = tma_api._at_patch("Leads", "recFAKE1234567890AB", {"status": "done"})
    chk("tma_api._at_patch(): return value unaffected by shadow recording", ok is True)
    chk("tma_api._at_patch(): shadow recorded after the real write", mock_record.call_count == 1)


# ══════════════════════════════════════════════════════════════════
# 4. core/output_gateway.py — _shadow_record_send()
# ══════════════════════════════════════════════════════════════════
print("\n── core/output_gateway.py call site ───")

from core.output_gateway import _shadow_record_send, OutboundEnvelope, OutputChannel, AudienceClass

_envelope = OutboundEnvelope(
    channel=OutputChannel.TWILIO_WHATSAPP,
    recipient="+972500000000",
    body="hello",
    audience=AudienceClass.CUSTOMER,
    source_module="app",
    source_ref="lead:123",
    domain="real_estate",
)

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "off"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    _shadow_record_send(_envelope)
    chk("output_gateway: flag off -> record() never called", mock_record.call_count == 0)

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    _shadow_record_send(_envelope)
    chk("output_gateway: flag on -> record() called with the channel in tool_or_action",
        mock_record.call_count == 1 and
        mock_record.call_args.kwargs.get("tool_or_action") == "send_outbound:twilio_whatsapp")
    chk("output_gateway: unmapped source_module falls back to 'agent_tool'",
        mock_record.call_args.kwargs.get("source") == "agent_tool")

with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record", side_effect=RuntimeError("boom")):
    try:
        _shadow_record_send(_envelope)
        raised = False
    except Exception:
        raised = True
    chk("output_gateway: record() raising never propagates out of _shadow_record_send()", raised is False)

_scheduler_envelope = OutboundEnvelope(
    channel=OutputChannel.TWILIO_WHATSAPP, recipient="+972500000000", body="hi",
    audience=AudienceClass.CUSTOMER, source_module="followup_engine", source_ref="lead:1", domain="general",
)
with patch.dict(os.environ, {"FEATURE_LAST_TOOL_RESULT_SHADOW": "on"}), \
     patch("core.last_tool_result_shadow.record") as mock_record:
    _shadow_record_send(_scheduler_envelope)
    chk("output_gateway: followup_engine maps to source=scheduler",
        mock_record.call_args.kwargs.get("source") == "scheduler")


print(f"\n{'='*40}")
print(f"last_tool_result_shadow tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
