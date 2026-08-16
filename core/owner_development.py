"""Read-only owner development projection from canonical §3.5 only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from dev_registry_contract import REGISTRY_PATH, RegistryRow, RegistryValidationError, validate_registry_file, validate_registry_text


FRESHNESS_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN"})
PROJECTION_STATES = frozenset({"CURRENT", "PARTIAL", "UNKNOWN"})
FRESHNESS_THRESHOLD = timedelta(days=7)
SECTION_BOUNDS = {
    "current_focus": 8,
    "next_actions": 5,
    "needs_verification": 5,
    "blocked": 5,
    "owner_decisions": 5,
    "recently_closed": 5,
}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _freshness(value: str, checked_at: datetime) -> str:
    age = checked_at - _parse_timestamp(value)
    return "CURRENT" if age <= FRESHNESS_THRESHOLD else "STALE"


@dataclass(frozen=True)
class DevelopmentItem:
    initiative_key: str
    title: str
    horizon: str
    work_state: str
    current_stage: str
    evidence_state: str
    next_step: str
    needs_verification: bool
    blocked: bool
    owner_decision_required: bool
    freshness: str
    last_reconciled: str
    evidence_source: str

    def __post_init__(self) -> None:
        if self.freshness not in FRESHNESS_STATES:
            raise ValueError(f"unsupported freshness: {self.freshness}")

    def as_dict(self) -> dict[str, object]:
        return {
            "initiative_key": self.initiative_key,
            "title": self.title,
            "horizon": self.horizon,
            "work_state": self.work_state,
            "current_stage": self.current_stage,
            "evidence_state": self.evidence_state,
            "next_step": self.next_step,
            "needs_verification": self.needs_verification,
            "blocked": self.blocked,
            "owner_decision_required": self.owner_decision_required,
            "freshness": self.freshness,
            "last_reconciled": self.last_reconciled,
        }


@dataclass(frozen=True)
class OwnerDevelopmentStatus:
    current_focus: tuple[DevelopmentItem, ...]
    next_actions: tuple[DevelopmentItem, ...]
    needs_verification: tuple[DevelopmentItem, ...]
    blocked: tuple[DevelopmentItem, ...]
    owner_decisions: tuple[DevelopmentItem, ...]
    recently_closed: tuple[DevelopmentItem, ...]
    horizon_summary: tuple[tuple[str, tuple[str, ...]], ...]
    updated_at: str
    source_version: str
    projection_state: str

    def __post_init__(self) -> None:
        if self.projection_state not in PROJECTION_STATES:
            raise ValueError(f"unsupported projection state: {self.projection_state}")

    def as_dict(self) -> dict[str, object]:
        def items(values: Iterable[DevelopmentItem]) -> list[dict[str, object]]:
            return [value.as_dict() for value in values]
        return {
            "current_focus": items(self.current_focus),
            "next_actions": items(self.next_actions),
            "needs_verification": items(self.needs_verification),
            "blocked": items(self.blocked),
            "owner_decisions": items(self.owner_decisions),
            "recently_closed": items(self.recently_closed),
            "horizon_summary": [
                {"horizon": horizon, "initiatives": list(initiatives)}
                for horizon, initiatives in self.horizon_summary
            ],
            "updated_at": self.updated_at,
            "source_version": self.source_version,
            "projection_state": self.projection_state,
        }


def _unavailable(checked_at: datetime) -> OwnerDevelopmentStatus:
    empty = ()
    return OwnerDevelopmentStatus(empty, empty, empty, empty, empty, empty, empty,
                                   checked_at.isoformat(), "unavailable", "UNKNOWN")


def _row_item(row: RegistryRow, checked_at: datetime) -> DevelopmentItem:
    value = row.values
    return DevelopmentItem(
        initiative_key=value["Initiative Key"],
        title=value["Initiative / Document"],
        horizon=value["Horizon"],
        work_state=value["Work State"],
        current_stage=value["Current Stage"],
        evidence_state=value["Evidence State"],
        next_step=value["Next Decided Step"],
        needs_verification=value["Needs Verification"] == "true",
        blocked=value["Blocked"] == "true",
        owner_decision_required=value["Owner Decision Required"] == "true",
        freshness=_freshness(value["Last Reconciled"], checked_at),
        last_reconciled=value["Last Reconciled"],
        evidence_source=value["Evidence Source"],
    )


def _sort_key(item: DevelopmentItem) -> tuple[int, int, float, str]:
    # H0 first, explicit gates before normal work, newest reconciliation next,
    # and Initiative Key as the stable final tie-breaker.
    gate = 0 if (item.blocked or item.owner_decision_required) else 1
    return (int(item.horizon[1:]), gate, -_parse_timestamp(item.last_reconciled).timestamp(), item.initiative_key)


def _bounded(items: Iterable[DevelopmentItem], name: str) -> tuple[DevelopmentItem, ...]:
    return tuple(sorted(items, key=_sort_key)[:SECTION_BOUNDS[name]])


def build_owner_development_status(text: str, *, checked_at: str | datetime) -> OwnerDevelopmentStatus:
    checked = _parse_timestamp(checked_at) if isinstance(checked_at, str) else checked_at.astimezone(timezone.utc)
    try:
        rows = validate_registry_text(text)
        items = tuple(_row_item(row, checked) for row in rows)
    except (RegistryValidationError, TypeError, ValueError, OverflowError):
        return _unavailable(checked)
    horizon_summary = tuple(
        (f"H{i}", tuple(item.initiative_key for item in sorted(items, key=lambda x: (x.initiative_key)) if item.horizon == f"H{i}"))
        for i in range(8)
    )
    return OwnerDevelopmentStatus(
        current_focus=_bounded((item for item in items if item.work_state == "ACTIVE"), "current_focus"),
        next_actions=_bounded(
            (item for item in items if item.next_step.strip() and item.next_step.strip() != "—"),
            "next_actions",
        ),
        needs_verification=_bounded((item for item in items if item.needs_verification), "needs_verification"),
        blocked=_bounded((item for item in items if item.blocked or item.work_state == "BLOCKED"), "blocked"),
        owner_decisions=_bounded((item for item in items if item.owner_decision_required or item.work_state == "OWNER_DECISION"), "owner_decisions"),
        recently_closed=_bounded((item for item in items if item.work_state == "CLOSED"), "recently_closed"),
        horizon_summary=horizon_summary,
        updated_at=checked.isoformat(),
        source_version="BOSS_UNIFIED_MASTER_PLAN.md:§3.5",
        projection_state="CURRENT",
    )


def generate_owner_development_status(
    registry_path: Path = REGISTRY_PATH,
    *,
    checked_at: str | None = None,
) -> OwnerDevelopmentStatus:
    checked = _parse_timestamp(checked_at) if checked_at else datetime.now(timezone.utc)
    try:
        text = registry_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _unavailable(checked)
    return build_owner_development_status(text, checked_at=checked)
