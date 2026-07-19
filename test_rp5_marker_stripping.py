# test_rp5_marker_stripping.py — BUG-RP5-MARKER-NOT-STRIPPED regression suite.
#
# Staging integration bug found while sampling real RP5 evidence: a
# confirmation reply carrying the [rp5-test:...] marker ("מאשר
# [rp5-test:write-403]") was never recognized as a confirmation at all —
# is_own_resolution_event()/app.py's _CONFIRM_WORDS both do an EXACT string
# match, which the trailing marker breaks. The ingress gate then marked the
# pending ActionContract context_interrupted, the message fell through to
# the general Agent path, and no [RP5FaultInjection] log or dispatch_tool
# call ever happened — RP5 samples could not be produced through a real
# confirm flow at all.
#
# Fix: core/rp5_fault_injection.py's begin_turn() (and the new stateless
# clean_text_for_routing() for the one consumer — the Telegram ingress
# gate — that necessarily runs before begin_turn()) now strip the marker
# out of the text before it reaches any routing/classification/business-
# field-extraction consumer, while still activating the turn's fault state
# from the ORIGINAL text. A companion fix switches the per-turn contextvar
# from a single value to a stack, so a nested/recursive run_agent() call
# (e.g. the Stage-A pending-approval retry) restores the outer turn's fault
# state on return instead of clobbering it to None (BUG-RP5-NESTED-TURN-
# CLOBBER) — a write dispatched by the outer turn after such a nested call
# must never silently lose RP5 protection.
#
# Does not touch RP5/F52 taxonomy, EvidenceFinalizer, or ActionGateway's
# actual approve/reject/dispatch semantics — only what TEXT those consumers
# see, and how the fault-injection turn state survives nested calls.
# Staging-only; this branch is not merged.

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-rp5-marker-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:RP5_MARKER_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRp5MarkerTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRp5MarkerTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import pytest

from core import rp5_fault_injection as rp5
from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor
from identity import Identity

import app as _app


_OWNER = Identity(
    user_id="eliyahu", role="owner", tenant_id="boss_hq",
    external_id="1", channel="telegram",
)
_CANONICAL = _OWNER.memory_key
_RAW = "מאשר [rp5-test:write-403]"


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    for var in (
        "APP_ENV", "RP5_FAULT_INJECTION_ENABLED", "RP5_FAULT_ALLOWLIST",
        "RP5_FAULT_REQUIRE_MARKER", "RP5_FAULT_MARKER_PREFIX",
    ):
        monkeypatch.delenv(var, raising=False)
    rp5.end_turn()
    yield
    rp5.end_turn()


def _enable_staging(monkeypatch, *, allowlist: str = _CANONICAL) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", allowlist)


# ══════════════════════════════════════════════════
# 1. Marker stripped before route_confirmation_word / is_own_resolution_event
# ══════════════════════════════════════════════════

def test_begin_turn_strips_marker_to_exact_confirm_word(monkeypatch):
    _enable_staging(monkeypatch)
    cleaned = rp5.begin_turn(_CANONICAL, _RAW)
    assert cleaned == "מאשר"
    assert cleaned.lower() in _app._CONFIRM_WORDS


def test_raw_marker_text_does_not_match_confirm_words():
    """Proves the bug existed: the RAW text is not a recognized confirm
    word (exact-match breaks on the trailing marker)."""
    assert _RAW.strip().lower() not in _app._CONFIRM_WORDS


def test_clean_text_for_routing_matches_begin_turn_result(monkeypatch):
    """The stateless preview used by the webhook's ingress-gate call (which
    runs BEFORE begin_turn()/run_agent()) must agree with what begin_turn()
    itself would compute for the SAME (env, user, text) — otherwise the
    ingress gate and the real activation could disagree."""
    _enable_staging(monkeypatch)
    preview = rp5.clean_text_for_routing(_CANONICAL, _RAW)
    rp5.end_turn()  # clean_text_for_routing must not have pushed anything
    activated = rp5.begin_turn(_CANONICAL, _RAW)
    assert preview == activated == "מאשר"


def test_is_own_resolution_event_recognizes_cleaned_marker_confirmation(monkeypatch):
    """Direct proof for the exact consumer named in the bug report:
    core.action_gateway.action_gateway.is_own_resolution_event() (called by
    app.py's Telegram ingress-context-gate, BEFORE run_agent()) must
    recognize the cleaned text as a genuine resolution event — the raw
    marker-carrying text must not."""
    _enable_staging(monkeypatch)
    ledger = ExecutionLedger()
    gw = ActionGateway(ledger=ledger, tool_executor=lambda *a, **kw: {"ok": True})
    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=_CANONICAL,
        tool_name="airtable_add",
        tool_inputs={"table": "Contacts", "fields": {"name": "Test"}},
        origin_channel="telegram", origin_chat_id=_CANONICAL,
        requires_approval=True, identity=_OWNER,
    )
    assert result.ok is True
    live = gw.find_live_contracts(_CANONICAL)

    assert gw.is_own_resolution_event(_CANONICAL, _RAW, live=live) is False

    cleaned = rp5.clean_text_for_routing(_CANONICAL, _RAW)
    assert gw.is_own_resolution_event(_CANONICAL, cleaned, live=live) is True


# ══════════════════════════════════════════════════
# 2-4. Full integration: propose -> "מאשר [rp5-test:write-403]" -> approve
#      -> real dispatch_tool -> write-403 blocks it, no real Airtable call.
# ══════════════════════════════════════════════════

def test_marker_confirmation_approves_last_prompted_contract_and_blocks_real_write(monkeypatch):
    _enable_staging(monkeypatch)
    ledger = ExecutionLedger()
    gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=_CANONICAL,
        tool_name="airtable_add",
        tool_inputs={"table": "Contacts", "fields": {"name": "Test Contact"}},
        origin_channel="telegram", origin_chat_id=_CANONICAL,
        requires_approval=True, identity=_OWNER,
    )
    assert result.ok is True
    contract_id = result.contract_id

    # This is the exact reported confirmation message. begin_turn() both
    # activates the fault AND returns the cleaned text app.py must use for
    # confirmation routing (mirrors the fix in app.py's _run_agent_impl and
    # the Telegram webhook handler).
    cleaned = rp5.begin_turn(_CANONICAL, _RAW)
    assert cleaned == "מאשר"

    reply = gw.route_confirmation_word(_CANONICAL, approver_role="owner")

    contract = ledger.find_by_id(contract_id)
    # dispatch_tool received the active write-403 context (requirement:
    # "dispatch_tool receives active write-403 context") — the contract was
    # approved (route_confirmation_word did resolve it — "approves the last
    # prompted contract") but execution failed closed rather than writing
    # for real. The real Airtable write function is never even reached (the
    # RP5 check short-circuits before tools/dispatcher.py's `match name:`
    # dispatch) — proven directly and more strongly by the next test.
    assert contract is not None
    assert contract.status in ("failed", "outcome_unknown", "rejected")
    assert "⛔" not in reply  # not an authority-denial — it WAS approved
    assert "לא נמצא" not in reply  # not "contract not found"


def test_no_real_airtable_post_under_write_403(monkeypatch):
    """Stronger, more direct proof than the test above: the real HTTP-
    calling Airtable function is mocked to raise if it's ever invoked at
    all — dispatch_tool's RP5 injection point (before the `match name:`
    dispatch) must short-circuit before reaching it."""
    _enable_staging(monkeypatch)
    ledger = ExecutionLedger()
    gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

    from unittest.mock import patch
    with patch("tools.airtable_tools.airtable_add") as mock_add:
        mock_add.side_effect = AssertionError("real airtable_add must never run under write-403")

        result = gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=_CANONICAL,
            tool_name="airtable_add",
            tool_inputs={"table": "Contacts", "fields": {"name": "Test Contact 2"}},
            origin_channel="telegram", origin_chat_id=_CANONICAL,
            requires_approval=True, identity=_OWNER,
        )
        assert result.ok is True

        rp5.begin_turn(_CANONICAL, _RAW)
        gw.route_confirmation_word(_CANONICAL, approver_role="owner")

        mock_add.assert_not_called()


# ══════════════════════════════════════════════════
# 5. Marker never leaks into a business payload
# ══════════════════════════════════════════════════

def test_marker_does_not_appear_in_normalized_payload(monkeypatch):
    """Simulates a marker embedded in the SAME message used to build a
    task's fields (not just a separate confirm message) — the cleaned text
    app.py's _run_agent_impl now uses for the rest of the turn must never
    let the marker reach an ActionContract's normalized tool_inputs."""
    _enable_staging(monkeypatch)
    raw_task_text = "צור משימה זכייה במונדיאל [rp5-test:write-403] עד ה-20/07"
    cleaned = rp5.begin_turn(_CANONICAL, raw_task_text)
    assert "[rp5-test:" not in cleaned

    ledger = ExecutionLedger()
    gw = ActionGateway(ledger=ledger, tool_executor=lambda *a, **kw: {"ok": True})
    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=_CANONICAL,
        tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": cleaned}},
        origin_channel="telegram", origin_chat_id=_CANONICAL,
        requires_approval=True, identity=_OWNER, user_text=cleaned,
    )
    assert result.ok is True
    contract = ledger.find_by_id(result.contract_id)
    assert "[rp5-test:" not in str(contract.normalized_payload)


# ══════════════════════════════════════════════════
# 6. Production / gate-inert paths — byte-identical, marker never stripped
# ══════════════════════════════════════════════════

def test_production_env_marker_never_stripped(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", _CANONICAL)
    assert rp5.begin_turn(_CANONICAL, _RAW) == _RAW
    assert rp5.clean_text_for_routing(_CANONICAL, _RAW) == _RAW
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is None


def test_staging_but_disabled_marker_never_stripped(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "false")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", _CANONICAL)
    assert rp5.begin_turn(_CANONICAL, _RAW) == _RAW
    assert rp5.clean_text_for_routing(_CANONICAL, _RAW) == _RAW


def test_staging_enabled_not_allowlisted_marker_never_stripped(monkeypatch):
    _enable_staging(monkeypatch, allowlist="boss_hq:someone_else")
    assert rp5.begin_turn(_CANONICAL, _RAW) == _RAW
    assert rp5.clean_text_for_routing(_CANONICAL, _RAW) == _RAW


# ══════════════════════════════════════════════════
# 7. Defense-in-depth: nested/recursive run_agent() call must not clobber
#    the outer turn's fault state (BUG-RP5-NESTED-TURN-CLOBBER) — required
#    by "fail safe rather than silently executing the real write."
# ══════════════════════════════════════════════════

def test_nested_turn_does_not_clobber_outer_fault_state(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _RAW)  # outer turn: write-403 active
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is not None

    # Simulates app.py's Stage-A pending-approval retry:
    # "return run_agent(pending_entry['text'], ...)" — a nested run_agent()
    # call, on unrelated, marker-free text.
    rp5.begin_turn(_CANONICAL, "אשר את הפעולה הקודמת")
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is None
    rp5.end_turn()  # the nested call's own cleanup

    # Back in the outer turn — the fault must still be active, not clobbered.
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is not None
    rp5.end_turn()  # outer cleanup
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
