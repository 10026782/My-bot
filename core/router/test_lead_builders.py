import inspect

import pytest

from airtable_schema import LeadFields, Tables
from core.router import build_create_lead_proposal, build_update_lead_proposal


def test_create_builder_returns_named_approval_proposal():
    proposal = build_create_lead_proposal("  Dana Cohen  ", **{LeadFields.DOMAIN: "general"})

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


@pytest.mark.parametrize(
    "builder",
    [
        lambda: build_create_lead_proposal(""),
        lambda: build_create_lead_proposal("x", **{LeadFields.NAME: "duplicate"}),
        lambda: build_create_lead_proposal("x", not_a_lead_field="bad"),
        lambda: build_update_lead_proposal("rec123"),
        lambda: build_update_lead_proposal("", **{LeadFields.NAME: "x"}),
    ],
)
def test_lead_builders_fail_closed(builder):
    with pytest.raises(ValueError):
        builder()


def test_lead_builders_never_call_agent_or_execute():
    """Builders only name a proposal -- no Agent/LLM call, no dispatcher/write import."""
    import core.router.lead_builders as module

    source = inspect.getsource(module)
    for banned in ("agent", "anthropic", "claude", "llm", "dispatch_tool", "airtable_gateway"):
        assert banned not in source.lower()
