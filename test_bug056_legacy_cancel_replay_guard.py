#!/usr/bin/env python3
"""
test_bug056_legacy_cancel_replay_guard.py — PR Hotfix B regression test.

CodeRabbit finding on PR #494 (BUG-151): app.py's legacy BUG-056 cancel-word
call site (~line 3391, `elif _lower in _CANCEL_WORDS:` inside the "2.55
Confirm-word + canonical tool-approval intercept" section) called
`ActionGateway.route_cancellation_word(identity.memory_key)` without an
explicit `recent_terminal` argument. That left the sentinel default
(`_TERMINAL_LOOKUP_UNSET`) in effect, which falls back to
`ExecutionLedger.find_most_recent_by_user()` — an UNBOUNDED-age lookup, not
even the 24h-bounded one PR2's own resolver uses. This is the same bug class
BUG-151 fixed for PR2's deterministic resolver (a bare confirm/cancel word
with no live contract must never replay a terminal contract by recency
alone) — and this legacy path is the one that actually runs by default,
since FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS is off in production.

Fix: app.py now passes `recent_terminal=None` explicitly at this call site,
matching the zero-recency-inference rule already applied to PR2's resolver.

This file proves two things:
  1. The exact call shape app.py now uses (`recent_terminal=None`) does NOT
     replay an old, unrelated terminal contract when there are no live
     contracts — regardless of how recent that terminal contract is.
  2. The OLD call shape (sentinel default, i.e. omitting the kwarg
     entirely) DID replay it — demonstrating this is a real behavior
     change, not a no-op kwarg addition.
  3. A wiring check on app.py's own source confirms the fixed call site is
     what actually ships, guarding against an accidental future revert to
     the bare `route_cancellation_word(identity.memory_key)` form.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug056-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG056_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug056Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug056Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _old_unrelated_contract(age_seconds: float) -> ActionContract:
    return ActionContract(
        contract_id="bug056-old-unrelated",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:bug056-owner",
        tool_name="airtable_add",
        normalized_payload={"table": "Leads", "fields": {}},
        business_action_fingerprint="fp-bug056-old-unrelated",
        origin_channel="telegram",
        origin_chat_id="bug056",
        requires_approval=True,
        status="completed",
        created_at=time.time() - age_seconds,
    )


# ── 1/2: functional contrast — fixed call shape vs. the old buggy default ──
for age_seconds, label in ((20, "20s old"), (7 * 24 * 3600, "7 days old")):
    gw = ActionGateway(ledger=ExecutionLedger())
    gw._ledger.save(_old_unrelated_contract(age_seconds))

    fixed_reply = gw.route_cancellation_word("boss_hq:bug056-owner", recent_terminal=None)
    chk(f"fixed call shape (recent_terminal=None): no replay of unrelated contract ({label})",
        fixed_reply is None)

    old_buggy_reply = gw.route_cancellation_word("boss_hq:bug056-owner")
    chk(f"OLD call shape (sentinel default, no kwarg): DOES replay the unrelated contract "
        f"({label}) -- proves this is a real fix, not a no-op",
        old_buggy_reply is not None and "הושלמה" in old_buggy_reply)


# ── 3: wiring check on app.py's own source (AST-based, not regex — a
# regex can't tell a real call from the same text inside a comment/string,
# and is sensitive to harmless reformatting) ────────────────────────────
_tree = ast.parse(inspect.getsource(app))


def _is_legacy_cancel_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "route_cancellation_word"
        and isinstance(func.value, ast.Name)
        and func.value.id == "_gw_cancel"
    )


_legacy_call_nodes = [n for n in ast.walk(_tree) if _is_legacy_cancel_call(n)]
chk("exactly one _gw_cancel.route_cancellation_word(...) call site exists in app.py",
    len(_legacy_call_nodes) == 1)

_recent_terminal_is_none_constant = False
if _legacy_call_nodes:
    for kw in _legacy_call_nodes[0].keywords:
        if kw.arg == "recent_terminal":
            _recent_terminal_is_none_constant = (
                isinstance(kw.value, ast.Constant) and kw.value.value is None
            )
chk("app.py's legacy BUG-056 cancel-word call site passes recent_terminal=None explicitly "
    "(AST-verified keyword value, not a text match)",
    _recent_terminal_is_none_constant)


print(f"\n{'='*50}")
print(f"BUG-056 legacy cancel replay guard tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
