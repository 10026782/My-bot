#!/usr/bin/env python3
"""tools/audit_gateway_bypass.py must scan tracked *.py files only
(Track D-Structure #7 — scan-boundary remediation).

Builds a scratch git repo per test so untracked files, nested .worktrees/*
paths, and nested checkouts can never leak into the real repo's audit input.
"""

import subprocess
from pathlib import Path

import pytest

import tools.audit_gateway_bypass as agb


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def scratch_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")

    # A. tracked python file.
    (tmp_path / "real_module.py").write_text("x = 1\n")
    _git(tmp_path, "add", "real_module.py")

    # B. untracked python file.
    (tmp_path / "untracked_module.py").write_text("y = 2\n")

    # C. .worktrees-like path — untracked, must never be scanned.
    worktree_dir = tmp_path / ".worktrees" / "foo"
    worktree_dir.mkdir(parents=True)
    (worktree_dir / "example.py").write_text("z = 3\n")

    # D. nested checkout — its own git repo with tracked content, not
    # tracked by the outer repo.
    nested = tmp_path / "nested_checkout"
    nested.mkdir()
    _git(nested, "init", "-q")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "test")
    (nested / "inner_module.py").write_text("w = 4\n")
    _git(nested, "add", "inner_module.py")
    _git(nested, "commit", "-q", "-m", "inner")

    # E. tracked fixture with a real Airtable-targeting bypass call.
    (tmp_path / "bypass_fixture.py").write_text(
        'import httpx\n'
        'def f():\n'
        '    return httpx.get(_at_url("Contacts"), headers=_at_headers())\n'
    )
    _git(tmp_path, "add", "bypass_fixture.py")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    monkeypatch.setattr(agb, "_REPO_ROOT", tmp_path)
    return tmp_path


def test_tracked_file_is_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in agb._iter_py_files()}
    assert "real_module.py" in found


def test_untracked_file_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in agb._iter_py_files()}
    assert "untracked_module.py" not in found


def test_worktrees_path_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in agb._iter_py_files()}
    assert not any(p.startswith(".worktrees/") for p in found)


def test_nested_checkout_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in agb._iter_py_files()}
    assert not any(p.startswith("nested_checkout/") for p in found)


def test_tracked_bypass_is_still_detected(scratch_repo: Path) -> None:
    findings = agb.scan()
    assert ("bypass_fixture.py", 3, "get") in findings


def test_scan_boundary_fails_closed_on_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agb, "_REPO_ROOT", tmp_path)  # not a git repo
    with pytest.raises(agb.ScanBoundaryError):
        list(agb._iter_py_files())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
