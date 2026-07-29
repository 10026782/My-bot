# test_pilot_preflight.py — smoke tests for tools/context_librarian/pilot_preflight.py
#
# Plain-script test (see CLAUDE.md: "there is no pytest/unittest harness wired
# up"), run directly with `python3 test_pilot_preflight.py`. Exercises the
# preflight gate for docs/governance/librarian/FIRST_REAL_CONSUMPTION_PILOT.md
# against a real, live-recomputed profile (approval_ux) — no mocking of
# tools.context_librarian.librarian, since the whole point of this gate is to
# never drift from what that module actually computes.

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.context_librarian.librarian import (  # noqa: E402
    consumption_checklist,
    load_catalog,
)
from tools.context_librarian.pilot_preflight import run_preflight  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent
TASK_TYPE = "approval_ux"


def _base_ledger(required_sources: list[str]) -> dict:
    return {
        "schema_version": "1.0",
        "task_type": TASK_TYPE,
        "profile": TASK_TYPE,
        "query": "pilot preflight smoke test",
        "production_claim": False,
        "bundle_generated_commit": "0" * 40,
        "bundle_generated_branch": "test-branch",
        "required_sources": required_sources,
        "review_receipts": [],
        "waived_sources": [],
    }


def run() -> bool:
    catalog = load_catalog(REPO_ROOT)
    profile = catalog.profiles[TASK_TYPE]
    live_required = consumption_checklist(catalog, profile, production_claim=False)

    results: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle_path = tmp_path / "bundle.md"
        ledger_path = tmp_path / "ledger.json"

        # 1. Missing bundle -> BLOCKED (exit 1), ledger not even inspected.
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("missing bundle -> exit 1", code == 1))

        bundle_path.write_text("# fake bundle\n", encoding="utf-8")

        # 2. Bundle present, ledger missing -> BLOCKED (exit 2).
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("missing ledger -> exit 2", code == 2))

        # 3. Ledger present but required_sources doesn't match the live tier
        #    -> BLOCKED (exit 3).
        ledger_path.write_text(
            json.dumps(_base_ledger(["code:not_a_real_mandatory_item.py"])),
            encoding="utf-8",
        )
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("required_sources mismatch -> exit 3", code == 3))

        # 4. Ledger's declared task_type disagrees with --task-type -> BLOCKED (exit 2).
        mismatched = _base_ledger(list(live_required))
        mismatched["task_type"] = "tool_execution"
        ledger_path.write_text(json.dumps(mismatched), encoding="utf-8")
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("task_type mismatch -> exit 2", code == 2))

        # 5. Fully matching skeleton -> PROCEED (exit 0).
        ledger_path.write_text(
            json.dumps(_base_ledger(list(live_required))), encoding="utf-8"
        )
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("matching skeleton -> exit 0 (PROCEED)", code == 0))
        results.append(
            ("PROCEED message present", any("PROCEED" in m for m in messages))
        )

        # 6. Invalid JSON ledger -> BLOCKED (exit 2), never crashes.
        ledger_path.write_text("{not json", encoding="utf-8")
        code, messages = run_preflight(
            repo_root=REPO_ROOT,
            task_type=TASK_TYPE,
            production_claim=False,
            bundle_path=bundle_path,
            ledger_path=ledger_path,
        )
        results.append(("invalid JSON ledger -> exit 2", code == 2))

    print("\n=== pilot_preflight smoke tests ===")
    failures = [name for name, passed in results if not passed]
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if failures:
        print(f"\n❌ FAILED: {', '.join(failures)}")
    else:
        print(f"\n✅ {len(results)}/{len(results)} passed")
    return not failures


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
