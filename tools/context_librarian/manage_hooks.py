"""Install/check the versioned `.githooks/` post-merge Context Librarian hook.

Git does not read `.githooks/` on its own — a repo-local
`core.hooksPath` config value has to point at it. This module sets and
checks exactly that one local (never global) git config value, so the
hook script itself can live under version control instead of the
untracked, per-clone `.git/hooks/` directory.
"""

from __future__ import annotations

import argparse
import stat
import subprocess
from pathlib import Path

HOOKS_DIR_NAME = ".githooks"
HOOK_FILE_NAME = "post-merge"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode, completed.stdout.strip()


def check_hooks(repo_root: Path) -> tuple[bool, str]:
    code, hooks_path = _git(repo_root, "config", "--get", "core.hooksPath")
    if code != 0 or not hooks_path:
        return (
            False,
            "core.hooksPath is not set -- run "
            "`python -m tools.context_librarian.manage_hooks install`",
        )
    configured = (repo_root / hooks_path).resolve()
    expected = (repo_root / HOOKS_DIR_NAME).resolve()
    if configured != expected:
        return False, f"core.hooksPath is {hooks_path!r}, expected {HOOKS_DIR_NAME!r}"
    hook_file = expected / HOOK_FILE_NAME
    if not hook_file.is_file():
        return False, f"{hook_file} does not exist"
    if not (hook_file.stat().st_mode & stat.S_IXUSR):
        return False, f"{hook_file} is not executable -- run `chmod +x {hook_file}`"
    return True, f"core.hooksPath={hooks_path}; {hook_file} present and executable"


def install_hooks(repo_root: Path) -> tuple[bool, str]:
    hook_file = repo_root / HOOKS_DIR_NAME / HOOK_FILE_NAME
    if not hook_file.is_file():
        return False, f"{hook_file} does not exist -- cannot install"
    mode = hook_file.stat().st_mode
    hook_file.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    code, output = _git(repo_root, "config", "core.hooksPath", HOOKS_DIR_NAME)
    if code != 0:
        return False, f"git config core.hooksPath failed: {output}"
    return check_hooks(repo_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.context_librarian.manage_hooks",
        description=(
            "Install or check the versioned .githooks/post-merge Context "
            "Librarian refresh hook. Sets repo-local git config only -- "
            "never --global."
        ),
    )
    parser.add_argument("command", choices=["install", "check"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = _repo_root()
    if args.command == "install":
        ok, message = install_hooks(repo_root)
    else:
        ok, message = check_hooks(repo_root)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
