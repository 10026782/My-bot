import hashlib

import marketing_gateway
from airtable_schema import MarketingCreativesFields as MCF


def _creative(**overrides):
    value = {
        MCF.SELECTION_STATUS: "Selected",
        MCF.SCRIPT_DRAFT: "טקסט מדויק\nעם רווח  ",
        MCF.APPROVED_SCRIPT: "טקסט מדויק\nעם רווח  ",
    }
    value[MCF.SCRIPT_SHA256] = hashlib.sha256(
        value[MCF.APPROVED_SCRIPT].encode("utf-8")
    ).hexdigest()
    value.update(overrides)
    return value


def test_draft_is_not_production_ready():
    assert not marketing_gateway.is_production_ready({
        MCF.SELECTION_STATUS: "Selected",
        MCF.SCRIPT_DRAFT: "draft",
    })


def test_approved_exact_script_and_hash_are_required():
    creative = _creative()
    assert marketing_gateway.is_production_ready(creative)
    assert creative[MCF.APPROVED_SCRIPT] == "טקסט מדויק\nעם רווח  "
    assert creative[MCF.SCRIPT_SHA256] == marketing_gateway.script_sha256(
        creative[MCF.APPROVED_SCRIPT]
    )


def test_one_character_change_invalidates_previous_approval():
    creative = _creative(**{MCF.SCRIPT_DRAFT: "טקסט מדויק\nעם רווח !"})
    assert not marketing_gateway.is_production_ready(creative)


def test_selected_idea_is_not_approved_script():
    creative = _creative()
    creative[MCF.SELECTED_IDEA] = "Idea 1"
    creative.pop(MCF.APPROVED_SCRIPT)
    assert not marketing_gateway.is_production_ready(creative)


def test_production_handoff_is_not_authority():
    creative = {MCF.PRODUCTION_HANDOFF: "Approved script hidden in prose"}
    assert not marketing_gateway.is_production_ready(creative)


def test_creative_without_script_fails_closed():
    assert not marketing_gateway.is_production_ready({MCF.SELECTION_STATUS: "Selected"})


def test_selection_invalidates_previous_approval(monkeypatch):
    captured = {}

    def patch(table, record_id, fields, source="unknown"):
        captured.update(fields)
        return True

    monkeypatch.setattr(marketing_gateway, "airtable_patch", patch)
    assert marketing_gateway.select_creative("recCreative", "Idea 1")
    assert captured[MCF.APPROVED_SCRIPT] is None
    assert captured[MCF.SCRIPT_SHA256] is None


def test_draft_save_invalidates_approval(monkeypatch):
    monkeypatch.setattr(
        marketing_gateway,
        "get_creative",
        lambda _creative_id: {MCF.SELECTION_STATUS: "Selected"},
    )
    captured = {}

    def patch(table, record_id, fields, source="unknown"):
        captured.update(fields)
        return True

    monkeypatch.setattr(marketing_gateway, "airtable_patch", patch)
    assert marketing_gateway.save_script_draft("recCreative", "draft")
    assert captured[MCF.SCRIPT_DRAFT] == "draft"
    assert captured[MCF.APPROVED_SCRIPT] is None
    assert captured[MCF.SCRIPT_SHA256] is None


def test_approve_script_persists_exact_value_and_hash(monkeypatch):
    exact = "שורה ראשונה\nשורה שנייה  "
    monkeypatch.setattr(
        marketing_gateway,
        "get_creative",
        lambda _creative_id: {
            MCF.SELECTION_STATUS: "Selected",
            MCF.SCRIPT_DRAFT: exact,
        },
    )
    captured = {}

    def patch(table, record_id, fields, source="unknown"):
        captured.update(fields)
        return True

    monkeypatch.setattr(marketing_gateway, "airtable_patch", patch)
    assert marketing_gateway.approve_script("recCreative")
    assert captured[MCF.APPROVED_SCRIPT] == exact
    assert captured[MCF.SCRIPT_SHA256] == hashlib.sha256(exact.encode("utf-8")).hexdigest()


def test_handoff_refuses_unapproved_creative(monkeypatch):
    monkeypatch.setattr(
        marketing_gateway,
        "get_creative",
        lambda _creative_id: {MCF.SCRIPT_DRAFT: "draft"},
    )
    monkeypatch.setattr(
        marketing_gateway,
        "airtable_patch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not write handoff")),
    )
    assert not marketing_gateway.save_production_handoff("recCreative", "handoff prose")
