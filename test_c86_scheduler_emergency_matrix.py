"""C86 regression matrix for the scheduler-wide emergency stop."""

from __future__ import annotations

from collections import defaultdict

import feature_flags
import lead_memory
import scheduler
import shabbat_guard


SCHEDULER_JOB_NAMES = (
    "_job_daily_digest",
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


def test_emergency_stop_matrix_blocks_every_registered_scheduler_job(monkeypatch):
    calls = defaultdict(int)
    emergency = {"active": True}

    scheduler.schedule.clear()
    monkeypatch.setattr(scheduler.threading, "Thread", _NoopThread)
    monkeypatch.setattr(shabbat_guard, "shabbat_safe", lambda job: job)
    monkeypatch.setattr(
        feature_flags,
        "is_enabled",
        lambda name: emergency["active"] if name == "EMERGENCY_STOP_AUTOMATION" else True,
    )

    for job_name in SCHEDULER_JOB_NAMES:
        monkeypatch.setattr(scheduler, job_name, _counter(calls, job_name))
    monkeypatch.setattr(
        lead_memory,
        "job_flush_lead_memory",
        _counter(calls, "job_flush_lead_memory"),
    )

    try:
        scheduler.start_scheduler()
        registered_jobs = tuple(scheduler.schedule.jobs)
        expected_names = (*SCHEDULER_JOB_NAMES, "job_flush_lead_memory")

        assert len(registered_jobs) == len(expected_names) == 22

        for job in registered_jobs:
            job.job_func()
        assert {name: calls[name] for name in expected_names} == {
            name: 0 for name in expected_names
        }

        emergency["active"] = False
        for job in registered_jobs:
            job.job_func()
        assert {name: calls[name] for name in expected_names} == {
            name: 1 for name in expected_names
        }
    finally:
        scheduler.schedule.clear()


def test_automation_guard_fails_closed_when_flag_lookup_errors(monkeypatch):
    calls = []

    def fail_flag_lookup(name):
        raise RuntimeError("flag backend unavailable")

    monkeypatch.setattr(feature_flags, "is_enabled", fail_flag_lookup)
    guarded = scheduler._automation_guard(lambda: calls.append("ran"), name="matrix_probe")

    assert guarded() is None
    assert calls == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
