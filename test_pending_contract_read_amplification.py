#!/usr/bin/env python3
"""
test_pending_contract_read_amplification.py — Case C read-amplification
regression, mirroring test_session_snapshot.py's LL-11 pattern.

Production baseline comparison (2026-07-14 vs 2026-07-15) found a plain
greeting turn went from 1 pending-ActionContract read to 3: the pre-existing
ingress-gate check (app._apply_ingress_context_gate ->
ActionGateway.is_own_resolution_event -> find_live_contracts) plus two new
Phase 0 reads (app._build_and_log_turn_envelope at "1.7" and the Case C2
signal check after sanitize_agent_response()).

Fix: establish ONE per-turn snapshot ("1.65" in run_agent(), or threaded in
from the webhook handler's own single fetch) and reuse it everywhere within
that turn — never a new mechanism, never cached across turns/requests.

These tests exercise run_agent() directly (like LL-11's own tests), since
that is where Phase 0's two added reads live and where this regression is
provable without mocking the full webhook/Telegram stack.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-readamp-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:READAMP_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patReadAmpTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appReadAmpTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402
from context import AgentContext  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
import session_store  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _fake_anthropic_response(text: str, tool_use: dict | None = None):
    blocks = [SimpleNamespace(type="text", text=text)]
    if tool_use:
        blocks.append(SimpleNamespace(
            type="tool_use", id="tu1", name=tool_use["name"], input=tool_use["input"],
        ))
    return SimpleNamespace(
        content=blocks,
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _run_agent_counting_live_contract_reads(
    chat_id: str, user_text: str, *, live_contracts_snapshot=None,
    anthropic_response=None, anthropic_responses=None,
):
    """Drives app.run_agent() end-to-end (Identity/Router/Anthropic mocked,
    same pattern as test_session_snapshot.py/test_a32_enforcement.py) while
    counting real calls to ActionGateway.find_live_contracts() — the only
    function that reads pending ActionContracts."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key=f"readamptest:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    calls = []
    real_find = action_gateway.find_live_contracts

    def _counting(*a, **kw):
        calls.append(a)
        return real_find(*a, **kw)

    kwargs = {}
    if live_contracts_snapshot is not None:
        kwargs["_live_contracts_snapshot"] = live_contracts_snapshot

    create_kwargs = (
        {"side_effect": anthropic_responses} if anthropic_responses is not None
        else {"return_value": anthropic_response or _fake_anthropic_response("שלום! איך אפשר לעזור?")}
    )

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create", **create_kwargs), \
         patch.object(action_gateway, "find_live_contracts", side_effect=_counting), \
         patch.object(session_store.lead_sessions, "get", return_value=None):
        reply = app.run_agent(user_text, chat_id, channel="telegram", **kwargs)

    return calls, reply


# ══════════════════════════════════════════════════
# Core regression: greeting turn read count
# ══════════════════════════════════════════════════

calls_no_snapshot, _ = _run_agent_counting_live_contract_reads("readamp_t1", "שלום")
chk(
    "greeting turn, run_agent() called WITHOUT a pre-fetched snapshot (e.g. "
    "a recursive/legacy caller) -> falls back to exactly 1 internal read, "
    "never 2 (the pre-fix regression)",
    len(calls_no_snapshot) == 1,
)

calls_with_snapshot, _ = _run_agent_counting_live_contract_reads(
    "readamp_t2", "שלום", live_contracts_snapshot=[],
)
chk(
    "greeting turn, run_agent() called WITH a pre-fetched snapshot (the "
    "webhook handler's own single fetch, threaded through) -> 0 additional "
    "internal reads",
    len(calls_with_snapshot) == 0,
)

# ══════════════════════════════════════════════════
# Sessions read count must remain untouched by this fix (LL-11)
# ══════════════════════════════════════════════════

_session_calls = []


def _run_agent_counting_sessions(chat_id: str):
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key=f"readamptest:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    calls = []

    def _counting_get(sender):
        calls.append(sender)
        return None

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response("שלום! איך אפשר לעזור?")), \
         patch.object(session_store.lead_sessions, "get", side_effect=_counting_get):
        app.run_agent("שלום", chat_id, channel="telegram")
    return calls


_sessions = _run_agent_counting_sessions("readamp_t3")
chk("Sessions remains exactly 1 read per turn (LL-11 untouched by this fix)",
    len(_sessions) == 1)

# ══════════════════════════════════════════════════
# A turn that creates a contract must not trigger a second query for the
# post-turn Case C2 check — tracked via local state (tool_results_log's
# __approval_queued__ sentinel), not a re-read.
# ══════════════════════════════════════════════════

_mutating_responses = [
    _fake_anthropic_response(
        "", tool_use={"name": "airtable_add", "input": {"table": "Tasks", "fields": {"Task": "בדיקה"}}},
    ),
    _fake_anthropic_response("בסדר, זה ממתין לאישור שלך."),
]
calls_mutating, reply_mutating = _run_agent_counting_live_contract_reads(
    "readamp_t4", "תוסיף משימה בדיקה", live_contracts_snapshot=[],
    anthropic_responses=_mutating_responses,
)
chk(
    "a turn that creates a new ActionContract performs exactly 1 proposal-"
    "boundary read to enforce BUG-122 before persistence",
    len(calls_mutating) == 1,
)
chk("the mutating turn's reply reflects the queued approval (sanity check, not a hallucination)",
    "ממתין" in reply_mutating or "⏳" in reply_mutating)


# ══════════════════════════════════════════════════
# TurnEnvelope output must be unaffected by the fix — same fields, same
# values, whether the snapshot is threaded in or fetched internally.
# ══════════════════════════════════════════════════

with patch("core.turn_envelope.log_turn_envelope") as _mock_log_a:
    app._build_and_log_turn_envelope(
        Identity(user_id="u1", role=Role.OWNER), "chat-1", None,
        live_contracts_snapshot=[],
    )
    _envelope_a = _mock_log_a.call_args[0][0]

with patch("core.action_gateway.action_gateway") as _mock_gw_b, \
     patch("core.turn_envelope.log_turn_envelope") as _mock_log_b:
    _mock_gw_b.find_live_contracts.return_value = []
    app._build_and_log_turn_envelope(
        Identity(user_id="u1", role=Role.OWNER), "chat-1", None,
    )
    _envelope_b = _mock_log_b.call_args[0][0]

chk("TurnEnvelope output is identical whether the snapshot is passed in or fetched internally",
    _envelope_a.to_log_dict() == _envelope_b.to_log_dict())


print(f"\n{'='*50}")
print(f"pending-contract read-amplification tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
