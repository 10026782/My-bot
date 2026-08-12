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
        "מה בדיוק צריך להיווצר: סוג תוצר, פלטפורמת יעד, טקסט חובה, מידות/פורמט "
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
    parts.append(f"[חוקי עסק] {profile.business_rules}")
    parts.append(f"[משימה] {_TASK_INSTRUCTIONS[task_type]}")
    parts.append(f"[פרטי הדרישה]\n{_demand_summary(demand)}")
    if selected_creative:
        parts.append(f"[הרעיון שנבחר]\n{selected_creative}")

    return "\n\n".join(parts)


# ערך מפורש לכל קלט הפקה שלא סופק בפועל — העובד החיצוני חייב לראות "לא סופק"
# ולא לנחש/להשלים ערך בעצמו. שם קבוע כדי שה-self-tests יוכלו לבדוק כנגדו.
_NOT_SUPPLIED = "לא סופק"

_INVENT_CONTRACT = (
    "אין להמציא עובדות עסקיות, תנאים, הטבות, ערוצים, מחירים, אמצעי יצירת "
    'קשר, בחירת פלטפורמה, פורמטים או דרישות הפקה שלא סופקו. כל שדה קלט '
    f'שמסומן למטה כ-"{_NOT_SUPPLIED}" נשאר "{_NOT_SUPPLIED}" — אין לנחש לו '
    "ערך. אם ערך שכן סופק נראה לא תקין או חסר-פרטים, אין להפוך אותו "
    "אוטומטית לעובדה מאושרת — יש להשאירו כפי שנמסר ולסמן שהוא טעון בדיקה."
)

_CREATIVE_DIRECTION_NOTE = (
    "זהו כיוון קריאייטיבי בלבד, לא מקור אמת לעובדות עסקיות. עובדה עסקית "
    "נחשבת מאושרת רק אם היא נתמכת ב-[פרטי הדרישה]/[חוקי תחום]/[חוקי עסק] "
    "או ב-[קלטי הפקה] שסופקו במפורש למטה — לא בניסוח היצירתי של הרעיון."
)


def compose_production_handoff(
    *,
    demand: dict,
    selected_creative: str,
    domain_rules: str = "",
    target_platform: str = "",
    required_asset_type: str = "",
    format_spec: str = "",
    cta_destination: str = "",
    contact_method: str = "",
    production_requirements: str = "",
) -> str:
    """
    Pure function — provider-neutral text handed to an external production
    worker (ChatGPT/Adobe/other). Never mentions a provider name.

    Every production input (target_platform/required_asset_type/format_spec/
    cta_destination/contact_method/production_requirements) that the caller
    doesn't supply is rendered explicitly as "לא סופק" rather than omitted —
    the external worker must never treat a missing input as free to invent.
    """
    from airtable_schema import MarketingDemandFields as MDF

    profile = get_profile(demand.get(MDF.DEMAND_TYPE, ""))

    def _known(value: str) -> str:
        return value if value else _NOT_SUPPLIED

    parts = [
        f"[persona] {profile.persona}",
        f"[חוקים כלליים] {GLOBAL_RULES}",
    ]
    if domain_rules:
        parts.append(f"[חוקי תחום] {domain_rules}")
    parts.append(f"[חוקי עסק] {profile.business_rules}")
    parts.append(f"[משימה] {_TASK_INSTRUCTIONS['production_handoff']}")
    parts.append(f"[פרטי הדרישה]\n{_demand_summary(demand)}")
    parts.append(
        f"[הרעיון שנבחר]\n{selected_creative}\n\n{_CREATIVE_DIRECTION_NOTE}"
    )
    parts.append(
        "[קלטי הפקה]\n"
        f"פלטפורמת יעד: {_known(target_platform)}\n"
        f"סוג תוצר: {_known(required_asset_type)}\n"
        f"פורמט/מידות: {_known(format_spec)}\n"
        f"יעד קריאה לפעולה (CTA): {_known(cta_destination)}\n"
        f"אמצעי יצירת קשר: {_known(contact_method)}\n"
        f"דרישות הפקה נוספות: {_known(production_requirements)}"
    )
    parts.append(f"[כלל מחייב] {_INVENT_CONTRACT}")

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
    assert "[חוקי עסק]" in b1, "business_rules section label missing from composed brief"
    import sys
    assert "llm_fallback" not in sys.modules, "compose_brief must never trigger an AI-call import"

    try:
        compose_brief(demand=demand, task_type="not_a_real_task")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    # --- compose_production_handoff() — F23 grounding fix self-tests ---

    handoff = compose_production_handoff(
        demand=demand, selected_creative="רעיון לדוגמה", target_platform="Telegram",
    )
    handoff_again = compose_production_handoff(
        demand=demand, selected_creative="רעיון לדוגמה", target_platform="Telegram",
    )
    assert handoff == handoff_again, "compose_production_handoff must be deterministic for identical inputs"
    assert "llm_fallback" not in sys.modules, "compose_production_handoff must never trigger an AI-call import"
    assert "Claude" not in handoff and "Anthropic" not in handoff and "Adobe" not in handoff

    assert "רעיון לדוגמה" in handoff

    # 1) business_rules (Manual Context Brain) must now flow into the handoff.
    assert "[חוקי עסק]" in handoff, "business_rules section label missing from Production Handoff"
    assert "שם החברה" in handoff, "recruitment's real business_rules content missing from Production Handoff"

    # 2+3) demand-neutral wording: no "סוג נכס" (real-estate-flavored) even for
    # a recruitment demand — the generic term "סוג תוצר" must be used instead.
    assert "סוג נכס" not in handoff, 'recruitment Production Handoff must not say "סוג נכס"'
    assert "סוג תוצר" in handoff, 'Production Handoff must use the generic term "סוג תוצר"'

    # 4) production inputs the caller didn't supply must be explicitly marked,
    # never silently omitted (which would invite the external worker to guess).
    assert handoff.count(_NOT_SUPPLIED) >= 5, "unsupplied production inputs must be marked as 'לא סופק'"
    assert f"פורמט/מידות: {_NOT_SUPPLIED}" in handoff
    assert f"יעד קריאה לפעולה (CTA): {_NOT_SUPPLIED}" in handoff
    assert f"אמצעי יצירת קשר: {_NOT_SUPPLIED}" in handoff
    assert f"דרישות הפקה נוספות: {_NOT_SUPPLIED}" in handoff
    # a supplied input is used as-is, not replaced with "לא סופק".
    assert "פלטפורמת יעד: Telegram" in handoff

    # 5) explicit "do not invent" contract must be present.
    assert "[כלל מחייב]" in handoff and "אין להמציא" in handoff, "do-not-invent contract missing from Production Handoff"

    # 6) selected creative must be labeled as creative direction, not fact.
    assert "כיוון קריאייטיבי בלבד" in handoff, "selected_creative must be marked as creative direction, not a source of business facts"

    # fully-supplied production inputs render as given, not as "לא סופק".
    full_handoff = compose_production_handoff(
        demand=demand,
        selected_creative="רעיון לדוגמה",
        target_platform="Telegram",
        required_asset_type="באנר",
        format_spec="1080x1080",
        cta_destination="קישור לטופס",
        contact_method="וואטסאפ",
        production_requirements="לוגו בפינה",
    )
    assert f"פורמט/מידות: {_NOT_SUPPLIED}" not in full_handoff
    assert f"יעד קריאה לפעולה (CTA): {_NOT_SUPPLIED}" not in full_handoff
    assert f"אמצעי יצירת קשר: {_NOT_SUPPLIED}" not in full_handoff
    assert f"דרישות הפקה נוספות: {_NOT_SUPPLIED}" not in full_handoff
    assert "1080x1080" in full_handoff and "לוגו בפינה" in full_handoff

    print("marketing_brief_composer.py self-test OK")
