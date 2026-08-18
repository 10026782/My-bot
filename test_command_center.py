from core.command_center import UnsupportedSection, compose_command_center_status
from core.owner_attention import OwnerAttentionSources, build_owner_attention_projection
from core.owner_development import build_owner_development_status
from dev_registry_contract import REQUIRED_COLUMNS
from identity import Identity, Role


CHECKED_AT = "2026-08-16T12:00:00+00:00"


def _attention(**overrides):
    values = {
        "approvals": lambda: {"pending_count": 0, "pending": []},
        "tasks": lambda: {"overdue_tasks": 0},
        "system_health": lambda: {"status": "ok", "active_emergency": []},
        "projects": lambda: {"hot_leads_count": 0, "projects": []},
        "marketing": lambda: {"demands": [], "count": 0},
        "ventures": lambda: {"active": 0, "total": 0, "stage_counts": {}},
    }
    values.update(overrides)
    return build_owner_attention_projection(
        identity=object(), sources=OwnerAttentionSources(**values), checked_at=CHECKED_AT
    )


def _development(**overrides):
    values = {
        "Initiative Key": "EXAMPLE_INITIATIVE",
        "Initiative / Document": "Example",
        "Scope": "Test",
        "Horizon": "H0",
        "Work State": "ACTIVE",
        "Current Stage": "Owner stage",
        "Evidence State": "UNKNOWN",
        "Next Decided Step": "Review",
        "Needs Verification": "false",
        "Blocked": "false",
        "Owner Decision Required": "false",
        "Last Reconciled": "2026-08-16T00:00:00Z",
        "Evidence Source": "migration-no-explicit-evidence",
    }
    values.update(overrides)
    text = "\n".join([
        "## 3.5 רישום עבודה חי (Active Work Registry)",
        "| " + " | ".join(REQUIRED_COLUMNS) + " |",
        "|" + "|".join("---" for _ in REQUIRED_COLUMNS) + "|",
        "| " + " | ".join(values[column] for column in REQUIRED_COLUMNS) + " |",
        "### 3.5 Runtime Capability Status",
    ])
    return build_owner_development_status(text, checked_at=CHECKED_AT)


def _unknown_development():
    return build_owner_development_status("not a Registry", checked_at=CHECKED_AT)


def test_valid_oc_b_and_dev_reg_compose_with_typed_boundaries():
    result = compose_command_center_status(_attention(), _development(), generated_at=CHECKED_AT)

    assert result.attention.overall_state == "OK"
    assert result.development_status.projection_state == "CURRENT"
    assert result.pending_decisions == ()
    # business_status/recent_activity stay the by-design unsupported placeholder
    # (state UNKNOWN, reason unsupported_canonical_source) but must not, by
    # themselves, degrade overall_state now that they're intentionally
    # unsupported optional capabilities (Owner Decision 2).
    assert result.business_status.state == "UNKNOWN"
    assert result.business_status.reason == "unsupported_canonical_source"
    assert result.overall_state == "OK"
    assert result.as_dict()["development_status"]["current_focus"][0]["initiative_key"] == "EXAMPLE_INITIATIVE"


def test_current_core_projections_plus_unsupported_sections_are_ok():
    """Proof point: unsupported optional sections alone never cause PARTIAL."""
    result = compose_command_center_status(_attention(), _development(), generated_at=CHECKED_AT)

    assert result.overall_state == "OK"


def test_unknown_attention_with_current_development_is_partial():
    result = compose_command_center_status(
        _attention(marketing=lambda: {"demands": [{}]}), _development(), generated_at=CHECKED_AT
    )

    assert result.attention.overall_state == "UNKNOWN"
    assert result.development_status.projection_state == "CURRENT"
    assert result.overall_state == "PARTIAL"


def test_current_attention_with_unknown_development_is_partial():
    result = compose_command_center_status(_attention(), _unknown_development(), generated_at=CHECKED_AT)

    assert result.attention.overall_state == "OK"
    assert result.development_status.projection_state == "UNKNOWN"
    assert result.overall_state == "PARTIAL"


def test_both_core_projections_unknown_make_unified_state_unknown():
    result = compose_command_center_status(
        _attention(marketing=lambda: {"demands": [{}]}), _unknown_development(), generated_at=CHECKED_AT
    )

    assert result.overall_state == "UNKNOWN"


def test_attention_precedence_survives_unknown_development():
    result = compose_command_center_status(
        _attention(system_health=lambda: {"status": "emergency", "active_emergency": ["STOP_ALL"]}),
        _unknown_development(),
        generated_at=CHECKED_AT,
    )

    assert result.overall_state == "ATTENTION"


def test_attention_requires_owner_action_and_emergency_is_critical():
    attention = _attention(system_health=lambda: {"status": "emergency", "active_emergency": ["STOP_ALL"]})
    result = compose_command_center_status(attention, _development(), generated_at=CHECKED_AT)

    assert result.overall_state == "ATTENTION"
    assert result.system_status.state == "ATTENTION"
    assert result.attention.items[0].severity == "CRITICAL"


def test_all_supported_current_sources_can_be_ok_without_inference():
    result = compose_command_center_status(
        _attention(),
        _development(),
        generated_at=CHECKED_AT,
        business_status=UnsupportedSection(state="CURRENT", reason="canonical_business_snapshot", source_version="business:v1"),
        recent_activity=UnsupportedSection(state="CURRENT", reason="canonical_activity_snapshot", source_version="activity:v1"),
    )

    assert result.overall_state == "OK"
    assert all(value == "CURRENT" for value in result.freshness.values())


def test_system_health_unknown_source_forces_partial_not_ok():
    """System Health is a real supported source (PR #727) — its own UNKNOWN
    state must still degrade overall_state, never be silently OK."""
    attention = _attention(system_health=lambda: {"status": "bogus"})
    result = compose_command_center_status(attention, _development(), generated_at=CHECKED_AT)

    assert result.attention.overall_state == "UNKNOWN"
    assert result.system_status.state == "UNKNOWN"
    assert result.overall_state == "PARTIAL"


def test_real_stale_business_source_still_causes_partial():
    """A genuinely-supported (non-placeholder) business/recent_activity source
    that is STALE must still degrade overall_state — only the by-design
    unsupported_canonical_source placeholder is exempt."""
    result = compose_command_center_status(
        _attention(),
        _development(),
        generated_at=CHECKED_AT,
        business_status=UnsupportedSection(state="STALE", reason="canonical_business_snapshot", source_version="business:v1"),
    )

    assert result.overall_state == "PARTIAL"


def test_stale_or_partial_source_does_not_become_ok():
    development = _development(**{"Last Reconciled": "2026-08-01T00:00:00Z"})
    result = compose_command_center_status(_attention(), development, generated_at=CHECKED_AT)

    assert result.development_status.projection_state == "PARTIAL"
    assert result.overall_state == "PARTIAL"


def test_failed_attention_source_preserves_unknown_and_successful_sections():
    attention = _attention(marketing=lambda: {"demands": [{}]})
    failed = compose_command_center_status(attention, _development(), generated_at=CHECKED_AT)

    assert failed.attention.overall_state == "UNKNOWN"
    assert failed.development_status.projection_state == "CURRENT"
    assert failed.overall_state == "PARTIAL"


def test_serialization_is_stable_and_contains_all_contract_sections():
    payload = compose_command_center_status(_attention(), _development(), generated_at=CHECKED_AT).as_dict()
    assert list(payload) == [
        "attention", "pending_decisions", "business_status", "system_status",
        "development_status", "recent_activity", "freshness", "generated_at",
        "source_versions", "overall_state",
    ]
    assert payload["generated_at"] == CHECKED_AT


def test_command_center_endpoint_is_owner_scoped_and_read_only(monkeypatch):
    import tma_api as api_module
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(api_module.tma_api)
    client = app.test_client()

    assert client.get("/api/owner/command-center").status_code == 401

    monkeypatch.setattr(api_module, "_validate_initdata", lambda _: {"id": "owner-1"})
    monkeypatch.setattr(api_module, "resolve_identity", lambda *_: Identity("owner-1", Role.OWNER))
    monkeypatch.setattr(api_module, "build_owner_attention_projection", lambda identity, checked_at: _attention())
    monkeypatch.setattr(api_module, "generate_owner_development_status", lambda checked_at: _development())
    response = client.get(
        "/api/owner/command-center",
        headers={"X-Telegram-Init-Data": "signed-test-data"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["development_status"]["source_version"] == "BOSS_UNIFIED_MASTER_PLAN.md:§3.5"
    assert payload["pending_decisions"] == []
