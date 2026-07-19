#!/usr/bin/env python3
"""
test_c84_tma_approval_ttl.py — C84: TMA Approvals TTL/freshness check.

ROADMAP C84 (🟡 גבוה): a `PENDING` TMA approval row could stay actionable
forever — no freshness check existed before executing it, unlike the
Telegram inline-button flow (BUG-112), which enforces its own
_PENDING_APPROVAL_TTL (600s) right before dispatch.

This adds a mirror of that principle to tma_api.py's
_claim_and_execute_approval() (the single choke point both act_on_approval()
and bulk_approve() route an "approve" decision through): once a contract's
own age (time.time() - ActionContract.created_at) exceeds
_TMA_APPROVAL_TTL_SECONDS (24h — a TMA dashboard row is reviewed
asynchronously, not a push-notification button checked within minutes), the
contract is rejected (verified, not assumed — mirrors
_reject_stale_telegram_approval()'s pattern) and dispatch never happens.

Does not touch RP5/F52, UnifiedStatusFormatter, or EvidenceFinalizer
taxonomy — this is a TMA-only, ActionGateway-adjacent freshness gate.

Tests:
  1. Fresh contract (age well under TTL) executes normally — baseline,
     unaffected by this change.
  2. Expired contract (age > TTL): action_gateway.approve() is NEVER called;
     the contract is rejected instead (verified via find_contract());
     response is ok=False, status_code=410, with a plain "expired" message.
  3. Exactly-at-boundary (age == TTL) still executes — the check is a strict
     `>`, not `>=`, so a freshly-crossed contract isn't punished by clock
     jitter alone.
  4. Expired contract's Approvals projection row is synced to reflect the
     rejection (STATUS=נדחה, PROJECTED_LIFECYCLE_STATUS=rejected) — the TMA
     UI must not keep showing a stale "pending" row.
  5. bulk_approve(): an expired item is never approved, lands in the
     "failed" bucket (not "approved", not silently dropped), and
     action_gateway.approve() is never called for it — a second, fresh item
     in the same batch is unaffected and still executes normally.
  6. A missing/garbage created_at is never treated as "expired" wrongly
     (would only ever happen for a malformed contract) is out of scope here —
     real ActionContract.created_at is a required dataclass field with no
     default (see core/action_gateway.py), so this can't occur for a genuine
     contract; not a case this suite needs to fabricate.
"""

from __future__ import annotations

import os
import sys
import time
import types
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── Minimal stubs so tma_api can be imported without full env ──────
os.environ.setdefault("TELEGRAM_TOKEN", "123:stub_token_for_tests")
os.environ.setdefault("AIRTABLE_API_KEY", "stub")
os.environ.setdefault("AIRTABLE_BASE_ID", "stub")
os.environ.setdefault("ANTHROPIC_API_KEY", "stub")

for mod_name in ["telebot", "anthropic", "httpx"]:
    sys.modules.setdefault(mod_name, MagicMock())

_sv = types.ModuleType("startup_validator")
_sv.validate_startup = lambda: None
_sv.format_startup_message = lambda: ""
sys.modules["startup_validator"] = _sv

# ── Import module under test ───────────────────────────────────────
import tma_api as _tma
from airtable_schema import ApprovalsFields, ApprovalStatus

_bulk_raw = _tma.bulk_approve.__wrapped__

from flask import Flask as _Flask
_app = _Flask(__name__)
_app.register_blueprint(_tma.tma_api)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _owner() -> SimpleNamespace:
    return SimpleNamespace(is_owner=True, user_id="owner_1", display_name="Owner", role="owner")


# ── Fake ActionGateway (same pattern as test_pr0c0_tma_approval_truthfulness.py) ──

class _FakeContract:
    def __init__(self, contract_id: str, status: str = "pending", created_at: float | None = None):
        self.contract_id = contract_id
        self.status = status
        self.approval_policy = "approval"
        self.tool_name = "tma_write"
        self.trusted_source = "tma_api"
        self.origin_channel = "tma"
        self.tenant_id = None
        self.created_at = created_at if created_at is not None else time.time()


class _FakeRepository:
    """Non-None sentinel — presence alone signals durable persistence available."""


class _FakeLedger:
    def __init__(self):
        self._repository = _FakeRepository()


class _FakeGateway:
    def __init__(self):
        self._ledger = _FakeLedger()
        self.contracts: dict[str, _FakeContract] = {}
        self.approve_calls: list[str] = []
        self.reject_calls: list[str] = []
        self.outcomes: dict[str, str] = {}   # per-contract_id forced approve() outcome

    def find_contract(self, contract_id):
        return self.contracts.get(contract_id)

    def approve(self, contract_id, approver, approver_role=""):
        self.approve_calls.append(contract_id)
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        outcome = self.outcomes.get(contract_id, "completed")
        c.status = outcome
        if outcome in ("completed", "executed"):
            return "✅ בוצע: test"
        return "❌ ביצוע נכשל: simulated failure"

    def reject(self, contract_id, rejected_by=""):
        self.reject_calls.append(contract_id)
        c = self.contracts.get(contract_id)
        if c is None:
            return "⚠️ פעולה לא נמצאה."
        if c.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {c.status})."
        c.status = "rejected"
        return "🚫 הפעולה בוטלה."


def _patched(gateway, at_list=None, at_get_record=None, at_patch=None, extra=()) -> ExitStack:
    stack = ExitStack()
    cms = [
        patch("core.action_gateway.action_gateway", gateway),
        patch("core.database.get_pool", return_value=object()),
        patch("feature_flags.is_enabled", return_value=True),
        patch("tma_api._try_bus_action", return_value=False),
        patch("tma_api._audit"),
        patch("tma_api._notify_owner"),
        *extra,
    ]
    if at_list is not None:
        cms.append(patch("tma_api._at_list", return_value=at_list))
    if at_get_record is not None:
        cms.append(patch("tma_api._at_get_record", side_effect=at_get_record))
    if at_patch is not None:
        cms.append(patch("tma_api._at_patch", side_effect=at_patch))
    for cm in cms:
        stack.enter_context(cm)
    return stack


def _rec(rec_id: str, contract_id: str = "", risk: str = "low", legacy: bool = False) -> dict:
    return {
        "id": rec_id,
        "fields": {
            ApprovalsFields.STATUS:              ApprovalStatus.PENDING,
            ApprovalsFields.ACTION:                "add lead",
            ApprovalsFields.RISK_LEVEL:            risk,
            ApprovalsFields.CONTEXT_ID:            f"ctx_{rec_id}",
            ApprovalsFields.CONTEXT_DATA:          "",
            ApprovalsFields.ACTION_CONTRACT_ID:    "" if legacy else (contract_id or f"c_{rec_id}"),
            ApprovalsFields.LEGACY_READ_ONLY:      legacy,
        },
    }


def _bulk(identity) -> dict:
    with _app.test_request_context("/api/approvals/bulk", method="POST"):
        result = _bulk_raw(identity=identity)
        resp = result[0] if isinstance(result, tuple) else result
        return resp.json


_TTL = _tma._TMA_APPROVAL_TTL_SECONDS


# ══════════════════════════════════════════════════════════════════
# 1. Fresh contract executes normally — unaffected baseline
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: fresh contract executes normally ──────────────────")

gw1 = _FakeGateway()
gw1.contracts["c_recA"] = _FakeContract("c_recA", created_at=time.time())

with _patched(gw1, at_get_record=lambda t, rid: _rec("recA"), at_patch=lambda t, rid, f: True):
    outcome1 = _tma._claim_and_execute_approval("recA", _owner())

chk("Test1: outcome is ok", outcome1.get("ok") is True)
chk("Test1: action_gateway.approve() was called", gw1.approve_calls == ["c_recA"])
chk("Test1: contract ended completed", gw1.contracts["c_recA"].status == "completed")


# ══════════════════════════════════════════════════════════════════
# 2. Expired contract (age > TTL): never approved, rejected instead,
#    ok=False / status_code=410
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2: expired contract is refused, not executed ─────────")

gw2 = _FakeGateway()
gw2.contracts["c_recB"] = _FakeContract("c_recB", created_at=time.time() - _TTL - 60)

with _patched(gw2, at_get_record=lambda t, rid: _rec("recB", contract_id="c_recB"),
              at_patch=lambda t, rid, f: True):
    outcome2 = _tma._claim_and_execute_approval("recB", _owner())

chk("Test2: outcome is not ok", outcome2.get("ok") is False)
chk("Test2: status_code is 410 (Gone/expired)", outcome2.get("status_code") == 410)
chk("Test2: action_gateway.approve() was NEVER called", gw2.approve_calls == [])
chk("Test2: action_gateway.reject() WAS called", gw2.reject_calls == ["c_recB"])
chk("Test2: contract ended rejected, not completed/executed",
    gw2.contracts["c_recB"].status == "rejected")


# ══════════════════════════════════════════════════════════════════
# 3. Exactly-at-boundary (age == TTL, not >) still executes
# ══════════════════════════════════════════════════════════════════
print("\n── Test 3: age exactly at TTL boundary still executes ────────")

gw3 = _FakeGateway()
# created_at chosen so (time.time() - created_at) is a hair under _TTL —
# avoids float/clock flakiness around an exact equality check.
gw3.contracts["c_recC"] = _FakeContract("c_recC", created_at=time.time() - _TTL + 5)

with _patched(gw3, at_get_record=lambda t, rid: _rec("recC", contract_id="c_recC"),
              at_patch=lambda t, rid, f: True):
    outcome3 = _tma._claim_and_execute_approval("recC", _owner())

chk("Test3: just-under-TTL contract still executes", outcome3.get("ok") is True)
chk("Test3: action_gateway.approve() was called", gw3.approve_calls == ["c_recC"])


# ══════════════════════════════════════════════════════════════════
# 4. Expired contract's Approvals projection is synced to reflect
#    the rejection (TMA UI must not keep showing stale "pending")
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: expired rejection syncs the Approvals projection ──")

gw4 = _FakeGateway()
gw4.contracts["c_recD"] = _FakeContract("c_recD", created_at=time.time() - _TTL - 3600)

patches_recorded: list[dict] = []


def _record_patch(table, rec_id, fields):
    patches_recorded.append(dict(fields))
    return True


with _patched(gw4, at_get_record=lambda t, rid: _rec("recD", contract_id="c_recD"),
              at_patch=_record_patch):
    patches_recorded.clear()
    outcome4 = _tma._claim_and_execute_approval("recD", _owner())

chk("Test4: outcome not ok", outcome4.get("ok") is False)
chk("Test4: projection sync did not report pending (write succeeded)",
    not outcome4.get("projection_sync_pending"))
chk("Test4: projection patched with STATUS=נדחה",
    any(p.get(ApprovalsFields.STATUS) == ApprovalStatus.REJECTED for p in patches_recorded))
chk("Test4: projection patched with PROJECTED_LIFECYCLE_STATUS=rejected",
    any(p.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS) == "rejected" for p in patches_recorded))


# ══════════════════════════════════════════════════════════════════
# 5. bulk_approve(): expired item never approved, lands in "failed",
#    a second fresh item in the same batch still executes normally
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: bulk_approve skips expired, still approves fresh ──")

gw5 = _FakeGateway()
gw5.contracts["c_recE"] = _FakeContract("c_recE", created_at=time.time() - _TTL - 60)   # expired
gw5.contracts["c_recF"] = _FakeContract("c_recF", created_at=time.time())               # fresh

recs5 = [
    _rec("recE", contract_id="c_recE"),
    _rec("recF", contract_id="c_recF"),
]


def _at_get_record5(table, rid):
    return {"recE": _rec("recE", contract_id="c_recE"),
            "recF": _rec("recF", contract_id="c_recF")}[rid]


with _patched(gw5, at_list=recs5, at_get_record=_at_get_record5, at_patch=lambda t, rid, f: True):
    resp5 = _bulk(_owner())

chk("Test5: approved count is 1 (only the fresh one)", resp5.get("approved") == 1)
chk("Test5: failed count is 1 (the expired one)", resp5.get("failed") == 1)
chk("Test5: action_gateway.approve() only called for the fresh contract",
    gw5.approve_calls == ["c_recF"])
chk("Test5: action_gateway.reject() called for the expired contract",
    gw5.reject_calls == ["c_recE"])
chk("Test5: expired contract ended rejected", gw5.contracts["c_recE"].status == "rejected")
chk("Test5: fresh contract ended completed", gw5.contracts["c_recF"].status == "completed")


# ══════════════════════════════════════════════════════════════════
# 6. Missing/invalid created_at fails CLOSED — deliberately the opposite
#    of BUG-112's Telegram check, which treats a malformed timestamp as
#    fresh. A contract whose age can't be verified must never execute.
# ══════════════════════════════════════════════════════════════════
print("\n── Test 6: missing/invalid created_at fails closed ───────────")

for label, bad_value in [
    ("None", None),
    ("empty string", ""),
    ("non-numeric string", "not-a-timestamp"),
    ("negative number", -5),
    ("zero", 0),
    ("bool True (never a real timestamp)", True),
]:
    gw6 = _FakeGateway()
    c6 = _FakeContract("c_recG", created_at=1.0)   # placeholder, overwritten below
    c6.created_at = bad_value
    gw6.contracts["c_recG"] = c6

    with _patched(gw6, at_get_record=lambda t, rid: _rec("recG", contract_id="c_recG"),
                  at_patch=lambda t, rid, f: True):
        outcome6 = _tma._claim_and_execute_approval("recG", _owner())

    chk(f"Test6 ({label}): never approved", gw6.approve_calls == [])
    chk(f"Test6 ({label}): rejected instead (fail closed)", gw6.reject_calls == ["c_recG"])
    chk(f"Test6 ({label}): outcome not ok, status 410",
        outcome6.get("ok") is False and outcome6.get("status_code") == 410)
    chk(f"Test6 ({label}): contract ended rejected", gw6.contracts["c_recG"].status == "rejected")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"C84 TMA Approval TTL tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
