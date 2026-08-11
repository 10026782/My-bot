# marketing_domain_profiles.py — F23 BOSS Marketing Bridge (M1)
#
# Static, code-owned reference data consumed by marketing_brief_composer.py.
# GLOBAL_RULES applies to every Marketing Demand regardless of domain.
# PROFILES is keyed by Demand Type (MarketingDemandFields.DEMAND_TYPE), not by
# Domain — Demand Type selects reusable domain knowledge (persona, key points,
# tone), Domain stays identity.Domain's canonical values (domain_utils.py). Two different
# fields on purpose (see BOSS_MEDIA_MARKETING audit — Domain vocabulary drift).
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
    key_points: str
    default_tone: str = "professional"


PROFILES: dict[str, DomainProfile] = {
    "recruitment": DomainProfile(
        demand_type="recruitment",
        persona=(
            "אתה מגייס מקצועי המנסח מודעות דרושים בעברית שמושכות מועמדים "
            "איכותיים ורלוונטיים."
        ),
        key_points=(
            "כלול: תיאור תפקיד תמציתי, דרישות מרכזיות (ניסיון/כישורים), "
            "יתרונות/תנאים בולטים, קריאה ברורה ליצירת קשר. הימנע ממונחים "
            "מקצועיים שדוחפים החוצה מועמדים טובים."
        ),
    ),
    "furniture_import": DomainProfile(
        demand_type="furniture_import",
        persona=(
            "אתה קופירייטר עסקי המתמחה בייבוא רהיטים וסחורות. הסגנון: ישיר, "
            "שכנועי, ממוקד בתועלת ללקוח."
        ),
        key_points=(
            "הדגש: איכות המוצר, מחיר תחרותי, אמינות הספק, זמינות/משלוח. "
            "עד 100 מילה אלא אם הפלטפורמה דורשת אחרת."
        ),
    ),
    "fiber_equipment": DomainProfile(
        demand_type="fiber_equipment",
        persona=(
            "אתה קופירייטר B2B המתמחה בציוד תשתיות סיבים אופטיים, פונה "
            "לאנשי מקצוע (קבלנים/טכנאים/רוכשים)."
        ),
        key_points=(
            "הדגש: מפרט טכני מדויק, תאימות תקנים, זמינות מלאי, יתרון תחרותי "
            "מול ספקים אחרים. טון מקצועי, לא שיווקי-רועש."
        ),
    ),
    "real_estate_listing": DomainProfile(
        demand_type="real_estate_listing",
        persona=(
            "אתה קופירייטר עסקי דובר עברית ברמה גבוהה, המתמחה בנדל\"ן. הסגנון: "
            "ישיר, שכנועי, ללא מילים מיותרות, ממוקד בתועלת ללקוח."
        ),
        key_points=(
            "כלול: כותרת חזקה, 3 יתרונות מפתח, קריאה לפעולה. עד 120 מילה."
        ),
    ),
    "service": DomainProfile(
        demand_type="service",
        persona=(
            "אתה קופירייטר עסקי המנסח פרסום לעסק שירותים מקומי, בגובה העיניים "
            "וללא ז'רגון."
        ),
        key_points=(
            "הדגש: מה השירות פותר ללקוח, למה לבחור בנו עכשיו, קריאה ברורה "
            "ליצירת קשר/הזמנה."
        ),
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
    try:
        get_profile("not_a_real_type")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
    print("marketing_domain_profiles.py self-test OK")
