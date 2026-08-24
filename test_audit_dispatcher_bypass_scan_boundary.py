#!/usr/bin/env python3
"""tools/audit_dispatcher_bypass.py must scan tracked *.py files only, and
must exclude only exact verified-sanctioned call sites, never a whole file
(Track D-Structure #7 — dispatcher-bypass scan-boundary and scanner
false-positive remediation).

Builds a scratch git repo per test so untracked files, non-dot-prefixed
nested checkouts, and dot-prefixed leftover worktrees can never leak into
the real repo's audit input.
"""

import subprocess
from pathlib import Path

import pytest

import tools.audit_dispatcher_bypass as adb


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

    # C. untracked bypass-shaped file — must not enter scan() findings.
    (tmp_path / "untracked_bypass.py").write_text(
        "from tools.airtable_tools import airtable_get\n"
        "def g():\n"
        '    return airtable_get("Deals")\n'
    )

    # D. dot-prefix defense: .worktrees-like path and a leftover worktree dir.
    worktree_dir = tmp_path / ".worktrees" / "foo"
    worktree_dir.mkdir(parents=True)
    (worktree_dir / "example.py").write_text("z = 3\n")

    leftover_dir = tmp_path / ".codex-leftover"
    leftover_dir.mkdir()
    (leftover_dir / "example.py").write_text("q = 5\n")

    # E. non-dot nested checkout — its own git repo with tracked content,
    # not tracked by the outer repo.
    nested = tmp_path / "nested_checkout"
    nested.mkdir()
    _git(nested, "init", "-q")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "test")
    (nested / "inner_module.py").write_text("w = 4\n")
    _git(nested, "add", "inner_module.py")
    _git(nested, "commit", "-q", "-m", "inner")

    # F. tracked fixture with a real dispatcher-bypass import.
    (tmp_path / "bypass_fixture.py").write_text(
        "from tools.airtable_tools import airtable_get\n"
        "def f():\n"
        '    return airtable_get("Contacts")\n'
    )
    _git(tmp_path, "add", "bypass_fixture.py")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    monkeypatch.setattr(adb, "_REPO_ROOT", tmp_path)
    return tmp_path


def test_tracked_file_is_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in adb._iter_py_files()}
    assert "real_module.py" in found


def test_untracked_file_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in adb._iter_py_files()}
    assert "untracked_module.py" not in found


def test_untracked_bypass_shaped_file_not_in_findings(scratch_repo: Path) -> None:
    findings = adb.scan()
    assert not any(f == "untracked_bypass.py" for f, _, _ in findings)


def test_worktrees_path_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in adb._iter_py_files()}
    assert not any(p.startswith(".worktrees/") for p in found)


def test_dot_prefixed_leftover_dir_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in adb._iter_py_files()}
    assert not any(p.startswith(".codex-leftover/") for p in found)


def test_nested_checkout_is_not_discovered(scratch_repo: Path) -> None:
    found = {p.as_posix() for p in adb._iter_py_files()}
    assert not any(p.startswith("nested_checkout/") for p in found)


def test_tracked_bypass_is_still_detected(scratch_repo: Path) -> None:
    findings = adb.scan()
    assert ("bypass_fixture.py", 1, "tools.airtable_tools") in findings


def test_sanctioned_call_site_filters_only_the_exact_tuple(
    scratch_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The filter must be exact-tuple, not whole-file: a second, unrelated
    bypass-shaped import in the same sanctioned file must still surface."""
    tools_dir = scratch_repo / "tools"
    tools_dir.mkdir()
    (tools_dir / "approval_actions.py").write_text(
        "def a():\n"
        "    import crm\n"          # line 2 — will be marked sanctioned
        "def b():\n"
        "    import crm\n"          # line 4 — must still be reported
    )
    _git(scratch_repo, "add", "tools/approval_actions.py")
    _git(scratch_repo, "commit", "-q", "-m", "approval_actions fixture")

    monkeypatch.setattr(
        adb, "_SANCTIONED_CALL_SITES",
        frozenset({("tools/approval_actions.py", 2, "crm")}),
    )
    findings = adb.scan()
    assert ("tools/approval_actions.py", 2, "crm") not in findings
    assert ("tools/approval_actions.py", 4, "crm") in findings


def test_real_sanctioned_call_sites_are_never_reported(scratch_repo: Path) -> None:
    """The two real sites this constant currently covers must never appear
    as findings, even though _is_allowed()'s filename-substring heuristic
    alone would not have excluded them (see the constant's own provenance
    comment for the verified caller-graph evidence)."""
    tools_dir = scratch_repo / "tools"
    tools_dir.mkdir()
    (tools_dir / "approval_actions.py").write_text(
        "\n" * 364 + "            import crm\n"
    )
    (tools_dir / "schema_snapshot.py").write_text(
        "\n" * 285 + "    from tools.airtable_tools import airtable_get_records\n"
    )
    _git(scratch_repo, "add", "tools/approval_actions.py", "tools/schema_snapshot.py")
    _git(scratch_repo, "commit", "-q", "-m", "real sanctioned call site fixtures")

    findings = adb.scan()
    assert ("tools/approval_actions.py", 365, "crm") not in findings
    assert ("tools/schema_snapshot.py", 286, "tools.airtable_tools") not in findings


def test_scan_boundary_fails_closed_on_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adb, "_REPO_ROOT", tmp_path)  # not a git repo
    with pytest.raises(adb.ScanBoundaryError):
        list(adb._iter_py_files())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
