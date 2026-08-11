import pytest

from core.router.route_decision import RouterDomain
from domain_utils import (
    UnknownBusinessDomain, business_domain_from_airtable,
    business_domain_to_airtable, business_domain_to_router,
    normalize_business_domain, resolve_business_domain,
)
from identity import Domain


def test_canonical_business_domain_set_includes_recruitment():
    assert Domain.ALL == {
        "real_estate", "import", "media", "saas", "finance", "recruitment", "general"
    }


@pytest.mark.parametrize("raw, expected", [
    ("Real Estate ", Domain.REAL_ESTATE), ("SaaS", Domain.SAAS),
    ("Recruiting", Domain.RECRUITMENT), ("גיוס", Domain.RECRUITMENT),
    ("ייבוא", Domain.IMPORT), ("שיווק", Domain.MEDIA),
])
def test_known_aliases_normalize(raw, expected):
    assert normalize_business_domain(raw) == expected


def test_unknown_domain_fails_closed_unless_fallback_is_explicit():
    assert normalize_business_domain("crm") is None
    with pytest.raises(UnknownBusinessDomain):
        resolve_business_domain("crm")
    assert resolve_business_domain("crm", fallback=Domain.GENERAL) == Domain.GENERAL


def test_airtable_adapters_are_explicit_and_round_trip():
    assert business_domain_to_airtable("recruiting", vocabulary="venture_legacy") == "Recruitment"
    assert business_domain_from_airtable(" Recruitment ", vocabulary="venture_legacy") == Domain.RECRUITMENT
    assert business_domain_to_airtable("ייבוא", vocabulary="decision_legacy") == "ייבוא"
    assert business_domain_to_airtable("recruitment", vocabulary="business_memory_legacy") == "recruitment"
    assert business_domain_from_airtable("recruitment", vocabulary="business_memory_legacy") == Domain.RECRUITMENT
    assert business_domain_from_airtable("Recruitment", vocabulary="business_memory_legacy") == Domain.RECRUITMENT
    assert business_domain_from_airtable("Real Estate ", vocabulary="business_memory_legacy") == Domain.REAL_ESTATE


def test_router_mapping_is_explicit_and_keeps_meta_namespaces_out():
    assert business_domain_to_router(Domain.RECRUITMENT) == RouterDomain.RECRUITMENT
    assert business_domain_to_router(Domain.GENERAL) == RouterDomain.GENERAL
    with pytest.raises(UnknownBusinessDomain):
        business_domain_to_router("crm")
