# test_session_snapshot.py — LL-11 regression: Sessions read exactly once per request
#
# Production log on Render (b8739a2, 2026-06-30 11:25) showed 3 separate
# Airtable Sessions GETs for one greeting/read_only request: the request-scoped
# snapshot load in run_agent (app.py "1.6") plus two independent fallback
# re-fetches inside resolve_context_pronouns()/_build_tool_context() whenever
# the snapshot came back None. Fix: those two functions no longer fall back to
# fetching — the caller (run_agent) is the only place allowed to read.

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-ll11-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LL11_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patLL11Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLL11Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402
from context import AgentContext  # noqa: E402
import session_store  # noqa: E402


def _fake_anthropic_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _run_agent_counting_sessions_get(chat_id: str, user_text: str, session_snapshot):
    """Drives the real app.run_agent() end-to-end (Identity/Router/Anthropic
    mocked, like test_a32_enforcement.py) while counting real calls to
    session_store.lead_sessions.get() — the only function allowed to touch
    Airtable's Sessions table."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt  = "test system prompt",
        allowed_tools  = [],
        memory_key     = f"ll11test:{chat_id}",
        max_tokens     = 500,
        model          = "claude-haiku-test",
        identity_label = "owner",
    )
    calls = []
    real_get = session_store.lead_sessions.get

    def _counting_get(sender):
        calls.append(sender)
        return session_snapshot

    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(app.client.messages, "create",
                       return_value=_fake_anthropic_response("שלום! איך אפשר לעזור?")), \
         patch.object(session_store.lead_sessions, "get", side_effect=_counting_get):
        app.run_agent(user_text, chat_id, channel="telegram")

    return calls


# ══════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════

def test_01_existing_session_single_read():
    """LL-11 core acceptance: a known sender with an existing session
    triggers exactly one lead_sessions.get() per request."""
    existing_session = {
        "domain": "general", "step": 0, "answers": {}, "done": False,
        "last_tool_result": None, "last_uploaded_file": None,
    }
    calls = _run_agent_counting_sessions_get("ll11_t1", "שלום", existing_session)
    assert len(calls) == 1, f"Expected 1 Sessions GET, got {len(calls)}: {calls}"
    return "✅ Test 01: existing session → exactly 1 Sessions GET"


def test_02_no_session_yet_still_single_read():
    """The actual LL-11 failure mode: snapshot load returns None (cache miss /
    no session yet). Before the fix, resolve_context_pronouns() and
    _build_tool_context() each independently re-fetched on a None snapshot,
    producing 3 reads total. Must still be exactly 1."""
    calls = _run_agent_counting_sessions_get("ll11_t2", "שלום", None)
    assert len(calls) == 1, f"Expected 1 Sessions GET even on cache miss, got {len(calls)}: {calls}"
    return "✅ Test 02: snapshot miss (None) → still exactly 1 Sessions GET (LL-11 regression)"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def run():
    tests = [
        test_01_existing_session_single_read,
        test_02_no_session_yet_still_single_read,
    ]
    passed = failed = 0

    print("\nLL-11 Session Snapshot Regression Tests")
    print("═" * 45)

    for t in tests:
        try:
            msg = t()
            print(msg)
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            failed += 1

    print(f"\n{'═' * 45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
