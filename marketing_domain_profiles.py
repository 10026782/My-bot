# marketing_domain_profiles.py — F23 BOSS Marketing Bridge (M1)
#
# Static, code-owned reference data consumed by marketing_brief_composer.py.
# GLOBAL_RULES applies to every Marketing Demand regardless of domain.
# PROFILES is keyed by Demand Type (MarketingDemandFields.DEMAND_TYPE), not by
# Domain — Demand Type selects reusable domain knowledge (persona,
# business_rules), Domain stays identity.Domain's canonical values
# (domain_utils.py). Two different fields on purpose (see BOSS_MEDIA_MARKETING
# audit — Domain vocabulary drift).
#
# business_rules deliberately does NOT restate generic professional/copywriting
# knowledge — the AI model already has that. It holds only what the model
# cannot know on its own: our concrete constraints/preferences for this
# business. Where we don't yet have real rules for a demand type, use
# _NO_KNOWN_RULES rather than inventing plausible-sounding placeholder content.
#
# Some persona/instruction text below is hand-ported (not imported) from
# creative_generator.py's TEMPLATES/_PERSONA — that module stays untouched
# and uncalled; see its own disposition note in the M1 spec.
#
# Changes here need a code deploy. Per-domain *editable* business rules
# (content that a human should be able to change without touching code)
# belong in Business Memory instead — see marketing_gateway.save_marketing_rule
# / get_marketing_rules.

from __future__ import annotations

from dataclasses import dataclass

GLOBAL_RULES = (
    "כתוב בעברית תקנית, ברורה וישירה. אין להבטיח דבר שלא אושר במפורש בפרטי "
    "הדרישה (Demand). כל טקסט חייב לכלול קריאה לפעולה אחת וברורה. אין להשתמש "
    "בסופרלטיבים גנריים (״הכי טוב״, ״אין כמונו״) בלי תוכן קונקרטי שתומך בהם. "
    "אורך: קצר ותכליתי — התאם לפלטפורמת היעד."
)


@dataclass(frozen=True)
class DomainProfile:
    demand_type: str
    persona: str
    business_rules: str


# ערך ניטרלי לסוגי דרישה שעדיין אין להם חוקי עסק ייחודיים ומאומתים — במכוון
# לא ממציאים ידע עסקי מדומה. ראה ה-M1 spec: Manual Context Brain צריך להכיל
# רק מה שאנחנו באמת יודעים, לא placeholder שמתחזה לידע אמיתי.
_NO_KNOWN_RULES = (
    "אין כרגע חוקי עסק ייחודיים מעבר לפרטי ה-Demand וה-Constraints. "
    "אין להמציא פרטים שלא נמסרו."
)

PROFILES: dict[str, DomainProfile] = {
    "recruitment": DomainProfile(
        demand_type="recruitment",
        persona=(
            "אתה מגייס מקצועי המנסח מודעות דרושים בעברית שמושכות מועמדים "
            "איכותיים ורלוונטיים."
        ),
        business_rules=(
            "אל תציין את שם החברה אלא אם ה-Demand אומר במפורש אחרת. אל "
            "תציין שכר או מספרי שכר אלא אם הם הוזנו ואושרו במפורש ב-Demand. "
            "דרישות כמו רכב, אזור פעילות וניסיון חייבות להגיע מה-"
            "Demand/Constraints ולא להיות מומצאות. ניסיון יוצג כחובה רק "
            "כאשר הוא הוגדר כחובה; אחרת אין להקשיח אותו לבד. אל תמציא "
            "תנאים, הטבות או דרישות שלא נמסרו. שמור את הפרטים הטכניים "
            "המדויקים של הדרישה כפי שנמסרו."
        ),
    ),
    "furniture_import": DomainProfile(
        demand_type="furniture_import",
        persona=(
            "אתה קופירייטר עסקי המתמחה בייבוא רהיטים וסחורות. הסגנון: ישיר, "
            "שכנועי, ממוקד בתועלת ללקוח."
        ),
        business_rules=_NO_KNOWN_RULES,
    ),
    "fiber_equipment": DomainProfile(
        demand_type="fiber_equipment",
        persona=(
            "אתה קופירייטר B2B המתמחה בציוד תשתיות סיבים אופטיים, פונה "
            "לאנשי מקצוע (קבלנים/טכנאים/רוכשים)."
        ),
        business_rules=_NO_KNOWN_RULES,
    ),
    "real_estate_listing": DomainProfile(
        demand_type="real_estate_listing",
        persona=(
            "אתה קופירייטר עסקי דובר עברית ברמה גבוהה, המתמחה בנדל\"ן. הסגנון: "
            "ישיר, שכנועי, ללא מילים מיותרות, ממוקד בתועלת ללקוח."
        ),
        business_rules=_NO_KNOWN_RULES,
    ),
    "service": DomainProfile(
        demand_type="service",
        persona=(
            "אתה קופירייטר עסקי המנסח פרסום לעסק שירותים מקומי, בגובה העיניים "
            "וללא ז'רגון."
        ),
        business_rules=_NO_KNOWN_RULES,
    ),
}


def get_profile(demand_type: str) -> DomainProfile:
    """
    Raises KeyError for an unrecognized demand_type — callers (cmd_marketing.py)
    only ever pass a value the user picked from a fixed keyboard built off
    PROFILES.keys(), so an unknown value here means a real bug upstream, not
    something to silently paper over with a fallback profile.
    """
    if demand_type not in PROFILES:
        raise KeyError(f"no DomainProfile for demand_type={demand_type!r}")
    return PROFILES[demand_type]


if __name__ == "__main__":
    assert set(PROFILES.keys()) == {
        "recruitment", "furniture_import", "fiber_equipment",
        "real_estate_listing", "service",
    }
    assert get_profile("recruitment").demand_type == "recruitment"
    for dt, profile in PROFILES.items():
        assert profile.business_rules, f"{dt} missing business_rules"
    assert "שם החברה" in PROFILES["recruitment"].business_rules
    assert PROFILES["service"].business_rules == _NO_KNOWN_RULES
    try:
        get_profile("not_a_real_type")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
    print("marketing_domain_profiles.py self-test OK")
