"""Fail-closed capability routing for CI changed paths."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Capabilities:
    backend_required: bool
    frontend_required: bool
    governance_required: bool
    librarian_required: bool
    full_ci_required: bool


_GOVERNANCE_ROOT_FILES = frozenset(
    {
        "AGENTS.md",
        "GOVERNANCE_RULES.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "CHANGE_CONTROL_LOG.md",
        "RELEASE_CHECKLIST.md",
        "MAINTENANCE_STATUS_MATRIX.md",
        "DAILY_SUMMARY.md",
    }
)
_LIBRARIAN_TESTS = frozenset(
    {"test_context_librarian.py", "test_refresh_after_merge.py", "test_reconcile.py"}
)
_DEPENDENCY_FILES = frozenset(
    {
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "setup.cfg",
        "setup.py",
        "tox.ini",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    }
)
_BUILD_FILES = frozenset(
    {"Dockerfile", "Makefile", "Procfile", "render.yaml", "vercel.json"}
)


def _is_hard_risk(path: str) -> bool:
    parts = Path(path).parts
    name = parts[-1] if parts else ""
    return (
        path.startswith(".github/workflows/")
        or name in _DEPENDENCY_FILES
        or name in _BUILD_FILES
        or path.startswith("core/migrations/")
        or "/migrations/" in path
        or name in {"airtable_schema.py", "schema_audit.py"}
        or path == "tools/ci_change_classifier.py"
    )


def _is_governance(path: str) -> bool:
    return (
        path in _GOVERNANCE_ROOT_FILES
        or path == ".github/pull_request_template.md"
        or path.startswith("docs/governance/")
        or path.startswith("docs/daily/")
    )


def _is_librarian(path: str) -> bool:
    return (
        path.startswith("tools/context_librarian/")
        or path.startswith("docs/context_librarian/")
        or path in _LIBRARIAN_TESTS
    )


def classify_paths(paths: object) -> Capabilities:
    """Classify paths into capabilities; invalid or unknown input is full CI."""
    if not isinstance(paths, (list, tuple, set)) or not paths:
        return Capabilities(True, False, False, False, True)
    if any(not isinstance(path, str) or not path or Path(path).is_absolute() for path in paths):
        return Capabilities(True, False, False, False, True)

    backend = frontend = governance = librarian = full = False
    for path in paths:
        if _is_hard_risk(path):
            backend = full = True
        elif _is_governance(path):
            governance = True
        elif _is_librarian(path):
            librarian = True
        elif path.startswith("tma-frontend/"):
            frontend = True
        else:
            backend = full = True

    return Capabilities(backend, frontend, governance, librarian, full)


def changed_paths(repo_root: Path, base: str, head: str) -> list[str]:
    merge_base = subprocess.run(
        ["git", "merge-base", base, head],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not merge_base:
        raise ValueError("git merge-base returned no commit")
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}..{head}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def classify_diff(repo_root: Path, base: str, head: str) -> Capabilities:
    try:
        return classify_paths(changed_paths(repo_root, base, head))
    except (OSError, subprocess.CalledProcessError, TypeError, ValueError):
        return Capabilities(True, False, False, False, True)


def _write_outputs(capabilities: Capabilities, output: Path) -> None:
    values = {
        "backend_required": capabilities.backend_required,
        "frontend_required": capabilities.frontend_required,
        "governance_required": capabilities.governance_required,
        "librarian_required": capabilities.librarian_required,
        "full_ci_required": capabilities.full_ci_required,
    }
    with output.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={str(value).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    capabilities = classify_diff(args.repo_root, args.base, args.head)
    print(capabilities)
    if args.github_output:
        _write_outputs(capabilities, args.github_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
