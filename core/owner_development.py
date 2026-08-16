"""Deterministic, read-only development status projection.

OC-C summarizes existing repository authorities; it is not a tracker and does
not write status anywhere.  The implemented reconciliation precedence is
intentionally explicit:

1. Active Work Registry supplies identity, Horizon, and declared step.
2. An explicitly linked current ROADMAP line may set the work state.
3. Explicitly linked CHANGE_CONTROL/BUG evidence may set evidence state.
4. Explicitly linked `main` commit subjects may set implementation/merge state.
5. Explicitly scoped production/runtime evidence for that same initiative wins.

AI_CONTEXT is consumed only for bounded current closure/owner-gate sections and
provenance; it is not used to override registry or ROADMAP status. Archived or
unlinked prose is never status evidence.

In particular, MERGED is never upgraded to DEPLOYED or RUNTIME_VERIFIED by
this module.  Only explicit source wording can provide those evidence states.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping


WORK_STATES = frozenset({
    "ACTIVE", "NEXT", "NEEDS_VERIFICATION", "BLOCKED",
    "OWNER_DECISION", "CLOSED", "UNKNOWN",
})
EVIDENCE_STATES = frozenset({
    "PLANNED", "CODE_DONE", "MERGED", "WIRED", "DEPLOYED",
    "RUNTIME_VERIFIED", "UNKNOWN",
})
FRESHNESS_STATES = frozenset({"current", "stale", "unknown"})
PROJECTION_STATES = frozenset({"CURRENT", "PARTIAL", "UNKNOWN"})
RECONCILIATION_STATES = frozenset({"RESOLVED", "UNRESOLVED", "CONFLICT"})


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
    reconciliation_state: str = "RESOLVED"

    def __post_init__(self) -> None:
        if self.state not in WORK_STATES:
            raise ValueError(f"unsupported development state: {self.state}")
        if self.evidence_state not in EVIDENCE_STATES:
            raise ValueError(f"unsupported evidence state: {self.evidence_state}")
        if self.freshness not in FRESHNESS_STATES:
            raise ValueError(f"unsupported freshness: {self.freshness}")
        if self.reconciliation_state not in RECONCILIATION_STATES:
            raise ValueError(f"unsupported reconciliation state: {self.reconciliation_state}")


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
                "reconciliation_state": value.reconciliation_state,
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


@dataclass(frozen=True)
class _Evidence:
    source: str
    source_ref: str
    evidence_state: str
    work_state: str | None = None
    scope_explicit: bool = False
    ambiguous_link: bool = False


@dataclass(frozen=True)
class _Reconciled:
    evidence_state: str
    work_state: str | None
    refs: tuple[str, ...]
    reconciliation_state: str


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


def _main_commit_subjects(repo_root: Path, main_ref: str) -> str:
    result = subprocess.run(
        ["git", "log", "--format=%s", main_ref], cwd=repo_root,
        text=True, capture_output=True, check=False,
    )
    return result.stdout if result.returncode == 0 else ""


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


def _bounded_evidence_state(text: str) -> str:
    """Classify only exact high-confidence phrases from canonical source fields."""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if re.search(r"\b(runtime[_ -]verified|verified in prod|production verified\s*:\s*(yes|כן))\b", normalized):
        return "RUNTIME_VERIFIED"
    if re.search(r"\b(deployed|deploy(ed)?\s*:\s*(yes|כן)|פרוס|נפרס)\b", normalized):
        return "DEPLOYED"
    if re.search(r"\b(wired|מחובר)\b", normalized):
        return "WIRED"
    if re.search(r"\b(merged|מוזג|merge\s*:\s*(yes|כן))\b", normalized):
        return "MERGED"
    if re.search(r"\b(code done|code complete|קוד הושלם)\b", normalized):
        return "CODE_DONE"
    if re.search(r"\b(planned|טרם התחיל|backlog|parking lot)\b", normalized):
        return "PLANNED"
    return "UNKNOWN"


def _explicit_work_state(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if re.search(r"ממתין להחלטת (owner|בעלים)|owner decision|owner gate", normalized):
        return "OWNER_DECISION"
    if re.search(r"\b(blocked|blocker)\b|חסום", normalized):
        return "BLOCKED"
    if re.search(r"\b(active|in progress)\b|בעבודה בפועל", normalized):
        return "ACTIVE"
    if re.search(r"verification (pending|open)|needs verification|לא אומת|טרם אומת|לא verified", normalized):
        return "NEEDS_VERIFICATION"
    return None


def _identity_tokens(entry: _RegistryEntry) -> tuple[str, ...]:
    """Return only explicit identity keys; prose similarity is never a link."""
    title = re.sub(r"\s+", " ", entry.title).strip().lower()
    tokens = set() if re.search(r"(?:\.md|/|\\)", title) else {title}
    tokens.update(value.lower() for value in re.findall(r"\b(?:bug[- ]?\d+[a-z0-9-]*|[cfnu]-\d+|[cfnu]\d+|f\d+|n\d+)\b", entry.title, re.IGNORECASE))
    return tuple(sorted(tokens, key=len, reverse=True))


def _explicitly_links(entry: _RegistryEntry, line: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip().lower()
    for token in _identity_tokens(entry):
        if len(token) >= 8 and token in normalized:
            return True
        if len(token) < 8 and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", normalized):
            return True
    return False


def _ambiguous_link(entry: _RegistryEntry, line: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip().lower()
    title = re.sub(r"\s+", " ", entry.title).strip().lower()
    return bool(
        title and title in normalized
        and re.search(r"\s(?:and|או|/)\s", normalized, re.IGNORECASE)
    )


def _canonical_candidate_lines(entry: _RegistryEntry, text: str, source: str) -> tuple[tuple[int, str], ...]:
    """Select canonical sections before applying identity matching.

    CHANGE_CONTROL/BUG records link through their heading or Requirement field;
    ROADMAP links through a matching section heading.  Short test fixtures may
    omit section structure and are intentionally allowed to use their lines.
    """
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if re.match(r"^#{2,4}\s", line)]
    if not headings:
        return tuple(enumerate(lines, 1))
    selected: list[tuple[int, str]] = []
    for position, start in enumerate(headings):
        end = headings[position + 1] if position + 1 < len(headings) else len(lines)
        block = lines[start:end]
        header_link = _explicitly_links(entry, lines[start])
        requirement_link = any(
            line.lstrip().startswith("- **Requirement:**") and _explicitly_links(entry, line)
            for line in block
        )
        if (source == "roadmap" and header_link) or (source in {"change", "bug"} and (header_link or requirement_link)):
            selected.extend((index + 1, line) for index, line in enumerate(block, start))
    if not selected and len(lines) < 80:
        return tuple(enumerate(lines, 1))
    return tuple(selected)


def _source_evidence(entry: _RegistryEntry, text: str, source: str) -> tuple[_Evidence, ...]:
    evidence: list[_Evidence] = []
    candidate_lines = (
        tuple(enumerate(text.splitlines(), 1))
        if source in {"main", "production"}
        else _canonical_candidate_lines(entry, text, source)
    )
    for line_number, line in candidate_lines:
        if not _explicitly_links(entry, line):
            continue
        state = _main_evidence_state(line) if source == "main" else _bounded_evidence_state(line)
        work_state = _explicit_work_state(line)
        if state == "UNKNOWN" and work_state is None:
            continue
        scope = source == "production" and bool(
            re.search(r"\b(?:production|runtime|staging|deploy|main)\b|פרוד|סטייג'ינג|פריסה", line, re.IGNORECASE)
        )
        ambiguous = _ambiguous_link(entry, line)
        evidence.append(_Evidence(
            source=source, source_ref=f"{source}:line-{line_number}",
            evidence_state=state, work_state=work_state, scope_explicit=scope,
            ambiguous_link=ambiguous,
        ))
    return tuple(evidence)


def _main_evidence_state(text: str) -> str:
    """Main history proves code/merge only, never deployment or runtime."""
    state = _bounded_evidence_state(text)
    if state in {"RUNTIME_VERIFIED", "DEPLOYED", "WIRED"}:
        return "MERGED" if re.search(r"\b(merged|מוזג|merge)\b", text, re.IGNORECASE) else "CODE_DONE"
    return state


def _reconcile(entry: _RegistryEntry, source_texts: Mapping[str, str], main_text: str) -> _Reconciled:
    registry_state = _bounded_evidence_state(entry.stage)
    refs = ["docs/governance/BOSS_UNIFIED_MASTER_PLAN.md:registry"]
    linked: list[_Evidence] = []
    for source, path in (
        ("roadmap", "ROADMAP.md"),
        ("change", "CHANGE_CONTROL_LOG.md"),
        ("bug", "BUG_AUDIT_LOG.md"),
        ("main", "__main__"),
        ("production", "__production__"),
    ):
        text = main_text if source == "main" else source_texts.get(path, "")
        matches = _source_evidence(entry, text, source)
        linked.extend(matches)
        refs.extend(match.source_ref for match in matches)

    ambiguous = [item for item in linked if item.ambiguous_link]
    if ambiguous:
        return _Reconciled("UNKNOWN", None, tuple(refs), "UNRESOLVED")

    # The precedence is scoped and deterministic.  A linked production/runtime
    # record is strongest; main evidence follows; change/bug evidence follows;
    # current ROADMAP can set the work state; registry remains the fallback.
    roadmap_evidence = [item for item in linked if item.source == "roadmap"]
    roadmap_work = roadmap_evidence[-1].work_state if roadmap_evidence else None
    production = [item for item in linked if item.source == "production" and item.scope_explicit and item.evidence_state == "RUNTIME_VERIFIED"]
    if production:
        return _Reconciled("RUNTIME_VERIFIED", roadmap_work or production[-1].work_state, tuple(refs), "RESOLVED")
    main_evidence = [item for item in linked if item.source == "main" and item.evidence_state != "UNKNOWN"]
    if main_evidence:
        return _Reconciled(main_evidence[-1].evidence_state, roadmap_work or main_evidence[-1].work_state, tuple(refs), "RESOLVED")
    change_evidence = [item for item in linked if item.source in {"change", "bug"} and item.evidence_state != "UNKNOWN"]
    if len({item.evidence_state for item in change_evidence}) > 1:
        return _Reconciled("UNKNOWN", roadmap_work, tuple(refs), "CONFLICT")
    if change_evidence:
        return _Reconciled(change_evidence[-1].evidence_state, roadmap_work or change_evidence[-1].work_state, tuple(refs), "RESOLVED")
    if roadmap_evidence:
        item = roadmap_evidence[-1]
        return _Reconciled(item.evidence_state if item.evidence_state != "UNKNOWN" else registry_state,
                           item.work_state, tuple(refs), "RESOLVED")
    return _Reconciled(registry_state, _explicit_work_state(entry.stage), tuple(refs), "RESOLVED")


def _item_state(stage: str, next_step: str | None, evidence: str, work_state: str | None) -> tuple[str, str | None, str | None]:
    if work_state == "OWNER_DECISION":
        return "OWNER_DECISION", None, next_step
    if work_state == "BLOCKED":
        return "BLOCKED", stage, None
    if work_state == "ACTIVE":
        return "ACTIVE", None, None
    if work_state == "NEEDS_VERIFICATION":
        return "NEEDS_VERIFICATION", None, None
    if evidence in {"MERGED", "WIRED", "DEPLOYED", "RUNTIME_VERIFIED"} and _has(
        stage, "לא verified", "לא אומת", "טרם אומת", "not production", "לא עדיין"
    ):
        return "NEEDS_VERIFICATION", None, None
    if next_step:
        return "NEXT", None, None
    return "UNKNOWN", None, None


def _registry_item(entry: _RegistryEntry, reconciled: _Reconciled, versions: tuple[str, ...]) -> DevelopmentItem:
    evidence = reconciled.evidence_state
    state, blocker, decision_question = _item_state(entry.stage, entry.next_step, evidence, reconciled.work_state)
    return DevelopmentItem(
        initiative_key=_slug(entry.title), title=entry.title, horizon=entry.horizon,
        state=state, summary=_owner_text(entry.stage) or "Unknown current stage",
        next_step=_owner_text(entry.next_step), blocker=_owner_text(blocker),
        decision_question=_owner_text(decision_question),
        evidence_state=evidence, freshness="current", source_refs=(
            f"docs/governance/BOSS_UNIFIED_MASTER_PLAN.md:registry-row-{entry.row_number}",
            *reconciled.refs,
        ), source_versions=versions, reconciliation_state=reconciled.reconciliation_state,
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
        evidence = _bounded_evidence_state(line)
        if evidence == "UNKNOWN":
            continue
        title = re.sub(r"\s+\(.+?\)$", "", match.group(1)).strip()
        result.append(DevelopmentItem(
            initiative_key=_slug(title), title=title, horizon=None, state="CLOSED",
            summary=_owner_text(line[2:].strip()) or "Closed item",
            next_step=None, blocker=None,
            decision_question=None, evidence_state=evidence, freshness="current",
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
            evidence = _bounded_evidence_state(line)
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
        main_text = texts.get("__main__", _main_commit_subjects(root, main_ref))
        versions = tuple(
            SourceVersion(path, version_resolver(root, path, main_ref), authority, "current")
            for path, authority in (
            ("ROADMAP.md", "planning"),
            ("docs/governance/BOSS_UNIFIED_MASTER_PLAN.md", "registry"),
            ("CHANGE_CONTROL_LOG.md", "reconciliation only when explicitly linked"),
            ("BUG_AUDIT_LOG.md", "reconciliation only when explicitly linked"),
            ("AI_CONTEXT.md", "bounded closures/owner gates; not registry status"),
            )
        )
        version_text = tuple(value.as_text() for value in versions) + (f"main@{main_sha}",)
        registry_items = tuple(
            _registry_item(entry, _reconcile(entry, texts, main_text), version_text)
            for entry in entries
        )
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
        projection_state = (
            "PARTIAL"
            if any(item.reconciliation_state != "RESOLVED" for item in registry_items)
            else "CURRENT"
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
            projection_state=projection_state,
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
