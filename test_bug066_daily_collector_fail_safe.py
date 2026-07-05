# test_bug066_daily_collector_fail_safe.py — BUG-066 (BUG-DAILY-01)
#
# daily_collector.py had no per-step isolation: only the LLM call was
# try/except-wrapped (history fetch and message formatting were not), and
# scheduler.py's job wrapper caught everything in one blanket except with no
# per-step start/success/error logging. Fix: every real step (fetch history,
# LLM analyze/parse, format message, send) is now isolated with its own
# try/except and explicit logging; collect_daily()/send_daily_collector()
# never raise regardless of which step fails, and bot.send_message() now
# has an explicit timeout so a network stall can't hang the single
# scheduler thread.
#
# Acceptance test (from the bug report): run Daily Tasks with one faulty
# step -> the error is logged, the run completes (no crash/no hang),
# nothing is silently dropped.

import logging

import daily_collector


def test_history_fetch_failure_does_not_crash_collect_daily(monkeypatch, caplog):
    """Step 1 (fetch history) failing must not raise past collect_daily()."""
    import memory_store

    def _boom(memory_key):
        raise RuntimeError("memory store unavailable")

    monkeypatch.setattr(memory_store.memory, "get_for_claude", _boom)

    with caplog.at_level(logging.ERROR):
        result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == {"items": [], "all_clear": True}
    assert "fetch history failed" in caplog.text


def test_llm_call_failure_does_not_crash_collect_daily(monkeypatch, caplog):
    """Step 2 (LLM analyze/parse) failing must not raise past collect_daily()."""
    import memory_store

    monkeypatch.setattr(
        memory_store.memory, "get_for_claude",
        lambda memory_key: [{"role": "user", "content": "שילמנו 5000 שח לספק אתמול, ולא בטוח בכלל שזה נרשם איפשהו במערכת"}],
    )
    monkeypatch.setattr(
        daily_collector, "call_anthropic_text",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Anthropic API timeout")),
    )

    with caplog.at_level(logging.ERROR):
        result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == {"items": [], "all_clear": True}
    assert "LLM analysis failed" in caplog.text


def test_malformed_llm_json_does_not_crash_collect_daily(monkeypatch, caplog):
    """A non-JSON LLM response is also a per-step failure, not a crash."""
    import memory_store

    monkeypatch.setattr(
        memory_store.memory, "get_for_claude",
        lambda memory_key: [{"role": "user", "content": "שילמנו 5000 שח לספק אתמול, ולא בטוח בכלל שזה נרשם איפשהו במערכת"}],
    )
    monkeypatch.setattr(daily_collector, "call_anthropic_text", lambda **kwargs: "not valid json at all")

    with caplog.at_level(logging.ERROR):
        result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == {"items": [], "all_clear": True}
    assert "LLM analysis failed" in caplog.text


def test_successful_run_logs_each_step_boundary(monkeypatch, caplog):
    """Positive path: step start/done logging is present (not just errors)."""
    import memory_store

    monkeypatch.setattr(
        memory_store.memory, "get_for_claude",
        lambda memory_key: [{"role": "user", "content": "שילמנו 5000 שח לספק אתמול, ולא בטוח בכלל שזה נרשם איפשהו במערכת"}],
    )
    monkeypatch.setattr(
        daily_collector, "call_anthropic_text",
        lambda **kwargs: '{"items": [], "all_clear": true}',
    )

    with caplog.at_level(logging.INFO):
        result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == {"items": [], "all_clear": True}
    assert "start — fetch history" in caplog.text
    assert "fetch history done — start LLM analysis" in caplog.text
    assert "LLM analysis done" in caplog.text


def test_format_step_failure_does_not_crash_send_daily_collector(monkeypatch, caplog):
    """Step 3 (format) failing must not raise past send_daily_collector(), and must not attempt to send."""
    monkeypatch.setattr(daily_collector, "collect_daily", lambda memory_key: {"items": [{"status": "unclear"}], "all_clear": False})
    monkeypatch.setattr(
        daily_collector, "format_collector_message",
        lambda result: (_ for _ in ()).throw(RuntimeError("formatting exploded")),
    )

    sent = []

    class _FakeBot:
        def send_message(self, *a, **kw):
            sent.append((a, kw))

    with caplog.at_level(logging.ERROR):
        daily_collector.send_daily_collector(_FakeBot(), "chat1", "boss_hq:eliyahu")

    assert sent == [], "must never attempt to send after a format failure"
    assert "format נכשל" in caplog.text


def test_send_step_failure_does_not_crash_and_is_logged(monkeypatch, caplog):
    """Step 4 (send) failing must not raise past send_daily_collector()."""
    monkeypatch.setattr(daily_collector, "collect_daily", lambda memory_key: {"items": [{"status": "unclear", "text": "x"}], "all_clear": False})

    class _FailingBot:
        def send_message(self, *a, **kw):
            raise RuntimeError("Telegram API down")

    with caplog.at_level(logging.ERROR):
        daily_collector.send_daily_collector(_FailingBot(), "chat1", "boss_hq:eliyahu")  # must not raise

    assert "שגיאת שליחה" in caplog.text


def test_send_uses_explicit_timeout():
    """BUG-066: bot.send_message must be called with an explicit timeout so a
    network stall can't hang the single-threaded scheduler."""
    calls = []

    class _RecordingBot:
        def send_message(self, chat_id, message, parse_mode=None, timeout=None):
            calls.append({"chat_id": chat_id, "timeout": timeout})

    result = {"items": [{"status": "unclear", "text": "לקוח חדש התקשר"}], "all_clear": False}
    import daily_collector as dc
    orig_collect = dc.collect_daily
    dc.collect_daily = lambda memory_key: result
    try:
        dc.send_daily_collector(_RecordingBot(), "chat1", "boss_hq:eliyahu")
    finally:
        dc.collect_daily = orig_collect

    assert len(calls) == 1
    assert calls[0]["timeout"] == dc._SEND_TIMEOUT
    assert calls[0]["timeout"] is not None


def test_all_clear_result_never_calls_send():
    """Regression guard: when nothing needs review, no message is sent at all."""
    sent = []

    class _FakeBot:
        def send_message(self, *a, **kw):
            sent.append((a, kw))

    import daily_collector as dc
    orig_collect = dc.collect_daily
    dc.collect_daily = lambda memory_key: {"items": [], "all_clear": True}
    try:
        dc.send_daily_collector(_FakeBot(), "chat1", "boss_hq:eliyahu")
    finally:
        dc.collect_daily = orig_collect

    assert sent == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
