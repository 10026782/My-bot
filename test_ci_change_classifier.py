from pathlib import Path

from tools.ci_change_classifier import Capabilities, classify_diff, classify_paths


FULL = Capabilities(True, False, False, False, True)


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
