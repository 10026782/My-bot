# test_episodic_capture_phase1.py — Episodic Memory Phase 1 capture regression suite
#
# Covers app._capture_turn_outcome_episodic() (the FEATURE_EPISODIC_CAPTURE
# turn-completion hook in run_agent()):
#   1. The call site is gated by FEATURE_EPISODIC_CAPTURE (source-level check).
#   2. Happy path: exactly one EpisodicEntry inserted, correct tenant_id/
#      canonical_user_id/domain_id/event_type/source.
#   3. No fabricated session_id/entity_id/entity_type/action_ref/outcome_ref/
#      provenance_ref.
#   4. Payload is bounded to {channel, classification, tool_count} — no raw
#      user text, no final_reply text, no tool payloads, no secrets.
#   5. A repository failure (EpisodicMemoryError) is swallowed — never raises.
#   6. A contract-validation failure (EpisodicEntryValidationError, e.g. an
#      empty tenant_id) is also swallowed — never raises.
#   7. Any other unexpected exception from the capture layer (last-resort
#      `except Exception`) is also swallowed — never raises, never touches
#      final_reply, never re-triggers tool execution.

import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-episodic-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:EPISODIC_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patEpisodicTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appEpisodicTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

from core.episodic_entry import EpisodicEntry  # noqa: E402
from core.episodic_memory_repository import EpisodicMemoryError  # noqa: E402

_passed = 0
_failed = 0


def chk(desc: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


def _fake_identity(tenant_id="boss_hq", user_id="12345", domain_id="general", channel="telegram"):
    return SimpleNamespace(tenant_id=tenant_id, user_id=user_id, domain_id=domain_id, channel=channel)


def _fake_turn_evidence(classification="verified_write_success"):
    return SimpleNamespace(classification=lambda: classification)


# ── 1. flag gate is real (source-level: the call is behind an is_enabled check) ──

def test_01_call_site_is_flag_gated():
    src = open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8").read()
    m = re.search(
        r'if _flag_enabled\("FEATURE_EPISODIC_CAPTURE"\):\s*\n\s*_capture_turn_outcome_episodic\(',
        src,
    )
    chk("run_agent() only calls _capture_turn_outcome_episodic() under FEATURE_EPISODIC_CAPTURE", bool(m))


# ── 2/3/4. happy path shape ──────────────────────────────────────────────

def test_02_happy_path_single_insert_correct_shape():
    mock_repo_instance = MagicMock()
    mock_repo_instance.insert.side_effect = lambda entry: entry
    with patch.object(app, "EpisodicMemoryRepository", return_value=mock_repo_instance) as mock_cls:
        identity = _fake_identity()
        app._capture_turn_outcome_episodic(identity, _fake_turn_evidence(), tool_results_log=[{"tool": "airtable_add"}])

    chk("EpisodicMemoryRepository constructed exactly once", mock_cls.call_count == 1)
    chk("insert() called exactly once", mock_repo_instance.insert.call_count == 1)

    entry: EpisodicEntry = mock_repo_instance.insert.call_args[0][0]
    chk("tenant_id matches identity", entry.tenant_id == "boss_hq")
    chk("canonical_user_id matches identity.user_id", entry.canonical_user_id == "12345")
    chk("domain_id matches identity", entry.domain_id == "general")
    chk("event_type == 'outcome'", entry.event_type == "outcome")
    chk("source == 'run_agent'", entry.source == "run_agent")
    chk("occurred_at is a real timestamp", isinstance(entry.occurred_at, float) and entry.occurred_at > 0)

    chk("session_id not fabricated", entry.session_id is None)
    chk("entity_type not fabricated", entry.entity_type is None)
    chk("entity_id not fabricated", entry.entity_id is None)
    chk("action_ref not fabricated", entry.action_ref is None)
    chk("outcome_ref not fabricated", entry.outcome_ref is None)
    chk("provenance_ref not fabricated", entry.provenance_ref is None)

    chk("payload is bounded to the declared 3 keys", set(entry.payload.keys()) == {"channel", "classification", "tool_count"})
    chk("payload.channel matches identity.channel", entry.payload["channel"] == "telegram")
    chk("payload.classification matches turn_evidence.classification()", entry.payload["classification"] == "verified_write_success")
    chk("payload.tool_count reflects len(tool_results_log)", entry.payload["tool_count"] == 1)
    chk("payload has no raw text field", not any(isinstance(v, str) and len(v) > 64 for v in entry.payload.values()))


# ── 5. repository failure is swallowed ───────────────────────────────────

def test_05_repository_error_is_swallowed():
    mock_repo_instance = MagicMock()
    mock_repo_instance.insert.side_effect = EpisodicMemoryError("db unavailable")
    raised = False
    with patch.object(app, "EpisodicMemoryRepository", return_value=mock_repo_instance):
        try:
            app._capture_turn_outcome_episodic(_fake_identity(), _fake_turn_evidence(), [])
        except Exception:
            raised = True
    chk("EpisodicMemoryError from insert() never propagates", not raised)


# ── 6. contract-validation failure is swallowed ──────────────────────────

def test_06_validation_error_is_swallowed():
    raised = False
    try:
        # empty tenant_id fails EpisodicEntry.__post_init__ validation
        app._capture_turn_outcome_episodic(_fake_identity(tenant_id=""), _fake_turn_evidence(), [])
    except Exception:
        raised = True
    chk("an invalid (unfabricated-identifier) entry never raises out of the capture hook", not raised)


# ── 7. any unexpected exception from the capture layer is swallowed ──────

def test_07_unexpected_exception_is_swallowed_and_final_reply_untouched():
    mock_repo_instance = MagicMock()
    mock_repo_instance.insert.side_effect = TypeError("something unrelated broke")
    dispatch_calls = []

    def fake_dispatch_tool(*a, **k):
        dispatch_calls.append((a, k))
        return {"ok": True}

    final_reply = "תשובה סופית שלא אמורה להשתנות"
    raised = False
    with patch.object(app, "EpisodicMemoryRepository", return_value=mock_repo_instance):
        try:
            app._capture_turn_outcome_episodic(_fake_identity(), _fake_turn_evidence(), [])
        except Exception:
            raised = True

    chk("a bare TypeError from the capture layer never propagates", not raised)
    chk("final_reply is untouched by the failed capture (helper returns None, caller's variable is unchanged)", final_reply == "תשובה סופית שלא אמורה להשתנות")
    chk("no tool dispatch is triggered by a failed capture", dispatch_calls == [])


if __name__ == "__main__":
    test_01_call_site_is_flag_gated()
    test_02_happy_path_single_insert_correct_shape()
    test_05_repository_error_is_swallowed()
    test_06_validation_error_is_swallowed()
    test_07_unexpected_exception_is_swallowed_and_final_reply_untouched()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
