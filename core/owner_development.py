"""Deterministic, read-only development status projection.

OC-C summarizes existing repository authorities; it is not a tracker and does
not write status anywhere.  The precedence below is intentionally explicit:

1. scoped production evidence (when a source contains it);
2. current main implementation evidence;
3. active planning documents (ROADMAP first, then the unified registry);
4. defect/change ledgers and current briefing;
5. dated snapshots and archived documents.

In particular, MERGED is never upgraded to DEPLOYED or RUNTIME_VERIFIED by
this module.  Only explicit source wording can provide those evidence states.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Callable, Iterable, Mapping


WORK_STATES = frozenset({
    "ACTIVE", "NEXT", "NEEDS_VERIFICATION", "BLOCKED",
    "OWNER_DECISION", "CLOSED", "UNKNOWN",
})
EVIDENCE_STATES = frozenset({
    "PLANNED", "CODE_DONE", "MERGED", "WIRED", "DEPLOYED",
    "RUNTIME_VERIFIED", "UNKNOWN",
})
FRESHNESS_STATES = frozenset({"current", "stale", "unknown"})
PROJECTION_STATES = frozenset({"CURRENT", "UNKNOWN"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "unknown-initiative"


def _owner_text(value: str | None) -> str | None:
    """Keep owner-facing text useful without leaking record/commit identifiers."""
    if value is None:
        return None
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\brec[A-Za-z0-9]{8,}\b", "[internal-id]", value)
    value = re.sub(r"\b[0-9a-f]{7,40}\b", "[commit-ref]", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class DevelopmentItem:
    initiative_key: str
    title: str
    horizon: str | None
    state: str
    summary: str
    next_step: str | None
    blocker: str | None
    decision_question: str | None
    evidence_state: str
    freshness: str
    source_refs: tuple[str, ...]
    source_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.state not in WORK_STATES:
            raise ValueError(f"unsupported development state: {self.state}")
        if self.evidence_state not in EVIDENCE_STATES:
            raise ValueError(f"unsupported evidence state: {self.evidence_state}")
        if self.freshness not in FRESHNESS_STATES:
            raise ValueError(f"unsupported freshness: {self.freshness}")


@dataclass(frozen=True)
class SourceVersion:
    path: str
    version: str
    authority: str
    freshness: str

    def as_text(self) -> str:
        return f"{self.path}@{self.version}"


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
    source_versions: tuple[SourceVersion, ...]
    projection_state: str

    def __post_init__(self) -> None:
        if self.projection_state not in PROJECTION_STATES:
            raise ValueError(f"unsupported projection state: {self.projection_state}")

    def as_dict(self) -> dict[str, object]:
        def item(value: DevelopmentItem) -> dict[str, object]:
            return {
                "initiative_key": value.initiative_key,
                "title": value.title,
                "horizon": value.horizon,
                "state": value.state,
                "summary": value.summary,
                "next_step": value.next_step,
                "blocker": value.blocker,
                "decision_question": value.decision_question,
                "evidence_state": value.evidence_state,
                "freshness": value.freshness,
                "source_refs": list(value.source_refs),
                "source_versions": list(value.source_versions),
            }

        return {
            "current_focus": [item(value) for value in self.current_focus],
            "next_actions": [item(value) for value in self.next_actions],
            "needs_verification": [item(value) for value in self.needs_verification],
            "blocked": [item(value) for value in self.blocked],
            "owner_decisions": [item(value) for value in self.owner_decisions],
            "recently_closed": [item(value) for value in self.recently_closed],
            "horizon_summary": [
                {"horizon": horizon, "initiatives": list(initiatives)}
                for horizon, initiatives in self.horizon_summary
            ],
            "updated_at": self.updated_at,
            "source_versions": [
                {"path": value.path, "version": value.version,
                 "authority": value.authority, "freshness": value.freshness}
                for value in self.source_versions
            ],
            "projection_state": self.projection_state,
        }


@dataclass(frozen=True)
class _RegistryEntry:
    title: str
    scope: str
    horizon: str | None
    stage: str
    next_step: str | None
    row_number: int


def _read_sources(repo_root: Path) -> dict[str, str]:
    paths = (
        "ROADMAP.md",
        "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md",
        "BUG_AUDIT_LOG.md",
        "CHANGE_CONTROL_LOG.md",
        "AI_CONTEXT.md",
    )
    return {path: (repo_root / path).read_text(encoding="utf-8") for path in paths}


def _git_version(repo_root: Path, path: str, main_ref: str) -> str:
    command = ["git", "log", "-1", "--format=%H", main_ref, "--", path]
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def _main_version(repo_root: Path, main_ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", main_ref], cwd=repo_root, text=True,
        capture_output=True, check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def _registry_rows(text: str) -> list[_RegistryEntry]:
    marker = "## 3.5 רישום עבודה חי"
    start = text.find(marker)
    if start < 0:
        raise ValueError("active work registry not found")
    end = text.find("\n## ", start + len(marker))
    section = text[start:] if end < 0 else text[start:end]
    entries: list[_RegistryEntry] = []
    for row_number, line in enumerate(section.splitlines(), 1):
        if not line.startswith("|") or line.count("|") < 5:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].startswith("---") or cells[0] in {"יוזמה / מסמך", ""}:
            continue
        horizon_match = re.search(r"\bH[0-7](?:-H[0-7])?\b", cells[2])
        horizon = horizon_match.group(0) if horizon_match else None
        if horizon is None:
            continue
        entries.append(_RegistryEntry(
            title=cells[0].strip("`") or "Unknown initiative",
            scope=cells[1], horizon=horizon, stage=cells[3],
            next_step=cells[4] if cells[4] and cells[4] != "—" else None,
            row_number=row_number,
        ))
    if not entries:
        raise ValueError("active work registry has no Horizon entries")
    return entries


def _horizons(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2).strip()
        for match in re.finditer(r"^### (Horizon [0-7]) — (.+)$", text, re.MULTILINE)
    }


def _has(text: str, *markers: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _evidence_state(stage: str) -> str:
    if _has(stage, "RUNTIME_VERIFIED", "VERIFIED IN PROD", "מאומת בפרוד", "production verified: כן"):
        return "RUNTIME_VERIFIED"
    if _has(stage, "DEPLOYED", "פרוס", "deployed"):
        return "DEPLOYED"
    if _has(stage, "WIRED", "מחובר"):
        return "WIRED"
    if _has(stage, "MERGED", "ממוזג", "merged"):
        return "MERGED"
    if _has(stage, "CODE DONE", "קוד הושלם", "מימוש", "implemented"):
        return "CODE_DONE"
    if _has(stage, "PLANNED", "טרם התחיל", "backlog", "parking lot"):
        return "PLANNED"
    return "UNKNOWN"


def _item_state(stage: str, next_step: str | None, evidence: str) -> tuple[str, str | None, str | None]:
    if _has(stage, "ממתין להחלטת owner", "ממתין להחלטת בעלים", "owner decision", "owner gate"):
        return "OWNER_DECISION", None, next_step
    if _has(stage, "חסום", "blocked", "blocker"):
        return "BLOCKED", stage, None
    if _has(stage, "בעבודה בפועל", "active", "in progress"):
        return "ACTIVE", None, None
    if evidence in {"MERGED", "WIRED", "DEPLOYED", "CODE_DONE"} and _has(
        stage, "לא verified", "לא אומת", "טרם אומת", "not production", "לא עדיין"
    ):
        return "NEEDS_VERIFICATION", None, None
    if next_step:
        return "NEXT", None, None
    return "UNKNOWN", None, None


def _registry_item(entry: _RegistryEntry, versions: tuple[str, ...]) -> DevelopmentItem:
    evidence = _evidence_state(entry.stage)
    state, blocker, decision_question = _item_state(entry.stage, entry.next_step, evidence)
    return DevelopmentItem(
        initiative_key=_slug(entry.title), title=entry.title, horizon=entry.horizon,
        state=state, summary=_owner_text(entry.stage) or "Unknown current stage",
        next_step=_owner_text(entry.next_step), blocker=_owner_text(blocker),
        decision_question=_owner_text(decision_question),
        evidence_state=evidence, freshness="current", source_refs=(
            f"docs/governance/BOSS_UNIFIED_MASTER_PLAN.md:registry-row-{entry.row_number}",
        ), source_versions=versions,
    )


def _recently_closed(text: str, versions: tuple[str, ...]) -> tuple[DevelopmentItem, ...]:
    marker = "## 3. Completed Since Last Update"
    start = text.find(marker)
    if start < 0:
        return ()
    end = text.find("\n## ", start + len(marker))
    section = text[start:] if end < 0 else text[start:end]
    result: list[DevelopmentItem] = []
    for line_number, line in enumerate(section.splitlines(), 1):
        match = re.match(r"^- \*\*(.+?)\*\*", line)
        if not match:
            continue
        if not _has(line, "מוזג", "merged", "implemented", "closed"):
            continue
        title = re.sub(r"\s+\(.+?\)$", "", match.group(1)).strip()
        result.append(DevelopmentItem(
            initiative_key=_slug(title), title=title, horizon=None, state="CLOSED",
            summary=_owner_text(line[2:].strip()) or "Closed item",
            next_step=None, blocker=None,
            decision_question=None, evidence_state="MERGED", freshness="current",
            source_refs=(f"AI_CONTEXT.md:completed-line-{line_number}",),
            source_versions=versions,
        ))
        if len(result) >= 8:
            break
    return tuple(result)


def _brief_items(text: str, versions: tuple[str, ...]) -> tuple[DevelopmentItem, ...]:
    """Read only explicit current-state bullets from the current briefing."""
    sections = (
        ("**מיושם חלקית / לא production-active:**", "verification"),
        ("**חסום (החלטה ארכיטקטונית/owner):**", "blocked"),
    )
    result: list[DevelopmentItem] = []
    for marker, section_kind in sections:
        start = text.find(marker)
        if start < 0:
            continue
        boundaries = [value for value in (
            text.find("\n**", start + len(marker)),
            text.find("\n## ", start + len(marker)),
        ) if value >= 0]
        end = min(boundaries) if boundaries else -1
        section = text[start:] if end < 0 else text[start:end]
        for line_number, line in enumerate(section.splitlines(), 1):
            match = re.match(r"^- \*\*(.+?)\*\*", line)
            if match:
                title = match.group(1).strip()
            elif section_kind == "blocked" and line.startswith("- "):
                title = line[2:].split("—", 1)[0].strip(" `")
            else:
                continue
            evidence = _evidence_state(line)
            if section_kind == "blocked":
                state = "OWNER_DECISION" if _has(line, "owner", "החלטת") else "BLOCKED"
                blocker = line[2:].strip() if state == "BLOCKED" else None
                decision = line[2:].strip() if state == "OWNER_DECISION" else None
            else:
                state = "NEEDS_VERIFICATION" if _has(
                    line, "לא אומת", "verification עדיין פתוח", "לא verified", "not verified"
                ) else "UNKNOWN"
                blocker = decision = None
            if state == "UNKNOWN":
                continue
            result.append(DevelopmentItem(
                initiative_key=_slug(title), title=title, horizon=None, state=state,
                summary=_owner_text(line[2:].strip()) or "Unknown current state",
                next_step=None, blocker=_owner_text(blocker),
                decision_question=_owner_text(decision), evidence_state=evidence,
                freshness="current", source_refs=(f"AI_CONTEXT.md:brief-line-{line_number}",),
                source_versions=versions,
            ))
    return tuple(result)


def generate_owner_development_status(
    repo_root: str | Path = ".",
    *,
    main_ref: str = "origin/main",
    checked_at: str | None = None,
    source_texts: Mapping[str, str] | None = None,
    version_resolver: Callable[[Path, str, str], str] = _git_version,
) -> OwnerDevelopmentStatus:
    """Build the OC-C projection from repository authorities without writes."""
    root = Path(repo_root)
    checked_at = checked_at or _now_iso()
    try:
        texts = dict(source_texts or _read_sources(root))
        registry_text = texts["docs/governance/BOSS_UNIFIED_MASTER_PLAN.md"]
        entries = _registry_rows(registry_text)
        main_sha = _main_version(root, main_ref)
        versions = tuple(
            SourceVersion(path, version_resolver(root, path, main_ref), authority, "current")
            for path, authority in (
                ("ROADMAP.md", "planning"),
                ("docs/governance/BOSS_UNIFIED_MASTER_PLAN.md", "registry"),
                ("CHANGE_CONTROL_LOG.md", "change_evidence"),
                ("AI_CONTEXT.md", "briefing"),
            )
        )
        version_text = tuple(value.as_text() for value in versions) + (f"main@{main_sha}",)
        registry_items = tuple(_registry_item(entry, version_text) for entry in entries)
        brief_items = _brief_items(texts.get("AI_CONTEXT.md", ""), version_text)
        items = registry_items + brief_items
        horizons = _horizons(registry_text)
        grouped: dict[str, list[str]] = {}
        for item in items:
            if item.horizon:
                grouped.setdefault(item.horizon, []).append(item.title)
        horizon_summary = tuple(
            (f"Horizon {number} — {horizons.get(f'Horizon {number}', 'Unknown')}", tuple(grouped.get(f"H{number}", [])))
            for number in range(8) if grouped.get(f"H{number}")
        )
        return OwnerDevelopmentStatus(
            current_focus=tuple(item for item in items if item.state == "ACTIVE"),
            next_actions=tuple(item for item in items if item.state == "NEXT"),
            needs_verification=tuple(item for item in items if item.state == "NEEDS_VERIFICATION"),
            blocked=tuple(item for item in items if item.state == "BLOCKED"),
            owner_decisions=tuple(item for item in items if item.state == "OWNER_DECISION"),
            recently_closed=_recently_closed(texts.get("AI_CONTEXT.md", ""), version_text),
            horizon_summary=horizon_summary, updated_at=checked_at,
            source_versions=versions + (SourceVersion("main", main_sha, "implementation", "current"),),
            projection_state="CURRENT",
        )
    except (OSError, UnicodeError, ValueError, KeyError):
        return OwnerDevelopmentStatus(
            current_focus=(), next_actions=(), needs_verification=(), blocked=(),
            owner_decisions=(), recently_closed=(), horizon_summary=(),
            updated_at=checked_at, source_versions=(), projection_state="UNKNOWN",
        )


__all__ = [
    "DevelopmentItem", "EVIDENCE_STATES", "OwnerDevelopmentStatus",
    "PROJECTION_STATES", "WORK_STATES", "generate_owner_development_status",
]
