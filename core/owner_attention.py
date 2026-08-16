"""Read-only business attention projection for the future Command Center.

This module deliberately does not own any business lifecycle.  It normalizes
bounded reads from existing TMA sources into an internal projection.  A caller
may inject source functions for tests or integration; default adapters import
the existing TMA helpers lazily to avoid creating a second source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from typing import Any, Callable, Mapping, Sequence


ATTENTION_STATES = frozenset({"OK", "ATTENTION", "UNKNOWN", "STALE"})
SOURCE_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN", "UNSUPPORTED"})
FRESHNESS_VALUES = frozenset({"current", "stale", "unknown", "unavailable", "snapshot"})
SEVERITIES = frozenset({"INFO", "WARNING", "CRITICAL"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_or_now(value: Any = None) -> str:
    if value is None:
        return _now_iso()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


@dataclass(frozen=True)
class OwnerAttentionItem:
    """Owner-readable projection item; IDs are intentionally absent."""

    signal_key: str
    domain: str
    category: str
    severity: str
    state: str
    title: str
    summary: str
    reason: str
    source_kind: str
    source_name: str
    source_ref: str
    detected_at: str
    last_checked_at: str
    freshness: str
    owner_action_required: bool
    destination: str
    canonicality: str

    def __post_init__(self) -> None:
        if self.state not in ATTENTION_STATES:
            raise ValueError(f"unsupported attention state: {self.state}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unsupported severity: {self.severity}")
        if self.freshness not in FRESHNESS_VALUES:
            raise ValueError(f"unsupported freshness: {self.freshness}")


@dataclass(frozen=True)
class SourceStatus:
    source: str
    state: str
    checked_at: str
    freshness: str
    item_count: int = 0
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.state not in SOURCE_STATES:
            raise ValueError(f"unsupported source state: {self.state}")
        if self.freshness not in FRESHNESS_VALUES:
            raise ValueError(f"unsupported freshness: {self.freshness}")


@dataclass(frozen=True)
class CollectorResult:
    source: str
    payload: Any = None
    status: SourceStatus | None = None


@dataclass(frozen=True)
class OwnerAttentionProjection:
    items: tuple[OwnerAttentionItem, ...]
    pending_decisions: tuple[OwnerAttentionItem, ...]
    source_status: tuple[SourceStatus, ...]
    generated_at: str
    overall_state: str

    def __post_init__(self) -> None:
        if self.overall_state not in ATTENTION_STATES:
            raise ValueError(f"unsupported projection state: {self.overall_state}")


SourceReader = Callable[[], Any]
PayloadValidator = Callable[[Any], None]


class PayloadValidationError(ValueError):
    """The transport succeeded but the source contract was not proven."""


@dataclass(frozen=True)
class OwnerAttentionSources:
    approvals: SourceReader
    tasks: SourceReader
    system_health: SourceReader
    projects: SourceReader
    marketing: SourceReader
    ventures: SourceReader


def _current_status(source: str, checked_at: str, item_count: int) -> SourceStatus:
    return SourceStatus(source, "CURRENT", checked_at, "current", item_count)


def _failed_status(source: str, checked_at: str, error: Exception) -> SourceStatus:
    reason = (
        f"invalid_payload:{error}"
        if isinstance(error, PayloadValidationError)
        else f"source_read_failed:{type(error).__name__}"
    )
    return SourceStatus(
        source,
        "UNKNOWN",
        checked_at,
        "unknown",
        reason=reason,
    )


def _run_reader(
    source: str,
    reader: SourceReader,
    checked_at: str,
    validator: PayloadValidator,
) -> CollectorResult:
    try:
        payload = reader()
        validator(payload)
        count = _payload_count(payload)
        return CollectorResult(source, payload, _current_status(source, checked_at, count))
    except Exception as error:  # source isolation is part of the contract
        return CollectorResult(source, None, _failed_status(source, checked_at, error))


def _mapping(payload: Any, source: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise PayloadValidationError(f"{source}:payload_not_mapping")
    return payload


def _nonnegative_int(payload: Mapping[str, Any], key: str, source: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value < 0:
        raise PayloadValidationError(f"{source}:{key}_invalid")
    return value


def _validate_approvals(payload: Any) -> None:
    data = _mapping(payload, "approvals")
    _nonnegative_int(data, "pending_count", "approvals")
    pending = data.get("pending")
    if not isinstance(pending, list) or not all(isinstance(item, Mapping) for item in pending):
        raise PayloadValidationError("approvals:pending_invalid")


def _validate_tasks(payload: Any) -> None:
    data = _mapping(payload, "tasks")
    _nonnegative_int(data, "overdue_tasks", "tasks")


def _validate_system_health(payload: Any) -> None:
    data = _mapping(payload, "system_health")
    status = data.get("status")
    if not isinstance(status, str) or status.lower() not in {"ok", "degraded", "emergency"}:
        raise PayloadValidationError("system_health:status_invalid")
    active = data.get("active_emergency")
    if not isinstance(active, list):
        raise PayloadValidationError("system_health:active_emergency_invalid")


def _validate_projects(payload: Any) -> None:
    data = _mapping(payload, "projects")
    _nonnegative_int(data, "hot_leads_count", "projects")
    projects = data.get("projects")
    if not isinstance(projects, list) or not all(isinstance(item, Mapping) for item in projects):
        raise PayloadValidationError("projects:projects_invalid")


def _validate_marketing(payload: Any) -> None:
    data = _mapping(payload, "marketing")
    demands = data.get("demands")
    if not isinstance(demands, list):
        raise PayloadValidationError("marketing:demands_invalid")
    for demand in demands:
        if not isinstance(demand, Mapping):
            raise PayloadValidationError("marketing:demand_invalid")
        _nonnegative_int(demand, "pending_creative_count", "marketing")


def _validate_ventures(payload: Any) -> None:
    data = _mapping(payload, "ventures")
    active = _nonnegative_int(data, "active", "ventures")
    total = _nonnegative_int(data, "total", "ventures")
    if active > total:
        raise PayloadValidationError("ventures:active_exceeds_total")
    stage_counts = data.get("stage_counts")
    if not isinstance(stage_counts, Mapping) or any(
        not isinstance(stage, str) or type(count) is not int or count < 0
        for stage, count in stage_counts.items()
    ):
        raise PayloadValidationError("ventures:stage_counts_invalid")


SOURCE_VALIDATORS: Mapping[str, PayloadValidator] = {
    "approvals": _validate_approvals,
    "tasks": _validate_tasks,
    "system_health": _validate_system_health,
    "projects": _validate_projects,
    "marketing": _validate_marketing,
    "ventures": _validate_ventures,
}


def _payload_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        for key in ("pending_count", "overdue_tasks", "hot_leads_count", "count"):
            value = payload.get(key)
            if isinstance(value, int):
                return value
        for key in ("approvals", "demands", "ventures", "projects"):
            value = payload.get(key)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return len(value)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        return len(payload)
    return 0


def _item(
    *,
    signal_key: str,
    domain: str,
    category: str,
    severity: str,
    title: str,
    summary: str,
    reason: str,
    source_name: str,
    source_ref: str,
    checked_at: str,
    owner_action_required: bool,
    destination: str,
    canonicality: str,
    state: str = "ATTENTION",
) -> OwnerAttentionItem:
    return OwnerAttentionItem(
        signal_key=signal_key,
        domain=domain,
        category=category,
        severity=severity,
        state=state,
        title=title,
        summary=summary,
        reason=reason,
        source_kind="api_read",
        source_name=source_name,
        source_ref=source_ref,
        detected_at=checked_at,
        last_checked_at=checked_at,
        freshness="current",
        owner_action_required=owner_action_required,
        destination=destination,
        canonicality=canonicality,
    )


def _approval_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    if not result.status or result.status.state != "CURRENT":
        return []
    payload = result.payload or {}
    pending = payload.get("pending") or [] if isinstance(payload, Mapping) else []
    count = payload.get("pending_count", len(pending)) if isinstance(payload, Mapping) else 0
    if not count:
        return []
    items = [
        _item(
            signal_key="approvals.pending",
            domain="global",
            category="approval",
            severity="WARNING",
            title="החלטות ממתינות",
            summary=f"{count} אישורים ממתינים להחלטת בעלים",
            reason="קיימות רשומות Approval במצב ממתין במקור הקנוני",
            source_name="Approvals",
            source_ref="tma_api.get_approvals",
            checked_at=checked_at,
            owner_action_required=True,
            destination="approvals",
            canonicality="canonical",
        )
    ]
    actionable = [
        approval for approval in pending
        if isinstance(approval, Mapping) and approval.get("actionable") is True
    ]
    actionable.sort(key=lambda approval: (
        str(approval.get("action", "")),
        str(approval.get("context_type", "")),
    ))
    seen: dict[str, int] = {}
    for approval in actionable[:3]:
        action = str(approval.get("action", "")).strip()
        context = str(approval.get("context_type", "")).strip()
        if not action:
            continue
        fragment = re.sub(r"[^a-z0-9א-ת]+", "-", f"{action}-{context}".lower()).strip("-") or "decision"
        seen[fragment] = seen.get(fragment, 0) + 1
        suffix = f":{seen[fragment]}" if seen[fragment] > 1 else ""
        items.append(
            _item(
                signal_key=f"approvals.pending.preview:{fragment}{suffix}",
                domain="global",
                category="approval",
                severity="WARNING",
                title=action,
                summary="החלטה actionable ממתינה לאישור או דחייה",
                reason="הפריט סומן actionable על ידי נתיב האישורים הקנוני",
                source_name="Approvals",
                source_ref="tma_api.get_approvals",
                checked_at=checked_at,
                owner_action_required=True,
                destination="approvals",
                canonicality="canonical",
            )
        )
    return items


def _task_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    if not result.status or result.status.state != "CURRENT":
        return []
    count = result.payload.get("overdue_tasks", 0) if isinstance(result.payload, Mapping) else 0
    if not count:
        return []
    return [
        _item(
            signal_key="tasks.overdue.global",
            domain="global",
            category="task",
            severity="WARNING",
            title="משימות שעברו מועד",
            summary=f"{count} משימות עברו את מועד היעד",
            reason="ספירת Tasks גלובלית לפי תאריך יעד וסטטוס",
            source_name="Tasks",
            source_ref="tma_api._get_global_kpis",
            checked_at=checked_at,
            owner_action_required=True,
            destination="actions",
            canonicality="derived",
        )
    ]


def _system_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    if not result.status or result.status.state != "CURRENT":
        return []
    payload = result.payload or {}
    if not isinstance(payload, Mapping):
        return []
    status = str(payload.get("status", "unknown")).lower()
    if status == "emergency" or payload.get("active_emergency"):
        return [
            _item(
                signal_key="system.emergency",
                domain="global",
                category="system",
                severity="CRITICAL",
                title="מצב חירום פעיל",
                summary="קיימת עצירת חירום פעילה במערכת",
                reason="מקור System Health דיווח על emergency או דגל חירום פעיל",
                source_name="System Health",
                source_ref="tma_api.system_health",
                checked_at=checked_at,
                owner_action_required=True,
                destination="system_health",
                canonicality="canonical",
            )
        ]
    if status == "degraded":
        return [
            _item(
                signal_key="system.health.degraded",
                domain="global",
                category="system",
                severity="CRITICAL",
                title="מצב המערכת דורש בדיקה",
                summary="אחד או יותר משירותי המערכת אינם תקינים",
                reason="מקור System Health דיווח על degraded",
                source_name="System Health",
                source_ref="tma_api.system_health",
                checked_at=checked_at,
                owner_action_required=True,
                destination="system_health",
                canonicality="canonical",
            )
        ]
    return []


def _project_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    if not result.status or result.status.state != "CURRENT":
        return []
    payload = result.payload or {}
    hot_count = payload.get("hot_leads_count", 0) if isinstance(payload, Mapping) else 0
    if not hot_count:
        return []
    return [
        _item(
            signal_key="leads.hot.visible_domains",
            domain="global",
            category="lead",
            severity="WARNING",
            title="לידים חמים דורשים בדיקה",
            summary=f"{hot_count} לידים קיבלו ציון חם בתחומים המוצגים",
            reason="נגזר מ־Leads פעילים עם score >= 70 בתחומים גלויים",
            source_name="Projects Hub / Leads",
            source_ref="tma_api._get_project_cards",
            checked_at=checked_at,
            owner_action_required=True,
            destination="projects",
            canonicality="derived",
        )
    ]


def _marketing_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    if not result.status or result.status.state != "CURRENT":
        return []
    payload = result.payload or {}
    demands = payload.get("demands", []) if isinstance(payload, Mapping) else []
    pending = sum(int(d.get("pending_creative_count", 0) or 0) for d in demands if isinstance(d, Mapping))
    if not pending:
        return []
    return [
        _item(
            signal_key="marketing.pending_review",
            domain="marketing",
            category="marketing",
            severity="WARNING",
            title="חומרי שיווק ממתינים לבדיקה",
            summary=f"{pending} פריטי creative מסומנים כ־Pending Review",
            reason="ספירת pending_creative_count ממקור Marketing הקנוני",
            source_name="Marketing Demands",
            source_ref="tma_api._marketing_status_payload",
            checked_at=checked_at,
            owner_action_required=True,
            destination="marketing",
            canonicality="derived",
        )
    ]


def _venture_items(result: CollectorResult, checked_at: str) -> list[OwnerAttentionItem]:
    """Active Ventures is an informational summary, not a priority alert."""
    if not result.status or result.status.state != "CURRENT":
        return []
    payload = result.payload or {}
    active = payload.get("active", 0) if isinstance(payload, Mapping) else 0
    if not active:
        return []
    return [
        _item(
            signal_key="ventures.active_summary",
            domain="ventures",
            category="venture",
            severity="INFO",
            state="OK",
            title="מיזמים פעילים",
            summary=f"{active} מיזמים נמצאים בשלבי עבודה",
            reason="ספירת Ventures בשלבים שאינם NO-GO או Converted",
            source_name="Ventures",
            source_ref="tma_api._owner_strategic_pipeline",
            checked_at=checked_at,
            owner_action_required=False,
            destination="ventures",
            canonicality="canonical",
        )
    ]


def _default_sources(identity: Any) -> OwnerAttentionSources:
    """Adapt existing TMA reads without copying their source logic."""

    def approvals() -> Mapping[str, Any]:
        from tma_api import _owner_approvals_snapshot

        payload, warnings = _owner_approvals_snapshot(identity)
        if warnings:
            raise RuntimeError(";".join(warnings))
        return payload

    def tasks() -> Mapping[str, Any]:
        from tma_api import _get_global_kpis

        return _get_global_kpis()

    def health() -> Mapping[str, Any]:
        from tma_api import system_health

        response = system_health(identity)
        return response.get_json() if hasattr(response, "get_json") else response

    def projects() -> Mapping[str, Any]:
        from tma_api import _get_project_cards

        cards, hot_leads_count = _get_project_cards(identity)
        return {"projects": cards, "hot_leads_count": hot_leads_count}

    def marketing() -> Mapping[str, Any]:
        from tma_api import _marketing_status_payload

        return _marketing_status_payload(identity)

    def ventures() -> Mapping[str, Any]:
        from tma_api import _owner_strategic_pipeline

        return _owner_strategic_pipeline()

    return OwnerAttentionSources(approvals, tasks, health, projects, marketing, ventures)


def _overall_state(items: Sequence[OwnerAttentionItem], statuses: Sequence[SourceStatus]) -> str:
    if any(item.state == "ATTENTION" for item in items):
        return "ATTENTION"
    if any(status.state == "UNKNOWN" for status in statuses):
        return "UNKNOWN"
    if any(status.state == "STALE" for status in statuses):
        return "STALE"
    return "OK"


def build_owner_attention_projection(
    identity: Any,
    *,
    sources: OwnerAttentionSources | None = None,
    checked_at: str | None = None,
) -> OwnerAttentionProjection:
    """Collect supported signals with source isolation and deterministic order."""

    timestamp = checked_at or _now_iso()
    source_set = sources or _default_sources(identity)
    readers = (
        ("approvals", source_set.approvals),
        ("tasks", source_set.tasks),
        ("system_health", source_set.system_health),
        ("projects", source_set.projects),
        ("marketing", source_set.marketing),
        ("ventures", source_set.ventures),
    )
    results = [
        _run_reader(name, reader, timestamp, SOURCE_VALIDATORS[name])
        for name, reader in readers
    ]
    item_builders = {
        "approvals": _approval_items,
        "tasks": _task_items,
        "system_health": _system_items,
        "projects": _project_items,
        "marketing": _marketing_items,
        "ventures": _venture_items,
    }
    items: list[OwnerAttentionItem] = []
    statuses: list[SourceStatus] = []
    for result in results:
        if result.status is None:
            continue
        statuses.append(result.status)
        items.extend(item_builders[result.source](result, timestamp))

    # Display ordering is deterministic grouping, not cross-domain priority.
    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    category_order = {"system": 0, "approval": 1, "task": 2, "lead": 3, "marketing": 4, "venture": 5}
    items.sort(key=lambda item: (severity_order[item.severity], category_order.get(item.category, 99), item.signal_key))
    pending = tuple(item for item in items if item.category == "approval")
    return OwnerAttentionProjection(
        items=tuple(items),
        pending_decisions=pending,
        source_status=tuple(statuses),
        generated_at=timestamp,
        overall_state=_overall_state(items, statuses),
    )
