"""Tests for tools/context_librarian/refresh_after_merge.py and manage_hooks.py."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.context_librarian import librarian, manage_hooks, refresh_after_merge
from tools.context_librarian.librarian import ContextLibrarianError, load_catalog
from tools.context_librarian.refresh_after_merge import (
    apply_refresh,
    compute_changed_files,
    plan_refresh,
    run_refresh,
)

REPO_ROOT = Path(__file__).resolve().parent
# A real, currently-reachable commit — required because refreshing a node
# re-triggers _freshness()'s `git diff --name-only <commit> --` on the next
# build, which fails closed (a *different* ContextLibrarianError) against a
# syntactically-valid-looking but nonexistent hash. Using the real HEAD
# means the budget-overflow tests below exercise the actual overflow
# condition instead of a fake-commit lookup failure.
NEW_COMMIT = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
).stdout.strip()


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT)


def _isolated_catalog(tmp_path: Path, monkeypatch) -> Path:
    source = REPO_ROOT / "docs/context_librarian"
    target = tmp_path / "catalog"
    shutil.copytree(source, target)
    monkeypatch.setattr(librarian, "CATALOG_RELATIVE_ROOT", target)
    return target


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 1. commit refresh
# ---------------------------------------------------------------------------


def test_commit_refresh_bumps_only_matched_nodes(catalog):
    a_node = catalog.nodes["layer.ux_f52"]
    changed = {a_node["code_paths"][0]}
    plan = plan_refresh(catalog, changed_files=changed, new_commit=NEW_COMMIT)
    assert plan.status == "OK"
    refreshed_ids = {item.node_id for item in plan.refreshed}
    assert "layer.ux_f52" in refreshed_ids
    # A node with none of its paths touched must not be refreshed.
    assert "layer.tools" not in refreshed_ids
    for item in plan.refreshed:
        if item.node_id == "layer.ux_f52":
            assert item.new_commit == NEW_COMMIT
            assert a_node["code_paths"][0] in item.matched_paths


def test_commit_refresh_writes_to_disk(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    catalog = load_catalog(REPO_ROOT)
    target_node = catalog.nodes["layer.ux_f52"]
    changed = {target_node["code_paths"][0]}
    plan = plan_refresh(catalog, changed_files=changed, new_commit=NEW_COMMIT)
    assert plan.status == "OK"
    assert len(plan.refreshed) >= 1

    apply_refresh(root, plan)

    data = _read_json(root / "layers/ux_f52.json")
    updated_node = next(n for n in data["nodes"] if n["id"] == "layer.ux_f52")
    assert updated_node["last_verified_commit"] == NEW_COMMIT


def test_commit_refresh_skips_nodes_already_current(catalog):
    node = catalog.nodes["layer.ux_f52"]
    already_current_commit = node["last_verified_commit"]
    plan = plan_refresh(
        catalog,
        changed_files={node["code_paths"][0]},
        new_commit=already_current_commit,
    )
    assert not any(item.node_id == "layer.ux_f52" for item in plan.refreshed)


def test_run_refresh_resolves_symbolic_refs_to_real_shas(tmp_path, monkeypatch):
    # A caller passing "HEAD"/"HEAD~1" (the natural way to invoke this by
    # hand) must never end up with the literal string "HEAD" written as
    # last_verified_commit — it fails the node schema's commit_pattern and
    # would make every future freshness check against that node meaningless.
    root = _isolated_catalog(tmp_path, monkeypatch)
    plan = run_refresh(REPO_ROOT, base_commit="HEAD~1", head_commit="HEAD", apply=True)
    assert plan.status in ("OK", "REVIEW_REQUIRED")
    assert plan.new_commit != "HEAD"
    assert len(plan.new_commit) >= 7
    assert all(ch in "0123456789abcdef" for ch in plan.new_commit)
    for item in plan.refreshed:
        path = _locate_layer_or_decision_file(root, item.node_id)
        data = _read_json(path)
        updated_node = next(n for n in data["nodes"] if n["id"] == item.node_id)
        assert updated_node["last_verified_commit"] == plan.new_commit


def _locate_layer_or_decision_file(catalog_root: Path, node_id: str) -> Path:
    for path in sorted((catalog_root / "layers").glob("*.json")) + [
        catalog_root / "decisions/canonical_boundaries.json"
    ]:
        data = _read_json(path)
        if any(n["id"] == node_id for n in data.get("nodes", [])):
            return path
    raise AssertionError(f"node {node_id} not found in any catalog file")


def test_compute_changed_files_against_real_git(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()

    (tmp_path / "a.py").write_text("2\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("3\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "head"], cwd=tmp_path, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()

    changed = compute_changed_files(tmp_path, base, head)
    assert changed == {"a.py", "b.py"}


# ---------------------------------------------------------------------------
# 2. stale reference
# ---------------------------------------------------------------------------


def test_stale_reference_reports_error(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    real_file = REPO_ROOT / "core/agent_message_formatter.py"
    assert real_file.exists()
    # Simulate the referenced file having been deleted/renamed by the merge —
    # a node still points at a path that no longer exists on disk.
    monkeypatch.setattr(
        librarian,
        "_load_catalog_json",
        librarian._load_catalog_json,  # keep normal loading of JSON
    )
    fake_missing = "core/this_file_was_deleted_by_the_merge.py"
    path = root / "layers/ux_f52.json"
    data = _read_json(path)
    data["nodes"][0]["code_paths"].append(fake_missing)
    _write_json(path, data)

    plan = run_refresh(REPO_ROOT, base_commit="HEAD~1", head_commit="HEAD", apply=False)
    assert plan.status == "ERROR"
    assert "does not exist" in plan.error
    assert fake_missing in plan.error


# ---------------------------------------------------------------------------
# 3. unknown new canonical file
# ---------------------------------------------------------------------------


def test_unknown_new_canonical_file_flagged_for_review(catalog):
    # core/ is already claimed by many nodes' code_paths, but this exact
    # filename is registered nowhere — must be flagged, never silently
    # ignored or silently added.
    new_file = "core/totally_new_module_not_in_catalog.py"
    plan = plan_refresh(catalog, changed_files={new_file}, new_commit=NEW_COMMIT)
    assert plan.status == "REVIEW_REQUIRED"
    categories = {item.category for item in plan.review_required}
    assert "unknown_canonical_file" in categories
    detail_text = " ".join(item.detail for item in plan.review_required)
    assert new_file in detail_text
    # And no node should have silently absorbed it.
    assert not plan.refreshed or all(
        new_file not in item.matched_paths for item in plan.refreshed
    )


def test_unknown_new_test_file_flagged_for_review(catalog):
    new_test = "test_totally_new_suite_not_in_catalog.py"
    plan = plan_refresh(catalog, changed_files={new_test}, new_commit=NEW_COMMIT)
    assert plan.status == "REVIEW_REQUIRED"
    categories = {item.category for item in plan.review_required}
    assert "unknown_test_file" in categories


def test_file_outside_any_claimed_directory_is_not_flagged(catalog):
    # A change under a directory the catalog has never referenced at all is
    # simply outside its scope — not every repo change is the catalog's
    # business.
    unrelated = "some/totally/unrelated/directory/file.txt"
    plan = plan_refresh(catalog, changed_files={unrelated}, new_commit=NEW_COMMIT)
    assert plan.status == "OK"
    assert plan.review_required == ()


# ---------------------------------------------------------------------------
# 4. broken edge
# ---------------------------------------------------------------------------


def test_broken_edge_reports_error(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    path = root / "layers/ux_f52.json"
    data = _read_json(path)
    data["edges"].append(
        {
            "from": "layer.ux_f52",
            "to": "decision.this_decision_does_not_exist",
            "type": "governed_by",
            "notes": "broken on purpose",
        }
    )
    _write_json(path, data)

    plan = run_refresh(REPO_ROOT, base_commit="HEAD~1", head_commit="HEAD", apply=False)
    assert plan.status == "ERROR"
    assert "edge target missing" in plan.error


# ---------------------------------------------------------------------------
# 5. token-budget overflow
# ---------------------------------------------------------------------------


def test_token_budget_overflow_flagged_for_review(tmp_path, monkeypatch):
    root = _isolated_catalog(tmp_path, monkeypatch)
    profiles_path = root / "task_profiles/profiles.json"
    data = _read_json(profiles_path)
    for profile in data["profiles"]:
        if profile["id"] == "ux_f52_message":
            # Deterministic overflow regardless of char-estimate arithmetic —
            # any non-trivial bundle will exceed a 1-token budget.
            profile["maximum_approximate_token_budget"] = 1
    _write_json(profiles_path, data)

    catalog = load_catalog(REPO_ROOT)
    node = catalog.nodes["layer.ux_f52"]
    plan = plan_refresh(
        catalog, changed_files={node["code_paths"][0]}, new_commit=NEW_COMMIT
    )
    assert plan.status == "REVIEW_REQUIRED"
    categories = {item.category for item in plan.review_required}
    assert "budget_overflow" in categories
    detail_text = " ".join(item.detail for item in plan.review_required)
    assert "ux_f52_message" in detail_text


def test_apply_refresh_does_not_write_review_required_nodes(tmp_path, monkeypatch):
    # Even when review_required items exist elsewhere in the plan, the
    # cleanly-matched nodes still get refreshed — the two are independent.
    root = _isolated_catalog(tmp_path, monkeypatch)
    catalog = load_catalog(REPO_ROOT)
    clean_node = catalog.nodes["layer.tools"]
    plan = plan_refresh(
        catalog,
        changed_files={clean_node["code_paths"][0], "core/unknown_new_file.py"},
        new_commit=NEW_COMMIT,
    )
    assert plan.status == "REVIEW_REQUIRED"
    assert any(item.node_id == "layer.tools" for item in plan.refreshed)

    apply_refresh(root, plan)
    data = _read_json(root / "layers/tools.json")
    updated_node = next(n for n in data["nodes"] if n["id"] == "layer.tools")
    assert updated_node["last_verified_commit"] == NEW_COMMIT


# ---------------------------------------------------------------------------
# 6. hook not installed
# ---------------------------------------------------------------------------


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def test_check_hooks_reports_not_installed(tmp_path):
    _init_repo(tmp_path)
    ok, message = manage_hooks.check_hooks(tmp_path)
    assert ok is False
    assert "core.hooksPath is not set" in message


def test_check_hooks_reports_wrong_path(tmp_path):
    _init_repo(tmp_path)
    subprocess.run(
        ["git", "config", "core.hooksPath", "some/other/dir"], cwd=tmp_path, check=True
    )
    ok, message = manage_hooks.check_hooks(tmp_path)
    assert ok is False
    assert "expected" in message


def test_install_then_check_reports_installed(tmp_path):
    _init_repo(tmp_path)
    hooks_dir = tmp_path / ".githooks"
    hooks_dir.mkdir()
    hook_file = hooks_dir / "post-merge"
    hook_file.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    hook_file.chmod(0o644)  # deliberately not executable yet

    ok, message = manage_hooks.install_hooks(tmp_path)
    assert ok is True, message

    ok, message = manage_hooks.check_hooks(tmp_path)
    assert ok is True, message

    code, hooks_path = manage_hooks._git(tmp_path, "config", "--get", "core.hooksPath")
    assert code == 0
    assert hooks_path == ".githooks"


def test_install_never_touches_global_config(tmp_path):
    _init_repo(tmp_path)
    hooks_dir = tmp_path / ".githooks"
    hooks_dir.mkdir()
    (hooks_dir / "post-merge").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    manage_hooks.install_hooks(tmp_path)

    # Only the local (repo) config file should have been touched.
    completed = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == ".githooks"


def test_install_fails_closed_when_hook_file_missing(tmp_path):
    _init_repo(tmp_path)
    ok, message = manage_hooks.install_hooks(tmp_path)
    assert ok is False
    assert "does not exist" in message


# ---------------------------------------------------------------------------
# 7. CI failure behavior
# ---------------------------------------------------------------------------


def test_main_exit_code_ok(monkeypatch):
    from tools.context_librarian.refresh_after_merge import RefreshPlan

    monkeypatch.setattr(
        refresh_after_merge,
        "run_refresh",
        lambda *a, **k: RefreshPlan(status="OK", new_commit=NEW_COMMIT, refreshed=(), review_required=()),
    )
    exit_code = refresh_after_merge.main(["--base", "a", "--head", "b", "--check"])
    assert exit_code == 0


def test_main_exit_code_review_required(monkeypatch):
    from tools.context_librarian.refresh_after_merge import RefreshPlan, ReviewItem

    monkeypatch.setattr(
        refresh_after_merge,
        "run_refresh",
        lambda *a, **k: RefreshPlan(
            status="REVIEW_REQUIRED",
            new_commit=NEW_COMMIT,
            refreshed=(),
            review_required=(ReviewItem(category="unknown_canonical_file", detail="x"),),
        ),
    )
    exit_code = refresh_after_merge.main(["--base", "a", "--head", "b", "--check"])
    assert exit_code == 1


def test_main_exit_code_error(monkeypatch):
    from tools.context_librarian.refresh_after_merge import RefreshPlan

    monkeypatch.setattr(
        refresh_after_merge,
        "run_refresh",
        lambda *a, **k: RefreshPlan(
            status="ERROR", new_commit=NEW_COMMIT, refreshed=(), review_required=(), error="boom"
        ),
    )
    exit_code = refresh_after_merge.main(["--base", "a", "--head", "b", "--check"])
    assert exit_code == 2


def test_main_check_mode_never_applies(monkeypatch, tmp_path):
    captured = {}

    def fake_run_refresh(repo_root, *, base_commit, head_commit, apply):
        captured["apply"] = apply
        from tools.context_librarian.refresh_after_merge import RefreshPlan

        return RefreshPlan(status="OK", new_commit=head_commit, refreshed=(), review_required=())

    monkeypatch.setattr(refresh_after_merge, "run_refresh", fake_run_refresh)
    refresh_after_merge.main(["--base", "a", "--head", "b", "--check"])
    assert captured["apply"] is False


def test_main_apply_mode_passes_apply_true(monkeypatch):
    captured = {}

    def fake_run_refresh(repo_root, *, base_commit, head_commit, apply):
        captured["apply"] = apply
        from tools.context_librarian.refresh_after_merge import RefreshPlan

        return RefreshPlan(status="OK", new_commit=head_commit, refreshed=(), review_required=())

    monkeypatch.setattr(refresh_after_merge, "run_refresh", fake_run_refresh)
    refresh_after_merge.main(["--base", "a", "--head", "b", "--apply"])
    assert captured["apply"] is True


def test_run_refresh_error_on_bad_git_range(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "f.py").write_text("1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    with pytest.raises(ContextLibrarianError):
        compute_changed_files(tmp_path, "not-a-real-commit", "HEAD")
