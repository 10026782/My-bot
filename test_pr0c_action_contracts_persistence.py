#!/usr/bin/env python3
"""
test_pr0c_action_contracts_persistence.py — Regression tests for PR-0C Phase
4A: durable ActionContracts persistence for ActionGateway (core/action_gateway.py).

Coverage:
  1. tools/airtable_gateway.py::at_upsert — create when no match, patch when a
     match exists, false when match_field's value is missing.
  2. core/action_gateway.py::_build_airtable_writer() now returns a real
     writer (Tables.ACTION_CONTRACTS exists) instead of the old None.
  3. ExecutionLedger.save()/update_status() call the airtable_writer with the
     expected field shape, and a writer failure never loses the RAM record
     (graceful degrade, matching the pre-existing try/except).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("AIRTABLE_API_KEY", "patPR0C4ATest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPR0C4ATest")

from airtable_schema import ActionContractsFields, Tables
from core.action_gateway import ActionContract, ExecutionLedger, _build_airtable_writer
from tools.airtable_gateway import at_upsert

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _fake_response(status_code: int, json_body: dict):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.text = str(json_body)
    return r


# ══════════════════════════════════════════════════════════════════
# 1. at_upsert — create vs patch vs missing match value
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: at_upsert create/patch/missing ────────────────────")

with patch("tools.airtable_gateway.httpx.get", return_value=_fake_response(200, {"records": []})), \
     patch("tools.airtable_gateway.airtable_create", return_value={"id": "recNEW1"}) as _create, \
     patch("tools.airtable_gateway.airtable_patch") as _patch:
    ok = at_upsert("ActionContracts", {"contract_id": "c1", "status": "pending"}, "contract_id")
chk("at_upsert: no existing match -> creates", ok is True and _create.called and not _patch.called)

with patch("tools.airtable_gateway.httpx.get", return_value=_fake_response(200, {"records": [{"id": "recEXIST1"}]})), \
     patch("tools.airtable_gateway.airtable_create") as _create2, \
     patch("tools.airtable_gateway.airtable_patch", return_value=True) as _patch2:
    ok = at_upsert("ActionContracts", {"contract_id": "c1", "status": "executed"}, "contract_id")
chk("at_upsert: existing match -> patches, not creates", ok is True and _patch2.called and not _create2.called)
chk("at_upsert: patches the found record id", _patch2.call_args[0][1] == "recEXIST1")

ok = at_upsert("ActionContracts", {"status": "pending"}, "contract_id")
chk("at_upsert: missing match_field value -> False, no HTTP call", ok is False)


# ══════════════════════════════════════════════════════════════════
# 2. _build_airtable_writer — now wired (Tables.ACTION_CONTRACTS exists)
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: _build_airtable_writer wiring ─────────────────────")

chk("Tables.ACTION_CONTRACTS is defined", hasattr(Tables, "ACTION_CONTRACTS"))
writer = _build_airtable_writer()
chk("_build_airtable_writer() returns a real callable, not None", writer is not None and callable(writer))

contract = ActionContract(
    contract_id="c-test-1", tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="send_followup", normalized_payload={"chat_id": "x"},
    business_action_fingerprint="fp1", origin_channel="telegram", origin_chat_id="owner_1",
    requires_approval=True, status="pending", created_at=1752345600.0,
)

with patch("tools.airtable_gateway.at_upsert", return_value=True) as _upsert:
    # _build_airtable_writer() imports at_upsert into its own closure at
    # build time, so patch first, then build fresh — patching after the
    # fact wouldn't affect an already-bound closure.
    fresh_writer = _build_airtable_writer()
    fresh_writer(contract)
chk("writer() calls at_upsert with Tables.ACTION_CONTRACTS", _upsert.call_args[0][0] == Tables.ACTION_CONTRACTS)
written_fields = _upsert.call_args[0][1]
chk("writer() sends contract_id field", written_fields.get(ActionContractsFields.CONTRACT_ID) == "c-test-1")
chk("writer() sends status field", written_fields.get(ActionContractsFields.STATUS) == "pending")
chk("writer() serializes normalized_payload as JSON string",
    written_fields.get(ActionContractsFields.NORMALIZED_PAYLOAD) == '{"chat_id": "x"}')
chk("writer() match_field is contract_id", _upsert.call_args.kwargs.get("match_field") == ActionContractsFields.CONTRACT_ID)


# ══════════════════════════════════════════════════════════════════
# 3. ExecutionLedger — persists on save/update_status, degrades gracefully
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: ExecutionLedger persistence + graceful degrade ────")

write_calls = []

def _tracking_writer(c: ActionContract) -> None:
    write_calls.append((c.contract_id, c.status))

ledger = ExecutionLedger(airtable_writer=_tracking_writer)
contract2 = ActionContract(
    contract_id="c-test-2", tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="send_followup", normalized_payload={"chat_id": "x"},
    business_action_fingerprint="fp2", origin_channel="telegram", origin_chat_id="owner_1",
    requires_approval=True, status="pending", created_at=1752345600.0,
)
ledger.save(contract2)
chk("ExecutionLedger.save() invokes airtable_writer", write_calls == [("c-test-2", "pending")])

ledger.update_status("c-test-2", "executed")
chk("ExecutionLedger.update_status() invokes airtable_writer again",
    write_calls == [("c-test-2", "pending"), ("c-test-2", "executed")])

def _exploding_writer(c: ActionContract) -> None:
    raise RuntimeError("Airtable is down")

ledger2 = ExecutionLedger(airtable_writer=_exploding_writer)
contract3 = ActionContract(
    contract_id="c-test-3", tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
    tool_name="send_followup", normalized_payload={}, business_action_fingerprint="fp3",
    origin_channel="telegram", origin_chat_id="owner_1", requires_approval=True,
    status="pending", created_at=1752345600.0,
)
ledger2.save(contract3)  # must not raise
chk("ExecutionLedger.save() survives a writer exception (RAM intact)",
    ledger2.find_by_id("c-test-3") is not None)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C Phase 4A persistence tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
