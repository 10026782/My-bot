"""Focused parity tests for the INTERACTION_INTELLIGENCE scheduler gate."""

from __future__ import annotations

import inspect
import sys
import types

import feature_flags
import scheduler


def _run_scheduler_gate(monkeypatch, raw_value: str | None) -> bool:
    if raw_value is None:
        monkeypatch.delenv("INTERACTION_INTELLIGENCE", raising=False)
    else:
        monkeypatch.setenv("INTERACTION_INTELLIGENCE", raw_value)
    feature_flags._RUNTIME.pop("INTERACTION_INTELLIGENCE", None)

    calls = []

    class Result:
        processed = []
        skipped = 0
        errors = []

    fake_engine = types.SimpleNamespace(
        send_upcoming_reminders=lambda _chat_id: calls.append("reminders"),
        run_interaction_scan=lambda **_kwargs: calls.append("scan") or Result(),
    )
    monkeypatch.setitem(sys.modules, "interaction_engine", fake_engine)
    monkeypatch.setenv("DIGEST_CHAT_ID", "test-chat")

    expected = feature_flags.is_enabled("INTERACTION_INTELLIGENCE")
    scheduler._job_interaction_scan()
    assert bool(calls) is expected
    return expected


def test_interaction_flag_unset_and_false_are_off(monkeypatch):
    assert _run_scheduler_gate(monkeypatch, None) is False
    assert _run_scheduler_gate(monkeypatch, "false") is False


def test_interaction_flag_truthy_values_match_consumer(monkeypatch):
    for value in ("true", "1", "yes", "on", "enabled"):
        assert _run_scheduler_gate(monkeypatch, value) is True


def test_scheduler_uses_canonical_accessor_not_direct_env_parsing():
    source = inspect.getsource(scheduler._job_interaction_scan)
    assert 'from feature_flags import is_enabled' in source
    assert 'os.getenv("INTERACTION_INTELLIGENCE"' not in source
