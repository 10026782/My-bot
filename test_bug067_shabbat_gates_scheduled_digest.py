# test_bug067_shabbat_gates_scheduled_digest.py — BUG-067 (BUG-DAILY-02)
#
# daily_digest.py only ever showed a Shabbat-mode text banner
# (shabbat_guard.shabbat_status_message()) inside the digest body — it never
# called the real gate (should_send_now()/shabbat_safe()), so the digest and
# daily_collector jobs kept running/sending on Shabbat/holidays exactly like
# any other day. Fix: scheduler.py now wraps _job_daily_digest and
# _job_daily_collector in shabbat_safe(), the same decorator already used
# for 6 other jobs (followup_scan, payment_reminders, lead_recovery,
# abandoned_scan, audience_report, interaction_scan).
#
# Scope guard: this fix must be gating-only. It must not touch
# build_digest()'s content, Airtable queries, scoring, leads, or formatting —
# this file asserts only registration/gating behavior, not digest content.

from __future__ import annotations

from collections import defaultdict

import lead_memory
import scheduler
import shabbat_guard

# Mirrors test_c86_scheduler_emergency_matrix.py's SCHEDULER_JOB_NAMES —
# every _job_* referenced in scheduler.py's registration block must be
# patched so calling all registered jobs is side-effect-free (no real
# Airtable/network calls) and only the two jobs under test matter.
SCHEDULER_JOB_NAMES = (
    "_job_daily_digest",
    "_job_daily_git_audit",
    "_job_schema_snapshot_archive",
    "_job_daily_collector",
    "_job_cleanup_pending",
    "_job_overdue_payments",
    "_job_followup_scan",
    "_job_payment_reminders",
    "_job_lead_recovery",
    "_job_learning_cycle",
    "_job_email_inbound",
    "_job_abandoned_scan",
    "_job_audience_report",
    "_job_attribution_report",
    "_job_interaction_scan",
    "_job_security_reminder",
    "_job_weekly_summary",
    "_job_daily_game_digest",
    "_job_weekly_quest_reset",
    "_job_boss_battle_check",
    "_job_cost_watchdog",
    "_job_daily_usage_report",
)


class _NoopThread:
    def __init__(self, *args, name=None, **kwargs):
        self.name = name

    def start(self):
        return None


def _counter(calls, name):
    def job():
        calls[name] += 1
    return job


def _register_jobs(monkeypatch, calls):
    scheduler.schedule.clear()
    monkeypatch.setattr(scheduler.threading, "Thread", _NoopThread)
    for job_name in SCHEDULER_JOB_NAMES:
        monkeypatch.setattr(scheduler, job_name, _counter(calls, job_name))
    monkeypatch.setattr(lead_memory, "job_flush_lead_memory", _counter(calls, "job_flush_lead_memory"))
    scheduler.start_scheduler()
    return tuple(scheduler.schedule.jobs)


def test_daily_digest_and_collector_skipped_on_shabbat(monkeypatch):
    """The real shabbat_safe() gate (not neutralized) must skip both jobs."""
    calls = defaultdict(int)
    monkeypatch.setattr(shabbat_guard, "should_send_now", lambda channel="default": False)

    try:
        registered = _register_jobs(monkeypatch, calls)
        assert len(registered) == len(SCHEDULER_JOB_NAMES) + 1  # +1 for job_flush_lead_memory

        for job in registered:
            job.job_func()

        assert calls["_job_daily_digest"] == 0, "daily_digest must be skipped on Shabbat/holiday"
        assert calls["_job_daily_collector"] == 0, "daily_collector must be skipped on Shabbat/holiday"
    finally:
        scheduler.schedule.clear()


def test_daily_digest_and_collector_still_run_when_not_shabbat(monkeypatch):
    """Regression guard: the gate must not block normal (non-Shabbat) days."""
    calls = defaultdict(int)
    monkeypatch.setattr(shabbat_guard, "should_send_now", lambda channel="default": True)

    try:
        registered = _register_jobs(monkeypatch, calls)
        for job in registered:
            job.job_func()

        assert calls["_job_daily_digest"] == 1, "daily_digest must still run on a normal day"
        assert calls["_job_daily_collector"] == 1, "daily_collector must still run on a normal day"
    finally:
        scheduler.schedule.clear()


def test_unrelated_jobs_unaffected_by_the_shabbat_gate(monkeypatch):
    """
    Scope guard: only daily_digest/daily_collector were newly gated.
    daily_git_audit, cleanup_pending, overdue_payments, flush_lead_memory,
    learning_cycle, and email_inbound were never gated by shabbat_safe and
    must remain that way — even when should_send_now() returns False.
    """
    calls = defaultdict(int)
    monkeypatch.setattr(shabbat_guard, "should_send_now", lambda channel="default": False)

    try:
        registered = _register_jobs(monkeypatch, calls)
        for job in registered:
            job.job_func()

        still_ungated = (
            "_job_daily_git_audit", "_job_cleanup_pending", "_job_overdue_payments",
            "job_flush_lead_memory", "_job_learning_cycle", "_job_email_inbound",
            "_job_attribution_report", "_job_security_reminder", "_job_weekly_summary",
            "_job_daily_game_digest", "_job_weekly_quest_reset", "_job_boss_battle_check",
            "_job_cost_watchdog", "_job_daily_usage_report",
        )
        for name in still_ungated:
            assert calls[name] == 1, f"{name} must remain ungated by Shabbat (unchanged scope), got calls={calls[name]}"

        already_gated = (
            "_job_followup_scan", "_job_payment_reminders", "_job_lead_recovery",
            "_job_abandoned_scan", "_job_audience_report", "_job_interaction_scan",
        )
        for name in already_gated:
            assert calls[name] == 0, f"{name} was already Shabbat-gated before this fix and must remain gated"
    finally:
        scheduler.schedule.clear()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
