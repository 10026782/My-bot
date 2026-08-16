from __future__ import annotations

from pathlib import Path

from core.owner_development import (
    DevelopmentItem,
    OwnerDevelopmentStatus,
    generate_owner_development_status,
)


ROOT = Path(__file__).parent


def test_projection_reads_registry_and_keeps_provenance():
    result = generate_owner_development_status(ROOT, checked_at="2026-08-16T00:00:00+00:00")

    assert result.projection_state == "CURRENT"
    assert result.source_versions
    assert result.source_versions[-1].path == "main"
    assert result.horizon_summary
    assert all(item.source_refs for item in result.next_actions + result.current_focus)


def test_merged_never_becomes_runtime_verified_without_explicit_evidence():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative A | Core | H0 | MERGED; לא verified בפרוד | verify after merge |
\n+### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
    }

    result = generate_owner_development_status(
        ROOT,
        source_texts=source,
        checked_at="2026-08-16T00:00:00+00:00",
        version_resolver=lambda *_: "fixture",
    )

    assert len(result.needs_verification) == 1
    item = result.needs_verification[0]
    assert item.evidence_state == "MERGED"
    assert item.evidence_state != "DEPLOYED"
    assert item.evidence_state != "RUNTIME_VERIFIED"


def test_explicit_owner_gate_and_blocker_are_not_inferred_from_next_step():
    registry = """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Owner gate | Core | H1 | ממתין להחלטת owner | לבחור אם להפעיל |
| Real blocker | Core | H2 | BLOCKED by dependency | resolve dependency |
| Plain next | Core | H3 | PLANNED | implement later |

### Horizon 1 — One
### Horizon 2 — Two
### Horizon 3 — Three
"""
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": registry,
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    assert [item.title for item in result.owner_decisions] == ["Owner gate"]
    assert [item.title for item in result.blocked] == ["Real blocker"]
    assert [item.title for item in result.next_actions] == ["Plain next"]


def test_missing_authority_fails_closed_to_unknown():
    result = generate_owner_development_status(
        ROOT,
        source_texts={"ROADMAP.md": "# no registry"},
        version_resolver=lambda *_: "fixture",
    )

    assert result.projection_state == "UNKNOWN"
    assert result.current_focus == ()
    assert result.next_actions == ()


def test_contract_rejects_unknown_state_values():
    try:
        DevelopmentItem(
            initiative_key="x", title="x", horizon=None, state="OK",
            summary="x", next_step=None, blocker=None, decision_question=None,
            evidence_state="UNKNOWN", freshness="current", source_refs=(),
            source_versions=(),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid state was accepted")


def test_projection_contract_can_be_serialized_for_future_read_api():
    result = OwnerDevelopmentStatus(
        current_focus=(), next_actions=(), needs_verification=(), blocked=(),
        owner_decisions=(), recently_closed=(), horizon_summary=(),
        updated_at="2026-08-16T00:00:00+00:00", source_versions=(),
        projection_state="CURRENT",
    )
    assert result.as_dict()["projection_state"] == "CURRENT"


def test_owner_facing_projection_redacts_internal_identifiers():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative | Core | H0 | MERGED recABC123456789 1234567 | deploy 123456789abcdef |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert "recABC" not in item.summary
    assert "1234567" not in item.summary
    assert "123456789abcdef" not in (item.next_step or "")
