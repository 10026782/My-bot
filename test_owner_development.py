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
        "AI_CONTEXT.md": "# context\n- **Initiative A** complete",
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


def test_code_done_without_explicit_merge_stays_code_done():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative B | Core | H0 | CODE DONE | verify |

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
    assert item.evidence_state == "CODE_DONE"
    assert item.evidence_state != "MERGED"


def test_scoped_main_production_evidence_can_upgrade_same_initiative():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative C | Core | H0 | MERGED | observe |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
        "__main__": "Initiative C merged",
        "__production__": "Initiative C — production verified: yes; deploy=main",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert item.evidence_state == "RUNTIME_VERIFIED"
    assert item.reconciliation_state == "RESOLVED"


def test_main_runtime_wording_without_production_source_cannot_prove_runtime():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| BUG-123 | Core | H0 | PLANNED | review |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
        "__main__": "BUG-123 runtime verified in production",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert item.evidence_state in {"CODE_DONE", "MERGED"}
    assert item.evidence_state != "RUNTIME_VERIFIED"


def test_registry_only_item_is_resolved_and_projection_stays_current():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Registry Only | Core | H0 | CODE DONE | review |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# no linked evidence",
        "CHANGE_CONTROL_LOG.md": "# no linked evidence",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert item.reconciliation_state == "RESOLVED"
    assert result.projection_state == "CURRENT"


def test_current_roadmap_verification_pending_beats_old_audit_completion():
    source = {
        "ROADMAP.md": "Initiative D — verification pending",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative D | Core | H0 | MERGED | verify |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "Initiative D complete",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.needs_verification[0]
    assert item.evidence_state == "MERGED"
    assert item.state == "NEEDS_VERIFICATION"


def test_unlinked_evidence_is_not_merged_into_registry_item():
    source = {
        "ROADMAP.md": "unrelated initiative complete",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative E | Core | H0 | CODE DONE | verify |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "Initiative E and Other Initiative merged",
        "CHANGE_CONTROL_LOG.md": "Other Initiative deployed",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert item.evidence_state == "UNKNOWN"
    assert item.reconciliation_state == "UNRESOLVED"
    assert result.projection_state == "PARTIAL"


def test_explicitly_linked_incompatible_change_sources_fail_closed_as_conflict():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative G | Core | H0 | PLANNED | resolve |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "Initiative G CODE DONE",
        "CHANGE_CONTROL_LOG.md": "Initiative G MERGED",
        "AI_CONTEXT.md": "# context",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    item = result.next_actions[0]
    assert item.reconciliation_state == "CONFLICT"
    assert item.evidence_state == "UNKNOWN"
    assert result.projection_state == "PARTIAL"


def test_recently_closed_uses_bounded_evidence_not_generic_implemented_word():
    source = {
        "ROADMAP.md": "# roadmap",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md": """\
## 3.5 רישום עבודה חי
| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| Initiative F | Core | H0 | PLANNED | review |

### Horizon 0 — Truth Reset
""",
        "BUG_AUDIT_LOG.md": "# bugs",
        "CHANGE_CONTROL_LOG.md": "# changes",
        "AI_CONTEXT.md": """\
## 3. Completed Since Last Update
- **Generic implementation** implemented
- **Explicit code** CODE DONE
- **Explicit merge** merged
""",
    }
    result = generate_owner_development_status(
        ROOT, source_texts=source, version_resolver=lambda *_: "fixture"
    )

    evidence = {item.title: item.evidence_state for item in result.recently_closed}
    assert "Generic implementation" not in evidence
    assert evidence["Explicit code"] == "CODE_DONE"
    assert evidence["Explicit merge"] == "MERGED"


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
            source_versions=(), reconciliation_state="bad",
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
