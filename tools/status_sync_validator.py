#!/usr/bin/env python3
"""Blocking semantic validator for the canonical current-state ROADMAP registry.

The registry in ROADMAP.md remains the only source of truth.  This module only
reads it and compares structured claims with repository history; it never edits
documents or promotes a status.  Relationships are recognized only from
explicit markers in registry cells, for example ``IMPLEMENTATION_OF: UX-01``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ci_change_classifier import changed_paths, classify_diff
else:
    from .ci_change_classifier import changed_paths, classify_diff


ROADMAP_PATH = Path("ROADMAP.md")
APPROVED_STATUSES = frozenset(
    {"PLANNED", "IN_PROGRESS", "MERGED_STATIC", "DEPLOYED", "RUNTIME_VERIFIED"}
)
RELATIONSHIP_TYPES = frozenset(
    {"IMPLEMENTATION_OF", "DEPENDS_ON", "BLOCKED_BY", "MERGED_INTO", "CONTINUES"}
)
ACTIVE_STATUSES = frozenset({"IN_PROGRESS", "MERGED_STATIC", "DEPLOYED", "RUNTIME_VERIFIED"})
MERGED_STATUSES = frozenset({"MERGED_STATIC", "DEPLOYED", "RUNTIME_VERIFIED"})
SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])", re.IGNORECASE)
PR_RE = re.compile(r"\bPR\s*#(\d+)\b", re.IGNORECASE)
DATE_RE = re.compile(r"עודכן:\s*(\d{2})/(\d{2})/(\d{4})")
REL_RE = re.compile(
    r"\b(IMPLEMENTATION_OF|DEPENDS_ON|BLOCKED_BY|MERGED_INTO|CONTINUES)\s*[:=]\s*"
    r"([A-Z][A-Z0-9_-]*)\b",
    re.IGNORECASE,
)


class StatusSyncError(ValueError):
    """Raised for malformed structured current-state data."""


@dataclass(frozen=True)
class Program:
    line_number: int
    program_id: str
    name: str
    status: str
    evidence: str
    next_step: str
    canonical_source: str
    raw: str


@dataclass(frozen=True)
class Relationship:
    source: str
    kind: str
    target: str
    line_number: int


def _cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.rstrip().endswith("|"):
        raise StatusSyncError("malformed ROADMAP registry row")
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_program_registry(text: str) -> tuple[Program, ...]:
    """Parse the six-column current-state registry in ROADMAP.md."""
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("| ID | Canonical Name |")), None)
    if header is None:
        raise StatusSyncError("ROADMAP Active Programs registry header not found")
    if header + 1 >= len(lines):
        raise StatusSyncError("ROADMAP registry separator row missing")
    separator = _cells(lines[header + 1])
    if len(separator) != 6 or any(set(cell) - {"-"} or not cell for cell in separator):
        raise StatusSyncError("malformed ROADMAP registry separator")

    programs: list[Program] = []
    for index in range(header + 2, len(lines)):
        line = lines[index]
        if not line.startswith("|"):
            break
        cells = _cells(line)
        if len(cells) != 6:
            raise StatusSyncError(f"malformed ROADMAP registry row at line {index + 1}")
        source_match = re.search(r"\]\(([^)#]+)", cells[5])
        source = source_match.group(1) if source_match else ""
        programs.append(Program(index + 1, cells[0], cells[1], cells[2], cells[3], cells[4], source, line))
    if not programs:
        raise StatusSyncError("ROADMAP registry has no programs")
    return tuple(programs)


def _relationships(programs: Iterable[Program]) -> tuple[Relationship, ...]:
    result: list[Relationship] = []
    for program in programs:
        for match in REL_RE.finditer(" ".join((program.evidence, program.next_step, program.canonical_source))):
            result.append(Relationship(program.program_id, match.group(1).upper(), match.group(2).upper(), program.line_number))
    return tuple(result)


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True)


def _is_ancestor(repo_root: Path, commit: str, main_ref: str) -> bool:
    result = _run_git(repo_root, "merge-base", "--is-ancestor", commit, main_ref)
    return result.returncode == 0


def _commit_exists(repo_root: Path, commit: str) -> bool:
    return _run_git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0


def _source_exists(repo_root: Path, source: str) -> bool:
    if not source or source.startswith("archive/"):
        return False
    return (repo_root / source).is_file()


def _date_marker(text: str) -> bool:
    match = DATE_RE.search(text)
    if not match:
        return False
    try:
        date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return False
    return True


def _next_is_completed(program: Program, text: str) -> str | None:
    """Return a stale next token only when current prose explicitly marks it complete."""
    candidates = re.findall(r"\b(?:R\d+(?:\.\d+)?|F\d+(?:-[A-Z0-9]+)*|F52-G\d+-S\d+)\b", program.next_step, re.IGNORECASE)
    for token in candidates:
        if re.search(rf"\b{re.escape(token)}\b[^\n]*\b(?:MERGED|CLOSED|COMPLETE|STATIC VERIFIED)\b", text, re.IGNORECASE):
            return token
    return None


def _material_status_docs(paths: list[str]) -> bool:
    return any(
        path == "ROADMAP.md"
        or path == "docs/governance/HORIZON.md"
        or path == "docs/governance/BOSS_UNIFIED_MASTER_PLAN.md"
        or path.startswith("docs/architecture/")
        for path in paths
    )


def _material_implementation(paths: list[str]) -> bool:
    governance_tools = {
        "tools/audit_dispatcher_bypass.py",
        "tools/status_sync_validator.py",
        "tools/ci_change_classifier.py",
        "tools/dev_registry_validator.py",
        "dev_registry_contract.py",
    }
    return any(
        path.endswith(".py")
        and not Path(path).name.startswith("test_")
        and not path.startswith(("tests/", "scripts/"))
        and path not in governance_tools
        for path in paths
    )


def validate_status_sync(
    text: str,
    *,
    repo_root: Path = Path("."),
    main_ref: str | None = None,
    changed_paths: list[str] | None = None,
) -> list[str]:
    """Return deterministic blocking findings; an empty list means consistent."""
    findings: list[str] = []
    try:
        programs = parse_program_registry(text)
    except StatusSyncError as exc:
        return [f"STRUCTURED_DATA: {exc}"]

    by_id: dict[str, Program] = {}
    for program in programs:
        if program.program_id in by_id:
            findings.append(f"DUPLICATE_PROGRAM_ID: {program.program_id} (line {program.line_number})")
        by_id[program.program_id] = program
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]*", program.program_id):
            findings.append(f"INVALID_PROGRAM_ID: {program.program_id} (line {program.line_number})")
        if program.status not in APPROVED_STATUSES:
            findings.append(f"INVALID_STATUS: {program.program_id}={program.status}")
        if not _source_exists(repo_root, program.canonical_source):
            findings.append(f"MISSING_CANONICAL_SOURCE: {program.program_id}={program.canonical_source or '<empty>'}")
        stale = _next_is_completed(program, text)
        if stale:
            findings.append(f"STALE_NEXT_STEP: {program.program_id} lists {stale} as next although it is marked merged/closed")

    relationships = _relationships(programs)
    for relation in relationships:
        if relation.target not in by_id:
            findings.append(f"UNKNOWN_RELATION_TARGET: {relation.source} {relation.kind} {relation.target}")

    for relation in relationships:
        if relation.kind == "IMPLEMENTATION_OF" and relation.target in by_id:
            parent = by_id[relation.target]
            child = by_id[relation.source]
            if parent.status == "PLANNED" and child.status in ACTIVE_STATUSES and "JUSTIFICATION:" not in child.raw.upper():
                findings.append(f"PARENT_CHILD_STATUS_DRIFT: {parent.program_id}=PLANNED, {child.program_id}={child.status}")
        if relation.kind == "BLOCKED_BY" and relation.target in by_id:
            blocker = by_id[relation.target]
            if blocker.status in MERGED_STATUSES:
                findings.append(f"STALE_BLOCKER: {relation.source} BLOCKED_BY {relation.target}={blocker.status}")

    merged_edges = [(r.source, r.target) for r in relationships if r.kind == "MERGED_INTO"]
    for source, target in merged_edges:
        if target not in by_id:
            continue
        if any(s == target and t == source for s, t in merged_edges):
            findings.append(f"MERGED_INTO_CYCLE: {source} <-> {target}")
        source_program = by_id[source]
        if re.search(r"\b(?:R\d+(?:\.\d+)?|F\d+(?:-[A-Z0-9]+)*)\b", source_program.next_step, re.IGNORECASE) and "follow" not in source_program.next_step.lower():
            findings.append(f"MERGED_INTO_HAS_INDEPENDENT_NEXT: {source} -> {target}")
    graph = {source: target for source, target in merged_edges}
    for source in graph:
        seen: set[str] = set()
        node = source
        while node in graph:
            if node in seen:
                findings.append(f"MERGED_INTO_CYCLE: {source}")
                break
            seen.add(node)
            node = graph[node]

    for program in programs:
        if "RESOLVED:" in program.raw.upper():
            for relation in relationships:
                if relation.target == program.program_id and relation.kind in {"BLOCKED_BY", "DEPENDS_ON"}:
                    findings.append(f"RESOLVED_BLOCKER: {program.program_id} still blocks {relation.source}")

    if main_ref:
        for program in programs:
            if program.status not in MERGED_STATUSES:
                continue
            evidence = program.evidence
            for sha in SHA_RE.findall(evidence):
                if not _commit_exists(repo_root, sha) or not _is_ancestor(repo_root, sha, main_ref):
                    findings.append(f"UNREACHABLE_MERGE_EVIDENCE: {program.program_id} SHA {sha} is not reachable from {main_ref}")
            for pr in PR_RE.findall(evidence):
                log = _run_git(repo_root, "log", main_ref, "--oneline", "--all", "--grep", f"#{pr}")
                if log.returncode != 0 or not log.stdout.strip():
                    findings.append(f"UNVERIFIED_PR_EVIDENCE: {program.program_id} PR #{pr} not found in {main_ref} history")

    if not _date_marker(text):
        findings.append("ROADMAP_DATE: missing or unparseable עודכן marker")

    if changed_paths is not None and _material_implementation(changed_paths) and not _material_status_docs(changed_paths):
        findings.append("STATUS_DOCUMENT_UPDATE_REQUIRED: material implementation change has no current-state/status-document update")
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="Base ref for material-change classification")
    parser.add_argument("--head", help="Head ref for material-change classification")
    parser.add_argument("--main-ref", default="origin/main", help="Main history used for merge evidence")
    args = parser.parse_args()
    roadmap = args.repo_root / ROADMAP_PATH
    try:
        text = roadmap.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"STATUS-SYNC BLOCKED: cannot read {roadmap}: {exc}")
        return 1
    changed = None
    if args.base and args.head:
        try:
            changed = changed_paths(args.repo_root, args.base, args.head)
            classify_diff(args.repo_root, args.base, args.head)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"STATUS-SYNC BLOCKED: cannot classify changed paths: {exc}")
            return 1
    findings = validate_status_sync(text, repo_root=args.repo_root, main_ref=args.main_ref, changed_paths=changed)
    if findings:
        print("STATUS-SYNC BLOCKED")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("STATUS-SYNC PASSED: current-state program status is semantically consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
