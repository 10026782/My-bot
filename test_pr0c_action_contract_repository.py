#!/usr/bin/env python3
"""
test_pr0c_action_contract_repository.py — Regression tests for PR-0C Phase
4B0: durable ActionContract recovery (core/action_contract_repository.py) and
ExecutionLedger's cache-fallback/guarded-transition wiring.

Required coverage (per the reviewer's explicit ask before Phase 4B can wire
TMA routing by contract_id):
  1. Restart recovery — find_by_id() falls back to the repository on a cache
     miss and hydrates the full contract (identity/policy included).
  2. Multi-instance race — two "processes" both attempt approve() on the same
     contract; only one wins, the other gets a real conflict, never double-
     executes.
  3. Identity binding — a hydrated contract preserves actor_role/
     actor_external_id/etc. exactly, so re-execution dispatches with the
     correct original identity, not a re-resolved one.
  4. Expiry — a pending contract older than the TTL is not recoverable.
  5. Repeated approval — approving an already-approved/executed contract a
     second time is refused, not re-executed.
  6. Stale-status regression — guarded_transition() refuses to apply an
     out-of-order/stale transition (wrong expected_version/status).
  7. Store outage — repository unreachable and not cached -> fails closed
     (None), never fabricates a replacement contract.
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("AIRTABLE_API_KEY", "patPR0C4B0Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPR0C4B0Test")

from airtable_schema import ActionContractsFields, Tables  # noqa: E402
from core.action_contract_repository import (  # noqa: E402
    CONTRACT_PENDING_TTL_SECONDS,
    ActionContractRepository,
)
from core.action_gateway import ActionContract, ExecutionLedger  # noqa: E402
from tools.airtable_gateway import AirtableLookupError  # noqa: E402

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
# Fake Airtable backing store — realistic GET (filterByFormula exact match) /
# PATCH (by record id) / POST (create) semantics, so guarded_transition()'s
# read-patch-reread sequence can be tested deterministically, including
# races (by calling repository internals in a controlled interleaving).
# ══════════════════════════════════════════════════════════════════

class _FakeTable:
    def __init__(self):
        self._records: dict[str, dict] = {}   # record_id -> {"id", "fields"}
        self._next_id = 1

    def _new_id(self) -> str:
        rid = f"rec{self._next_id:014d}"
        self._next_id += 1
        return rid

    def get(self, url, headers=None, params=None, timeout=None):
        formula = params.get("filterByFormula", "")
        resp = MagicMock()
        resp.status_code = 200
        matches = [r for r in self._records.values() if self._formula_matches(formula, r)]
        resp.json.return_value = {"records": matches[: params.get("maxRecords", 1)]}
        return resp

    def patch(self, url, headers=None, json=None, timeout=None):
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
        # Only supports what this test needs: {field}='value' and
        # AND({field1}='v1', {field2}='v2').
        import re
        conditions = re.findall(r"\{(\w+)\}='([^']*)'", formula)
        return all(record["fields"].get(field) == value for field, value in conditions)


def _seed_contract(table: _FakeTable, **overrides) -> tuple[str, dict]:
    """Seeds a fake Airtable record for a pending contract, returns (contract_id, fields)."""
    contract_id = overrides.pop("contract_id", "c-repo-1")
    fields = {
        ActionContractsFields.CONTRACT_ID: contract_id,
        ActionContractsFields.TENANT_ID: "boss_hq",
        ActionContractsFields.CANONICAL_USER_ID: "boss_hq:owner_1",
        ActionContractsFields.TOOL_NAME: "send_followup",
        ActionContractsFields.NORMALIZED_PAYLOAD: '{"chat_id": "owner_1", "draft": "hi"}',
        ActionContractsFields.BUSINESS_FINGERPRINT: "fp-repo-1",
        ActionContractsFields.ORIGIN_CHANNEL: "telegram",
        ActionContractsFields.ORIGIN_CHAT_ID: "owner_1",
        ActionContractsFields.REQUIRES_APPROVAL: True,
        ActionContractsFields.STATUS: "pending",
        ActionContractsFields.CREATED_AT: time.time(),
        ActionContractsFields.APPROVED_BY: "",
        ActionContractsFields.APPROVED_AT: 0.0,
        ActionContractsFields.VERSION: 1,
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
    return contract_id, fields


def _patched(table: _FakeTable):
    return (
        patch("tools.airtable_gateway.httpx.get", side_effect=table.get),
        patch("tools.airtable_gateway.httpx.patch", side_effect=table.patch),
        patch("tools.airtable_gateway.httpx.post", side_effect=table.post),
    )


# ══════════════════════════════════════════════════════════════════
# 1. Restart recovery — find_by_id() hydrates from the repository
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: restart recovery via find_by_id() ─────────────────")

table1 = _FakeTable()
_seed_contract(table1, contract_id="c-restart-1")
repo1 = ActionContractRepository()
ledger1 = ExecutionLedger(repository=repo1)  # empty cache — simulates a fresh process

p1, p2, p3 = _patched(table1)
with p1, p2, p3:
    chk("Test1: not yet in cache", ledger1._store.get("c-restart-1") is None)
    found = ledger1.find_by_id("c-restart-1")
    chk("Test1: hydrated from repository on cache miss", found is not None and found.status == "pending")
    chk("Test1: hydrated into cache for next call", ledger1._store.get("c-restart-1") is found)


# ══════════════════════════════════════════════════════════════════
# 2. Multi-instance race — only one of two approve() calls wins
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: multi-instance race — only one approve() wins ─────")

table2 = _FakeTable()
_seed_contract(table2, contract_id="c-race-1")
repo2 = ActionContractRepository()

p1, p2, p3 = _patched(table2)
with p1, p2, p3:
    # Two independent ExecutionLedgers simulate two Render instances — neither
    # has the other's in-memory cache, both must go through the repository.
    ledger_a = ExecutionLedger(repository=repo2)
    ledger_b = ExecutionLedger(repository=repo2)

    contract_a = ledger_a.find_by_id("c-race-1")
    contract_b = ledger_b.find_by_id("c-race-1")
    chk("Test2: both instances see version=1 pending before racing",
        contract_a.version == 1 and contract_b.version == 1 and
        contract_a.status == "pending" and contract_b.status == "pending")

    result_a = ledger_a.guarded_update_status("c-race-1", expected_status="pending", new_status="approved", approved_by="instance_a")
    result_b = ledger_b.guarded_update_status("c-race-1", expected_status="pending", new_status="approved", approved_by="instance_b")

    chk("Test2: exactly one instance wins the transition",
        (result_a is not None) != (result_b is not None))
    winner_field = table2._records[next(iter(table2._records))]["fields"][ActionContractsFields.APPROVED_BY]
    chk("Test2: durable record reflects exactly one approver", winner_field in ("instance_a", "instance_b"))
    chk("Test2: durable record status is 'approved' exactly once", table2._records[next(iter(table2._records))]["fields"][ActionContractsFields.STATUS] == "approved")


# ══════════════════════════════════════════════════════════════════
# 3. Identity binding survives hydration
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: identity binding survives hydration ───────────────")

table3 = _FakeTable()
_seed_contract(
    table3, contract_id="c-identity-1",
    **{
        ActionContractsFields.ACTOR_ROLE: "employee",
        ActionContractsFields.ACTOR_EXTERNAL_ID: "emp_42",
        ActionContractsFields.ACTOR_DOMAIN_ID: "real_estate",
        ActionContractsFields.TRUSTED_SOURCE: "lead_capture",
    },
)
repo3 = ActionContractRepository()
p1, p2, p3 = _patched(table3)
with p1, p2, p3:
    hydrated = repo3.get("c-identity-1")

chk("Test3: actor_role preserved through hydration", hydrated.actor_role == "employee")
chk("Test3: actor_external_id preserved (not re-resolved)", hydrated.actor_external_id == "emp_42")
chk("Test3: actor_domain_id preserved", hydrated.actor_domain_id == "real_estate")
chk("Test3: trusted_source preserved (not defaulted to 'agent')", hydrated.trusted_source == "lead_capture")


# ══════════════════════════════════════════════════════════════════
# 4. Expiry — an old pending contract is not recoverable
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: expired pending contract is not recoverable ───────")

table4 = _FakeTable()
old_ts = time.time() - CONTRACT_PENDING_TTL_SECONDS - 3600  # 1h past TTL
_seed_contract(table4, contract_id="c-expired-1", **{ActionContractsFields.CREATED_AT: old_ts})
repo4 = ActionContractRepository()
p1, p2, p3 = _patched(table4)
with p1, p2, p3:
    result = repo4.get("c-expired-1")
chk("Test4: expired pending contract returns None, not fabricated", result is None)

table4b = _FakeTable()
_seed_contract(table4b, contract_id="c-fresh-1", **{ActionContractsFields.CREATED_AT: time.time()})
repo4b = ActionContractRepository()
p1, p2, p3 = _patched(table4b)
with p1, p2, p3:
    result = repo4b.get("c-fresh-1")
chk("Test4: fresh (non-expired) pending contract IS recoverable", result is not None)


# ══════════════════════════════════════════════════════════════════
# 5. Repeated approval — second approve() on an already-approved contract fails
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: repeated approval is refused, not re-executed ─────")

table5 = _FakeTable()
_seed_contract(table5, contract_id="c-repeat-1")
repo5 = ActionContractRepository()
p1, p2, p3 = _patched(table5)
with p1, p2, p3:
    first = repo5.guarded_transition("c-repeat-1", expected_version=1, expected_status="pending", new_status="approved", approved_by="owner_1")
    chk("Test5: first approval succeeds", first is not None and first.status == "approved")

    # Second attempt still claims expected_version=1/status=pending (stale
    # caller state, e.g. a retried duplicate request) — must be refused.
    second = repo5.guarded_transition("c-repeat-1", expected_version=1, expected_status="pending", new_status="approved", approved_by="owner_1")
    chk("Test5: repeated approval with stale expectations is refused", second is None)


# ══════════════════════════════════════════════════════════════════
# 6. Stale-status regression — an out-of-order transition is refused
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: stale-status regression is refused ────────────────")

table6 = _FakeTable()
_seed_contract(table6, contract_id="c-stale-1", **{ActionContractsFields.STATUS: "executed", ActionContractsFields.VERSION: 3})
repo6 = ActionContractRepository()
p1, p2, p3 = _patched(table6)
with p1, p2, p3:
    # A stale writer thinks it's still "pending" at version 1 — must not be
    # allowed to regress an already-executed contract back to "approved".
    regressed = repo6.guarded_transition("c-stale-1", expected_version=1, expected_status="pending", new_status="approved")
chk("Test6: stale transition attempt is refused", regressed is None)
chk("Test6: durable status remains 'executed', not regressed",
    table6._records[next(iter(table6._records))]["fields"][ActionContractsFields.STATUS] == "executed")


# ══════════════════════════════════════════════════════════════════
# 7. Store outage — fails closed, never fabricates a replacement contract
# ══════════════════════════════════════════════════════════════════
print("\n── Test 7: store outage fails closed ──────────────────────────")

repo7 = ActionContractRepository()
with patch("tools.airtable_gateway.httpx.get", side_effect=RuntimeError("network down")):
    result = repo7.get("c-outage-1")
chk("Test7: get() returns None on store outage (not an exception, not a fabricated contract)", result is None)

ledger7 = ExecutionLedger(repository=repo7)
with patch("tools.airtable_gateway.httpx.get", side_effect=RuntimeError("network down")):
    found = ledger7.find_by_id("c-outage-2")
chk("Test7: ExecutionLedger.find_by_id() also fails closed on store outage", found is None)

with patch("tools.airtable_gateway.httpx.get", side_effect=RuntimeError("network down")):
    transitioned = repo7.guarded_transition("c-outage-3", expected_version=1, expected_status="pending", new_status="approved")
chk("Test7: guarded_transition() fails closed on store outage", transitioned is None)


# ══════════════════════════════════════════════════════════════════
# 8. End-to-end through the public ActionGateway.approve() API — two
# separate ActionGateway instances (simulating two Render processes, sharing
# only the durable repository) racing on the same contract must execute the
# tool exactly once.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 8: end-to-end approve() race via two ActionGateway instances ─")

from core.action_gateway import ActionGateway  # noqa: E402

table8 = _FakeTable()
_seed_contract(
    table8, contract_id="c-e2e-race-1",
    **{
        ActionContractsFields.TOOL_NAME: "send_followup",
        ActionContractsFields.NORMALIZED_PAYLOAD: '{"chat_id": "owner_1", "draft": "hi"}',
        ActionContractsFields.ACTOR_ROLE: "owner",
        ActionContractsFields.ACTOR_EXTERNAL_ID: "owner_1",
    },
)
repo8 = ActionContractRepository()

dispatch_calls = []

def _counting_executor(tool_name, tool_inputs, contract_id):
    dispatch_calls.append(contract_id)
    return {"ok": True, "tool": tool_name, "external_id": "audit-e2e", "evidence": {"audit_id": "audit-e2e"}, "user_message": "✅"}

gw_instance_1 = ActionGateway(ledger=ExecutionLedger(repository=repo8), tool_executor=_counting_executor)
gw_instance_2 = ActionGateway(ledger=ExecutionLedger(repository=repo8), tool_executor=_counting_executor)

p1, p2, p3 = _patched(table8)
with p1, p2, p3:
    reply_1 = gw_instance_1.approve("c-e2e-race-1", approver="boss_hq:owner_1", approver_role="owner")
    reply_2 = gw_instance_2.approve("c-e2e-race-1", approver="boss_hq:owner_1", approver_role="owner")

chk("Test8: dispatch_tool (executor) called exactly once across both instances", len(dispatch_calls) == 1)
chk("Test8: exactly one of the two approve() calls reports success",
    ("❌" not in reply_1 and "⚠️" not in reply_1) != ("❌" not in reply_2 and "⚠️" not in reply_2))
chk("Test8: durable contract ends 'executed', not stuck at 'approved'/'executing'",
    table8._records[next(iter(table8._records))]["fields"][ActionContractsFields.STATUS] == "executed")


# ══════════════════════════════════════════════════════════════════
# 9. Live singleton must still NOT be wired — same discipline as Phase 4A.
# Wiring the repository into the live singleton is a deliberate, separate
# activation step (real writes/reads on every live approval), not something
# that should ride along silently in the same commit that builds and tests
# the repository.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 9: live singleton still deliberately unwired ─────────")

from core.action_gateway import action_gateway as _live_gw2  # noqa: E402

chk(
    "action_gateway's live ledger still has no repository wired "
    "(Phase 4B0 builds+tests the read/recovery path; activating it in "
    "production is a separate, deliberate step)",
    _live_gw2._ledger._repository is None,
)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C Phase 4B0 repository tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
