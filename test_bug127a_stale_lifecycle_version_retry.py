#!/usr/bin/env python3
"""
test_bug127a_stale_lifecycle_version_retry.py — BUG-127A regression suite.

Live incident (RP5 staging, 21/07/2026): every inbound message calls
app.py's _apply_ingress_context_gate(), which calls
ExecutionLedger.mark_context_interrupted(), and on failure falls back to
mark_context_integrity_unknown(). Both failed together, twice in a row, on
the same 4 live contracts:

    [ERROR] ... ingress context gate primary mark failed ...
        ActionContractTransitionConflictError: stale lifecycle state:
        expected=pending/v1 actual=pending/v2
    [CRITICAL] ... ingress context gate fallback ALSO failed ...
        pending contracts may be silently stale-approvable

Root cause: ExecutionLedger.update_status() reads expected_version from the
RAM cache (self._store) BEFORE calling the repository's transition(), which
re-fetches fresh durable truth internally but never reports it back to the
caller on conflict. update_status() only re-caches on SUCCESS
(_cache_contract(persisted)) — so once the RAM cache drifts behind the
durable version, NOTHING in the existing code corrects it, and the same
contract fails this exact check forever (both mark_context_interrupted() and
its fallback read from the same stale self._store, so both fail identically
-- the fallback is not a real safety net for this failure class).

Fix: on ActionContractTransitionConflictError, refresh the RAM cache from
durable truth (repository.get()) and retry ONCE with the corrected version.
_cas_expected (the caller's real status requirement) is never touched by the
refresh -- only the version is corrected, so a GENUINE status divergence
(the contract really moved on, not just RAM staleness) still fails the
retry exactly as before the fix (fail-closed preserved).

Scope: core/action_gateway.py::ExecutionLedger.update_status() only. No
change to action_contract_repository.py::transition() itself, to
require_status's CAS semantics, or to approve()/reject()/execute() beyond
the shared benefit of fixing this one choke point.
"""

from __future__ import annotations

import os
import re
import sys
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("AIRTABLE_API_KEY", "patBug127ATest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug127ATest")

from airtable_schema import ActionContractsFields  # noqa: E402
from core.action_contract_repository import (  # noqa: E402
    ActionContractRepository,
    ActionContractTransitionConflictError,
)
from core.action_gateway import ActionContract, ExecutionLedger  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Fake Airtable backing store (same shape as test_pr0c_action_contract_repository.py)
# ══════════════════════════════════════════════════

class _FakeTable:
    def __init__(self):
        self._records: dict[str, dict] = {}
        self._next_id = 1
        self.get_calls = 0
        self.patch_calls = 0

    def _new_id(self) -> str:
        rid = f"rec{self._next_id:014d}"
        self._next_id += 1
        return rid

    def get(self, url, headers=None, params=None, timeout=None):
        self.get_calls += 1
        formula = params.get("filterByFormula", "")
        resp = MagicMock()
        resp.status_code = 200
        matches = [r for r in self._records.values() if self._formula_matches(formula, r)]
        resp.json.return_value = {"records": matches[: params.get("maxRecords", 1)]}
        return resp

    def patch(self, url, headers=None, json=None, timeout=None):
        self.patch_calls += 1
        record_id = url.rsplit("/", 1)[-1]
        resp = MagicMock()
        if record_id not in self._records:
            resp.status_code = 404
            resp.text = "not found"
            return resp
        self._records[record_id]["fields"].update(json["fields"])
        resp.status_code = 200
        resp.json.return_value = self._records[record_id]
        return resp

    def post(self, url, headers=None, json=None, timeout=None):
        rid = self._new_id()
        self._records[rid] = {"id": rid, "fields": dict(json["fields"])}
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = self._records[rid]
        return resp

    @staticmethod
    def _formula_matches(formula: str, record: dict) -> bool:
        conditions = re.findall(r"\{(\w+)\}='([^']*)'", formula)
        return all(record["fields"].get(field) == value for field, value in conditions)

    def fields_for(self, contract_id: str) -> dict:
        for rec in self._records.values():
            if rec["fields"].get(ActionContractsFields.CONTRACT_ID) == contract_id:
                return rec["fields"]
        raise KeyError(contract_id)


def _seed(table: _FakeTable, **overrides) -> str:
    contract_id = overrides.pop("contract_id", "c-stale-1")
    fields = {
        ActionContractsFields.CONTRACT_ID: contract_id,
        ActionContractsFields.TENANT_ID: "boss_hq",
        ActionContractsFields.CANONICAL_USER_ID: "boss_hq:owner_1",
        ActionContractsFields.TOOL_NAME: "send_followup",
        ActionContractsFields.NORMALIZED_PAYLOAD: '{"chat_id": "owner_1", "draft": "hi"}',
        ActionContractsFields.BUSINESS_FINGERPRINT: f"fp-{contract_id}",
        ActionContractsFields.ORIGIN_CHANNEL: "telegram",
        ActionContractsFields.ORIGIN_CHAT_ID: "owner_1",
        ActionContractsFields.REQUIRES_APPROVAL: True,
        ActionContractsFields.STATUS: "pending",
        ActionContractsFields.CREATED_AT: time.time(),
        ActionContractsFields.APPROVED_BY: "",
        ActionContractsFields.APPROVED_AT: 0.0,
        ActionContractsFields.VERSION: 2,
        ActionContractsFields.ACTOR_ROLE: "owner",
        ActionContractsFields.ACTOR_USER_ID: "owner_1",
        ActionContractsFields.ACTOR_DISPLAY_NAME: "Owner",
        ActionContractsFields.ACTOR_DOMAIN_ID: "general",
        ActionContractsFields.ACTOR_EXTERNAL_ID: "owner_1",
        ActionContractsFields.ACTOR_ALLOWED_DOMAINS: "[]",
        ActionContractsFields.APPROVAL_POLICY: "approval",
        ActionContractsFields.TRUSTED_SOURCE: "agent",
        ActionContractsFields.CONTEXT_INTERRUPTED: False,
        ActionContractsFields.RECONFIRMATION_REQUIRED: False,
        ActionContractsFields.CONTEXT_INTEGRITY_UNKNOWN: False,
    }
    fields.update(overrides)
    rid = table._new_id()
    table._records[rid] = {"id": rid, "fields": fields}
    return contract_id


def _stale_ram_contract(contract_id: str, *, status: str = "pending", version: int = 1) -> ActionContract:
    c = ActionContract(
        contract_id=contract_id, tenant_id="boss_hq", canonical_user_id="boss_hq:owner_1",
        tool_name="send_followup", normalized_payload={}, business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram", origin_chat_id="owner_1", requires_approval=True,
        status=status, created_at=time.time(),
    )
    c.version = version
    return c


def _patched(table: _FakeTable):
    return (
        patch("tools.airtable_gateway.httpx.get", side_effect=table.get),
        patch("tools.airtable_gateway.httpx.patch", side_effect=table.patch),
        patch("tools.airtable_gateway.httpx.post", side_effect=table.post),
    )


# ══════════════════════════════════════════════════
# Test 1 — pure version staleness self-heals via refresh + single retry
# ══════════════════════════════════════════════════
print("── Test 1: pure RAM version staleness self-heals ──────────────")

table1 = _FakeTable()
cid1 = _seed(table1, contract_id="c-stale-1", **{ActionContractsFields.VERSION: 2})
ledger1 = ExecutionLedger(repository=ActionContractRepository())
ledger1._store[cid1] = _stale_ram_contract(cid1, status="pending", version=1)

p1, p2, p3 = _patched(table1)
with p1, p2, p3:
    raised = None
    try:
        ledger1.mark_context_interrupted("boss_hq:owner_1")
    except Exception as exc:
        raised = exc
    chk("Test1: mark_context_interrupted() no longer raises on stale RAM version", raised is None)
    chk("Test1: RAM cache healed to the post-transition version (v2 -> v3)",
        ledger1._store[cid1].version == 3)
    chk("Test1: context_interrupted actually got set (the real operation succeeded)",
        ledger1._store[cid1].context_interrupted is True)
    chk("Test1: durable store reflects the same version/flag",
        table1.fields_for(cid1)[ActionContractsFields.VERSION] == 3
        and table1.fields_for(cid1)[ActionContractsFields.CONTEXT_INTERRUPTED] is True)


# ══════════════════════════════════════════════════
# Test 2 — genuine status divergence (not just version) still fails closed
# ══════════════════════════════════════════════════
print("\n── Test 2: genuine status divergence still fails closed ───────")

table2 = _FakeTable()
cid2 = _seed(table2, contract_id="c-approved-1", **{
    ActionContractsFields.STATUS: "approved",
    ActionContractsFields.VERSION: 2,
})
ledger2 = ExecutionLedger(repository=ActionContractRepository())
# RAM still thinks "pending"/v1 -- durable already moved on to "approved"/v2 for real.
ledger2._store[cid2] = _stale_ram_contract(cid2, status="pending", version=1)

p1, p2, p3 = _patched(table2)
with p1, p2, p3:
    raised = None
    try:
        ledger2.mark_context_interrupted("boss_hq:owner_1")
    except ActionContractTransitionConflictError as exc:
        raised = exc
    chk("Test2: a REAL status change (not just stale version) still raises after the retry",
        raised is not None)
    chk("Test2: durable status/version untouched by the failed attempt",
        table2.fields_for(cid2)[ActionContractsFields.STATUS] == "approved"
        and table2.fields_for(cid2)[ActionContractsFields.VERSION] == 2)


# ══════════════════════════════════════════════════
# Test 3 — the fallback (mark_context_integrity_unknown) gets the same fix
# ══════════════════════════════════════════════════
print("\n── Test 3: mark_context_integrity_unknown() also self-heals ───")

table3 = _FakeTable()
cid3 = _seed(table3, contract_id="c-stale-3", **{ActionContractsFields.VERSION: 5})
ledger3 = ExecutionLedger(repository=ActionContractRepository())
ledger3._store[cid3] = _stale_ram_contract(cid3, status="pending", version=1)

p1, p2, p3 = _patched(table3)
with p1, p2, p3:
    raised = None
    try:
        ledger3.mark_context_integrity_unknown("boss_hq:owner_1")
    except Exception as exc:
        raised = exc
    chk("Test3: mark_context_integrity_unknown() no longer raises on stale RAM version",
        raised is None)
    chk("Test3: context_integrity_unknown actually got set",
        ledger3._store[cid3].context_integrity_unknown is True)


# ══════════════════════════════════════════════════
# Test 4 — refresh itself failing (repository unreachable) falls back to
# the original pre-fix behavior, not an infinite loop
# ══════════════════════════════════════════════════
print("\n── Test 4: refresh failure falls back to raising, no infinite loop ──")

table4 = _FakeTable()
cid4 = _seed(table4, contract_id="c-stale-4", **{ActionContractsFields.VERSION: 2})
ledger4 = ExecutionLedger(repository=ActionContractRepository())
ledger4._store[cid4] = _stale_ram_contract(cid4, status="pending", version=1)

p1, p2, p3 = _patched(table4)
with p1, p2, p3:
    with patch(
        "core.action_gateway.ExecutionLedger._refresh_stale_contract_cache",
        return_value=None,
    ):
        raised = None
        try:
            ledger4.mark_context_interrupted("boss_hq:owner_1")
        except Exception as exc:
            raised = exc
        chk("Test4: refresh returning None (can't recover) still raises, not silently succeeds",
            raised is not None)


# ══════════════════════════════════════════════════
# Test 5 — no repository configured (legacy RAM-only path) is unaffected
# ══════════════════════════════════════════════════
print("\n── Test 5: legacy RAM-only ledger (no repository) unaffected ──")

ledger5 = ExecutionLedger()  # no repository
c5 = _stale_ram_contract("c-legacy-1", status="pending", version=1)
ledger5._store["c-legacy-1"] = c5
ledger5.mark_context_interrupted("boss_hq:owner_1")
chk("Test5: legacy RAM-only path still works with no repository configured",
    ledger5._store["c-legacy-1"].context_interrupted is True)


print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
