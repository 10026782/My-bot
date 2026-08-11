# marketing_brief_composer.py — F23 BOSS Marketing Bridge (M1)
#
# Pure, deterministic composition: Global Rules + Domain Rules + DomainProfile
# + Demand + Task Type (+ optional selected creative) -> one provider-neutral
# prompt/brief string. No Airtable I/O and no AI call happens in this module —
# callers (cmd_marketing.py) fetch domain_rules via marketing_gateway.py and
# pass it in, and call llm_fallback.call_anthropic_text() themselves with the
# composed brief. Keeping this pure is what makes compose_brief()/
# compose_production_handoff() unit-testable without mocking anything.

from __future__ import annotations

from marketing_domain_profiles import GLOBAL_RULES, get_profile

__version__ = "1.0.0"

TASK_TYPES = (
    "creative_ideas",
    "creative_review",
    "ad_package",
    "production_handoff",
    "publishing_plan",
)

_TASK_INSTRUCTIONS: dict[str, str] = {
    "creative_ideas": (
        "המשימה: הצע 3 רעיונות קריאייטיב שונים באופן מהותי זה מזה (זווית/מסר "
        "שונה בכל רעיון, לא 3 ניסוחים לאותו רעיון). סמן כל רעיון במספר (1/2/3)."
    ),
    "creative_review": (
        "המשימה: סקור את הרעיון הבא מול הדרישות והחוקים למטה, וציין בקצרה אם "
        "הוא עומד בהם."
    ),
    "ad_package": (
        "המשימה: כתוב חבילת תוכן פרסומית מלאה (כותרת + גוף + קריאה לפעולה) "
        "מוכנה לפרסום, על בסיס הרעיון שנבחר."
    ),
    "production_handoff": (
        "המשימה: זהו תדריך הפקה (Production Handoff) — לא טקסט לפרסום. פרט "
        "מה בדיוק צריך להיווצר: סוג נכס, פלטפורמת יעד, טקסט חובה, מידות/פורמט "
        "אם רלוונטי, וקריאה לפעולה."
    ),
    "publishing_plan": (
        "המשימה: הצע תוכנית פרסום קצרה — לאילו ערוצים, באיזה סדר עדיפות, ולמה."
    ),
}


def _demand_summary(demand: dict) -> str:
    from airtable_schema import MarketingDemandFields as MDF

    lines = [
        f"תחום: {demand.get(MDF.DOMAIN, '')}",
        f"סוג דרישה: {demand.get(MDF.DEMAND_TYPE, '')}",
        f"נושא/הצעה: {demand.get(MDF.NAME, '')}",
    ]
    if demand.get(MDF.TARGET_AUDIENCE):
        lines.append(f"קהל יעד: {demand[MDF.TARGET_AUDIENCE]}")
    if demand.get(MDF.LOCATION):
        lines.append(f"מיקום: {demand[MDF.LOCATION]}")
    if demand.get(MDF.GOAL):
        lines.append(f"מטרה: {demand[MDF.GOAL]}")
    if demand.get(MDF.CONSTRAINTS):
        lines.append(f"אילוצים: {demand[MDF.CONSTRAINTS]}")
    return "\n".join(lines)


def compose_brief(
    *,
    demand: dict,
    task_type: str,
    domain_rules: str = "",
    selected_creative: str | None = None,
) -> str:
    """
    Pure function — no Airtable read, no AI call. Same inputs always produce
    the same output string.

    demand: the Marketing Demand record's `fields` dict (MarketingDemandFields
    keys). domain_rules: prose fetched by the caller via
    marketing_gateway.get_marketing_rules(domain) — passed in, not fetched here.
    """
    if task_type not in TASK_TYPES:
        raise ValueError(f"unknown task_type={task_type!r}, expected one of {TASK_TYPES}")

    from airtable_schema import MarketingDemandFields as MDF

    profile = get_profile(demand.get(MDF.DEMAND_TYPE, ""))

    parts = [
        f"[persona] {profile.persona}",
        f"[חוקים כלליים] {GLOBAL_RULES}",
    ]
    if domain_rules:
        parts.append(f"[חוקי תחום] {domain_rules}")
    parts.append(f"[נקודות מפתח] {profile.key_points}")
    parts.append(f"[משימה] {_TASK_INSTRUCTIONS[task_type]}")
    parts.append(f"[פרטי הדרישה]\n{_demand_summary(demand)}")
    if selected_creative:
        parts.append(f"[הרעיון שנבחר]\n{selected_creative}")

    return "\n\n".join(parts)


def compose_production_handoff(
    *,
    demand: dict,
    selected_creative: str,
    domain_rules: str = "",
    target_platform: str = "",
    required_asset_type: str = "",
) -> str:
    """
    Pure function — provider-neutral text handed to an external production
    worker (ChatGPT/Adobe/other). Never mentions a provider name.
    """
    from airtable_schema import MarketingDemandFields as MDF

    profile = get_profile(demand.get(MDF.DEMAND_TYPE, ""))

    parts = [
        f"[persona] {profile.persona}",
        f"[חוקים כלליים] {GLOBAL_RULES}",
    ]
    if domain_rules:
        parts.append(f"[חוקי תחום] {domain_rules}")
    parts.append(f"[משימה] {_TASK_INSTRUCTIONS['production_handoff']}")
    parts.append(f"[פרטי הדרישה]\n{_demand_summary(demand)}")
    parts.append(f"[הרעיון שנבחר]\n{selected_creative}")
    if target_platform:
        parts.append(f"[פלטפורמת יעד] {target_platform}")
    if required_asset_type:
        parts.append(f"[סוג נכס נדרש] {required_asset_type}")

    return "\n\n".join(parts)


if __name__ == "__main__":
    from airtable_schema import MarketingDemandFields as MDF

    demand = {
        MDF.DOMAIN: "general",
        MDF.DEMAND_TYPE: "recruitment",
        MDF.NAME: "דרישה למתקינים",
        MDF.TARGET_AUDIENCE: "ניסיון 3+ שנים",
        MDF.LOCATION: "בית שמש",
        MDF.GOAL: "10 מועמדים תוך שבוע",
    }

    b1 = compose_brief(demand=demand, task_type="creative_ideas", domain_rules="תמיד לציין שכר.")
    b2 = compose_brief(demand=demand, task_type="creative_ideas", domain_rules="תמיד לציין שכר.")
    assert b1 == b2, "compose_brief must be deterministic for identical inputs"
    assert "מתקינים" in b1
    assert "תמיד לציין שכר" in b1
    import sys
    assert "llm_fallback" not in sys.modules, "compose_brief must never trigger an AI-call import"

    try:
        compose_brief(demand=demand, task_type="not_a_real_task")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    handoff = compose_production_handoff(
        demand=demand, selected_creative="רעיון לדוגמה", target_platform="Telegram",
    )
    assert "רעיון לדוגמה" in handoff
    assert "Claude" not in handoff and "Anthropic" not in handoff and "Adobe" not in handoff

    print("marketing_brief_composer.py self-test OK")
