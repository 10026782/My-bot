"""Focused tests for FEATURE_WEEKLY_SUMMARY scheduler registration."""

from __future__ import annotations

import feature_flags
import lead_memory
import scheduler
import shabbat_guard


class _NoopThread:
    def __init__(self, *args, name=None, **kwargs):
        self.name = name

    def start(self):
        return None


def _register_names(monkeypatch, raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        monkeypatch.delenv("FEATURE_WEEKLY_SUMMARY", raising=False)
    else:
        monkeypatch.setenv("FEATURE_WEEKLY_SUMMARY", raw_value)
    feature_flags._RUNTIME.pop("FEATURE_WEEKLY_SUMMARY", None)

    def named_guard(func, *, name=None):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__name__ = name or func.__name__
        return wrapper

    monkeypatch.setattr(scheduler.threading, "Thread", _NoopThread)
    monkeypatch.setattr(scheduler, "_automation_guard", named_guard)
    monkeypatch.setattr(shabbat_guard, "shabbat_safe", lambda job: job)
    monkeypatch.setattr(lead_memory, "job_flush_lead_memory", lambda: None)

    scheduler.schedule.clear()
    try:
        scheduler.start_scheduler()
        return tuple(job.job_func.__name__ for job in scheduler.schedule.jobs)
    finally:
        scheduler.schedule.clear()


def test_weekly_summary_flag_off_does_not_register_job(monkeypatch):
    names = _register_names(monkeypatch, None)
    assert "weekly_summary" not in names


def test_weekly_summary_flag_on_registers_once(monkeypatch):
    names = _register_names(monkeypatch, "true")
    assert names.count("weekly_summary") == 1


def test_repeated_scheduler_setup_keeps_existing_registration_contract(monkeypatch):
    monkeypatch.setenv("FEATURE_WEEKLY_SUMMARY", "true")
    feature_flags._RUNTIME.pop("FEATURE_WEEKLY_SUMMARY", None)
    monkeypatch.setattr(scheduler.threading, "Thread", _NoopThread)
    monkeypatch.setattr(scheduler, "_automation_guard", lambda func, *, name=None: func)
    monkeypatch.setattr(shabbat_guard, "shabbat_safe", lambda job: job)
    monkeypatch.setattr(lead_memory, "job_flush_lead_memory", lambda: None)

    scheduler.schedule.clear()
    try:
        scheduler.start_scheduler()
        first_names = [job.job_func.__name__ for job in scheduler.schedule.jobs]
        scheduler.start_scheduler()
        second_names = [job.job_func.__name__ for job in scheduler.schedule.jobs]
        assert second_names == first_names
        assert second_names.count("_job_weekly_summary") == 1
    finally:
        scheduler.schedule.clear()


def test_weekly_flag_does_not_change_unrelated_registration(monkeypatch):
    off = set(_register_names(monkeypatch, "false"))
    on = set(_register_names(monkeypatch, "true"))
    assert on - {"weekly_summary"} == off
