#!/usr/bin/env python3
"""
test_pr0c_action_contract_repository.py — Regression tests for PR-0C Phase
4B0 (re-scoped): durable ActionContract recovery
(core/action_contract_repository.py) and ExecutionLedger's cache-fallback
wiring, scoped to persistence / hydration / identity-binding / fail-closed
reads ONLY.

Phase 4B0 originally also included a "guarded_transition()" claim mechanism
built on Airtable read->check->PATCH->re-read. That mechanism was removed
after tracing showed it provides NO protection under genuine concurrency:
two callers who both read before either writes independently compute the
identical expected_version+1/new_status, both PATCH, both pass their own
re-read check, and BOTH get a non-None success — i.e. both proceed to
execute. This was not a "narrowed race window," it never worked for the
exact case (near-simultaneous duplicate requests) that matters most. See
core/action_contract_repository.py's module docstring. A real claim
mechanism requires a genuinely atomic coordination primitive outside
Airtable (transactional SQL/CAS, Redis SET-NX with lease and fencing, or a
single-consumer execution queue) — tracked separately as Phase 4B0.1, not
built yet. Phase 4B (TMA routes approve/reject by contract_id) stays
blocked until it lands.

Coverage in this file (persistence/hydration/identity/fail-closed only):
  1. Restart recovery — find_by_id() falls back to the repository on a cache
     miss and hydrates the full contract (identity/policy included).
  2. Identity binding — a hydrated contract preserves actor_role/
     actor_external_id/etc. exactly, so re-execution dispatches with the
     correct original identity, not a re-resolved one.
  3. Expiry — a pending contract older than the TTL is not recoverable.
  4. Store outage — repository unreachable and not cached raises an explicit
     lookup error, never fabricates a not-found result.
  5. Live singleton must still not be wired with a repository, and
     ActionGateway.approve()/_execute_contract() must still use the plain,
     non-atomic update_status() path — activating any durable claim
     mechanism is a deliberate, separate step gated on Phase 4B0.1.
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
    ActionContractLookupError,
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
# PATCH (by record id) / POST (create) semantics.
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
# 2. Identity binding survives hydration
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: identity binding survives hydration ───────────────")

table2 = _FakeTable()
_seed_contract(
    table2, contract_id="c-identity-1",
    **{
        ActionContractsFields.ACTOR_ROLE: "employee",
        ActionContractsFields.ACTOR_EXTERNAL_ID: "emp_42",
        ActionContractsFields.ACTOR_DOMAIN_ID: "real_estate",
        ActionContractsFields.TRUSTED_SOURCE: "lead_capture",
    },
)
repo2 = ActionContractRepository()
p1, p2, p3 = _patched(table2)
with p1, p2, p3:
    hydrated = repo2.get("c-identity-1")

chk("Test2: actor_role preserved through hydration", hydrated.actor_role == "employee")
chk("Test2: actor_external_id preserved (not re-resolved)", hydrated.actor_external_id == "emp_42")
chk("Test2: actor_domain_id preserved", hydrated.actor_domain_id == "real_estate")
chk("Test2: trusted_source preserved (not defaulted to 'agent')", hydrated.trusted_source == "lead_capture")


# ══════════════════════════════════════════════════════════════════
# 3. Expiry — an old pending contract is not recoverable
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: expired pending contract is not recoverable ───────")

table3 = _FakeTable()
old_ts = time.time() - CONTRACT_PENDING_TTL_SECONDS - 3600  # 1h past TTL
_seed_contract(table3, contract_id="c-expired-1", **{ActionContractsFields.CREATED_AT: old_ts})
repo3 = ActionContractRepository()
p1, p2, p3 = _patched(table3)
with p1, p2, p3:
    result = repo3.get("c-expired-1")
chk("Test3: expired pending contract returns None, not fabricated", result is None)

table3b = _FakeTable()
_seed_contract(table3b, contract_id="c-fresh-1", **{ActionContractsFields.CREATED_AT: time.time()})
repo3b = ActionContractRepository()
p1, p2, p3 = _patched(table3b)
with p1, p2, p3:
    result = repo3b.get("c-fresh-1")
chk("Test3: fresh (non-expired) pending contract IS recoverable", result is not None)


# ══════════════════════════════════════════════════════════════════
# 4. Store outage — fails closed, never fabricates a replacement contract
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: store outage fails closed ──────────────────────────")

repo4 = ActionContractRepository()
lookup_error = None
with patch("tools.airtable_gateway.httpx.get", side_effect=RuntimeError("network down")):
    try:
        repo4.get("c-outage-1")
    except ActionContractLookupError as exc:
        lookup_error = exc
chk("Test4: get() distinguishes store outage from clean not-found", lookup_error is not None)

ledger4 = ExecutionLedger(repository=repo4)
ledger_lookup_error = None
with patch("tools.airtable_gateway.httpx.get", side_effect=RuntimeError("network down")):
    try:
        ledger4.find_by_id("c-outage-2")
    except ActionContractLookupError as exc:
        ledger_lookup_error = exc
chk("Test4: ExecutionLedger.find_by_id() propagates lookup failure", ledger_lookup_error is not None)


# ══════════════════════════════════════════════════════════════════
# 5. Live singleton must still NOT be wired, and approve()/_execute_contract()
# must still use the plain, non-atomic update_status() path — same discipline
# as Phase 4A. There is no durable claim mechanism to activate yet (Phase
# 4B0.1 is not built), so nothing should route through one.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: live singleton unwired; approve() uses plain update_status() ─")

from core.action_gateway import action_gateway as _live_gw2  # noqa: E402

chk(
    "action_gateway's live ledger still has no repository wired "
    "(Phase 4B0 builds+tests the read/recovery path only; a durable claim "
    "mechanism does not exist yet and activating any repository wiring for "
    "transitions is a separate, deliberate step gated on Phase 4B0.1)",
    _live_gw2._ledger._repository is None,
)
chk(
    "ExecutionLedger has no guarded_update_status method (removed — no "
    "transition path should exist until a genuinely atomic mechanism lands)",
    not hasattr(_live_gw2._ledger, "guarded_update_status"),
)
chk(
    "ActionContractRepository has no guarded_transition method (removed — "
    "see module docstring)",
    not hasattr(ActionContractRepository(), "guarded_transition"),
)


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C Phase 4B0 repository tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
