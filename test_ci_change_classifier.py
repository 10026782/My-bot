from pathlib import Path
import subprocess

from tools.ci_change_classifier import Capabilities, classify_diff, classify_paths


FULL = Capabilities(True, False, False, False, True)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(
        repo,
        "-c", "user.name=CI Test",
        "-c", "user.email=ci@example.com",
        "commit", "-m", message,
    )
    return _git(repo, "rev-parse", "HEAD")


def _pr_history(
    tmp_path: Path,
    feature_paths: list[tuple[str, str]],
    *,
    later_main_backend_change: bool,
) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    root = _commit(repo, "README.md", "root\n", "root")
    _git(repo, "switch", "-c", "feature", root)
    for index, (path, content) in enumerate(feature_paths):
        feature = _commit(repo, path, content, f"feature {index}")
    _git(repo, "switch", "main")
    main = root
    if later_main_backend_change:
        main = _commit(repo, "core/runtime.py", "later backend change\n", "main later")
    _git(repo, "switch", "feature")
    return repo, main, feature


def test_safe_and_fail_safe_path_classes():
    assert classify_paths(["core/action_gateway.py"]) == FULL
    assert classify_paths(["docs/governance/ordinary.md"]) == Capabilities(False, False, True, False, False)
    assert classify_paths(["docs/governance/HORIZON.md"]).governance_required
    assert classify_paths(["docs/governance/BOSS_UNIFIED_MASTER_PLAN.md"]).governance_required
    assert classify_paths(["ROADMAP.md"]).governance_required
    assert classify_paths(["docs/context_librarian/README.md"]).librarian_required
    assert classify_paths(["tools/context_librarian/librarian.py"]).librarian_required
    assert classify_paths(["test_context_librarian.py"]).librarian_required
    assert classify_paths(["docs/context_librarian/README.md", "ROADMAP.md"]) == Capabilities(False, False, True, True, False)
    assert classify_paths(["tma-frontend/src/App.tsx"]) == Capabilities(False, True, False, False, False)
    assert classify_paths(["tma-frontend/src/App.tsx", "core/action_gateway.py"]) == Capabilities(True, True, False, False, True)


def test_fail_safe_paths_and_input():
    for paths in (
        ["unknown/file.txt"],
        [".github/workflows/ci.yml"],
        ["requirements.txt"],
        ["core/migrations/001.sql"],
        ["test_other.py"],
        ["tools/ci_change_classifier.py"],
        [""],
        [],
        None,
        {"path": "core/action_gateway.py"},
    ):
        assert classify_paths(paths) == FULL


def test_unavailable_diff_fails_safe(tmp_path):
    assert classify_diff(tmp_path, "missing", "also-missing") == FULL


def test_current_main_docs_only_is_governance_only(tmp_path):
    repo, main, feature = _pr_history(
        tmp_path, [("docs/governance/status.md", "docs\n")], later_main_backend_change=False
    )
    assert classify_diff(repo, main, feature) == Capabilities(False, False, True, False, False)


def test_stale_docs_only_pr_ignores_later_main_backend_commit(tmp_path):
    repo, main, feature = _pr_history(
        tmp_path, [("docs/governance/status.md", "docs\n")], later_main_backend_change=True
    )
    assert classify_diff(repo, main, feature) == Capabilities(False, False, True, False, False)


def test_stale_frontend_only_pr_ignores_later_main_backend_commit(tmp_path):
    repo, main, feature = _pr_history(
        tmp_path, [("tma-frontend/src/App.tsx", "export {}\n")], later_main_backend_change=True
    )
    assert classify_diff(repo, main, feature) == Capabilities(False, True, False, False, False)


def test_pr_backend_and_docs_changes_are_union(tmp_path):
    repo, main, feature = _pr_history(
        tmp_path,
        [("core/changed.py", "backend\n"), ("docs/governance/status.md", "docs\n")],
        later_main_backend_change=True,
    )
    assert classify_diff(repo, main, feature) == Capabilities(True, False, True, False, True)


def test_mixed_frontend_and_docs_changes_are_union(tmp_path):
    repo, main, feature = _pr_history(
        tmp_path,
        [("tma-frontend/src/App.tsx", "export {}\n"), ("docs/governance/status.md", "docs\n")],
        later_main_backend_change=True,
    )
    assert classify_diff(repo, main, feature) == Capabilities(False, True, True, False, False)


def test_invalid_merge_base_fails_safe(tmp_path):
    assert classify_diff(tmp_path, "missing-base", "missing-head") == FULL


def test_lightweight_routes_have_no_backend_stack():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    governance = workflow.split("  governance-ci:", 1)[1].split("  context-librarian-ci:", 1)[0]
    librarian = workflow.split("  context-librarian-ci:", 1)[1].split("  frontend-ci:", 1)[0]
    for job in (governance, librarian):
        assert "services:" not in job
        assert "postgres" not in job
        assert "TC10" not in job
        assert "test_*.py" not in job

    backend = workflow.split("  backend-ci:", 1)[1].split("  governance-ci:", 1)[0]
    assert "services:" in backend
    assert "TC10 isolated regression matrix" in backend
    assert "Run test_*.py scripts" in backend
