from __future__ import annotations

import pytest

from core.owner_attention import OwnerAttentionItem, OwnerAttentionSources, build_owner_attention_projection


CHECKED_AT = "2026-08-16T00:00:00+00:00"


def sources(**overrides):
    defaults = {
        "approvals": lambda: {"pending_count": 0, "pending": []},
        "tasks": lambda: {"overdue_tasks": 0},
        "system_health": lambda: {"status": "ok", "active_emergency": []},
        "projects": lambda: {"hot_leads_count": 0, "projects": []},
        "marketing": lambda: {"count": 0, "demands": []},
        "ventures": lambda: {"active": 0, "total": 0, "stage_counts": {}},
    }
    defaults.update(overrides)
    return OwnerAttentionSources(**defaults)


def project(source_set):
    return build_owner_attention_projection(identity=object(), sources=source_set, checked_at=CHECKED_AT)


def test_all_successful_sources_without_attention_are_ok():
    result = project(sources())

    assert result.overall_state == "OK"
    assert result.items == ()
    assert {status.source for status in result.source_status} == {
        "approvals", "tasks", "system_health", "projects", "marketing", "ventures",
    }
    assert all(status.state == "CURRENT" for status in result.source_status)


def test_supported_attention_items_have_stable_keys_and_deterministic_order():
    result = project(sources(
        approvals=lambda: {"pending_count": 2, "pending": []},
        tasks=lambda: {"overdue_tasks": 3},
        system_health=lambda: {"status": "degraded", "active_emergency": []},
        projects=lambda: {"hot_leads_count": 4, "projects": []},
        marketing=lambda: {"demands": [{"pending_creative_count": 2}]},
        ventures=lambda: {"active": 5, "total": 6, "stage_counts": {"Research": 5}},
    ))

    assert result.overall_state == "ATTENTION"
    assert next(item for item in result.items if item.signal_key == "system.health.degraded").severity == "WARNING"
    assert [item.signal_key for item in result.items] == [
        "system.health.degraded",
        "approvals.pending",
        "tasks.overdue.global",
        "leads.hot.visible_domains",
        "marketing.pending_review",
        "ventures.active_summary",
    ]
    assert result.pending_decisions[0].signal_key == "approvals.pending"
    assert all(item.source_ref for item in result.items)


def test_failed_collector_isolated_and_projection_is_unknown_not_ok():
    def broken():
        raise RuntimeError("airtable unavailable")

    result = project(sources(marketing=broken))

    assert result.overall_state == "UNKNOWN"
    marketing_status = next(status for status in result.source_status if status.source == "marketing")
    assert marketing_status.state == "UNKNOWN"
    assert marketing_status.freshness == "unknown"
    assert marketing_status.reason == "source_read_failed:RuntimeError"
    assert all(status.source != "marketing" or status.state == "UNKNOWN" for status in result.source_status)


@pytest.mark.parametrize(
    ("source_name", "payload"),
    [
        ("approvals", {"pending_count": 0}),
        ("tasks", {"overdue_tasks": "0"}),
        ("projects", {"hot_leads_count": 0}),
        ("marketing", {"demands": [{"pending_creative_count": "0"}]}),
        ("ventures", {"active": 0, "total": 0}),
    ],
)
def test_malformed_payload_is_unknown_not_healthy_zero(source_name, payload):
    result = project(sources(**{source_name: lambda: payload}))

    status = next(item for item in result.source_status if item.source == source_name)
    assert status.state == "UNKNOWN"
    assert status.freshness == "unknown"
    assert status.reason.startswith("invalid_payload:")
    assert result.overall_state == "UNKNOWN"


@pytest.mark.parametrize("payload", [{"status": "unknown"}, {}, {"status": "bogus", "active_emergency": []}, None])
def test_system_health_unknown_or_invalid_status_is_unknown(payload):
    result = project(sources(system_health=lambda: payload))

    status = next(item for item in result.source_status if item.source == "system_health")
    assert status.state == "UNKNOWN"
    assert result.overall_state == "UNKNOWN"


def test_system_health_valid_ok_is_current_without_attention():
    result = project(sources(system_health=lambda: {"status": "ok", "active_emergency": []}))

    status = next(item for item in result.source_status if item.source == "system_health")
    assert status.state == "CURRENT"
    assert not any(item.category == "system" for item in result.items)
    assert result.overall_state == "OK"


def test_system_health_emergency_flag_is_current_critical_attention():
    result = project(sources(system_health=lambda: {"status": "ok", "active_emergency": ["STOP_ALL"]}))

    status = next(item for item in result.source_status if item.source == "system_health")
    item = next(item for item in result.items if item.signal_key == "system.emergency")
    assert status.state == "CURRENT"
    assert item.severity == "CRITICAL"
    assert result.overall_state == "ATTENTION"


def test_attention_dominates_unknown_but_unknown_source_is_preserved():
    result = project(sources(
        tasks=lambda: {"overdue_tasks": 1},
        marketing=lambda: {"demands": [{"pending_creative_count": "invalid"}]},
    ))

    assert result.overall_state == "ATTENTION"
    assert any(item.signal_key == "tasks.overdue.global" for item in result.items)
    marketing_status = next(item for item in result.source_status if item.source == "marketing")
    assert marketing_status.state == "UNKNOWN"


def test_overdue_tasks_are_global_and_not_project_scoped():
    result = project(sources(tasks=lambda: {"overdue_tasks": 1}))

    item = next(item for item in result.items if item.signal_key == "tasks.overdue.global")
    assert item.domain == "global"
    assert item.destination == "actions"
    assert item.canonicality == "derived"


def test_approval_preview_is_bounded_actionable_and_has_no_record_id():
    result = project(sources(approvals=lambda: {
        "pending_count": 4,
        "pending": [
            {"action": "שלח הודעה", "context_type": "lead", "actionable": True, "context_id": "rec-secret"},
            {"action": "עדכן משימה", "context_type": "task", "actionable": True, "context_id": "rec-secret-2"},
            {"action": "פעולה לא זמינה", "context_type": "legacy", "actionable": False, "context_id": "rec-secret-3"},
        ],
    }))

    previews = [item for item in result.pending_decisions if ".preview:" in item.signal_key]
    assert len(previews) == 2
    assert all(item.severity == "WARNING" for item in previews)
    assert all("rec-secret" not in item.signal_key for item in previews)
    assert all(item.destination == "approvals" for item in previews)


def test_system_emergency_is_critical_and_routes_to_system_health():
    result = project(sources(system_health=lambda: {"status": "emergency", "active_emergency": ["STOP_ALL"]}))

    item = next(item for item in result.items if item.signal_key == "system.emergency")
    assert item.severity == "CRITICAL"
    assert item.destination == "system_health"
    assert item.canonicality == "canonical"


def test_unsupported_signals_are_not_inferred_from_empty_payloads():
    result = project(sources(
        tasks=lambda: {},
        projects=lambda: {"projects": []},
        marketing=lambda: {"demands": [{}]},
        ventures=lambda: {"active": 0},
    ))

    keys = {item.signal_key for item in result.items}
    assert "tasks.due_soon.global" not in keys
    assert "leads.stale" not in keys
    assert "leads.missing_followup" not in keys
    assert "ventures.decision_overdue" not in keys


def test_invalid_contract_values_fail_closed():
    with pytest.raises(ValueError):
        OwnerAttentionItem(
            signal_key="x", domain="global", category="system", severity="INFO", state="GREEN",
            title="x", summary="x", reason="x", source_kind="api_read", source_name="x",
            source_ref="x", detected_at=CHECKED_AT, last_checked_at=CHECKED_AT,
            freshness="current", owner_action_required=False, destination="x", canonicality="canonical",
        )


# ══════════════════════════════════════════════════════════════════
# Regression: _default_sources().system_health() used to call the
# @require_tma_auth-decorated tma_api.system_health(identity) route
# function directly. The decorator's wrapper does
# `f(*args, identity=identity, **kwargs)`, so a positional `identity`
# already in args collided with the injected keyword and raised
# `TypeError: system_health() got multiple values for argument 'identity'`
# on every real Command Center read. The fix routes through the
# undecorated tma_api._system_health_payload(identity) helper instead.
# ══════════════════════════════════════════════════════════════════

class _FakeIdentity:
    is_owner = True


def test_default_sources_system_health_calls_undecorated_helper_without_typeerror(monkeypatch):
    import tma_api
    from core.owner_attention import _default_sources

    identity = _FakeIdentity()
    seen_identity = []

    def fake_payload(passed_identity):
        seen_identity.append(passed_identity)
        return {"status": "ok", "active_emergency": []}

    monkeypatch.setattr(tma_api, "_system_health_payload", fake_payload)

    result = _default_sources(identity).system_health()

    assert result == {"status": "ok", "active_emergency": []}
    assert seen_identity == [identity]


def test_default_sources_system_health_maps_healthy_result_into_projection(monkeypatch):
    import tma_api
    from core.owner_attention import _default_sources

    monkeypatch.setattr(
        tma_api, "_system_health_payload",
        lambda identity: {"status": "ok", "active_emergency": []},
    )

    real_source_set = _default_sources(_FakeIdentity())
    result = project(sources(system_health=real_source_set.system_health))

    status = next(item for item in result.source_status if item.source == "system_health")
    assert status.state == "CURRENT"
    assert not any(item.category == "system" for item in result.items)
    assert result.overall_state == "OK"


def test_default_sources_system_health_maps_emergency_result_into_projection(monkeypatch):
    import tma_api
    from core.owner_attention import _default_sources

    monkeypatch.setattr(
        tma_api, "_system_health_payload",
        lambda identity: {"status": "emergency", "active_emergency": ["EMERGENCY_STOP_ALL"]},
    )

    real_source_set = _default_sources(_FakeIdentity())
    result = project(sources(system_health=real_source_set.system_health))

    status = next(item for item in result.source_status if item.source == "system_health")
    item = next(item for item in result.items if item.signal_key == "system.emergency")
    assert status.state == "CURRENT"
    assert item.severity == "CRITICAL"
    assert result.overall_state == "ATTENTION"


def test_default_sources_system_health_fails_closed_to_unknown_when_helper_raises(monkeypatch):
    import tma_api
    from core.owner_attention import _default_sources

    def broken(identity):
        raise RuntimeError("airtable unavailable")

    monkeypatch.setattr(tma_api, "_system_health_payload", broken)

    real_source_set = _default_sources(_FakeIdentity())
    result = project(sources(system_health=real_source_set.system_health))

    status = next(item for item in result.source_status if item.source == "system_health")
    assert status.state == "UNKNOWN"
    assert status.reason == "source_read_failed:RuntimeError"
    assert result.overall_state == "UNKNOWN"
