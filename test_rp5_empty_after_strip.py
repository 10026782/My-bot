# test_rp5_empty_after_strip.py — BUG-RP5-EMPTY-AFTER-STRIP regression suite.
#
# Staging integration bug found while sampling real RP5 evidence: sending
# ONLY a marker ("[rp5-test:write-validation-400]", no other text) strips
# down to an empty string (core/rp5_fault_injection.py's begin_turn()).
# That empty string was never checked before being embedded as the
# Anthropic user message's content ("app.py"'s `messages = history +
# [{"role": "user", "content": clean_msg}]`) — Anthropic's API itself
# rejected it ("messages.14: user messages must have non-empty content"),
# surfacing as a raw Anthropic 400 instead of being handled locally.
#
# Fix: app.py's _run_agent_impl() checks immediately after begin_turn()
# reassigns user_text (before router/context/tool-loop/Anthropic) — if the
# cleaned text is empty, return a safe local response without ever calling
# the model, calling a tool, or touching ActionGateway. This is a general
# invariant (Anthropic must never receive empty message content), not an
# RP5-specific behavior change — it was simply unreachable before RP5
# could legitimately produce an empty user_text.
#
# Does not touch RP5/F52 taxonomy, EvidenceFinalizer classification logic,
# or ActionGateway semantics — only adds a guard for a text shape that
# could not previously occur. Staging-only scenario; this branch is not
# merged.

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-rp5-empty-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:RP5_EMPTY_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRp5EmptyTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRp5EmptyTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import pytest
from unittest.mock import patch

from core import rp5_fault_injection as rp5
from identity import Identity, Role
from core.router.route_decision import RouteDecision
from context import AgentContext

import app as _app


_OWNER = Identity(
    user_id="eliyahu", role="owner", tenant_id="boss_hq",
    external_id="1", channel="telegram",
)
_CANONICAL = _OWNER.memory_key


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


def _explode_if_called(*args, **kwargs):
    raise AssertionError("Anthropic must never be called for a marker-only, empty-after-strip turn")


def _run(user_text: str) -> str:
    """Drives the real app.run_agent() end-to-end. Identity/Router/Context
    are mocked (same harness as test_a32_enforcement.py /
    test_rp5_marker_stripping.py) but app.client.messages.create is mocked
    to RAISE if invoked at all — the strongest possible proof that no
    Anthropic call happens for this turn shape. dispatch_tool is also
    mocked to raise, proving no tool call either. Always uses _OWNER/
    _CANONICAL so the identity's memory_key matches RP5_FAULT_ALLOWLIST."""
    fake_ctx = AgentContext(
        system_prompt="test system prompt", allowed_tools=[],
        memory_key=_CANONICAL, max_tokens=500,
        model="claude-haiku-test", identity_label="owner",
    )
    with patch.object(_app, "resolve_identity", return_value=_OWNER), \
         patch.object(_app, "_safe_route", return_value=RouteDecision()), \
         patch.object(_app, "build_context", return_value=fake_ctx), \
         patch.object(_app, "dispatch_tool", side_effect=_explode_if_called), \
         patch.object(_app.client.messages, "create", side_effect=_explode_if_called):
        return _app.run_agent(user_text, _CANONICAL, channel="telegram")


def test_marker_only_message_never_reaches_anthropic(monkeypatch):
    _enable_staging(monkeypatch)
    reply = _run("[rp5-test:write-validation-400]")

    assert isinstance(reply, str)
    assert reply.strip() != ""
    assert reply == "לא זיהיתי תוכן לעיבוד בהודעה. שלח בקשה או שאלה."
    # No exception means neither client.messages.create nor dispatch_tool
    # (both wired to raise above) were ever called — proves no Anthropic
    # call, no tool call, no ActionGateway execution for this turn.


def test_marker_only_with_surrounding_whitespace_also_short_circuits(monkeypatch):
    _enable_staging(monkeypatch)
    reply = _run("   [rp5-test:write-validation-400]   ")
    assert reply == "לא זיהיתי תוכן לעיבוד בהודעה. שלח בקשה או שאלה."


def test_marker_only_logs_marker_only_reason_not_generic(monkeypatch, caplog):
    _enable_staging(monkeypatch)
    with caplog.at_level("INFO"):
        _run("[rp5-test:write-validation-400]")
    assert "marker_only_empty_after_strip" in caplog.text
    assert "empty_user_text_after_processing" not in caplog.text


def test_marker_only_produces_no_evidence_neutral_shadow_sample(monkeypatch, caplog):
    """Requirement: EvidenceFinalizerShadow still records a real sample for
    this turn shape (no_evidence + neutral, no mismatch) rather than being
    silently blind to it — RP5 sampling must not lose this data point."""
    _enable_staging(monkeypatch)
    monkeypatch.setenv("FEATURE_EVIDENCE_FINALIZER", "shadow")
    with caplog.at_level("INFO", logger="core.turn_evidence"):
        _run("[rp5-test:write-validation-400]")
    assert "[EvidenceFinalizerShadow]" in caplog.text
    assert "evidence_status=no_evidence" in caplog.text
    assert "response_claim=neutral" in caplog.text
    assert "mismatch=false" in caplog.text


def test_marker_with_real_content_is_unaffected(monkeypatch):
    """Regression: a marker attached to a REAL message (the normal,
    intended RP5 usage) must not be treated as empty-after-strip — only a
    bare marker with nothing else strips down to empty."""
    cleaned = rp5.clean_text_for_routing(_CANONICAL, "מאשר [rp5-test:write-403]")
    assert cleaned.strip() != ""


def test_non_staging_empty_message_still_short_circuits_safely(monkeypatch):
    """The empty-content guard is a general invariant, not RP5-gated —
    verified directly on the (rare, defense-in-depth) case of some other
    caller passing an already-empty user_text with no RP5 activity at all."""
    monkeypatch.setenv("APP_ENV", "production")
    reply = _run("   ")
    assert reply == "לא זיהיתי תוכן לעיבוד בהודעה. שלח בקשה או שאלה."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
