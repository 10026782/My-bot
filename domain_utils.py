"""Canonical business-domain vocabulary and explicit legacy adapters."""

from __future__ import annotations

from typing import Final

from identity import Domain
from core.router.route_decision import RouterDomain


class UnknownBusinessDomain(ValueError):
    """Raised when a value is not an approved business-domain alias."""


# Values observed in current code, schema comments, and existing writers.
BUSINESS_DOMAIN_ALIASES: Final[dict[str, str]] = {
    "real_estate": Domain.REAL_ESTATE, "real estate": Domain.REAL_ESTATE,
    "נדלן": Domain.REAL_ESTATE, 'נדל"ן': Domain.REAL_ESTATE,
    "import": Domain.IMPORT, "יבוא": Domain.IMPORT, "ייבוא": Domain.IMPORT,
    "media": Domain.MEDIA, "marketing": Domain.MEDIA, "שיווק": Domain.MEDIA,
    "saas": Domain.SAAS, "finance": Domain.FINANCE,
    "recruitment": Domain.RECRUITMENT, "recruiting": Domain.RECRUITMENT,
    "גיוס": Domain.RECRUITMENT, "גיוסים": Domain.RECRUITMENT,
    "general": Domain.GENERAL, "כללי": Domain.GENERAL,
}

_AIRTABLE_VENTURE_VALUES: Final[dict[str, str]] = {
    Domain.REAL_ESTATE: "Real Estate", Domain.IMPORT: "Import",
    Domain.SAAS: "SaaS", Domain.RECRUITMENT: "Recruitment",
    Domain.GENERAL: "General",
}
_DECISION_LEGACY_VALUES: Final[dict[str, str]] = {
    Domain.REAL_ESTATE: 'נדל"ן', Domain.IMPORT: "ייבוא",
    Domain.RECRUITMENT: "גיוס", Domain.GENERAL: "כללי",
}
_BUSINESS_MEMORY_VALUES: Final[dict[str, str]] = {
    Domain.REAL_ESTATE: "Real Estate ", Domain.IMPORT: "Import",
    Domain.MEDIA: "Media", Domain.SAAS: "Saas", Domain.FINANCE: "Finance",
    Domain.RECRUITMENT: "recruitment", Domain.GENERAL: "General",
}


def normalize_business_domain(value: object) -> str | None:
    """Return a canonical value, or ``None`` for an unknown/empty value."""
    if value is None:
        return None
    return BUSINESS_DOMAIN_ALIASES.get(str(value).strip().casefold())


def resolve_business_domain(value: object, *, fallback: str | None = None) -> str:
    normalized = normalize_business_domain(value)
    if normalized is not None:
        return normalized
    if fallback is not None:
        fallback_value = normalize_business_domain(fallback)
        if fallback_value is None:
            raise UnknownBusinessDomain(f"invalid fallback business domain: {fallback!r}")
        return fallback_value
    raise UnknownBusinessDomain(f"unknown business domain: {value!r}")


def business_domain_to_airtable(value: object, *, vocabulary: str = "canonical") -> str:
    domain = resolve_business_domain(value)
    if vocabulary == "canonical":
        return domain
    values = {"venture_legacy": _AIRTABLE_VENTURE_VALUES,
              "decision_legacy": _DECISION_LEGACY_VALUES,
              "business_memory_legacy": _BUSINESS_MEMORY_VALUES}
    if vocabulary not in values:
        raise ValueError(f"unknown Airtable domain vocabulary: {vocabulary!r}")
    try:
        return values[vocabulary][domain]
    except KeyError as exc:
        raise UnknownBusinessDomain(f"no {vocabulary} value for {domain!r}") from exc


def business_domain_from_airtable(value: object, *, vocabulary: str = "canonical") -> str | None:
    if value is None:
        return None
    if vocabulary == "canonical":
        return normalize_business_domain(value)
    values = {"venture_legacy": _AIRTABLE_VENTURE_VALUES,
              "decision_legacy": _DECISION_LEGACY_VALUES,
              "business_memory_legacy": _BUSINESS_MEMORY_VALUES}
    if vocabulary not in values:
        raise ValueError(f"unknown Airtable domain vocabulary: {vocabulary!r}")
    reverse = {raw.strip().casefold(): canonical for canonical, raw in values[vocabulary].items()}
    return reverse.get(str(value).strip().casefold())


def business_domain_to_router(value: object) -> str:
    domain = resolve_business_domain(value)
    return {
        Domain.REAL_ESTATE: RouterDomain.REAL_ESTATE,
        Domain.IMPORT: RouterDomain.IMPORT, Domain.MEDIA: RouterDomain.MEDIA,
        Domain.SAAS: RouterDomain.SAAS, Domain.FINANCE: RouterDomain.FINANCE,
        Domain.RECRUITMENT: RouterDomain.RECRUITMENT,
        Domain.GENERAL: RouterDomain.GENERAL,
    }[domain]
