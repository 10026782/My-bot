"""Unified read-only Command Center composition.

This module is deliberately a composition boundary, not a source of truth.
It consumes the already-built OC-B and DEV-REG-3 read models and keeps
unsupported sections explicit instead of inferring business health.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from core.owner_attention import OwnerAttentionItem, OwnerAttentionProjection
from core.owner_development import OwnerDevelopmentStatus


UNIFIED_STATES = frozenset({"OK", "ATTENTION", "PARTIAL", "UNKNOWN"})
SECTION_STATES = frozenset({"CURRENT", "STALE", "PARTIAL", "UNKNOWN"})
SYSTEM_STATES = SECTION_STATES | {"ATTENTION"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UnsupportedSection:
    """A typed unavailable section; absence is never treated as healthy."""

    state: str = "UNKNOWN"
    reason: str = "unsupported_canonical_source"
    source_version: str = "unsupported"

    def __post_init__(self) -> None:
        if self.state not in SECTION_STATES:
            raise ValueError(f"unsupported section state: {self.state}")

    def as_dict(self) -> dict[str, str]:
        return {
            "state": self.state,
            "reason": self.reason,
            "source_version": self.source_version,
        }


@dataclass(frozen=True)
class SystemStatus:
    state: str
    freshness: str
    source: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.state not in SYSTEM_STATES:
            raise ValueError(f"unsupported system state: {self.state}")

    def as_dict(self) -> dict[str, str | None]:
        return {
            "state": self.state,
            "freshness": self.freshness,
            "source": self.source,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CommandCenterStatus:
    attention: OwnerAttentionProjection
    pending_decisions: tuple[OwnerAttentionItem, ...]
    business_status: UnsupportedSection
    system_status: SystemStatus
    development_status: OwnerDevelopmentStatus
    recent_activity: UnsupportedSection
    freshness: Mapping[str, str]
    generated_at: str
    source_versions: Mapping[str, str]
    overall_state: str

    def __post_init__(self) -> None:
        if self.overall_state not in UNIFIED_STATES:
            raise ValueError(f"unsupported Command Center state: {self.overall_state}")
        if any(value not in SECTION_STATES for value in self.freshness.values()):
            raise ValueError("unsupported Command Center freshness state")

    def as_dict(self) -> dict[str, Any]:
        return {
            "attention": {
                "items": [item.__dict__ for item in self.attention.items],
                "pending_decisions": [item.__dict__ for item in self.attention.pending_decisions],
                "source_status": [status.__dict__ for status in self.attention.source_status],
                "generated_at": self.attention.generated_at,
                "overall_state": self.attention.overall_state,
            },
            "pending_decisions": [item.__dict__ for item in self.pending_decisions],
            "business_status": self.business_status.as_dict(),
            "system_status": self.system_status.as_dict(),
            "development_status": self.development_status.as_dict(),
            "recent_activity": self.recent_activity.as_dict(),
            "freshness": dict(self.freshness),
            "generated_at": self.generated_at,
            "source_versions": dict(self.source_versions),
            "overall_state": self.overall_state,
        }


def _system_status(attention: OwnerAttentionProjection) -> SystemStatus:
    source = next((item for item in attention.source_status if item.source == "system_health"), None)
    if source is None or source.state != "CURRENT":
        return SystemStatus("UNKNOWN", "UNKNOWN", "OC-B:system_health", source.reason if source else "source_missing")
    if any(item.category == "system" and item.state == "ATTENTION" for item in attention.items):
        return SystemStatus("ATTENTION", "CURRENT", "OC-B:system_health")
    return SystemStatus("CURRENT", "CURRENT", "OC-B:system_health")


def _is_unsupported_placeholder(section: UnsupportedSection) -> bool:
    """True only for the by-design unsupported-capability marker.

    A real (supported) business/recent-activity source would carry a
    different `reason`; only the intentional placeholder is exempt from
    degrading `overall_state` — a genuinely unknown/stale *real* source
    must still degrade it (rule below).
    """

    return section.reason == "unsupported_canonical_source"


def _overall_state(
    attention: OwnerAttentionProjection,
    development: OwnerDevelopmentStatus,
    business: UnsupportedSection,
    system: SystemStatus,
    recent_activity: UnsupportedSection,
) -> str:
    attention_unavailable = attention.overall_state == "UNKNOWN"
    development_unavailable = development.projection_state == "UNKNOWN"
    if attention_unavailable and development_unavailable:
        return "UNKNOWN"
    if any(item.owner_action_required and item.state == "ATTENTION" for item in attention.items):
        return "ATTENTION"
    if attention.overall_state == "ATTENTION":
        return "ATTENTION"
    business_degrades = (
        not _is_unsupported_placeholder(business) and business.state in {"STALE", "PARTIAL", "UNKNOWN"}
    )
    recent_activity_degrades = (
        not _is_unsupported_placeholder(recent_activity)
        and recent_activity.state in {"STALE", "PARTIAL", "UNKNOWN"}
    )
    if (
        attention_unavailable
        or attention.overall_state == "STALE"
        or development.projection_state in {"PARTIAL", "UNKNOWN"}
        or business_degrades
        or system.state in {"STALE", "PARTIAL", "UNKNOWN"}
        or recent_activity_degrades
    ):
        return "PARTIAL"
    return "OK"


def compose_command_center_status(
    attention: OwnerAttentionProjection,
    development: OwnerDevelopmentStatus,
    *,
    generated_at: str | None = None,
    business_status: UnsupportedSection | None = None,
    recent_activity: UnsupportedSection | None = None,
) -> CommandCenterStatus:
    """Compose existing projections without rereading or reconciling sources."""

    timestamp = generated_at or _now_iso()
    business = business_status or UnsupportedSection()
    activity = recent_activity or UnsupportedSection()
    system = _system_status(attention)
    freshness = {
        "attention": "CURRENT" if attention.overall_state in {"OK", "ATTENTION"} else attention.overall_state,
        "development": development.projection_state,
        "business_status": business.state,
        "system_status": "CURRENT" if system.state == "ATTENTION" else system.state,
        "recent_activity": activity.state,
    }
    return CommandCenterStatus(
        attention=attention,
        pending_decisions=attention.pending_decisions,
        business_status=business,
        system_status=system,
        development_status=development,
        recent_activity=activity,
        freshness=freshness,
        generated_at=timestamp,
        source_versions={
            "attention": "OC-B:OwnerAttentionProjection",
            "development_status": development.source_version,
            "business_status": business.source_version,
            "system_status": "OC-B:system_health",
            "recent_activity": activity.source_version,
        },
        overall_state=_overall_state(attention, development, business, system, activity),
    )
