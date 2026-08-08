#!/usr/bin/env python3
"""
test_tc6_app_reply_ownership.py — TC6 integrator regression suite.

Covers the app.py cutover that completes TC6 (docs/architecture/
turn-coordinator-full/TC6_APP_INTEGRATOR_PATCH_SPEC.md): exact-contract
correlation -> ActionLifecycleResult from that exact contract -> explicit
reply ownership -> exactly one final speaker when FEATURE_SINGLE_SPEAKER_
APPROVAL_UX is enabled.

Two levels of proof, matching the round-2 review correction that a
producer-level dict shape alone is not enough:

  * PRODUCER level — _queue_approval_detailed_impl()/_ownership_for_
    contract_or_none() build the correct dict shape (message/terminal_
    outcome/reply_owner/action_lifecycle_result) for Branch A (canonical
    Gateway ownership) and Branch B (correlated turn, ownership
    verification failed).

  * TOOL LOOP level — run_agent() itself (Identity/Router/Context/
    Anthropic mocked, app._queue_approval_detailed() mocked to return a
    given producer-shaped dict) actually reacts to that dict: Branch A/
    Branch B both hard-return before a second Claude API call, before
    tool_calls_made increments, and before any Agent text can escape.
"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-tc6-app-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TC6_APP_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patTc6AppTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTc6AppTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402
from core.router.ownership_contracts import ActionLifecycleResult  # noqa: E402
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger  # noqa: E402
from context import AgentContext  # noqa: E402

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
# Fixture helpers
# ══════════════════════════════════════════════════════════════════

def _lifecycle(reply_owner: str = "gateway", state: str = "pending", contract_ref: str = "c1"):
    return ActionLifecycleResult(
        contract_ref=contract_ref, lifecycle_state=state, approval_state=state,
        execution_state="not_started", reply_owner=reply_owner,
    )


def _tool_use_response(tool_name="airtable_add", tool_input=None, tool_use_id="tu_1"):
    return SimpleNamespace(
        content=[SimpleNamespace(
            type="tool_use", id=tool_use_id, name=tool_name,
            input=tool_input or {"table": "Tasks", "fields": {"Task": "בדיקת TC6"}},
        )],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
        stop_reason="tool_use",
    )


_SECOND_TURN_AGENT_TEXT = (
    "טקסט Agent מהסבב השני — אסור שייצא אם ה-Gateway (או Branch B) בעל התשובה."
)


def _text_response(text: str = _SECOND_TURN_AGENT_TEXT):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
        stop_reason="end_turn",
    )


def _branch_a_outcome(
    *, owner_notified: bool = False, message: str = "🅰️ טקסט-Gateway: הפעולה ממתינה לאישור.",
    contract_id: str = "contract-a-1",
):
    lifecycle = SimpleNamespace(safe_user_message=message, canonical_state="pending")
    return {
        "message": message,
        "contract_id": contract_id,
        "ok": True,
        "terminal_outcome": None,
        "action_tool": "airtable_add",
        "created_this_turn": True,
        "owner_notified": owner_notified,
        "reply_owner": "gateway",
        "lifecycle_result": lifecycle,
        "action_lifecycle_result": _lifecycle(reply_owner="gateway", contract_ref=contract_id),
        "final_response_count": 1,
    }


def _branch_b_outcome(
    *, owner_notified: bool = False, message: str = "🅱️ טקסט-Gateway-ישן-בטוח: הפעולה כבר קיימת.",
    contract_id: str = "contract-b-1",
):
    # Deliberately NO "reply_owner" / "action_lifecycle_result" /
    # "lifecycle_result" keys — matches _queue_approval_detailed_impl()'s
    # actual Branch B return shape exactly (see app.py).
    return {
        "message": message,
        "contract_id": contract_id,
        "ok": False,
        "terminal_outcome": app._APPROVAL_OWNERSHIP_VERIFICATION_FAILED,
        "action_tool": "airtable_add",
        "created_this_turn": False,
        "owner_notified": owner_notified,
        "final_response_count": 1,
    }


def _no_contract_outcome(message: str = "⚠️ פעולה זו כבר בוצעה לאחרונה. כפילות נחסמה."):
    # Matches a genuine "no contract at all" branch (duplicate fingerprint /
    # cross-channel dedup) — no reply_owner/action_lifecycle_result keys,
    # but ALSO no APPROVAL_OWNERSHIP_VERIFICATION_FAILED marker. Must never
    # be mistaken for Branch A or Branch B.
    return {
        "message": message,
        "contract_id": None,
        "ok": False,
        "terminal_outcome": "APPROVAL_QUEUE_ERROR",
        "action_tool": "airtable_add",
        "created_this_turn": False,
    }


def _run_agent_tool_loop(
    approval_outcome: dict, *, chat_id: str, flag_on: bool = True,
    out_meta: dict | None = None, pa01_state: str = "off",
):
    """
    Drives the real app.run_agent() end-to-end with Identity/Router/Context/
    Anthropic mocked, and app._queue_approval_detailed() mocked to return
    the given producer-shaped outcome dict — proving the TOOL LOOP's own
    Branch A/Branch B derivation reacts to it, not merely that the dict
    itself has the right shape.
    """
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test system prompt", allowed_tools=[],
        memory_key=f"tc6apptest:{chat_id}", max_tokens=500,
        model="claude-haiku-test", identity_label="owner",
    )
    create_mock = MagicMock(side_effect=[_tool_use_response(), _text_response()])

    def _flag(name):
        if name == "FEATURE_SINGLE_SPEAKER_APPROVAL_UX":
            return flag_on
        return False

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app, "_queue_approval_detailed", return_value=approval_outcome), \
         patch.object(app, "_flag_enabled", side_effect=_flag), \
         patch("feature_flags.get_pa01_enforcement_state", return_value=pa01_state), \
         patch.object(app.client.messages, "create", create_mock):
        reply = app.run_agent(
            "צור משימת בדיקת TC6", chat_id, channel="telegram", _out_meta=out_meta,
        )
    return reply, create_mock


def _identity_owner(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


# ══════════════════════════════════════════════════════════════════
# A. Branch A — canonical Gateway ownership (tool-loop level)
# ══════════════════════════════════════════════════════════════════
print("── A. Branch A — canonical Gateway ownership ──")

# 1. exact current-turn contract projection with gateway owner suppresses
#    further Agent output.
_reply_a1, _mock_a1 = _run_agent_tool_loop(
    _branch_a_outcome(message="A1-GATEWAY-TEXT"), chat_id="tc6_a1",
)
chk("1. Branch A: reply is the Gateway text, not Agent-generated text",
    _reply_a1 == "A1-GATEWAY-TEXT")
chk("1. Branch A: reply is NOT the second-turn Agent text",
    _reply_a1 != _SECOND_TURN_AGENT_TEXT)

# 2. Agent-generated conflicting text never escapes — the second Claude
#    call (whose text would contradict the Gateway's own state) is never
#    even made.
chk("2. Branch A: no second Claude API call happens (Agent never gets a "
    "chance to contradict the Gateway)",
    _mock_a1.call_count == 1)

# 3. owner_notified=True -> suppress duplicate channel reply.
_reply_a3, _mock_a3 = _run_agent_tool_loop(
    _branch_a_outcome(owner_notified=True, message="A3-GATEWAY-TEXT"), chat_id="tc6_a3",
)
chk("3. Branch A: owner_notified=True -> returns '' (no duplicate send)",
    _reply_a3 == "")
chk("3. Branch A: owner_notified=True -> still exactly one Claude call",
    _mock_a3.call_count == 1)

# 4. owner_notified=False -> exactly one legacy safe_user_message.
_reply_a4, _ = _run_agent_tool_loop(
    _branch_a_outcome(owner_notified=False, message="A4-GATEWAY-TEXT"), chat_id="tc6_a4",
)
chk("4. Branch A: owner_notified=False -> exactly one safe_user_message returned",
    _reply_a4 == "A4-GATEWAY-TEXT")

# 5. final_response_count == 1.
_out_meta_a5: dict = {}
_run_agent_tool_loop(
    _branch_a_outcome(message="A5-GATEWAY-TEXT"), chat_id="tc6_a5", out_meta=_out_meta_a5,
)
chk("5. Branch A: out_meta['final_response_count'] == 1",
    _out_meta_a5.get("final_response_count") == 1)
chk("5. Branch A: out_meta['reply_owner'] == 'gateway'",
    _out_meta_a5.get("reply_owner") == "gateway")

# 6. stale/unrelated contract for same user cannot own this turn (producer/
#    app.py-integration-seam level — app._ownership_for_contract_or_none()
#    is the exact helper the tool-loop's Branch A/B derivation depends on
#    transitively via _queue_approval_detailed_impl()).
_gw6 = ActionGateway(ledger=ExecutionLedger())
_stale = ActionContract(
    contract_id="stale-A", tenant_id="boss_hq", canonical_user_id="boss_hq:owner-6",
    tool_name="airtable_add", normalized_payload={"table": "Tasks", "fields": {"a": 1}},
    business_action_fingerprint="fp-stale-A", origin_channel="telegram",
    origin_chat_id="chat-6", requires_approval=True, status="rejected",
    created_at=time.time() - 300,
)
_current = ActionContract(
    contract_id="current-B", tenant_id="boss_hq", canonical_user_id="boss_hq:owner-6",
    tool_name="airtable_add", normalized_payload={"table": "Tasks", "fields": {"b": 2}},
    business_action_fingerprint="fp-current-B", origin_channel="telegram",
    origin_chat_id="chat-6", requires_approval=True, status="pending",
    created_at=time.time() - 5,
)
_gw6._ledger.save(_stale)
_gw6._ledger.save(_current)
_result6 = app._ownership_for_contract_or_none(_gw6, "current-B")
chk("6. app._ownership_for_contract_or_none() resolves the exact touched "
    "contract (current-B), not a stale/unrelated one (stale-A)",
    _result6 is not None and _result6.contract_ref == "current-B")
chk("6. resolved lifecycle_state reflects the CURRENT contract's real "
    "status ('pending'), not the stale one's ('rejected')",
    _result6.lifecycle_state == "pending")


# ══════════════════════════════════════════════════════════════════
# B. Branch B — correlated turn, ownership verification failed
# ══════════════════════════════════════════════════════════════════
print("\n── B. Branch B — ownership verification failed (safety stop) ──")


class _RaisingRepository:
    def get(self, contract_id: str):
        raise RuntimeError("simulated repository outage")


class _NoneReturningGateway:
    """Simulates reply_ownership_for_contract() returning an unexpected
    None (clean, not-found style) rather than raising."""

    def reply_ownership_for_contract(self, contract_id):
        return None


# 7. exact-contract ownership read RAISES -> _ownership_for_contract_or_none
#    returns None (never propagates, never fabricates) -> the producer-
#    shaped Branch B dict -> the tool loop's deterministic early return ->
#    no subsequent Agent round.
_gw7 = ActionGateway(ledger=ExecutionLedger(repository=_RaisingRepository()))
_result7 = app._ownership_for_contract_or_none(_gw7, "some-contract")
chk("7a. ownership read RAISES -> _ownership_for_contract_or_none() "
    "returns None (never propagates, never fabricates)",
    _result7 is None)

_reply_7, _mock_7 = _run_agent_tool_loop(
    _branch_b_outcome(message="B7-SAFE-LEGACY-TEXT"), chat_id="tc6_b7",
)
chk("7b. Branch B (raise-case shape): reply is the already-computed safe "
    "legacy text, not Agent text",
    _reply_7 == "B7-SAFE-LEGACY-TEXT")
chk("7c. Branch B: no subsequent Agent round (only one Claude API call)",
    _mock_7.call_count == 1)

# 8. exact-contract ownership read returns an unexpected None -> identical
#    Branch B behavior.
_result8 = app._ownership_for_contract_or_none(_NoneReturningGateway(), "some-contract")
chk("8a. ownership read returns unexpected None -> _ownership_for_contract_"
    "or_none() also surfaces None (same as the raise-case)",
    _result8 is None)

_reply_8, _mock_8 = _run_agent_tool_loop(
    _branch_b_outcome(message="B8-SAFE-LEGACY-TEXT"), chat_id="tc6_b8",
)
chk("8b. Branch B (None-case shape): reply is the safe legacy text",
    _reply_8 == "B8-SAFE-LEGACY-TEXT")
chk("8c. Branch B (None-case shape): no subsequent Agent round",
    _mock_8.call_count == 1)

# 9. owner_notified=True on Branch B -> no duplicate reply.
_reply_9, _mock_9 = _run_agent_tool_loop(
    _branch_b_outcome(owner_notified=True, message="B9-TEXT"), chat_id="tc6_b9",
)
chk("9. Branch B: owner_notified=True -> returns '' (no duplicate send)",
    _reply_9 == "")
chk("9. Branch B: owner_notified=True -> still exactly one Claude call",
    _mock_9.call_count == 1)

# 10. owner_notified=False on Branch B -> exactly one existing safe message.
_reply_10, _ = _run_agent_tool_loop(
    _branch_b_outcome(owner_notified=False, message="B10-TEXT"), chat_id="tc6_b10",
)
chk("10. Branch B: owner_notified=False -> exactly one safe message returned",
    _reply_10 == "B10-TEXT")

# 11. Branch B final_response_count == 1, and no positive reply_owner claim
#     is made (telemetry correction — never 'unverified', never 'gateway').
_out_meta_11: dict = {}
_run_agent_tool_loop(
    _branch_b_outcome(message="B11-TEXT"), chat_id="tc6_b11", out_meta=_out_meta_11,
)
chk("11a. Branch B: out_meta['final_response_count'] == 1",
    _out_meta_11.get("final_response_count") == 1)
chk("11b. Branch B: out_meta carries NO positive reply_owner claim "
    "('gateway') and NOT the rejected 'unverified' wording",
    _out_meta_11.get("reply_owner") not in ("gateway", "unverified"))
chk("11c. Branch B: separate observability field ownership_verification=="
    "'failed' is present instead of a reply_owner claim",
    _out_meta_11.get("ownership_verification") == "failed")

# 12. Branch B does not depend on PA-01 state — off/shadow/enforce must all
#     behave identically (the early return happens structurally, before
#     PA-01's own separate code is ever reached).
_pa01_results = {}
for _pa01_state in ("off", "shadow", "enforce"):
    _reply_12, _mock_12 = _run_agent_tool_loop(
        _branch_b_outcome(message="B12-TEXT"), chat_id=f"tc6_b12_{_pa01_state}",
        pa01_state=_pa01_state,
    )
    _pa01_results[_pa01_state] = (_reply_12, _mock_12.call_count)
chk("12. Branch B: identical reply text across PA-01 off/shadow/enforce",
    len({r for r, _ in _pa01_results.values()}) == 1
    and next(iter(_pa01_results.values()))[0] == "B12-TEXT")
chk("12. Branch B: identical single-Claude-call count across PA-01 "
    "off/shadow/enforce (never reaches PA-01's own code)",
    all(count == 1 for _, count in _pa01_results.values()))


# ══════════════════════════════════════════════════════════════════
# C. Shared authority — enforcement and observability never disagree
# ══════════════════════════════════════════════════════════════════
print("\n── C. Shared authority ──")

# 13. sentinel presence alone cannot claim Gateway ownership — a
#     __approval_queued__ entry with NO action_lifecycle_result/reply_owner
#     at all (a genuine "no contract" branch) must let the Agent continue
#     normally, not be mistaken for Branch A or Branch B.
_reply_13, _mock_13 = _run_agent_tool_loop(_no_contract_outcome(), chat_id="tc6_c13")
chk("13a. sentinel-only entry (no ownership claim) -> Agent DOES get a "
    "second round (not suppressed)",
    _mock_13.call_count == 2)
chk("13b. sentinel-only entry -> final reply is the Agent's own (second-"
    "turn) text, not a fabricated Gateway/Branch-B text",
    _reply_13 == _SECOND_TURN_AGENT_TEXT)

# 14. scalar reply_owner, if retained, always equals the typed
#     ActionLifecycleResult.reply_owner — producer-level proof using a
#     REAL rejected contract through the real _queue_approval_detailed_impl()
#     BUG-162 generic block (mirrors test_bug162_gateway_reply_owner_on_
#     generic_block.py's own setup).
_identity14 = _identity_owner("tc6_owner_14")
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
_propose14 = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=_identity14.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": "TC6-14"}},
    origin_channel="telegram", origin_chat_id=_identity14.user_id,
    requires_approval=True, identity=_identity14, trusted_source="agent",
)
assert _propose14.ok, f"setup propose failed: {_propose14.reason}"
_reject14 = _real_gw.reject(_propose14.contract_id, rejected_by="test_user")
assert _reject14.startswith("🚫"), f"setup reject failed: {_reject14}"

with patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"), \
     patch.object(app, "resolve_identity", side_effect=lambda channel, ext_id: _identity14):
    _outcome14 = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"כותרת המשימה": "TC6-14"}},
        _identity14.user_id, "telegram", "נסה שוב", trusted_source="agent",
    )
chk("14a. real rejected-contract outcome carries a typed action_lifecycle_result",
    _outcome14.get("action_lifecycle_result") is not None)
chk("14b. scalar reply_owner == typed action_lifecycle_result.reply_owner "
    "(never independently hardcoded)",
    _outcome14.get("reply_owner") == _outcome14["action_lifecycle_result"].reply_owner)

# 15. enforcement (Branch A/B) and OwnershipSignal (observability) derive
#     from the SAME typed action_lifecycle_result — proven with the flag
#     OFF (so the early-return never fires and OwnershipSignal code IS
#     reached), a Branch-A-shaped tool_results_log entry present.
import core.turn_envelope as _turn_envelope_module  # noqa: E402
_real_build_ownership_signal = _turn_envelope_module.build_ownership_signal
_signal_spy = MagicMock(side_effect=_real_build_ownership_signal)
with patch.object(_turn_envelope_module, "build_ownership_signal", _signal_spy):
    _reply_15, _mock_15 = _run_agent_tool_loop(
        _branch_a_outcome(message="C15-TEXT"), chat_id="tc6_c15", flag_on=False,
    )
chk("15a. flag OFF -> Branch A early return does not fire (Agent gets a "
    "second round)", _mock_15.call_count == 2)
chk("15b. OwnershipSignal was actually built (observability path reached)",
    _signal_spy.call_count >= 1)
chk("15c. OwnershipSignal's reply_owner agrees with the SAME typed "
    "action_lifecycle_result Branch A itself would have used ('gateway')",
    _signal_spy.call_args.kwargs.get("reply_owner") == "gateway")

# 16. no synthetic ActionLifecycleResult is constructed anywhere in app.py —
#     structural guard: app.py must never call the constructor directly,
#     only ever read .reply_owner off a result obtained via
#     ActionGateway.reply_ownership_for_contract() (WS2's canonical
#     projection).
with open(os.path.join(os.path.dirname(__file__) or ".", "app.py"), encoding="utf-8") as _f:
    _app_source = _f.read()
chk("16. app.py source never directly instantiates ActionLifecycleResult(...)",
    "ActionLifecycleResult(" not in _app_source)


# ══════════════════════════════════════════════════════════════════
# D. Flag / rollback — FEATURE_SINGLE_SPEAKER_APPROVAL_UX
# ══════════════════════════════════════════════════════════════════
print("\n── D. Flag / rollback ──")

# 17. FEATURE_SINGLE_SPEAKER_APPROVAL_UX OFF: legacy behavior unchanged for
#     BOTH a Branch-A-shaped AND a Branch-B-shaped entry — an ownership
#     projection failure must not introduce a NEW blocking behavior when
#     the flag is off.
_reply_17a, _mock_17a = _run_agent_tool_loop(
    _branch_a_outcome(message="D17A-TEXT"), chat_id="tc6_d17a", flag_on=False,
)
chk("17a. flag OFF + Branch-A-shaped entry -> Agent still gets a second "
    "round (legacy behavior, unchanged)", _mock_17a.call_count == 2)
chk("17a. flag OFF + Branch-A-shaped entry -> final reply is the Agent's "
    "own text", _reply_17a == _SECOND_TURN_AGENT_TEXT)

_reply_17b, _mock_17b = _run_agent_tool_loop(
    _branch_b_outcome(message="D17B-TEXT"), chat_id="tc6_d17b", flag_on=False,
)
chk("17b. flag OFF + Branch-B-shaped entry (ownership verification failed) "
    "-> does NOT newly block -> Agent still gets a second round",
    _mock_17b.call_count == 2)
chk("17b. flag OFF + Branch-B-shaped entry -> final reply is the Agent's "
    "own text, not a safety-stop text", _reply_17b == _SECOND_TURN_AGENT_TEXT)

# 18. FEATURE_SINGLE_SPEAKER_APPROVAL_UX ON: both Branch A and Branch B
#     suppress the Agent via their own deterministic early return (explicit
#     combined confirmation — individually proven in tests 1-2 and 7-8 above).
_reply_18a, _mock_18a = _run_agent_tool_loop(
    _branch_a_outcome(message="D18A-TEXT"), chat_id="tc6_d18a", flag_on=True,
)
_reply_18b, _mock_18b = _run_agent_tool_loop(
    _branch_b_outcome(message="D18B-TEXT"), chat_id="tc6_d18b", flag_on=True,
)
chk("18a. flag ON + Branch A -> exactly one Claude call, Gateway text returned",
    _mock_18a.call_count == 1 and _reply_18a == "D18A-TEXT")
chk("18b. flag ON + Branch B -> exactly one Claude call, safety-stop text returned",
    _mock_18b.call_count == 1 and _reply_18b == "D18B-TEXT")


print()
print("=" * 60)
print(f"TC6 app.py integrator (reply ownership) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
