"""Preflight gate for the first real Consumption Enforcement pilot.

See docs/governance/librarian/FIRST_REAL_CONSUMPTION_PILOT.md. This blocks
step 5 of the pilot's required sequence ("perform the task using the
bundle") until steps 1-4 (build the bundle, inspect it, generate the
consumption checklist, create the Consumption Ledger skeleton) have actually
produced their artifacts on disk — instead of relying on an agent's
self-report that it did those steps.

Read-only and additive: does not modify librarian.py, __main__.py, or any of
their 112 existing tests. Reuses load_catalog()/consumption_checklist()
directly rather than re-deriving the mandatory-tier logic, so it cannot drift
from what `verify-consumption` itself would compute.

This is not a replacement for `verify-consumption` (which needs a completed
ledger, with receipts/waivers, checked against exact commit/branch/query
identity). It only proves the ledger *skeleton* (required_sources) matches
the live mandatory tier before the pilot task starts consuming sources.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.context_librarian.librarian import (
    LEDGER_TOP_LEVEL_REQUIRED_FIELDS,
    ContextLibrarianError,
    consumption_checklist,
    load_catalog,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _bundle_title_line(task_type: str) -> str:
    # Must match _render()'s own f"# BOSS Context Bundle — {profile['id']}"
    # exactly (tools/context_librarian/librarian.py) — duplicated as a
    # literal here rather than imported, since _render() has no public
    # "title for this profile" helper to reuse.
    return f"# BOSS Context Bundle — {task_type}"


def _bundle_checklist_items(bundle_text: str) -> list[str] | None:
    """Item ids under the bundle's own "## Consumption Checklist" section.

    Returns None when the section is missing or its expected item-list/"None"
    marker never appears — i.e. the file is not a real generated bundle
    (hand-written, truncated, or built by a different/older code path).
    """
    lines = bundle_text.splitlines()
    try:
        start = lines.index("## Consumption Checklist")
    except ValueError:
        return None
    items: list[str] = []
    found_marker = False
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line == "- None.":
            found_marker = True
            continue
        if line.startswith("- `") and line.endswith("`"):
            items.append(line[3:-1])
            found_marker = True
    return items if found_marker else None


def run_preflight(
    *,
    repo_root: Path,
    task_type: str,
    production_claim: bool,
    bundle_path: Path,
    ledger_path: Path,
) -> tuple[int, list[str]]:
    """Returns (exit_code, messages). 0 means the pilot task may proceed."""
    bundle_path = _resolve(bundle_path, repo_root)
    ledger_path = _resolve(ledger_path, repo_root)

    catalog = load_catalog(repo_root)
    if task_type not in catalog.profiles:
        available = ", ".join(sorted(catalog.profiles))
        return 2, [f"BLOCKED: unknown task type {task_type!r}; choose one of: {available}"]
    profile = catalog.profiles[task_type]
    live_required = set(
        consumption_checklist(catalog, profile, production_claim=production_claim)
    )

    if not bundle_path.is_file():
        return 1, [
            f"BLOCKED: bundle not found at {bundle_path} — run "
            "`python -m tools.context_librarian build` first (pilot steps 1-2)."
        ]
    bundle_text = bundle_path.read_text(encoding="utf-8")
    if not bundle_text.strip():
        return 1, [
            f"BLOCKED: bundle at {bundle_path} is empty — run "
            "`python -m tools.context_librarian build` first (pilot steps 1-2)."
        ]

    # Bind the bundle to the selected profile and the live mandatory tier —
    # file existence/non-emptiness alone lets a stale, wrong-profile, or
    # hand-written bundle satisfy this gate (CodeRabbit PR #501 review).
    bundle_lines = bundle_text.splitlines()
    expected_title = _bundle_title_line(task_type)
    if not bundle_lines or bundle_lines[0] != expected_title:
        return 1, [
            f"BLOCKED: bundle at {bundle_path} was not built for task-type "
            f"{task_type!r} (expected first line {expected_title!r}, got "
            f"{bundle_lines[0] if bundle_lines else ''!r}) — rebuild with "
            f"`--task-type {task_type}`."
        ]
    bundle_checklist = _bundle_checklist_items(bundle_text)
    if bundle_checklist is None:
        return 1, [
            f"BLOCKED: bundle at {bundle_path} has no recognizable "
            "'## Consumption Checklist' section — it is not a bundle produced "
            "by `python -m tools.context_librarian build`; rebuild it."
        ]
    bundle_checklist_set = set(bundle_checklist)
    if bundle_checklist_set != live_required:
        missing = sorted(live_required - bundle_checklist_set)
        extra = sorted(bundle_checklist_set - live_required)
        return 1, [
            f"BLOCKED: bundle at {bundle_path}'s Consumption Checklist does not "
            f"match the live-recomputed mandatory tier for {task_type!r} "
            f"(production_claim={production_claim}) — the bundle is stale or was "
            f"built with a different --production-claim; rebuild it: "
            f"missing_from_bundle={missing}, extra_in_bundle={extra}."
        ]

    if not ledger_path.is_file():
        return 2, [
            f"BLOCKED: Consumption Ledger not found at {ledger_path} — create "
            "the ledger skeleton first (pilot steps 3-4)."
        ]
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 2, [f"BLOCKED: ledger at {ledger_path} is not valid JSON: {exc}"]
    if not isinstance(ledger, dict):
        return 2, [f"BLOCKED: ledger at {ledger_path} must be a JSON object."]

    missing_top = sorted(LEDGER_TOP_LEVEL_REQUIRED_FIELDS - set(ledger))
    if missing_top:
        return 2, [
            f"BLOCKED: ledger missing top-level fields: {', '.join(missing_top)}."
        ]

    messages: list[str] = []
    if ledger.get("task_type") != task_type:
        messages.append(
            f"BLOCKED: ledger task_type {ledger.get('task_type')!r} does not "
            f"match --task-type {task_type!r}."
        )
    if ledger.get("production_claim") != production_claim:
        messages.append(
            f"BLOCKED: ledger production_claim {ledger.get('production_claim')!r} "
            f"does not match --production-claim ({production_claim})."
        )
    required_sources = ledger.get("required_sources")
    if not isinstance(required_sources, list):
        messages.append("BLOCKED: ledger required_sources must be a list.")
    elif not all(isinstance(item, str) for item in required_sources):
        # A syntactically valid JSON list may still hold objects/nested lists —
        # set() over those raises TypeError before a message could ever be
        # printed, crashing main() instead of failing closed (CodeRabbit PR
        # #501 review).
        messages.append(
            "BLOCKED: ledger required_sources must contain only string item ids."
        )
    if messages:
        return 2, messages

    declared_required = set(required_sources)
    if declared_required != live_required:
        missing = sorted(live_required - declared_required)
        extra = sorted(declared_required - live_required)
        return 3, [
            "BLOCKED: ledger required_sources does not match the live-recomputed "
            f"mandatory tier for {task_type!r} (production_claim={production_claim}): "
            f"missing_from_ledger={missing}, extra_in_ledger={extra}."
        ]

    return 0, [
        "PROCEED: bundle matches the selected profile and live mandatory tier, "
        "and the ledger skeleton's required_sources matches it too. Steps 1-4 "
        "are done — the pilot task (step 5) may begin.",
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.context_librarian.pilot_preflight",
        description=(
            "Block starting the Consumption Enforcement pilot task until the "
            "bundle and Consumption Ledger skeleton actually exist on disk."
        ),
    )
    parser.add_argument("--task-type", required=True)
    parser.add_argument("--production-claim", action="store_true")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        exit_code, messages = run_preflight(
            repo_root=_repo_root(),
            task_type=args.task_type,
            production_claim=args.production_claim,
            bundle_path=args.bundle,
            ledger_path=args.ledger,
        )
    except ContextLibrarianError as exc:
        print(f"pilot-preflight: {exc}", file=sys.stderr)
        return 2
    for message in messages:
        print(message)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
