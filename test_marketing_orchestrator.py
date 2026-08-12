# test_marketing_orchestrator.py — F23 BOSS Marketing Bridge (M2)
#
# Standalone script, run directly: python3 test_marketing_orchestrator.py
# (no pytest harness in this repo — see CLAUDE.md's Tests section). Exercises
# marketing_orchestrator.compute_next_action()'s full state-dispatch table,
# beyond the smaller self-test already in the module's own __main__ block.

from airtable_schema import (
    MarketingCreativesFields as MCF,
    MarketingDemandFields as MDF,
    MarketingDemandStage as Stage,
)
from marketing_orchestrator import compute_next_action, format_status_card


def _demand(stage: str, status: str = "Active") -> dict:
    return {MDF.NAME: "דרישה לדוגמה", MDF.CURRENT_STAGE: stage, MDF.STATUS: status}


def test_active_intake_prompts_restart():
    r = compute_next_action("rec1", _demand(Stage.INTAKE))
    assert "יצירת הרעיונות לא הושלמה" in r.next_step.action
    assert r.show_ideas is False
    assert r.creative_id is None


def test_ideas_generated_exactly_one_pending():
    creatives = {
        "recC1": {
            MCF.SELECTION_STATUS: "Pending Review",
            MCF.IDEA_1: "idea one", MCF.IDEA_2: "idea two", MCF.IDEA_3: "idea three",
        },
    }
    r = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED), creatives)
    assert r.show_ideas is True
    assert r.creative_id == "recC1"
    assert r.ideas == ("idea one", "idea two", "idea three")


def test_ideas_generated_zero_pending():
    creatives = {"recC1": {MCF.SELECTION_STATUS: "Selected"}}
    r = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED), creatives)
    assert r.show_ideas is False
    assert r.creative_id is None
    assert "לא נמצא Creative" in r.next_step.action

    r_empty = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED), {})
    assert r_empty.show_ideas is False
    assert "לא נמצא Creative" in r_empty.next_step.action


def test_ideas_generated_multiple_pending_fails_closed():
    creatives = {
        "recC1": {MCF.SELECTION_STATUS: "Pending Review"},
        "recC2": {MCF.SELECTION_STATUS: "Pending Review"},
        "recC3": {MCF.SELECTION_STATUS: "Selected"},
    }
    r = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED), creatives)
    assert r.show_ideas is False
    assert r.creative_id is None
    assert "2 Creatives" in r.next_step.action
    assert "מצב לא עקבי" in r.next_step.action


def test_handoff_sent_returns_saved_text():
    creatives = {"recC1": {MCF.PRODUCTION_HANDOFF: "PRODUCTION HANDOFF TEXT HERE"}}
    r = compute_next_action("rec1", _demand(Stage.HANDOFF_SENT), creatives)
    assert "PRODUCTION HANDOFF TEXT HERE" in r.next_step.detail


def test_handoff_sent_missing_text_has_fallback():
    r = compute_next_action("rec1", _demand(Stage.HANDOFF_SENT), {"recC1": {}})
    assert "לא נמצא טקסט" in r.next_step.detail
    r_no_creative = compute_next_action("rec1", _demand(Stage.HANDOFF_SENT), {})
    assert "לא נמצא טקסט" in r_no_creative.next_step.detail


def test_published_suggests_manual_tracking():
    r = compute_next_action("rec1", _demand(Stage.PUBLISHED))
    assert "עקוב אחר ביצועי" in r.next_step.action


def test_inactive_statuses_need_no_action():
    for status, label in (("Paused", "בהמתנה"), ("Done", "הושלמה"), ("Cancelled", "בוטלה")):
        r = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED, status=status))
        assert "אין פעולה נדרשת" in r.next_step.action
        assert label in r.next_step.action


def test_reserved_and_unknown_stages_are_not_inferred():
    for stage in (Stage.BRIEF_COMPOSED, Stage.SELECTED, Stage.CLOSED, "totally_unrecognized_stage"):
        r = compute_next_action("rec1", _demand(stage))
        assert "אינו מטופל אוטומטית" in r.next_step.action, stage
        assert r.show_ideas is False


def test_format_status_card_renders_all_pieces():
    creatives = {"recC1": {MCF.SELECTION_STATUS: "Pending Review", MCF.IDEA_1: "a", MCF.IDEA_2: "b", MCF.IDEA_3: "c"}}
    r = compute_next_action("rec1", _demand(Stage.IDEAS_GENERATED), creatives)
    card = format_status_card(r)
    assert "דרישה לדוגמה" in card
    assert "צעד הבא" in card
    assert r.next_step.action in card


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"test_marketing_orchestrator.py: {len(tests)}/{len(tests)} passed")
