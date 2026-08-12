# marketing_orchestrator.py — F23 BOSS Marketing Bridge (M2, Telegram slice)
#
# Pull-only lifecycle status for one Marketing Demand — mirrors
# decision_orchestrator.py's contract exactly: receives records already
# fetched by the caller, determines the right status/next-step card, and
# returns a display model. It never writes canonical state, sends messages,
# or creates actions. cmd_marketing.py's mkt_status:/mkt_select: handlers own
# all I/O and all writes (the existing M1 selection/handoff write path is
# reused as-is when this module reports exactly one Creative pending review —
# this module itself adds no new write path).

from __future__ import annotations

from dataclasses import dataclass

from airtable_schema import (
    MarketingCreativesFields as MCF,
    MarketingDemandFields as MDF,
    MarketingDemandStage as Stage,
)

_INACTIVE_STATUSES = {"Paused", "Done", "Cancelled"}
_STATUS_LABELS = {"Paused": "בהמתנה", "Done": "הושלמה", "Cancelled": "בוטלה"}


@dataclass(frozen=True)
class NextStep:
    action: str
    detail: str = ""


@dataclass(frozen=True)
class DemandStatus:
    demand_id: str
    title: str
    stage: str
    status: str
    next_step: NextStep
    show_ideas: bool = False
    ideas: tuple[str, str, str] | None = None
    creative_id: str | None = None


def compute_next_action(
    demand_id: str,
    demand: dict,
    creatives: dict[str, dict] | None = None,
) -> DemandStatus:
    """
    Returns the lifecycle status + recommended next step for one Marketing
    Demand. `demand` is the Demand record's `fields` dict (as returned by
    marketing_gateway.get_demand()). `creatives` is {creative_id: fields}
    for every Creative linked to this Demand (marketing_gateway.get_creative()
    per id in demand[MDF.CREATIVES]) — not just the most recent one, so this
    function can detect and fail closed on an inconsistent multi-pending
    state instead of guessing which one is "the" active Creative.
    """
    creatives = creatives or {}
    stage = demand.get(MDF.CURRENT_STAGE) or Stage.INTAKE
    status = demand.get(MDF.STATUS) or "Active"
    title = demand.get(MDF.NAME) or demand_id

    if status in _INACTIVE_STATUSES:
        return DemandStatus(
            demand_id, title, stage, status,
            NextStep(f"אין פעולה נדרשת — הדרישה {_STATUS_LABELS.get(status, status)}"),
        )

    if stage == Stage.PUBLISHED:
        return DemandStatus(
            demand_id, title, stage, status,
            NextStep("עקוב אחר ביצועי הפרסום ועדכן Responses/Spend ידנית ב-Airtable"),
        )

    if stage == Stage.HANDOFF_SENT:
        handoff = next(
            (c.get(MCF.PRODUCTION_HANDOFF, "") for c in creatives.values() if c.get(MCF.PRODUCTION_HANDOFF)),
            "",
        )
        detail = handoff or "לא נמצא טקסט Production Handoff שמור — בדוק ב-Airtable."
        return DemandStatus(
            demand_id, title, stage, status,
            NextStep(
                "העבר את ה-Production Handoff הבא לגורם המפיק; לאחר הפרסום תעד ב-Marketing Publications",
                detail=detail,
            ),
        )

    if stage == Stage.IDEAS_GENERATED:
        pending = {
            cid: c for cid, c in creatives.items()
            if c.get(MCF.SELECTION_STATUS) == "Pending Review"
        }
        if len(pending) == 1:
            cid, c = next(iter(pending.items()))
            ideas = (c.get(MCF.IDEA_1, ""), c.get(MCF.IDEA_2, ""), c.get(MCF.IDEA_3, ""))
            return DemandStatus(
                demand_id, title, stage, status,
                NextStep("בחר אחד מ-3 הרעיונות למטה"),
                show_ideas=True, ideas=ideas, creative_id=cid,
            )
        if len(pending) == 0:
            return DemandStatus(
                demand_id, title, stage, status,
                NextStep(
                    "לא נמצא Creative הממתין לבחירה — בדוק ידנית ב-Airtable או "
                    "פתח דרישה חדשה עם /marketing_new"
                ),
            )
        return DemandStatus(
            demand_id, title, stage, status,
            NextStep(
                f"נמצאו {len(pending)} Creatives הממתינים לבחירה עבור דרישה זו — "
                "מצב לא עקבי, נדרש ניקוי ידני ב-Airtable לפני שניתן לבחור רעיון"
            ),
        )

    if stage == Stage.INTAKE:
        # Demand exists but no Creative was ever generated (e.g. the AI call
        # failed after creation). Empty/missing Current Stage is coerced to
        # INTAKE above, so this also covers that case.
        return DemandStatus(
            demand_id, title, stage, status,
            NextStep("יצירת הרעיונות לא הושלמה — פתח מחדש עם /marketing_new (ניתן לבדוק/למחוק את הדרישה ידנית ב-Airtable)"),
        )

    # Everything else: the 3 schema-reserved-but-never-set-by-any-live-writer
    # stages (brief_composed/selected/closed) plus any genuinely unrecognized
    # value (e.g. a manual Airtable edit with a typo). Per the M2 review: do
    # not invent behavior for a stage the live M1 code path never reaches —
    # a safe "not handled automatically" card beats a wrong inference.
    return DemandStatus(
        demand_id, title, stage, status,
        NextStep(f"שלב '{stage}' קיים בסכמה אך אינו מטופל אוטומטית במסלול החי כרגע — בדוק ידנית ב-Airtable"),
    )


def format_status_card(result: DemandStatus) -> str:
    """Render a Telegram-ready Markdown block."""
    lines = [
        f"📣 *{result.title}*",
        f"🔄 שלב: {result.stage} | סטטוס: {result.status}",
        "",
        f"➡️ *צעד הבא:* {result.next_step.action}",
    ]
    if result.next_step.detail:
        lines.extend(("", result.next_step.detail))
    return "\n".join(lines)


if __name__ == "__main__":
    d_active_intake = {MDF.NAME: "t", MDF.CURRENT_STAGE: Stage.INTAKE, MDF.STATUS: "Active"}
    r = compute_next_action("rec1", d_active_intake)
    assert "יצירת הרעיונות לא הושלמה" in r.next_step.action
    assert r.show_ideas is False

    d_ideas = {MDF.NAME: "t", MDF.CURRENT_STAGE: Stage.IDEAS_GENERATED, MDF.STATUS: "Active"}
    one_pending = {"recC1": {MCF.SELECTION_STATUS: "Pending Review", MCF.IDEA_1: "a", MCF.IDEA_2: "b", MCF.IDEA_3: "c"}}
    r = compute_next_action("rec1", d_ideas, one_pending)
    assert r.show_ideas is True and r.creative_id == "recC1" and r.ideas == ("a", "b", "c")

    r = compute_next_action("rec1", d_ideas, {})
    assert r.show_ideas is False and "לא נמצא Creative" in r.next_step.action

    two_pending = {
        "recC1": {MCF.SELECTION_STATUS: "Pending Review"},
        "recC2": {MCF.SELECTION_STATUS: "Pending Review"},
    }
    r = compute_next_action("rec1", d_ideas, two_pending)
    assert r.show_ideas is False and "מצב לא עקבי" in r.next_step.action

    d_handoff = {MDF.NAME: "t", MDF.CURRENT_STAGE: Stage.HANDOFF_SENT, MDF.STATUS: "Active"}
    r = compute_next_action("rec1", d_handoff, {"recC1": {MCF.PRODUCTION_HANDOFF: "HANDOFF TEXT"}})
    assert "HANDOFF TEXT" in r.next_step.detail
    r = compute_next_action("rec1", d_handoff, {})
    assert "לא נמצא טקסט" in r.next_step.detail

    d_pub = {MDF.NAME: "t", MDF.CURRENT_STAGE: Stage.PUBLISHED, MDF.STATUS: "Active"}
    r = compute_next_action("rec1", d_pub)
    assert "עקוב אחר ביצועי" in r.next_step.action

    for st in ("Paused", "Done", "Cancelled"):
        d = {MDF.NAME: "t", MDF.CURRENT_STAGE: Stage.INTAKE, MDF.STATUS: st}
        r = compute_next_action("rec1", d)
        assert "אין פעולה נדרשת" in r.next_step.action

    for st in (Stage.BRIEF_COMPOSED, Stage.SELECTED, Stage.CLOSED, "not_a_real_stage"):
        d = {MDF.NAME: "t", MDF.CURRENT_STAGE: st, MDF.STATUS: "Active"}
        r = compute_next_action("rec1", d)
        assert "אינו מטופל אוטומטית" in r.next_step.action, st

    card = format_status_card(r)
    assert "צעד הבא" in card

    print("marketing_orchestrator.py self-test OK")
