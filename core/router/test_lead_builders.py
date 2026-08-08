import ast
import inspect
from types import SimpleNamespace

import pytest

from airtable_schema import LeadFields, Tables
from core.router import build_create_lead_proposal, build_update_lead_proposal
from core.router.lead_builders import CapturePolicy, LeadIdentityPrecondition

_VALID_IDENTITY = LeadIdentityPrecondition(valid=True, is_duplicate=False)


def test_create_builder_returns_named_approval_proposal():
    proposal = build_create_lead_proposal(
        "  Dana Cohen  ", scope="tenant:u1", capture_policy=CapturePolicy.PREVIEW_REQUIRED,
        identity_precondition=_VALID_IDENTITY, **{LeadFields.DOMAIN: "general"},
    )

    assert proposal.intent == "create_lead"
    assert proposal.canonical_tool == "lead_create"
    assert proposal.resource == Tables.LEADS
    assert proposal.fields[LeadFields.NAME] == "Dana Cohen"
    assert proposal.approval_required is True


def test_update_builder_requires_resolved_record():
    update = build_update_lead_proposal("rec123", **{LeadFields.STATUS: "active"})

    assert update.intent == "update_lead"
    assert update.canonical_tool == "lead_update"
    assert update.fields == {"record_id": "rec123", LeadFields.STATUS: "active"}
    assert update.approval_required is True


@pytest.mark.parametrize(
    "builder",
    [
        lambda: build_create_lead_proposal(
            "", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=_VALID_IDENTITY,
        ),
        lambda: build_create_lead_proposal(
            "x", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=_VALID_IDENTITY, **{LeadFields.NAME: "duplicate"},
        ),
        lambda: build_create_lead_proposal(
            "x", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=_VALID_IDENTITY, not_a_lead_field="bad",
        ),
        lambda: build_update_lead_proposal("rec123"),
        lambda: build_update_lead_proposal("", **{LeadFields.NAME: "x"}),
    ],
)
def test_lead_builders_fail_closed(builder):
    with pytest.raises(ValueError):
        builder()


# --- Review follow-up (PR #564): scope, capture policy, identity precondition ---


def test_create_lead_missing_scope_fails_before_proposal_creation():
    """An empty/blank scope must fail closed, never produce a canonical proposal."""
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=_VALID_IDENTITY,
        )
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="   ", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=_VALID_IDENTITY,
        )


def test_create_lead_scope_is_not_written_into_fields():
    """scope is a precondition, not a business field -- it must never leak into
    the Airtable-bound fields dict (no schema invention)."""
    proposal = build_create_lead_proposal(
        "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
        identity_precondition=_VALID_IDENTITY,
    )
    assert "tenant:u1" not in proposal.fields.values()
    assert "scope" not in proposal.fields


def test_create_lead_capture_policy_omission_fails_closed():
    """capture_policy has no default -- omitting it must fail closed."""
    with pytest.raises(TypeError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", identity_precondition=_VALID_IDENTITY,
        )


def test_create_lead_rejects_an_unrecognized_capture_policy():
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy="yolo_write",
            identity_precondition=_VALID_IDENTITY,
        )


@pytest.mark.parametrize(
    "policy,expected_approval_required",
    [
        (CapturePolicy.AUTO_WRITE, False),
        (CapturePolicy.PREVIEW_REQUIRED, True),
    ],
)
def test_create_lead_covers_the_canonical_capture_policy_outcomes(policy, expected_approval_required):
    proposal = build_create_lead_proposal(
        "Dana Cohen", scope="tenant:u1", capture_policy=policy,
        identity_precondition=_VALID_IDENTITY,
    )
    assert proposal.approval_required is expected_approval_required


def test_create_lead_needs_review_cannot_produce_a_proposal():
    """needs_review is not TC4's to turn into a write proposal at all -- it
    must fail closed, never silently become approval_required=True."""
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.NEEDS_REVIEW,
            identity_precondition=_VALID_IDENTITY,
        )


def test_create_lead_identity_precondition_omission_fails_closed():
    """identity_precondition has no default -- omitting it must fail closed."""
    with pytest.raises(TypeError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
        )


def test_create_lead_invalid_identity_fails_closed():
    invalid = LeadIdentityPrecondition(valid=False, is_duplicate=False)
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=invalid,
        )


def test_create_lead_duplicate_identity_fails_closed():
    duplicate = LeadIdentityPrecondition(valid=True, is_duplicate=True)
    with pytest.raises(ValueError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=duplicate,
        )


def test_lead_identity_precondition_requires_explicit_booleans():
    """Omitting either field entirely must fail closed at construction --
    merely instantiating the precondition class must not silently grant a
    valid, non-duplicate identity."""
    with pytest.raises(TypeError):
        LeadIdentityPrecondition()
    with pytest.raises(TypeError):
        LeadIdentityPrecondition(valid=True)
    with pytest.raises(TypeError):
        LeadIdentityPrecondition(is_duplicate=False)


def test_create_lead_rejects_a_duck_typed_identity_precondition():
    """A caller cannot bypass LeadIdentityPrecondition's own __post_init__
    validation by passing a lookalike object that merely exposes
    valid/is_duplicate attributes -- the builder must check isinstance
    before ever reading those attributes."""
    deceptive = SimpleNamespace(valid=True, is_duplicate=False)
    with pytest.raises(TypeError):
        build_create_lead_proposal(
            "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
            identity_precondition=deceptive,
        )


def test_create_lead_valid_scoped_create_still_builds():
    proposal = build_create_lead_proposal(
        "Dana Cohen", scope="tenant:u1", capture_policy=CapturePolicy.AUTO_WRITE,
        identity_precondition=_VALID_IDENTITY, **{LeadFields.PHONE: "0521234567"},
    )
    assert proposal.intent == "create_lead"
    assert proposal.fields[LeadFields.NAME] == "Dana Cohen"
    assert proposal.fields[LeadFields.PHONE] == "0521234567"
    assert proposal.approval_required is False


def test_lead_builders_never_call_agent_or_execute():
    """Builders only name a proposal -- no Agent/LLM call, no dispatcher/write import."""
    import core.router.lead_builders as module

    source = inspect.getsource(module)
    for banned in ("agent", "anthropic", "claude", "llm", "dispatch_tool", "airtable_gateway"):
        assert banned not in source.lower()


def test_lead_builders_no_runtime_or_write_import():
    """No concrete data-source/runtime import -- every precondition is caller-
    asserted, this module performs no lookup, no flag read, no write."""
    import core.router.lead_builders as module

    tree = ast.parse(inspect.getsource(module))
    forbidden_substrings = (
        "dispatcher", "airtable_tools", "airtable_gateway", "action_gateway",
        "action_contract_repository", "event_bus", "session_store", "app",
        "lead_candidate_handler", "feature_flags", "turn_coordinator_runtime",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not any(bad in module_name for bad in forbidden_substrings), (
                f"unexpected import touching a write/runtime path: {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(bad in alias.name for bad in forbidden_substrings), (
                    f"unexpected import touching a write/runtime path: {alias.name}"
                )
